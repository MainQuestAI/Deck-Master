import {get, revisionQuery, canonical} from './api.js';
import {el, button, heading, empty, version, sortHeading, icon, disabledReason, modal, downloadJSON} from './dom.js';
import {imageView} from './images.js';
import {layers} from './routes.js';
import {stageKey} from './gallery.js';
import {openAction} from './action-targets.js';
import {batchActions} from './batch-actions.js';
import {OverviewMemory} from './overview-state.js';
import {routeHash} from './routes.js';

// A03 总览：待办与矩阵全部来自 B01 的实时投影（next_actions/attention/prompt_summary），
// 不硬编码页数、不出现无证据的风格结论；矩阵保持普通 Tab 顺序（设计系统第 07 节）。
const kindLabels = {verify_execution: '执行待核实', handoff: '制作任务待交接', inspect_failure: '失败待查看',
  replan: '需重新计划', compare_candidates: '候选待决定', reconcile_inputs: '输入待协调',
  prepare_stage: '产物待补齐', refresh_stage: '产物依据已变化', review_results: '结果待阅读', review_quality: '质量记录待查看'};
const nextLabels = {verify_execution: '去核实', handoff: '去交接', inspect_failure: '查看失败', replan: '重新计划',
  compare_candidates: '比较候选', reconcile_inputs: '去协调', prepare_stage: '去补齐', refresh_stage: '查看依据',
  review_results: '去阅读', review_quality: '查看记录'};
const reasonLabels = {unknown_calls_recorded: '任务记录了未知调用；先核实原执行，未确认前不要重复派发。',
  running_task_stale: '任务已运行超过 30 分钟，状态待核实；超时不等于失败。',
  running_task_unclaimed: '运行中的任务缺少执行标识，需核实接手记录。',
  task_failed: '执行失败；当前稿件保留，可调整要求后重试。',
  task_superseded: '任务已由新任务接续；查看当前任务后再操作。',
  task_awaiting_host: '要求已保存，尚未开始；复制制作要求到制作工具执行。',
  task_unreadable: '任务记录损坏，已隔离；其余记录不受影响。',
  candidate_pending: '候选已返回，当前版本保留；比较后再决定是否采用。',
  candidate_unreadable: '候选记录损坏，已隔离；仍计入待决定。',
  content_needs_reconciliation: '新输入与当前内容尚未对齐；先看影响再决定。',
  stage_missing: '上游内容已就绪，该层尚未生成。',
  stage_basis_changed: '该层的生成依据与当前上游版本不同。已有产物仍可阅读，请查看依据后决定是否重新试作。',
  quality_reviews_recorded: '已记录质量检查；查看结论与范围。',
  task_results_ready: '结果已返回待阅读；查看不代表采用。'};
const routeLayer = {blueprint: 'original_image', svg: 'svg', svg_preview: 'svg', ppt_preview: 'ppt', pptx: 'ppt'};
const layerKeys = ['content', 'original_image', 'svg', 'ppt'];

function actionRoute(action) {
  if (['prepare_stage', 'refresh_stage'].includes(action.kind) && action.page_ids?.length === 1 && routeLayer[action.layer])
    return {surface: 'page', page_id: action.page_ids[0], layer: routeLayer[action.layer]};
  if (action.kind === 'reconcile_inputs') return {surface: 'content'};
  return {surface: 'runs'};
}
function todoTitle(action) {
  const base = kindLabels[action.kind] || action.kind;
  return action.page_ids?.length ? `${action.page_ids.length} 页${base}` : base;
}
function reasonText(action) {
  return (reasonLabels[action.reason_code] || action.reason_code || '') +
    (action.blocked_reason === 'candidate_unreadable' ? ' 候选记录损坏，已隔离。' : '');
}
function todoMeta(app, action) {
  const pages = (action.page_ids || []).map(id => {
    const index = app.summary.pages.findIndex(page => page.page_id === id);
    return index < 0 ? id : index + 1;
  });
  if (!pages.length) return '项目级事项';
  return pages.length > 4 ? `第 ${pages.slice(0, 4).join('、')} 等共 ${pages.length} 页` : `第 ${pages.join('、')} 页`;
}
function todoButton(app, action, primary = false) {
  const blocked = action.enabled === false;
  const precise = app.health.ui_capabilities?.includes('action_targets.v1');
  return disabledReason(button((nextLabels[action.kind] || '查看') + (precise ? '' : ' · 通用入口'), () => openAction(app, action, actionRoute(action)), primary,
    {disabled: blocked}), blocked ? '该项记录暂不可读（已隔离），先处理其它待办。' : '');
}

