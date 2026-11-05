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

let root;
let state;
let payload;
let versions;
let calls;
let readVersion;
const originalFetch = globalThis.fetch;

function snapshot(version) {
  return {
    version, deck: {
      brief: { title: `合成方案 ${version}`, audience: '业务团队', task_type: '首提', goal: `目标 ${version}`, constraints: ['公开材料'], page_limit: 10 },
      framing: { thesis: `主张 ${version}`, pillars: [{ title: '范围', points: ['试点'] }], facts: ['已有流程'], assumptions: [], questions: [] },
      pages: [{
        id: 'p1', purpose: '说明范围', layout: '单栏', notes: `讲稿 ${version}`, todo: ['确认时间'], refs: ['公开说明'],
        content: {
          title: '试点范围', subtitle: `副标题 ${version}`,
          body_blocks: [{ type: 'paragraph', id: 'b1', text: `正文 ${version}` }, {
            type: 'table', id: 'table', title: '预算', columns: [{ id: 'c1', label: '金额' }],
            rows: [{ id: 'r1', cells: [{ id: 's1', column_id: 'c1', display_text: `${version} 元`, value: version, unit: '元' }] }],
          }], labels: [], callouts: [], footnotes: [],
        }, image: { file: 'synthetic.png' }, svg: null, preview: null,
      }, {
        id: 'p2', purpose: '', layout: '', notes: '另一页讲稿', todo: [], refs: [],
        content: { title: '后续安排', subtitle: '', body_blocks: [], labels: [], callouts: [], footnotes: [] },
      }],
    },
  };
}
function history() {
  return [...versions.values()].reverse().map(item => ({ id: item.version, created_at: `2026-11-0${item.version}T00:00:00Z`, summary: `合成改稿 ${item.version}` }));
}
function Probe() {
  state = useDeckMaster();
  return createElement('div', null,
    createElement('button', { onClick: () => state.openDrawer('history') }, '打开历史'),
    createElement(DrawerPanel));
}
async function mount(t) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  versions = new Map([3, 7].map(version => [version, snapshot(version)]));
  versions.get(7).deck.pages.reverse();
  payload = { ...structuredClone(versions.get(7)), history: history(), runs: [], reviews: [], artifact_status: { missing_pages: [], stale_pages: [], stale_images: [] } };
  calls = [];
  readVersion = async version => Response.json(structuredClone(versions.get(version)));
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), method: options.method || 'GET' });
    if (String(url).startsWith('/api/versions/')) return readVersion(Number(String(url).split('/').at(-1)));
    if (String(url).startsWith('/api/restore/')) {
      const restored = structuredClone(versions.get(Number(String(url).split('/').at(-1))));
      restored.version = payload.version + 1;
      versions.set(restored.version, restored);
      payload = { ...payload, ...restored, history: history() };
      return Response.json(restored);
    }
    assert.equal(url, '/api/deck', 'history must not invoke build, Host or other write endpoints');
    return Response.json(structuredClone(payload));
  };
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(Probe))); });
  await click('打开历史');
}
async function click(text, scope = document) {
  const button = [...scope.querySelectorAll('button')].find(node => node.textContent === text);
  assert.ok(button, `missing button: ${text}`);
  assert.equal(button.disabled, false);
  await act(async () => { button.click(); });
}
function entry(version) {
  return [...document.querySelectorAll('[aria-label="历史版本列表"] article')].find(node => node.querySelector('h3').textContent.startsWith(`版本 ${version}`));
}
function reading() { return document.querySelector('[aria-label="历史正文"]'); }
function comparison() { return document.querySelector('[aria-label="历史正文对比"]'); }
async function choose(label, version) {
  const select = [...document.querySelectorAll('label')].find(node => node.querySelector('span')?.textContent === label)?.querySelector('select');
  assert.ok(select);
  assert.equal(select.disabled, false);
  await act(async () => {
    select.value = String(version);
    select.dispatchEvent(new window.Event('change', { bubbles: true }));
  });
}
async function poll(t, version = 8) {
  const next = snapshot(version);
  versions.set(version, next);
  payload = { ...payload, ...structuredClone(next), history: history() };
  await act(async () => { t.mock.timers.tick(1500); });
}
function writes() { return calls.filter(call => call.method !== 'GET'); }

afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  root = null;
  globalThis.fetch = originalFetch;
  document.body.innerHTML = '<div id="root"></div>';
});

test('view reads a frozen historical body; only the explicit whole-deck restore writes and preserves drafts', async t => {
  await mount(t);
  await act(async () => { state.editPage('p1'); state.openContextEdit('brief'); });
  await act(async () => {
    state.updateDraft({ ...state.drafts.p1.page, notes: '未保存讲稿' });
    state.updateContextDraft('brief', { ...state.contextDrafts.brief.value, goal: '未保存目标' });
    state.openDrawer('history');
  });
  const before = structuredClone(state.workspace);
  const drafts = structuredClone({ pages: state.drafts, context: state.contextDrafts });
  await click('查看正文', entry(3));
  assert.ok(reading().textContent.includes('正文 3'));
  assert.ok(reading().textContent.includes('讲稿 3'));
  assert.ok(reading().textContent.includes('3 元'));
  const fieldLabels = [...reading().querySelectorAll('dt')].map(node => node.textContent);
  assert.ok(fieldLabels.includes('作品名称'));
  assert.ok(fieldLabels.includes('页面标题'));
  assert.equal(reading().textContent.includes('正文 7'), false);
  assert.deepEqual(calls.filter(call => call.url.startsWith('/api/versions/')), [{ url: '/api/versions/3', method: 'GET' }]);
  assert.deepEqual(writes(), []);
  assert.deepEqual(state.workspace, before);
  const frozen = reading().innerHTML;
  await poll(t);
  assert.equal(reading().innerHTML, frozen);
  assert.deepEqual(writes(), []);
  await click('整稿恢复到版本 3');
  assert.deepEqual(writes(), [{ url: '/api/restore/3', method: 'POST' }]);
  assert.equal(state.workspace.version, 9);
  assert.equal(state.workspace.deck.pages[0].notes, '讲稿 3');
  assert.deepEqual({ pages: state.drafts, context: state.contextDrafts }, drafts);
  await click('返回历史列表');
  assert.ok(entry(9));
  assert.ok(entry(3));
  await click('查看正文', entry(7));
  assert.ok(reading().textContent.includes('正文 7'));
});

test('comparison freezes both exact versions and scroll position on poll, then refreshes only the right side', async t => {
  await mount(t);
  await click('与当前稿对比', entry(3));
  assert.deepEqual(calls.filter(call => call.url.startsWith('/api/versions/')).map(call => call.url), ['/api/versions/3', '/api/versions/7']);
  for (const value of ['目标 3', '目标 7', '主张 3', '主张 7', '正文 3', '正文 7', '讲稿 3', '讲稿 7']) {
    assert.ok(comparison().textContent.includes(value), value);
  }
  assert.ok(comparison().textContent.includes('位置变化'));
  const details = comparison().querySelector('details');
  details.open = true;
  const frozen = comparison().innerHTML;
  const drawer = document.querySelector('.drawer-body');
  drawer.scrollTop = 184;
  await poll(t);
  assert.match(document.querySelector('.history-panel > .s4-message').textContent, /8/);
  assert.equal(comparison().innerHTML, frozen);
  assert.equal(details.open, true);
  assert.equal(drawer.scrollTop, 184);
  assert.deepEqual(writes(), []);
  const leftMeta = comparison().querySelector('header').innerHTML;
  await click('刷新右侧比较');
  assert.deepEqual(calls.filter(call => call.url.startsWith('/api/versions/')).map(call => call.url), ['/api/versions/3', '/api/versions/7', '/api/versions/8']);
  assert.equal(comparison().querySelector('header').innerHTML, leftMeta);
  assert.ok(comparison().textContent.includes('正文 8'));
  assert.ok(comparison().textContent.includes('正文 3'));
  assert.equal(comparison().textContent.includes('正文 7'), false);
  assert.equal(document.querySelector('.history-panel > .s4-message'), null);
  assert.equal(state.workspace.version, 8);
  assert.deepEqual(writes(), []);
  await poll(t, 9);
  assert.ok(document.querySelector('.history-panel > .s4-message'));
  await choose('左侧版本', 7);
  assert.ok(comparison().textContent.includes('正文 7'));
  assert.ok(comparison().textContent.includes('正文 8'));
  await choose('右侧版本', 3);
  assert.ok(comparison().textContent.includes('正文 3'));
  assert.deepEqual(writes(), []);
});

