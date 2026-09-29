import {runDesk} from './run-desk.js';
import {candidateBatch} from './candidate-desk.js';
import {get, post, readableError} from './api.js';
import {el, button, heading, empty, field, version, modal, toast} from './dom.js';
import {layers} from './routes.js';
import {DraftEditor} from './drafts.js';
import {stageKey, stageLabel} from './gallery.js';
import {changeHandoffs} from './change-handoff.js';

const pageTitle = (page, index) => `第 ${index + 1} 页 · ${page.title || '未命名页面'}`;
const panel = (title, ...children) => el('section', {class: 'panel'}, el('div', {class: 'panel-head'}, el('h2', {}, title)), el('div', {class: 'panel-body stack'}, children));
function draft(app, target = {scope: 'project', page_id: null, layer: 'notes'}, ref = null) {
  const info = {...app.info, page_label: target.page_id ? `第 ${app.summary.pages.findIndex(page => page.page_id === target.page_id) + 1} 页` : null};
  app.editor = new DraftEditor(info, target, app.route.revision, ref, {readonly: app.readonly});
  return app.editor.mount();
}
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
export function content(app, data) {
  const inputs = data.inputs;
  const node = el('div', {}, heading('内容与来源', '确认用途、受众和材料，再把内容整理交给制作工具。',
    !app.readonly && button('整理内容并生成大纲', () => app.handoff(), true)));
  if (inputs) {
    node.append(panel('项目要求', el('dl', {class: 'facts'}, el('dt', {}, '用途'), el('dd', {}, inputs.task.brief),
      el('dt', {}, '受众'), el('dd', {}, inputs.task.audience || '未填写'),
      el('dt', {}, '页数目标'), el('dd', {}, inputs.task.page_limit || '未指定'))));
    const sources = el('ul', {class: 'source-list'});
    for (const source of inputs.sources) sources.append(el('li', {}, el('strong', {}, source.name || source.original_name || source.source_id || '材料'),
      el('span', {class: 'muted'}, source.extract ? ' · 已有提取内容，仍需制作工具阅读' : ' · 已登记，待读取')));
    node.append(panel('材料', sources.children.length ? sources : el('p', {class: 'muted'}, '材料暂为空。当前不能判断内容是否足够，请补充材料或在制作工具中明确要求。'),
      !app.readonly && button('补充本机材料', () => addMaterial(app, inputs))));
  } else node.append(el('p', {class: 'notice'}, '此处按固定版本阅读内容计划。当前任务要求可能已经改变，未混入这个版本。'));
  const plan = data.plan;
  if (plan?.status === 'recorded' || plan?.goals?.length) {
    const goals = el('ol', {class: 'goal-list'});
    for (const goal of plan.goals || []) {
      const page = app.summary.pages.find(page => page.page_id === goal.page_id);
      goals.append(el('li', {}, page ? button(page.title || goal.purpose, () => app.go({surface: 'page', page_id: page.page_id, layer: 'content'})) : el('strong', {}, goal.purpose),
        el('p', {class: 'muted'}, goal.purpose), (goal.unresolved_facts || []).map(fact => el('p', {class: 'muted'}, '待确认：' + fact))));
    }
    node.append(panel('内容计划', el('p', {}, plan.input_summary || '按已记录的逐页内容查看。'), goals));
  } else if (app.summary.pages.length) node.append(panel('逐页稿', app.summary.pages.map((page, index) => button(pageTitle(page, index), () => app.go({surface: 'page', page_id: page.page_id, layer: 'content'})))));
  else node.append(empty('逐页稿尚未返回', '项目已建立，内容整理尚待交接。复制交接说明后，需要到 Codex 发送。'));
  node.append(draft(app)); return node;
}
function addMaterial(app, inputs) {
  const paths = field('材料文件完整路径', el('textarea', {required: true, rows: 4, placeholder: '每行一个已有文件的完整路径'}), '路径由本机服务验证。材料登记后，原内容整理任务会失效，由最新任务接续。');
  const notice = el('p', {class: 'field-error', role: 'status'});
  let pending;
  const form = el('form', {class: 'stack'}, paths.node, notice);
  const submit = button('登记材料', () => form.requestSubmit(), true);
  const dialog = modal('补充材料', form, [submit]);
  form.addEventListener('submit', async event => {
    event.preventDefault(); submit.disabled = true;
    try { await app.business?.available(); }
    catch (error) { notice.textContent = readableError(error); submit.disabled = false; return; }
    pending ||= {base_revision: inputs.revision_id, operation_id: 'input-' + crypto.randomUUID(),
      patch: {reason: '在工作台补充材料', source_changes: {add: paths.input.value.split('\n').map(v => v.trim()).filter(Boolean).map(path => ({path}))}}};
    try {
      await post('/api/inputs/update', pending); dialog.close();
      const current = await get('/api/view/summary'); app.go({surface: 'content', revision: current.revision_id}); toast('材料已登记，内容整理仍需交接。');
    } catch (error) {
      const unknown = !error.status || error.status >= 500;
      notice.textContent = readableError(error) + (unknown ? ' 保存结果待核实，重试使用原内容与原操作标识。' : ' 本次材料未登记。');
      submit.textContent = unknown ? '核实原材料登记' : '重新登记';
      paths.input.readOnly = unknown;
      if (!unknown) pending = null;
      submit.disabled = false;
    }
  });
}
export {pageDetail} from './page-workbench.js';
const taskNames = {compose: '整理内容', blueprint: '制作原图', svg: '制作 SVG', render: '渲染预览', repair: '局部修改', review: '检查', export: '准备文件'};
const taskStatus = {awaiting_host: '待交接', running: '已记录处理中', completed: '结果已记录', failed: '执行失败', cancelled: '已取消', superseded: '已由新任务接续', blocked: '需要处理阻碍'};
export function runs(app, data) {
  const selected = data.runDetail?.task || data.tasks.find(task => task.task_id === app.route.task_id);
  const node = el('div', {}, heading(selected ? '当前任务' : '任务与交付', '任务状态按当前阅读版本展示。复制交接说明不会启动模型。',
    selected?.kind === 'compose' && selected.status === 'awaiting_host' && !app.readonly ? button('交接这项内容整理', () => app.handoff(selected.task_id), true) : null));
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
  const revisions = el('select', {'aria-label': '阅读历史版本'}, data.history.revisions.map(revision => el('option', {value: revision.revision_id},
    `${version(revision.revision_id)} · ${revision.page_count} 页${revision.revision_id === data.history.current ? ' · 当前' : ''}`)));
  revisions.value = app.route.revision;
  node.append(panel('版本记录', el('div', {class: 'row wrap'}, revisions, button('读取所选版本', () => app.go({revision: revisions.value, task_id: null})))));
  node.append(panel('交付状态', el('p', {}, app.summary.outputs.pptx.existence === 'recorded' ? '这个版本已记录整稿 PPT 文件，正式交付仍需检查质量与完整性。' : '这个版本尚无整稿 PPT 文件。'),
    el('p', {class: 'muted'}, '可在原有工作区查看已有导出流程。'), el('a', {href: '/'}, '打开原有工作区')));
  return node;
}
export function style(app) {
  return el('div', {}, heading('风格校准', '先阅读固定版本的原图，明确希望保留或调整的部分。'),
    empty('先记录你的风格判断', '个人草稿可保存参考方向。当前工作面尚未接入跨页试作与候选采用。', button('查看整稿原图', () => app.go({surface: 'gallery'}))), draft(app));
}
