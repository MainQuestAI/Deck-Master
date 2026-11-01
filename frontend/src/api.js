export class ApiError extends Error {
  constructor(status, data) {
    super(data.error || `请求失败（${status}），请重试`);
    this.status = status;
    this.data = data;
  }
}

async function request(path, options = {}, timeout = 15000, read = response => response.json(), timeoutMessage = '请求本地服务超时，请检查服务状态后重试') {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (options.signal?.aborted) abort();
  else options.signal?.addEventListener('abort', abort, { once: true });
  const timer = timeout === null ? null : setTimeout(abort, timeout);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal }).catch(error => {
      if (options.signal?.aborted) throw error;
      throw new Error('无法连接本地服务，请检查 deck serve 是否仍在运行后重试');
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({ error: `请求失败（${response.status}），请重试` }));
      throw new ApiError(response.status, data);
    }
    return await read(response);
  } catch (error) {
    if (options.signal?.aborted) throw error;
    if (controller.signal.aborted) throw new Error(timeoutMessage);
    throw error;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', abort);
  }
}

const post = (path, timeout, timeoutMessage) => request(path, { method: 'POST' }, timeout, undefined, timeoutMessage);

export const getDeck = (signal) => request('/api/deck', { signal });
export const putDeck = (base, patch) => request(`/api/deck?base=${base}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(patch),
});
export const cancelRun = (id) => post(`/api/runs/${encodeURIComponent(id)}/cancel`);
export const buildDeck = (signal) => request('/api/build', { method: 'POST', signal }, null);
export const restoreVersion = (version) => post(`/api/restore/${version}`, undefined, '结果未知，请刷新查看当前版本');

export function fileUrl(reference) {
  if (!reference) return null;
  const sha = reference.split('.')[0];
  return `/api/files/${sha}`;
}

export async function exportDeck(format) {
  return request(`/api/export/${format}`, {}, 15000, async response => {
    const status = JSON.parse(response.headers.get('X-Deck-Status') || '{}');
    return { blob: await response.blob(), filename: `deck.${format}`, status };
  });
}

// Runs can change without a new deck version. A late poll must not undo a save.
export function mergeWorkspace(current, incoming) {
  if (current && incoming.version < current.version) return current;
  return incoming;
}

export function createDraft(page, base) {
  return { base, original: structuredClone(page), page: structuredClone(page), conflict: null };
}

export function draftPatch(draft) {
  const page = { id: draft.page.id };
  for (const field of ['content', 'purpose', 'layout', 'notes']) {
    if (JSON.stringify(draft.original[field]) !== JSON.stringify(draft.page[field])) {
      page[field] = draft.page[field];
    }
  }
  return { pages: [page] };
}
