import {get, post, readableError} from './api.js';
import {el, button, modal} from './dom.js';
import {personalBackupButton} from './personal-recovery.js';

// B05（INTERFACES 个人状态清理）：只读计划先行，确认后按同 etag 清理；
// 备份可下载；任务/候选/调用事实不在范围（服务端强制，UI 如实转述）。
export function personalClearPanel(app) {
  const notice = el('p', {class: 'muted', role: 'status'});
  const scopeView = el('div', {class: 'stack'});
  let plan = null, keepBusy = false;
  const planButton = button('生成清理计划', async () => {
    if (keepBusy) return; keepBusy = true; planButton.disabled = true; scopeView.replaceChildren();
    try {
      const current = await get('/api/view/summary');
      plan = await post('/api/ui-state/plan-clear', {input: {project_id: current.project_id, scope: 'current_project',
                                                             draft_ids: 'all', reading_preferences: true}});
      // replaceChildren 会把 null/数字实参字符串化（"null"/"0" 文本）：条件节点
      // 必须先组数组过滤再展开。
      const planParts = [
        el('p', {}, `将清理 ${plan.items.length} 项：${plan.items.map(item => ({draft: '草稿', gallery_state: '画廊选择', reading_position: '阅读位置', overview_preferences: '总览阅读偏好',result_reading:'结果已读记录'})[item.kind]).join('、') || '无'}；恢复备份将保存在本机。`),
        plan.blockers.length ? el('p', {class: 'field-error'}, `${plan.blockers.length} 项暂不清理（未确认的提交）：请先在顶部核实未确认的保存请求。`) : null,
        plan.kept_out.length ? el('p', {class: 'muted'}, `损伤保留：${plan.kept_out.join('；')}`) : null,
        el('p', {class: 'muted'}, '任务、候选、调用记录与项目文件不在清理范围。')];
      scopeView.replaceChildren(...planParts.filter(part => part));
      notice.textContent = '';
    } catch (error) { plan = null; notice.textContent = readableError(error); }
    finally { keepBusy = false; planButton.disabled = false; commit.disabled = !plan || !plan.items.length; }
  });
  const commit = button('确认清理并保留备份', async () => {
    if (keepBusy || !plan) return; keepBusy = true; commit.disabled = true;
    try {
      const result = await post('/api/ui-state/commit-clear', {operation_id: crypto.randomUUID(),
        input: {project_id: plan.project_id, scope: 'current_project', draft_ids: 'all', reading_preferences: true},
        plan_id: plan.plan_id, manifest_digest: plan.manifest_digest});
      notice.replaceChildren(el('p', {}, `已清理 ${result.cleared.length} 项，恢复备份已保留；任务与候选未受影响。`), personalBackupButton(app));
      scopeView.replaceChildren();
      plan = null;
    } catch (error) { notice.textContent = readableError(error) + ' 未清理任何对象。'; }
    finally { keepBusy = false; planButton.disabled = false; }
  }, true, {disabled: true});
  const body = el('div', {class: 'panel-body stack'}, el('p', {class: 'muted'}, '只清理本项目的个人草稿与阅读设置；先出只读计划，确认后才清理，并保留恢复备份。项目内容、任务与调用记录不受影响。'),
      el('div', {class: 'row wrap'}, planButton, commit, personalBackupButton(app)), scopeView, notice);
  if (document.documentElement.dataset.workbenchUi === 'studio') {
    return button('个人状态与恢复', () => modal('个人状态与恢复', body));
  }
  return el('details', {'data-container':'section', class: 'panel personal-clear'}, el('summary', {}, '清理本机个人状态（草稿与阅读设置）'), body);
}
