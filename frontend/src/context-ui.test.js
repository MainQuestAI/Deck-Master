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
const { default: OverviewView } = await import('./components/scenes/OverviewView.jsx');

const brief = { title: '合成方案', audience: '业务团队', task_type: '首提', goal: '确认范围', constraints: ['只用公开信息', '先小范围试点'], page_limit: 12 };
const framing = { thesis: '先试点再扩大', pillars: [{ title: '范围', points: ['两批试点', '每批两周'] }, { title: '行动', points: ['安排负责人'] }], facts: ['已有流程'], assumptions: ['有负责人'], questions: ['何时开始？'] };
let root;
let state;
let payload;
let write;
let requests;
let hidden = false;

function Probe() {
  state = useDeckMaster();
  return state.workspace && !hidden ? createElement(OverviewView) : null;
}

async function mount(t) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  payload = {
    version: 7, deck: { brief: structuredClone(brief), framing: structuredClone(framing), pages: [] },
    artifact_status: { missing_pages: [], stale_pages: [], stale_images: [] }, runs: [], reviews: [],
  };
  requests = [];
  hidden = false;
  write = async patch => {
    payload = { ...payload, version: payload.version + 1, deck: { ...payload.deck, ...structuredClone(patch) } };
    return Response.json({ version: payload.version, deck: payload.deck });
  };
  globalThis.fetch = async (url, options = {}) => {
    if (options.method !== 'PUT') return Response.json(structuredClone(payload));
    const patch = JSON.parse(options.body);
    requests.push({ url, patch });
    return write(patch);
  };
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(Probe))); });
}

function section(kind) {
  return document.querySelector(`section[aria-label="${kind === 'brief' ? '任务信息' : '业务框架'}"]`);
}

async function click(text, scope = document) {
  const button = [...scope.querySelectorAll('button')].find(node => (node.getAttribute('aria-label') || node.textContent) === text);
  assert.ok(button, `missing button: ${text}`);
  assert.equal(button.disabled, false, `disabled button: ${text}`);
  await act(async () => { button.click(); });
}

function input(label, scope = document) {
  const node = [...scope.querySelectorAll('label')].find(node => node.querySelector('span')?.textContent === label);
  assert.ok(node, `missing field: ${label}`);
  return node.querySelector('input, textarea');
}

async function fill(label, value) {
  const node = input(label);
  const prototype = node.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(node, value);
    node.dispatchEvent(new window.Event('input', { bubbles: true }));
  });
}

async function poll(t) {
  await act(async () => { t.mock.timers.tick(1500); });
}

afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  root = null;
  document.body.innerHTML = '<div id="root"></div>';
});

test('overview keeps draft input through collapse, polling, scene changes and failed saves', async t => {
  await mount(t);
  await click('编辑任务信息');
  await fill('希望对方理解或做出什么判断', '确认试点');
  await click('收起编辑', section('brief'));
  payload.version++;
  payload.deck.brief.goal = '服务器目标';
  await poll(t);
  await click('编辑任务信息');
  assert.equal(input('希望对方理解或做出什么判断').value, '确认试点');
  hidden = true;
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(Probe))); });
  hidden = false;
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(Probe))); });
  await click('编辑任务信息');
  assert.equal(input('希望对方理解或做出什么判断').value, '确认试点');
  write = async () => Response.json({ error: '服务暂时不可用' }, { status: 503 });
  await click('保存任务信息');
  assert.ok(state.contextDrafts.brief.error);
  assert.equal(input('希望对方理解或做出什么判断').value, '确认试点');
  assert.deepEqual(requests[0], { url: '/api/deck?base=7', patch: { brief: { ...brief, goal: '确认试点' } } });
});

