import {get, post, readableError, ApiError} from './api.js';
import {el, button, modal, version, field, downloadJSON} from './dom.js';
import {pageText} from './page-text.js';
import {diffView} from './text-diff.js';

const intents = {full_deck: '完整方案', content_only: '内容工作', design_trial: '设计试作', review_only: '只读审阅', edit: '局部修改'};
const contentIntents = {plan_only: '论证与大纲', write_only: '上屏稿', speech_only: '口播稿', content_full: '完整内容'};
const layerLabels = {narrative: '论证主线', plan: '页面大纲', page_copy: '上屏稿', speech: '口播稿', design: '设计要求', blueprint: '原图', svg: 'SVG', review: '审阅', output: '整稿文件'};
const states = {in_progress: '内容进行中', awaiting_decision: '内容待决定', needs_reviewer: '内容待审阅', completed: '本次内容已完成'};
const roles = {user: '用户', content: '内容制作', reviewer: '审阅者', host: '制作工具', design: '设计制作', owner: '项目负责人', caller: '发起人', runtime: '工作台'};
const topics = {direction:'论证方向',manuscript:'确认稿',speech:'口播要求',style:'风格要求',tradeoff:'取舍',delivery_acceptance:'交付接受',policy:'工作政策'};
const dispositions = {accepted:'已接受',rejected:'已拒绝',deferred:'暂缓',active:'当前记录',withdrawn:'已撤回',superseded:'已由新记录接续'};
function nextAction(value, codes=[]) {
  if(value==='return_requested_content')return '阅读约定内容。本次内容工作已正常结束。';
  if(codes.includes('needs_reviewer'))return '安排符合要求的审阅者，继续阅读保留的稿件与报告。';
  if(codes.includes('decision_needed'))return '核对实际稿件与取舍后，记录对应范围的明确决定。';
  if(codes.includes('request_paused'))return '明确恢复原请求，或保留暂停并取消未开始的制作。';
  if(codes.includes('authorization_revoked'))return '保留撤回事实；后续制作须有新的明确指令。';
  return '查看具体缺口与依据，再由对应责任继续处理。';
}
export const projectAPI = app => '/api/projects/' + encodeURIComponent(app.info.project_id);
const details = (title, value) => el('details', {}, el('summary', {}, title), el('pre', {class: 'evidence-json'}, JSON.stringify(value, null, 2)));
const resultOf = value => value?.schema_version === 'collaboration_response.v1' ? value.result : value;
export function scopeView(app, scope) {
  if (!scope) return el('p', {class: 'muted'}, '尚未记录本次范围。空页集不会表示全部页面。');
  const pages = scope.page_ids || [];
  const names = pages.map(id => {
    const index = app.summary.pages.findIndex(page => page.page_id === id);
    return index < 0 ? '已固定页面（见详情）' : `第 ${index + 1} 页 · ${app.summary.pages[index].title || '未命名页面'}`;
  });
  return el('div', {class: 'collaboration-scope stack'},
    el('p', {}, `${scope.subject === 'external_artifact' ? '外部稿件' : '项目内容'} · ${pages.length} 页 · ${(scope.layers || []).map(key => layerLabels[key] || key).join('、') || '无写入层'}`),
    names.length > 0 && el('ul', {}, names.map(name => el('li', {}, name))),
    el('p', {class: 'muted'}, `${scope.allow_page_membership_change ? '允许增减页面' : '保持页面集合'} · ${scope.allow_page_order_change ? '允许调整页序' : '保持页序'} · ${ {exploratory:'探索', review:'审阅', working:'工作稿', delivery:'正式交付'}[scope.purpose] || scope.purpose}`));
}

export function admissionView(app, error) {
  const facts = error.details || {};
  const card = facts.decision_card_ref_or_projection || facts.decision_card;
  const report = error.result?.report || error.result?.readable_report || error.result;
  return el('div', {class: 'collaboration-admission stack', role: 'alert'},
    el('p', {class: 'field-error'}, readableError(error)),
    el('p', {}, '当前稿件、可读报告和本次输入均保留。'),
    (facts.effective_scope||facts.scope) && scopeView(app, facts.effective_scope||facts.scope),
    facts.responsible_role && el('p', {}, '下一责任：' + (roles[facts.responsible_role] || facts.responsible_role)),
    facts.next_action && el('p', {}, '下一步：' + nextAction(facts.next_action,facts.reason_codes||[error.code])),
    card && details('决定范围与影响', card),
    report && details('保留的可读报告', report),
    details('错误依据与范围', {path: error.path || error.field, ...facts}));
}

