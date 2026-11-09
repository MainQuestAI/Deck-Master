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
const { default: PageReaderView } = await import('./components/scenes/PageReaderView.jsx');
const { formatFinding, fileUrl } = await import('./api.js');
const originalFetch = globalThis.fetch;
let root;
let state;
let payload;
let requests;
let buildFindings;
let reviewFails;

function page(id, original = 'a', preview = 'b') {
  return {
    id, purpose: '解释流程', layout: '右侧保留证据', notes: '说明交接', todo: [], refs: [],
    content: { title: `合成页面 ${id}`, body_blocks: [{ type: 'paragraph', text: '核对流程', id: 'text' }] },
    image: original ? { file: `${original.repeat(64)}.png`, basis: 'image-basis' } : null,
    svg: { file: `${'e'.repeat(64)}.svg`, basis: 'svg-basis' },
    preview: preview ? `${preview.repeat(64)}.png` : null,
  };
}

function Probe() {
  state = useDeckMaster();
  if (!state.workspace) return null;
  return createElement('div', null,
    state.actionError && createElement('p', { role: 'alert' }, state.actionError),
    createElement(PageReaderView));
}

async function mount(t, first = page('p1')) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  payload = {
    version: 7,
    deck: { brief: { title: '合成流程' }, style: { canvas: { width_px: 1280, height_px: 720 } }, pages: [first, page('p2', 'c', 'd')] },
    artifact_status: { missing_pages: [], stale_images: ['p1'], stale_pages: ['p1'] },
    runs: [], reviews: [],
  };
  requests = [];
  buildFindings = [];
  reviewFails = false;
  globalThis.fetch = async (url, options = {}) => {
    const method = options.method || 'GET';
    const body = options.body && JSON.parse(options.body);
    requests.push({ url, method, body });
    if (url === '/api/build') { payload.default_build = { id: 1, version_id: 7 }; return Response.json({ id: 1 }); }
    if (url === '/api/builds/1') return Response.json({ id: 1, version_id: 7, current_version: payload.version, readback_available: true, readback_matches_current: true, pages: payload.deck.pages.map((page, index) => ({ page_id: page.id, source_order: index + 1 })), findings: { findings: buildFindings } });
    if (url === '/api/reviews') {
      if (reviewFails) return Response.json({ error: '暂时无法保存' }, { status: 500 });
      const review = { id: 12, version_id: 7, page_id: null, method: 'human', ...body };
      payload.reviews.push(review);
      return Response.json(review);
    }
    if (url === '/api/reviews/12/resolve') {
      payload.reviews = payload.reviews.filter(review => review.id !== 12);
      return Response.json({ id: 12, status: 'resolved' });
    }
    assert.equal(url, '/api/deck', 'comparison must not create a run or call a provider');
    return Response.json(structuredClone(payload));
  };
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(Probe))); });
  await act(async () => { state.openPage('p1'); });
}

async function click(label) {
  const button = [...document.querySelectorAll('button')].find(node => node.textContent === label);
  assert.ok(button, `missing action: ${label}`);
  assert.equal(button.disabled, false);
  await act(async () => { button.click(); });
}

async function change(node, value) {
  assert.ok(node);
  const prototype = node.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(node, String(value));
    node.dispatchEvent(new window.Event('input', { bubbles: true }));
    node.dispatchEvent(new window.Event('change', { bubbles: true }));
  });
}

const images = () => [...document.querySelectorAll('.page-comparison img')].map(node => node.getAttribute('src'));
const control = label => document.querySelector(`input[aria-label="${label}"]`);
const viewports = () => [...document.querySelectorAll('.page-comparison-viewport')];

afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  root = null;
  globalThis.fetch = originalFetch;
  document.body.innerHTML = '<div id="root"></div>';
});

test('same selected page compares original on the left and adopted preview on the right with stale status', async t => {
  await mount(t);
  payload.runs = [{ id: 9, kind: 'svg', pages: [{ page_id: 'p1', result_preview: 'candidate.png' }] }];
  await act(async () => { await state.refresh(); });
  await click('原图／编译预览对照');
  assert.deepEqual(images(), [fileUrl(payload.deck.pages[0].image.file), fileUrl(payload.deck.pages[0].preview)]);
  assert.equal(document.querySelectorAll('.page-comparison .badge.warn').length, 2);
  assert.equal(requests.some(request => request.method !== 'GET'), false);
  assert.equal(state.comparison, null);
  assert.ok(document.querySelector('.page-comparison').textContent.includes('讲稿见正文层'));
  assert.ok([...document.querySelectorAll('button')].some(node => node.textContent === '修改正文与讲稿'));
});

