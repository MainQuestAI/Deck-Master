import {el, button, heading, empty, version, toast, modal, downloadJSON} from './dom.js';
import {imageView} from './images.js';
import {GalleryMemory} from './gallery-state.js';
import {layers} from './routes.js';
import {canonical} from './api.js';

export const stageKey = {content: 'content', original_image: 'blueprint', svg: 'svg', ppt: 'ppt_preview'};
export const stageLabel = stage => !stage || stage.existence === 'not_generated' ? '未生成' : stage.existence !== 'recorded' ? '暂不可读' :
  stage.applicability?.status === 'basis_changed' ? '依据已变化' : stage.applicability?.status === 'current' ? '可看' : '适用性待核实';
const title = (page, index) => `第 ${index + 1} 页 · ${page.title || '未命名页面'}`;
const layerNames = {original_image: '原图', svg: 'SVG', ppt: 'PPT'};
const statuses = {all: '全部页面', missing: '缺少当前层', stale: '依据已变化', attention: '有个人意见', references: '个人参考页'};

export function gallery(app, data) {
  if (data.unsupported) return el('div', {}, heading('整稿画廊', '当前项目服务需要更新画廊读取能力。'),
    empty('请重启升级后的项目服务', '已保留项目和原有页面。', button('查看制作总览', () => app.go({surface: 'overview'}))));
  const memory = app.galleryMemory ||= new GalleryMemory(app, data.saved);
  const pages = app.summary.pages; const ids = new Set(pages.map(page => page.page_id));
  const plan = data.plan || {};
  const chapters = plan.chapters || [];
  const goals = new Map((plan.goals || []).map(goal => [goal.goal_id, goal.page_id]));
  const chapterPages = new Map(chapters.map(chapter => [chapter.chapter_id, new Set(chapter.goal_ids.map(id => goals.get(id)))]));
  const noted = new Set((data.drafts?.records || []).filter(record => record.draft.target.scope === 'page' && typeof record.draft.content.text === 'string' && record.draft.content.text.trim() &&
    record.draft.base_revision === app.route.revision).map(record => record.draft.target.page_id));
  const selected = memory.state.selected_page_ids.filter(id => ids.has(id));
  const layer = layerNames[app.route.layer] ? app.route.layer : 'original_image';
  const adjusted = {...memory.state, revision_id: app.route.revision, layer, selected_page_ids: selected,
    mode: memory.state.mode === 'compare' && selected.length < 2 ? 'grid' : memory.state.mode,
    anchor: ids.has(memory.state.anchor.page_id) ? memory.state.anchor : {page_id: null, offset: 0},
    filter: {...memory.state.filter, chapter_id: chapterPages.has(memory.state.filter.chapter_id) ? memory.state.filter.chapter_id : null}};
  if (canonical(adjusted) !== canonical(memory.state)) memory.update(adjusted);
  let disposed = false, rowsKey = '', views = [], cards = new Map(), frame, restoring = false, userScrolled = false;
  let focusId = app.galleryFocus || memory.state.anchor.page_id || pages[0]?.page_id;
  const zooms = new Map();
  const state = () => memory.state;
  const stage = page => page.stages[stageKey[state().layer]];
  const filtered = () => pages.filter(page => {
    const filter = state().filter;
    if (filter.chapter_id && !chapterPages.get(filter.chapter_id)?.has(page.page_id)) return false;
    const current = stage(page);
    return filter.status === 'all' || filter.status === 'missing' && current.existence !== 'recorded' ||
      filter.status === 'stale' && current.applicability.status === 'basis_changed' || filter.status === 'attention' && noted.has(page.page_id) ||
      filter.status === 'references' && state().references.some(ref => ref.page_id === page.page_id);
  });
  const node = el('div', {class: 'gallery-view'}, heading('整稿画廊', `${pages.length} 页 · ${version(app.route.revision)} · 同层、固定版本阅读`));
  const status = el('div', {class: 'gallery-save', role: 'status'});
  const summary = el('p', {class: 'gallery-selection', role: 'status'});
  const controls = el('div', {class: 'gallery-controls'});
  const viewPort = el('div', {class: 'gallery-viewport', tabindex: '0', 'aria-label': '整稿画廊阅读区'});
  const topSpace = el('div', {'aria-hidden': true}); const grid = el('div', {class: 'gallery-grid'}); const bottomSpace = el('div', {'aria-hidden': true});
  viewPort.append(topSpace, grid, bottomSpace);
  node.append(controls, summary, status, viewPort, el('p', {class: 'matrix-caption'}, '方向键移动页面焦点，Enter 打开，Escape 从单页返回。个人参考不会自动写入风格方案。'));

  function rememberAnchor() {
    if (disposed || restoring || state().mode === 'compare') return;
    const visible = filtered(), columns = columnsNow(), height = rowHeight();
    const index = Math.min(visible.length - 1, Math.floor(viewPort.scrollTop / height) * columns);
    const anchor = {page_id: visible[index]?.page_id || null, offset: (viewPort.scrollTop % height) / height};
    if (canonical(anchor) !== canonical(state().anchor)) memory.update({anchor});
  }
  function resetReading(patch, preserveAnchor = false) {
    rememberAnchor(); memory.update(patch); rowsKey = ''; renderControls();
    restoring = true; viewPort.scrollTop = state().mode !== 'compare' && preserveAnchor ? anchorTop() : 0; restoring = false; renderRows(true);
    if (!preserveAnchor) rememberAnchor();
  }
  function columnsNow() { return state().mode === 'continuous' ? 1 : state().mode === 'compare' ? state().selected_page_ids.length : innerWidth < 768 ? 1 : state().columns; }
  function rowHeight() { return ((viewPort.clientWidth - 20 - (columnsNow() - 1) * 20) / columnsNow()) * 9 / 16 + 130; }
  function anchorTop() {
    const index = filtered().findIndex(page => page.page_id === state().anchor.page_id);
    return index < 0 ? 0 : (Math.floor(index / columnsNow()) + state().anchor.offset) * rowHeight();
  }
  function open(page) {
    rememberAnchor(); memory.flush(); app.galleryFocus = page.page_id;
    app.go({surface: 'page', page_id: page.page_id, layer: state().layer});
  }
  function toggle(page) {
    const selection = state().selected_page_ids;
    if (!selection.includes(page.page_id) && selection.length === 4) { toast('最多同时选择 4 页。先取消一页后再选择。'); renderRows(true); return; }
    const next = selection.includes(page.page_id) ? selection.filter(id => id !== page.page_id) : [...selection, page.page_id];
    const patch = {selected_page_ids: next};
    if (state().mode === 'compare' && next.length < 2) patch.mode = 'grid';
    memory.update(patch); renderControls(); renderRows(true);
  }
  function reference(page) {
    const references = state().references;
    const existing = references.find(ref => ref.page_id === page.page_id);
    if (existing) memory.update({references: references.filter(ref => ref !== existing)});
    else if (page.stages.blueprint.existence === 'recorded') memory.update({references: [...references, {page_id: page.page_id,
      revision_id: app.route.revision, original_ref: page.stages.blueprint.file}]});
    renderControls(); renderRows(true);
  }
  function renderControls() {
    const s = state();
    const tabs = el('nav', {class: 'layer-tabs', 'aria-label': '画廊图层'});
    for (const [key, label] of Object.entries(layerNames)) tabs.append(button(label, () => { rememberAnchor(); app.go({layer: key}); }, false,
      {'aria-pressed': String(s.layer === key), class: s.layer === key ? 'active' : ''}));
    const modes = el('div', {class: 'row', role: 'group', 'aria-label': '阅读方式'});
    for (const [key, label] of Object.entries({grid: '联系表', continuous: '连续阅读', compare: '并排比较'})) modes.append(button(label,
      () => resetReading({mode: key}, true), false, {'aria-pressed': String(s.mode === key), disabled: key === 'compare' && s.selected_page_ids.length < 2}));
    const columns = el('select', {'aria-label': '联系表列数', disabled: s.mode !== 'grid'}, [2, 3, 4].map(number => el('option', {value: number}, number + ' 列')));
    columns.value = String(s.columns); columns.addEventListener('change', () => resetReading({columns: Number(columns.value)}, true));
    const chapter = el('select', {'aria-label': '筛选章节'}, el('option', {value: ''}, '全部章节'), chapters.map(item => el('option', {value: item.chapter_id}, item.title)));
    chapter.value = s.filter.chapter_id || ''; chapter.addEventListener('change', () => resetReading({filter: {...s.filter, chapter_id: chapter.value || null}}));
    const filter = el('select', {'aria-label': '筛选页面状态'}, Object.entries(statuses).map(([value, text]) => el('option', {value}, text)));
    filter.value = s.filter.status; filter.addEventListener('change', () => resetReading({filter: {...s.filter, status: filter.value}}));
    const extras = el('div', {class: 'row wrap'});
    if (s.mode === 'compare') {
      const sync = el('input', {type: 'checkbox', checked: s.zoom.synchronized, 'aria-label': '同步缩放'});
      sync.addEventListener('change', () => { memory.update({zoom: {...state().zoom, synchronized: sync.checked}}); if (sync.checked) zooms.clear(); renderRows(true); });
      extras.append(el('label', {class: 'inline-control'}, sync, '同步缩放'), button('回到联系表', () => resetReading({mode: 'grid'}, true)));
    }
    if (s.selected_page_ids.length) extras.append(button('清空选页', () => resetReading({selected_page_ids: [], mode: s.mode === 'compare' ? 'grid' : s.mode}, true)));
    if (s.references.length) extras.append(button(`管理参考页（${s.references.length}）`, manageReferences));
    controls.replaceChildren(el('div', {class: 'row between wrap'}, tabs, modes), el('div', {class: 'gallery-filters'}, chapter, filter, columns, extras));
    const shown = new Set(filtered().map(page => page.page_id));
    const outside = s.selected_page_ids.filter(id => !shown.has(id)).length;
    const modeSummary = s.mode === 'compare' ? `并排 ${s.selected_page_ids.length} 页 · 筛选命中 ${shown.size} / ${pages.length} 页` : `显示 ${shown.size} / ${pages.length} 页 · 已选 ${s.selected_page_ids.length} 页`;
    summary.textContent = `${layers[s.layer]} · ${modeSummary}${outside ? ` · 筛选外选中 ${outside} 页，比较仍保留` : ''}`;
  }
  function manageReferences() {
    const list = el('div', {class: 'stack'}, state().references.map(ref => {
      const page = pages.find(item => item.page_id === ref.page_id);
      const row = el('div', {class: 'row between'}, el('span', {}, `${page ? title(page, pages.indexOf(page)) : ref.page_id} · 原图 · ${version(ref.revision_id)}`),
        button('移除参考', () => { memory.update({references: state().references.filter(item => item.page_id !== ref.page_id)}); row.remove(); renderControls(); renderRows(true); }));
      return row;
    }));
    modal('个人参考页', el('div', {class: 'stack'}, el('p', {}, '参考保留选择时的原图与版本。更新当前稿不会自动改换参考图。'), list));
  }
  function card(page, compare = false) {
    const index = pages.indexOf(page), current = stage(page), label = title(page, index);
    const tile = el('article', {class: 'gallery-card', 'data-page-id': page.page_id, 'data-layer': state().layer, 'data-revision': app.route.revision});
    const selected = state().selected_page_ids.includes(page.page_id);
    const check = el('input', {type: 'checkbox', checked: selected, 'aria-label': '选择' + label}); check.addEventListener('change', () => toggle(page));
    const image = el('div', {class: compare ? 'compare-image' : 'gallery-image'});
    const retrySlot = el('div', {class: 'image-retry-slot'});
    if (current.existence === 'recorded' && current.media_type?.startsWith('image/')) {
      const view = imageView(app, current, label + ' · ' + layers[state().layer], {kind: state().mode === 'grid' ? 'thumb' : 'large',
        onFailure: retry => retrySlot.replaceChildren(button('重试图片', () => { retrySlot.replaceChildren(); retry(); }))});
      views.push(view); image.append(view.node);
      if (compare) {
        const scale = state().zoom.synchronized ? state().zoom.scale : zooms.get(page.page_id) || 1;
        view.node.style.width = `${scale * 100}%`;
        view.node.style.height = `${Math.max(120, viewPort.clientHeight - 200) * scale}px`;
        view.node.style.flexShrink = '0';
      }
    } else image.append(el('span', {class: 'missing-layer'}, `${layers[state().layer]} · ${stageLabel(current)}`));
    const openButton = button(image, () => open(page), false, {class: 'gallery-open', 'aria-label': '打开' + label, tabindex: page.page_id === focusId ? '0' : '-1'});
    openButton.addEventListener('focus', () => { focusId = page.page_id; for (const [id, control] of cards) control.tabIndex = id === focusId ? 0 : -1; });
    cards.set(page.page_id, openButton);
    const isRef = state().references.some(ref => ref.page_id === page.page_id);
    tile.append(openButton, retrySlot, el('div', {class: 'gallery-card-info'}, el('label', {class: 'inline-control'}, check, el('strong', {title: label}, label)),
      el('p', {class: 'muted'}, `${current.existence === 'recorded' ? '◉' : '○'} ${layers[state().layer]} · ${stageLabel(current)}${noted.has(page.page_id) ? ' · 有个人意见' : ''}`),
      el('div', {class: 'row between'}, button(isRef ? '★ 个人参考' : '☆ 标记原图参考', () => reference(page), false,
        {class: 'reference-button', 'aria-pressed': String(isRef), disabled: !isRef && page.stages.blueprint.existence !== 'recorded'}),
        current.existence !== 'recorded' && page.execution?.find(task => ['awaiting_host', 'running', 'blocked'].includes(task.status)) &&
          button('查看待办', () => app.go({surface: 'runs', task_id: page.execution.find(task => ['awaiting_host', 'running', 'blocked'].includes(task.status)).task_id})))));
    if (compare) {
      const zoom = el('select', {'aria-label': label + '缩放'}, [.5, .75, 1, 1.25, 1.5, 2, 3].map(value => el('option', {value}, `${value * 100}%`)));
      zoom.value = String(state().zoom.synchronized ? state().zoom.scale : zooms.get(page.page_id) || 1);
      zoom.addEventListener('change', () => {
        if (state().zoom.synchronized) memory.update({zoom: {...state().zoom, scale: Number(zoom.value)}});
        else zooms.set(page.page_id, Number(zoom.value));
        renderRows(true);
      });
      tile.append(el('label', {class: 'inline-control'}, '阅读缩放 ', zoom));
    }
    return tile;
  }
  function renderRows(force = false) {
    if (disposed) return;
    const compare = state().mode === 'compare';
    const visible = compare ? state().selected_page_ids.map(id => pages.find(page => page.page_id === id)).filter(Boolean) : filtered();
    const columns = columnsNow(), height = rowHeight(), count = Math.ceil(visible.length / columns);
    const first = compare ? 0 : Math.max(0, Math.floor(viewPort.scrollTop / height) - (state().mode === 'grid' ? 1 : 0));
    const last = compare ? 1 : Math.min(count, Math.ceil((viewPort.scrollTop + viewPort.clientHeight) / height) + 1);
    const key = [state().mode, state().layer, columns, first, last, ...visible.map(page => page.page_id)].join(':');
    if (!force && key === rowsKey) return;
    const focused = document.activeElement.closest?.('[data-page-id]')?.dataset.pageId;
    rowsKey = key; views.forEach(view => view.dispose()); views = []; cards.clear();
    grid.style.gridTemplateColumns = `repeat(${columns || 1}, minmax(0, 1fr))`;
    grid.style.setProperty('--compare-height', `${Math.max(120, viewPort.clientHeight - 200)}px`);
    grid.classList.toggle('is-comparison', compare); grid.classList.toggle('is-continuous', state().mode === 'continuous');
    topSpace.style.height = `${compare ? 0 : first * height}px`; bottomSpace.style.height = `${compare ? 0 : Math.max(0, count - last) * height}px`;
    grid.style.gridAutoRows = compare ? 'auto' : `${height - 20}px`;
    grid.replaceChildren(...visible.slice(first * columns, last * columns).map(page => card(page, compare)));
    if (!visible.length) grid.append(empty('没有符合筛选的页面', '已选页面仍保留，可更换章节或状态。'));
    viewPort.dataset.mode = state().mode; viewPort.dataset.visiblePages = String(cards.size);
    if (!cards.has(focusId) && cards.size) cards.values().next().value.tabIndex = 0;
    if (focused && cards.has(focused)) cards.get(focused).focus({preventScroll: true});
  }
  function onScroll() {
    cancelAnimationFrame(frame); frame = requestAnimationFrame(() => { renderRows(); if (userScrolled) rememberAnchor(); });
  }
  // Restoring a saved fractional anchor may round to a different pixel in a
  // second window. Reading alone must not turn that rounding into a CAS write.
  for (const event of ['wheel', 'touchstart', 'pointerdown']) viewPort.addEventListener(event, () => { userScrolled = true; }, {passive: true});
  viewPort.addEventListener('scroll', onScroll);
  viewPort.addEventListener('keydown', event => {
    userScrolled = true;
    if (!event.target.classList.contains('gallery-open') && event.target !== viewPort) return;
    const list = state().mode === 'compare' ? state().selected_page_ids.map(id => pages.find(page => page.page_id === id)) : filtered();
    let index = Math.max(0, list.findIndex(page => page.page_id === focusId));
    const offsets = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -columnsNow(), ArrowDown: columnsNow()};
    if (!(event.key in offsets)) return;
    event.preventDefault(); index = Math.max(0, Math.min(list.length - 1, index + offsets[event.key]));
    if (!list[index]) return;
    const nextId = list[index].page_id; focusId = nextId;
    if (!cards.has(nextId)) viewPort.scrollTop = Math.floor(index / columnsNow()) * rowHeight();
    renderRows(true); cards.get(nextId)?.focus({preventScroll: false});
  });
  const unsubscribe = memory.subscribe(() => {
    status.replaceChildren(el('span', {}, memory.message));
    if (memory.error?.code === 'local_state_conflict') status.append(button('比较窗口选择', async () => {
      try {
        const saved = await memory.compareSaved();
        modal('两个窗口的画廊选择', el('div', {class: 'stack'},
          el('p', {}, `此窗口：${state().selected_page_ids.join('、') || '未选页'}；${layers[state().layer]}`),
          el('p', {}, `项目保存：${saved.record?.state.selected_page_ids.join('、') || '未选页'}；${layers[saved.record?.state.layer] || '未记录'}`)),
          [button('保存此窗口选择', () => { memory.useWindow(saved.record); document.querySelector('#modal').close(); }),
            button('读取项目保存的选择', () => { memory.useSaved(saved.record); document.querySelector('#modal').close(); app.go({surface: 'gallery', revision: state().revision_id, layer: state().layer}); })]);
      } catch { toast('暂时无法读取另一个窗口的选择，请恢复连接后重试。'); }
    }));
    else if (memory.error) status.append(button('核实画廊保存', () => memory.retry()));
    if (memory.error) status.append(button('下载画廊选择', () => downloadJSON(state(), 'gallery-selection.json')));
  });
  const fitHeight = () => { viewPort.style.height = `${Math.max(280, innerHeight - viewPort.getBoundingClientRect().top - 64)}px`; };
  const observer = new ResizeObserver(() => { if (!disposed) { rowsKey = ''; renderRows(true); } });
  observer.observe(viewPort);
  const resize = () => { fitHeight(); renderRows(true); };
  addEventListener('resize', resize);
  app.disposables.push(() => { rememberAnchor(); memory.flush(); disposed = true; cancelAnimationFrame(frame); observer.disconnect(); removeEventListener('resize', resize); unsubscribe(); views.forEach(view => view.dispose()); });
  renderControls();
  requestAnimationFrame(() => {
    if (disposed) return;
    fitHeight(); restoring = true; renderRows(true); viewPort.scrollTop = state().mode === 'compare' ? 0 : anchorTop(); renderRows(true); restoring = false;
    if (app.galleryFocus) { cards.get(app.galleryFocus)?.focus({preventScroll: true}); app.galleryFocus = null; }
  });
  return node;
}