function todoPanel(app) {
  const block = app.summary.next_actions;
  if (block?.status === 'recorded' && block.actions?.length) {
    const [first, ...rest] = block.actions;
    const node = el('section', {class: 'overview-todos', 'aria-label': '制作待办'},
      el('div', {class: 'todo-priority'},
        el('div', {class: 'row between'}, el('span', {class: 'todo-kicker'}, '优先处理'),
          el('span', {class: 'status'}, kindLabels[first.kind] || first.kind)),
        el('h2', {}, todoTitle(first)), el('p', {}, reasonText(first)),
        el('div', {class: 'todo-bottom'}, el('span', {}, todoMeta(app, first)), todoButton(app, first, true))),
      el('div', {class: 'todo-secondary'},
        el('div', {class: 'todo-list-head'}, el('h3', {}, '接下来'), el('span', {}, `${rest.length} 类事项`)),
        rest.length ? rest.map(action => el('article', {class: 'todo-row'},
          el('div', {}, el('h3', {}, todoTitle(action)), el('p', {}, reasonText(action))), todoButton(app, action)))
          : el('p', {class: 'muted'}, '处理当前优先事项后，继续核对整稿。')));
    return node;
  }
  if (!block) {
    // 旧核心没有待办投影：读模式引导，不臆断项目没有内容
    return el('section', {class: 'overview-todos todo-clear'},
      el('h2', {}, '当前核心未提供待办投影'),
      el('p', {}, '升级核心后，这里会显示按真实事实排序的待办。现在可从整稿与下方矩阵阅读制作状态。'),
      button('查看整稿', () => app.go({surface: 'gallery'})));
  }
  const readable = block.readable;
  return el('section', {class: 'overview-todos todo-clear'},
    el('h2', {}, '当前没有记录到制作待办'),
    el('p', {}, readable?.scope === 'deck_pages' ? '各页产物记录齐备。可继续检查整稿内容与交付要求。' : '此版本没有记录到待办动作。'),
    readable?.scope === 'deck_pages' ? button('查看整稿', () => app.go({surface: 'gallery'})) : button('查看矩阵', () => document.querySelector('.matrix-wrap')?.scrollIntoView({block: 'center'})));
}

function promptState(page) {
  const prompt = page.prompt_summary;
  if (!prompt) return 'unknown';
  const blocks = ['submitted', 'frozen', 'prepared'].map(key => prompt[key]).filter(Boolean);
  if (blocks.some(block => block.status === 'recorded'))
    return blocks.some(block => (block.unreadable_count || 0) > 0) ? 'partial' : 'ready';
  if (blocks.some(block => block.status === 'unreadable')) return 'unreadable';
  return 'missing';
}
// 提示词列沿用设计稿文案：缺失是"记录缺失"而非"尚未生成"；部分损坏显示待核实。
const promptView = state => ({ready: {icon: 'check', text: '已就绪'}, partial: {icon: 'attention', text: '记录待核实'},
  unreadable: {icon: 'attention', text: '记录待核实'}, missing: {icon: 'attention', text: '记录缺失'},
  unknown: {icon: 'attention', text: '待核实'}}[state]);
function stageState(stage) {
  if (!stage || stage.existence === 'not_generated') return 'missing';
  if (stage.existence !== 'recorded') return 'unreadable';
  if (stage.applicability?.status === 'basis_changed') return 'stale';
  // 与画廊口径一致：无可验证的存储绑定时只声明"待核实"，不断言已就绪
  return stage.applicability?.status === 'current' ? 'ready' : 'unknown';
}
const cellView = state => ({ready: {icon: 'check', text: '已就绪'}, missing: {icon: 'minus', text: '尚未生成'},
  stale: {icon: 'attention', text: '依据已变化'}, unreadable: {icon: 'attention', text: '暂不可读'},
  unknown: {icon: 'attention', text: '依据待核实'}}[state]);

