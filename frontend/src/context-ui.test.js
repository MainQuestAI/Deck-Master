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
const { default: PageReaderView } = await import('./components/scenes/PageReaderView.jsx');
const { hasUnsavedInputs } = await import('./api.js');

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
  if (!state.workspace || hidden) return null;
  if (state.scene === 'page') return createElement(PageReaderView);
  return createElement(OverviewView);
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
    if (options.method === 'POST' && url === '/api/reviews') {
      const body = JSON.parse(options.body);
      requests.push({ url, method: 'POST', body });
      const created = { id: payload.reviews.length + 1, method: 'human', version_id: payload.version, page_id: body.page_id ?? null, text: body.text };
      payload.reviews = [...payload.reviews, created];
      return Response.json(created);
    }
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

test('conflict keepMine preserves concurrent server updates to v7 brief and framing fields', async t => {
  await mount(t);
  payload.deck.brief = {
    ...brief,
    decision: '',
    concerns: [],
    narrator: { role: '', tone: '' },
  };
  payload.deck.framing = {
    ...framing,
    storyline: [],
  };
  await poll(t);

  // Brief conflict: author only edits title while Host fills v7 fields.
  await click('编辑任务信息');
  await fill('作品标题', '作者修订标题');
  payload.version = 8;
  payload.deck.brief = {
    ...payload.deck.brief,
    decision: '批准试点预算',
    concerns: ['交付周期', '合规边界'],
    narrator: { role: '项目负责人', tone: '直接给判断' },
  };
  const serverBrief = structuredClone(payload.deck.brief);
  const save = write;
  write = async () => Response.json({ exit_code: 5, conflicts: [{ unit: 'brief', current: serverBrief }] }, { status: 409 });
  await click('保存任务信息');
  const serverBriefView = section('brief').querySelector('[aria-label="服务器当前整单元"]').textContent;
  assert.ok(serverBriefView.includes('批准试点预算'));
  assert.ok(serverBriefView.includes('交付周期'));
  assert.ok(serverBriefView.includes('项目负责人 · 直接给判断'));
  await click('保留我的整单元，核对后再保存');
  write = save;
  await click('保存任务信息');
  assert.deepEqual(requests[1].patch, {
    brief: {
      ...serverBrief,
      title: '作者修订标题',
    },
  });

  // Framing conflict: author only edits thesis while Host fills storyline.
  await click('编辑业务框架');
  await fill('中心主张', '作者修订主张');
  payload.version = 10;
  payload.deck.framing = {
    ...payload.deck.framing,
    storyline: ['现状痛点', '试点方案', '决策建议'],
  };
  const serverFraming = structuredClone(payload.deck.framing);
  write = async () => Response.json({ exit_code: 5, conflicts: [{ unit: 'framing', current: serverFraming }] }, { status: 409 });
  await click('保存业务框架');
  assert.ok(section('framing').querySelector('[aria-label="服务器当前整单元"]').textContent.includes('现状痛点'));
  await click('保留我的整单元，核对后再保存');
  write = save;
  await click('保存业务框架');
  assert.deepEqual(requests[3].patch, {
    framing: {
      ...serverFraming,
      thesis: '作者修订主张',
    },
  });
});

