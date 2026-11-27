import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1:4173/',
  pretendToBeVisual: true,
});
const { window } = dom;
for (const [key, value] of Object.entries({
  window,
  document: window.document,
  navigator: window.navigator,
  HTMLElement: window.HTMLElement,
  Element: window.Element,
  Node: window.Node,
  DocumentFragment: window.DocumentFragment,
  MutationObserver: window.MutationObserver,
  localStorage: window.localStorage,
  Event: window.Event,
  MouseEvent: window.MouseEvent,
  getComputedStyle: window.getComputedStyle.bind(window),
  IS_REACT_ACT_ENVIRONMENT: true,
})) {
  Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });
}

const { createElement } = await import('react');
const { act } = await import('react');
const { createRoot } = await import('react-dom/client');
const { default: App } = await import('./App.jsx');
const { DeckMasterProvider } = await import('./context/DeckMasterContext.jsx');

const style = {
  canvas: { width_px: 1280, height_px: 720, slide_width_in: 13.333, slide_height_in: 7.5 },
  palette: [],
  fonts: [],
  assets: [],
};

function content(text, title = '增长') {
  return {
    title,
    subtitle: '',
    body_blocks: [{ type: 'paragraph', id: 'a1', text }],
    labels: [],
    footnotes: [],
    callouts: [],
  };
}

function workspace({
  version = 8,
  kind = 'svg',
  body = '预期增长 10%',
  notes = '讲稿',
  otherNotes = '另一页讲稿',
  basisChanged = false,
  currentBasis = 'basis-v8',
  preview = 'current-preview.png',
  resultPreview = 'candidate-preview.png',
  currentFile = kind === 'svg' ? 'current.svg' : 'current-image.png',
  candidateFile = kind === 'svg' ? 'candidate.svg' : 'candidate-image.png',
} = {}) {
  const page = {
    id: 'p1',
    purpose: '说明增长',
    layout: '单栏',
    content: content(body),
    notes,
    todo: [],
    refs: [],
    image: kind === 'image' ? { file: currentFile, basis: 'image-basis' } : { file: 'original.png', basis: 'image-basis' },
    svg: kind === 'svg' ? { file: currentFile, basis: 'svg-basis' } : null,
    preview: kind === 'svg' ? preview : 'built-preview.png',
    open_reviews: 0,
  };
  const other = {
    ...page,
    id: 'p2',
    content: content('其他页面', '其他'),
    notes: otherNotes,
    image: null,
    svg: null,
    preview: null,
  };
  return {
    version,
    deck: {
      brief: { title: '合成方案', audience: '', task_type: '', goal: '', constraints: [] },
      materials: [],
      framing: { thesis: '', pillars: [], facts: [], assumptions: [], questions: [] },
      style,
      pages: [page, other],
    },
    artifact_status: { missing_pages: [], stale_pages: [], stale_images: [] },
    runs: [{
      id: 4,
      kind,
      status: 'open',
      max_calls: kind === 'image' ? 2 : null,
      calls_used: 0,
      pages: [{
        page_id: 'p1',
        status: 'unadopted',
        reason: '结果仅保存，请比较后手动采用',
        basis_changed: basisChanged,
        current_basis: currentBasis,
        result_file: candidateFile,
        result_preview: kind === 'svg' ? resultPreview : null,
        result_url: `/api/files/${candidateFile.split('.')[0]}`,
        current_image_url: '/api/files/original',
      }],
    }],
    history: [{ id: version, created_at: '2026-11-04T00:00:00.000Z', summary: '保存正文' }],
    reviews: [],
    open_reviews_total: 0,
  };
}

let root;
let payload;
const calls = [];
const pending = [];

function installFetch() {
  calls.length = 0;
  pending.length = 0;
  globalThis.fetch = (url, options = {}) => {
    const record = { url: String(url), method: options.method || 'GET', body: options.body };
    calls.push(record);
    if (record.url.includes('/adopt/')) return Promise.resolve(Response.json({ ok: true }));
    return new Promise(resolve => {
      pending.push(() => resolve(Response.json(structuredClone(payload))));
    });
  };
}

async function settle() {
  assert.ok(pending.length > 0, 'expected a deck read');
  const finish = pending.shift();
  await act(async () => { finish(); });
}

function click(target) {
  const node = target.startsWith('#')
    ? document.querySelector(target)
    : [...document.querySelectorAll('button')].find(button => button.textContent.includes(target));
  assert.ok(node, `missing control: ${target}`);
  node.click();
  return node;
}

