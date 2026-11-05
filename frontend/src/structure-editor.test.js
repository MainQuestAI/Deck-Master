import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://127.0.0.1/' });
const { window } = dom;
for (const [key, value] of Object.entries({
  window, document: window.document, navigator: window.navigator, HTMLElement: window.HTMLElement,
  localStorage: window.localStorage, IS_REACT_ACT_ENVIRONMENT: true,
})) Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });

const { createElement, act } = await import('react');
const { createRoot } = await import('react-dom/client');
const { DeckMasterProvider, useDeckMaster } = await import('./context/DeckMasterContext.jsx');
const { default: DrawerPanel } = await import('./components/modals/DrawerPanel.jsx');
const originalFetch = globalThis.fetch;
let root;
let state;
let payload;
let writes;
let normalize;

function page() {
  return {
    id: 'p1', purpose: '说明试点', layout: '比较', notes: '保留讲稿', todo: ['补充范围'], refs: ['合成材料第 1 页'],
    content: {
      title: '合成试点', subtitle: '分步推进',
      body_blocks: [{ type: 'table', id: 'table', title: '合成预算',
        columns: [{ id: 'col-a', label: '项目' }, { id: 'col-b', label: '预算' }],
        rows: [
          { id: 'row-a', cells: [{ id: 'cell-a', column_id: 'col-b', display_text: '约20万元', value: 200000, unit: '元' }, { id: 'cell-b', column_id: 'col-a', display_text: '试点', value: false }] },
          { id: 'row-b', cells: [{ id: 'cell-c', column_id: 'col-a', display_text: '后续', value: { range: [1, 2] } }, { id: 'cell-d', column_id: 'col-b', display_text: '待定', value: 0, unit: '%' }] },
        ],
      }],
      labels: [{ id: 'label', text: '保留标签' }], callouts: [{ id: 'callout', text: '保留补充' }], footnotes: [{ id: 'footnote', text: '保留脚注' }],
    },
    image: { file: 'synthetic.png' }, svg: null, preview: null,
  };
}

function Probe() {
  state = useDeckMaster();
  return state.workspace ? createElement(DrawerPanel) : null;
}

async function mount(t, original = page()) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  payload = { version: 7, deck: { brief: { title: '合成方案' }, pages: [original] }, runs: [], reviews: [] };
  writes = [];
  normalize = value => value;
  globalThis.fetch = async (url, options = {}) => {
    if (options.method !== 'PUT') return Response.json(structuredClone(payload));
    const patch = JSON.parse(options.body);
    writes.push({ url, patch });
    payload.version++;
    payload.deck.pages = payload.deck.pages.map(item => normalize({ ...item, ...patch.pages.find(entry => entry.id === item.id) }));
    return Response.json({ version: payload.version, deck: payload.deck });
  };
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(Probe))); });
  await act(async () => { state.editPage('p1'); });
}

async function click(label, scope = document) {
  const node = [...scope.querySelectorAll('button')].find(item => (item.getAttribute('aria-label') || item.textContent) === label);
  assert.ok(node, `missing button: ${label}`);
  assert.equal(node.disabled, false, `disabled button: ${label}`);
  await act(async () => { node.click(); });
}

function input(label) {
  const field = [...document.querySelectorAll('label')].find(node => node.querySelector('span')?.textContent === label);
  assert.ok(field, `missing field: ${label}`);
  return field.querySelector('input, textarea, select');
}

async function fill(label, value) {
  const node = input(label);
  const prototype = node.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : node.tagName === 'SELECT' ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(node, value);
    node.dispatchEvent(new window.Event(node.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  });
}

const draft = () => state.drafts.p1.page;
const table = () => draft().content.body_blocks.find(block => block.type === 'table');

afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  root = null;
  globalThis.fetch = originalFetch;
  document.body.innerHTML = '<div id="root"></div>';
});