test('overview edits v7 brief/framing intent fields without blocking partial saves and renders derived summary panel', async t => {
  await mount(t);
  payload.writing_brief = '讲述人：业务负责人。语气：先给结论。\n待决事项：批准试点预算。';
  payload.outline = [{ page_id: 'p1', kind: 'judgment', title: '试点建议' }];
  payload.gap_list = [
    { page_id: 'p1', source: 'evidence', text: '去年基线', gap: '缺少同期数据' },
    { page_id: 'p1', source: 'todo', text: '补充预算明细' },
  ];
  payload.deck.pages = [{
    id: 'p1', purpose: '结论', layout: '', notes: '', todo: [], refs: [], kind: 'judgment', argument: null,
    content: { title: '试点建议', subtitle: '', body_blocks: [], labels: [], callouts: [], footnotes: [] },
    image: null, svg: null, preview: null,
  }];
  await poll(t);

  const summary = document.querySelector('details[aria-label="写作简报、提纲与缺口汇总"]');
  assert.ok(summary);
  assert.ok(summary.textContent.includes('讲述人：业务负责人'));
  assert.ok(summary.textContent.includes('试点建议'));
  assert.ok(summary.textContent.includes('判断页'));
  assert.ok(summary.textContent.includes('缺少同期数据'));
  assert.ok(summary.textContent.includes('补充预算明细'));

  await click('编辑任务信息');
  assert.ok(section('brief').textContent.includes('待补提示（不影响保存）'));
  await fill('待决事项', '批准第一阶段试点预算');
  await click('添加读者关注点');
  await fill('读者关注点 1', '投入产出比');
  await click('添加读者关注点');
  await fill('读者关注点 2', '交付周期');
  await fill('讲述人角色', '项目负责人');
  await fill('讲述语气', '直接给结论');
  await click('保存任务信息');
  assert.deepEqual(requests[0].patch, {
    brief: {
      ...brief,
      decision: '批准第一阶段试点预算',
      concerns: ['投入产出比', '交付周期'],
      narrator: { role: '项目负责人', tone: '直接给结论' },
    },
  });

  await click('编辑业务框架');
  await click('添加故事主线');
  await fill('故事主线 1', '痛点与现状');
  await click('添加故事主线');
  await fill('故事主线 2', '试点方案与预期收益');
  await click('保存业务框架');
  assert.deepEqual(requests[1].patch, {
    framing: {
      ...framing,
      storyline: ['痛点与现状', '试点方案与预期收益'],
    },
  });
});

test('field-level 3-way conflict diff merges disjoint edits and allows per-field selection on colliding keys', async t => {
  await mount(t);
  await click('编辑任务信息');
  await fill('作品标题', '我的新标题');
  await fill('希望对方理解或做出什么判断', '我的目标');

  // Server concurrently changes goal (collides), title (collides), and audience (disjoint).
  payload.version = 10;
  payload.deck.brief = {
    ...brief,
    title: '服务器标题',
    goal: '服务器目标',
    audience: '服务器更新的受众',
  };
  const serverBrief = structuredClone(payload.deck.brief);
  const save = write;
  write = async () => Response.json({ exit_code: 5, conflicts: [{ unit: 'brief', current: serverBrief }] }, { status: 409 });
  await click('保存任务信息');

  const diffBox = section('brief').querySelector('[aria-label="字段级三方冲突对照"]');
  assert.ok(diffBox);
  assert.ok(diffBox.querySelector('[data-conflict-field="title"]'));
  assert.ok(diffBox.querySelector('[data-conflict-field="goal"]'));
  assert.equal(diffBox.querySelector('[data-conflict-field="audience"]'), null);

  // Choose server for title, keep mine for goal; disjoint audience must remain server's value.
  await click('作品标题：采用当前', diffBox);
  await click('希望对方理解或做出什么判断：保留我的', diffBox);
  await click('按所选字段合并，核对后再保存', diffBox);

  assert.equal(state.contextDrafts.brief.base, 10);
  assert.equal(state.contextDrafts.brief.conflict, null);
  write = save;
  await click('保存任务信息');
  assert.deepEqual(requests.at(-1), {
    url: '/api/deck?base=10',
    patch: {
      brief: {
        ...serverBrief,
        title: '服务器标题',
        goal: '我的目标',
        audience: '服务器更新的受众',
      },
    },
  });
});