test('zoom and horizontal/vertical region controls share one view and reset on a different selected page', async t => {
  await mount(t);
  await click('原图／编译预览对照');
  assert.equal(control('横向查看位置').disabled, true);
  await change(control('对照缩放'), 250);
  await change(control('横向查看位置'), 80);
  await change(control('纵向查看位置'), 20);
  for (const viewport of viewports()) {
    assert.equal(viewport.style.getPropertyValue('--compare-scale'), '2.5');
    assert.equal(viewport.style.getPropertyValue('--compare-left'), '-120%');
    assert.equal(viewport.style.getPropertyValue('--compare-top'), '-30%');
  }
  await act(async () => { await state.refresh(); });
  assert.equal(control('对照缩放').value, '250');
  await click('查看整页');
  assert.equal(control('对照缩放').value, '100');
  assert.equal(control('横向查看位置').value, '50');
  await change(control('对照缩放'), 300);
  await act(async () => { state.openPage('p2'); });
  assert.deepEqual(images(), [fileUrl(payload.deck.pages[1].image.file), fileUrl(payload.deck.pages[1].preview)]);
  assert.equal(control('对照缩放').value, '100');
  assert.equal(document.querySelectorAll('.page-comparison .badge.warn').length, 0);
});

for (const [original, preview] of [[null, 'b'], ['a', null], [null, null]]) {
  test(`missing artwork stays missing without using another layer (${original}, ${preview})`, async t => {
    await mount(t, page('p1', original, preview));
    await click('原图／编译预览对照');
    const expected = [payload.deck.pages[0].image?.file, payload.deck.pages[0].preview].filter(Boolean).map(fileUrl);
    assert.deepEqual(images(), expected);
    assert.equal(document.querySelectorAll('.page-comparison .s4-empty').length, 2 - expected.length);
    assert.ok(images().every(url => !url.includes('eeee')));
  });
}

test('an attachment load failure remains an error until retried and never substitutes the opposite image', async t => {
  await mount(t);
  await click('原图／编译预览对照');
  const img = document.querySelector('.page-comparison img');
  await act(async () => { img.dispatchEvent(new window.Event('error')); });
  assert.deepEqual(images(), [fileUrl(payload.deck.pages[0].preview)]);
  assert.ok(document.querySelector('.page-comparison [role="alert"]'));
  await click('重新加载附件');
  assert.deepEqual(images(), [fileUrl(payload.deck.pages[0].image.file), fileUrl(payload.deck.pages[0].preview)]);
});

test('comparison filters build findings by page and retains real object and region locators without invented boxes', async t => {
  await mount(t);
  buildFindings = [
    { page_id: 'p1', code: 'reversed_arrow', edge_id: 'edge-4', from: 'node-4', to: 'node-2' },
    { page_id: 'p1', code: 'table_cell_ownership_mismatch', table_id: 'table-1', row_id: 'row-2', column_id: 'col-3', atom_id: 'atom-1',
      svg_elements: ['text-1'], position: [144, 216], cell_bounds: [100, 200, 300, 400],
      native_carriers: [{ native_shape_id: '9', element: 'text-1', x: 144, y: 216, width: 80, height: 30 }] },
    { page_id: 'p1', code: 'shape_outside_slide', element: 'text-2', bounds: [-10, 20, 30, 40], slide: [12192000, 6858000] },
    { page_id: 'p2', code: 'missing_node', node_id: 'other-page-node' },
    { code: 'slide_count_mismatch', expected: 2, actual: 1 },
  ];
  await act(async () => { await state.build(); });
  await click('原图／编译预览对照');
  const findings = [...document.querySelectorAll('.page-comparison-findings > li')];
  assert.equal(findings.length, 3);
  for (const [index, finding] of buildFindings.slice(0, 3).entries()) assert.ok(findings[index].textContent.includes(formatFinding(finding)));
  const fields = finding => Object.fromEntries([...finding.querySelectorAll('dl > div')].map(row => [row.querySelector('dt').textContent, row.querySelector('dd').textContent]));
  for (const [label, value] of Object.entries({ 表格: 'table-1', 行: 'row-2', 列: 'col-3', 文字对象: 'atom-1' })) {
    assert.equal(fields(findings[1])[label], value);
  }
  assert.equal(fields(findings[2])['SVG 元素'], 'text-2');
  assert.equal(document.querySelector('.page-comparison-findings').textContent.includes('other-page-node'), false);
  assert.deepEqual([...findings[0].querySelectorAll('dd')].map(node => node.textContent), ['edge-4', 'node-4', 'node-2']);
  assert.equal(document.querySelectorAll('.page-comparison-findings svg, .page-comparison-findings rect, .page-comparison-findings [data-bbox]').length, 0);
  await act(async () => { state.openPage('p2'); });
  assert.equal(document.querySelectorAll('.page-comparison-findings > li').length, 1);
  assert.ok(document.querySelector('.page-comparison-findings').textContent.includes('other-page-node'));
});

test('no session readback is distinguished from a build with no same-page findings', async t => {
  await mount(t);
  await click('原图／编译预览对照');
  const before = document.querySelector('.page-comparison-readback').textContent;
  assert.equal(document.querySelectorAll('.page-comparison-findings > li').length, 0);
  await act(async () => { await state.build(); });
  assert.notEqual(document.querySelector('.page-comparison-readback').textContent, before);
  assert.equal(document.querySelectorAll('.page-comparison-findings > li').length, 0);
});

