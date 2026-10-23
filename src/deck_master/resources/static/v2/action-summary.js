// Presentation of existing backend action facts; no eligibility or priority decisions.
import {button, disabledReason} from './dom.js';
import {openAction} from './action-targets.js';

export const kindLabels = {verify_execution: '执行待核实', handoff: '制作任务待交接', inspect_failure: '失败待查看',
  replan: '需重新计划', compare_candidates: '候选待决定', reconcile_inputs: '输入待协调',
  prepare_stage: '产物待补齐', refresh_stage: '产物依据已变化', review_results: '结果待阅读', review_quality: '质量记录待查看'};
export const nextLabels = {verify_execution: '去核实', handoff: '去交接', inspect_failure: '查看失败', replan: '重新计划',
  compare_candidates: '比较候选', reconcile_inputs: '去协调', prepare_stage: '查看待补页', refresh_stage: '查看依据',
  review_results: '去阅读', review_quality: '查看记录'};
const reasonLabels = {dependency_basis_changed:'已采用依据变化，重新准备本次任务后再交接。', dependencies_unverifiable:'任务依据暂不可核实，先检查原记录。',unknown_calls_recorded: '任务记录了未知调用；先核实原执行，未确认前不要重复派发。',
  running_task_stale: '任务已运行超过 30 分钟，状态待核实；超时不等于失败。',
  running_task_unclaimed: '运行中的任务缺少执行标识，需核实接手记录。',
  task_failed: '执行失败；当前稿件保留，可调整要求后重试。',
  task_superseded: '任务已由新任务接续；查看当前任务后再操作。',
  task_awaiting_host: '要求已保存，尚未开始；复制制作要求到制作工具执行。',
  task_unreadable: '任务记录损坏，已隔离；其余记录不受影响。',
  candidate_pending: '候选已返回，当前版本保留；比较后再决定是否采用。',
  candidate_unreadable: '候选记录损坏，已隔离；仍计入待决定。',
  content_needs_reconciliation: '新输入与当前内容尚未对齐；先看影响再决定。',
  stage_missing: '上游内容已就绪，该层尚未生成。',
  stage_basis_changed: '该层的生成依据与当前上游版本不同。已有产物仍可阅读，请查看依据后决定是否重新试作。',
  quality_reviews_recorded: '已记录质量检查；查看结论与范围。',
  task_results_ready: '结果已返回待阅读；查看不代表采用。'};
const routeLayer = {blueprint: 'original_image', svg: 'svg', svg_preview: 'svg', ppt_preview: 'ppt', pptx: 'ppt'};

export function actionRoute(action) {
  if (['prepare_stage', 'refresh_stage'].includes(action.kind) && action.page_ids?.length === 1 && routeLayer[action.layer])
    return {surface: 'page', page_id: action.page_ids[0], layer: routeLayer[action.layer]};
  if (action.kind === 'reconcile_inputs') return {surface: 'content'};
  return {surface: 'runs'};
}
export function todoTitle(action) {
  const layer = {blueprint:'原图',svg:'SVG',svg_preview:'SVG 预览',ppt_preview:'PPT 预览',pptx:'整稿 PPT'}[action.layer] || '产物类型待核实';
  const base = action.kind === 'prepare_stage' ? `${layer}待生成`
    : action.kind === 'refresh_stage' ? `${layer}依据已变化` : kindLabels[action.kind] || '待核实事项';
  if (['verify_execution','handoff','inspect_failure','replan','review_results'].includes(action.kind) && action.object_count) return `${action.object_count} 个任务 · ${base}`;
  if (action.kind === 'compare_candidates' && action.object_count) return `${action.object_count} 个候选 · ${action.state === 'unknown' ? '依据待核实' : base}`;
  return action.page_ids?.length ? `${action.page_ids.length} 页${base}` : base;
}
export function reasonText(action) {
  if (action.kind === 'compare_candidates' && action.state === 'unknown') return '候选依据或任务关系暂不可核实，先查看原记录。';
  return (reasonLabels[action.reason_code] || action.reason_code || '') +
    (action.blocked_reason === 'candidate_unreadable' ? ' 候选记录损坏，已隔离。' : '');
}
export function todoMeta(app, action) {
  const pages = (action.page_ids || []).map(id => {
    const index = app.summary.pages.findIndex(page => page.page_id === id);
    return index < 0 ? id : index + 1;
  });
  if (!pages.length) return '项目级事项';
  return pages.length > 4 ? `第 ${pages.slice(0, 4).join('、')} 等共 ${pages.length} 页` : `第 ${pages.join('、')} 页`;
}
export function todoButton(app, action, primary = false, beforeNavigate = () => {}) {
  const blocked = action.enabled === false;
  const precise = app.health.ui_capabilities?.includes('action_targets.v1');
  return disabledReason(button((nextLabels[action.kind] || '查看') + (precise ? '' : ' · 通用入口'), () => {beforeNavigate(); return openAction(app, action, actionRoute(action));}, primary,
    {disabled: blocked}), blocked ? '该项记录暂不可读（已隔离），先处理其它待办。' : '');
}

