import {get, post, readableError} from './api.js';
import {el, button, modal} from './dom.js';
import {personalBackupButton} from './personal-recovery.js';

// B05（INTERFACES 个人状态清理）：只读计划先行，确认后按同 etag 清理；
// 备份可下载；任务/候选/调用事实不在范围（服务端强制，UI 如实转述）。
export function personalClearPanel(app) {
  const notice = el('p', {class: 'muted', role: 'status'});
  const scopeView = el('div', {class: 'stack'});
  const identity = app.info.project_identity;
  const key = `deck-master:v3:personal-clear:${identity}`;
  let plan = null, keepBusy = false, pending = null, storageBlocked = false;
  const readPending = () => {
    try {
      const raw = localStorage.getItem(key);
      pending = raw ? JSON.parse(raw) : null;
      if (pending && (pending.project_identity !== identity || !pending.request?.operation_id ||
          pending.request.input?.project_id !== app.info.project_id ||
          pending.request.input?.scope !== 'current_project' || !pending.request.plan_id || !pending.request.manifest_digest)) {
        throw new Error('unverifiable retained request');
      }
      storageBlocked = false;
      if (pending) notice.textContent = '清理结果待核实。原操作编号和请求已保留，请核实并重试原清理。';
    } catch {
      storageBlocked = true;
      notice.textContent = '本机清理恢复记录暂不可核实。原记录保留，请先查看清理备份；未发起新清理。';
    }
  };
  const refresh = () => {
    planButton.disabled = keepBusy || storageBlocked || Boolean(pending);
    commit.disabled = keepBusy || storageBlocked || (!pending && (!plan || !plan.items.length));
    commit.textContent = pending ? '核实并重试原清理' : '确认清理并保留备份';
  };
  const planButton = button('生成清理计划', async () => {
    if (keepBusy) return;
    readPending();
    if (pending || storageBlocked) { refresh(); return; }
    keepBusy = true; refresh(); scopeView.replaceChildren();
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
    finally { keepBusy = false; readPending(); refresh(); }
  });
  const commit = button('确认清理并保留备份', async () => {
    if (keepBusy) return;
    readPending();
    if (storageBlocked || (!pending && !plan)) { refresh(); return; }
    const recovering = Boolean(pending);
    keepBusy = true; refresh();
    try {
      const current = await get('/api/project?light=1');
      if (current.project_identity !== identity) throw new Error('项目身份已改变，请重新打开原项目核实。');
      if (!pending) {
        readPending();
        if (pending || storageBlocked) throw new Error('本机已有待核实记录，请先处理原清理请求。');
        pending = {project_identity: identity, request: {operation_id: crypto.randomUUID(),
          input: {project_id: plan.project_id, scope: 'current_project', draft_ids: 'all', reading_preferences: true},
          plan_id: plan.plan_id, manifest_digest: plan.manifest_digest}};
        try { localStorage.setItem(key, JSON.stringify(pending)); }
        catch { pending = null; throw new Error('无法保留清理恢复记录，未发起清理。'); }
      }
      const sent = pending;
      const result = await post('/api/ui-state/commit-clear', sent.request);
      if (result.status !== 'cleared' || result.operation_id !== sent.request.operation_id ||
          result.plan_id !== sent.request.plan_id || result.manifest_digest !== sent.request.manifest_digest ||
          !Array.isArray(result.cleared)) throw new Error('清理回执无法与原请求对应。');
      if (localStorage.getItem(key) === JSON.stringify(sent)) localStorage.removeItem(key);
      pending = null;
      notice.replaceChildren(el('p', {}, `已清理 ${result.cleared.length} 项，恢复备份已保留；任务与候选未受影响。`), personalBackupButton(app));
      scopeView.replaceChildren();
      plan = null;
    } catch (error) {
      // Only a first-attempt, explicit CAS refusal proves this operation did
      // not clear anything. A replay refusal cannot resolve earlier uncertainty.
      if (!recovering && error.code === 'local_state_conflict' && error.field === 'manifest_digest') {
        try { localStorage.removeItem(key); pending = null; plan = null; }
        catch { /* retain the original recovery request */ }
        notice.textContent = '个人状态已变化，本次清理被拒绝；请重新生成计划。';
      } else notice.textContent = readableError(error) + (pending ? ' 清理结果待核实。原请求保留，请核实并重试原清理。' : '');
    }
    finally { keepBusy = false; refresh(); }
  }, true, {disabled: true});
  const body = el('div', {class: 'panel-body stack'}, el('p', {class: 'muted'}, '只清理本项目的个人草稿与阅读设置；先出只读计划，确认后才清理，并保留恢复备份。项目内容、任务与调用记录不受影响。'),
      el('div', {class: 'row wrap'}, planButton, commit, personalBackupButton(app)), scopeView, notice);
  readPending(); refresh();
  if (document.documentElement.dataset.workbenchUi === 'studio') {
    return button('个人状态与恢复', () => { readPending(); refresh(); modal('个人状态与恢复', body); });
  }
  return el('details', {'data-container':'section', class: 'panel personal-clear'}, el('summary', {}, '清理本机个人状态（草稿与阅读设置）'), body);
}