for (const kind of ['brief', 'framing']) {
  for (const saved of [false, true]) {
    test(`${kind} reopens a clean draft from the polled workspace after ${saved ? 'saving' : 'closing without edits'}`, async t => {
      await mount(t);
      const title = kind === 'brief' ? '任务信息' : '业务框架';
      const field = kind === 'brief' ? '希望对方理解或做出什么判断' : '中心主张';
      const key = kind === 'brief' ? 'goal' : 'thesis';
      await click(`编辑${title}`);
      if (saved) {
        await fill(field, '已保存的输入');
        await click(`保存${title}`);
      }
      await click('收起编辑', section(kind));
      payload.version++;
      payload.deck[kind][key] = '服务器更新的内容';
      const server = structuredClone(payload.deck[kind]);
      const version = payload.version;
      await poll(t);
      assert.ok(section(kind).textContent.includes('服务器更新的内容'));
      await click(`编辑${title}`);
      assert.equal(input(field).value, '服务器更新的内容');
      assert.equal(state.contextDrafts[kind].base, version);
      assert.deepEqual(state.contextDrafts[kind].original, server);
      assert.deepEqual(state.contextDrafts[kind].value, server);
      assert.equal(section(kind).querySelector('button[type="submit"]').disabled, true);
      await fill(field, '基于服务器更新继续修改');
      await click(`保存${title}`);
      assert.deepEqual(requests.at(-1), {
        url: `/api/deck?base=${version}`, patch: { [kind]: { ...server, [key]: '基于服务器更新继续修改' } },
      });
    });
  }
}

