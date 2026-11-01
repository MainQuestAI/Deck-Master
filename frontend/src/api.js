export class ApiError extends Error {
  constructor(status, data) {
    super(data.error || `请求失败（${status}），请重试`);
    this.status = status;
    this.data = data;
  }
}

async function request(path, options) {
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error('无法连接本地服务，请检查 deck serve 是否仍在运行后重试');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({ error: `请求失败（${response.status}），请重试` }));
    throw new ApiError(response.status, data);
  }
  return response;
}

const json = async (path, options) => (await request(path, options)).json();
const post = (path) => json(path, { method: 'POST' });

export const getDeck = (signal) => json('/api/deck', { signal });
export const putDeck = (base, patch) => json(`/api/deck?base=${base}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(patch),
});
export const cancelRun = (id) => post(`/api/runs/${encodeURIComponent(id)}/cancel`);
export const buildDeck = () => post('/api/build');
export const restoreVersion = (version) => post(`/api/restore/${version}`);

export function fileUrl(reference) {
  if (!reference) return null;
  const sha = reference.split('.')[0];
  if (!/^[a-f0-9]{64}$/i.test(sha)) throw new Error('作品附件编号有误，请重新读取作品');
  return `/api/files/${sha}`;
}

export async function exportDeck(format) {
  if (!['md', 'pptx'].includes(format)) throw new Error('请选择 Markdown 或 PPTX');
  const response = await request(`/api/export/${format}`);
  const status = JSON.parse(response.headers.get('X-Deck-Status') || '{}');
  return { blob: await response.blob(), filename: `deck.${format}`, status };
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