// These are editable instruction copies, never a cached grant or readiness
// verdict. Each window keeps its own buffer; recovery copies remain selectable.
function instructionBuffer(app, action) {
  const prefix = `deck-master:v3:control-draft:${app.info.project_identity}:${action}:`;
  const key = prefix + crypto.randomUUID();
  const text = field('本次明确要求（必填）', el('textarea', {rows: 4, required: true, autocomplete: 'off'}), '只记录这次指令。保存副本不会开始制作或授予权限。');
  const status = el('p', {class: 'muted', role: 'status'});
  const recovery = el('select', {'aria-label': '恢复本机的请求文字'}, el('option', {value: ''}, '选择保留的请求文字'));
  const copies = []; let currentPending = null;
  try {
    for (const entry of Object.keys(localStorage).filter(item => item.startsWith(prefix))) {
      const copy = JSON.parse(localStorage.getItem(entry));
      if (typeof copy.text === 'string') copies.push(copy);
    }
  } catch { status.textContent = '部分本机副本暂不可读。请保留输入并下载副本。'; }
  copies.forEach((copy, index) => recovery.append(el('option', {value: String(index)}, (copy.pending?'提交结果待核实 · ':'')+(copy.text.slice(0, 70) || '空白请求'))));
  const save = () => {
    try { localStorage.setItem(key, JSON.stringify({text: text.input.value,pending:currentPending})); status.textContent = currentPending?'原请求已保留在本机；提交结果待核实。':'请求文字副本已保留在本机；保存副本不会提交。'; return true; }
    catch { status.textContent = '本机保存未完成。请复制文字或下载副本后再关闭。'; return false; }
  };
  const buffer={input:text.input,save,setPending(value){currentPending=value;return save();},
    lock(value){text.input.readOnly=value;recovery.disabled=value;},onRestore:null};
  recovery.addEventListener('change', () => { if (recovery.value !== '') {
    const copy=copies[Number(recovery.value)];text.input.value=copy.text;currentPending=copy.pending||null;save();buffer.onRestore?.(copy);
  } });
  text.input.addEventListener('input', save);
  buffer.node=el('div', {class: 'stack'}, text.node, status, copies.length > 0 && recovery,
    button('下载请求文字', () => downloadJSON({instruction_text:text.input.value,pending:currentPending}, 'deck-master-request-draft.json')));
  return buffer;
}

function controlForm(app, {title, action, path, body, explanation, build, initial = ''}) {
  if (document.querySelector('#modal')?.open) return;
  const base_revision = app.info.control_revision_id || app.info.revision_id;
  const instruction = instructionBuffer(app, action); instruction.input.value = initial;
  const status = el('div', {role: 'status', class: 'stack'});
  const fields = el('fieldset', {class: 'collaboration-form-fields'}, body);
  const form = el('form', {class: 'stack'}, el('p', {}, explanation), fields, instruction.node, status);
  let pending = null, sending = false;
  const submit = button('确认' + title, () => form.requestSubmit(), true);
  const dialog = modal(title, form, [submit], {protectDraft: true});
  instruction.onRestore=copy=>{
    if(copy.pending&&copy.pending.path!==projectAPI(app)+path){
      pending=null;submit.hidden=true;
      status.replaceChildren(el('p',{class:'field-error'},'这份待核实请求属于另一个明确对象。原请求仍保留，请从对应对象核实；不会改成当前对象提交。'),details('保留的原请求',copy.pending));return;
    }
    pending=copy.pending?.payload||null;fields.disabled=Boolean(pending);instruction.lock(Boolean(pending));
    submit.hidden=false;
    submit.textContent=pending?'核实并重试原请求':'确认'+title;
    status.replaceChildren(...(pending?[el('p',{},'已恢复待核实的原请求。版本、范围、操作编号均保持原样，不按当前表单重新提交。'),details('已冻结的原请求',pending)]:[]));
  };
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (sending) return;
    if (!instruction.input.value.trim()) { instruction.input.reportValidity(); return; }
    sending = true; submit.disabled = true; fields.disabled = true; instruction.lock(true); instruction.save();
    try {
      // Unknown responses retry the exact operation and payload. A new head
      // never silently replaces the basis the user confirmed in this dialog.
      if (!pending) {
        const operation_id = crypto.randomUUID();
        const evidence = {kind: 'host_attested_instruction', text: instruction.input.value,
          source_locator: `studio:${action}:${operation_id}`};
        pending = {project_id: app.info.project_id, base_revision,
          operation_id, ...build(evidence)};
      }
      if(!instruction.setPending({path:projectAPI(app)+path,payload:pending}))throw new ApiError('原请求副本尚未保存，本次没有发送。请保留文字与恢复文件，恢复本机保存后重试。','local_buffer_failed',400);
      const response = await post(projectAPI(app) + path, pending);
      const result = resultOf(response);
      status.replaceChildren(el('p', {}, '请求已记录。当前阅读稿和比较保持固定，请重新读取当前状态。'), details('本次操作回执', response),
        button('重新读取当前状态', () => { dialog.close(); app.loadRoute({...app.route}); }));
      if(action==='request.start')status.append(button('读取下一工作单',()=>{dialog.close();continueWork(app);}));
      submit.hidden = true;
      instruction.setPending(null);
      app.root.dispatchEvent(new CustomEvent('business-state-changed'));
      return result;
    } catch (error) {
      status.replaceChildren(admissionView(app, error));
      const unknown = !error.status || error.status >= 500 || error.code === 'invalid_response';
      if (unknown) {
        status.prepend(el('p', {}, '提交结果待核实。已冻结原请求，可按同一编号重试；后写文字不会覆盖原请求。'));
        submit.textContent = '核实并重试原请求';
      } else {
        pending = null; instruction.setPending(null); fields.disabled = false; instruction.lock(false);
        if (error.status === 409) {
          submit.hidden = true;
          status.append(button('保留输入并读取当前状态', () => { instruction.save(); dialog.close(); app.loadRoute({...app.route}); }));
        }
      }
    } finally { sending = false; submit.disabled = false; }
  });
}