export function overview(app, data = {}) {
  const pages = app.summary.pages;
  const root = el('div', {});
  if (!pages.length) {
    root.append(heading('制作总览', '项目已建立，还没有页面内容。'),
      empty('先把内容整理清楚', '补充材料并交接内容整理后，这里会出现逐页内容与制作状态。',
        button('去整理内容', () => app.go({surface: 'content'}), true)));
    return root;
  }
  const blueprintCount = pages.filter(page => page.stages.blueprint?.existence === 'recorded').length;
  root.append(heading('制作总览',
    `${pages.length} 页内容 · ${blueprintCount} 页已有原图`,
    button('查看整稿', () => app.go({surface: 'gallery'}), true)));
  root.append(el('details', {class: 'overview-state-help'}, el('summary', {}, '如何理解制作状态'), el('p', {}, '依据已变化表示上游内容更新；可先查看已有作品，再决定检查或修改。候选返回后需要比较采用；工程检查和人工认可分别记录。')));
  const todo=todoPanel(app);root.append(todo);
  const sync=event=>{const next=event.detail;if(next.revision_id===app.summary.revision_id&&next.reading_etag!==app.summary.reading_etag){app.summary=next;const updated=todoPanel(app);root.querySelector('.overview-todos')?.replaceWith(updated);}};app.root.addEventListener('summary-refreshed',sync);app.disposables.push(()=>app.root.removeEventListener('summary-refreshed',sync));
  root.append(matrixPanel(app, data.overview));
  return root;
}

