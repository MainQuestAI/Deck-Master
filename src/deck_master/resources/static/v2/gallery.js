import {el, button, heading, empty, version, toast, modal, downloadJSON, icon} from './dom.js';
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
// 连续阅读节距的模块级缓存：跨视图挂载保持同一节距，使 topSpace 与 scrollTop
// 的映射在整个会话内稳定（挂载级首测会随窗口起点漂移，导致锚点恢复失真）。
let continuousPitch = null;
const invalidatePitch = () => { continuousPitch = null; };
// 已记录层的瓷片状态标签：事实来自 stage 投影，不用当前稿补造。
const tileTag = stage => !stage || stage.existence !== 'recorded' ? (stage?.existence === 'not_generated' ? ['尚无产物', ''] : ['暂不可读', 'warn']) :
  stage.applicability?.status === 'basis_changed' ? ['制作依据已变化', 'warn'] :
  stage.applicability?.status === 'current' ? ['当前采用', 'ok'] : ['适用性待核实', 'warn'];

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
  let query = '';
  const zooms = new Map();
  const state = () => memory.state;
  // Responsive reading is a projection: retain the user's desktop mode.
  const narrow = () => innerWidth < 768;
  const effectiveMode = () => narrow() ? 'continuous' : state().mode;
  const readingOffset = () => narrow() ? Math.max(0, -viewPort.getBoundingClientRect().top) : viewPort.scrollTop;
  const setReadingOffset = value => {
    if (narrow()) { const top = viewPort.getBoundingClientRect().top + scrollY; window.scrollTo({top: top + value}); }
    else viewPort.scrollTop = value;
  };
  const readingHeight = () => narrow() ? innerHeight : viewPort.clientHeight;
  const stage = page => page.stages[stageKey[state().layer]];
  const orderOf = new Map(pages.map((page, index) => [page.page_id, index]));
  const recordCount = key => pages.reduce((total, page) => total + (page.stages[stageKey[key]].existence === 'recorded' ? 1 : 0), 0);
  const matchesQuery = page => {
    if (!query) return true;
    const index = orderOf.get(page.page_id), label = `${index + 1} ${String(index + 1).padStart(2, '0')} ${page.title || '未命名页面'}`;
    return label.toLowerCase().includes(query.toLowerCase());
  };
  const filtered = () => pages.filter(page => {
    const filter = state().filter;
    if (filter.chapter_id && !chapterPages.get(filter.chapter_id)?.has(page.page_id)) return false;
    if (!matchesQuery(page)) return false;
    const current = stage(page);
    return filter.status === 'all' || filter.status === 'missing' && current.existence !== 'recorded' ||
      filter.status === 'stale' && current.applicability.status === 'basis_changed' || filter.status === 'attention' && noted.has(page.page_id) ||
      filter.status === 'references' && state().references.some(ref => ref.page_id === page.page_id);
  });
  const node = el('div', {class: 'gallery-view'}, heading('整稿画廊', `${pages.length} 页 · 浏览作品与比较修改`));
  const status = el('div', {class: 'gallery-save', role: 'status'});
  const legend = el('div', {class: 'legend gallery-legend', role: 'status'});
  const hint = el('p', {class: 'form-hint', hidden: true});
  const controls = el('div', {class: 'gallery-controls'});
  const viewPort = el('div', {class: 'gallery-viewport', tabindex: '0', 'aria-label': '整稿画廊阅读区'});
  const topSpace = el('div', {'aria-hidden': true}); const grid = el('div', {class: 'gallery'}); const bottomSpace = el('div', {'aria-hidden': true});
  viewPort.append(topSpace, grid, bottomSpace);
  node.append(controls, legend, status, hint, viewPort, el('p', {class: 'matrix-caption'}, '方向键移动页面焦点，Enter 打开，Escape 从单页返回。个人参考不会自动写入风格方案。'));

  function rememberAnchor() {
    if (disposed || restoring || effectiveMode() === 'compare') return;
    const visible = filtered(), columns = columnsNow(), height = rowHeight();
    const offset = readingOffset();
    const index = Math.min(visible.length - 1, Math.floor(offset / height) * columns);
    const anchor = {page_id: visible[index]?.page_id || null, offset: (offset % height) / height};
    if (canonical(anchor) !== canonical(state().anchor)) memory.update({anchor});
  }
  function resetReading(patch, preserveAnchor = false) {
    if (patch.mode && patch.mode !== state().mode) invalidatePitch();
    rememberAnchor(); memory.update(patch); rowsKey = ''; renderControls();
    // 先渲染新模式瓷片再测量：连续节距首测若发生在旧模式 DOM 上，会把网格
    // 瓷片高写入模块级缓存并污染整个会话的虚拟化（评审 reading-P1b）。
    restoring = true; renderRows(true);
    if (!narrow() || preserveAnchor) setReadingOffset(effectiveMode() !== 'compare' && preserveAnchor ? anchorTop() : 0);
    renderRows(true); restoring = false;
    if (!preserveAnchor) rememberAnchor();
  }
  // 列数按可用宽度计算，与当前控件选择保持一致。
  function columnsNow() {
    if (effectiveMode() === 'continuous') return 1;
    if (effectiveMode() === 'compare') return Math.max(1, state().selected_page_ids.length);
    // 每张作品至少保留 280px，空间不足时降低实际列数。
    const width = viewPort.clientWidth - 20;
    return Math.max(1, Math.min(state().columns, Math.floor((width + 20) / 300)));
  }
  function rowHeight() {
    if (effectiveMode() === 'continuous') {
      // 连续节距的唯一事实源是 renderRows 尾部的 DOM 实测校准；这里只读缓存，
      // 未校准时用几何估算回落（与实测差 ~1px）。绝不在渲染前测量写入——
      // 那会测到上一模式的旧瓷片并污染整个会话（终审 reading-P1b）。
      return continuousPitch || Math.min(920, viewPort.clientWidth - 20) * 9 / 16 + 130;
    }
    return ((viewPort.clientWidth - 20 - (columnsNow() - 1) * 20) / columnsNow()) * 9 / 16 + 130;
  }
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
    if (effectiveMode() === 'compare' && next.length < 2) patch.mode = 'grid';
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
    const settingsOpen = Boolean(controls.querySelector('.gallery-reading-settings')?.open);
    const isNarrow = narrow(), mode = effectiveMode();
    const tabs = el('div', {class: 'segmented', role: 'group', 'aria-label': '画廊图层'});
    for (const [key, label] of Object.entries(layerNames)) tabs.append(button(`${label} ${recordCount(key)}/${pages.length}`,
      () => { rememberAnchor(); app.go({layer: key}); }, false,
      {'aria-pressed': String(s.layer === key), class: s.layer === key ? 'active' : ''}));
    const modes = el('div', {class: 'segmented', role: 'group', 'aria-label': '阅读方式'});
    for (const [key, label] of Object.entries({grid: '联系表', continuous: '连续阅读', compare: '并排比较'})) modes.append(button(label,
      () => resetReading({mode: key}, true), false, {'aria-pressed': String(mode === key), class: mode === key ? 'active' : '',
        disabled: isNarrow && key !== 'continuous' || key === 'compare' && s.selected_page_ids.length < 2}));
    const columns = el('div', {class: 'segmented', role: 'group', 'aria-label': '联系表列数', hidden: mode !== 'grid' || isNarrow});
    for (const number of [2, 3, 4]) columns.append(button(`${number} 列`, () => resetReading({columns: number}, true), false,
      {'data-columns': number, 'aria-pressed': String(columnsNow() === number), class: columnsNow() === number ? 'active' : ''}));
    const chapter = el('select', {'aria-label': '筛选章节'}, el('option', {value: ''}, '全部章节'), chapters.map(item => el('option', {value: item.chapter_id}, item.title)));
    chapter.value = s.filter.chapter_id || ''; chapter.addEventListener('change', () => resetReading({filter: {...s.filter, chapter_id: chapter.value || null}}));
    const filter = el('select', {'aria-label': '筛选页面状态'}, Object.entries(statuses).map(([value, text]) => el('option', {value}, text)));
    filter.value = s.filter.status; filter.addEventListener('change', () => resetReading({filter: {...s.filter, status: filter.value}}));
    const extras = el('div', {class: 'row wrap'});
    if (mode === 'compare') {
      const sync = el('input', {type: 'checkbox', checked: s.zoom.synchronized, 'aria-label': '同步缩放'});
      sync.addEventListener('change', () => { memory.update({zoom: {...state().zoom, synchronized: sync.checked}}); if (sync.checked) zooms.clear(); renderRows(true); });
      extras.append(el('label', {class: 'inline-control'}, sync, '同步缩放'), button('回到联系表', () => resetReading({mode: 'grid'}, true)));
    }
    if (s.selected_page_ids.length) extras.append(button('清空选页', () => resetReading({selected_page_ids: [], mode: s.mode === 'compare' ? 'grid' : s.mode}, true)));
    if (s.references.length) extras.append(button(`管理参考页（${s.references.length}）`, manageReferences));
    if (s.selected_page_ids.length && app.health.ui_capabilities?.includes('style_recipes.v1')) extras.append(button('用选页开始风格校准', () => {
      const first = pages.find(p => p.page_id === s.selected_page_ids[0]);
      app.styleSelection = {reference: first.stages.blueprint.existence === 'recorded' ? {page_id:first.page_id, revision_id:app.route.revision, artifact_ref:first.stages.blueprint.ref, file:first.stages.blueprint.file, role:'reference'} : null,
        project_identity:app.info.project_identity, revision:app.route.revision,
        target_ids:s.selected_page_ids.slice(1), target_refs:s.selected_page_ids.slice(1).map(id => ({page_id:id, page_ref:pages.find(page => page.page_id === id).stages.content.ref}))};
      app.go({surface:'style', page_id:null, candidate_id:null, task_id:null, revision:app.route.revision});
    }, false, {disabled:app.readonly}));
    const filters = el('div', {class: 'row wrap gallery-filter-fields'}, chapter, filter, searchSlot, modes, columns, extras);
    if (isNarrow) {
      const expanded = Boolean(query || s.filter.chapter_id || s.filter.status !== 'all');
      controls.replaceChildren(tabs, el('details', {class: 'gallery-filter-disclosure', open: expanded}, el('summary', {}, expanded ? '筛选作品（已筛选）' : '筛选作品与管理选页'), filters));
    } else {
      const settings = el('details', {class: 'gallery-reading-settings', open: settingsOpen}, el('summary', {}, '阅读设置'),
        el('div', {class: 'stack'}, modes, columns));
      controls.replaceChildren(el('div', {class: 'row wrap'}, tabs, searchSlot, settings),
        el('div', {class: 'row wrap'}, chapter, filter, extras));
    }
    renderLegend();
  }
  function renderLegend() {
    const s = state();
    const shown = new Set(filtered().map(page => page.page_id));
    const outside = s.selected_page_ids.filter(id => !shown.has(id)).length;
    const stale = [...shown].reduce((total, id) => total + (pages.find(page => page.page_id === id)?.stages[stageKey[s.layer]]?.applicability?.status === 'basis_changed' ? 1 : 0), 0);
    const counts = effectiveMode() === 'compare' ? `并排 ${s.selected_page_ids.length} 页 · 筛选命中 ${shown.size} / ${pages.length} 页`
      : `显示 ${shown.size} / ${pages.length} 页 · 已选 ${s.selected_page_ids.length} 页`;
    // replaceChildren 不做子节点过滤：布尔条件必须先组数组，避免渲染出 "false" 文本。
    const parts = [el('span', {}, '当前显示：', el('strong', {}, layers[s.layer])),
      el('span', {class: 'muted'}, `${counts}${outside ? ` · 筛选外选中 ${outside} 页，比较仍保留` : ''}`)];
    if (stale > 0) parts.push(el('span', {class: 'accent'}, `${stale} 页依据已变化`));
    const text = parts.map(part => part.textContent).join('\u0000');
    if (text !== legend.dataset.text) { legend.dataset.text = text; legend.replaceChildren(...parts); }
  }
  const searchSlot = el('span', {class: 'gallery-search'});
  const search = el('input', {'aria-label': '搜索页面', placeholder: '搜索页码或标题'});
  let searchTimer, preSearchAnchor = null;
  search.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      if (search.value === query) return;
      // 先按旧过滤保存真实阅读位置；锚点计算必须与当前过滤/滚动一致，不写临时乱值。
      rememberAnchor();
      if (!query && search.value) preSearchAnchor = {...state().anchor};
      query = search.value;
      if (!query && preSearchAnchor) { memory.update({anchor: preSearchAnchor}); preSearchAnchor = null; }
      rowsKey = '';
      restoring = true; renderRows(true);
      setReadingOffset(effectiveMode() !== 'compare' ? anchorTop() : 0);
      restoring = false;
    }, 120);
  });
  searchSlot.append(search);
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
    const index = orderOf.get(page.page_id), current = stage(page), label = title(page, index);
    const tile = el('article', {class: 'slide-tile', 'data-page-id': page.page_id, 'data-layer': state().layer, 'data-revision': app.route.revision});
    const selected = state().selected_page_ids.includes(page.page_id);
    const check = el('input', {type: 'checkbox', checked: selected, 'aria-label': '选择' + label}); check.addEventListener('change', () => toggle(page));
    const [tagText, tagClass] = tileTag(current);
    const image = el('div', {class: compare ? 'compare-image' : 'gallery-image'});
    const retrySlot = el('div', {class: 'image-retry-slot'});
    if (current.existence === 'recorded' && current.media_type?.startsWith('image/')) {
      const view = imageView(app, current, label + ' · ' + layers[state().layer], {kind: effectiveMode() === 'grid' ? 'thumb' : 'large',
        onFailure: retry => retrySlot.replaceChildren(button('重试图片', () => { retrySlot.replaceChildren(); retry(); }))});
      views.push(view); image.append(view.node);
      if (compare) {
        const scale = state().zoom.synchronized ? state().zoom.scale : zooms.get(page.page_id) || 1;
        view.node.style.width = `${scale * 100}%`;
        view.node.style.height = `${Math.max(120, viewPort.clientHeight - 200) * scale}px`;
        view.node.style.flexShrink = '0';
      }
    } else image.append(el('div', {class: 'empty-artifact'}, el('span', {class: 'empty-symbol'}, icon('minus')),
      el('strong', {}, layers[state().layer]), el('span', {}, stageLabel(current))));
    const cover = button(image, () => open(page), false, {class: 'slide-cover',
      'aria-label': '打开' + label, tabindex: page.page_id === focusId ? '0' : '-1'});
    cover.addEventListener('focus', () => { focusId = page.page_id; for (const [id, control] of cards) control.tabIndex = id === focusId ? 0 : -1; });
    cards.set(page.page_id, cover);
    const isRef = state().references.some(ref => ref.page_id === page.page_id);
    const chapter = chapters.find(item => chapterPages.get(item.chapter_id)?.has(page.page_id));
    const runningTask = page.execution?.find(task => ['awaiting_host', 'running', 'blocked'].includes(task.status));
    tile.append(cover, retrySlot,
      el('div', {class: 'tile-title'}, el('strong', {title: label}, el('span', {class: 'mono'}, String(index + 1).padStart(2, '0')), page.title || '未命名页面'),
        el('label', {class: 'inline-control tile-select'}, check, '比较')),
      el('div', {class: 'tile-meta'}, el('span', {class: `status ${tagClass}`}, tagText),
        chapter && el('span', {}, chapter.title), noted.has(page.page_id) && el('span', {class: 'accent'}, '有个人意见'),
        el('span', {class: 'tile-actions'},
          button(isRef ? '★ 个人参考' : '☆ 标记参考', () => reference(page), false,
            {class: 'reference-button', 'aria-pressed': String(isRef), disabled: !isRef && page.stages.blueprint.existence !== 'recorded'}),
          runningTask && button('查看待办', () => app.go({surface: 'runs', task_id: runningTask.task_id}), false, {class: 'text-link'}))));
    if (compare) {
      const zoom = el('select', {'aria-label': label + '缩放'}, [.5, .75, 1, 1.25, 1.5, 2, 3].map(value => el('option', {value}, `${value * 100}%`)));
      zoom.value = String(state().zoom.synchronized ? state().zoom.scale : zooms.get(page.page_id) || 1);
      zoom.addEventListener('change', () => {
        if (state().zoom.synchronized) memory.update({zoom: {...state().zoom, scale: Number(zoom.value)}});
        else zooms.set(page.page_id, Number(zoom.value));
        renderRows(true);
      });
      tile.append(el('label', {class: 'inline-control compare-zoom'}, '阅读缩放 ', zoom));
    }
    return tile;
  }
  function renderRows(force = false) {
    if (disposed) return;
    const compare = effectiveMode() === 'compare';
    const visible = compare ? state().selected_page_ids.map(id => pages.find(page => page.page_id === id)).filter(Boolean) : filtered();
    const columns = columnsNow(), height = rowHeight(), count = Math.ceil(visible.length / columns);
    const first = compare ? 0 : Math.max(0, Math.floor(readingOffset() / height) - (effectiveMode() === 'grid' ? 1 : 0));
    const last = compare ? 1 : Math.min(count, first + (narrow() ? 4 : Infinity), Math.ceil((readingOffset() + readingHeight()) / height) + 1);
    const key = [effectiveMode(), state().layer, columns, first, last, query, ...visible.map(page => page.page_id)].join(':');
    if (!force && key === rowsKey) return;
    const activeElement = document.activeElement;
    const focused = activeElement.closest?.('[data-page-id]')?.dataset.pageId;
    const focusSelector = activeElement.matches?.('.tile-select input') ? '.tile-select input' : activeElement.matches?.('.reference-button') ? '.reference-button' : '.slide-cover';
    rowsKey = key; views.forEach(view => view.dispose()); views = []; cards.clear();
    grid.classList.toggle('continuous', effectiveMode() === 'continuous');
    grid.classList.toggle('is-comparison', compare);
    grid.style.setProperty('--gallery-columns', compare ? String(Math.max(1, columns)) : String(columns));
    controls.querySelectorAll('[data-columns]').forEach(control => {
      const active = Number(control.dataset.columns) === columns;
      control.setAttribute('aria-pressed', String(active)); control.classList.toggle('active', active);
    });
    grid.style.removeProperty('grid-template-columns');
    if (compare) grid.style.setProperty('grid-template-columns', `repeat(${columns || 1}, minmax(0, 1fr))`);
    // 设计降级提示：实际列数低于所选列数时说明原因（读屏与视觉同源）。
    const downgraded = !compare && effectiveMode() === 'grid' && columns !== state().columns;
    hint.hidden = !downgraded;
    if (downgraded) hint.textContent = `适应当前窗口，显示为 ${columns} 列。`;
    grid.style.setProperty('--compare-height', `${Math.max(120, viewPort.clientHeight - 200)}px`);
    topSpace.style.height = `${compare ? 0 : first * height}px`; bottomSpace.style.height = `${compare ? 0 : Math.max(0, count - last) * height}px`;
    grid.style.gridAutoRows = compare ? 'auto' : `${height - 24}px`;
    grid.replaceChildren(...visible.slice(first * columns, last * columns).map(page => card(page, compare)));
    if (!visible.length) grid.append(empty(query ? '没有匹配的页面' : '没有符合筛选的页面', query ? '可更换搜索词，或清除搜索查看全部。' : '已选页面仍保留，可更换章节或状态。'));
    renderLegend();
    viewPort.dataset.mode = effectiveMode(); viewPort.dataset.visiblePages = String(cards.size);
    // 连续模式渲染后校准节距：窗口内相邻瓷片的实测 top 差是唯一事实源。
    // 校准发生在 replaceChildren 之后，测到的必是当前模式瓷片；后续滚动/
    // 锚点计算随下一次渲染自然收敛到同一节距。
    if (effectiveMode() === 'continuous') {
      const rendered = [...grid.querySelectorAll('.slide-tile')];
      if (rendered.length >= 2) {
        const pitch = rendered[1].getBoundingClientRect().top - rendered[0].getBoundingClientRect().top;
        if (pitch > 200 && Math.abs(pitch - (continuousPitch || 0)) > 0.5) continuousPitch = pitch;
      }
    }
    if (!cards.has(focusId) && cards.size) cards.values().next().value.tabIndex = 0;
    if (focused && cards.has(focused)) cards.get(focused).closest('.slide-tile').querySelector(focusSelector)?.focus({preventScroll: true});
  }
  function alignAnchorTile() {
    // 仅连续模式需要解析式校正：网格模式 anchorTop() 的行基公式本身正确，
    // 而这里的平铺索引×节距推导在多列布局下不成立（评审 reading-P1a）。
    const anchor = state().anchor;
    if (disposed || effectiveMode() !== 'continuous' || !anchor.page_id) return;
    const anchorIndex = filtered().findIndex(page => page.page_id === anchor.page_id);
    if (anchorIndex < 0) return;
    const tiles = [...grid.querySelectorAll('.slide-tile')];
    const tile = grid.querySelector(`[data-page-id="${anchor.page_id}"]`);
    const measured = tile && tiles[tiles.indexOf(tile) + 1]
      ? tiles[tiles.indexOf(tile) + 1].getBoundingClientRect().top - tile.getBoundingClientRect().top
      : (tile ? tile.getBoundingClientRect().height : 0) + 32;
    // 实测节距写回会话缓存后再定位+重渲染：topSpace=first×pitch 与分片位移
    // 同基准，瓷片高度不均时落点误差不再随锚点序号放大（评审 reading-P2）。
    const pitch = Math.max(200, measured);
    continuousPitch = pitch;
    setReadingOffset(anchorIndex * pitch + Math.min(anchor.offset * pitch, pitch - 1));
    renderRows(true);
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
    if (!event.target.classList.contains('slide-cover') && event.target !== viewPort) return;
    const list = effectiveMode() === 'compare' ? state().selected_page_ids.map(id => pages.find(page => page.page_id === id)) : filtered();
    let index = Math.max(0, list.findIndex(page => page.page_id === focusId));
    const offsets = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -columnsNow(), ArrowDown: columnsNow()};
    if (!(event.key in offsets)) return;
    event.preventDefault(); index = Math.max(0, Math.min(list.length - 1, index + offsets[event.key]));
    if (!list[index]) return;
    const nextId = list[index].page_id; focusId = nextId;
    if (!cards.has(nextId)) setReadingOffset(Math.floor(index / columnsNow()) * rowHeight());
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
  const fitHeight = () => { viewPort.style.height = narrow() ? 'auto' : `${Math.max(280, innerHeight - viewPort.getBoundingClientRect().top - 64)}px`; };
  const pageScroll = () => { if (narrow()) { userScrolled = true; onScroll(); } };
  addEventListener('scroll', pageScroll, {passive: true});
  const observer = new ResizeObserver(() => { if (!disposed) { rowsKey = ''; renderRows(true); } });
  observer.observe(viewPort);
  let previousNarrow = narrow();
  const resize = () => {
    const changedLayout = previousNarrow !== narrow(); previousNarrow = narrow();
    invalidatePitch(); fitHeight(); renderControls(); restoring = true; renderRows(true);
    if (changedLayout && (state().anchor.offset || state().anchor.page_id && state().anchor.page_id !== filtered()[0]?.page_id)) { setReadingOffset(anchorTop()); renderRows(true); }
    restoring = false;
  };
  addEventListener('resize', resize);
  app.disposables.push(() => { rememberAnchor(); memory.flush(); disposed = true; cancelAnimationFrame(frame); observer.disconnect(); removeEventListener('resize', resize); removeEventListener('scroll', pageScroll); unsubscribe(); views.forEach(view => view.dispose()); });
  renderControls();
  requestAnimationFrame(() => {
    if (disposed) return;
    fitHeight(); restoring = true; renderRows(true);
    if (!narrow() || state().anchor.offset || state().anchor.page_id && state().anchor.page_id !== filtered()[0]?.page_id) setReadingOffset(effectiveMode() === 'compare' ? 0 : anchorTop());
    renderRows(true); restoring = false;
    if (!narrow() || readingOffset() > 0) alignAnchorTile();
    if (app.galleryFocus) { cards.get(app.galleryFocus)?.focus({preventScroll: true}); app.galleryFocus = null; }
  });
  return node;
}