async function openComparison(initial) {
  payload = initial;
  installFetch();
  const mount = document.getElementById('root');
  root = createRoot(mount);
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });
  await settle();
  await act(async () => { click('#nav-delivery'); });
  await act(async () => { click('比对与采用'); });
}

function imageSources() {
  return [...document.querySelectorAll('.compare-grid-board img')].map(image => image.getAttribute('src'));
}

afterEach(async () => {
  if (root) {
    await act(async () => { root.unmount(); });
    root = null;
  }
  document.body.innerHTML = '<div id="root"></div>';
});

test('svg comparison shows the compiled previews and adopts the svg file', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  await openComparison(workspace());
  assert.deepEqual(imageSources(), ['/api/files/current-preview', '/api/files/candidate-preview']);
  for (const image of document.querySelectorAll('.compare-grid-board img')) {
    assert.match(image.alt, /预览/);
  }
  payload.deck.pages[0].preview = 'later-current.png';
  payload.runs[0].pages[0].result_preview = 'later-candidate.png';
  payload.version = 9;
  await act(async () => { t.mock.timers.tick(1500); });
  await settle();
  assert.deepEqual(imageSources(), ['/api/files/current-preview', '/api/files/candidate-preview']);
  const adopt = [...document.querySelectorAll('button')].find(button => button.textContent.includes('采用此候选'));
  assert.ok(adopt);
  assert.equal(adopt.disabled, false);
  await act(async () => { adopt.click(); });
  const request = calls.find(call => call.url.includes('/adopt/'));
  assert.equal(request.url, '/api/runs/4/adopt/p1');
  assert.equal(request.method, 'POST');
  assert.deepEqual(JSON.parse(request.body), { expected_file: 'candidate.svg' });
});

function messageText() {
  return [...document.querySelectorAll('.s4-message')].map(node => node.textContent).join('\n');
}

async function replaceWorkspace(t, next) {
  payload = next;
  await act(async () => { t.mock.timers.tick(1500); });
  await settle();
}

test('svg comparison asks to reopen when that page basis changes and still allows adoption', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  await openComparison(workspace({ body: '预期增长 10%', currentBasis: 'basis-10', basisChanged: false }));
  const sources = imageSources();
  assert.equal(messageText().includes('请重新打开'), false);
  await replaceWorkspace(t, workspace({
    version: 9, body: '预期增长 10%', otherNotes: '改了另一页讲稿', currentBasis: 'basis-10', basisChanged: false,
  }));
  assert.equal(messageText().includes('请重新打开'), false);
  assert.deepEqual(imageSources(), sources);
  await replaceWorkspace(t, workspace({
    version: 10, body: '预期增长 10%', notes: '只改本页讲稿', currentBasis: 'basis-10', basisChanged: false,
  }));
  assert.equal(messageText().includes('请重新打开'), false);
  assert.deepEqual(imageSources(), sources);
  await replaceWorkspace(t, workspace({
    version: 11, body: '预期增长 5%', notes: '只改本页讲稿', currentBasis: 'basis-5', basisChanged: true,
  }));
  assert.match(messageText(), /当前作品已变化/);
  assert.match(messageText(), /请重新打开/);
  assert.deepEqual(imageSources(), sources);
  const adopt = [...document.querySelectorAll('button')].find(button => button.textContent.includes('采用此候选'));
  assert.equal(adopt.disabled, false);
  await act(async () => { adopt.click(); });
  const request = calls.find(call => call.url.includes('/adopt/'));
  assert.deepEqual(JSON.parse(request.body), { expected_file: 'candidate.svg' });
});

test('a further basis change still asks to reopen when the flag was already true', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  await openComparison(workspace({ body: '预期增长 10%', currentBasis: 'basis-stale', basisChanged: true }));
  assert.equal(messageText().includes('请重新打开'), false);
  await replaceWorkspace(t, workspace({
    version: 9, body: '预期增长 5%', currentBasis: 'basis-stale-2', basisChanged: true,
  }));
  assert.match(messageText(), /请重新打开/);
  assert.deepEqual(imageSources(), ['/api/files/current-preview', '/api/files/candidate-preview']);
  const adopt = [...document.querySelectorAll('button')].find(button => button.textContent.includes('采用此候选'));
  assert.equal(adopt.disabled, false);
});

test('image comparison keeps the bitmap files on both sides', async () => {
  await openComparison(workspace({
    kind: 'image',
    currentFile: 'current-image.png',
    candidateFile: 'candidate-image.png',
  }));
  assert.deepEqual(imageSources(), ['/api/files/current-image', '/api/files/candidate-image']);
});


