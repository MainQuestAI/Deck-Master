export class ApiError extends Error {
  constructor(message, code = 'network_unavailable', status = 0, field = null) {
    super(message); this.code = code; this.status = status; this.field = field;
  }
}
let token;
export async function get(path, {signal} = {}) { return request(path, {signal}); }
export async function post(path, value, {signal} = {}) {
  const body = JSON.stringify(value);
  if (new TextEncoder().encode(body).length > 2_000_000) throw new ApiError('内容过大，输入仍保留。请减少本次内容后重试。', 'body_too_large', 422);
  if (!token) token = (await get('/api/session')).token;
  return request(path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Deck-Token': token}, body, signal});
}
async function request(path, options) {
  let response;
  try { response = await fetch(path, {cache: 'no-store', credentials: 'same-origin', ...options}); }
  catch (error) { if (error.name === 'AbortError') throw error; throw new ApiError('本机服务暂时无法连接，已读内容与本机输入仍保留。'); }
  let payload;
  try { payload = await response.json(); }
  catch { throw new ApiError('服务回包无法读取，当前输入仍保留。', 'invalid_response', response.status); }
  if (!response.ok) {
    const error = payload.error || {};
    if (response.status === 403) token = null;
    throw new ApiError(typeof error === 'string' ? error : error.message || '本次操作未完成，当前输入仍保留。',
      error.code || 'request_failed', response.status, error.field);
  }
  return payload;
}
export function readableError(error) {
  const labels = {
    local_state_conflict: '另一个窗口已保存不同内容。你的草稿仍保留，请比较两稿或另存一份。',
    legacy_run_format: '这是旧运行目录，新工作台不会在原目录迁移。请新建项目并重新选入材料。',
    project_unavailable: '项目目前无法读取，请检查保存位置、权限或版本兼容性。',
    revision_not_found: '这个版本不在当前项目的已提交历史中。没有跳转到其它版本。',
    sample_readonly: '这个示例项目只供阅读。请新建自己的项目后编辑。',
    port_conflict: '端口已被占用，未关闭其它服务。请使用自动端口重新打开。',
  };
  return labels[error.code] || error.message || '操作未完成，当前输入仍保留。';
}
export function fileURL(ref) {
  if (!ref || !/^\.deckmaster\/objects\/[a-f0-9]{2}\/[a-f0-9]{64}\.[a-z0-9]+$/.test(ref.path) || !/^[a-f0-9]{64}$/.test(ref.sha256)) return null;
  return '/api/file?' + new URLSearchParams({path: ref.path, sha256: ref.sha256});
}
export const revisionQuery = (revision) => revision ? '?' + new URLSearchParams({revision}) : '';
export function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
  return JSON.stringify(value);
}
export async function digest(value) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical(value)));
  return [...new Uint8Array(bytes)].map(v => v.toString(16).padStart(2, '0')).join('');
}
