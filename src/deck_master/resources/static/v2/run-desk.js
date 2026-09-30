import {cancelRecovery} from './run-recovery.js';
import {get, readableError, revisionQuery, fileURL} from './api.js';
import {el, button, empty, version, modal, loading, errorNote, disabledReason} from './dom.js';

const names = {compose: '整理内容', blueprint: '制作原图', svg: '制作 SVG', render: '渲染预览', repair: '局部修改', review: '检查', export: '准备文件'};
const statuses = {queued: '等待执行', awaiting_host: '待交接', running: '已记录处理中', completed: '结果已记录', failed: '执行失败', cancelled: '已取消', superseded: '由新任务接续', unreadable: '记录无法读取'};
const actions = {handoff: '需要交接', verify_unknown_call: '核实未知调用', verify_execution: '核实原执行', inspect_failure: '查看失败原因', replan: '按当前依据重新计划', compare_candidates: '候选待决定', review_results: '结果待阅读'};
const seenKey = task => JSON.stringify([task.task_id, task.result_refs?.map(ref => ref.sha256)]);
const clock = value => value ? new Date(value).toLocaleString('zh-CN', {hour12: false}) : '未记录';

export function runDesk(app, data) {
  const recovery = cancelRecovery(app);
  const root = el('section', {class: 'panel run-desk', 'aria-label': '运行记录'});
  const rows = el('div', {class: 'run-rows stack'}), pager = el('div', {class: 'row wrap run-pagination'});
  const notice = el('div', {role: 'status', class: 'muted run-notice'});
  const detail = el('div', {class: 'run-detail stack'});
  const group = el('select', {'aria-label': '按修改组筛选'}), status = el('select', {'aria-label': '按执行状态筛选'}, el('option', {value: ''}, '所有执行状态'),
    Object.entries(statuses).map(([key, label]) => el('option', {value: key}, label)));
  const attention = el('input', {type: 'checkbox', 'aria-label': '只看需我处理'});
  let page = data.runPage, selected = data.runDetail, disposed = false, serial = 0, busy = false, loaded = false;
  let state = {offset: 0, group: '', status: '', attention: false, seen: []};
  let pinned = app.route.revision, live = !app.historical, pendingRefresh = false, choiceMade = false;
  root.append(el('div', {class: 'panel-head'}, el('h2', {}, '运行记录'), button('核实最新执行状态', () => { choiceMade = true; live = true; state.offset = 0; persist(); read(); })),
    el('div', {class: 'panel-body stack'}, el('p', {class: 'muted'}, '当前执行状态与顶栏的页面阅读版本分开。正常处理中无需你操作；查看结果不代表采用或质量通过。'),
      el('div', {class: 'row wrap run-filters'}, group, status, el('label', {}, attention, '只看需我处理')), notice, detail, rows, pager));
  function persist() {
    const editor = app.editor;
    if (!editor || editor.readonly || editor.disposed || !editor.draft) return;
    editor.draft.content.run_desk = structuredClone(state); editor.changed();
  }
  const todo = task => (task.human_actions || []).filter(action => action !== 'review_results' || !state.seen.includes(seenKey(task)));
  const errorBox = error => errorNote({what: error.message || error.cause || '对象无法读取',
    kept: '已显示的运行记录仍保留。', next: `对象：${error.object || error.field || '运行记录'} · ${error.next_action || '核实原任务后重试读取'}`,
    ref: error.docs_ref || 'docs/agent-recovery-playbook.md#run-desk-recovery'});
  function render() {
    group.replaceChildren(el('option', {value: ''}, '所有修改组'), ...page.groups.filter(item => item.change_id).map(item =>
      el('option', {value: item.change_id}, `${item.change_id} · ${item.completed_count}/${item.total_count} 项`)));
    group.value = state.group; status.value = state.status; attention.checked = state.attention;
    notice.textContent = `${live ? '当前执行状态' : '固定执行记录'} · ${version(page.revision_id)} · 共 ${page.pagination.total} 项`;
    const tasks = page.tasks.filter(task => !state.attention || todo(task).length);
    rows.replaceChildren(...tasks.map(task => el('article', {class: 'run-task stack', 'data-task-id': task.task_id},
      el('div', {class: 'row wrap'}, el('strong', {}, names[task.kind] || '制作任务'), el('span', {class: 'status'}, statuses[task.status] || task.status)),
      el('p', {}, task.scope_pages?.length ? `作用页：${task.scope_pages.join('、')}` : '作用于项目'),
      el('p', {class: 'muted'}, `任务 ${task.task_id || '无法读取'} · 接手时间：${clock(task.execution_started_at)}`),
      task.human_actions?.includes('verify_execution') && el('p', {class: 'field-error'}, '需要核实原执行。不会自动重试或取消；未确认取消前请勿重复派发。'),
      todo(task).length > 0 && el('p', {class: 'run-actions'}, todo(task).map(key => actions[key] || key).join(' · ')),
      task.error && errorBox(typeof task.error === 'object' ? task.error : {message: task.error}),
      task.task_id && button('查看这项任务', () => app.go({task_id: task.task_id, revision: page.revision_id})))));
    if (!tasks.length) rows.append(empty(state.attention ? '本页没有需要你处理的记录' : '没有匹配的运行记录',
      '可继续阅读内容与制作状态。查看其它记录不会触发执行。', el('div', {class: 'row wrap'}, button('阅读内容', () => app.go({surface: 'content'})), button('查看整稿', () => app.go({surface: 'gallery'})))));
    const move = offset => { choiceMade = true; state.offset = offset; state.revision = page.revision_id; pinned = page.revision_id; live = false; persist(); read(); };
    pager.replaceChildren(disabledReason(button('上一页任务', () => move(Math.max(0, state.offset - 30)), false, {disabled: state.offset === 0}), state.offset === 0 ? '已在第一页。' : '', {visible: false}),
      el('span', {}, `第 ${Math.floor(state.offset / 30) + 1} 页 · 每页最多 30 项`),
      disabledReason(button('下一页任务', () => move(page.pagination.next_offset), false, {disabled: page.pagination.next_offset === null}), page.pagination.next_offset === null ? '已是最后一页。' : '', {visible: false}));
    rows.hidden = Boolean(selected); pager.hidden = Boolean(selected);
    if (selected) renderDetail();
  }
  async function showEvidence(kind, id, revision) {
    try {
      const value = await get(`/api/${kind}/${encodeURIComponent(id)}` + revisionQuery(revision));
      if (!disposed) modal('调用依据与结果记录', el('pre', {class: 'run-evidence'}, JSON.stringify(value, null, 2)));
    } catch (error) { if (!disposed) detail.append(errorBox({...error.details, message: readableError(error)})); }
  }
  function renderDetail() {
    const task = selected.task, revision = selected.revision_id;
    recovery.observe(task);
    const resultLinks = (task.result_refs || []).map((ref, index) => {
      const url = fileURL(ref);
      return url ? el('a', {href: url, target: '_blank', rel: 'noopener'}, `读取结果 ${index + 1} · ${ref.sha256.slice(0, 12)}`) : el('span', {}, '结果引用无法读取');
    });
    detail.replaceChildren(el('div', {class: 'stack'}, el('h3', {}, `${names[task.kind] || '制作任务'} · ${statuses[task.status] || task.status}`),
      el('p', {}, task.instruction), el('p', {class: 'muted'}, `任务 ${task.task_id} · ${version(revision)}`),
      el('p', {}, `真实接手时间：${clock(task.execution_started_at)}${task.execution_started_at ? '' : '，不会用最后更新时间代替'}`),
      el('p', {class: 'execution-reference'}, task.execution_ref ? `执行标识：${task.execution_ref}` : '尚无执行标识'),
      el('div', {class: 'row wrap'}, (task.scope_pages || []).map(id => button(`阅读 ${id}`, () => app.go({surface: 'page', page_id: id, layer: 'original_image', revision})))),
      el('p', {}, `已记录结果 ${task.result_refs.length} 项 · 候选 ${task.candidate_refs.length} 项 · 未知调用 ${task.call_counts.unknown || 0} 次`),
      (task.call_counts.unknown || 0) > 0 && el('p', {class: 'field-error'}, '未知调用不等于未执行。请核实原调用；本工作台不会重新分配额度或自动重试。'),
      recovery.pending.has(task.task_id) && el('p', {class: 'field-error'}, '取消结果待核实，未安排替代任务。'),
      el('div', {class: 'row wrap'}, button('核实原任务', async () => {
        try { selected = await recovery.verify(task.task_id); if (!disposed) renderDetail(); }
        catch (error) { if (!disposed) detail.append(errorBox({...error.details, message: readableError(error)})); }
      }), ['queued', 'awaiting_host', 'running'].includes(task.status) && disabledReason(button(recovery.pending.has(task.task_id) ? '再次请求取消原任务' : '取消原任务', async () => {
        try { await recovery.cancel(task, recovery.pending.has(task.task_id)); if (!disposed) { selected = await recovery.verify(task.task_id); renderDetail(); } }
        catch (error) { if (!disposed) detail.append(errorBox({...error.details, message: '取消结果请核实。' + readableError(error)})); }
      }, false, {disabled: app.readonly || recovery.sending.has(task.task_id)}),
        app.readonly ? '当前视图只读，不能取消任务。' : recovery.sending.has(task.task_id) ? '取消请求已发送，等待核实结果。' : '')),
      el('div', {class: 'stack'}, resultLinks),
      task.result_refs.length > 0 && !task.candidate_refs.length && button(state.seen.includes(seenKey(task)) ? '已标记读过这些结果' : '标记这些结果已读', () => {
        state.seen = [...new Set([...state.seen, seenKey(task)])].slice(-500); persist(); render();
      }, false, {disabled: app.readonly || state.seen.includes(seenKey(task))}),
      el('details', {}, el('summary', {}, '请求、Attempt 与调用额度'),
        el('div', {class: 'stack'}, selected.links.generation_requests.map(link => button(link.request_id, () => showEvidence('requests', link.request_id, revision))),
          selected.links.generation_attempts.map(link => button(link.attempt_id, () => showEvidence('attempts', link.attempt_id, revision)))),
        el('pre', {class: 'run-evidence'}, JSON.stringify(selected.call_allowances, null, 2))),
      (selected.errors || []).map(errorBox), button('查看全部任务', () => app.go({task_id: null}))));
  }
  async function read() {
    if (disposed) return;
    if (busy) { pendingRefresh = true; return; }
    busy = true; const token = ++serial;
    if (loaded) notice.replaceChildren(loading(live ? '正在读取当前执行状态…' : '正在读取固定执行记录…'));
    const query = new URLSearchParams({limit: '30', offset: String(state.offset)});
    if (!live) query.set('revision', pinned);
    if (state.group) query.set('change_id', state.group);
    if (state.status) query.set('status', state.status);
    if (state.attention) query.set('attention', '1');
    try {
      const value = await get('/api/tasks?' + query);
      const nextDetail = app.route.task_id ? await get('/api/tasks/' + encodeURIComponent(app.route.task_id) + revisionQuery(live ? null : pinned)) : null;
      if (disposed || token !== serial) return;
      page = value; selected = nextDetail; loaded = true; render();
    } catch (error) {
      if (!disposed) notice.replaceChildren(errorBox({...error.details, message: readableError(error)}), button('重试读取', () => read()));
    } finally { busy = false; if (pendingRefresh && !disposed) { pendingRefresh = false; read(); } }
  }
  for (const input of [group, status, attention]) input.addEventListener('change', () => {
    choiceMade = true; state.group = group.value; state.status = status.value; state.attention = attention.checked; state.offset = 0; persist(); read();
  });
  const sync = () => { if (live && !document.hidden) read(); };
  app.root.addEventListener('summary-refreshed', sync);
  function hydrate() {
    const editor = app.editor;
    if (!editor) { read(); return; }
    editor.ready.then(() => {
      if (disposed || editor !== app.editor) return;
      recovery.hydrate(editor);
      const saved = editor.draft.content.run_desk;
      if (!choiceMade && saved && typeof saved === 'object') {
        state = {offset: Number.isSafeInteger(saved.offset) && saved.offset >= 0 ? saved.offset : 0,
          group: typeof saved.group === 'string' ? saved.group : '', status: Object.hasOwn(statuses, saved.status) ? saved.status : '',
          attention: saved.attention === true, seen: Array.isArray(saved.seen) ? saved.seen.filter(v => typeof v === 'string').slice(-500) : []};
        if (state.offset) { live = false; pinned = typeof saved.revision === 'string' ? saved.revision : app.route.revision; state.revision = pinned; }
      }
      if (choiceMade) persist();
      read();
    });
  }
  const onCancel = () => queueMicrotask(() => { if (!disposed && selected) renderDetail(); });
  app.root.addEventListener('cancel-state-changed', onCancel);
  app.root.addEventListener('draft-editor-replaced', hydrate);
  app.disposables.push(() => { disposed = true; serial++; app.root.removeEventListener('cancel-state-changed', onCancel); app.root.removeEventListener('summary-refreshed', sync); app.root.removeEventListener('draft-editor-replaced', hydrate); });
  render(); hydrate(); return root;
}
