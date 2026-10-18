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
export async function postBinary(path, file) {
  if(!token)token=(await get('/api/session')).token;
  return request(path,{method:'POST',headers:{'Content-Type':file.type || 'application/octet-stream','X-Deck-Token':token},body:file});
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
    failure.path = typeof error === 'object' ? error.path || error.field || null : null;
    failure.field ||= failure.path;
    // New collaboration envelopes nest facts in details; old workbench errors
    // keep them directly beside code/field. Preserve both forms and any readable
    // partial report even when admission returns HTTP 409.
    failure.details = typeof error === 'object' ? {...error, ...(error.details || {})} : {};
    failure.result = payload.result ?? null;
    failure.envelope = payload;
    failure.recoverable = error.recoverable;
    throw failure;
  }
  return payload;
}
export function readableError(error) {
  const labels = {
    migration_required: '此项目需要先确认升级控制记录。已有稿件保留；升级不会批准制作或授予额度。',
    request_paused: '当前请求已暂停。稿件和报告仍可阅读；明确恢复后才能继续本次制作。',
    request_closed: '当前请求已结束。已有产物保留，请按新的明确要求开始下一请求。',
    authorization_revoked: '本次授权已撤回。已有稿件和调用记录保留；旧版本也不能恢复该授权。',
    needs_reviewer: '还需要符合要求的审阅者。当前稿件和可读报告保留，请查看审阅范围与缺口。',
    professional_review_required: '还缺所选实际文件的专业复核。稿件和审阅包仍可阅读，请核对文件与复核范围。',
    scope_exceeded: '本次动作超出明确范围。输入仍保留，请核对所选页、层与用途。',
    authority_insufficient: '当前授权不足以执行本次动作。输入仍保留，请查看实际范围与下一责任。',
    decision_needed: '还缺本次工作的明确决定。请核对具体缺项、相关范围和下一步操作。',
    authority_channel_unavailable: '当前连接不能核实所需授权。输入仍保留，请通过支持的指令通道继续。',
    budget_exhausted: '当前制作额度已用完。已有结果保留，不会自动重试或刷新额度。',
    budget_unknown: '已有调用费用尚待核实。已有稿件保留，请先核实原调用。',
    basis_stale: '本次依据已过期。输入和固定比较仍保留，请读取当前状态后重新确认影响。',
    binding_stale: '任务绑定的依据已过期。原稿与调用事实保留，请按当前依据重新计划。',
    binding_invalid: '任务没有可核实的当前绑定。原稿和已发生调用保留，请通过当前请求重新计划。',
    preproduction_blocked: '制作前审阅仍有缺口。当前稿件和报告可读，请处理明确问题后继续。',
    engineering_checks_required: '所选实际文件的工程检查尚未完成，请核对文件与未完成项。',
    persistence_none: '这是严格只读工作。报告应保留在来源之外，导入须作为单独的明确动作。',
    user_stop: '项目处于用户停止状态。读取和原调用核实仍可进行。',
    invalid_input: '本次要求有未满足的字段或范围。输入仍保留，请查看具体依据后调整。',
    object_not_found: '没有找到明确选择的项目或记录。输入仍保留，请核对来源位置与版本。',
    source_not_found: '没有找到明确选择的源文件。原稿未改，请核对文件位置。',
    source_changed: '来源在读取期间发生变化。可读报告已保留，请固定来源后重新审阅。',
    conflict: '项目已由另一项操作更新。本次输入仍保留，请读取当前状态并比较后重试。',
    material_upload_invalid:'材料文件未接收。请检查支持的文件类型、文件名及 64 MiB 大小限制；已有材料保留。',
    material_upload_not_found:'尚未找到这个文件的接收记录。可重新选择原文件，沿原编号继续上传。',
    material_upload_conflict:'此接收编号对应另一份文件。已接收内容保留，请重新选入要添加的文件。',
    material_upload_changed:'已接收文件与原记录不一致，未改项目输入。请重新选入文件并核对。',
    visual_reference_conflict: '参考或项目已更新，要求仍保留，请回当前版本核实后重新分析。',
    visual_reference_invalid: '截图或分析结果不满足要求，请检查格式、范围和参考冲突。',
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
