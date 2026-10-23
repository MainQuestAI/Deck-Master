import {openAction} from './action-targets.js';
import {el, button} from './dom.js';

// Both surfaces render the same fixed read projection. Navigation is not a
// production action; every eventual submission still uses the existing guard.
export function currentWork(app, work = app.summary.current_work) {
  if (!work) return el('section', {class:'stack'},
    el('h2', {}, '当前核心未提供本次工作投影'),
    button('阅读已有产物', () => app.go({surface:'content'})));
  const next = work.next;
  const roles = {master:'主协调',content:'内容制作',design:'设计制作',caller:'发起人',user:'用户',reviewer:'审阅者'};
  const actionLabels={verify_execution:'核实执行',inspect_failure:'查看失败',reconcile_inputs:'协调输入',replan:'重新计划',handoff:'查看交接',compare_candidates:'比较候选',review_results:'阅读结果',review_quality:'查看审查',prepare_stage:'查看缺少产物',refresh_stage:'查看过期依据'};
  const checks = {pass:'当前范围已审',missing:'稿件待审',blocked:'存在待修问题',unknown:'审查依据待核实',not_evaluated:'尚未评估',no_manuscript:'尚无逐页稿'};
  return el('section', {class:'overview-todos todo-clear', 'aria-label':'本次工作'},
    el('h2', {}, next.title),
    el('p', {}, '下一责任：' + (roles[next.responsible_role] || next.responsible_role)),
    el('p', {}, '审查：' + (checks[work.review.status] || work.review.status)),
    button(next.label, () => {document.querySelector('#modal')?.close();if(next.primary_action)openAction(app,next.primary_action,{surface:next.surface});else app.go({surface:next.surface});}, true, {disabled:next.primary_action?.enabled===false}),
    next.actions.filter(action=>action.action_id!==next.primary_action?.action_id).length>0&&el('details',{},el('summary',{},'其他当前动作'),next.actions.filter(action=>action.action_id!==next.primary_action?.action_id).map(action=>button(actionLabels[action.kind]||'查看记录',()=>openAction(app,action,{surface:'runs'}),false,{disabled:action.enabled===false}))),
    work.blockers.length > 0 && el('p', {class:'field-error'}, '接续仍有阻断，请查看具体范围与依据。'),
    el('details', {}, el('summary', {}, '产物、审查与下一步依据'),
      el('pre', {class:'evidence-json'}, JSON.stringify(work, null, 2))));
}