test('brief accepts custom tasks, list ordering and an empty page limit, then accepts the server result', async t => {
  await mount(t);
  await click('编辑任务信息');
  await fill('本次任务', '试点复盘');
  await fill('页数上限（可留空）', '');
  await click('添加已有决定与实际约束');
  await fill('已有决定与实际约束 3', '只讨论本次试点');
  await click('已有决定与实际约束 3上移');
  await click('移除已有决定与实际约束 1');
  write = async patch => {
    payload.version++;
    payload.deck.brief = { ...patch.brief, title: '服务端返回标题' };
    return Response.json({ version: payload.version, deck: payload.deck });
  };
  await click('保存任务信息');
  assert.deepEqual(requests[0].patch, { brief: { ...brief, task_type: '试点复盘', page_limit: null, constraints: ['只讨论本次试点', '先小范围试点'] } });
  assert.equal(input('作品标题').value, '服务端返回标题');
  assert.equal(section('brief').querySelector('button[type="submit"]').disabled, true);
  await act(async () => { section('brief').querySelector('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })); });
  assert.equal(requests.length, 1);
});

test('framing moves whole groups without losing supporting lists and allows an empty framework', async t => {
  await mount(t);
  await click('编辑业务框架');
  await fill('分组 1 支持点 1', '三批试点');
  await click('分组 1下移');
  await click('保存业务框架');
  assert.deepEqual(requests[0].patch, { framing: { ...framing, pillars: [framing.pillars[1], { ...framing.pillars[0], points: ['三批试点', '每批两周'] }] } });
  await click('移除分组 1');
  await click('移除分组 1');
  await fill('中心主张', '');
  for (const label of ['已知事实', '当前假设', '待回答问题']) {
    await click(`移除${label} 1`);
  }
  await click('保存业务框架');
  assert.deepEqual(requests[1].patch, { framing: { thesis: '', pillars: [], facts: [], assumptions: [], questions: [] } });
  assert.equal(state.contextDrafts.framing.error, '');
});

for (const kind of ['brief', 'framing']) {
  for (const keepMine of [false, true]) {
    test(`${kind} conflict requires an explicit whole-unit choice (${keepMine ? 'mine' : 'server'})`, async t => {
      await mount(t);
      const title = kind === 'brief' ? '任务信息' : '业务框架';
      const field = kind === 'brief' ? '希望对方理解或做出什么判断' : '中心主张';
      const key = kind === 'brief' ? 'goal' : 'thesis';
      await click(`编辑${title}`);
      await fill(field, '我的输入');
      payload.version = 9;
      payload.deck[kind][key] = '服务器输入';
      const server = structuredClone(payload.deck[kind]);
      const mine = structuredClone(state.contextDrafts[kind].value);
      const save = write;
      write = async patch => Response.json({ exit_code: 5, submitted: patch, conflicts: [{ unit: kind, current: server }] }, { status: 409 });
      await click(`保存${title}`);
      assert.equal(input(field).value, '我的输入');
      assert.equal(section(kind).querySelector('button[type="submit"]').disabled, true);
      assert.ok(section(kind).querySelector('[aria-label="服务器当前整单元"]').textContent.includes('服务器输入'));
      assert.ok(section(kind).querySelector('[aria-label="我的整单元"]').textContent.includes('我的输入'));
      await poll(t);
      assert.deepEqual(state.contextDrafts[kind].value, mine);
      await click(keepMine ? '保留我的整单元，核对后再保存' : '采用服务器当前整单元');
      assert.equal(state.contextDrafts[kind].base, 9);
      assert.equal(state.contextDrafts[kind].conflict, null);
      assert.deepEqual(state.contextDrafts[kind].value, keepMine ? mine : server);
      assert.equal(requests.length, 1);
      if (keepMine) {
        write = save;
        await click(`保存${title}`);
        assert.deepEqual(requests[1], { url: '/api/deck?base=9', patch: { [kind]: mine } });
      } else assert.equal(section(kind).querySelector('button[type="submit"]').disabled, true);
    });
  }
}

test('a failed read after 409 keeps both inputs and requires a successful read before resolution', async t => {
  await mount(t);
  await click('编辑任务信息');
  await fill('希望对方理解或做出什么判断', '我的待保存目标');
  payload.version = 8;
  payload.deck.brief.goal = '服务器的当前目标';
  const fetchDeck = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    if (options.method === 'PUT') return Response.json({ exit_code: 5, conflicts: [{ unit: 'brief', current: payload.deck.brief }] }, { status: 409 });
    throw new Error('read unavailable');
  };
  await click('保存任务信息');
  assert.equal(state.contextDrafts.brief.base, 7);
  assert.equal(state.contextDrafts.brief.value.goal, '我的待保存目标');
  assert.ok(state.contextDrafts.brief.error);
  assert.ok(section('brief').querySelector('[aria-label="服务器当前整单元"]').textContent.includes('服务器的当前目标'));
  assert.equal([...section('brief').querySelectorAll('button')].find(button => button.textContent === '采用服务器当前整单元').disabled, true);
  globalThis.fetch = fetchDeck;
  await click('重新读取服务器当前内容');
  assert.equal(state.contextDrafts.brief.base, 7);
  assert.equal(state.contextDrafts.brief.error, '');
  await click('保留我的整单元，核对后再保存');
  assert.equal(state.contextDrafts.brief.base, 8);
  assert.equal(state.contextDrafts.brief.value.goal, '我的待保存目标');
});

test('reopening retains an unresolved conflict even when input matches the original', async t => {
  await mount(t);
  await click('编辑任务信息');
  await fill('希望对方理解或做出什么判断', '我的输入');
  payload.version++;
  payload.deck.brief.goal = '服务器输入';
  write = async () => Response.json({ exit_code: 5, conflicts: [{ unit: 'brief', current: payload.deck.brief }] }, { status: 409 });
  await click('保存任务信息');
  await fill('希望对方理解或做出什么判断', brief.goal);
  const draft = state.contextDrafts.brief;
  assert.deepEqual(draft.value, draft.original);
  assert.ok(draft.conflict);
  await click('收起编辑', section('brief'));
  payload.version++;
  payload.deck.brief.goal = '服务器再次更新';
  await poll(t);
  await click('编辑任务信息');
  assert.equal(state.contextDrafts.brief, draft);
  assert.equal(input('希望对方理解或做出什么判断').value, brief.goal);
  assert.equal(section('brief').querySelector('button[type="submit"]').disabled, true);
  assert.ok(section('brief').querySelector('[aria-label="服务器当前整单元"]').textContent.includes('服务器输入'));
});

test('new framing groups and supporting lists remain editable and preserve existing context', async t => {
  await mount(t);
  await click('编辑业务框架');
  await click('添加分组');
  await fill('分组 3 标题', '复盘');
  await click('添加分组 3 支持点');
  await fill('分组 3 支持点 1', '检查试点');
  await click('添加分组 3 支持点');
  await fill('分组 3 支持点 2', '决定后续范围');
  await click('分组 3 支持点 2上移');
  await click('移除分组 3 支持点 2');
  for (const label of ['已知事实', '当前假设', '待回答问题']) {
    await click(`添加${label}`);
    await fill(`${label} 2`, `${label}补充`);
    await click(`${label} 2上移`);
  }
  await click('保存业务框架');
  assert.deepEqual(requests[0].patch, { framing: {
    ...framing,
    pillars: [...framing.pillars, { title: '复盘', points: ['决定后续范围'] }],
    facts: ['已知事实补充', ...framing.facts],
    assumptions: ['当前假设补充', ...framing.assumptions],
    questions: ['待回答问题补充', ...framing.questions],
  } });
});
