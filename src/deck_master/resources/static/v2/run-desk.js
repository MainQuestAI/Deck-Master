import {cancelRecovery} from './run-recovery.js';
import {taskHandoff} from './change-handoff.js';
import {get, post, readableError, revisionQuery, fileURL} from './api.js';
import {el, button, empty, version, modal, loading, errorNote, disabledReason} from './dom.js';

const names = {style_analyze:'分析截图规范', reconstruct:'制作可编辑稿', compile:'编译整稿', check:'工程检查', compose: '整理内容', blueprint: '制作原图', svg: '制作 SVG', render: '渲染预览', repair: '局部修改', review: '检查', export: '准备文件'};
const statuses = {queued: '等待执行', awaiting_host: '待接手', running: '已记录处理中', completed: '结果已记录', failed: '执行失败', cancelled: '已取消', superseded: '由新任务接续', unreadable: '记录无法读取'};
const actions = {handoff: '交给 Deck Master Agent', verify_unknown_call: '核实未知调用', verify_execution: '核实原执行', inspect_failure: '查看失败原因', replan: '按当前依据重新计划', compare_candidates: '候选待决定', review_results: '结果待阅读'};
const seenKey = task => task.reading_key;
const clock = value => value ? new Date(value).toLocaleString('zh-CN', {hour12: false}) : '未记录';

// B05（INTERFACES 个人状态清理）：只读计划先行，确认后按同 etag 清理；
// 备份可下载；任务/候选/调用事实不在范围（服务端强制，UI 如实转述）。
function personalClearPanel(app) {
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
      notice.replaceChildren(el('p', {}, `已清理 ${result.cleared.length} 项，恢复备份已保留；任务与候选未受影响。`), el('details', {}, el('summary', {}, '恢复备份位置'), el('code', {}, result.backup_ref)));
      scopeView.replaceChildren();
      plan = null;
    } catch (error) { notice.textContent = readableError(error) + ' 未清理任何对象。'; }
    finally { keepBusy = false; planButton.disabled = false; }
  }, true, {disabled: true});
  return el('details', {class: 'panel personal-clear'}, el('summary', {}, '清理本机个人状态（草稿与阅读设置）'),
    el('div', {class: 'panel-body stack'}, el('p', {class: 'muted'}, '只清理本项目的个人草稿与阅读设置；先出只读计划，确认后才清理，并保留恢复备份。项目内容、任务与调用记录不受影响。'),
      el('div', {class: 'row wrap'}, planButton, commit), scopeView, notice));
}

