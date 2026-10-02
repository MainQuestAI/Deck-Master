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
    const failure = new ApiError(typeof error === 'string' ? error : error.message || '本次操作未完成，当前输入仍保留。',
      error.code || 'request_failed', response.status, error.field);
    failure.details = typeof error === 'object' ? error : {}; throw failure;
  }
  return payload;
}
export function readableError(error) {
  const labels = {
    icon_basis_changed:'图标对象或页面版本已变化。范围和意见保留，请重新定位并确认。',
    icon_invalid:'图标要求超出可验证范围，请核对对象、区域和处理方式。',
    icon_preview_required:'此图标候选需先通过实际 PPT 检查，再预览采用。',
    restore_basis_changed: '当前版本已变化，未恢复或覆盖任何页。来源与当前版本均保留，请比较后重新预览。',
    delivery_blocked: '所选版本尚不满足正式交付条件，请处理下面的页与检查项。',
    input_reconciliation_pending: '所选版本的内容与任务要求尚未协调，请先完成内容更新。',
    export_privacy_blocked: '公开副本中存在需处理的私密内容或不支持的资源。本次未生成文件包，原件保留。',
    export_file_changed: '文件包或清单已变化，未提供损坏文件。请从所选版本重新生成。',
    export_not_found: '本项目尚未找到这个文件包，可按保留的原版本与用途重试。',
    content_basis_changed: '内容或大纲基准已变化。你的输入仍保留，请比较后重新预览影响。',
    content_invalid: '本次内容调整不满足范围或来源约束，请核对选页和要求。',
    local_state_conflict: '另一个窗口已保存不同内容。你的草稿仍保留，请比较两稿或另存一份。',
    legacy_run_format: '这是旧运行目录，新工作台不会在原目录迁移。请新建项目并重新选入材料。',
    project_unavailable: '项目目前无法读取，请检查保存位置、权限或版本兼容性。',
    revision_not_found: '这个版本不在当前项目的已提交历史中。没有跳转到其它版本。',
    sample_readonly: '这个示例项目只供阅读。请新建自己的项目后编辑。',
    candidate_basis_changed: '候选的生成依据已变化。本次未采用任何页，选择仍保留；请核对冲突后重新选择并预览。',
    adoption_target_changed: '当前采用目标或计划已变化。本次未采用任何页，请重新预览采用影响。',
    stage_prerequisite_missing: '整稿制作前还需要当前原图、SVG 与对应预览。请先继续本页制作。',
    stage_quality_blocked: '当前逐页审图尚未全部通过。请先完成审阅，已查看和候选采用都不代表通过。',
    stage_format_required: '这个阶段需要新版工作台项目；旧项目不会原地迁移。',
    style_conflict: '风格要求或目标页基准已变化，未覆盖任何新内容；请核对逐项冲突后另建计划。',
    style_invalid: '本次风格要求或扩展条件不满足，请检查所选版本、目标与已采用候选。',
    candidate_not_found: '所选版本没有这个候选，未跳转到其它候选。',
    action_not_found: '这个固定版本无法再解析该项待办。已保留当前工作面，请重新读取待办或查看对应历史。',
    invalid_action_query: '待办读取范围无效，当前工作面仍保留。请重新打开所选版本。',
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
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(wireCanonical(value)));
  return [...new Uint8Array(bytes)].map(v => v.toString(16).padStart(2, '0')).join('');
}
// The service hashes Python's canonical_json_bytes after JSON parsing. Small
// fractional coordinates use scientific notation there (including a two-digit
// exponent), while JSON.stringify uses decimal notation down to 1e-6.
export function wireCanonical(value) {
  if (Array.isArray(value)) return '[' + value.map(wireCanonical).join(',') + ']';
  if (value && typeof value === 'object') {
    const order = (a, b) => {
      const left = Array.from(a, ch => ch.codePointAt(0)), right = Array.from(b, ch => ch.codePointAt(0));
      for (let i = 0; i < Math.min(left.length, right.length); i++) if (left[i] !== right[i]) return left[i] - right[i];
      return left.length - right.length;
    };
    return '{' + Object.keys(value).sort(order).map(key => JSON.stringify(key) + ':' + wireCanonical(value[key])).join(',') + '}';
  }
  if (typeof value === 'number' && value !== 0 && Math.abs(value) < .0001) {
    return value.toExponential().replace(/e([+-])(\d)$/, 'e$10$2');
  }
  return JSON.stringify(value);
}