test('drawer adds/moves a column, deletes a row and saves full content with correct column_id cells (B5)', async t => {
  const original = page();
  await mount(t, structuredClone(original));
  await click('添加列');
  const columnId = table().columns.at(-1).id;
  assert.equal(document.activeElement, input('表格 1 列标题 3'));
  assert.ok(table().rows.every(row => row.cells.find(cell => cell.column_id === columnId)?.id));
  await fill('表格 1 列标题 3', '负责人');
  await fill('表格 1 第 1 行 第 3 列', '试点团队');
  await click('表格 1 第 3 列左移');
  assert.equal(input('表格 1 第 1 行 第 2 列').value, '试点团队');
  assert.equal(input('表格 1 第 1 行 第 3 列').value, '约20万元');
  await click('删除表格 1 第 2 行');
  assert.deepEqual(table().rows[0].cells.slice(0, 2), original.content.body_blocks[0].rows[0].cells);
  const submitted = structuredClone(draft().content);
  normalize = value => ({ ...value, content: { ...value.content, title: '服务端规范化标题' } });
  await click('保存正文与讲稿');
  assert.deepEqual(writes, [{ url: '/api/deck?base=7', patch: { pages: [{ id: 'p1', content: submitted }] } }]);
  const savedTable = writes[0].patch.pages[0].content.body_blocks[0];
  assert.ok(savedTable.rows.every(row => savedTable.columns.every(column => row.cells.some(cell => cell.column_id === column.id))));
  assert.equal(state.drawer, null);
  await act(async () => { state.editPage('p1'); });
  assert.equal(input('页面标题').value, '服务端规范化标题');
  assert.deepEqual(draft().todo, original.todo);
  assert.deepEqual(draft().refs, original.refs);
  assert.equal(draft().notes, original.notes);
});

test('todo/refs save sends only those page fields', async t => {
  await mount(t);
  await click('添加待补');
  await fill('待补 2', '补充试点边界');
  await click('添加出处');
  await fill('出处 2', '合成材料第 2 页');
  await click('保存正文与讲稿');
  assert.deepEqual(writes, [{
    url: '/api/deck?base=7',
    patch: { pages: [{ id: 'p1', todo: ['补充范围', '补充试点边界'], refs: ['合成材料第 1 页', '合成材料第 2 页'] }] },
  }]);
});

test('notes-only save excludes content and all unrelated fields', async t => {
  await mount(t);
  await fill('讲稿', '只更新讲稿');
  await click('保存正文与讲稿');
  assert.deepEqual(writes, [{ url: '/api/deck?base=7', patch: { pages: [{ id: 'p1', notes: '只更新讲稿' }] } }]);
});

test('block and bullet editing preserves siblings, nested tone and all auxiliary content (C4)', async t => {
  const original = page();
  await mount(t, structuredClone(original));
  await click('添加正文段落');
  await fill('正文段落 2', '一行很长的中文内容，说明试点范围与行动。'.repeat(10));
  await click('添加要点');
  await fill('要点组 3 1', '试点');
  await act(async () => {
    const pageDraft = structuredClone(draft());
    pageDraft.content.body_blocks[2].items[0].children = [{ id: 'child', text: '既有子项', tone: 'emphasis' }];
    state.updateDraft(pageDraft);
  });
  await fill('要点组 3 1 子项 1', '修改子项');
  await click('添加要点组 3条目');
  await fill('要点组 3 2', '后续');
  await click('要点组 3 2上移');
  await click('移除要点组 3 2及其 1 个子项');
  assert.deepEqual(draft().content.body_blocks[2].items.map(item => item.text), ['后续']);
  await click('正文块 3上移');
  await click('移除正文块 3（含全部内容）');
  await click('添加表格');
  const added = draft().content.body_blocks.at(-1);
  assert.ok(added.id && added.rows[0].id && added.rows[0].cells[0].id);
  assert.equal(added.rows[0].cells[0].column_id, added.columns[0].id);
  await click('保存正文与讲稿');
  const saved = writes[0].patch.pages[0].content;
  assert.deepEqual(saved.body_blocks.map(block => block.type), ['table', 'bullets', 'table']);
  for (const key of ['labels', 'callouts', 'footnotes']) assert.deepEqual(saved[key], original.content[key]);
});

