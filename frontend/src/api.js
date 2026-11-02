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

const findingLabels = {
  notes_page_identity_mismatch: '讲稿对应的页面不一致', speaker_notes_mismatch: '讲稿内容不一致',
  slide_count_mismatch: '幻灯片数量不一致', missing_slide: '缺少幻灯片',
  unreadable_text: '文字不可读', svg_ppt_text_mismatch: 'SVG 与 PPTX 文字不一致',
  missing_visible_atom: '缺少正文文字', shape_outside_slide: '元素超出页面',
  missing_node: '缺少节点', missing_edge: '缺少连线',
  unverifiable_edge_geometry: '无法核对连线位置', reversed_arrow: '箭头方向相反', edge_not_connected: '连线未连接到节点',
  unverifiable_text_mapping: '无法核对文字对应关系', hidden_or_tiny_text: '文字隐藏或过小',
  unverifiable_table_ownership: '无法核对表格归属', table_cell_ownership_mismatch: '表格单元格归属不一致',
  table_cell_text_mismatch: '表格单元格文字不一致',
  node_atom_ownership_mismatch: '节点与正文归属不一致',
};

export function formatFinding(finding) {
  const parts = [
    `${findingLabels[finding.code] || finding.code}${finding.text ? `：${finding.text}` : ''}${finding.element && finding.element !== finding.table_id ? `（${finding.element}）` : ''}`,
  ];
  if (finding.table_id != null) {
    parts.push(`表格 ${finding.table_id}`);
    if (finding.row_id != null) parts.push(`行 ${finding.row_id}`);
    else if (Number.isInteger(finding.row)) parts.push(`第 ${finding.row + 1} 行`);
    if (finding.column_id != null) parts.push(`列 ${finding.column_id}`);
    else if (Number.isInteger(finding.column)) parts.push(`第 ${finding.column + 1} 列`);
  }
  if ('expected' in finding) parts.push(`期望：${JSON.stringify(finding.expected)}`);
  if ('actual' in finding) parts.push(`实际：${JSON.stringify(finding.actual)}`);
  return parts.join(' · ');
}
