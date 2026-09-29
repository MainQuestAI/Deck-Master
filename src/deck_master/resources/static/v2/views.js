import {deliveryDesk, historyDesk} from './delivery-desk.js';
import {runDesk} from './run-desk.js';
import {candidateBatch} from './candidate-desk.js';
import {el, button, heading, empty, version} from './dom.js';
import {layers} from './routes.js';
import {stageKey, stageLabel} from './gallery.js';
import {changeHandoffs} from './change-handoff.js';

const pageTitle = (page, index) => `第 ${index + 1} 页 · ${page.title || '未命名页面'}`;
const panel = (title, ...children) => el('section', {class: 'panel'}, el('div', {class: 'panel-head'}, el('h2', {}, title)), el('div', {class: 'panel-body stack'}, children));
export function overview(app) {
  const pages = app.summary.pages;
  const count = pages.filter(page => page.stages.blueprint.existence === 'recorded').length;
  const primary = count ? button('看整稿原图', () => app.go({surface: 'gallery'}), true) : button('查看内容与来源', () => app.go({surface: 'content'}), true);
  const node = el('div', {}, heading('制作总览', `${pages.length} 页内容 · ${count} 页已有原图。可看状态不代表质量检查通过。`, primary));
  if (!pages.length) return el('div', {}, node, empty('先把内容整理清楚', '项目已建立。补充材料并交接内容整理后，这里会出现逐页内容与制作状态。'));
  node.append(el('div', {class: 'action-band'}, el('div', {class: 'action-main'}, el('h2', {}, '从整稿开始阅读'),
    el('p', {class: 'muted'}, '先看页面节奏，再进入单页查看逐页稿、原图和制作依据。')),
    el('div', {class: 'action-list'}, el('div', {class: 'action-item'}, el('div', {}, el('h3', {}, '需要制作工具继续'), el('p', {}, '工作台保留阅读与个人草稿。生成任务仍需交接。')),
      button('查看任务', () => app.go({surface: 'runs'}))))));
  const table = el('table', {class: 'matrix', 'aria-label': '逐页制作状态'});
  const keys = ['content', 'original_image', 'svg', 'ppt'];
  table.append(el('thead', {}, el('tr', {}, el('th', {scope: 'col'}, '页面'), keys.map(key => el('th', {scope: 'col'}, layers[key])))));
  const rows = el('tbody'); const cells = [];
  pages.forEach((page, index) => {
    const controls = [button(pageTitle(page, index), () => app.go({surface: 'page', page_id: page.page_id, layer: 'original_image'}), false, {class: 'title-button', tabindex: index ? '-1' : '0'})];
    controls.push(...keys.map(layer => button(stageLabel(page.stages[stageKey[layer]]), () => app.go({surface: 'page', page_id: page.page_id, layer}), false,
      {class: 'cell-btn', tabindex: '-1', 'aria-label': `${pageTitle(page, index)}，${layers[layer]}，${stageLabel(page.stages[stageKey[layer]])}`})));
    cells.push(controls); rows.append(el('tr', {}, controls.map((control, i) => el(i ? 'td' : 'th', i ? {} : {scope: 'row'}, control))));
  });
  table.append(rows);
  table.addEventListener('keydown', event => {
    const r = cells.findIndex(row => row.includes(document.activeElement)); if (r < 0) return;
    const c = cells[r].indexOf(document.activeElement);
    const offsets = {ArrowDown: [1, 0], ArrowUp: [-1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1], Home: [0, -c], End: [0, 4 - c]};
    if (!offsets[event.key]) return;
    event.preventDefault(); const [dr, dc] = offsets[event.key];
    const next = cells[Math.max(0, Math.min(cells.length - 1, r + dr))][Math.max(0, Math.min(4, c + dc))];
    document.activeElement.tabIndex = -1; next.tabIndex = 0; next.focus();
  });
  node.append(el('div', {class: 'matrix-wrap'}, table), el('p', {class: 'matrix-caption'}, '方向键在表格中移动，Enter 打开对应页与层。原图保留完整画布。'));
  return node;
}
export {content} from './content-sources.js';
export {pageDetail} from './page-workbench.js';
const taskNames = {compose: '整理内容', blueprint: '制作原图', svg: '制作 SVG', render: '渲染预览', repair: '局部修改', review: '检查', export: '准备文件'};
const taskStatus = {awaiting_host: '待交接', running: '已记录处理中', completed: '结果已记录', failed: '执行失败', cancelled: '已取消', superseded: '已由新任务接续', blocked: '需要处理阻碍'};
export function runs(app, data) {
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
    !selected && button('查看这项任务', () => app.go({task_id: task.task_id})), selected && button('查看全部任务', () => app.go({task_id: null}))))) : empty('没有已记录的任务', '此版本还没有制作任务。'));
  if (handoffs) node.append(handoffs);
  node.append(batch);
  if (app.health.ui_capabilities?.includes('exports.v1')) node.append(historyDesk(app, data.history), deliveryDesk(app));
  else node.append(panel('版本与文件', el('p', {}, '升级核心后可读取固定版本的导出与恢复功能。')));
  return node;
}
export {style} from './style-calibration.js';
