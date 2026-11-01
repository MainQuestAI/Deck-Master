import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, getDeck, putDeck, cancelRun, exportDeck, fileUrl, mergeWorkspace, createDraft, draftPatch } from './api.js';

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

test('cancel is an interface call and does not use browser storage', async () => {
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

test('file URLs use SHA without extension and reject non-file references', () => {
  assert.equal(fileUrl(`${'a'.repeat(64)}.jpg`), `/api/files/${'a'.repeat(64)}`);
  assert.equal(fileUrl(null), null);
  assert.throws(() => fileUrl('../outside'), /附件/);
});
