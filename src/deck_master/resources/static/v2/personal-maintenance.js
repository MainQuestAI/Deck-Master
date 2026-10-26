import {get, post, readableError, canonical, digest} from './api.js';
import {el, button, modal} from './dom.js';
import {personalBackupButton} from './personal-recovery.js';

function clearError(error) {
  return error.code === 'local_state_conflict'
    ? '清理请求或核实依据与当前状态不一致，请先核实原清理结果。'
    : readableError(error);
}

// B05（INTERFACES 个人状态清理）：只读计划先行，确认后按同 etag 清理；
// 备份可下载；任务/候选/调用事实不在范围（服务端强制，UI 如实转述）。
export function personalClearPanel(app) {
  const notice = el('p', {class: 'muted', role: 'status'});
  const scopeView = el('div', {class: 'stack'});
  const identity = app.info.project_identity;
  const key = `deck-master:v3:personal-clear:${identity}`;
  let plan = null, keepBusy = false, pending = null, storageBlocked = false, inspection = null;
  const sameRequest = (left, right) => Boolean(left && right &&
    left.project_identity === identity && right.project_identity === identity &&
    left.request?.operation_id === right.request?.operation_id &&
    canonical(left.request) === canonical(right.request));
  const readPending = () => {
    const previous = pending;
    try {
      const raw = localStorage.getItem(key);
      pending = raw ? JSON.parse(raw) : null;
      if (pending && (pending.project_identity !== identity || !pending.request?.operation_id ||
          pending.request.input?.project_id !== app.info.project_id ||
          pending.request.input?.scope !== 'current_project' || !pending.request.plan_id || !pending.request.manifest_digest)) {
        throw new Error('unverifiable retained request');
      }
      if ((previous || pending) && !sameRequest(previous, pending)) { plan = null; inspection = null; }
      storageBlocked = false;
      if (pending && !sameRequest(previous, pending)) notice.textContent = '清理结果待核实。原操作编号和请求已保留，请核实并重试原清理。';
    } catch {
      pending = null; inspection = null; storageBlocked = true;
      notice.textContent = '本机清理恢复记录暂不可核实。原记录保留，请先查看清理备份；未发起新清理。';
    }
  };
  const refresh = () => {
    planButton.disabled = keepBusy || storageBlocked || Boolean(pending);
    commit.disabled = keepBusy || storageBlocked || (!pending && (!plan || !plan.items.length));
    commit.textContent = pending ? '核实并重试原清理' : '确认清理并保留备份';
    inspectButton.hidden = endButton.hidden = !pending;
    inspectButton.disabled = keepBusy || storageBlocked || !pending;
    endButton.disabled = keepBusy || storageBlocked || !pending || !inspection ||
      canonical(inspection.request) !== canonical(pending.request) ||
      !['no_execution_evidence', 'incomplete'].includes(inspection.status);
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
    } catch (error) { plan = null; notice.textContent = clearError(error); }
    finally { keepBusy = false; readPending(); refresh(); }
  });
  // Only local read/compare/write runs under the origin-wide project lock.
  // Never hold it while waiting for the server: another tab must be able to recover.
  const lockedPending = async (change) => {
    if (!navigator.locks?.request) throw new Error('无法安全保留清理恢复记录，未发起新的清理；请在支持本机恢复锁的浏览器中核实。');
    return navigator.locks.request(key, () => {
      readPending();
      if (storageBlocked) throw new Error('本机清理恢复记录暂不可核实，原记录保留。');
      return change();
    });
  };
  const requireOwner = (sent) => {
    if (!sameRequest(pending, sent)) throw new Error('恢复记录已属于其他操作，请核实当前保留的请求。');
  };
  const releasePending = (sent) => lockedPending(() => {
    requireOwner(sent);
    localStorage.removeItem(key);
    pending = null; plan = null; inspection = null; scopeView.replaceChildren();
  });
  const finish = () => { keepBusy = false; readPending(); refresh(); };
  const commit = button('确认清理并保留备份', async () => {
    if (keepBusy) return;
    readPending();
    if (storageBlocked || (!pending && !plan)) { refresh(); return; }
    const recovering = Boolean(pending), expected = pending, planned = plan;
    let sent = null;
    keepBusy = true; refresh();
    try {
      const current = await get('/api/project?light=1');
      if (current.project_identity !== identity) throw new Error('项目身份已改变，请重新打开原项目核实。');
      sent = await lockedPending(() => {
        if (recovering) requireOwner(expected);
        else {
          if (pending) throw new Error('本机已有待核实记录，请先处理原清理请求。');
          const next = {project_identity: identity, request: {operation_id: crypto.randomUUID(),
            input: {project_id: planned.project_id, scope: 'current_project', draft_ids: 'all', reading_preferences: true},
            plan_id: planned.plan_id, manifest_digest: planned.manifest_digest}};
          localStorage.setItem(key, JSON.stringify(next)); pending = next;
        }
        return JSON.parse(JSON.stringify(pending));
      });
      const result = await post('/api/ui-state/commit-clear', sent.request);
      if (result.status !== 'cleared' || result.operation_id !== sent.request.operation_id ||
          result.plan_id !== sent.request.plan_id || result.manifest_digest !== sent.request.manifest_digest ||
          !Array.isArray(result.cleared)) throw new Error('清理回执无法与原请求对应。');
      await releasePending(sent);
      notice.replaceChildren(el('p', {}, `已清理 ${result.cleared.length} 项，恢复备份已保留；任务与候选未受影响。`), personalBackupButton(app));
    } catch (error) {
      // An explicit first-attempt CAS refusal resolves only the request sent here.
      if (sent && !recovering && error.code === 'local_state_conflict' && error.field === 'manifest_digest') {
        try {
          await releasePending(sent);
          notice.textContent = '个人状态已变化，本次清理被拒绝；请重新生成计划。';
        } catch (releaseError) { notice.textContent = clearError(releaseError); }
      } else notice.textContent = clearError(error) + (pending ? ' 清理结果待核实，原请求保留。' : '');
    } finally { finish(); }
  }, true, {disabled: true});
  const validateBinding = async (result, sent) => {
    if (result.project_identity !== identity || canonical(result.request) !== canonical(sent.request) ||
        result.request_digest !== await digest(sent.request)) throw new Error('核实结果无法与原清理请求对应。');
  };
  const showEnded = async (sent) => {
    await releasePending(sent);
    notice.replaceChildren(el('p', {}, '旧清理操作已结束。结果与恢复记录已保留；请生成新计划并重新确认范围。结束操作没有继续删除或恢复草稿。'),
      personalBackupButton(app));
  };
  const inspectButton = button('核实原清理结果', async () => {
    if (keepBusy) return;
    readPending();
    if (!pending || storageBlocked) { refresh(); return; }
    const sent = JSON.parse(JSON.stringify(pending));
    inspection = null; keepBusy = true; refresh();
    try {
      const result = await post('/api/ui-state/inspect-clear', sent.request);
      await validateBinding(result, sent);
      if (result.status === 'cleared') {
        const receipt = result.receipt;
        if (!receipt || receipt.operation_id !== sent.request.operation_id || receipt.plan_id !== sent.request.plan_id ||
            receipt.manifest_digest !== sent.request.manifest_digest || !Array.isArray(receipt.cleared)) {
          throw new Error('成功回执无法与原清理请求对应。');
        }
        await releasePending(sent);
        notice.replaceChildren(el('p', {}, `已清理 ${receipt.cleared.length} 项；本次核实没有再次清理。${result.backup?.available ? '原备份可查看。' : '原备份暂不可用，请保留回执。'}`), personalBackupButton(app));
      } else if (result.status === 'ended') await showEnded(sent);
      else if (['no_execution_evidence', 'incomplete', 'unverifiable'].includes(result.status) &&
               /^[a-f0-9]{64}$/.test(result.inspection_digest)) {
        await lockedPending(() => { requireOwner(sent); inspection = result; });
        if (result.status === 'no_execution_evidence') notice.textContent =
          (result.backup?.related_operation ? '同范围备份属于另一清理操作，原备份保留；它不能证明本次请求已完成。' : '') +
          '未发现执行证据，不能据此认定旧请求从未执行。可明确结束旧操作，再生成新计划。';
        if (result.status === 'incomplete') notice.textContent = `发现清理中断证据，已核实备份中 ${result.backup?.count || 0} 项记录。结束旧操作会保留备份，不继续删除或自动恢复。`;
        if (result.status === 'unverifiable') notice.textContent = '原清理证据暂无法核实。原请求保留，请检查本机恢复记录后重新核实。';
      } else throw new Error('清理核实状态无法识别，原请求保留。');
    } catch (error) { inspection = null; notice.textContent = clearError(error) + ' 清理结果待核实，原请求保留。'; }
    finally { finish(); }
  });
  const endButton = button('结束旧操作并重新计划', async () => {
    if (keepBusy) return;
    readPending();
    if (storageBlocked || !pending || !inspection || canonical(inspection.request) !== canonical(pending.request) ||
        !['no_execution_evidence', 'incomplete'].includes(inspection.status)) { refresh(); return; }
    const expected = JSON.parse(JSON.stringify(pending)), confirmation = inspection.inspection_digest;
    keepBusy = true; refresh();
    try {
      const sent = await lockedPending(() => {
        requireOwner(expected);
        const next = {...pending, end_inspection_digest: confirmation};
        localStorage.setItem(key, JSON.stringify(next)); pending = next;
        return JSON.parse(JSON.stringify(next));
      });
      const result = await post('/api/ui-state/end-clear', {...sent.request, inspection_digest: sent.end_inspection_digest});
      await validateBinding(result, sent);
      if (result.status !== 'ended' || result.inspection_digest !== sent.end_inspection_digest) throw new Error('结束回执无法对应原核实结果。');
      await showEnded(sent);
    } catch (error) { inspection = null; notice.textContent = clearError(error) + ' 清理结果待核实，原请求保留，请重新核实。'; }
    finally { finish(); }
  });
  const body = el('div', {class: 'panel-body stack'}, el('p', {class: 'muted'}, '只清理本项目的个人草稿与阅读设置；先出只读计划，确认后才清理，并保留恢复备份。项目内容、任务与调用记录不受影响。'),
      el('div', {class: 'row wrap'}, planButton, commit, inspectButton, endButton, personalBackupButton(app)), scopeView, notice);
  readPending(); refresh();
  if (document.documentElement.dataset.workbenchUi === 'studio') {
    return button('个人状态与恢复', () => { readPending(); refresh(); modal('个人状态与恢复', body); });
  }
  return el('details', {'data-container':'section', class: 'panel personal-clear'}, el('summary', {}, '清理本机个人状态（草稿与阅读设置）'), body);
}