test('scalar metadata edits/clear are explicit; zero, false and complex values survive display edits', async t => {
  const original = page();
  await mount(t, structuredClone(original));
  assert.equal(input('表格 1 第 1 行 第 1 列 原始值（布尔）').value, 'false');
  assert.equal(input('表格 1 第 2 行 第 2 列 原始值（数字）').value, '0');
  const complex = document.querySelector('pre');
  assert.deepEqual(JSON.parse(complex.textContent), { range: [1, 2] });
  assert.equal(complex.closest('details').querySelectorAll('input').length, 1);
  await fill('表格 1 第 1 行 第 2 列', '待定');
  assert.deepEqual(table().rows[0].cells[0], { ...original.content.body_blocks[0].rows[0].cells[0], display_text: '待定' });
  await fill('表格 1 第 1 行 第 2 列 原始值（数字）', '0');
  await fill('表格 1 第 1 行 第 2 列 单位', '%');
  await fill('表格 1 第 1 行 第 1 列 原始值（布尔）', 'true');
  await click('清空表格 1 第 2 行 第 2 列原始值');
  await fill('表格 1 第 2 行 第 2 列 单位', '');
  await click('保存正文与讲稿');
  const rows = writes[0].patch.pages[0].content.body_blocks[0].rows;
  assert.deepEqual(rows[0].cells[0], { ...original.content.body_blocks[0].rows[0].cells[0], display_text: '待定', value: 0, unit: '%' });
  assert.equal(rows[0].cells[1].value, true);
  assert.deepEqual(rows[1].cells[0], original.content.body_blocks[0].rows[1].cells[0]);
  assert.deepEqual(rows[1].cells[1], { ...original.content.body_blocks[0].rows[1].cells[1], value: null, unit: null });
});

test('empty tables remain editable and adding a row focuses its first cell', async t => {
  const original = page();
  original.content.body_blocks[0] = { type: 'table', id: 'empty', title: '', columns: [], rows: [] };
  await mount(t, original);
  await click('添加列');
  await click('添加行');
  assert.equal(document.activeElement, input('表格 1 第 1 行 第 1 列'));
  await fill('表格 1 第 1 行 第 1 列', '约20%');
  await click('表格 1 删除第 1 列及其单元格');
  assert.deepEqual(table().rows[0].cells, []);
  await click('删除表格 1 第 1 行');
  await fill('表格 1 标题', '空表草稿');
  await click('保存正文与讲稿');
  const saved = writes[0].patch.pages[0].content.body_blocks[0];
  assert.deepEqual(saved.rows, []);
  assert.deepEqual(saved.columns, []);
});

test('existing nested items and string raw values remain editable without dropping tone', async t => {
  const original = page();
  original.content.body_blocks.push({ type: 'bullets', id: 'bullets', heading: '范围', items: [{ id: 'parent', text: '试点', tone: 'emphasis', children: [{ id: 'child', text: '首批' }] }] });
  original.content.body_blocks[0].rows[0].cells[1].value = '原始文本';
  await mount(t, original);
  await fill('要点组 2 1 子项 1', '第二批');
  await fill('表格 1 第 1 行 第 1 列 原始值（文本）', '显式修改');
  await click('保存正文与讲稿');
  const saved = writes[0].patch.pages[0].content;
  assert.deepEqual(saved.body_blocks[1].items[0], { ...original.content.body_blocks[1].items[0], children: [{ id: 'child', text: '第二批' }] });
  assert.deepEqual(saved.body_blocks[0].rows[0].cells[1], { ...original.content.body_blocks[0].rows[0].cells[1], value: '显式修改' });
});