test('native runs appear in overview and delivery, can be stopped, compared side by side, and adopted with note and warnings', async () => {
  const { comparisonSnapshot } = await import('./api.js');
  payload = workspace({
    kind: 'native',
    candidateFile: 'candidate.native.json',
    resultPreview: 'native-render.png',
  });
  payload.artifact_status.build_mode = 'native';
  payload.runs[0].pages[0].result_preview = 'native-render.png';
  payload.deck.pages[0].native = { file: 'current.native.json', basis: 'svg-v2:basis' };

  const snap = comparisonSnapshot(payload.runs[0], payload.runs[0].pages[0], payload.deck.pages[0], 8);
  assert.ok(snap);
  assert.equal(snap.currentView, 'original.png');
  assert.equal(snap.candidateView, 'native-render.png');
  assert.equal(snap.candidateFile, 'candidate.native.json');

  calls.length = 0;
  pending.length = 0;
  globalThis.fetch = (url, options = {}) => {
    const record = { url: String(url), method: options.method || 'GET', body: options.body };
    calls.push(record);
    if (record.url.includes('/cancel')) {
      payload.runs[0].status = 'cancelled';
      return Promise.resolve(Response.json({ runs: structuredClone(payload.runs) }));
    }
    if (record.url.includes('/adopt/')) {
      payload.deck.pages[0].native = { file: 'adopted-with-note.native.json', basis: 'svg-v2:basis' };
      payload.runs[0].pages[0].result_file = 'adopted-with-note.native.json';
      payload.runs[0].pages[0].status = 'done';
      return Promise.resolve(Response.json({
        runs: structuredClone(payload.runs),
        warnings: [{
          level: 'warning',
          code: 'note_unspecific',
          page_id: 'p1',
          message: '本页对照结论去掉空白和标点后只剩确认用语，没有写出本页对照了什么。此提示不阻止采用。',
        }],
      }));
    }
    return new Promise(resolve => {
      pending.push(() => resolve(Response.json(structuredClone(payload))));
    });
  };

  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });
  await settle();

  const metric = [...document.querySelectorAll('.metric-item')].find(node => node.textContent.includes('进行中任务'));
  assert.equal(metric.querySelector('strong').textContent, '1');

  await act(async () => { click('#nav-delivery'); });
  assert.ok(document.body.textContent.includes('原生还原'));
  assert.ok(document.body.textContent.includes('缺原生还原'));
  const previewLink = [...document.querySelectorAll('a')].find(link => link.textContent === '查看渲染预览');
  assert.ok(previewLink);
  assert.equal(previewLink.getAttribute('href'), '/api/files/native-render');

  // Open native run can be stopped from delivery view.
  await act(async () => { click('停止任务'); });
  await settle();
  assert.ok(calls.some(call => call.url === '/api/runs/4/cancel' && call.method === 'POST'));

  // Open side-by-side comparison for native candidate.
  await act(async () => { click('比对与采用'); });
  assert.deepEqual(imageSources(), ['/api/files/original', '/api/files/native-render']);

  const adopt = () => [...document.querySelectorAll('button')].find(button => button.textContent.includes('采用此候选'));
  assert.equal(adopt().disabled, true);

  const noteInput = document.querySelector('textarea');
  assert.ok(noteInput);
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(noteInput, 'ok');
    noteInput.dispatchEvent(new window.Event('input', { bubbles: true }));
  });
  assert.equal(adopt().disabled, false);

  await act(async () => { adopt().click(); });
  await settle();

  const adoptCall = calls.find(call => call.url.includes('/adopt/'));
  assert.equal(adoptCall.url, '/api/runs/4/adopt/p1');
  assert.deepEqual(JSON.parse(adoptCall.body), { expected_file: 'candidate.native.json', note: 'ok' });
  assert.ok(document.body.textContent.includes('当前作品已采用此候选'));
  assert.ok(document.body.textContent.includes('本页对照结论去掉空白和标点后只剩确认用语'));
  assert.equal(document.body.textContent.includes('--note'), false);
});

