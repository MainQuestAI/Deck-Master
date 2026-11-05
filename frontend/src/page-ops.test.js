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
const { default: ContentView } = await import('./components/scenes/ContentView.jsx');
const { default: PageReaderView } = await import('./components/scenes/PageReaderView.jsx');
const { default: DrawerPanel } = await import('./components/modals/DrawerPanel.jsx');
const originalFetch = globalThis.fetch;
let root;
let state;
let payload;
let write;
let requests;
let confirmations;
let showReader;

function page(id) {
  return { id, content: { title: `合成页面 ${id}`, body_blocks: [] }, purpose: '说明方案', layout: '', notes: `${id} 讲稿`, todo: [], refs: [], image: { file: `${id}.png` }, svg: null, preview: null };
}

function Probe() {
  state = useDeckMaster();
  if (!state.workspace) return null;
  return createElement('div', null, createElement(showReader ? PageReaderView : ContentView), showReader && createElement(DrawerPanel));
}

function saved(patch) {
  const pages = patch.order.map(id => payload.deck.pages.find(item => item.id === id));
  payload = { ...payload, version: payload.version + 1, deck: { ...payload.deck, pages } };
  return Response.json({ version: payload.version, deck: payload.deck });
}

async function mount(t, ids = ['p1', 'p2', 'p3']) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  payload = { version: 7, deck: { brief: { title: '合成方案' }, pages: ids.map(page) }, runs: [], reviews: [] };
  requests = [];
  confirmations = [];
  showReader = false;
  write = async patch => saved(patch);
  window.confirm = text => { confirmations.push(text); return true; };
  globalThis.fetch = async (url, options = {}) => {
    const patch = options.method === 'PUT' ? JSON.parse(options.body) : undefined;
    requests.push({ url, method: options.method || 'GET', patch });
    return patch ? write(patch) : Response.json(structuredClone(payload));
  };
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(Probe))); });
  await act(async () => { state.setScene('content'); });
}

const puts = () => requests.filter(item => item.method === 'PUT');
const ids = () => state.pages.map(item => item.id);
const row = index => document.querySelectorAll('article')[index];
function button(text, scope = document) {
  const node = [...scope.querySelectorAll('button')].find(item => item.textContent === text);
  assert.ok(node, `missing button: ${text}`);
  return node;
}
async function click(text, scope = document) {
  const node = button(text, scope);
  assert.equal(node.disabled, false, `disabled button: ${text}`);
  await act(async () => { node.click(); });
}
async function selectPosition(index, position) {
  const node = row(index).querySelector('select');
  assert.ok(node.getAttribute('aria-label'));
  await act(async () => {
    node.value = String(position - 1);
    node.dispatchEvent(new window.Event('change', { bubbles: true }));
  });
}
async function draft(id, notes) {
  await act(async () => { state.editPage(id); });
  await act(async () => { state.updateDraft({ ...state.drafts[id].page, notes }); });
}

afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  root = null;
  globalThis.fetch = originalFetch;
  document.body.innerHTML = '<div id="root"></div>';
});

test('up and down submit only the full order and keep selection, page bodies and file references', async t => {
  await mount(t);
  await act(async () => { state.openPage('p2'); });
  const before = structuredClone(state.pages);
  assert.equal(button('上移', row(0)).disabled, true);
  assert.equal(button('下移', row(2)).disabled, true);
  await click('上移', row(1));
  assert.deepEqual(puts()[0], { url: '/api/deck?base=7', method: 'PUT', patch: { order: ['p2', 'p1', 'p3'] } });
  assert.deepEqual(ids(), ['p2', 'p1', 'p3']);
  assert.equal(state.currentPage, 'p2');
  assert.equal(row(0).getAttribute('aria-current'), 'true');
  await click('下移', row(0));
  assert.deepEqual(puts()[1].patch, { order: ['p1', 'p2', 'p3'] });
  assert.equal(puts()[1].url, '/api/deck?base=8');
  assert.equal(state.currentPage, 'p2');
  assert.deepEqual(state.pages, before);
  assert.deepEqual(confirmations, []);
});