test('brief narrator merges role/tone independently and framing pillars conflict renders readable preview', async t => {
  await mount(t);
  payload.deck.brief = { ...brief, narrator: { role: '原角色', tone: '原语气' } };
  await poll(t);

  await click('编辑任务信息');
  await fill('讲述人角色', '作者新角色');
  payload.version = 10;
  payload.deck.brief = { ...brief, narrator: { role: '原角色', tone: '服务器新语气' } };
  const serverBrief = structuredClone(payload.deck.brief);
  const save = write;
  write = async () => Response.json({ exit_code: 5, conflicts: [{ unit: 'brief', current: serverBrief }] }, { status: 409 });
  await click('保存任务信息');

  const briefDiff = section('brief').querySelector('[aria-label="字段级三方冲突对照"]');
  // narrator.role (mine) and narrator.tone (server) do not collide!
  assert.equal(briefDiff.querySelector('[data-conflict-field="narrator.role"]'), null);
  assert.equal(briefDiff.querySelector('[data-conflict-field="narrator.tone"]'), null);
  assert.ok(briefDiff.textContent.includes('讲述人角色'));
  assert.ok(briefDiff.textContent.includes('讲述语气'));
  await click('按所选字段合并，核对后再保存', briefDiff);
  write = save;
  await click('保存任务信息');
  assert.deepEqual(requests.at(-1).patch.brief.narrator, { role: '作者新角色', tone: '服务器新语气' });

  // Framing pillars conflict must render readable pillar headings and points instead of raw JSON.
  await click('编辑业务框架');
  await fill('分组 1 标题', '作者分组');
  payload.version = 12;
  payload.deck.framing = {
    ...framing,
    pillars: [{ title: '服务器分组', points: ['服务器要点'] }, framing.pillars[1]],
  };
  const serverFraming = structuredClone(payload.deck.framing);
  write = async () => Response.json({ exit_code: 5, conflicts: [{ unit: 'framing', current: serverFraming }] }, { status: 409 });
  await click('保存业务框架');

  const framingDiff = section('framing').querySelector('[aria-label="字段级三方冲突对照"]');
  assert.ok(framingDiff.querySelector('[data-conflict-field="pillars"]'));
  assert.ok(framingDiff.textContent.includes('服务器分组'));
  assert.ok(framingDiff.textContent.includes('服务器要点'));
  assert.ok(framingDiff.textContent.includes('作者分组'));
  assert.equal(framingDiff.textContent.includes('"points"'), false);
});

test('overview Host handoff uses workspace.reviews counts and preserves ReviewPanel drafts', async t => {
  await mount(t);
  payload.deck.pages = [
    {
      id: 'p1', purpose: '结论', layout: '', notes: '', todo: [], refs: [], kind: 'judgment', argument: null,
      content: { title: '结论页', subtitle: '', body_blocks: [], labels: [], callouts: [], footnotes: [] },
      image: null, svg: null, preview: null,
    },
    {
      id: 'p2', purpose: '附录', layout: '', notes: '', todo: [], refs: [], kind: 'reference', argument: null,
      content: { title: '附录页', subtitle: '', body_blocks: [], labels: [], callouts: [], footnotes: [] },
      image: null, svg: null, preview: null,
    },
  ];
  payload.reviews = [
    { id: 101, method: 'human', version_id: 7, page_id: 'p1', text: '补齐证据出处' },
    { id: 102, method: 'self_check', version_id: 7, page_id: 'p1', text: '结论句太长' },
  ];
  await poll(t);

  // Open review count must derive from real workspace.reviews without fake page.open_reviews field.
  const badgeButton = document.querySelector('button[aria-label="查看第 01 页 2 条待处理意见"]');
  assert.ok(badgeButton);
  assert.equal(badgeButton.textContent, '2 条意见');

  // Type an unsaved draft in deck ReviewPanel, then submit deck HostHandoffCard; ReviewPanel draft must survive.
  const deckReviewBox = document.querySelector('#deck-reviews textarea');
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(deckReviewBox, '尚未提交的整稿意见');
    deckReviewBox.dispatchEvent(new window.Event('input', { bubbles: true }));
  });
  const handoff = document.querySelector('section[aria-label="整稿交给 Host"]');
  await click('交给 Host', handoff);
  await fill('给 Host 的补充说明', '请先补齐判断页证据并重绘配图');
  assert.equal(hasUnsavedInputs(state.drafts, state.contextDrafts, state.reviewDrafts, state.handoffDrafts), true);
  await click('写入意见并生成 Host 指令', handoff);

  const postReq = requests.find(req => req.method === 'POST' && req.url === '/api/reviews');
  assert.ok(postReq);
  assert.ok(postReq.body.text.includes('交给 Host'));
  assert.ok(postReq.body.text.includes('请先补齐判断页证据并重绘配图'));
  assert.equal(state.reviewDrafts.deck, '尚未提交的整稿意见');
  const card = handoff.querySelector('[aria-label="可复制的 Host 指令"]');
  assert.ok(card);
  assert.ok(card.textContent.includes('复制指令不会自动启动生成'));
  assert.ok(card.textContent.includes('#3'));
});

