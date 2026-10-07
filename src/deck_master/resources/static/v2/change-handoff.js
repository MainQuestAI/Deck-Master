import {cancelRecovery} from './run-recovery.js';
import {openCandidate} from './trial-actions.js';
import {get, readableError} from './api.js';
import {el, button, modal, version} from './dom.js';

const labels = {awaiting_host: '待交接 · 尚未开始', running: '已接手 · 处理中', partial: '部分已返回',
  completed: '已返回结果 · 仍需审阅', cancelled: '取消已确认', failed: '执行未完成', unknown: '调用状态待核实'};
const taskLabels = {queued: '等待', awaiting_host: '尚未接手', running: '处理中', completed: '已返回',
  cancelled: '取消已确认', failed: '失败', superseded: '基准已更新'};
// 复制只作用于已成功读取且与当前所选一致的组。等待响应期间切换组时，
// 旧组文本不得再被复制，本机复制提示也只属于被复制的那一组（C01/N01）。
export const copySnapshot = (loaded, loadedId, selectedId) => loaded && loadedId != null && loadedId === selectedId ? {id: loadedId, text: loaded.text} : null;
// A task owns the handoff target. Never default to the last group in the catalog.
export function taskHandoff(app, task, groups) {
  const group = groups.find(row => row.task_ids?.includes(task.task_id));
  if (!group || app.historical || task.status !== 'awaiting_host') return null;
  const note = el('p', {role: 'status'}, '正在读取这项任务的交接说明…');
  const text = el('textarea', {readOnly: true, rows: 7, 'aria-label': '本任务完整交接说明'});
  let snapshot = null, disposed = false;
  const copy = button('复制交接说明', async () => {
    const frozen = snapshot;
    if (!frozen || disposed) return;
    copy.disabled = true;
    try {
      await navigator.clipboard.writeText(frozen.text);
      const key = `deck-master:v3:copied:${app.info.project_identity}`;
      try { const ids = new Set(JSON.parse(localStorage.getItem(key) || '[]')); ids.add(frozen.id); localStorage.setItem(key, JSON.stringify([...ids])); } catch { /* Clipboard success is independent of the local hint. */ }
      if (!disposed) note.textContent = '交接说明已复制 · 待接手。复制不会启动制作。';
    } catch {
      if (!disposed) { details.open = true; text.focus(); text.select(); note.textContent = '自动复制未完成，请复制下面的完整说明。'; }
    } finally { if (!disposed) copy.disabled = !snapshot; }
  }, true, {disabled: true});
  const read = async () => {
    snapshot = null; copy.disabled = true;
    try {
      const value = await get('/api/changes/' + encodeURIComponent(group.change_id) + '/handoff');
      if (disposed) return;
      if (!value.handoff.tasks.some(row => row.task_id === task.task_id)) throw new Error('交接说明与当前任务不一致，请核实原任务。');
      if (!value.handoff.tasks.some(row => row.task_id === task.task_id && row.status === 'awaiting_host')) throw new Error('任务状态已经变化，请核实原任务后继续。');
      snapshot = {id: group.change_id, text: value.text}; text.value = value.text;
      note.textContent = `本次交接包含 ${value.handoff.tasks.length} 项任务。要求已保存，尚未接手。`;
      copy.disabled = false;
    } catch (error) { if (!disposed) note.textContent = readableError(error); }
  };
  const details = el('details', {}, el('summary', {}, '完整交接说明与涉及页面'),
    el('p', {}, (group.page_ids || []).map(id => { const i = app.summary.pages.findIndex(p => p.page_id === id); return i < 0 ? id : `第 ${i + 1} 页 · ${app.summary.pages[i].title}`; }).join('、')), text);
  const node = el('section', {class: 'task-handoff stack'}, note, el('div', {class: 'row wrap'}, copy, button('重新读取交接说明', read)), details);
  read(); return {node, dispose: () => { disposed = true; }};
}
export function changeHandoffs(app) {
  const node = el('section', {class: 'panel change-handoffs', 'aria-label': '持久修改交接'});
  const heading = el('div', {class: 'panel-head'}, el('h2', {}, '修改交接'), el('span', {class: 'status'}, '当前执行状态'));
  const list = el('div', {class: 'change-list stack'}), detail = el('div', {class: 'handoff-detail stack'});
  const notice = el('p', {role: 'status', class: 'muted'});
  node.append(heading, el('div', {class: 'panel-body stack'}, el('p', {class: 'muted'}, '这里读取当前交接事实；页面与任务的历史阅读版本保持不变。'), notice, list, detail));
  const modern = app.health.ui_capabilities?.includes('run_desk.v1');
  let disposed = false, busy = false, timer, delay = 3000, active = null, lastSync = null, latest, latestChangeId = null, rerun = false, readFailed = false, lastList, candidateRows = [], candidateRevision = null, candidateSignature = "";
  const copied = new Set();
  try { for (const id of JSON.parse(localStorage.getItem(`deck-master:v3:copied:${app.info.project_identity}`) || '[]')) copied.add(id); } catch { /* Copy hints are not execution facts. */ }
  const recovery = cancelRecovery(app), cancelUnknown = recovery.pending;
  const open = async id => {
    active = id; readFailed = false; notice.textContent = '正在读取已保存的要求与执行状态…';
    // 立即以旧组内容重绘：复制按钮对新对象停用并说明原因，面板标签仍指向
    // 已读取的那一组；等待响应期间切换组不得复制旧内容（C01/N01）。
    renderDetail();
    await refresh();
  };
  async function cancel(task) {
    notice.textContent = '正在请求取消；只有服务确认后才能安排替代任务。';
    renderDetail();
    try {
      await recovery.cancel(task); await refresh();
      app.root.dispatchEvent(new CustomEvent('business-state-changed'));
    } catch (error) { notice.textContent = '取消结果尚未确认，请核实当前状态后再安排。' + readableError(error); renderDetail(); }
  }
  async function copy() {
    const snapshot = copySnapshot(latest, latestChangeId, active);
    if (!snapshot) return;
    try {
      await navigator.clipboard.writeText(snapshot.text); copied.add(snapshot.id);
      try { localStorage.setItem(`deck-master:v3:copied:${app.info.project_identity}`, JSON.stringify([...copied])); }
      catch { notice.textContent = '说明已复制；本机复制提示未保存，执行状态不受影响。'; }
      renderDetail();
    } catch {
      modal('未能自动复制，说明仍保留', el('div', {class: 'stack'}, el('p', {}, '请手动选择下面的完整说明并复制。尚未记录接手。'),
        el('textarea', {readOnly: true, rows: 12, value: snapshot.text, 'aria-label': '手动复制交接说明'})));
    }
  }
  function renderDetail() {
    if (!latest) return;
    const tasks = latest.handoff.tasks;
    const trial = latest.handoff.plan.input.mode === 'trial';
    const staleSelection = latestChangeId !== active;
    const title = trial && latest.status === 'completed' ? '候选已返回 · 待比较' : latest.status === 'awaiting_host' && copied.has(latestChangeId) ? '已复制、未接手' : labels[latest.status] || '执行状态待核实';
    detail.replaceChildren(el('div', {class: 'stack'}, el('h3', {'data-change-id': latestChangeId}, title),
      staleSelection && el('p', {class: 'muted'}, readFailed ? '所选修改组读取失败；下面仍是上一组的内容，复制暂不可用。可重试核实。' : '正在读取所选修改组；下面仍是上一组的内容，复制暂不可用。'),
      el('p', {class: 'handoff-progress', role: 'status'}, `${latest.completed_count} / ${latest.total_count} 项已返回 · ${version(latest.handoff.base_revision)} 的计划`),
      latest.needs_verification && el('p', {class: 'field-error'}, '已超过等待阈值或调用状态不明。请核实原执行，或确认取消后重新计划；不会自动重试。'),
      el('p', {}, latest.handoff.plan.input.instruction.slice(0,200)+(latest.handoff.plan.input.instruction.length>200?'…':'')),
      el('div', {class: 'row wrap'}, button('交给 Deck Master Agent', copy, latest.status === 'awaiting_host' && !staleSelection, {disabled: staleSelection}), button('核实执行状态', refresh)),
      el('div', {class: 'handoff-tasks stack'}, tasks.map(task => {
        recovery.observe(task);
        return el('article', {class: 'handoff-task'},
          el('strong', {}, taskLabels[task.status] || '待核实'), el('details', {},el('summary', {},'任务身份'),el('p', {class:'muted'}, `任务 ${task.task_id}`),task.execution_ref && el('p',{},`接手记录 ${task.execution_ref}`)),
          modern ? (task.candidate_refs || []).map((ref, index) => button(`比较返回候选${task.candidate_refs.length > 1 ? ' ' + (index + 1) : ''}`, () => compare(task, ref))) : candidateRows.filter(row => row.candidate.task_id === task.task_id).map(row => button('比较返回候选', () => openCandidate(app, row.candidate, candidateRevision))),
          modern && el('p', {class: 'muted'}, task.execution_started_at ? '接手时间：' + new Date(task.execution_started_at).toLocaleString('zh-CN') : '接手时间未记录'),
          modern && button('查看任务与调用记录', () => app.go({surface: 'runs', task_id: task.task_id, revision: null})),
          cancelUnknown.has(task.task_id) && el('p', {class: 'field-error'}, '取消结果待核实，未安排替代任务。'),
          ['queued', 'awaiting_host', 'running'].includes(task.status) && button('取消这项任务', () => cancel(task), false,
            {disabled: cancelUnknown.has(task.task_id) || Boolean(app.info.sample?.readonly)}));
      })),
      el('details', {}, el('summary', {}, '完整交接说明与身份'), el('textarea', {readOnly: true, rows: 9, value: latest.text, 'aria-label': '已保存的完整交接说明'}))));
  }
  async function compare(task, ref) {
    try {
      const result = await get('/api/candidates?' + new URLSearchParams({page_id: task.scope_pages[0]}));
      const row = result.candidates.find(row => row.candidate.task_id === task.task_id && row.ref.sha256 === ref.sha256);
      if (!row) throw new Error('当前版本未读到这个候选，请核实原任务。');
      if (!disposed) openCandidate(app, row.candidate, result.revision_id);
    } catch (error) { if (!disposed) notice.textContent = readableError(error); }
  }
  async function refresh() {
    if (disposed) return;
    // 组切换在读取中途到来时，不丢弃请求：当前读取结束后立即按最新所选重读，
    // 否则面板会一直停留在上一组，等待下一次轮询（N01 的另一半成因）。
    if (busy) { rerun = true; return; }
    busy = true;
    try {
      const [changes, candidateResult] = await Promise.all([modern ? get('/api/tasks?limit=1').then(value => ({changes: value.groups.filter(group => group.change_id), revision_id: value.revision_id})) : get('/api/changes'), !modern && app.health.ui_capabilities?.includes('candidates.v1') ? get('/api/candidates') : Promise.resolve(null)]); if (disposed) return;
      let candidatesChanged = false;
      if (candidateResult) {
        const signature = JSON.stringify(candidateResult.candidates.map(row => row.ref));
        candidatesChanged = signature !== candidateSignature; candidateSignature = signature;
        candidateRows = candidateResult.candidates; candidateRevision = candidateResult.revision_id;
      }
      const nextList = JSON.stringify([active, changes.changes]);
      if (lastList !== nextList) {
        lastList = nextList;
        if (modern && changes.changes.length > 6) {
          const select = el('select', {'aria-label': '选择修改交接组'}, changes.changes.map(change => el('option', {value: change.change_id},
            `${labels[change.status] || '待核实'} · ${change.completed_count}/${change.total_count} 项${change.page_ids?.length ? ` · ${change.page_ids.length} 页` : ''} · ${change.change_id.slice(-6)}`)));
          select.value = active || changes.changes.at(-1).change_id; select.addEventListener('change', () => open(select.value)); list.replaceChildren(select);
        } else list.replaceChildren(...changes.changes.map(change => button(`${labels[change.status] || '待核实'} · ${change.completed_count}/${change.total_count} 项${change.page_ids?.length ? ` · ${change.page_ids.length} 页` : ''} · ${change.change_id.slice(-6)}`, () => open(change.change_id), false,
          {'aria-pressed': active === change.change_id})));
        if (!changes.changes.length) list.append(el('p', {class: 'muted'}, '尚无已提交修改。保存意见、预览影响后，交接会持续保留在这里。'));
      }
      if (!active && changes.changes.length) {
        const last = changes.changes[changes.changes.length - 1]; active = last.change_id;
        if (app.route.task_id) {
          const selected = changes.changes.find(change => change.task_ids?.includes(app.route.task_id));
          if (selected) active = selected.change_id;
          else if (!modern) for (const change of changes.changes) {
            const handoff = await get('/api/changes/' + encodeURIComponent(change.change_id) + '/handoff');
            if (handoff.handoff.tasks.some(task => task.task_id === app.route.task_id)) { active = change.change_id; break; }
          }
        }
      }
      if (active) {
        const id = active; const result = await get('/api/changes/' + encodeURIComponent(id) + '/handoff');
        if (disposed || id !== active) return;
        const contentChanged = candidatesChanged || JSON.stringify(latest) !== JSON.stringify(result);
        const identityChanged = latestChangeId !== id;
        latest = result; latestChangeId = id; readFailed = false;
        if (contentChanged || identityChanged) renderDetail();
      }
      lastSync = new Date(); notice.textContent = '最后同步：' + lastSync.toLocaleTimeString();
      delay = latest && ['awaiting_host', 'running', 'partial', 'unknown'].includes(latest.status) ? 3000 : 15000;
    } catch (error) {
      if (!disposed) {
        readFailed = true;
        notice.textContent = readableError(error) + (lastSync ? ' 保留最后同步内容：' + lastSync.toLocaleTimeString() : '');
        if (latest && latestChangeId !== active) renderDetail();
      }
      delay = Math.min(30000, delay * 2);
    } finally {
      busy = false;
      if (rerun && !disposed) { rerun = false; queueMicrotask(refresh); }
    }
  }
  const tick = async () => { if (!document.hidden) await refresh(); if (!disposed) timer = setTimeout(tick, delay); };
  const sync = () => { if (!document.hidden) refresh(); };
  const hydrate = () => { const editor = app.editor; editor?.ready.then(() => {
    if (disposed || editor !== app.editor) return;
    recovery.hydrate(editor);
    renderDetail();
  }); };
  const onCancel = () => queueMicrotask(() => { if (!disposed) renderDetail(); });
  app.root.addEventListener('cancel-state-changed', onCancel);
  app.root.addEventListener('summary-refreshed', sync); app.root.addEventListener('draft-editor-replaced', hydrate);
  queueMicrotask(hydrate);
  if (modern) refresh(); else tick();
  app.disposables.push(() => { disposed = true; clearTimeout(timer); app.root.removeEventListener('cancel-state-changed', onCancel); app.root.removeEventListener('summary-refreshed', sync); app.root.removeEventListener('draft-editor-replaced', hydrate); }); return node;
}
