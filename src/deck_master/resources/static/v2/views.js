import {deliveryDesk, historyDesk} from './delivery-desk.js';
import {runDesk} from './run-desk.js';
import {candidateBatch} from './candidate-desk.js';
import {el, button, empty, heading} from './dom.js';
import {changeHandoffs} from './change-handoff.js';

const panel = (title, ...children) => el('section', {class: 'panel'}, el('div', {class: 'panel-head'}, el('h2', {}, title)), el('div', {class: 'panel-body stack'}, children));
export {overview} from './overview.js';
export {content} from './content-sources.js';
export {pageDetail} from './page-workbench.js';
const taskNames = {compose: '整理内容', blueprint: '制作原图', svg: '制作 SVG', render: '渲染预览', repair: '局部修改', review: '检查', export: '准备文件'};
const taskStatus = {awaiting_host: '待交接', running: '已记录处理中', completed: '结果已记录', failed: '执行失败', cancelled: '已取消', superseded: '已由新任务接续', blocked: '需要处理阻碍'};
export function runs(app, data) {
  if (data.review) {
    const review = data.review;
    return el('div', {class: 'stack'}, heading('质量记录', '此记录按正在阅读的版本固定；记录存在不代表所有交付条件已通过。',
      button('返回任务与交付', () => app.go({review_id: null}))),
      el('p', {}, ({pass: '该项检查通过', fail: '该项检查未通过', blocked: '该项检查受阻'})[review.status] || '记录状态待核实'),
      (review.observations || []).map(text => el('p', {}, text)),
      (review.findings || []).map(finding => el('article', {class: 'panel'}, el('div', {class: 'panel-body stack'},
        el('h2', {}, finding.message), el('p', {}, '预期：' + finding.expected), el('p', {}, '记录：' + finding.actual)))),
      el('details', {}, el('summary', {}, '记录身份与依据'), el('pre', {class: 'evidence-json'}, JSON.stringify(review, null, 2))));
  }
  const selected = data.runDetail?.task || data.tasks.find(task => task.task_id === app.route.task_id);
  const node = el('div', {}, heading(selected ? '当前任务' : '任务与交付', '任务状态按当前阅读版本展示。复制交接说明不会启动模型。',
    selected?.kind === 'compose' && selected.status === 'awaiting_host' && !app.readonly ? button('交接这项内容整理', () => app.handoff(selected.task_id), true) : null));
  if (app.health.ui_capabilities?.includes('exports.v1')) node.append(button('查看版本与文件', () => { const target = document.querySelector('#delivery-desk'); target?.scrollIntoView({block: 'start'}); target?.querySelector('h2')?.focus({preventScroll: true}); }));
  if (selected && app.returnTo && !app.returnTo.task_id) node.append(button('返回上次工作面', () => app.go(app.returnTo)));
  const handoffs = app.health.ui_capabilities?.includes('changes.v1') ? changeHandoffs(app) : null;
  const batch = candidateBatch(app);
  const tasks = selected ? [selected] : data.tasks;
  node.append(data.runPage ? runDesk(app, data) : tasks.length ? el('div', {class: 'task-list stack'}, tasks.map(task => el('article', {class: 'panel task-row'},
    el('div', {}, el('h2', {}, taskNames[task.kind] || '制作任务'), el('p', {class: 'muted'}, `${taskStatus[task.status] || '状态待核实'} · 任务 ${task.task_id}`),
      task.result_refs?.length > 0 && el('p', {class: 'muted'}, `${task.result_refs.length} 项已记录结果；这不代表专业质量通过。`)),
    !selected && button('查看这项任务', () => app.go({task_id: task.task_id})), selected && button('查看全部任务', () => app.go({task_id: null}))))): empty('没有已记录的任务', '此版本还没有制作任务。'));
  if (handoffs) node.append(handoffs);
  node.append(batch);
  if (app.health.ui_capabilities?.includes('exports.v1')) node.append(historyDesk(app, data.history), deliveryDesk(app));
  else node.append(panel('版本与文件', el('p', {}, '升级核心后可读取固定版本的导出与恢复功能。')));
  return node;
}
export {style} from './style-calibration.js';