test('single-page Host handoff isolates page drafts across page switches, preserves across scene switches, consumes nonce and protects page ReviewPanel draft', async t => {
  await mount(t);
  payload.deck.pages = [
    {
      id: 'p1', purpose: '结论', layout: '', notes: '', todo: [], refs: [], kind: 'judgment', argument: null,
      content: { title: '第一页', subtitle: '', body_blocks: [], labels: [], callouts: [], footnotes: [] },
      image: null, svg: null, preview: null,
    },
    {
      id: 'p2', purpose: '附录', layout: '', notes: '', todo: [], refs: [], kind: 'reference', argument: null,
      content: { title: '第二页', subtitle: '', body_blocks: [], labels: [], callouts: [], footnotes: [] },
      image: null, svg: null, preview: null,
    },
  ];
  await poll(t);

  // Navigate to p1 and trigger openHostHandoff via PageArtwork "进入制作".
  await act(async () => { state.openPage('p1'); });
  await click('原图');
  await click('进入制作');
  let p1Handoff = document.querySelector('section[aria-label="本页交给 Host"]');
  assert.ok(p1Handoff.querySelector('select'));
  assert.equal(p1Handoff.querySelector('select').value, 'redraw_image');
  assert.equal(state.handoffRequest, null);

  // Collapse and re-click "进入制作" on the same page with same intent -> must re-expand cleanly!
  await click('收起交给 Host', p1Handoff);
  assert.equal(p1Handoff.querySelector('select'), null);
  await click('进入制作');
  assert.ok(p1Handoff.querySelector('select'));
  assert.equal(p1Handoff.querySelector('select').value, 'redraw_image');

  // Type an unsaved handoff note on p1 AND an unsaved ReviewPanel draft on p1.
  await fill('给 Host 的补充说明', '仅属于第一页的重绘要求');
  const p1ReviewBox = document.querySelector('#page-reviews textarea');
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(p1ReviewBox, '第一页未提交审阅草稿');
    p1ReviewBox.dispatchEvent(new window.Event('input', { bubbles: true }));
  });
  assert.equal(hasUnsavedInputs(state.drafts, state.contextDrafts, state.reviewDrafts, state.handoffDrafts), true);

  // Switch to p2: p1's handoff note MUST NOT bleed into p2.
  await act(async () => { state.openPage('p2'); });
  const p2Handoff = document.querySelector('section[aria-label="本页交给 Host"]');
  await click('交给 Host', p2Handoff);
  assert.equal(input('给 Host 的补充说明', p2Handoff).value, '');

  // Switch scene to overview and back to p1: p1's handoff note survives unmount/remount.
  await act(async () => { state.setScene('overview'); });
  assert.equal(hasUnsavedInputs(state.drafts, state.contextDrafts, state.reviewDrafts, state.handoffDrafts), true);
  await act(async () => { state.openPage('p1'); });
  p1Handoff = document.querySelector('section[aria-label="本页交给 Host"]');
  assert.equal(input('给 Host 的补充说明', p1Handoff).value, '仅属于第一页的重绘要求');

  // Submit p1 handoff: creates review on page_id 'p1' and does NOT clear p1's ReviewPanel draft!
  await click('写入意见并生成 Host 指令', p1Handoff);
  const postReq = requests.find(req => req.method === 'POST' && req.url === '/api/reviews');
  assert.ok(postReq);
  assert.equal(postReq.body.page_id, 'p1');
  assert.ok(postReq.body.text.includes('仅属于第一页的重绘要求'));
  assert.equal(state.reviewDrafts['page:p1'], '第一页未提交审阅草稿');
  assert.equal(input('给 Host 的补充说明', p1Handoff).value, '');
  assert.ok(p1Handoff.querySelector('[aria-label="可复制的 Host 指令"]').textContent.includes('p1'));
});
