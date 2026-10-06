import {deliveryDesk, historyDesk} from './delivery-desk.js';
import {runDesk} from './run-desk.js';
import {candidateBatch} from './candidate-desk.js';
import {el, button, empty, heading} from './dom.js';
import {changeHandoffs} from './change-handoff.js';
import {runsAreas, routeHash} from './routes.js';

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
  if (selected && app.returnTo && !app.returnTo.task_id) node.append(button('返回上次工作面', () => app.go(app.returnTo)));
  const handoffs = app.health.ui_capabilities?.includes('changes.v1') ? changeHandoffs(app) : null;
  const batch = candidateBatch(app);
  const tasks = selected ? [selected] : data.tasks;
  const runsPanel = data.runPage ? runDesk(app, data) : tasks.length ? el('div', {class: 'task-list stack'}, tasks.map(task => el('article', {class: 'panel task-row'},
    el('div', {}, el('h2', {}, taskNames[task.kind] || '制作任务'), el('p', {class: 'muted'}, `${taskStatus[task.status] || '状态待核实'} · 任务 ${task.task_id}`),
      task.result_refs?.length > 0 && el('p', {class: 'muted'}, `${task.result_refs.length} 项已记录结果；这不代表专业质量通过。`)),
    !selected && button('查看这项任务', () => app.go({task_id: task.task_id})), selected && button('查看全部任务', () => app.go({task_id: null}))))): empty('没有已记录的任务', '此版本还没有制作任务。');
  // UX-05b（对账报告 §5：任务/决定/版本/文件职责混排）：四个子区改为分段切换——
  // 同一时刻只呈现一个工作上下文，默认进入「正在进行」；切换后焦点落到该子区
  // 标题，按钮以 aria-pressed 说明当前所在，而不是把四段内容纵向堆在一起。
  // R4（深度复审）：子区上下文随链接保存与恢复——读取版本、刷新或从别的工作面
  // 返回后仍落在同一个子区；只有初次访问（链接里没有 area）才默认「正在进行」。
  const subareas = [
    ['tasks', 'runs-tasks', '正在进行', el('div', {id: 'runs-tasks', class: 'stack runs-subarea'}, runsPanel)],
    ['decisions', 'runs-decisions', '待决定', el('div', {id: 'runs-decisions', class: 'stack runs-subarea'}, ...(handoffs ? [handoffs] : []), batch)],
  ];
  if (app.health.ui_capabilities?.includes('exports.v1')) {
    subareas.push(['versions', 'runs-versions', '版本', el('div', {id: 'runs-versions', class: 'stack runs-subarea'}, historyDesk(app, data.history))]);
    subareas.push(['files', 'runs-files', '文件', el('div', {id: 'runs-files', class: 'stack runs-subarea'}, deliveryDesk(app))]);
  } else subareas.push(['versions', 'runs-versions', '版本与文件', el('div', {id: 'runs-versions', class: 'stack runs-subarea'},
    panel('版本与文件', el('p', {}, '升级核心后可读取固定版本的导出与恢复功能。')))]);
  const switchers = new Map();
  const showSubarea = (key, {focus = false, persist = false} = {}) => {
    for (const [area, , , section] of subareas) section.hidden = area !== key;
    for (const [area, control] of switchers) control.setAttribute('aria-pressed', String(area === key));
    if (persist) {
      app.route.runs_area = key;
      history.replaceState(null, '', routeHash(app.info, app.route));
    }
    if (!focus) return;
    const head = subareas.find(([area]) => area === key)?.[3].querySelector('h2');
    if (head) { head.tabIndex = -1; head.focus({preventScroll: true}); }
  };
  node.append(el('div', {class: 'row wrap runs-subareas', role: 'group', 'aria-label': '任务与交付的子区'},
    ...subareas.map(([area, id, name]) => {
      const control = button(name, () => showSubarea(area, {focus: true, persist: true}), false, {class: 'quiet', 'aria-controls': id, 'aria-pressed': 'false'});
      switchers.set(area, control); return control;
    })));
  node.append(...subareas.map(([, , , section]) => section));
  showSubarea(runsAreas.includes(app.route.runs_area) ? app.route.runs_area : 'tasks');
  return node;
}
export {style} from './style-calibration.js';
