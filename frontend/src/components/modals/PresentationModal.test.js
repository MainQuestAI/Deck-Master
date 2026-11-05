import { JSDOM } from 'jsdom';
import { test } from 'node:test';
import assert from 'node:assert/strict';

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true,
});
const { window } = dom;
for (const key of ['HTMLElement', 'Element', 'Node', 'SVGElement', 'DocumentFragment', 'MutationObserver', 'Event', 'KeyboardEvent', 'MouseEvent', 'NodeFilter', 'DOMParser']) {
  globalThis[key] = window[key];
}
function installGlobal(name, value) {
  Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
}
installGlobal('window', window);
installGlobal('document', window.document);
installGlobal('navigator', window.navigator);
installGlobal('localStorage', window.localStorage);
installGlobal('getComputedStyle', window.getComputedStyle.bind(window));
installGlobal('requestAnimationFrame', window.requestAnimationFrame.bind(window));
installGlobal('cancelAnimationFrame', window.cancelAnimationFrame.bind(window));
window.scrollTo = () => {};
// jsdom's focus steps re-enter React's act flush when the presentation dialog opens.
window.HTMLElement.prototype.focus = () => {};
window.HTMLElement.prototype.blur = () => {};
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const React = (await import('react')).default;
const { act } = await import('react');
const { createRoot } = await import('react-dom/client');
const { DeckMasterProvider, useDeckMaster } = await import('../../context/DeckMasterContext.jsx');
const App = (await import('../../App.jsx')).default;

const originalFetch = globalThis.fetch;
let root;
let deck;
let pending;
let api;

function page(id, title) {
  return {
    id,
    content: { title, subtitle: '', body_blocks: [], labels: [], callouts: [], footnotes: [] },
    notes: '',
    purpose: '',
    layout: '',
    todo: [],
    image: null,
    svg: null,
  };
}

function workspace(pages, version) {
  return {
    version,
    deck: {
      brief: { title: '验收作品', audience: '', task_type: '', goal: '', constraints: [], page_limit: null },
      framing: { thesis: '', pillars: [], facts: [], assumptions: [], questions: [] },
      pages,
    },
    artifact_status: { missing_pages: [], stale_pages: [], stale_images: [] },
    runs: [],
    history: [],
    reviews: [],
    open_reviews_total: 0,
  };
}

function PresentationProbe() {
  api = useDeckMaster();
  return React.createElement('output', { 'data-presentation': api.presentation ?? '' });
}

function presented() {
  return document.querySelector('output[data-presentation]').getAttribute('data-presentation');
}

function stage() {
  return document.querySelector('[role="dialog"][aria-label="整稿放映"]');
}

function settle(work) {
  act(() => { work?.(); });
}

async function flushFetches() {
  await act(async () => {
    pending.splice(0).forEach(run => run());
    await new Promise(resolve => setImmediate(resolve));
  });
}

async function click(text) {
  const button = [...document.querySelectorAll('button')].find(item => item.textContent.includes(text) && !item.disabled);
  if (!button) throw new Error(`missing enabled button ${text}`);
  settle(() => button.click());
}

function pressBackground(key) {
  settle(() => {
    document.body.dispatchEvent(new window.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
  });
}

async function refreshDeck() {
  await act(async () => {
    const done = api.refresh();
    pending.splice(0).forEach(run => run());
    await done;
  });
}

async function boot(pages) {
  deck = workspace(pages, 1);
  pending = [];
  globalThis.fetch = (url) => {
    if (url !== '/api/deck') return Promise.reject(new Error(`unexpected ${url}`));
    const snapshot = deck;
    return new Promise(resolve => pending.push(() => resolve(Response.json(snapshot))));
  };
  root?.unmount();
  root = createRoot(document.getElementById('root'));
  settle(() => {
    root.render(React.createElement(React.StrictMode, null,
      React.createElement(DeckMasterProvider, null,
        React.createElement(App),
        React.createElement(PresentationProbe))));
  });
  await flushFetches();
}

async function presentPage(title) {
  await click('整稿画廊');
  await click('全屏放映预览');
  assert.match(stage().textContent, /第一页/);
  if (title === '第二页') {
    await pressBackground('ArrowRight');
    assert.match(stage().textContent, /第二页/);
    assert.equal(presented(), 'p2');
  }
}

test.afterEach(() => {
  if (root) act(() => root.unmount());
  root = null;
  globalThis.fetch = originalFetch;
});

test('deleting the presented page ends playback so a background arrow cannot reopen it', async () => {
  await boot([page('p1', '第一页'), page('p2', '第二页')]);
  await presentPage('第二页');

  deck = workspace([page('p1', '第一页')], 2);
  await refreshDeck();

  assert.equal(Boolean(stage()), false);
  pressBackground('ArrowRight');
  assert.equal(Boolean(stage()), false, `background ArrowRight reopened presentation as ${presented()}`);
  assert.equal(presented(), '');
});

test('deleting a different page leaves the current presentation in place', async () => {
  await boot([page('p1', '第一页'), page('p2', '第二页')]);
  await presentPage('第二页');

  deck = workspace([page('p2', '第二页')], 2);
  await refreshDeck();

  assert.equal(Boolean(stage()), true);
  assert.match(stage().textContent, /第二页/);
  assert.equal(presented(), 'p2');
  pressBackground('ArrowRight');
  assert.equal(presented(), 'p2');
  assert.match(stage().textContent, /第二页/);
});
