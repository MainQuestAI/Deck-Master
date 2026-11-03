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

test('image comparison keeps the bitmap files on both sides', async () => {
  await openComparison(workspace({
    kind: 'image',
    currentFile: 'current-image.png',
    candidateFile: 'candidate-image.png',
  }));
  assert.deepEqual(imageSources(), ['/api/files/current-image', '/api/files/candidate-image']);
});