test('switching comparison candidate mid-adopt does not leak adoptedFile or warnings into the new comparison', async () => {
  payload = workspace({
    kind: 'native',
    candidateFile: 'candidate-a.native.json',
    resultPreview: 'render-a.png',
  });
  payload.artifact_status.build_mode = 'native';
  payload.artifact_status.page_modes = { p1: 'native', p2: 'native' };
  payload.deck.pages[0].native = { file: 'current-a.native.json', basis: 'basis-a' };
  payload.deck.pages[1].image = { file: 'original-b.png', basis: 'img-b' };
  payload.deck.pages[1].native = { file: 'current-b.native.json', basis: 'basis-b' };
  payload.runs[0].pages = [
    {
      page_id: 'p1', status: 'unadopted', reason: '待核对', basis_changed: false,
      current_basis: 'basis-a', result_file: 'candidate-a.native.json', result_preview: 'render-a.png',
    },
    {
      page_id: 'p2', status: 'unadopted', reason: '待核对', basis_changed: false,
      current_basis: 'basis-b', result_file: 'candidate-b.native.json', result_preview: 'render-b.png',
    },
  ];

  let finishAdopt;
  calls.length = 0;
  pending.length = 0;
  globalThis.fetch = (url, options = {}) => {
    const record = { url: String(url), method: options.method || 'GET', body: options.body };
    calls.push(record);
    if (record.url.includes('/adopt/')) {
      return new Promise(resolve => {
        finishAdopt = () => resolve(Response.json({
          runs: structuredClone(payload.runs),
          warnings: [{
            level: 'warning',
            code: 'note_unspecific',
            page_id: 'p1',
            message: '本页对照结论去掉空白和标点后只剩确认用语，没有写出本页对照了什么。此提示不阻止采用。',
          }],
        }));
      });
    }
    return new Promise(resolve => {
      pending.push(() => resolve(Response.json(structuredClone(payload))));
    });
  };

  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });
  await settle();
  await act(async () => { click('#nav-delivery'); });
  // Open p1 candidate and kick off adopt without resolving yet.
  const compareButtons = [...document.querySelectorAll('button')].filter(btn => btn.textContent.includes('比对与采用'));
  await act(async () => { compareButtons[0].click(); });
  const noteInput = document.querySelector('textarea');
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(noteInput, 'ok');
    noteInput.dispatchEvent(new window.Event('input', { bubbles: true }));
  });
  await act(async () => { click('采用此候选'); });
  assert.equal(typeof finishAdopt, 'function');

  // Switch back to delivery and open p2 comparison while p1 adopt is still in flight.
  await act(async () => { click('返回制作任务'); });
  const compareButtonsAfter = [...document.querySelectorAll('button')].filter(btn => btn.textContent.includes('比对与采用'));
  await act(async () => { compareButtonsAfter[1].click(); });
  assert.deepEqual(imageSources(), ['/api/files/original-b', '/api/files/render-b']);

  // Now resolve p1 adopt: p2 comparison must NOT show p1's warnings or adopted status!
  await act(async () => { finishAdopt(); });
  if (pending.length) await settle();
  assert.equal(document.body.textContent.includes('本页对照结论去掉空白和标点后'), false);
  assert.equal(document.body.textContent.includes('当前作品已采用此候选'), false);
});

test('page reader and page comparison align native preview labels across pure-native and mixed pages via page_modes', async () => {
  payload = workspace({ kind: 'native', candidateFile: 'candidate.native.json', resultPreview: 'render.png' });
  payload.artifact_status = {
    build_mode: 'mixed',
    page_modes: { p1: 'native', p2: 'svg' },
    missing_pages: [],
    stale_pages: [],
    stale_images: [],
  };
  // Mixed page p1 has BOTH native and legacy svg; page_modes['p1'] === 'native' must win.
  payload.deck.pages[0].native = { file: 'p1.native.json', basis: 'b1' };
  payload.deck.pages[0].svg = { file: 'p1.svg', basis: 'old-svg' };
  payload.deck.pages[0].preview = 'p1-native-preview.png';
  payload.deck.pages[1].svg = { file: 'p2.svg', basis: 'b2' };
  payload.deck.pages[1].preview = 'p2-svg-preview.png';
  payload.deck.pages[1].image = { file: 'p2-orig.png', basis: 'img2' };

  installFetch();
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });
  await settle();

  // Open p1 from overview table.
  await act(async () => { click('增长'); });
  const tabs = [...document.querySelectorAll('.reader-layers button')].map(btn => btn.textContent);
  assert.deepEqual(tabs, ['正文', '原图', '原生渲染预览', '原图／原生渲染对照']);

  await act(async () => { click('原图／原生渲染对照'); });
  const cmp = document.querySelector('section[aria-label="本页原图与原生渲染预览对照"]');
  assert.ok(cmp);
  assert.ok(cmp.textContent.includes('已采用的原生渲染预览'));
  assert.equal(cmp.textContent.includes('已采用的编译预览'), false);
});