export async function requestForm(app, {source = null, transition = null} = {}) {
  if (document.querySelector('#modal')?.open || app.requestSourceLoading) return;
  let reading=app.summary;
  if(source){
    const generation=app.generation;app.requestSourceLoading=true;
    try{
      reading=await get('/api/view/summary?'+new URLSearchParams({revision:source.revision_id}));
      if(generation!==app.generation)return;
      if(reading.revision_id!==source.revision_id||reading.project_id!==app.info.project_id)throw new Error('来源版本与当前项目不匹配，未替换为当前稿。');
    }catch(error){app.setNotice(readableError(error)+' 所选来源保持不变。');return;}
    finally{app.requestSourceLoading=false;}
  }
  const current = app.info.collaboration?.request;
  const intent = field('工作类型', el('select', {}, Object.entries(intents).map(([value, label]) => el('option', {value}, label))));
  intent.input.value = transition === 'edit_variant' ? 'edit' : 'content_only';
  const content = field('内容产物', el('select', {}, Object.entries(contentIntents).map(([value, label]) => el('option', {value}, label))));
  const purpose = field('本次用途', el('select', {}, [['working','工作稿'],['review','审阅'],['delivery','正式交付'],['exploratory','探索']].map(([value,label]) => el('option',{value},label))));
  const pageBoxes = reading.pages.map((page,index) => ({page_id: page.page_id, input: el('input',{type:'checkbox'}), label:`第 ${index + 1} 页 · ${page.title || '未命名页面'}`}));
  const layers = Object.entries(layerLabels).map(([value,label]) => ({value, input:el('input',{type:'checkbox',checked:['narrative','plan'].includes(value)}),label}));
  const membership = el('input',{type:'checkbox'}), order = el('input',{type:'checkbox'});
  const label = field('版本名称', el('input',{autocomplete:'off',placeholder:'例如：现场讲述版'}));
  const variantId = field('原指令声明的版本',el('select',{required:transition==='next_variant'},el('option',{value:''},'选择原指令声明的版本'),
    ...(current?.variant?.requested_variant_ids || []).map((value,index)=>el('option',{value},({live:'现场讲述版',read:'独立阅读版'})[value]||`原声明的版本 ${index+1}`))));
  label.input.required=transition==='next_variant';
  const body=el('div',{class:'stack'}, source && el('p',{},`固定来源 ${version(source.revision_id)}；当前控制 ${version(app.info.control_revision_id)}。提交后只在明确范围内继续，保留其它版本文件。`),
    intent.node,content.node,purpose.node,
    el('fieldset',{},el('legend',{},'明确选页（不选表示 0 页）'),pageBoxes.map(item=>el('label',{class:'inline-control'},item.input,item.label))),
    el('fieldset',{},el('legend',{},'允许内容层'),layers.map(item=>el('label',{class:'inline-control'},item.input,item.label))),
    el('label',{class:'inline-control'},membership,'允许增减页面'),el('label',{class:'inline-control'},order,'允许调整页序'),
    transition === 'next_variant' && [variantId.node,label.node]);
  intent.input.addEventListener('change',()=>{content.node.hidden=intent.input.value!=='content_only';});
  content.node.hidden=intent.input.value!=='content_only';
  controlForm(app,{title:transition==='next_variant'?'开始下一版本':transition==='edit_variant'?'按所选版本局改':'开始本次请求',action:'request.start',path:'/collaboration/requests',body,
    explanation:'核对工作类型、固定来源与精确范围。替换当前请求会结束其未完成制作；已有调用费用和稿件保留，不会自动复制额度。',
    build:instruction_evidence=>({request:{intent:intent.input.value,content_intent:intent.input.value==='content_only'?content.input.value:null,
      instruction_evidence,scope:{subject:'deck',page_ids:pageBoxes.filter(item=>item.input.checked).map(item=>item.page_id),page_manifest_ref:null,external_artifact_ref:null,
        layers:layers.filter(item=>item.input.checked).map(item=>item.value),allow_page_membership_change:membership.checked,allow_page_order_change:order.checked,purpose:purpose.input.value},
      ...(current&&!current.closed?{replace_request_id:current.request_id}:{}),
      ...(transition?{variant_transition:{kind:transition,source}}:{}),
      ...(transition==='next_variant'?{variant:{...current?.variant,variant_id:variantId.input.value,label:label.input.value}}:{})}})});
}