export function runDesk(app, data) {
  const recovery = cancelRecovery(app);
  const root = el('section', {class: 'panel run-desk', 'aria-label': '运行记录'});
  const rows = el('div', {class: 'run-rows stack'}), pager = el('div', {class: 'row wrap run-pagination'});
  const notice = el('div', {class: 'muted run-notice'});
  const detail = el('div', {class: 'run-detail stack'});
  let handoff = null;
  const group = el('select', {'aria-label': '按修改组筛选'}), status = el('select', {'aria-label': '按执行状态筛选'}, el('option', {value: ''}, '所有执行状态'),
    Object.entries(statuses).map(([key, label]) => el('option', {value: key}, label)));
  const attention = el('input', {type: 'checkbox', 'aria-label': '只看需我处理'});
  let page = data.runPage, selected = data.runDetail, disposed = false, serial = 0, busy = false, loaded = false;
  let state = {offset: 0, group: '', status: '', attention: false};
  let reading={seen:[],etag:null},readingUnavailable=false;const readingSupported=app.health.ui_capabilities?.includes('result_reading.v1');
  let pinned = app.route.revision, live = !app.historical, pendingRead = null, choiceMade = false, readingBlocked = false, recoveryState = null;
  const restart = () => { choiceMade = true; read({state:{...(recoveryState||state),offset:0},live:true,refreshReading:true,persist:true}); };
  const refreshButton = button('核实最新执行状态', restart);
  root.append(el('div', {class: 'panel-head'}, el('h2', {}, '运行记录'), refreshButton),
    el('div', {class: 'panel-body stack'}, el('p', {class: 'muted'}, '当前执行状态与顶栏的页面阅读版本分开。正常处理中无需你操作；查看结果不代表采用或质量通过。'),
      el('div', {class: 'row wrap run-filters'}, group, status, el('label', {}, attention, '只看需我处理')), notice, detail, rows, pager),
    personalClearPanel(app));
  function persist() {
    const editor = app.editor;
    if (!editor || editor.readonly || editor.disposed || !editor.draft) return;
    editor.draft.content.run_desk = {...editor.draft.content.run_desk,...structuredClone(state),reading_etag:reading.etag}; editor.changed();
  }
  const pageLabels = new Map(app.summary.pages.map((page, n) => [page.page_id, `第 ${n + 1} 页 · ${page.title || '未命名页面'}`]));
  const scopeLabel = task => task.scope_pages?.length ? task.scope_pages.map(id => pageLabels.get(id) || '页面').join('、') : '整个项目';
  const todo = task => (task.human_actions || []).filter(action => action !== 'review_results' || !reading.seen.includes(seenKey(task)));
  const errorBox = error => errorNote({what: error.message || error.cause || '对象无法读取',
    kept: '已显示的运行记录仍保留。', next: `对象：${error.object || error.field || '运行记录'} · ${error.next_action || '核实原任务后重试读取'}`,
    ref: error.docs_ref || 'docs/agent-recovery-playbook.md#run-desk-recovery'});
  function render() {
    group.replaceChildren(el('option', {value: ''}, '所有修改组'), ...page.groups.filter(item => item.change_id).map(item =>
      el('option', {value: item.change_id}, `修改组 ${page.groups.indexOf(item) + 1} · ${item.completed_count}/${item.total_count} 项已返回${item.page_ids?.length ? ` · ${item.page_ids.length} 页` : ''} · ${item.change_id.slice(-6)}`)));
    if (state.group && !page.groups.some(item => item.change_id === state.group)) state.group = '';
    group.value = state.group; status.value = state.status; attention.checked = state.attention;
    notice.textContent = `${live ? '当前执行状态' : '固定执行记录'} · 共 ${page.pagination.total} 项`;
    const tasks = page.tasks.filter(task => !state.attention || todo(task).length);
    // UX-05b：每条运行记录默认回答「做什么、对哪些页、现在怎样」，要求原文
    // 折叠在详情里，列表本身不再只有任务类型和内部时间。
    rows.replaceChildren(...tasks.map(task => el('article', {class: 'run-task stack', 'data-task-id': task.task_id},
      el('div', {class: 'row wrap'}, el('strong', {}, names[task.kind] || '制作任务'), el('span', {class: 'status'}, statuses[task.status] || task.status)),
      el('p', {class: 'run-requirement'}, `要求：${(task.instruction || '').trim() || '未记录制作要求'}`),
      el('p', {}, `目标：${scopeLabel(task)}`),
      el('p', {class: 'muted'}, `接手时间：${clock(task.execution_started_at)}`),
      task.human_actions?.includes('verify_execution') && el('p', {class: 'field-error'}, '需要核实原执行。不会自动重试或取消；未确认取消前请勿重复派发。'),
      todo(task).length > 0 && el('p', {class: 'run-actions'}, todo(task).map(key => actions[key] || key).join(' · ')),
      task.error && errorBox(typeof task.error === 'object' ? task.error : {message: task.error}),
      task.task_id && button('查看这项任务', () => app.go({task_id: task.task_id, revision: page.revision_id})))));
    if (!tasks.length) rows.append(empty(state.attention ? '本页没有需要你处理的记录' : '没有匹配的运行记录',
      '可继续阅读内容与制作状态。查看其它记录不会触发执行。', el('div', {class: 'row wrap'}, button('阅读内容', () => app.go({surface: 'content'})), button('查看整稿', () => app.go({surface: 'gallery'})))));
    const move = offset => { choiceMade = true; read({state:{offset},live:false,pinned:page.revision_id,persist:true}); };
    pager.replaceChildren(disabledReason(button('上一页任务', () => move(Math.max(0, state.offset - 30)), false, {disabled: state.offset === 0}), state.offset === 0 ? '已在第一页。' : '', {visible: false}),
      el('span', {}, `第 ${Math.floor(state.offset / 30) + 1} 页 · 每页最多 30 项`),
      disabledReason(button('下一页任务', () => move(page.pagination.next_offset), false, {disabled: page.pagination.next_offset === null}), page.pagination.next_offset === null ? '已是最后一页。' : '', {visible: false}));
    rows.hidden = Boolean(selected); pager.hidden = Boolean(selected);
    if (selected) renderDetail();
    controls();
  }
  function controls() {
    for(const input of [group,status,attention,refreshButton])input.disabled=busy;
    const buttons=pager.querySelectorAll('button');
    if(buttons[0])buttons[0].disabled=!loaded||busy||readingBlocked||state.offset===0;
    if(buttons[1])buttons[1].disabled=!loaded||busy||readingBlocked||page.pagination.next_offset===null;
  }
  async function showEvidence(kind, id, revision) {
    try {
      const value = await get(`/api/${kind}/${encodeURIComponent(id)}` + revisionQuery(revision));
      if (!disposed) modal('调用依据与结果记录', el('pre', {class: 'run-evidence'}, JSON.stringify(value, null, 2)));
    } catch (error) { if (!disposed) detail.append(errorBox({...error.details, message: readableError(error)})); }
  }
  function renderDetail() {
    const task = selected.task, revision = selected.revision_id;
    handoff?.dispose(); handoff = taskHandoff(app, task, page.groups);
    recovery.observe(task);
    const resultLinks = (task.result_refs || []).map((ref, index) => {
      const url = fileURL(ref);
      return url ? el('a', {href: url, target: '_blank', rel: 'noopener'}, `查看结果 ${index + 1}`) : el('span', {}, '结果引用无法读取');
    });
    detail.replaceChildren(el('div', {class: 'stack'}, el('h3', {}, `${names[task.kind] || '制作任务'} · ${statuses[task.status] || task.status}`),
      el('p', {}, scopeLabel(task)),
      handoff?.node,
      el('details', {}, el('summary',{},'制作要求与执行身份'), el('p',{},task.instruction),el('p',{class:'muted'},`任务 ${task.task_id} · ${version(revision)}`)),
      el('p', {}, `真实接手时间：${clock(task.execution_started_at)}${task.execution_started_at ? '' : '，不会用最后更新时间代替'}`),
      el('details',{},el('summary',{},'执行记录'),el('p',{class:'execution-reference'},task.execution_ref ? `执行标识：${task.execution_ref}` : '尚无接手记录')),
      // 快捷阅读去任务实际产物所在层：SVG 族任务不再落到原图（N06）；
      // render 任务去 PPT 层（AC16 快捷入口与名称相符）。
      (() => { const shortcutLayer = {compose: 'content', blueprint: 'original_image', svg: 'svg', reconstruct: 'svg', repair: 'svg', render: 'ppt'}[task.kind] || 'original_image';
        const layerName = {content: '逐页稿', original_image: '原图', svg: 'SVG', ppt: 'PPT'}[shortcutLayer] || '原图';
        return el('div', {class: 'row wrap'}, (task.scope_pages || []).map(id => button(`阅读 ${pageLabels.get(id) || '对应页面'} · ${layerName}`, () => app.go({surface: 'page', page_id: id, layer: shortcutLayer, revision})))); })(),
      el('p', {}, `已记录结果 ${task.result_refs.length} 项 · 候选 ${task.candidate_refs.length} 项 · 未知调用 ${task.call_counts.unknown || 0} 次`),
      (task.call_counts.unknown || 0) > 0 && el('p', {class: 'field-error'}, '未知调用不等于未执行。请核实原调用；本工作台不会重新分配额度或自动重试。'),
      recovery.pending.has(task.task_id) && el('p', {class: 'field-error'}, '取消结果待核实，未安排替代任务。'),
      el('div', {class: 'row wrap'}, button('核实原任务', async () => {
        try { selected = await recovery.verify(task.task_id); if (!disposed) renderDetail(); }
        catch (error) { if (!disposed) detail.append(errorBox({...error.details, message: readableError(error)})); }
      }), ['queued', 'awaiting_host', 'running'].includes(task.status) && disabledReason(button(recovery.pending.has(task.task_id) ? '再次请求取消原任务' : '取消原任务', async () => {
        try { await recovery.cancel(task, recovery.pending.has(task.task_id)); if (!disposed) { selected = await recovery.verify(task.task_id); renderDetail(); } }
        catch (error) { if (!disposed) detail.append(errorBox({...error.details, message: '取消结果请核实。' + readableError(error)})); }
      }, false, {disabled: app.readonly || recovery.sending.has(task.task_id)}),
        app.readonly ? '当前视图只读，不能取消任务。' : recovery.sending.has(task.task_id) ? '取消请求已发送，等待核实结果。' : '')),
      el('div', {class: 'stack'}, resultLinks),
      task.result_refs.length > 0 && !task.candidate_refs.length && button(reading.seen.includes(seenKey(task)) ? '已标记读过这些结果' : readingSupported?'标记这些结果已读':'当前核心不支持跨工作面已读', async () => {
        try{await post('/api/result-reading',{project_identity:app.info.project_identity,revision,task_id:task.task_id,result_key:task.reading_key,expected_etag:reading.etag});await read({state:{offset:0},refreshReading:true,persist:true});app.summaryPoll?.refresh();}
        catch(error){notice.textContent=readableError(error)+' 请重新读取结果后标记。';await read();}
      }, false, {disabled: app.readonly || readingBlocked || !readingSupported || !reading.etag || reading.seen.includes(seenKey(task))}),
      el('details', {}, el('summary', {}, '请求与实际调用记录'),
        el('div', {class: 'stack'}, selected.links.generation_requests.map(link => button(link.request_id, () => showEvidence('requests', link.request_id, revision))),
          selected.links.generation_attempts.map(link => button(link.attempt_id, () => showEvidence('attempts', link.attempt_id, revision)))),
        el('pre', {class: 'run-evidence'}, JSON.stringify(selected.call_allowances, null, 2))),
      (selected.errors || []).map(errorBox), button('查看全部任务', () => app.go({task_id: null}))));
  }
  async function read(options={}) {
    if (disposed) return;
    if (busy) { if(Object.keys(options).length||pendingRead===null)pendingRead=options; return; }
    busy = true; const token = ++serial;
    const nextState={...state,...options.state},nextLive=options.live??live,nextPinned=options.pinned??pinned;
    const savedReading=Object.hasOwn(options,'readingEtag');
    const fixedReading=savedReading||(!nextLive&&loaded&&!options.refreshReading);
    controls();
    if (loaded) notice.replaceChildren(loading(nextLive ? '正在读取当前执行状态…' : '正在读取固定执行记录…'));
    const query = new URLSearchParams({limit: '30', offset: String(nextState.offset)});
    if (!nextLive) query.set('revision', nextPinned);
    if (nextState.group) query.set('change_id', nextState.group);
    if (nextState.status) query.set('status', nextState.status);
    if (nextState.attention) query.set('attention', '1');
    let readingRequest=false;
    try {
      let nextReading=reading;let readingWarning=fixedReading&&readingUnavailable;
      if(readingSupported&&(!fixedReading||savedReading)){
        if(savedReading&&options.readingEtag===null)nextReading={seen:[],etag:null};
        else {
          readingRequest=true;
          try{nextReading=await get('/api/result-reading');}
          catch(error){if(fixedReading||error.status===409)throw error;nextReading={seen:[],etag:null};readingWarning=true;}
          readingRequest=false;
        }
      }
      const etag=savedReading?options.readingEtag:nextReading.etag;
      if(readingSupported&&etag){query.set('personal','1');query.set('reading_etag',etag);}
      const value = await get('/api/tasks?' + query);
      const nextDetail = app.route.task_id ? await get('/api/tasks/' + encodeURIComponent(app.route.task_id) + revisionQuery(nextLive ? null : nextPinned)) : null;
      if (disposed || token !== serial) return;
      // Commit the page, its cursor and its reading snapshot together. Failed
      // pagination must leave both the visible rows and their old offset intact.
      state={...nextState,revision:value.revision_id};live=nextLive;pinned=nextPinned;
      reading=nextReading;readingUnavailable=readingWarning;page = value; selected = nextDetail; loaded = true;readingBlocked=false;recoveryState=null;render();
      if(options.persist)persist();
      if(readingWarning)notice.append(el('p',{class:'field-error'},'个人已读记录暂不可用，任务按未过滤状态展示；损伤文件保留，标记已读暂停。'));
      if(options.notice)notice.append(el('p',{class:'muted'},options.notice));
      return true;
    } catch (error) {
      if (!disposed) {
        const conflict=error.status===409&&error.field==='reading_etag';
        const unavailable=fixedReading&&(readingRequest||error.code==='local_state_invalid');
        if(fixedReading||conflict){live=false;pinned=page.revision_id;pendingRead=null;}
        group.value=state.group;status.value=state.status;attention.checked=state.attention;
        if(conflict||unavailable){
          readingBlocked=true;recoveryState={...nextState};
          notice.replaceChildren(el('p',{class:'field-error'},conflict
            ?'已读记录已变化，当前页保留；请重新读取第一页后继续翻页。'
            :'个人已读记录暂不可用，当前页保留；请重新读取第一页后继续。'),button('重新读取第一页',restart));
          if(selected)renderDetail();
        }else notice.replaceChildren(errorBox({...error.details,message:readableError(error)}),button('重试读取',()=>read(options)));
      }
      return false;
    } finally { busy = false;controls();if(pendingRead&&!disposed){const next=pendingRead;pendingRead=null;read(next);} }
  }
  for (const input of [group, status, attention]) input.addEventListener('change', () => {
    choiceMade = true;read({state:{group:group.value,status:status.value,attention:attention.checked,offset:0},refreshReading:true,persist:true});
  });
  const sync = () => { if (live && !document.hidden) read(); };
  app.root.addEventListener('summary-refreshed', sync);
  function hydrate() {
    const editor = app.editor;
    if (!editor) { read(); return; }
    editor.ready.then(() => {
      if (disposed || editor !== app.editor) return;
      recovery.hydrate(editor);
      const saved = editor.draft.content.run_desk;
      let options={};
      if (!choiceMade && saved && typeof saved === 'object') {
        const restored = {offset: Number.isSafeInteger(saved.offset) && saved.offset >= 0 ? saved.offset : 0,
          group: typeof saved.group === 'string' ? saved.group : '', status: Object.hasOwn(statuses, saved.status) ? saved.status : '',
          attention: saved.attention === true};
        options={state:restored};
        if(restored.offset){
          if(!readingSupported||typeof saved.reading_etag==='string'&&/^[a-f0-9]{64}$/.test(saved.reading_etag))
            Object.assign(options,{live:false,pinned:typeof saved.revision==='string'?saved.revision:app.route.revision,readingEtag:readingSupported?saved.reading_etag:null});
          else {restored.offset=0;options.notice='原分页的已读版本无法核实，已从第一页重新读取；筛选保留。';}
        }
      }
      if(readingSupported&&saved?.seen?.length){const migrate=button('核实并导入旧草稿的已读记录',async()=>{try{await editor.save();const current=await get('/api/result-reading');const result=await post('/api/result-reading/import-legacy',{draft_id:editor.draft.draft_id,project_identity:app.info.project_identity,expected_etag:current.etag});if(await read({state:{offset:0},refreshReading:true,persist:true}))notice.textContent=`已核实导入 ${result.verified_count} 项旧记录，原草稿保留。`;migrate.remove();app.summaryPoll?.refresh();}catch(error){notice.textContent=readableError(error);}});root.append(migrate);}
      read(options);
    });
  }
  const onCancel = () => queueMicrotask(() => { if (!disposed && selected) renderDetail(); });
  app.root.addEventListener('cancel-state-changed', onCancel);
  app.root.addEventListener('draft-editor-replaced', hydrate);
  app.disposables.push(() => { disposed = true; handoff?.dispose(); serial++; app.root.removeEventListener('cancel-state-changed', onCancel); app.root.removeEventListener('summary-refreshed', sync); app.root.removeEventListener('draft-editor-replaced', hydrate); });
  render(); hydrate(); return root;
}
