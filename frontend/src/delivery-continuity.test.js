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
  sessionStorage: window.sessionStorage,
  Event: window.Event,
  MouseEvent: window.MouseEvent,
  getComputedStyle: window.getComputedStyle.bind(window),
  IS_REACT_ACT_ENVIRONMENT: true,
})) {
  Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });
}

const { createElement, act } = await import('react');
const { createRoot } = await import('react-dom/client');
const { safeExportFilename } = await import('./api.js');
const { default: App } = await import('./App.jsx');
const { DeckMasterProvider } = await import('./context/DeckMasterContext.jsx');

function sampleWorkspace(workspaceId = 'ws-demo-0001') {
  return {
    workspace_id: workspaceId,
    version: 5,
    deck: {
      brief: { title: '季度汇报: Q4/计划', audience: '管理层', task_type: '汇报', goal: '确认预算', decision: '批准试点', concerns: ['周期'], narrator: { role: '负责人', tone: '直接' }, constraints: [], page_limit: 10 },
      materials: [],
      framing: { thesis: '聚焦试点', storyline: ['背景', '行动'], pillars: [], facts: [], assumptions: [], questions: [] },
      style: { canvas: { width_px: 1280, height_px: 720, slide_width_in: 13.333, slide_height_in: 7.5 }, palette: [], fonts: [], assets: [] },
      pages: [
        {
          id: 'p1', purpose: '核心结论', layout: '双栏', kind: 'judgment', argument: null,
          content: { title: '第一页结论', subtitle: '', body_blocks: [{ type: 'paragraph', id: 'a1', text: '正文' }], labels: [], footnotes: [], callouts: [] },
          notes: '讲稿一', todo: [], refs: [], image: { file: 'img1.png', basis: 'b1' }, svg: null, native: null, preview: null, open_reviews: 0,
        },
        {
          id: 'p2', purpose: '行动计划', layout: '时间线', kind: 'explanation', argument: null,
          content: { title: '第二页行动', subtitle: '', body_blocks: [{ type: 'paragraph', id: 'a2', text: '行动' }], labels: [], footnotes: [], callouts: [] },
          notes: '讲稿二', todo: [], refs: [], image: null, svg: null, native: null, preview: null, open_reviews: 0,
        },
      ],
    },
    artifact_status: { build_mode: 'svg', missing_pages: [], stale_pages: [], stale_images: ['p1'] },
    default_build: { id: 12, version_id: 4, input_changed: true, warning: '有新改动', build_missing_pages: [] },
    content_review: { status: 'stale', methods: ['self_check'], version_id: 4, unreviewed_pages: ['p2'] },
    runs: [],
    reviews: [
      { id: 1, method: 'self_check', version_id: 4, page_id: null, text: '自检条目' },
      { id: 2, method: 'other_model', version_id: 4, page_id: null, text: '跨模型检查条目' },
    ],
    history: [{ id: 5, created_at: '2026-11-26T00:00:00Z', summary: '保存正文' }],
  };
}

const sampleBuildDetail = {
  id: 12,
  version_id: 4,
  created_at: '2026-11-26T00:00:00Z',
  pptx_url: '/api/files/aaaa',
  current_version: 5,
  input_changed: true,
  readback_available: true,
  readback_matches_current: false,
  pages: [{ page_id: 'p1', title: '第一页结论', source_order: 1, pptx_slide: 1 }],
  findings: {
    status: 'fail',
    findings: [{ code: 'missing_visible_atom', page_id: 'p1', text: '缺少正文' }],
  },
  content_review: { status: 'reviewed', methods: ['other_model'], version_id: 4, unreviewed_pages: [] },
  current_content_review: { status: 'stale', methods: ['self_check'], version_id: 4, unreviewed_pages: ['p2'] },
  warnings: [
    // Test real backend stale_image payload shape even when message is omitted (legacy builds)
    // as well as current backend shared_layout message.
    { level: 'warning', code: 'stale_image', page_id: 'p1' },
    { level: 'warning', code: 'shared_layout', pages: ['p1', 'p2'], message: '本组第 1、2 页复用同一题头，请核对节奏' },
  ],
};

let root;
const originalSessionStorage = globalThis.sessionStorage;

afterEach(async () => {
  if (root) {
    await act(async () => { root.unmount(); });
    root = null;
  }
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, writable: true, value: originalSessionStorage });
  try { originalSessionStorage.clear(); } catch { /* ignore */ }
  document.body.innerHTML = '<div id="root"></div>';
});

test('safeExportFilename sanitizes unsafe title characters and falls back cleanly', () => {
  assert.equal(safeExportFilename('季度汇报: Q4/计划*', 'pptx'), '季度汇报 Q4 计划.pptx');
  assert.equal(safeExportFilename('   ...   ', 'md'), 'deck.md');
  assert.equal(safeExportFilename('', 'pptx'), 'deck.pptx');
});