function stateDetails(app) {
  const state=app.info.collaboration, request=state?.request, completion=app.info.completion;
  const body=el('div',{class:'stack'},el('p',{},'下面显示当前控制事实。正在阅读的历史稿和固定比较不会随控制变化而替换。'),
    scopeView(app,request?.scope),
    request?.pause_reason&&el('p',{class:'field-error'},'暂停原因：'+request.pause_reason),
    completion&&el('section',{class:'stack'},el('h3',{},states[completion.state]||'内容状态未分类'),
      el('p',{},'约定产物：'+(contentIntents[completion.content_intent]||intents[completion.intent]||'见当前请求')),
      completion.responsible_role&&el('p',{},'下一责任：'+(roles[completion.responsible_role]||completion.responsible_role)),
      completion.next_action&&el('p',{},'下一步：'+nextAction(completion.next_action,completion.state==='needs_reviewer'?['needs_reviewer']:[])),details('产物、检查与缺口',completion)),
    el('section',{class:'stack'},el('h3',{},'决定与后续影响'),(state?.decisions||[]).length?(state.decisions.map(decision=>el('article',{class:'collaboration-record'},
      el('strong',{},topics[decision.topic]||'决定'),el('p',{},[dispositions[decision.disposition],dispositions[decision.status]].filter(Boolean).join(' · ')||'状态未记录'),
      el('p',{},typeof decision.value==='string'?decision.value:decision.rationale||decision.reason||'查看具体范围与依据'),scopeView(app,decision.scope),details('决定依据与影响',decision)))):el('p',{class:'muted'},'尚未记录可用决定；旧文本不会自动变成已确认。')),
    el('section',{class:'stack'},el('h3',{},'授权范围与撤回'),(state?.authorizations||[]).map(auth=>el('article',{class:'collaboration-record'},
      el('strong',{},auth.status==='revoked'?'授权已撤回':'授权记录'),scopeView(app,auth.scope),
      el('p',{},`调用上限 ${auth.max_external_calls??'未记录'} · 候选上限 ${auth.max_candidate_count??'未记录'}`),details('授权动作、依据与额度',auth),
      auth.status!=='revoked'&&button('撤回此授权',()=>{
        document.querySelector('#modal').close();
        controlForm(app,{title:'撤回此授权',action:'revoke',path:'/collaboration/authorizations/'+encodeURIComponent(auth.authorization_id)+'/revoke',
          body:scopeView(app,auth.scope),explanation:'撤回后停止该授权及其下级的后续采用和制作。已发生调用与费用保留；其它授权不能接管原任务。',build:instruction_evidence=>({evidence:instruction_evidence,reason:instruction_evidence.text})});
      },false,{disabled:Boolean(app.info.sample?.readonly)})))),
    controlRecovery(app),requestControls(app),
    !app.info.sample?.readonly&&button('导入确认稿',()=>{document.querySelector('#modal').close();draftImportForm(app);}),
    app.health.ui_capabilities?.includes('external_review.v1')&&button('只读审阅稿件',()=>{document.querySelector('#modal').close();externalReviewForm(app);}),
    details('当前控制与请求身份',{control_revision_id:app.info.control_revision_id,reading_revision_id:app.route.revision,...state}));
  modal('本次工作与范围',body);
}