test('move-to uses a labelled select and form submission without a reorder confirmation', async t => {
  await mount(t);
  assert.equal(button('应用', row(0)).disabled, true);
  const select = row(0).querySelector('select');
  assert.deepEqual([...select.options].map(option => option.value), ['0', '1', '2']);
  await selectPosition(0, 3);
  await act(async () => { row(0).querySelector('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })); });
  assert.deepEqual(puts()[0].patch, { order: ['p2', 'p3', 'p1'] });
  assert.deepEqual(ids(), ['p2', 'p3', 'p1']);
  assert.equal(row(2).querySelector('select').value, '2');
  assert.deepEqual(confirmations, []);
  await act(async () => { await state.movePage('p1', 2); });
  assert.equal(puts().length, 1);
});

test('remove preserves all drafts, selects the previous neighbor and reopens the orphan read-only', async t => {
  await mount(t);
  await draft('p1', '其他页未保存讲稿');
  await draft('p2', '移除页未保存讲稿');
  const before = structuredClone(state.drafts);
  await click('从当前稿件移除', row(1));
  assert.deepEqual(puts()[0].patch, { order: ['p1', 'p3'], pages: [{ id: 'p2' }] });
  assert.equal(confirmations.length, 1);
  assert.ok(confirmations[0].includes('合成页面 p2') && confirmations[0].includes('历史'));
  assert.deepEqual(ids(), ['p1', 'p3']);
  assert.equal(state.currentPage, 'p1');
  assert.equal(state.drawer, null);
  assert.deepEqual(state.drafts, before);
  await act(async () => { t.mock.timers.tick(1500); });
  assert.deepEqual(state.drafts, before);
  showReader = true;
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(Probe))); });
  await click('查看未保存输入');
  const dialog = document.querySelector('[role="dialog"]');
  assert.ok(dialog);
  assert.equal(state.currentPage, 'p2');
  assert.equal(dialog.querySelector('textarea').readOnly, true);
  assert.ok([...dialog.querySelectorAll('textarea')].some(node => node.value === '移除页未保存讲稿' && node.readOnly));
  assert.equal([...dialog.querySelectorAll('button')].some(node => node.textContent === '保存正文与讲稿'), false);
  assert.equal(puts().length, 1);
});

test('remove chooses the next neighbor for the first page and clears selection for an empty deck', async t => {
  await mount(t, ['p1', 'p2']);
  await act(async () => { state.openPage('p1'); });
  await click('从当前稿件移除', row(0));
  assert.equal(state.currentPage, 'p2');
  assert.equal(state.scene, 'page');
  await click('从当前稿件移除', row(0));
  assert.deepEqual(puts()[1].patch, { order: [], pages: [{ id: 'p2' }] });
  assert.equal(state.currentPage, null);
  assert.equal(state.scene, 'content');
  assert.equal(document.querySelectorAll('article').length, 0);
  assert.ok(document.querySelector('.s4-empty'));
});

test('remove closes presentation and comparison that refer to the removed page', async t => {
  await mount(t);
  await act(async () => {
    state.openPage('p2');
    state.setPresentation('p2');
    state.compareCandidate({ id: 1, kind: 'image' }, { page_id: 'p2', result_file: 'candidate.png' });
  });
  await click('从当前稿件移除', row(1));
  assert.equal(state.currentPage, 'p1');
  assert.equal(state.presentation, null);
  assert.equal(state.comparison, null);
  assert.equal(state.scene, 'content');
});

test('the last removed page draft remains reachable from the empty content view', async t => {
  await mount(t, ['p1']);
  await draft('p1', '空稿时仍能找回的输入');
  const before = structuredClone(state.drafts.p1);
  await click('从当前稿件移除', row(0));
  assert.equal(state.currentPage, null);
  assert.equal(state.scene, 'content');
  assert.ok(document.querySelector('.s4-empty'));
  await click('查看未保存输入');
  assert.equal(state.currentPage, 'p1');
  assert.equal(state.drawer, 'editor');
  assert.deepEqual(state.drafts.p1, before);
  assert.deepEqual(ids(), []);
  assert.equal(puts().length, 1);
});

test('removing another page leaves selection, presentation and comparison intact', async t => {
  await mount(t);
  await act(async () => {
    state.openPage('p3');
    state.setPresentation('p3');
    state.compareCandidate({ id: 1, kind: 'image' }, { page_id: 'p3', result_file: 'candidate.png' });
  });
  const comparison = state.comparison;
  await click('从当前稿件移除', row(0));
  assert.equal(state.currentPage, 'p3');
  assert.equal(state.presentation, 'p3');
  assert.equal(state.comparison, comparison);
  assert.equal(state.scene, 'compare');
});

