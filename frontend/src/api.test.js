import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, getDeck, putDeck, cancelRun, buildDeck, restoreVersion, exportDeck, fileUrl, mergeWorkspace, createDraft, createPageId, draftPatch, formatFinding, addReview, resolveReview, adoptCandidate, comparisonSnapshot } from './api.js';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test('review writes preserve original text and keep global and page scopes distinct', async () => {
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push([url, options.method, options.body && JSON.parse(options.body)]);
    return Response.json({ id: 3 });
  };
  await addReview('全稿意见\n原文');
  await addReview('本页意见', '页/3');
  await resolveReview(3);
  assert.deepEqual(requests, [
    ['/api/reviews', 'POST', { text: '全稿意见\n原文' }],
    ['/api/reviews', 'POST', { text: '本页意见', page_id: '页/3' }],
    ['/api/reviews/3/resolve', 'POST', undefined],
  ]);
});

test('comparison freezes the same layer and adopts the displayed file even after polling changes the candidate', async () => {
  const page = { id: '页/3', content: { title: '原稿' }, image: { file: 'image.png' }, svg: { file: 'old.svg' } };
  const result = { page_id: page.id, result_file: 'candidate.svg' };
  const selected = comparisonSnapshot({ id: 4, kind: 'svg' }, result, page, 2);
  page.svg.file = 'new-current.svg';
  result.result_file = 'late.svg';
  assert.equal(selected.currentFile, 'old.svg');
  assert.equal(selected.candidateFile, 'candidate.svg');
  assert.equal(comparisonSnapshot({ id: 5, kind: 'image' }, result, page, 3).currentFile, 'image.png');
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/runs/4/adopt/%E9%A1%B5%2F3');
    assert.deepEqual(JSON.parse(options.body), { expected_file: 'candidate.svg' });
    return Response.json({ error: '候选已更新' }, { status: 409 });
  };
  await assert.rejects(adoptCandidate(selected.runId, selected.pageId, selected.candidateFile), error => error.status === 409);
});

test('table findings show the cell location and expected and actual text', () => {
  const output = formatFinding({
    code: 'table_cell_text_mismatch', table_id: 't1', row_id: 'r2', column_id: 'c3',
    expected: '合成原文', actual: '回读文字',
  });
  for (const detail of ['表格单元格文字不一致', '表格 t1', '行 r2', '列 c3', '期望："合成原文"', '实际："回读文字"']) {
    assert.ok(output.includes(detail), output);
  }
});

test('finding details retain empty values and support partial table locations', () => {
  const output = formatFinding({ code: 'table_cell_text_mismatch', table_id: 't1', expected: ' ', actual: '' });
  assert.ok(output.includes('表格 t1'));
  assert.ok(output.includes('期望：" "'));
  assert.ok(output.includes('实际：""'));
  assert.ok(!output.includes('undefined'));
  assert.equal(formatFinding({ code: 'missing_node', text: '正文', element: 'n1' }), '缺少节点：正文（n1）');
  assert.equal(formatFinding({ code: 'new_code' }), 'new_code');
  const cell = formatFinding({ code: 'unreadable_text', table_id: 't1', row: 1, column: 0 });
  assert.ok(cell.includes('第 2 行') && cell.includes('第 1 列'));
});

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

test('Card B: deleting a page then creating another preserves unsaved drafts', async () => {
  const page = { id: 'p1', content: { title: '原稿', body_blocks: [] }, notes: '讲稿' };
  const drafts = { p1: createDraft(page, 1) };
  drafts.p1.page.content.title = '作者未保存的输入';
  drafts.p1.page.notes = '作者未保存的讲稿';
  const before = structuredClone(drafts.p1);
  // The Host deletes the page; polling must not remove its local draft.
  globalThis.fetch = async () => Response.json({ version: 2, deck: { pages: [] } });
  const workspace = await getDeck();
  const id = createPageId(workspace.deck.pages, drafts);
  assert.match(id, /^p[0-9a-f]{8}$/);
  assert.equal(Object.hasOwn(drafts, id), false);
  globalThis.fetch = async (_url, options) => {
    const patch = JSON.parse(options.body);
    assert.deepEqual(patch, { order: [id], pages: [{ id }] });
    return Response.json({ version: 3, deck: { pages: [{ ...page, id }] } });
  };
  const result = await putDeck(workspace.version, { order: [id], pages: [{ id }] });
  drafts[id] = createDraft(result.deck.pages[0], result.version);
  assert.deepEqual(drafts.p1, before);
  assert.notEqual(drafts[id], drafts.p1);
  assert.equal(result.deck.pages.some(item => item.id === 'p1'), false);
  assert.equal(drafts.p1.page.content.title, '作者未保存的输入');
  assert.equal(drafts.p1.page.notes, '作者未保存的讲稿');
});

test('Card B: page IDs retry collisions with both saved pages and draft keys', () => {
  const pages = [{ id: 'p11111111' }];
  const drafts = { p22222222: createDraft({ id: 'p22222222' }, 1) };
  const candidates = ['11111111-aaaa', '22222222-bbbb', '33333333-cccc'];
  const id = createPageId(pages, drafts, () => candidates.shift());
  assert.equal(id, 'p33333333');
  assert.equal(candidates.length, 0);
  assert.deepEqual(pages, [{ id: 'p11111111' }]);
  assert.deepEqual(Object.keys(drafts), ['p22222222']);
});