test('a deliberate historical right selection stops following current until current is selected again', async t => {
  await mount(t);
  await click('与当前稿对比', entry(3));
  await choose('右侧版本', 3);
  const refreshButton = () => [...document.querySelectorAll('button')].find(node => node.textContent === '刷新右侧比较');
  assert.equal(document.querySelector('.history-panel > .s4-message'), null);
  assert.equal(refreshButton(), undefined);
  const frozen = comparison().innerHTML;
  await poll(t);
  assert.equal(comparison().innerHTML, frozen);
  assert.equal(document.querySelector('.history-panel > .s4-message'), null);
  assert.equal(refreshButton(), undefined);
  await choose('左侧版本', 7);
  assert.equal(document.querySelector('.history-panel > .s4-message'), null);
  await choose('右侧版本', 8);
  await poll(t, 9);
  assert.ok(document.querySelector('.history-panel > .s4-message'));
  assert.ok(refreshButton());
  assert.deepEqual(writes(), []);
});

test('late reads cannot overwrite a newer selection or a closed history panel', async t => {
  await mount(t);
  const pending = new Map();
  readVersion = version => new Promise(resolve => { pending.set(version, resolve); });
  await click('查看正文', entry(3));
  await choose('阅读版本', 7);
  await act(async () => { pending.get(7)(Response.json(versions.get(7))); });
  assert.ok(reading().textContent.includes('正文 7'));
  await act(async () => { pending.get(3)(Response.json(versions.get(3))); });
  assert.ok(reading().textContent.includes('正文 7'));
  assert.equal(reading().textContent.includes('正文 3'), false);
  await click('返回历史列表');
  await click('与当前稿对比', entry(3));
  await click('关闭');
  await act(async () => {
    pending.get(3)(Response.json(versions.get(3)));
    pending.get(7)(Response.json(versions.get(7)));
  });
  await click('打开历史');
  assert.ok(entry(3));
  assert.equal(comparison(), null);
  assert.deepEqual(writes(), []);
});

test('a missing history version shows the read failure and can retry without falling back to current', async t => {
  await mount(t);
  readVersion = async () => Response.json({ error: '版本不存在，请重新选择' }, { status: 404 });
  await click('查看正文', entry(3));
  assert.ok(document.querySelector('[role="alert"]'));
  assert.equal(reading(), null);
  assert.equal(state.workspace.version, 7);
  assert.deepEqual(writes(), []);
  readVersion = async version => Response.json(versions.get(version));
  await click('重试读取');
  assert.ok(reading().textContent.includes('正文 3'));
});

test('failed refresh keeps both frozen sides and retries only the right snapshot', async t => {
  await mount(t);
  await click('与当前稿对比', entry(3));
  const frozen = comparison().innerHTML;
  await poll(t);
  readVersion = async () => Response.json({ error: '读取暂时失败' }, { status: 500 });
  await click('刷新右侧比较');
  assert.equal(comparison().innerHTML, frozen);
  assert.ok(document.querySelector('[role="alert"]'));
  readVersion = async version => Response.json(versions.get(version));
  await click('重试读取');
  assert.ok(comparison().textContent.includes('正文 8'));
  assert.equal(calls.filter(call => call.url === '/api/versions/3').length, 1);
  assert.deepEqual(writes(), []);
});

test('artifact-only comparison reports no body change and ID-free content shows full readable blocks', async t => {
  await mount(t);
  const old = versions.get(3);
  versions.set(7, { version: 7, deck: structuredClone(old.deck) });
  versions.get(7).deck.pages[0].image = { file: 'changed.png' };
  await click('与当前稿对比', entry(3));
  assert.ok(comparison().querySelector('[role="status"]'));
  assert.equal(comparison().querySelector('details'), null);
  await click('返回历史列表');
  for (const version of [3, 7]) {
    const page = versions.get(version).deck.pages[0];
    delete page.content.body_blocks[0].id;
    page.content.body_blocks[0].text = `完整正文 ${version}`;
  }
  await click('与当前稿对比', entry(3));
  for (const text of ['完整前后值', '完整正文 3', '完整正文 7', '3 元']) assert.ok(comparison().textContent.includes(text));
  assert.deepEqual(writes(), []);
});