function migrationForm(app) {
  const migration=app.info.migration, plan=migration?.plan;
  if(!plan)return;
  controlForm(app,{title:'升级项目控制记录',action:'migration.apply',path:'/collaboration/migration',
    explanation:'升级保留原稿、材料和调用费用；旧任务停止新制作。旧意见不会自动成为已确认决定，升级本身不授予制作权限。',
    body:el('div',{class:'stack'},el('p',{},`保留 ${plan.counts?.pages??'未知'} 页，停止 ${plan.counts?.runnable_tasks??'未知'} 项旧待办或运行任务。未知调用 ${plan.unknown_calls??'未知'}。`),details('逐项升级影响',plan)),
    build:instruction_evidence=>({plan_digest:migration.plan_digest,instruction_evidence})});
}

export function collaborationBanner(app) {
  if(!app.info.collaboration)return null;
  const state=app.info.collaboration,request=state.request,completion=app.info.completion;
  const revoked=(state.authorizations||[]).some(auth=>auth.status==='revoked');
  const label=!state.migrated?'需要升级控制记录':request?.paused?'本次请求已暂停':request?.closed?'本次请求已结束':completion?states[completion.state]||'本次内容状态待核实':request?'本次请求已记录':'尚无本次请求';
  return el('section',{class:'collaboration-control','aria-label':'本次工作状态'},
    button(label+(revoked?' · 存在已撤回授权':''),()=>stateDetails(app),false,{'aria-label':'查看本次工作与范围',title:'查看本次工作与范围 · '+label}));
}

function requestControls(app) {
  const state=app.info.collaboration,request=state?.request;
  const open=run=>{document.querySelector('#modal')?.close();run();};
  return el('div',{class:'row wrap'},
      !state?.migrated?button('查看升级影响',()=>open(()=>migrationForm(app)),false,{disabled:Boolean(app.info.sample?.readonly)}):
      [request&&!request.closed&&button(request.paused?'恢复本次请求':'暂停本次请求',()=>open(()=>controlForm(app,{
        title:request.paused?'恢复本次请求':'暂停本次请求',action:request.paused?'resume':'pause',path:'/collaboration/request/'+(request.paused?'resume':'pause'),
        body:scopeView(app,request.scope),explanation:request.paused?'恢复只继续原请求的有效范围，撤回、费用和缺口均保留。':'暂停将阻止新的制作与采用；读取、取消和已发生调用结算仍可进行。',
        build:evidence=>({request_id:request.request_id,evidence,...(!request.paused?{reason:evidence.text}:{})})})),false,{disabled:Boolean(app.info.sample?.readonly)}),
      request&&button('读取下一工作单',()=>open(()=>continueWork(app)),false,{disabled:Boolean(app.info.sample?.readonly)}),
      button('开始新的明确请求',()=>open(()=>requestForm(app)),false,{disabled:Boolean(app.info.sample?.readonly)})]);
}

function continueWork(app) {
  if(document.querySelector('#modal')?.open)return;
  const body=el('div',{class:'stack'},el('p',{},'按当前请求读取下一步。已有待办由核心复用；本次动作不会运行制作工具或授予额度。'));
  const status=el('div',{class:'stack',role:'status'});body.append(status);
  const read=button('重新读取下一工作单',load);
  const dialog=modal('下一工作单',body,[read]);
  async function load(){
    read.disabled=true;status.replaceChildren(el('p',{},'正在核对当前请求、已完成内容与待办。'));
    try{
      const envelope=await post(projectAPI(app)+'/continue',{}),result=resultOf(envelope),completion=result.completion;
      const pending=result.pending_tasks||[];
      status.replaceChildren(el('div',{class:'stack'},el('h3',{},completion?.state==='completed'?'本次内容已完成':pending.length?`有 ${pending.length} 项工作单待处理`:'当前工作仍需处理缺口'),
        completion?.state==='completed'&&el('p',{},'约定内容已正常返回；本次读取没有继续派发原图制作。'),
        pending.map(task=>el('article',{class:'collaboration-record'},el('strong',{},({compose:'内容整理',blueprint:'原图制作',reconstruct:'SVG 重建',review:'稿件审阅'})[task.kind]||'待处理工作单'),
          el('p',{},`明确范围 ${task.scope_pages?.length||0} 页；尚未由这次读取开始制作。`),details('工作单要求、范围与依据',task),
          button('查看工作单',()=>{dialog.close();app.go({surface:'runs',runs_area:'tasks',task_id:task.task_id,revision:result.revision_id||envelope.artifact_revision_id});}))),
        result.eligibility?.allowed===false&&admissionView(app,{code:result.eligibility.reason_codes?.[0],details:result.eligibility,result,message:'当前条件尚未满足。'}),
        completion&&details('约定产物、检查与内容完成状态',completion),details('核心返回的下一步与完整记录',envelope)));
      app.root.dispatchEvent(new CustomEvent('business-state-changed'));
    }catch(error){status.replaceChildren(admissionView(app,error),el('p',{},'若回包中断，请先核实已有任务。已读稿和草稿保持，不会由网页执行制作工具。'),
      button('查看当前任务',()=>{dialog.close();app.go({surface:'runs',runs_area:'tasks',task_id:null,revision:null});}));}
    finally{read.disabled=false;}
  }
  load();
}