test('delivery view shows content_review, current_content_review, warnings, and jumps directly to unreviewed pages and findings', async () => {
  const ws = sampleWorkspace();
  globalThis.fetch = async (url) => {
    if (String(url).startsWith('/api/builds/')) return Response.json(structuredClone(sampleBuildDetail));
    return Response.json(structuredClone(ws));
  };
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });

  // Unified review method labels & sidebar aria-current.
  assert.equal(document.querySelector('#nav-overview').getAttribute('aria-current'), 'page');
  assert.ok(document.body.textContent.includes('自检'));
  assert.ok(document.body.textContent.includes('另一模型检查'));
  assert.equal(document.body.textContent.includes('Host 自检'), false);

  // Gallery aria-pressed check.
  await act(async () => { document.querySelector('#nav-gallery').click(); });
  assert.equal(document.querySelector('#nav-gallery').getAttribute('aria-current'), 'page');
  const pressed = [...document.querySelectorAll('.segmented-control button')].find(btn => btn.getAttribute('aria-pressed') === 'true');
  assert.ok(pressed);

  // Navigate to DeliveryView and verify live vs build-snapshot content reviews + warnings + jumps.
  await act(async () => { document.querySelector('#nav-delivery').click(); });
  const liveReviewBox = document.querySelector('[aria-label="当前作品内容审阅"]');
  assert.ok(liveReviewBox);
  assert.ok(liveReviewBox.textContent.includes('需复审'));
  const buildReviewBox = document.querySelector('[aria-label="默认构建来源版本内容审阅"]');
  assert.ok(buildReviewBox);
  assert.ok(buildReviewBox.textContent.includes('已审阅'));
  assert.ok(buildReviewBox.textContent.includes('另一模型检查'));

  // stale_image warning without message must map to actionable Chinese, never leaking raw "stale_image".
  const warningBox = document.querySelector('[aria-label="交付警告"]');
  assert.ok(warningBox.textContent.includes('第 01 页原图制作依据已变，请核对或重绘原图'));
  assert.equal(warningBox.textContent.includes('stale_image'), false);
  assert.ok(warningBox.textContent.includes('复用同一题头'));

  // Click unreviewed page button -> jumps directly to PageReaderView for p2.
  const jumpP2 = [...liveReviewBox.querySelectorAll('button')].find(btn => btn.textContent.includes('第 02 页'));
  assert.ok(jumpP2);
  await act(async () => { jumpP2.click(); });
  assert.ok(document.querySelector('h1').textContent.includes('第二页行动'));

  // Go back to DeliveryView and click readback finding -> jumps to p1.
  await act(async () => { document.querySelector('#nav-delivery').click(); });
  const findingBtn = [...document.querySelectorAll('details button')].find(btn => btn.textContent.includes('构建时第 1 页'));
  assert.ok(findingBtn);
  await act(async () => { findingBtn.click(); });
  assert.ok(document.querySelector('h1').textContent.includes('第一页结论'));
});

test('delivery view invalidates stale downloadStatus after content_review updates and never mislabels live review as build review', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const ws = sampleWorkspace();
  ws.default_build = null;
  ws.content_review = { status: 'unreviewed', methods: [], version_id: 5, unreviewed_pages: ['p1', 'p2'] };
  globalThis.fetch = async (url, options = {}) => {
    if (options.method === 'POST' && url === '/api/build') {
      return Response.json({
        id: 20,
        version_id: 5,
        url: '/api/files/bbbb',
        missing_pages: [],
        stale_pages: [],
        stale_images: [],
        warnings: [],
        content_review: { status: 'unreviewed', methods: [], version_id: 5, unreviewed_pages: ['p1', 'p2'] },
      });
    }
    return Response.json(structuredClone(ws));
  };
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });
  await act(async () => { document.querySelector('#nav-delivery').click(); });

  // Before any build, only live review is shown — never labeled as build source review.
  assert.ok(document.querySelector('[aria-label="当前作品内容审阅"]').textContent.includes('未审阅'));
  assert.equal(document.querySelector('[aria-label="默认构建来源版本内容审阅"]'), null);
  assert.equal(document.querySelector('[aria-label="最近构建来源版本内容审阅"]'), null);

  // Trigger build -> downloadSnapshot appears with recent build review.
  const buildBtn = [...document.querySelectorAll('button')].find(btn => btn.textContent === '构建 PPTX');
  await act(async () => { buildBtn.click(); });
  assert.ok(document.querySelector('[aria-label="最近构建来源版本内容审阅"]').textContent.includes('未审阅'));

  // Now Host records a content review -> next poll updates workspace.content_review
  // and must invalidate stale downloadStatus so live review reflects "已审阅" cleanly.
  ws.content_review = { status: 'reviewed', methods: ['self_check'], version_id: 5, unreviewed_pages: [] };
  await act(async () => { t.mock.timers.tick(1500); });
  assert.ok(document.querySelector('[aria-label="当前作品内容审阅"]').textContent.includes('已审阅'));
  assert.equal(document.querySelector('[aria-label="最近构建来源版本内容审阅"]'), null);
});

