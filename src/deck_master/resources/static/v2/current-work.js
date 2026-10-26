import {openAction} from './action-targets.js';
import {el, button} from './dom.js';
import {todoTitle, todoMeta, todoButton} from './action-summary.js';

// Both surfaces render the same fixed read projection. Navigation is not a
// production action; every eventual submission still uses the existing guard.
export function currentWork(app, work = app.summary.current_work) {
  if (!work) return el('section', {class:'overview-todos stack', 'data-current-work':'true'},
    el('h2', {}, '本次工作投影待重新读取'),
    el('p', {}, '当前控制状态与工作投影尚未对齐。已读稿件和版本保持，重新读取后再查看下一动作。'),
    button('重新读取本次工作', () => app.loadRoute({...app.route})),
    button('阅读已有产物', () => app.go({surface:'content'})));
  let panel;
  const closePanel = () => panel.closest('dialog')?.close();
  const next = work.next;
  const roles = {master:'主协调',content:'内容制作',design:'设计制作',caller:'发起人',user:'用户',reviewer:'审阅者'};
  const checks = {pass:'当前范围已审',missing:'稿件待审',blocked:'存在待修问题',unknown:'审查依据待核实',not_evaluated:'尚未评估',no_manuscript:'尚无逐页稿'};
  const rest = next.actions.filter(action => action.action_id !== next.primary_action?.action_id);
  const row = action => el('article', {class:'todo-row'},
    el('div', {}, el('h3', {}, todoTitle(action)), el('p', {class:'muted'}, todoMeta(app, action))),
    todoButton(app, action, false, closePanel));
  const evidence = el('details', {}, el('summary', {}, '产物、审查与下一步依据'),
    el('pre', {class:'evidence-json'}, JSON.stringify(work, null, 2)));
  const secondary = rest.length > 0 && el('details', {class:'todo-secondary', open:window.innerWidth > 1100},
    el('summary', {class:'todo-list-head'}, el('h3', {}, '其他当前动作'), el('span', {}, `${rest.length} 类事项`)),
    row(rest[0]), rest.length > 1 && el('details', {class:'todo-more'},
      el('summary', {}, `其余 ${rest.length - 1} 类事项与依据`), rest.slice(1).map(row), evidence),
    rest.length === 1 && evidence);
  // Optional records remain readable, but never acquire current-work priority.
  const optional = work.optional.length > 0 && el('details',
    {class:'current-work-optional', open:!work.scope.known},
    el('summary', {}, '其他可读记录（不属于本次必做）'), work.optional.map(row));
  return panel = el('section', {class:'overview-todos', 'aria-label':'制作待办', 'data-current-work':'true'},
    el('div', {class:'todo-priority'},
      el('span', {class:'todo-kicker'}, '本次工作'),
      el('h2', {}, next.title),
      el('p', {}, '下一责任：' + (roles[next.responsible_role] || next.responsible_role) +
        ' · 审查：' + (checks[work.review.status] || work.review.status)),
      el('div', {class:'todo-bottom'},
        next.primary_action && el('span', {}, todoMeta(app, next.primary_action)),
        button(next.label, () => {closePanel();if(next.primary_action)openAction(app,next.primary_action,{surface:next.surface});else app.go(next.navigation||{surface:next.surface});}, true, {disabled:next.primary_action?.enabled===false,'data-priority-action':'true'}))),
    el('div', {class:'stack'}, secondary, optional,
      work.blockers.length > 0 && el('p', {class:'field-error'}, '接续仍有阻断，请查看具体范围与依据。'),
      !rest.length && evidence));
}
