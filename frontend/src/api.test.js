import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, getDeck, putDeck, cancelRun, buildDeck, restoreVersion, exportDeck, fileUrl, mergeWorkspace, createDraft, draftPatch } from './api.js';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test('save sends the bare patch and retains submitted input on conflict', async () => {
  const page = { id: 'p1', content: { title: '原稿', body_blocks: [] }, notes: '讲稿' };
  const draft = createDraft(page, 2);
  draft.page.content.title = '作者输入';
  const patch = draftPatch(draft);
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/deck?base=2');
    assert.equal(options.method, 'PUT');
    assert.deepEqual(JSON.parse(options.body), patch);
    return Response.json({ exit_code: 5, submitted: patch, conflicts: [{ unit: 'page:p1', current: page }] }, { status: 409 });
  };
  await assert.rejects(putDeck(2, patch), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 409);
    assert.deepEqual(error.data.submitted, patch);
    return true;
  });
  assert.equal(draft.page.content.title, '作者输入');
  assert.equal(page.content.title, '原稿');
  assert.equal(patch.pages[0].notes, undefined);
});

test('same-version polling refreshes runs; older polls cannot undo saves', () => {
  const current = { version: 3, runs: [{ status: 'open' }] };
  const incoming = { version: 3, runs: [{ status: 'cancelled' }] };
  assert.equal(mergeWorkspace(current, incoming), incoming);
  assert.equal(mergeWorkspace(current, { version: 2 }), current);
});

test('cancel posts to the selected run endpoint', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/runs/7/cancel');
    assert.equal(options.method, 'POST');
    return Response.json({ runs: [{ id: 7, status: 'cancelled' }] });
  };
  assert.equal((await cancelRun(7)).runs[0].status, 'cancelled');
});

test('downloads retain status warnings and content', async () => {
  const status = { missing_pages: ['p2'], stale_pages: ['p1'], input_changed: true };
  globalThis.fetch = async () => new Response('download', { headers: { 'X-Deck-Status': JSON.stringify(status) } });
  const result = await exportDeck('pptx');
  assert.deepEqual(result.status, status);
  assert.equal(await result.blob.text(), 'download');
  assert.equal(result.filename, 'deck.pptx');
});

test('input, missing-tool and network errors remain actionable', async () => {
  for (const status of [400, 404, 500, 503]) {
    globalThis.fetch = async () => Response.json({ error: '工具失败，请安装工具后重试' }, { status });
    await assert.rejects(getDeck(), (error) => error.status === status && error.message.includes('重试'));
  }
  globalThis.fetch = async () => { throw new TypeError('network'); };
  await assert.rejects(getDeck(), /deck serve/);
});

test('file URLs take the reference before its first dot without render-time validation', () => {
  assert.equal(fileUrl(`${'a'.repeat(64)}.jpg`), `/api/files/${'a'.repeat(64)}`);
  assert.equal(fileUrl(null), null);
  assert.equal(fileUrl('invalid.jpg'), '/api/files/invalid');
});

test('requests time out after 15 seconds', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let signal;
  globalThis.fetch = async (_url, options) => {
    signal = options.signal;
    return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(signal.reason), { once: true }));
  };
  const rejected = assert.rejects(getDeck(), /超时.*重试/);
  t.mock.timers.tick(14999);
  assert.equal(signal.aborted, false);
  t.mock.timers.tick(1);
  await rejected;
  assert.equal(signal.aborted, true);
});

test('builds remain pending beyond the default timeout and complete normally', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let signal;
  let finish;
  globalThis.fetch = (url, options) => {
    assert.equal(url, '/api/build');
    assert.equal(options.method, 'POST');
    signal = options.signal;
    return new Promise((resolve, reject) => {
      finish = resolve;
      signal.addEventListener('abort', () => reject(signal.reason), { once: true });
    });
  };
  const pending = buildDeck();
  t.mock.timers.tick(15000);
  assert.equal(signal.aborted, false);
  t.mock.timers.tick(300000);
  assert.equal(signal.aborted, false);
  finish(Response.json({ id: 1 }));
  assert.deepEqual(await pending, { id: 1 });
});

test('caller cancellation still aborts builds without a client timeout', async () => {
  globalThis.fetch = async (_url, { signal }) => {
    signal.throwIfAborted();
    return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(signal.reason), { once: true }));
  };
  const controller = new AbortController();
  const rejected = assert.rejects(buildDeck(controller.signal), (error) => error.name === 'AbortError');
  controller.abort();
  await rejected;
  await assert.rejects(buildDeck(controller.signal), (error) => error.name === 'AbortError');
});

test('restore timeout reports an unknown result and asks to refresh', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  globalThis.fetch = async (url, { method, signal }) => {
    assert.equal(url, '/api/restore/2');
    assert.equal(method, 'POST');
    return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(signal.reason), { once: true }));
  };
  const rejected = assert.rejects(restoreVersion(2), (error) => {
    assert.match(error.message, /结果未知/);
    assert.match(error.message, /刷新/);
    assert.doesNotMatch(error.message, /重试/);
    return true;
  });
  t.mock.timers.tick(15000);
  await rejected;
});

test('timeout covers response content and caller cancellation still aborts polling', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  globalThis.fetch = async (_url, { signal }) => ({
    ok: true,
    json: () => {
      signal.throwIfAborted();
      return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(signal.reason), { once: true }));
    },
  });
  const pending = getDeck();
  const rejected = assert.rejects(pending, /超时/);
  await Promise.resolve();
  t.mock.timers.tick(15000);
  await rejected;

  const controller = new AbortController();
  const cancelled = getDeck(controller.signal);
  const aborted = assert.rejects(cancelled, (error) => error.name === 'AbortError');
  await Promise.resolve();
  controller.abort();
  await aborted;
});