function controlRecovery(app) {
  const prefix=`deck-master:v3:control-draft:${app.info.project_identity}:`,copies=new Map();
  try{
    for(const key of Object.keys(localStorage).filter(value=>value.startsWith(prefix))){
      const copy=JSON.parse(localStorage.getItem(key)),pending=copy.pending;
      if(pending?.payload?.operation_id&&pending.path?.startsWith(projectAPI(app)+'/'))copies.set(pending.payload.operation_id,pending);
    }
  }catch{return button('核实请求副本',()=>modal('请求副本暂不可读',el('p',{},'本机副本保持原样。请保留恢复文件并核实原请求，不要重复派发。')));}
  if(!copies.size)return null;
  return button(`核实已保留的请求（${copies.size}）`,()=>{
    document.querySelector('#modal')?.close();
    const rows=el('div',{class:'stack'});
    for(const [operation,pending] of copies){
      const status=el('div',{class:'stack',role:'status'});
      const verify=button('按原编号核实请求',async()=>{
        verify.disabled=true;
        try{
          const response=await post(pending.path,pending.payload);
          for(const key of Object.keys(localStorage).filter(value=>value.startsWith(prefix))){
            const copy=JSON.parse(localStorage.getItem(key));
            if(copy.pending?.payload?.operation_id===operation)localStorage.setItem(key,JSON.stringify({...copy,pending:null}));
          }
          status.replaceChildren(el('p',{},'原请求回执已核实。是否允许下一动作仍按当前控制重新判断。'),details('原操作回执',response),button('重新读取当前状态',()=>{dialog.close();app.loadRoute({...app.route});}));
        }catch(error){status.replaceChildren(admissionView(app,error));verify.disabled=false;}
      });
      rows.append(el('article',{class:'collaboration-record'},el('p',{},'提交结果待核实；固定版本、对象与范围保持原样。'),details('冻结的原请求',pending),verify,status));
    }
    const dialog=modal('核实已保留的请求',rows,[],{protectDraft:true});
  });
}

export async function deliveryJudgement(app, revision, options={}) {
  const params=new URLSearchParams({revision,...options});
  return resultOf(await get(projectAPI(app)+'/delivery-eligibility?'+params));
}

export function deliveryJudgementView(value) {
  const labels={pass:'通过',allowed:'允许',blocked:'受阻',fail:'未通过',needs_reviewer:'待审阅',not_evaluated:'未评估',needs_review:'待判断',not_required:'无需此项',ready:'就绪'};
  const state=(part,key)=>{
    if(typeof part==='string')return part;
    if(part?.status||part?.state)return part.status||part.state;
    if(key==='engineering'&&typeof part?.ready==='boolean')return part.ready?'pass':'blocked';
    if(key==='collaboration'&&typeof part?.allowed==='boolean')return part.allowed?'allowed':'blocked';
    if(key==='professional'&&part?.required===false)return 'not_required';
    if(key==='professional'&&typeof part?.satisfied==='boolean')return part.satisfied?'pass':'needs_reviewer';
    return '未记录';
  };
  return el('section',{class:'delivery-judgement stack','aria-label':'所选实际文件的交付判断'},
    el('h3',{},value.allowed===true||value.status==='ready'?'所选文件满足当前交付条件':'所选文件仍有交付缺口'),
    el('p',{},`稿件 ${version(value.artifact_revision_id||value.selected_revision_id)} · 当前控制 ${version(value.control_revision_id)}`),
    el('dl',{class:'facts'},...['engineering','collaboration','professional'].flatMap(key=>[el('dt',{}, {engineering:'工程检查',collaboration:'协作控制',professional:'专业复核'}[key]),el('dd',{},labels[state(value[key]||value[key+'_status'],key)]||state(value[key]||value[key+'_status'],key))])),
    el('p',{},'实际文件与口播保留方式按下面的固定记录核对。当前暂停或撤回同样适用于历史文件。'),
    (value.reason_codes||[]).length>0&&el('ul',{},value.reason_codes.map(code=>el('li',{},readableError({code,message:'此项条件尚未满足。请查看完整判断中的具体依据与范围。'})))),
    details('实际文件、口播方式、支持依据与完整判断',value));
}

