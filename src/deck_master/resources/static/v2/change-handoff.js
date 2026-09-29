import {get, post, readableError} from './api.js';
import {el, button, modal, version} from './dom.js';

const labels = {awaiting_host: '待交接 · 尚未开始', running: '已接手 · 处理中', partial: '部分已返回',
  completed: '已返回结果 · 仍需审阅', cancelled: '取消已确认', failed: '执行未完成', unknown: '调用状态待核实'};
const taskLabels = {queued: '等待', awaiting_host: '尚未接手', running: '处理中', completed: '已返回',
  cancelled: '取消已确认', failed: '失败', superseded: '基准已更新'};
export function changeHandoffs(app) {
  const node = el('section', {class: 'panel change-handoffs', 'aria-label': '持久修改交接'});
  const heading = el('div', {class: 'panel-head'}, el('h2', {}, '修改交接'), el('span', {class: 'status'}, '当前执行状态'));
  const list = el('div', {class: 'change-list stack'}), detail = el('div', {class: 'handoff-detail stack'});
  const notice = el('p', {role: 'status', class: 'muted'});
  node.append(heading, el('div', {class: 'panel-body stack'}, el('p', {class: 'muted'}, '这里读取当前交接事实；页面与任务的历史阅读版本保持不变。'), notice, list, detail));
  let disposed = false, busy = false, timer, delay = 3000, active = null, lastSync = null, latest, lastList;
  const copied = new Set();
  try { for (const id of JSON.parse(localStorage.getItem(`deck-master:v3:copied:${app.info.project_identity}`) || '[]')) copied.add(id); } catch { /* Copy hints are not execution facts. */ }
  const cancelUnknown = new Set();
  const open = async id => {
    active = id; notice.textContent = '正在读取已保存的要求与执行状态…';
    await refresh();
  };
  async function cancel(task) {
    notice.textContent = '正在请求取消；只有服务确认后才能安排替代任务。';
    cancelUnknown.add(task.task_id); renderDetail();
    try {
      await post('/api/cancel', {task_id: task.task_id, reason: '用户在修改交接面板取消'});
      cancelUnknown.delete(task.task_id); await refresh();
    } catch (error) { notice.textContent = '取消结果尚未确认，请核实当前状态后再安排。' + readableError(error); renderDetail(); }
  }
  async function copy() {
    if (!latest) return;
    try {
      await navigator.clipboard.writeText(latest.text); copied.add(active);
      try { localStorage.setItem(`deck-master:v3:copied:${app.info.project_identity}`, JSON.stringify([...copied])); }
      catch { notice.textContent = '说明已复制；本机复制提示未保存，执行状态不受影响。'; }
      renderDetail();
    } catch {
      modal('未能自动复制，说明仍保留', el('div', {class: 'stack'}, el('p', {}, '请手动选择下面的完整说明并复制。尚未记录接手。'),
        el('textarea', {readOnly: true, rows: 12, value: latest.text, 'aria-label': '手动复制交接说明'})));
    }
  }
  function renderDetail() {
    if (!latest) return;
    const tasks = latest.handoff.tasks;
    const title = latest.status === 'awaiting_host' && copied.has(active) ? '已复制、未接手' : labels[latest.status] || '执行状态待核实';
    detail.replaceChildren(el('div', {class: 'stack'}, el('h3', {'data-change-id': active}, title),
      el('p', {class: 'handoff-progress', role: 'status'}, `${latest.completed_count} / ${latest.total_count} 项已返回 · ${version(latest.handoff.base_revision)} 的计划`),
      latest.needs_verification && el('p', {class: 'field-error'}, '已超过等待阈值或调用状态不明。请核实原执行，或确认取消后重新计划；不会自动重试。'),
      el('p', {}, latest.handoff.plan.input.instruction),
      el('div', {class: 'row wrap'}, button('复制交接说明', copy, latest.status === 'awaiting_host'), button('核实执行状态', refresh)),
      el('div', {class: 'handoff-tasks stack'}, tasks.map(task => {
        if (task.status === 'cancelled') cancelUnknown.delete(task.task_id);
        return el('article', {class: 'handoff-task'},
          el('strong', {}, taskLabels[task.status] || '待核实'), el('p', {class: 'muted'}, `任务 ${task.task_id}`),
          task.execution_ref && el('p', {class: 'execution-reference'}, `已记录接手：${task.execution_ref}`),
          cancelUnknown.has(task.task_id) && el('p', {class: 'field-error'}, '取消结果待核实，未安排替代任务。'),
          ['queued', 'awaiting_host', 'running'].includes(task.status) && button('取消这项任务', () => cancel(task), false,
            {disabled: cancelUnknown.has(task.task_id) || Boolean(app.info.sample?.readonly)}));
      })),
      el('details', {}, el('summary', {}, '完整交接说明与身份'), el('textarea', {readOnly: true, rows: 9, value: latest.text, 'aria-label': '已保存的完整交接说明'}))));
  }
  async function refresh() {
    if (busy || disposed) return; busy = true;
    try {
      const changes = await get('/api/changes'); if (disposed) return;
      const nextList = JSON.stringify([active, changes.changes]);
      if (lastList !== nextList) {
        lastList = nextList;
        list.replaceChildren(...changes.changes.map(change => button(`${labels[change.status] || '待核实'} · ${change.completed_count}/${change.total_count} 项`, () => open(change.change_id), false,
          {'aria-pressed': active === change.change_id})));
        if (!changes.changes.length) list.append(el('p', {class: 'muted'}, '尚无已提交修改。保存意见、预览影响后，交接会持续保留在这里。'));
      }
      if (!active && changes.changes.length) {
        const last = changes.changes[changes.changes.length - 1]; active = last.change_id;
        if (app.route.task_id) {
          for (const change of changes.changes) {
            const handoff = await get('/api/changes/' + encodeURIComponent(change.change_id) + '/handoff');
            if (handoff.handoff.tasks.some(task => task.task_id === app.route.task_id)) { active = change.change_id; break; }
          }
        }
      }
      if (active) {
        const id = active; const result = await get('/api/changes/' + encodeURIComponent(id) + '/handoff');
        if (disposed || id !== active) return;
        if (JSON.stringify(latest) !== JSON.stringify(result)) { latest = result; renderDetail(); }
      }
      lastSync = new Date(); notice.textContent = '最后同步：' + lastSync.toLocaleTimeString();
      delay = latest && ['awaiting_host', 'running', 'partial', 'unknown'].includes(latest.status) ? 3000 : 15000;
    } catch (error) {
      if (!disposed) notice.textContent = readableError(error) + (lastSync ? ' 保留最后同步内容：' + lastSync.toLocaleTimeString() : '');
      delay = Math.min(30000, delay * 2);
    } finally { busy = false; }
  }
  const tick = async () => { if (!document.hidden) await refresh(); if (!disposed) timer = setTimeout(tick, delay); };
  tick(); app.disposables.push(() => { disposed = true; clearTimeout(timer); }); return node;
}
