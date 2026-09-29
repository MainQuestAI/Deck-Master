import {get, revisionQuery, readableError} from './api.js';
import {el, button, heading, empty, version, modal} from './dom.js';
import {layers, routeHash} from './routes.js';
import {DraftEditor} from './drafts.js';
import {imageView} from './images.js';
import {stageKey, stageLabel} from './gallery.js';
import {promptView, generationBasis, preparedRecords} from './request-view.js';
import {textObject} from './text-selection.js';
import {diffView} from './text-diff.js';
import {productionView} from './production-view.js';
import {trialActions} from './trial-actions.js';
import {candidateDesk} from './candidate-desk.js';
import {Annotations} from './annotations.js';

const pageTitle = (page, index) => `第 ${index + 1} 页 · ${page.title || '未命名页面'}`;
const detail = (title, ...body) => el('details', {class: 'source-detail'}, el('summary', {}, title), ...body);
function bulletItems(items) {
  return el('ul', {}, items.map(item => el('li', {}, typeof item === 'string' ? item : item.text, item.children?.length ? bulletItems(item.children) : null)));
}
function bodyBlocks(blocks) {
  return (blocks || []).map(block => {
    if (block.type === 'paragraph') return el('p', {}, block.text);
    if (block.type === 'bullets') return el('section', {}, block.heading && el('h3', {}, block.heading), bulletItems(block.items));
    if (block.type === 'table') return el('div', {class: 'table-scroll'}, el('table', {class: 'body-table'}, block.title && el('caption', {}, block.title),
      el('thead', {}, el('tr', {}, block.columns.map(col => el('th', {scope: 'col'}, col.label)))),
      el('tbody', {}, block.rows.map(row => el('tr', {}, block.columns.map(col => el('td', {}, row.cells.find(cell => cell.column_id === col.id)?.display_text || '')))))));
    return el('p', {class: 'muted'}, '这个内容块暂不可读。');
  });
}
function sourceView(app, data) {
  const node = el('div', {class: 'stack'}, el('p', {}, `本页来源固定在 ${version(data.revision_id)}。`));
  node.append(data.sources.citations.length ? el('pre', {class: 'evidence-json'}, JSON.stringify(data.sources.citations, null, 2)) : el('p', {class: 'muted'}, '此页未记录材料引用，不能据此补造来源。'),
    button('回到此版本的内容与来源', () => { document.querySelector('#modal').close(); app.go({surface: 'content', revision: data.revision_id}); }));
  return node;
}
function contentView(app, data) {
  const visible = data.page?.customer_visible;
  const node = el('article', {class: 'page-copy stack'}, el('h2', {}, visible?.title || '逐页稿暂不可读'),
    visible?.subtitle && el('p', {}, visible.subtitle), visible?.body_blocks?.length ? bodyBlocks(visible.body_blocks) : el('p', {class: 'muted'}, '此页未记录正文块。'),
    ['callouts', 'labels', 'footnotes'].flatMap(key => (visible?.[key] || []).map(item => el('p', {class: key}, item.text))));
  const sources = data.text_sources?.content || [];
  if (sources.length) {
    const select = el('select', {'aria-label': '选择原文文本对象'}, sources.map((source, i) => el('option', {value: i}, `${i + 1} · ${source.text.slice(0, 42) || '空文本'}`)));
    const textSlot = el('div');
    const show = () => textSlot.replaceChildren(textObject(app, sources[Number(select.value)], {revision: data.revision_id, pageId: data.page_id, layer: 'content', label: '正文原文'}));
    select.addEventListener('change', show); show();
    node.append(detail('正文原文与精确选段', el('label', {}, '选择文字对象 ', select), textSlot));
  }
  node.append(button('查看本页来源', () => modal('本页来源', sourceView(app, data)))); return node;
}
function imageLayer(app, data, layer, title, releases) {
  const stage = data.stages[stageKey[layer]];
  const viewport = el('div', {class: 'page-image-viewport', tabindex: '0', 'aria-label': `${layers[layer]}阅读画布`});
  if (stage?.existence === 'recorded' && stage.media_type?.startsWith('image/')) {
    const view = imageView(app, stage, title + ' · ' + layers[layer], {kind: 'large'});
    view.node.style.width = `${(app.route.zoom || 1) * 100}%`; view.node.style.height = `${(app.route.zoom || 1) * 100}%`;
    releases.push(() => view.dispose()); viewport.append(view.node);
  } else viewport.append(empty(`${layers[layer]}${stageLabel(stage)}`, layer === 'ppt' ? '整稿制作后才会有此版本的逐页 PPT 预览。单页 SVG 预览不会替代它。' : '这一层没有可读图像，可查看逐页稿或任务记录。',
    button('查看逐页稿', () => app.go({layer: 'content', revision: data.revision_id, page_id: data.page_id}))));
  return el('div', {class: 'stack'}, el('p', {class: 'muted'}, stageLabel(stage)), viewport,
    layer === 'svg' && el('p', {class: 'muted'}, 'SVG 安全图像预览；这里没有自由编辑或 OCR 文字层。'),
    layer === 'ppt' && el('p', {class: 'muted'}, '整稿制作后的按页 PPT 预览，按此快照读取；不是单页独立 PPT 编译。'));
}
function renderLayer(app, data, layer, title, releases, onBasis) {
  if (layer === 'content') { onBasis?.(data.stages.content.ref, null); return contentView(app, data); }
  if (layer === 'prepared_prompt' || layer === 'submitted_prompt') {
    const scoped = Object.create(app); scoped.disposables = releases;
    return promptView(scoped, data, layer, onBasis);
  }
  onBasis?.(data.stages[stageKey[layer]]?.ref || null, null);
  return imageLayer(app, data, layer, title, releases);
}
export function pageDetail(app, data) {
  if (app.route.candidate_id) return candidateDesk(app, data);
  const index = app.summary.pages.findIndex(p => p.page_id === data.page_id);
  const page = app.summary.pages[index], layer = app.route.layer, fixed = data.revision_id;
  const node = el('div', {class: 'page-workbench'}, heading(pageTitle(page, index), `${layers[layer]} · ${version(fixed)} · 固定阅读基准`));
  if (!app.health.ui_capabilities?.includes('page_detail.v1')) return el('div', {}, node, empty('核心需要升级', '单页证据与文本选段需要新版核心。此页面没有写入草稿。'));
  let disposed = false, compareSerial = 0, compareData = null;
  const primaryReleases = [], compareReleases = [];
  app.disposables.push(() => { disposed = true; compareSerial++; primaryReleases.forEach(fn => fn()); compareReleases.forEach(fn => fn()); });
  const selector = el('select', {'aria-label': '转到页面'});
  app.summary.pages.forEach((p, n) => selector.append(el('option', {value: p.page_id}, pageTitle(p, n))));
  selector.value = page.page_id; selector.addEventListener('change', () => app.go({page_id: selector.value}));
  const tabs = el('nav', {class: 'layer-tabs', 'aria-label': '页面层'}, button('来源', () => modal('本页来源', sourceView(app, data))));
  for (const value of ['content', 'prepared_prompt', 'submitted_prompt', 'original_image', 'svg', 'ppt']) tabs.append(button(layers[value], () => app.go({layer: value}), false,
    {'aria-current': value === layer ? 'page' : null, class: value === layer ? 'active' : ''}));
  const update = el('div', {class: 'notice', role: 'status', hidden: true});
  let lastSync = Date.now(), polling = false;
  const poll = async () => {
    if (polling || disposed) return; polling = true;
    try {
      const latest = await get('/api/view/summary'); if (disposed) return;
      lastSync = Date.now();
      if (latest.revision_id === fixed) update.hidden = true;
      if (latest.revision_id !== fixed) {
        update.hidden = false; update.replaceChildren(el('span', {}, '当前稿已更新；这里的页、图层与比较双方仍固定。'),
          button('查看新的当前版本', () => app.go({revision: latest.revision_id})));
      }
    } catch {
      if (!disposed) { update.hidden = false; update.textContent = '服务暂时断线，保留已读内容。最后同步：' + new Date(lastSync).toLocaleTimeString(); }
    } finally { polling = false; }
  };
  const timer = setInterval(poll, 5000); app.disposables.push(() => clearInterval(timer));
  const aside = el('aside', {class: 'page-context stack'}), draftSlot = el('div');
  let annotations, draftRef;
  function bindDraft(ref, text) {
    draftRef = ref;
    app.editor?.dispose(); app.editor = null;
    if (layer === 'prepared_prompt' && preparedRecords(data).length > 1 && !ref) {
      annotations?.bind(null, null);
      draftSlot.replaceChildren(el('p', {class: 'muted'}, '请选择明确的预备稿，再写绑定这份原文的个人草稿。')); return;
    }
    const info = {...app.info, page_label: `第 ${index + 1} 页`};
    const samePageBasis = app.latest.pages.find(p => p.page_id === data.page_id)?.stages.content.ref?.sha256 === data.stages.content.ref?.sha256;
    app.editor = new DraftEditor(info, {scope: 'page', page_id: data.page_id, layer}, fixed, ref,
      {readonly: app.business && samePageBasis ? Boolean(app.info.sample?.readonly) : app.readonly});
    draftSlot.replaceChildren(app.editor.mount());
    annotations?.bind(app.editor, ref);
    if (text !== null) draftSlot.append(button('比较原文与草稿', () => {
      if (app.editor?.draft.base_ref?.sha256 !== ref?.sha256) { modal('草稿依据不同', el('p', {}, '恢复的草稿属于另一份原文，请先选择对应基准。')); return; }
      modal('原文与个人草稿', diffView(text, app.editor.input.value, '已记录原文（只读）', '个人草稿（未提交）'));
    }));
  }
  const original = el('section', {class: 'page-reading stack', 'aria-label': '页面内容', 'data-revision': fixed, 'data-page-id': data.page_id},
    renderLayer(app, data, layer, pageTitle(page, index), primaryReleases, bindDraft));
  const fixedLabel = el('h2', {class: 'fixed-side-label', hidden: true}, `原固定版本 · ${version(fixed)} · ${layers[layer]}`);
  original.prepend(fixedLabel);
  const comparison = el('section', {class: 'page-reading stack compare-side', 'aria-label': '比较版本内容', hidden: true});
  const reading = el('div', {class: 'fixed-page-pair'}, original, comparison);
  if (layer === 'original_image' || layer === 'prepared_prompt' || layer === 'submitted_prompt') {
    const basis = generationBasis(app, data); basis.open = layer === 'original_image'; aside.append(basis);
  }
  if (layer === 'svg' || layer === 'ppt') aside.append(productionView(data));
  if (app.business && app.health.ui_capabilities?.includes('annotations.v1')) {
    annotations = new Annotations(app, data, layer, original, draftSlot);
    if (app.editor) annotations.bind(app.editor, draftRef);
    aside.append(annotations.node); app.disposables.push(() => annotations.dispose());
  } else aside.append(draftSlot);
  const layout = el('div', {class: 'page-columns'}, reading, aside);
  const compareControls = el('div', {class: 'fixed-compare-controls stack', hidden: true});
  const error = el('p', {class: 'field-error', role: 'status'});
  const revisionSelect = el('select', {'aria-label': '选择同页比较版本'});
  const mode = el('select', {'aria-label': '固定比较显示方式'}, el('option', {value: 'side'}, '并排'), el('option', {value: 'toggle'}, '切换'));
  const toggle = button('显示比较版本', () => {
    const other = original.hidden === false; original.hidden = other; comparison.hidden = !other;
    toggle.textContent = other ? '显示原固定版本' : '显示比较版本';
  }); toggle.hidden = true;
  function displayMode() {
    const stacked = mode.value === 'toggle' || innerWidth < 1280;
    reading.classList.toggle('is-comparing', Boolean(compareData) && !stacked);
    original.hidden = false; comparison.hidden = !compareData || stacked;
    toggle.hidden = !compareData || !stacked; toggle.textContent = '显示比较版本';
  }
  mode.addEventListener('change', displayMode); addEventListener('resize', displayMode); app.disposables.push(() => removeEventListener('resize', displayMode));
  const compareButton = button('固定比较这个版本', async () => {
    const serial = ++compareSerial, revision = revisionSelect.value; if (!revision) return;
    error.textContent = '正在读取所选版本；已读内容保持原样。'; compareButton.disabled = true;
    try {
      const other = await get('/api/pages/' + encodeURIComponent(data.page_id) + '/lineage' + revisionQuery(revision));
      if (disposed || serial !== compareSerial) return;
      if (other.revision_id !== revision || other.page_id !== data.page_id) throw new Error('返回的页或版本不匹配，未替换比较内容。');
      compareReleases.splice(0).forEach(fn => fn()); compareData = other;
      comparison.replaceChildren(el('h2', {}, `比较版本 · ${version(revision)} · ${layers[layer]}`), renderLayer(app, other, layer, pageTitle(page, index), compareReleases));
      if (layer === 'original_image') {
        const scoped = Object.create(app); scoped.disposables = compareReleases;
        const basis = generationBasis(scoped, other); basis.open = false; comparison.append(basis);
      } else if (layer === 'svg' || layer === 'ppt') comparison.append(productionView(other));
      comparison.dataset.revision = revision;
      layout.classList.add('with-fixed-compare'); fixedLabel.hidden = false; error.textContent = '';
      displayMode();
    } catch (failure) { if (!disposed && serial === compareSerial) error.textContent = readableError(failure) + ' 已读的固定一侧或双方仍保留。'; }
    finally { if (serial === compareSerial) compareButton.disabled = false; }
  });
  compareControls.append(el('p', {class: 'muted'}, `同一页、同一层；左侧固定 ${version(fixed)}。窄窗口使用切换阅读。`),
    el('div', {class: 'row'}, revisionSelect, compareButton, mode, toggle), error);
  const openCompare = button('比较此页版本', async () => {
    compareControls.hidden = false;
    try {
      const history = await get('/api/history'); if (disposed) return;
      revisionSelect.replaceChildren(el('option', {value: ''}, '选择已提交版本'), ...history.revisions.filter(r => r.revision_id !== fixed).map(r => el('option', {value: r.revision_id}, version(r.revision_id))));
      if (revisionSelect.options.length === 1) error.textContent = '还没有其它已提交版本。';
    } catch (failure) { error.textContent = readableError(failure); }
  });
  const closeCompare = button('结束固定比较', () => {
    compareSerial++; compareData = null; compareReleases.splice(0).forEach(fn => fn()); comparison.replaceChildren(); comparison.hidden = true; original.hidden = false;
    compareControls.hidden = true; fixedLabel.hidden = true; reading.classList.remove('is-comparing'); layout.classList.remove('with-fixed-compare'); compareButton.disabled = false;
  }); compareControls.querySelector('.row').append(closeCompare);
  const toolbar = el('div', {class: 'toolbar'}, selector, button('回到整稿画廊', () => app.go({surface: 'gallery'})), openCompare);
  if (['original_image', 'svg', 'ppt'].includes(layer)) {
    const zoom = el('select', {'aria-label': '阅读缩放'}, [.5, .75, 1, 1.25, 1.5, 2, 3].map(value => el('option', {value}, `${value * 100}%`)));
    zoom.value = String(app.route.zoom || 1); zoom.addEventListener('change', () => {
      const value = Number(zoom.value); node.querySelectorAll('.page-image-viewport>.stack,.page-image-viewport>.pooled-image').forEach(image => { image.style.width = `${value * 100}%`; image.style.height = `${value * 100}%`; });
      app.route.zoom = value; history.replaceState(null, '', routeHash(app.info, app.route)); app.savePosition();
    }); toolbar.append(el('label', {}, '阅读缩放 ', zoom));
  }
  node.append(toolbar, tabs, update, compareControls, layout, trialActions(app, data)); return node;
}
