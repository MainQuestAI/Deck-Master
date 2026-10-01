// 候选决定收据的终态判定与摘要重算（零 DOM 依赖）。
// business-operations.js 与收据回归测试共同导入生产实现——终审补丁 P2：
// 回归测试不得维护仅存在于测试中的终态判定副本。
import {digest} from './api.js';

// 升级前的待核实记录以旧 action 名冻结（摘要也用旧 kind 计算）。
export const LEGACY_ACTIONS = {'candidates.decision': 'candidates.decide'};
export const canonicalAction = action => LEGACY_ACTIONS[action] || action;

// 非 legacy：business.submit 冻结的 payload.request_digest 即预期摘要（payload
// 已被 payload_digest 锁定）。legacy（candidates.decision）：升级前冻结摘要用旧
// kind 计算，与升级后服务端记录必然不等——按规范 kind 与原 payload 重算。
// project_id 用 document 的 project_id（与 operations.request_digest 同字段）。
export async function expectedRequestDigest(payload, projectId) {
  const {action, request} = payload;
  if (!LEGACY_ACTIONS[action]) return payload.request_digest;
  return await digest({protocol: 'changes.v1', kind: canonicalAction(action), project_id: projectId,
    base_revision: request.base_revision, payload: request.input});
}

// 确定终态谓词：operation 身份一致 + 摘要一致 + committed 带修订或 unchanged。
export async function receiptTerminal(entry, response, projectId) {
  const expected = await expectedRequestDigest(entry.pending.payload, projectId);
  return Boolean(response.operation_id === entry.pending.operation_id &&
    response.request_digest === expected &&
    (response.status === 'committed' && response.operation_result?.revision_id ||
     response.status === 'unchanged'));
}