function draftImportForm(app) {
  const file=field('确认稿 JSON 文件（必填）',el('input',{type:'file',accept:'.json,application/json',required:true}),
    '读取文件中的完整逐页稿。预览与选择不会修改项目；确认后由服务端一次核对来源、范围与当前版本。');
  const preserve=el('input',{type:'checkbox',checked:true});
  const choice=field('比较导入页面',el('select',{'aria-label':'比较导入页面'}));
  const preview=el('div',{class:'stack'}),notice=el('p',{role:'status'});
  let payload=null,serial=0;
  const currentRevision=app.info.control_revision_id||app.info.revision_id;
  file.input.setCustomValidity('请选择完整的确认稿 JSON 文件。');
  async function compare(){
    const token=++serial,index=Number(choice.input.value),incoming=payload?.pages?.[index];
    if(!incoming)return;
    preview.replaceChildren(el('p',{},'正在读取对应的固定基准稿。'));
    try{
      const summary=await get('/api/view/summary?'+new URLSearchParams({revision:currentRevision}));
      const exists=summary.pages.some(page=>page.page_id===incoming.page_id);
      const prior=exists?(await get('/api/pages/'+encodeURIComponent(incoming.page_id)+'/lineage?'+new URLSearchParams({revision:currentRevision}))).page:null;
      if(token!==serial)return;
      preview.replaceChildren(el('div',{class:'stack'},diffView(prior?pageText(prior):'（当前版本没有此页）',pageText(incoming),'当前固定稿','所选确认稿'),
        (prior?.speaker_notes||incoming.speaker_notes)&&diffView(prior?.speaker_notes||'',incoming.speaker_notes||'','当前口播稿','所选口播稿')));
    }catch(error){if(token===serial)preview.replaceChildren(admissionView(app,error));}
  }
  choice.input.addEventListener('change',compare);
  file.input.addEventListener('change',async()=>{
    serial++;payload=null;preview.replaceChildren();file.input.setCustomValidity('正在读取或尚未选入有效稿件。');
    const selected=file.input.files[0];if(!selected)return;
    try{
      if(selected.size>1_800_000)throw new Error('确认稿超过本次可接收大小，请减少文件内容后重试。');
      const value=JSON.parse(await selected.text());
      if(!Array.isArray(value.pages)||!value.pages.length)throw new Error('确认稿需要完整的非空 pages 数组。原文件保持。');
      payload=value;choice.input.replaceChildren(...value.pages.map((page,index)=>el('option',{value:String(index)},`第 ${index+1} 页 · ${page.customer_visible?.title||'未命名页面'}`)));
      file.input.setCustomValidity('');notice.textContent=`已读 ${value.pages.length} 页。请逐页比较，核对主线保留方式与影响；尚未写入项目。`;compare();
    }catch(error){file.input.setCustomValidity(error.message);notice.textContent=error.message;}
  });
  controlForm(app,{title:'导入确认稿',action:'draft.import',path:'/draft/import',
    explanation:'导入会采用所选完整稿件与页序，已有原件留在历史中。保持主线只进入保真审阅，不制造新论证或专业批准；改变主线需要新的论证与范围。',
    body:el('div',{class:'stack'},file.node,el('label',{class:'inline-control'},preserve,'保留确认稿主线，进入保真审阅'),notice,choice.node,preview),
    build:instruction_evidence=>({draft_payload:payload,preserve_mainline:preserve.checked,instruction_evidence})});
}