test('cancelling remove confirmation performs no write', async t => {
  await mount(t);
  window.confirm = () => false;
  await click('从当前稿件移除', row(1));
  assert.equal(puts().length, 0);
  assert.deepEqual(ids(), ['p1', 'p2', 'p3']);
});

for (const destination of ['other-page', 'removed-page']) {
  test(`remove handles navigation to ${destination} while the request is pending`, async t => {
    await mount(t);
    await act(async () => { state.openPage('p2'); });
    let finish;
    write = patch => new Promise(resolve => { finish = () => resolve(saved(patch)); });
    await click('从当前稿件移除', row(1));
    if (destination === 'other-page') {
      await act(async () => { state.editPage('p3'); });
    } else {
      await act(async () => { state.openPage('p1'); });
      await act(async () => { state.editPage('p2'); });
      await act(async () => { state.compareCandidate({ id: 1, kind: 'image' }, { page_id: 'p2', result_file: 'candidate.png' }); });
    }
    await act(async () => { finish(); });
    assert.equal(state.currentPage, destination === 'other-page' ? 'p3' : 'p1');
    assert.equal(state.drawer, destination === 'other-page' ? 'editor' : null);
    assert.equal(state.comparison, null);
    if (destination === 'removed-page') assert.equal(state.scene, 'content');
  });
}

for (const operation of ['move', 'remove']) {
  test(`${operation} locks all page-order controls and ignores another call before completion`, async t => {
    await mount(t);
    let finish;
    write = patch => new Promise(resolve => { finish = () => resolve(saved(patch)); });
    await click(operation === 'move' ? '上移' : '从当前稿件移除', row(1));
    assert.equal(state.busy['page-order'], true);
    for (const article of document.querySelectorAll('article')) {
      for (const label of ['上移', '下移', '应用', '从当前稿件移除']) assert.equal(button(label, article).disabled, true);
    }
    await act(async () => { await state.movePage('p3', 0); await state.removePage('p1'); });
    assert.equal(puts().length, 1);
    await act(async () => { finish(); });
    assert.equal(state.busy['page-order'], false);
    assert.equal(puts().length, 1);
  });

  test(`${operation} conflict reloads without resubmitting the old patch or discarding drafts`, async t => {
    await mount(t);
    await draft('p2', '冲突后仍在的输入');
    const before = structuredClone(state.drafts);
    write = async () => {
      payload.version = 8;
      payload.deck.pages = [page('p4'), ...payload.deck.pages];
      return Response.json({ error: '页面顺序发生冲突', conflicts: [{ unit: 'order', current: ['p4', 'p1', 'p2', 'p3'] }] }, { status: 409 });
    };
    await click(operation === 'move' ? '上移' : '从当前稿件移除', row(1));
    assert.deepEqual(puts(), [{ url: '/api/deck?base=7', method: 'PUT', patch: operation === 'move'
      ? { order: ['p2', 'p1', 'p3'] } : { order: ['p1', 'p3'], pages: [{ id: 'p2' }] } }]);
    assert.equal(requests.at(-1).method, 'GET');
    assert.deepEqual(ids(), ['p4', 'p1', 'p2', 'p3']);
    assert.equal(state.currentPage, 'p2');
    assert.deepEqual(state.drafts, before);
    assert.ok(document.querySelector('[role="alert"]').textContent.includes(state.actionError));
    assert.ok(state.actionError);
    assert.equal(state.busy['page-order'], false);
    await act(async () => { t.mock.timers.tick(1500); });
    assert.equal(puts().length, 1);
    write = async patch => saved(patch);
    await click('上移', row(2));
    assert.deepEqual(puts()[1], { url: '/api/deck?base=8', method: 'PUT', patch: { order: ['p4', 'p2', 'p1', 'p3'] } });
  });
}

test('failed move shows the error, retains its target and unlocks for an explicit retry', async t => {
  await mount(t);
  write = async () => Response.json({ error: '保存失败，请稍后重试' }, { status: 503 });
  await selectPosition(0, 3);
  await click('应用', row(0));
  assert.ok(state.actionError);
  assert.equal(row(0).querySelector('select').value, '2');
  assert.equal(button('应用', row(0)).disabled, false);
  assert.deepEqual(ids(), ['p1', 'p2', 'p3']);
  assert.equal(puts().length, 1);
  write = async patch => saved(patch);
  await click('应用', row(0));
  assert.deepEqual(ids(), ['p2', 'p3', 'p1']);
  assert.equal(state.actionError, '');
});