test('draft continuity survives a second reload before Restore/Dismiss and isolates workspaces by workspace_id across title renames', async () => {
  const ws = sampleWorkspace('ws-alpha-1111');
  globalThis.fetch = async (url) => {
    if (String(url).startsWith('/api/builds/')) return Response.json(structuredClone(sampleBuildDetail));
    return Response.json(structuredClone(ws));
  };
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });

  // Edit brief title without saving -> mirrored into sessionStorage under workspace_id.
  const editBtn = [...document.querySelectorAll('button')].find(btn => btn.textContent === '编辑任务信息');
  await act(async () => { editBtn.click(); });
  const titleLabel = [...document.querySelectorAll('label')].find(node => node.querySelector('span')?.textContent === '作品标题');
  const titleInput = titleLabel.querySelector('input');
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(titleInput, '尚未保存的新标题');
    titleInput.dispatchEvent(new window.Event('input', { bubbles: true }));
  });

  // First reload: recovery banner shows, user does NOT click Restore or Dismiss yet!
  // Also simulate server brief.title rename on the same workspace_id.
  ws.deck.brief.title = '服务端重命名后的标题';
  await act(async () => { root.unmount(); });
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });
  assert.ok(document.querySelector('[aria-label="未保存草稿恢复提示"]'));

  // Second reload BEFORE clicking Restore/Dismiss: draft must STILL be intact (regression for same-cycle remove race)!
  await act(async () => { root.unmount(); });
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });
  const banner = document.querySelector('[aria-label="未保存草稿恢复提示"]');
  assert.ok(banner);
  assert.ok(banner.textContent.includes('版本 5'));

  // A different project served on the same port (different workspace_id) must NOT see ws-alpha's draft!
  await act(async () => { root.unmount(); });
  const otherWs = sampleWorkspace('ws-beta-2222');
  globalThis.fetch = async (url) => {
    if (String(url).startsWith('/api/builds/')) return Response.json(structuredClone(sampleBuildDetail));
    return Response.json(structuredClone(otherWs));
  };
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });
  assert.equal(document.querySelector('[aria-label="未保存草稿恢复提示"]'), null);

  // Switch back to ws-alpha: draft is STILL available and restores cleanly!
  await act(async () => { root.unmount(); });
  globalThis.fetch = async (url) => {
    if (String(url).startsWith('/api/builds/')) return Response.json(structuredClone(sampleBuildDetail));
    return Response.json(structuredClone(ws));
  };
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });
  const alphaBanner = document.querySelector('[aria-label="未保存草稿恢复提示"]');
  assert.ok(alphaBanner);
  const restoreBtn = [...alphaBanner.querySelectorAll('button')].find(btn => btn.textContent === '恢复草稿');
  await act(async () => { restoreBtn.click(); });

  const reopenBtn = [...document.querySelectorAll('button')].find(btn => btn.textContent === '编辑任务信息');
  await act(async () => { reopenBtn.click(); });
  const restoredLabel = [...document.querySelectorAll('label')].find(node => node.querySelector('span')?.textContent === '作品标题');
  assert.equal(restoredLabel.querySelector('input').value, '尚未保存的新标题');
});

test('disabled sessionStorage degrades silently without interrupting editing or navigation', async () => {
  const brokenStorage = {
    getItem() { throw new Error('SecurityError'); },
    setItem() { throw new Error('SecurityError'); },
    removeItem() { throw new Error('SecurityError'); },
  };
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, writable: true, value: brokenStorage });

  const ws = sampleWorkspace();
  globalThis.fetch = async (url) => {
    if (String(url).startsWith('/api/builds/')) return Response.json(structuredClone(sampleBuildDetail));
    return Response.json(structuredClone(ws));
  };
  root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(createElement(DeckMasterProvider, null, createElement(App))); });

  const editBtn = [...document.querySelectorAll('button')].find(btn => btn.textContent === '编辑任务信息');
  await act(async () => { editBtn.click(); });
  const titleLabel = [...document.querySelectorAll('label')].find(node => node.querySelector('span')?.textContent === '作品标题');
  const titleInput = titleLabel.querySelector('input');
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(titleInput, '无痕模式输入');
    titleInput.dispatchEvent(new window.Event('input', { bubbles: true }));
  });
  assert.equal(titleInput.value, '无痕模式输入');
  assert.equal(document.querySelector('[aria-label="未保存草稿恢复提示"]'), null);
});