test('reader keeps original single-layer switches', async t => {
  await mount(t);
  await click('原图');
  assert.deepEqual([...document.querySelectorAll('img')].map(node => node.getAttribute('src')), [fileUrl(payload.deck.pages[0].image.file)]);
  await click('SVG 预览');
  assert.deepEqual([...document.querySelectorAll('img')].map(node => node.getAttribute('src')), [fileUrl(payload.deck.pages[0].preview)]);
  await click('正文');
  assert.equal(document.querySelectorAll('img').length, 0);
});

test('natural-language review from comparison uses the existing page scope and resolve chain, retaining failed drafts', async t => {
  await mount(t);
  await click('原图／编译预览对照');
  const text = '  不够像流程\n节点 4 应连接 2  ';
  await change(document.querySelector('textarea'), text);
  reviewFails = true;
  await click('保存意见');
  assert.equal(document.querySelector('textarea').value, text);
  assert.equal(state.reviewDrafts['page:p1'], text);
  assert.ok(document.querySelector('[role="alert"]'));
  reviewFails = false;
  await click('保存意见');
  assert.equal(document.querySelector('textarea').value, '');
  assert.deepEqual(requests.filter(request => request.url === '/api/reviews').map(request => request.body), [{ text, page_id: 'p1' }, { text, page_id: 'p1' }]);
  assert.equal(document.querySelectorAll('.s5-reviews li').length, 1);
  assert.ok(document.querySelector('.s5-reviews').textContent.includes(text));
  await act(async () => { state.openPage('p2'); });
  assert.equal(document.querySelectorAll('.s5-reviews li').length, 0);
  await act(async () => { state.openPage('p1'); });
  await click('标记已处理');
  assert.equal(document.querySelectorAll('.s5-reviews li').length, 0);
  assert.equal(requests.filter(request => request.url === '/api/reviews/12/resolve').length, 1);
  assert.equal(state.workspace.version, 7);
});


test('persistent details refresh for changed default IDs and ignore a late older detail', async t => {
  await mount(t);
  const previousFetch = globalThis.fetch;
  let finishOld;
  const details = [];
  globalThis.fetch = async (url, options) => {
    if (url.startsWith('/api/builds/')) {
      details.push(url);
      if (url === '/api/builds/1') return new Promise(resolve => { finishOld = resolve; });
      return Response.json({ id: 2, version_id: 7, current_version: payload.version, readback_matches_current: true, readback_available: true, pages: [], findings: { findings: [] } });
    }
    return previousFetch(url, options);
  };
  payload.default_build = { id: 1, version_id: 7 };
  await act(async () => { await state.refresh(); });
  assert.equal(typeof finishOld, 'function');
  payload.default_build = { id: 2, version_id: 7 };
  await act(async () => { await state.refresh(); });
  assert.equal(state.buildResult.id, 2);
  await act(async () => { finishOld(Response.json({ id: 1, current_version: 7, readback_matches_current: true })); });
  assert.equal(state.buildResult.id, 2);
  await act(async () => { await state.refresh(); await state.refresh(); });
  assert.deepEqual(details, ['/api/builds/1', '/api/builds/2']);
  payload.version += 1;
  await act(async () => { await state.refresh(); });
  assert.equal(details.length, 3);
  assert.equal(state.buildResult.current_version, payload.version);
});

test('detail transport errors remain visible and do not become empty passing findings', async t => {
  await mount(t);
  const previousFetch = globalThis.fetch;
  globalThis.fetch = (url, options) => url.startsWith('/api/builds/')
    ? Promise.resolve(Response.json({ error: 'Stored readback is unreadable' }, { status: 500 }))
    : previousFetch(url, options);
  payload.default_build = { id: 1, version_id: 7 };
  await act(async () => { await state.refresh(); });
  await click('原图／编译预览对照');
  assert.equal(state.buildResult, null);
  assert.equal(state.buildError, 'Stored readback is unreadable');
  assert.ok(document.querySelector('[role="alert"]').textContent.includes('Stored readback is unreadable'));
});

for (const imported of [true, false]) {
  test(`a page without a stored report is not shown as zero findings (imported=${imported})`, async t => {
    await mount(t);
    const previousFetch = globalThis.fetch;
    globalThis.fetch = (url, options) => url.startsWith('/api/builds/')
      ? Promise.resolve(Response.json({ id: 1, version_id: 7, current_version: 7, readback_available: !imported, pages: [], findings: { findings: [] } }))
      : previousFetch(url, options);
    payload.default_build = { id: 1, version_id: 7 };
    await act(async () => { await state.refresh(); });
    await click('原图／编译预览对照');
    const panel = document.querySelector('.page-comparison-readback');
    assert.equal(panel.querySelector('h2').textContent.includes('（0）'), false);
    assert.equal(panel.querySelectorAll('.page-comparison-findings').length, 0);
    assert.ok(panel.textContent.includes(imported ? '该导入成品没有构建回读' : '本页未参与该次构建'));
  });
}