export function externalReviewForm(app=null) {
  if(document.querySelector('#modal')?.open)return;
  const kind=field('稿件来源',el('select',{},el('option',{value:'file'},'单个文件'),el('option',{value:'project'},'项目固定版本'),el('option',{value:'fileset'},'明确文件集')));
  const path=field('源文件或项目位置（必填）',el('textarea',{rows:3,required:true,autocomplete:'off'}),'文件集每行填写一个完整文件位置。只读取明确选择的来源，不建立制作项目。');
  const revision=field('固定项目版本（可选）',el('input',{autocomplete:'off'}),'留空读取评估开始时的当前版本；报告记录实际版本。');
  const pageChoices=(app?.summary.pages||[]).map((page,index)=>({page_id:page.page_id,input:el('input',{type:'checkbox'}),label:`第 ${index+1} 页 · ${page.title||'未命名页面'}`}));
  const pages=el('fieldset',{hidden:true},el('legend',{},'审阅页面（不选表示 0 页）'),pageChoices.map(item=>el('label',{class:'inline-control'},item.input,item.label)));
  revision.node.hidden=true;
  kind.input.addEventListener('change',()=>{revision.node.hidden=kind.input.value!=='project';pages.hidden=kind.input.value!=='project';});
  const status=el('div',{class:'stack',role:'status'}),form=el('form',{class:'stack'},
    el('p',{},'只读检查源文件并生成可读报告，不修改来源、不制作或采用。没有实际审阅者时保留“待审阅”，工程读取不会成为专业通过。'),kind.node,path.node,revision.node,pages,status);
  const submit=button('读取并生成审阅报告',()=>form.requestSubmit(),true);
  const dialog=modal('只读审阅稿件',form,[submit],{protectDraft:true});
  form.addEventListener('submit',async event=>{
    event.preventDefault();submit.disabled=true;
    const source=kind.input.value==='fileset'?{kind:'fileset',files:path.input.value.split('\n').map(value=>value.trim()).filter(Boolean)}:
      {kind:kind.input.value,path:path.input.value.trim(),...(kind.input.value==='project'&&revision.input.value.trim()?{revision:revision.input.value.trim()}:{})};
    const scope={subject:kind.input.value==='project'?'deck':'external_artifact',page_ids:kind.input.value==='project'?pageChoices.filter(item=>item.input.checked).map(item=>item.page_id):[],page_manifest_ref:null,external_artifact_ref:null,
      layers:['review'],allow_page_membership_change:false,allow_page_order_change:false,purpose:'review'};
    status.replaceChildren(el('p',{},'正在读取固定来源。源稿不写入，已有输入保持。'));
    try {
      const result=resultOf(await post('/api/reviews/evaluate',{source,scope,persistence:'none'}));
      const external=result.external_report,report=external?.report;
      const labels={needs_reviewer:'审阅报告已生成 · 仍需审阅者',needs_tool:'审阅报告已生成 · 渲染工具有缺口',source_changed:'来源在读取期间变化 · 不可导入'};
      status.replaceChildren(el('div',{class:'stack'},el('h3',{},labels[result.status]||'审阅结果已返回'),
        el('p',{},report?.source_unchanged?'来源前后完整性一致；没有修改源稿。':'来源完整性尚未确认，请保留报告并重新固定来源。'),
        el('p',{},'此报告只证明实际读取的字段；专业质量、独立审阅和未覆盖维度继续保留缺口。'),
        ...(report?.engineering_observations||[]).map((observation,index)=>el('article',{class:'collaboration-record'},el('h4',{},`来源 ${index+1}`),
          observation.text&&el('pre',{class:'read-text'},observation.text),observation.slides&&details('逐页实际读取内容',observation.slides),details('读取范围与来源身份',observation))),
        external&&button('下载完整审阅报告',()=>downloadJSON(external,'deck-master-external-review.json')),details('报告范围、证据与缺口',result)));
      if(app&&external&&report?.source_unchanged)status.append(button('查看导入此报告的影响',async event=>{
        const trigger=event.currentTarget;trigger.disabled=true;
        try {
          const bindings=resultOf(await post(projectAPI(app)+'/reviews/bindings',{external_report:external,artifact_revision:app.route.revision}));
          dialog.close();
          controlForm(app,{title:'导入报告记录',action:'review.import',path:'/reviews/import',explanation:'只把这份报告与已核对的实际来源绑定到当前项目。导入不提升审阅身份，不把工程读取当作专业批准。',
            body:details('精确来源与目标绑定',bindings),build:evidence=>({external_report:external,source_bindings:bindings.source_bindings||bindings.bindings,
              artifact_revision:app.route.revision,evidence})});
        }catch(error){status.append(admissionView(app,error));}finally{trigger.disabled=false;}
      }));
    }catch(error){status.replaceChildren(admissionView(app||{summary:{pages:[]}},error));}
    finally{submit.disabled=false;}
  });
}
