import {get, post, fileURL, readableError} from './api.js';
import {el, button, heading, empty, field, version, modal, toast} from './dom.js';
import {layers} from './routes.js';
import {DraftEditor} from './drafts.js';

const stageKey = {content: 'content', original_image: 'blueprint', svg: 'svg', ppt: 'ppt_preview'};
const stageLabel = stage => !stage || stage.existence === 'not_generated' ? '未生成' : stage.existence !== 'recorded' ? '暂不可读' :
  stage.applicability?.status === 'basis_changed' ? '依据已变化' : stage.applicability?.status === 'current' ? '可看' : '适用性待核实';
const pageTitle = (page, index) => `第 ${index + 1} 页 · ${page.title || '未命名页面'}`;
const panel = (title, ...children) => el('section', {class: 'panel'}, el('div', {class: 'panel-head'}, el('h2', {}, title)), el('div', {class: 'panel-body stack'}, children));
function draft(app, target = {scope: 'project', page_id: null, layer: 'notes'}, ref = null) {
  const info = {...app.info, page_label: target.page_id ? `第 ${app.summary.pages.findIndex(page => page.page_id === target.page_id) + 1} 页` : null};
  app.editor = new DraftEditor(info, target, app.route.revision, ref, {readonly: app.readonly});
  return app.editor.mount();
}
function imageFigure(stage, title, onOpen) {
  const image = stage?.existence === 'recorded' && fileURL(stage.file);
  const body = el('div', {class: 'image-frame'});
  if (image) {
    const img = el('img', {src: image, alt: title, loading: 'lazy', decoding: 'async'});
    img.addEventListener('error', () => body.replaceChildren(el('p', {class: 'muted'}, '此图暂不可读。原位置保留。'), button('重新读取图片', () => { body.replaceChildren(img); img.src = image; })));
    body.append(img);
  } else body.append(el('span', {class: 'muted'}, stageLabel(stage)));
  return el('figure', {class: 'slide-tile'}, onOpen ? button(body, onOpen, false, {class: 'image-button', 'aria-label': title}) : body,
    el('figcaption', {}, el('strong', {}, title), el('p', {class: 'muted'}, `${stageLabel(stage)} · 原图`)));
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
export function gallery(app) {
  return el('div', {}, heading('整稿画廊', `${app.summary.page_count} 页 · 原图 · ${version(app.route.revision)}。点击图片查看该页。`),
    app.summary.page_count ? el('div', {class: 'gallery'}, app.summary.pages.map((page, index) =>
      imageFigure(page.stages.blueprint, pageTitle(page, index), () => app.go({surface: 'page', page_id: page.page_id, layer: 'original_image'})))) :
      empty('还没有原图', '先到内容与来源整理逐页稿，再交接制作要求。', button('查看内容与来源', () => app.go({surface: 'content'}))));
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
function bulletItems(items) {
  return el('ul', {}, items.map(item => el('li', {}, typeof item === 'string' ? item : item.text, item.children?.length ? bulletItems(item.children) : null)));
}
function bodyBlocks(blocks) {
  return (blocks || []).map(block => {
    if (block.type === 'paragraph') return el('p', {}, block.text);
    if (block.type === 'bullets') return el('section', {}, block.heading && el('h3', {}, block.heading), bulletItems(block.items));
    if (block.type === 'table') return el('div', {class: 'table-scroll'}, el('table', {class: 'body-table'}, block.title && el('caption', {}, block.title),
      el('thead', {}, el('tr', {}, block.columns.map(col => el('th', {scope: 'col'}, col.label)))),
      el('tbody', {}, block.rows.map(row => el('tr', {}, block.columns.map(col => el('td', {}, row.cells.find(cell => cell.column_id === col.id)?.display_text || '')))))));
    return el('p', {class: 'muted'}, '这个内容块暂不可读。');
  });
}
export function pageDetail(app, data) {
  const index = app.summary.pages.findIndex(page => page.page_id === app.route.page_id);
  const page = app.summary.pages[index]; const layer = app.route.layer;
  const node = el('div', {}, heading(pageTitle(page, index), `${layers[layer]} · ${version(app.route.revision)} · 固定阅读基准`));
  const selector = el('select', {'aria-label': '转到页面'});
  app.summary.pages.forEach((page, n) => selector.append(el('option', {value: page.page_id, selected: n === index}, pageTitle(page, n))));
  selector.value = page.page_id; selector.addEventListener('change', () => app.go({page_id: selector.value}));
  const tabs = el('nav', {class: 'layer-tabs', 'aria-label': '页面层'});
  for (const [value, label] of Object.entries(layers)) tabs.append(button(label, () => app.go({layer: value}), false, {'aria-current': value === layer ? 'page' : null, class: value === layer ? 'active' : ''}));
  node.append(el('div', {class: 'toolbar'}, selector, button('回到整稿画廊', () => app.go({surface: 'gallery'}))), tabs);
  let ref = data.stages[stageKey[layer]]?.ref || null;
  const main = el('section', {class: 'page-reading stack', 'aria-label': '页面内容'});
  if (layer === 'content') {
    main.append(el('article', {class: 'page-copy stack'}, el('h2', {}, data.page?.customer_visible?.title || '逐页稿暂不可读'),
      data.page?.customer_visible?.subtitle && el('p', {}, data.page.customer_visible.subtitle),
      data.page?.customer_visible?.body_blocks?.length ? bodyBlocks(data.page.customer_visible.body_blocks) : el('p', {class: 'muted'}, '此页未记录正文块。'),
      ['callouts', 'labels', 'footnotes'].flatMap(key => (data.page?.customer_visible?.[key] || []).map(item => el('p', {class: key}, item.text)))));
    main.append(el('details', {class: 'source-detail'}, el('summary', {}, '内容来源'),
      data.sources.citations.length ? el('pre', {class: 'read-text'}, JSON.stringify(data.sources.citations, null, 2)) : el('p', {class: 'muted'}, '此页未记录材料引用。')));
  } else if (layer === 'submitted_prompt' || layer === 'prepared_prompt') {
    const prepared = data.prompts.prepared;
    if (layer === 'submitted_prompt') {
      ref = data.prompts.submitted.ref;
      main.append(el('h2', {}, '这张原图的实际提示词'), data.prompts.submitted.text !== null ?
        el('div', {}, el('p', {class: 'muted'}, data.prompts.submitted.observer === 'tool_observed' ? '已由工具调用记录核实' : '由制作工具报告，未独立观察实际调用'), el('pre', {class: 'read-text'}, data.prompts.submitted.text)) :
        empty('实际提示词未记录', '现有预备稿不能证明实际使用了相同内容。', button('查看预备提示词', () => app.go({layer: 'prepared_prompt'}))));
    } else {
      ref = prepared.length === 1 ? prepared[0].ref : null;
      main.append(el('h2', {}, '预备提示词'), el('p', {class: 'muted'}, '这是准备交给制作工具的内容；是否实际使用，以实际调用记录为准。'),
        prepared.length ? prepared.map(item => el('article', {class: 'panel-body'}, el('pre', {class: 'read-text'}, item.text))) : empty('尚无预备提示词', '此页没有记录可读取的预备稿。'));
    }
  } else {
    const stage = data.stages[stageKey[layer]];
    const url = stage?.existence === 'recorded' && fileURL(stage.file);
    const viewport = el('div', {class: 'page-image-viewport', tabindex: '0', 'aria-label': `${layers[layer]}阅读画布`});
    if (url && stage.media_type?.startsWith('image/')) {
      const img = el('img', {class: 'page-image', src: url, alt: `${pageTitle(page, index)} · ${layers[layer]}`});
      img.style.width = `${(app.route.zoom || 1) * 100}%`;
      img.addEventListener('error', () => { viewport.replaceChildren(empty('这张图片暂不可读', '固定版本和个人草稿保持，可重新读取。', button('重新读取', () => app.loadRoute()))); });
      viewport.append(img);
    } else viewport.append(empty(`${layers[layer]}${stageLabel(stage)}`, layer === 'ppt' ? '只有这个版本的逐页 PPT 预览才会出现在这里。' : '没有用其它层的图片替代。可回到逐页稿查看内容。'));
    const zoom = el('select', {'aria-label': '阅读缩放'}, [.5, .75, 1, 1.25, 1.5, 2, 3].map(value => el('option', {value}, `${value * 100}%`)));
    if (![.5, .75, 1, 1.25, 1.5, 2, 3].includes(app.route.zoom)) zoom.append(el('option', {value: app.route.zoom}, `${app.route.zoom * 100}%`));
    zoom.value = String(app.route.zoom || 1); zoom.addEventListener('change', () => app.go({zoom: Number(zoom.value)}));
    main.append(el('div', {class: 'row'}, el('label', {}, '阅读缩放 ', zoom), el('span', {class: 'muted'}, stageLabel(stage))), viewport);
  }
  const target = {scope: 'page', page_id: page.page_id, layer};
  let notes;
  if (layer === 'prepared_prompt' && data.prompts.prepared.length > 1) {
    const select = el('select', {'aria-label': '选择草稿绑定的预备提示词'}, el('option', {value: ''}, '先选择具体预备稿'));
    data.prompts.prepared.forEach((item, index) => select.append(el('option', {value: item.ref.sha256}, `预备稿 ${index + 1} · ${version(item.dispatch_revision)}`)));
    const slot = el('div', {}, el('p', {class: 'muted'}, '同一页有多份预备稿。个人草稿需要绑定其中一份，避免混淆依据。'));
    select.addEventListener('change', () => {
      const selected = data.prompts.prepared.find(item => item.ref.sha256 === select.value);
      if (!selected) return;
      app.editor?.dispose();
      main.replaceChildren(el('h2', {}, '所选预备提示词'), el('p', {class: 'muted'}, '是否实际使用，以实际调用记录为准。'), el('pre', {class: 'read-text'}, selected.text));
      slot.replaceChildren(draft(app, target, selected.ref));
    });
    notes = el('aside', {class: 'stack'}, el('label', {}, '选择个人草稿的依据', select), slot);
  } else notes = draft(app, target, ref);
  node.append(el('div', {class: 'page-columns'}, main, notes));
  return node;
}
const taskNames = {compose: '整理内容', blueprint: '制作原图', svg: '制作 SVG', render: '渲染预览', repair: '局部修改', review: '检查', export: '准备文件'};
const taskStatus = {awaiting_host: '待交接', running: '已记录处理中', completed: '结果已记录', failed: '执行失败', cancelled: '已取消', superseded: '已由新任务接续', blocked: '需要处理阻碍'};
export function runs(app, data) {
  const selected = data.tasks.find(task => task.task_id === app.route.task_id);
  const node = el('div', {}, heading(selected ? '当前任务' : '任务与交付', '任务状态按当前阅读版本展示。复制交接说明不会启动模型。',
    selected?.kind === 'compose' && selected.status === 'awaiting_host' && !app.readonly ? button('交接这项内容整理', () => app.handoff(selected.task_id), true) : null));
  if (selected && app.returnTo && !app.returnTo.task_id) node.append(button('返回上次工作面', () => app.go(app.returnTo)));
  const tasks = selected ? [selected] : data.tasks;
  node.append(tasks.length ? el('div', {class: 'task-list stack'}, tasks.map(task => el('article', {class: 'panel task-row'},
    el('div', {}, el('h2', {}, taskNames[task.kind] || '制作任务'), el('p', {class: 'muted'}, `${taskStatus[task.status] || '状态待核实'} · 任务 ${task.task_id}`),
      task.result_refs?.length > 0 && el('p', {class: 'muted'}, `${task.result_refs.length} 项已记录结果；这不代表专业质量通过。`)),
    !selected && button('查看这项任务', () => app.go({task_id: task.task_id})), selected && button('查看全部任务', () => app.go({task_id: null}))))) : empty('没有已记录的任务', '此版本还没有制作任务。'));
  node.append(panel('版本记录', data.history.revisions.map(revision => button(`${version(revision.revision_id)} · ${revision.page_count} 页${revision.revision_id === data.history.current ? ' · 当前' : ' · 只读查看'}`,
    () => app.go({revision: revision.revision_id, task_id: null})))));
  node.append(panel('交付状态', el('p', {}, app.summary.outputs.pptx.existence === 'recorded' ? '这个版本已记录整稿 PPT 文件，正式交付仍需检查质量与完整性。' : '这个版本尚无整稿 PPT 文件。'),
    el('p', {class: 'muted'}, '可在原有工作区查看已有导出流程。'), el('a', {href: '/'}, '打开原有工作区')));
  return node;
}
export function style(app) {
  return el('div', {}, heading('风格校准', '先阅读固定版本的原图，明确希望保留或调整的部分。'),
    empty('先记录你的风格判断', '个人草稿可保存参考方向。当前工作面尚未接入跨页试作与候选采用。', button('查看整稿原图', () => app.go({surface: 'gallery'}))), draft(app));
}