function matrixPanel(app, saved) {
  const pages = app.summary.pages;
  const pageIndex = new Map(pages.map((page, index) => [page.page_id, index]));
  const needsWork = page => (page.attention?.items?.length || 0) > 0 || promptState(page) === 'missing';
  const thumbs = new Map();
  let chapterTitleOf = () => null;
  const memory = new OverviewMemory(app, saved);
  let filter = memory.state.filter, search = memory.state.search, ascending = memory.state.sort === 'ascending', disposed = false, tableState = null;
  // D1：选择随个人阅读状态持久化。改变筛选只改变可见范围，不再清空选择；
  // 筛选外选择始终有计数，只有「清除选择」或移除受限页才改变选择集合。
  // localStorage（项目键）承载跨刷新/版本前进的连续性；ui_overview 的
  // selected_page_ids 字段保存该版本阅读的选择记录（恢复的不是可提交计划）。
  const pageIdSet = new Set(pages.map(page => page.page_id));
  const selectionKey = 'deck-master:overview-selection:' + app.info.project_identity;
  let storedSelection = [];
  try { storedSelection = JSON.parse(localStorage.getItem(selectionKey) || '[]'); } catch { /* 选择是阅读辅助，读不到就从空开始 */ }
  const selected = new Set([...(memory.state.selected_page_ids || []), ...storedSelection].filter(id => pageIdSet.has(id)));
  const count = el('span', {class: 'muted', role: 'status'});
  const selectionNote = el('span', {class: 'muted', role: 'status'});
  const clearButton = button('清除选择', () => { selected.clear(); batch.invalidate(); saveSelection(); render(); });
  const searchInput = el('input', {type: 'search', value:search, maxLength:200, placeholder: '搜索页码或标题', 'aria-label': '搜索页码或标题', autocomplete: 'off'});
  const filterAll = button('', () => setFilter('all'), false, {'aria-pressed': 'true'});
  const filterTodo = button('只看需要处理', () => setFilter('todo'), false, {'aria-pressed': 'false'});
  const allCheckbox = el('input', {type: 'checkbox', 'aria-label': '选择当前筛选内所有可操作页面'});
  const table = el('table', {class: 'matrix', 'aria-label': '逐页制作进展'});
  let batch;
  batch = batchActions(app, selected, () => { if (batch) { saveSelection(); render(); } });
  const preferenceStatus = el('p', {role:'status', class:'muted overview-preference-status'});
  const compareButton = button('核实总览偏好', async () => {
    compareButton.disabled = true;
    try {
      const result = await memory.verify(); if (disposed || result.confirmed) return;
      const stored = result.saved;
      const description = value => el('p', {class:'read-text'}, `搜索：${value?.search || '未设置'}\n范围：${value?.filter === 'todo' ? '只看需要处理' : '全部页面'}\n页序：${value?.sort === 'descending' ? '从后向前' : '从前向后'}`);
      modal('总览阅读偏好：选择保留哪一份', el('div', {class:'stack'},
        el('p', {}, '当前输入保留。读取或保存偏好不会改变稿件、选页任务或调用。'),
        el('h3', {}, '此窗口'), description(memory.state),
        el('h3', {}, '项目保存的偏好'), description(stored.record?.state),
        el('details', {}, el('summary', {}, '固定版本与恢复详情'), el('pre', {class:'evidence-json'}, JSON.stringify({window:memory.state, saved:stored.record}, null, 2)))),
        [button('读取项目保存的偏好', () => { document.querySelector('#modal').close(); memory.useSaved(stored); reflectURL(); }),
          button('明确保存此窗口偏好', () => { document.querySelector('#modal').close(); memory.useWindow(stored); })]);
    } catch { if (!disposed) preferenceStatus.textContent = '总览偏好核实未完成，当前输入保留；连接恢复后重试。'; }
    finally { compareButton.disabled = false; }
  });
  const downloadButton = button('下载总览偏好副本', () => downloadJSON(memory.state, 'deck-master-overview-preferences.json'));
  function reflectURL() { app.route.overview_preferences = {search,filter,sort:ascending ? 'ascending' : 'descending'}; history.replaceState(null, '', routeHash(app.info, app.route)); }
  function saveSelection() {
    try { localStorage.setItem(selectionKey, JSON.stringify([...selected])); } catch { /* 选择保留在本页，未写入本机 */ }
    memory.update({search,filter,sort:ascending ? 'ascending' : 'descending',selected_page_ids:[...selected]});
    reflectURL();
  }
  function saveReading() { saveSelection(); }

  function setFilter(value) {
    if (filter === value) return;
    filter = value;
    batch.invalidate();
    saveReading();
    render();
  }
  function visiblePages() {
    const term = search.trim().toLowerCase();
    const list = pages.filter(page => (!term || `${page.page_id} ${page.title || ''}`.toLowerCase().includes(term))
      && (filter === 'all' || needsWork(page)));
    return ascending ? list : [...list].reverse();
  }
  function cellButton(page, layer, view, extraLayer) {
    return button([icon(view.icon), el('span', {}, view.text)], () => app.go({surface: 'page', page_id: page.page_id, layer: extraLayer || layer}),
      false, {class: `cell-btn ${view.icon === 'attention' ? 'warn' : view.icon === 'minus' ? 'empty' : ''}`,
        'aria-label': `第 ${pageIndex.get(page.page_id) + 1} 页，${layers[layer]}，${view.text}`});
  }
  function nextButton(page) {
    const item = page.attention?.items?.[0];
    const identity = canonical([page.page_id, item ? item.action_id || item : 'view_page']);
    if (!item) return button('查看页面', () => app.go({surface: 'page', page_id: page.page_id, layer: 'content'}), false,
      {class: 'quiet', 'data-matrix-next': identity});
    const blocked = item.enabled === false;
    return disabledReason(button((nextLabels[item.kind] || '查看') + (app.health.ui_capabilities?.includes('action_targets.v1') ? '' : ' · 通用入口'), () => openAction(app, item, actionRoute(item)), false,
      {disabled: blocked, 'data-matrix-next': identity}), blocked ? '该项记录暂不可读（已隔离）。' : '');
  }
  function render() {
    // Rebuilding rows must keep keyboard users on the same control. Only
    // restore focus owned by this table; asynchronous reads must not steal it
    // from the search field, navigation or a dialog.
    const focused = document.activeElement;
    const focusLabel = table.contains(focused) ? focused.getAttribute('aria-label') : null;
    const focusSort = table.contains(focused) && focused.matches('th[aria-sort] button');
    const focusNext = table.contains(focused) ? focused.getAttribute('data-matrix-next') : null;
    const list = visiblePages();
    const operable = list.filter(batch.eligible);
    count.textContent = `${list.length} / ${pages.length} 页`;
    filterAll.textContent = `全部 ${pages.length} 页`;
    filterTodo.textContent = `只看需要处理 ${pages.filter(needsWork).length} 页`;
    filterAll.classList.toggle('active', filter === 'all');
    filterAll.setAttribute('aria-pressed', String(filter === 'all'));
    filterTodo.classList.toggle('active', filter === 'todo');
    filterTodo.setAttribute('aria-pressed', String(filter === 'todo'));
    const hiddenSelected = selected.size ? [...selected].filter(id => !list.some(page => page.page_id === id)).length : 0;
    selectionNote.textContent = selected.size
      ? `已选择 ${selected.size} 页${hiddenSelected ? `，当前筛选外 ${hiddenSelected} 页` : ''}`
      : '未选择页面';
    clearButton.disabled = !selected.size;
    clearButton.hidden = !selected.size;
    selectionNote.hidden = !selected.size;
    allCheckbox.checked = operable.length > 0 && operable.every(page => selected.has(page.page_id));
    allCheckbox.indeterminate = operable.some(page => selected.has(page.page_id)) && !allCheckbox.checked;
    allCheckbox.disabled = !operable.length;

    // Batch eligibility and preference messages still synchronize on every
    // refresh. Equal matrix facts must not replace keyboard-owned controls.
    batch.render();
    preferenceStatus.textContent = memory.message; compareButton.hidden = !memory.error; downloadButton.hidden = !memory.error;
    const nextTableState = canonical([filter, search, ascending, list.map(page => [page.page_id,
      page.attention?.items?.[0] || null, selected.has(page.page_id), batch.eligible(page), chapterTitleOf(page.page_id)])]);
    if (nextTableState === tableState) return;
    tableState = nextTableState;

    const head = el('tr', {},
      el('th', {scope: 'col'}, el('label', {class: 'check-target'}, allCheckbox)),
      sortHeading('页面', ascending ? 'ascending' : 'descending', () => { ascending = !ascending; batch.invalidate(); saveReading(); render(); }),
      el('th', {scope: 'col'}, layers.content), el('th', {scope: 'col'}, '提示词'),
      el('th', {scope: 'col'}, layers.original_image), el('th', {scope: 'col'}, layers.svg),
      el('th', {scope: 'col'}, layers.ppt), el('th', {scope: 'col'}, '下一步'));
    const body = el('tbody');
    if (!list.length) {
      body.append(el('tr', {}, el('td', {colspan: 8}, el('div', {class: 'matrix-empty stack'},
        el('h3', {}, '没有符合条件的页面'), el('p', {}, '尝试其他页码或标题，或清除筛选查看全部页面。已选页面不受筛选影响。'),
        button('清除筛选', () => { search = ''; searchInput.value = ''; filter = 'all'; batch.invalidate(); saveReading(); render(); })))));
    }
    let lastChapter = Symbol();
    for (const page of list) {
      const chapter = chapterTitleOf(page.page_id);
      if (chapter !== null && chapter !== lastChapter) {
        lastChapter = chapter;
        body.append(el('tr', {class: 'chapter-row'}, el('th', {scope: 'rowgroup', colspan: 8}, chapter)));
      }
      const number = String(pageIndex.get(page.page_id) + 1).padStart(2, '0');
      const thumb = el('span', {class: 'matrix-thumbnail', 'aria-hidden': true});
      const blueprint = page.stages.blueprint;
      if (blueprint?.existence === 'recorded' && blueprint.file) {
        // 复用同一页的缩略图视图：render 重建表格不重新占用图片池
        let view = thumbs.get(page.page_id);
        if (!view) {
          view = imageView(app, blueprint, `第 ${number} 页缩略图`, {kind: 'thumb'});
          thumbs.set(page.page_id, view);
          app.disposables.push(view.dispose);
        }
        thumb.append(view.node);
      } else thumb.append(icon('minus'));
      const row = el('tr', {},
        el('td', {}, el('label', {class: 'check-target'}, el('input', {type: 'checkbox',
          checked: selected.has(page.page_id), disabled: !batch.eligible(page) && !selected.has(page.page_id),
          'aria-label': `选择第 ${number} 页`, onchange: event => {
            if (event.target.checked) selected.add(page.page_id); else selected.delete(page.page_id);
            batch.invalidate(); saveSelection(); render();
          }}))),
        el('th', {scope: 'row'}, button([thumb, el('span', {class: 'mono faint'}, number), el('span', {}, page.title || '未命名页面')],
          () => app.go({surface: 'page', page_id: page.page_id, layer: 'original_image'}),
          false, {class: 'title-button', 'aria-label': `打开第 ${number} 页`})),
        el('td', {}, cellButton(page, 'content', cellView(stageState(page.stages[stageKey.content])))),
        el('td', {}, cellButton(page, 'prepared_prompt', promptView(promptState(page)), 'prepared_prompt')),
        el('td', {}, cellButton(page, 'original_image', cellView(stageState(page.stages[stageKey.original_image])))),
        el('td', {}, cellButton(page, 'svg', cellView(stageState(page.stages[stageKey.svg])))),
        el('td', {}, cellButton(page, 'ppt', cellView(stageState(page.stages[stageKey.ppt])))),
        el('td', {class: 'matrix-next'}, nextButton(page)));
      body.append(row);
    }
    table.replaceChildren(el('thead', {}, head), body);
    const replacement = focusSort ? table.querySelector('th[aria-sort] button')
      : focusNext ? table.querySelector(`[data-matrix-next="${CSS.escape(focusNext)}"]`)
      : focusLabel ? table.querySelector(`[aria-label="${CSS.escape(focusLabel)}"]`) : null;
    if (replacement && !replacement.disabled) replacement.focus({preventScroll:true});
  }
  searchInput.addEventListener('input', () => { search = searchInput.value; batch.invalidate(); saveReading(); render(); });
  allCheckbox.addEventListener('change', () => {
    for (const page of visiblePages().filter(batch.eligible)) {
      if (allCheckbox.checked) selected.add(page.page_id); else selected.delete(page.page_id);
    }
    batch.invalidate(); saveSelection(); render();
  });

  // 章节行来自 content plan 的固定投影；读取失败或没有计划时矩阵仍完整，只是没有章节分组。
  const unsubscribe = memory.subscribe(() => {
    if (filter !== memory.state.filter || search !== memory.state.search || ascending !== (memory.state.sort === 'ascending')) {
      filter = memory.state.filter; search = memory.state.search; searchInput.value = search; ascending = memory.state.sort === 'ascending'; batch.invalidate();
    }
    render();
  });
  const readingSync=event=>{const next=event.detail;if(next.revision_id!==app.route.revision)return;let changed=false;for(const page of pages){const fresh=next.pages.find(p=>p.page_id===page.page_id);if(fresh&&canonical(page.attention)!==canonical(fresh.attention)){page.attention=fresh.attention;changed=true;}}if(changed)render();};app.root.addEventListener('summary-refreshed',readingSync);
  app.disposables.push(() => { disposed = true; unsubscribe(); memory.dispose();app.root.removeEventListener('summary-refreshed',readingSync); });
  (async () => {
    try {
      const plan = await get('/api/content-plan' + revisionQuery(app.route.revision));
      if (disposed) return;
      const goalChapter = new Map();
      for (const chapter of plan.content_plan?.chapters || [])
        for (const goalId of chapter.goal_ids || []) goalChapter.set(goalId, chapter.title || chapter.chapter_id);
      const pageChapter = new Map();
      for (const goal of plan.content_plan?.goals || [])
        if (goal.page_id) pageChapter.set(goal.page_id, goalChapter.get(goal.goal_id) ?? null);
      chapterTitleOf = pageId => pageChapter.get(pageId) ?? null;
      render();
    } catch { /* 章节分组保持关闭，不影响矩阵与待办 */ }
  })();

  const node = el('section', {class: 'stack', 'aria-label': '逐页制作进展'},
    el('div', {class: 'section-head'}, el('h2', {}, '逐页制作进展'), count),
    el('div', {class: 'toolbar'}, el('div', {class: 'segmented', role: 'group', 'aria-label': '页面筛选'}, filterAll, filterTodo),
      el('div', {class: 'row wrap matrix-search'}, searchInput, batch.toolbar, selectionNote, clearButton)),
    el('div', {class:'row wrap overview-preferences'}, preferenceStatus, compareButton, downloadButton),
    el('div', {class: 'matrix-wrap'}, table),
    el('div', {class: 'matrix-caption'},
      el('span', {}, icon('check'), ' 可查看　', icon('attention'), ' 需要处理　', icon('minus'), ' 尚未生成'),
      el('span', {}, '按 Tab 访问产物与操作；窄屏可横向滚动查看完整进度。')), batch.node);
  render();
  return node;
}
