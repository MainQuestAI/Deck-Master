import {historyLabel} from './history-labels.js';
import {sourceReader, pageContentEditor} from './content-edit.js';
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
import {iconWorkbench} from './icon-workbench.js';
import {Annotations} from './annotations.js';

const pageTitle = (page, index) => `第 ${index + 1} 页 · ${page.title || '未命名页面'}`;
const detail = (title, ...body) => el('details', {class: 'source-detail'}, el('summary', {}, title), ...body);
// 六段制作链：材料来源 → 逐页稿 → 提示词 → 原图 → SVG → PPT，同一页同一固定版本。
const chainStages = [
  {layer: 'source', label: '来源'},
  {layer: 'content', label: '逐页稿'},
  {layer: 'prepared_prompt', label: '提示词'},
  {layer: 'original_image', label: '原图'},
  {layer: 'svg', label: 'SVG'},
  {layer: 'ppt', label: 'PPT 预览'},
];
function chainState(stage) {
  if (!stage || stage.existence === 'not_generated') return '尚未生成';
  if (stage.existence !== 'recorded') return '暂不可读';
  if (stage.applicability?.status === 'basis_changed') return '制作依据已变化';
  return stage.applicability?.status === 'current' ? '可查看' : '适用性待核实';
}
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
function sourceBody(app, data) {
  const node = el('div', {class: 'stack'}, el('p', {}, `本页来源固定在 ${version(data.revision_id)}。`));
  const links = (data.content_plan?.goals || []).flatMap(g => g.source_links || []);
  if (app.health.ui_capabilities?.includes('content_ops.v1')) node.append(...links.map(link => button('查看材料 ' + (link.locator || '原文'), () => sourceReader(app, link, data.revision_id))));
  node.append(data.sources.citations.length ? el('pre', {class: 'evidence-json'}, JSON.stringify(data.sources.citations, null, 2)) : el('p', {class: 'muted'}, '此页未记录材料引用，不能据此补造来源。'),
    button('回到此版本的内容与来源', () => { const dialog = document.querySelector('#modal'); if (dialog.open) dialog.close(); app.go({surface: 'content', revision: data.revision_id}); }));
  return node;
}
function sourceView(app, data) {
  return modal('本页来源', sourceBody(app, data));
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
  if (data.page?.customer_visible && !app.readonly && app.health.ui_capabilities?.includes('content_ops.v1') && data.revision_id === app.route.revision && data.page_id === app.route.page_id) node.append(pageContentEditor(app, data));
  node.append(button('查看本页来源', () => sourceView(app, data))); return node;
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
function sourceLayer(app, data) {
  return el('article', {class: 'page-copy stack'}, el('h2', {}, '本页来源与材料'), sourceBody(app, data));
}
function renderLayer(app, data, layer, title, releases, onBasis) {
  if (layer === 'source') { onBasis?.(null, null); return sourceLayer(app, data); }
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
  const activeStage = layer === 'submitted_prompt' ? 2 : chainStages.findIndex(item => item.layer === layer);
  const stepPage = step => app.summary.pages[index + step];
  const pager = el('div', {class: 'row page-pager'},
    button('← 上一页', () => stepPage(-1) && app.go({page_id: stepPage(-1).page_id}), false,
      {class: 'quiet', disabled: index <= 0, 'aria-label': `上一页，${stepPage(-1) ? pageTitle(stepPage(-1), index - 1) : '没有上一页'}`}),
    button('下一页 →', () => stepPage(1) && app.go({page_id: stepPage(1).page_id}), false,
      {class: 'quiet', disabled: index >= app.summary.pages.length - 1, 'aria-label': `下一页，${stepPage(1) ? pageTitle(stepPage(1), index + 1) : '没有下一页'}`}));
  const node = el('div', {class: 'page-workbench'}, heading(pageTitle(page, index), `${layers[layer]} · ${app.historical ? '历史稿' : '当前稿'}`, pager));
  if (!app.health.ui_capabilities?.includes('page_detail.v1')) return el('div', {}, node, empty('核心需要升级', '单页证据与文本选段需要新版核心。此页面没有写入草稿。'));
  const chain = el('nav', {class: 'chain', 'aria-label': '本页生成链路'});
  const chainStates = [
    data.sources.citations.length ? '可查看' : '记录缺失',
    chainState(data.stages.content),
    (data.prompts.prepared.length || data.prompts.submitted.text !== null || (data.generation?.requests || []).length) ? '可查看' : '记录缺失',
    chainState(data.stages.blueprint),
    chainState(data.stages.svg),
    chainState(data.stages.ppt_preview),
  ];
  chainStages.forEach((item, i) => chain.append(button([el('span', {class: 'chain-number'}, `0${i + 1}`), item.label,
    el('span', {class: 'chain-state'}, chainStates[i])], () => app.go({layer: item.layer}), false,
    {class: i === activeStage ? 'active' : '', 'aria-current': i === activeStage ? 'step' : null,
      'aria-label': `0${i + 1} ${item.label}，${chainStates[i]}`})));
  // Grouped with the other view actions instead of taking a full row of its own
  // above the chain: the page header budget decides how much artwork fits.
  const styleReference = app.health.ui_capabilities?.includes('style_recipes.v1') && data.stages.blueprint.existence === 'recorded'
    ? button('以本页为风格参考', () => {
      app.styleSelection = {reference: {page_id:data.page_id, revision_id:data.revision_id, artifact_ref:data.stages.blueprint.ref, file:data.stages.blueprint.file, role:'reference'}, target_ids:[]};
      app.go({surface:'style', page_id:null, candidate_id:null, task_id:null, revision:app.latest.revision_id});
    }) : null;
  let disposed = false, compareSerial = 0, compareData = null;
  const primaryReleases = [], compareReleases = [];
  app.disposables.push(() => { disposed = true; compareSerial++; primaryReleases.forEach(fn => fn()); compareReleases.forEach(fn => fn()); });
  const selector = el('select', {'aria-label': '转到页面'});
  app.summary.pages.forEach((p, n) => selector.append(el('option', {value: p.page_id}, `第 ${n + 1} / ${app.summary.pages.length} 页`)));
  selector.value = page.page_id; selector.addEventListener('change', () => app.go({page_id: selector.value}));
  pager.prepend(selector);
  const layerSelect = el('select', {class: 'compact-layer-select', 'aria-label': '查看制作图层'},
    chainStages.map((item, i) => el('option', {value: item.layer}, `${item.label} · ${chainStates[i]}`)));
  layerSelect.value = layer === 'submitted_prompt' ? 'prepared_prompt' : layer;
  layerSelect.addEventListener('change', () => app.go({layer: layerSelect.value}));
  const update = el('div', {class: 'notice', role: 'status', hidden: true});
  let lastSync = Date.now(), polling = false;
  const poll = async () => {
    if (polling || disposed || document.hidden) return; polling = true;
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
  const fromSummary = event => {
    if (disposed) return;
    const latest = event.detail; lastSync = Date.now(); update.hidden = latest.revision_id === fixed;
    if (!update.hidden) update.replaceChildren(el('span', {}, '当前稿已更新；这里的页、图层与比较双方仍固定。'),
      button('查看新的当前版本', () => app.go({revision: latest.revision_id})));
  };
  app.root.addEventListener('summary-refreshed', fromSummary);
  const timer = app.health.ui_capabilities?.includes('run_desk.v1') ? null : setInterval(poll, 5000);
  app.disposables.push(() => { clearInterval(timer); app.root.removeEventListener('summary-refreshed', fromSummary); });
  const aside = el('aside', {class: 'page-context stack'}), draftSlot = el('div');
  const noteRecovery = el('div', {class: 'note-recovery-slot'});
  let annotations, draftRef;
  function bindDraft(ref, text) {
    noteRecovery.replaceChildren();
    draftRef = ref;
    app.editor?.dispose(); app.editor = null;
    if (layer === 'source') {
      annotations?.bind(null, null);
      draftSlot.replaceChildren(el('p', {class: 'muted'}, '个人草稿绑定逐页稿或提示词层；来源层只提供阅读。')); return;
    }
    if (layer === 'prepared_prompt' && preparedRecords(data).length > 1 && !ref) {
      annotations?.bind(null, null);
      draftSlot.replaceChildren(el('p', {class: 'muted'}, '请选择明确的预备稿，再写绑定这份原文的个人草稿。')); return;
    }
    const info = {...app.info, page_label: `第 ${index + 1} 页`};
    const samePageBasis = app.latest.pages.find(p => p.page_id === data.page_id)?.stages.content.ref?.sha256 === data.stages.content.ref?.sha256;
    app.editor = new DraftEditor(info, {scope: 'page', page_id: data.page_id, layer}, fixed, ref,
      {readonly: app.business && samePageBasis ? Boolean(app.info.sample?.readonly) : app.readonly, exactRevision: true});
    const draftView = app.editor.mount();
    app.editor.input.rows = 2;
    // Recovery and portability stay a separate secondary entry next to the note,
    // not nested one level deeper behind it.
    const recovery = detail('恢复、下载与版本详情', app.editor.basisNode);
    const download = draftView.querySelector('.panel-body > .row button:last-child');
    if (download) recovery.append(download);
    draftView.querySelectorAll('.recovery-import, .field-help, .draft-restore').forEach(control => recovery.append(control));
    // 维护区顺序：私人笔记与草稿操作（意见面板移交）→ 恢复、下载与版本详情。
    noteRecovery.replaceChildren(...(annotations?.maintenanceNodes || [draftSlot]), recovery);
    draftSlot.replaceChildren(draftView);
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
    const basis = generationBasis(app, data); basis.open = false; aside.append(basis);
  }
  const production = layer === 'svg' || layer === 'ppt' ? detail('可编辑性与制作检查', productionView(data)) : null;
  if (app.business && app.health.ui_capabilities?.includes('annotations.v1') && layer !== 'source') {
    annotations = new Annotations(app, data, layer, original, draftSlot);
    if (app.editor) annotations.bind(app.editor, draftRef);
    // 面板可能在草稿绑定之后才建立：这里把它的维护项补进维护区（顺序在恢复入口之前）。
    noteRecovery.prepend(...annotations.maintenanceNodes);
    aside.append(annotations.node); app.disposables.push(() => annotations.dispose());
  } else aside.append(draftSlot);
  aside.append(noteRecovery);
  if (production) aside.append(production);
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
  let historyCursor = null, historySerial = 0, historyBusy = false, historyLoaded = false, historyShowingAll = false;
  const allHistory = el('input', {type: 'checkbox', 'aria-label': '显示这页全部历史记录'});
  const moreHistory = button('更早的修改', () => loadHistory(false), false, {class: 'history-more', disabled: true});
  const pageLabels = new Map(app.summary.pages.map((item, n) => [item.page_id, `第 ${n + 1} 页`]));
  async function loadHistory(reset = true) {
    if (historyBusy || disposed) return;
    const serial = ++historySerial, all = allHistory.checked;
    const query = new URLSearchParams({revision: fixed, page_id: data.page_id, limit: 20, related_only: all ? '0' : '1'});
    if (!reset && historyCursor) query.set('cursor', historyCursor);
    historyBusy = true; moreHistory.disabled = true; allHistory.disabled = true;
    try {
      const value = await get('/api/history?' + query);
      if (disposed || serial !== historySerial) return;
      if (reset) revisionSelect.replaceChildren(el('option', {value: ''}, '选择这页的修改'));
      const existing = new Set([...revisionSelect.options].map(option => option.value));
      value.revisions.filter(row => row.revision_id !== fixed && !existing.has(row.revision_id)).forEach(row => revisionSelect.append(el('option', {value: row.revision_id}, historyLabel(row, pageLabels))));
      historyCursor = value.pagination?.next_cursor || null; historyLoaded = true; historyShowingAll = all;
      error.textContent = revisionSelect.options.length === 1 ? (historyCursor ? '当前范围尚无这页的其它修改，可继续加载更早记录。' : '此范围没有这页的其它修改。') : '';
    } catch (failure) { if (!disposed && serial === historySerial) { allHistory.checked = historyShowingAll; error.textContent = readableError(failure) + ' 已固定的比较仍保留。'; } }
    finally { if (!disposed && serial === historySerial) { historyBusy = false; moreHistory.disabled = !historyCursor; allHistory.disabled = false; } }
  }
  allHistory.addEventListener('change', () => loadHistory(true));
  compareControls.append(el('div', {class: 'row wrap'}, moreHistory, el('label', {class: 'inline-control'}, allHistory, '全部记录')));
  const openCompare = button('比较此页版本', async () => {
    pageActions.open = false;
    compareControls.hidden = false;
    if (!historyLoaded) await loadHistory(true);
    revisionSelect.focus();
  });
  const closeCompare = button('结束固定比较', () => {
    compareSerial++; compareData = null; compareReleases.splice(0).forEach(fn => fn()); comparison.replaceChildren(); comparison.hidden = true; original.hidden = false;
    compareControls.hidden = true; fixedLabel.hidden = true; reading.classList.remove('is-comparing'); layout.classList.remove('with-fixed-compare'); compareButton.disabled = false;
    pageActions.querySelector('summary').focus();
  }); compareControls.querySelector('.row').append(closeCompare);
  // Escape handles the topmost layer: an open dialog or a fullscreen element wins,
  // then an open fixed comparison ends without the same keypress also leaving the
  // page. Capture phase, because the work-surface handler sits on an ancestor and
  // the focused element may not live inside this view at all.
  const escapeCompare = event => {
    if (event.key !== 'Escape' || !compareData || disposed) return;
    if (document.querySelector('dialog[open]') || document.fullscreenElement) return;
    event.preventDefault(); event.stopPropagation(); closeCompare.click();
  };
  document.addEventListener('keydown', escapeCompare, true);
  app.disposables.push(() => document.removeEventListener('keydown', escapeCompare, true));
  const pageActions = detail('页面操作', el('div', {class: 'stack'}, openCompare, styleReference));
  pageActions.classList.add('page-actions');
  pageActions.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || !pageActions.open) return;
    event.preventDefault(); event.stopPropagation(); pageActions.open = false;
    pageActions.querySelector('summary').focus();
  });
  const toolbar = el('div', {class: 'toolbar reading-toolbar'},
    button('回到整稿画廊', () => app.go({surface: 'gallery'}), false, {class: 'quiet'}), layerSelect, pageActions);
  if (['original_image', 'svg', 'ppt'].includes(layer)) {
    const zoom = el('select', {'aria-label': '阅读缩放'}, [.5, .75, 1, 1.25, 1.5, 2, 3].map(value => el('option', {value}, `${value * 100}%`)));
    zoom.value = String(app.route.zoom || 1); zoom.addEventListener('change', () => {
      const value = Number(zoom.value); node.querySelectorAll('.page-image-viewport>.stack,.page-image-viewport>.pooled-image').forEach(image => { image.style.width = `${value * 100}%`; image.style.height = `${value * 100}%`; });
      app.route.zoom = value; history.replaceState(null, '', routeHash(app.info, app.route)); app.savePosition();
    }); pageActions.querySelector(':scope > div').append(el('label', {}, '阅读缩放 ', zoom));
  }
  const trials = trialActions(app, data);
  if (trials.classList.contains('page-trial-entry')) reading.append(trials);
  node.append(chain, toolbar, update, compareControls, layout, iconWorkbench(app, data)); return node;
}
