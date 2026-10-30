import {get,post,readableError,revisionQuery} from './api.js';
import {el,button,modal,field,downloadJSON} from './dom.js';
import {projectAPI} from './collaboration-desk.js';

const detail=(title,value)=>el('details',{},el('summary',{},title),typeof value==='string'?el('p',{class:'read-text'},value):el('pre',{class:'evidence-json'},JSON.stringify(value,null,2)));
const outcome=value=>{const r=value.result||value;return r.operation_result||r;};
const retainDraft=(persist,saved,status)=>{try{persist();}catch{status.replaceChildren(el('p',{role:'alert'},'本机草稿尚未保存，当前输入仍在窗口中；请下载保留后核实本机存储。'),button('下载当前操作草稿',()=>downloadJSON(saved,'outline-draft.json')));}};
const readKey=(key,fallback)=>JSON.parse(localStorage.getItem(key)||'null')||fallback;
async function recover(pending){try{return outcome(await get('/api/operations/'+pending.payload.operation_id));}catch(e){if(e.code!=='operation_not_found')throw e;return outcome(await post(pending.path,pending.payload));}}
const roleNames={requirement:'需求',capability:'现有能力',scenario:'使用场景',constraint:'条件与边界',support:'支撑说明'};

export function businessFrameBody(data){
  const n=data.narrative,s=n.business_strategy,f=n.business_frame;
  if(!s)return el('p',{class:'muted'},'未记录业务框架；已存主线和逐页职责仍可阅读。');
  const nodes=new Map(n.nodes.map(node=>[node.node_id,node.statement]));
  const chosen=(ids=[])=>ids.map(id=>el('p',{class:'read-text'},nodes.get(id)||'对应内容暂不可读'));
  const root=el('section',{class:'stack business-frame'},el('h4',{},'作者任务与业务框架'),el('p',{class:'read-text'},s.author_goal),
    el('p',{class:'muted'},({first_proposal:'首次提案',competitive_bid:'竞标'})[s.scenario]||s.scenario),
    n.maturity==='framing'&&el('p',{},'这是任务理解提案；主题与页序尚未采用。'),
    data.business_group?.author_revision&&el('p',{class:'muted'},'本版为作者手工修订，原稿与方法沿革保留。'),
    el('details',{},el('summary',{},'重点、共识与取舍'),el('h5',{},'本次重点'),chosen(s.focus_node_ids),
      el('h5',{},'已有共识'),chosen(s.established_node_ids),el('h5',{},'不单独展开'),chosen(s.omitted_node_ids),detail('完整取舍理由',s.rationale)));
  if(!f)return root.appendChild(el('p',{},'业务主题尚未形成；可继续阅读任务理解与未决问题。')),root;
  const names=new Map(f.topics.map(topic=>[topic.topic_id,topic.name]));
  root.append(el('p',{class:'read-text'},f.organizing_basis),...f.topics.map(topic=>el('section',{class:'insight-node business-topic'},
    el('h5',{},topic.name),el('p',{class:'read-text'},topic.meaning),
    el('details',{},el('summary',{},'查看需求、能力与场景对应'),...topic.links.map(link=>el('p',{class:'read-text'},
      el('strong',{},(roleNames[link.role]||'内容对应')+'：'),nodes.get(link.node_id)||'对应内容暂不可读'))),
    topic.gap_issue_ids.length>0&&el('details',{},el('summary',{},'相关待定问题'),...topic.gap_issue_ids.map(id=>el('p',{class:'read-text'},n.issues.find(i=>i.issue_id===id)?.question||'问题暂不可读'))))),
    el('details',{},el('summary',{},'主题怎样衔接'),...f.relations.map(r=>el('p',{class:'read-text'},el('strong',{},`${names.get(r.from_topic_id)||'原主题'} → ${names.get(r.to_topic_id)||'目标主题'}：`),r.relation))));
  return root;
}

export function businessControls(app,value){
  const d=value.data,g=d.business_group,root=el('section',{class:'stack business-outline-actions'});
  if(!g)return root;
  const prefix=`deck-master:outline:${app.info.project_identity}:${g.narrative_ref.sha256}:${g.plan_ref?.sha256||''}`;
  try{
    if(localStorage.getItem(prefix+':adopt'))root.append(button('核实原主线与计划采用',()=>adoptDialog(app,value,prefix+':adopt')));
    if(localStorage.getItem(prefix+':edit'))root.append(button('恢复框架修订草稿',()=>editDialog(app,value,prefix+':edit')));
  }catch{root.append(el('p',{},'本机草稿暂不可读，请核实后再提交。'));return root;}
  if(g.is_adopted)root.append(el('p',{},'当前主线与匹配计划已采用。'));
  if(!app.readonly&&(g.can_start_followup||g.can_record_direction_decision||g.can_adopt)&&!g.is_adopted)
    root.append(button('采用主线与计划',()=>adoptDialog(app,value,prefix+':adopt'),true));
  if(!app.readonly&&g.can_revise)root.append(button('修订这份框架',()=>editDialog(app,value,prefix+':edit')));
  if(app.readonly)root.append(el('p',{class:'muted'},'当前为固定历史版本，保留只读。'));
  else if(g.reason_codes.length)root.append(detail('操作范围与待核对依据',g.reason_codes));
  return root;
}

function adoptDialog(app,initial,key){
  let saved,busy=false,current=initial;
  try{saved=readKey(key,{reason:'',pending:null,receipts:[]});}catch{return modal('采用操作恢复',el('p',{},'原操作草稿无法读取，请先保留本机数据并核实。'));}
  const reason=field('采用这份主线与计划的理由',el('textarea',{rows:3,required:true},saved.reason)),status=el('div',{class:'stack',role:'status'});
  const persist=()=>localStorage.setItem(key,JSON.stringify(saved));
  const submit=button('确认采用主线与计划',send,true),fresh=button('保留原操作并核对当前版本',refresh);
  const dialog=modal('采用固定主线与计划',el('div',{class:'stack'},el('p',{},'将采用当前选择的主线与其匹配计划；保留原稿，不启动页面制作。'),reason.node,status,
    detail('固定对象与操作范围',initial.data.business_group)),[submit,fresh],{protectDraft:true});
  reason.input.addEventListener('input',()=>{if(!saved.pending){saved.reason=reason.input.value;retainDraft(persist,saved,status);}});
  function paint(){submit.disabled=busy||Boolean(saved.complete);fresh.disabled=busy;reason.input.disabled=busy||Boolean(saved.pending)||Boolean(saved.complete);submit.textContent=saved.pending?'核实并继续原采用操作':'确认采用主线与计划';}
  function same(g){const fixed=initial.data.business_group;return g?.narrative_ref.sha256===fixed.narrative_ref.sha256&&g?.plan_ref?.sha256===fixed.plan_ref?.sha256;}
  async function send(){if(busy)return;if(!reason.input.value.trim()){reason.input.reportValidity();return;}busy=true;paint();
    try{for(let step=0;step<5;step++){
      let result,kind;
      if(saved.pending){kind=saved.pending.kind;result=await recover(saved.pending);}
      else{
        const g=current.data.business_group;if(!same(g))throw Error('匹配计划已变化，请保留原选择重新核对。');
        if(g.is_adopted){saved.complete={revision_id:current.revision_id};persist();break;}
        const id=crypto.randomUUID(),payload={project_id:app.info.project_id,base_revision:g.assessed_control_revision,operation_id:id};let path;
        if(g.can_start_followup){kind='request';path=projectAPI(app)+'/collaboration/requests';payload.request={intent:'content_only',content_intent:'plan_only',
          scope:{...g.write_scope,layers:['narrative','plan','review']},instruction_evidence:{kind:'host_attested_instruction',text:reason.input.value,source_locator:'studio:outline-adoption:'+id}};}
        else if(g.can_adopt){kind=g.next_ref.sha256===g.narrative_ref.sha256?'narrative':'plan';path=projectAPI(app)+'/collaboration/proposal-adoptions';Object.assign(payload,{proposal_ref:g.next_ref,decision_ref:g.existing_decision_ref,write_scope:g.write_scope});}
        else if(g.can_record_direction_decision&&!saved.receipts.some(r=>r.kind==='decision')){kind='decision';path=projectAPI(app)+'/collaboration/decisions';payload.decision={topic:'direction',authority_mode:'direct_user',subject_refs:g.subject_refs,scope:g.write_scope,basis:g.basis,
          value:{selected:g.narrative_ref.sha256,plan:g.plan_ref.sha256},disposition:'accepted',instruction_evidence:{kind:'host_attested_instruction',text:reason.input.value,source_locator:'studio:outline-direction:'+id}};}
        else throw Error('当前准入已变化，请核对原操作和当前任务。');
        saved={...saved,reason:reason.input.value,pending:{kind,path,payload}};persist();result=outcome(await post(path,payload));
      }
      saved.receipts.push({kind,result});saved.pending=null;persist();
      current=await get('/api/content/arguments/'+initial.data.item.ref.sha256+revisionQuery(result.revision_id));
      if(!same(current.data.business_group))throw Error('原主线与计划的对应已变化，未自动采用另一份计划。');
      if(current.data.business_group.is_adopted){saved.complete={revision_id:result.revision_id};persist();break;}
    }
    if(!saved.complete)throw Error('原操作已记录，请继续核实剩余步骤。');
    status.replaceChildren(el('p',{},'主线与匹配计划已采用，未启动页面制作。'),button('阅读采用后的固定版本',()=>{dialog.close();app.go({revision:saved.complete.revision_id});}));
    }catch(e){status.replaceChildren(el('p',{role:'alert'},'采用尚未确认完成；原选择、理由与操作记录已保留。'),detail('核对依据',readableError(e)));}finally{busy=false;paint();}}
  async function refresh(){if(busy)return;busy=true;paint();try{
    if(saved.pending){try{await get('/api/operations/'+saved.pending.payload.operation_id);throw Error('原操作已有回执，请先核实并继续原操作。');}catch(e){if(e.code!=='operation_not_found')throw e;}
      saved.previous_attempts=[...(saved.previous_attempts||[]),saved.pending];saved.pending=null;}
    current=await get('/api/content/arguments/'+initial.data.item.ref.sha256);
    if(!same(current.data.business_group))throw Error('匹配对象已变化，原选择保留。');
    saved.receipts=saved.receipts.filter(r=>r.kind!=='decision');persist();status.replaceChildren(el('p',{},'当前准入已读取；请核对后明确继续。'));
  }catch(e){status.replaceChildren(el('p',{role:'alert'},readableError(e)));}finally{busy=false;paint();}}
  if(saved.complete)status.append(el('p',{},'原采用操作已完成。'),button('阅读已采用的固定版本',()=>{dialog.close();app.go({revision:saved.complete.revision_id});}));
  paint();
}

function editDialog(app,initial,key){
  const d=initial.data,g=d.business_group,n=d.narrative,plan=d.plans.find(p=>p.ref.sha256===g.plan_ref.sha256)?.data.plan;
  let saved,busy=false,current=initial;
  try{saved=readKey(key,{fields:{},reason:'',pending:null});}catch{return modal('框架修订恢复',el('p',{},'原草稿无法读取，请先核实本机数据。'));}
  const persist=()=>localStorage.setItem(key,JSON.stringify(saved)),inputs=[],topics=[],nodes=[],pages=[];
  function edit(row,type,index,idKey,keys,list){const fields={};for(const [property,label] of keys){const k=type+':'+row[idKey]+':'+property;
    const f=field(label,el('textarea',{rows:property==='name'?1:3,required:true},saved.fields[k]??row[property]));
    f.input.addEventListener('input',()=>{saved.fields[k]=f.input.value;retainDraft(persist,saved,status);});fields[property]=f;inputs.push(f.input);}
    list.push({row,idKey,fields});return el('section',{class:'stack insight-node'},...Object.values(fields).map(f=>f.node));}
  const topicFields=n.business_frame.topics.map((r,i)=>edit(r,'topic',i,'topic_id',[['name',`主题 ${i+1} 名称`],['meaning',`主题 ${i+1} 含义`]],topics));
  const nodeFields=n.nodes.filter(r=>['inference','hypothesis','recommendation'].includes(r.authority)).map((r,i)=>edit(r,'node',i,'node_id',[['statement',`主张与解释 ${i+1}`]],nodes));
  const pageFields=plan.input.page_roles.map((r,i)=>edit(r,'page',i,'page_id',[['role',`第 ${i+1} 页职责`],['audience_question',`第 ${i+1} 页读者问题`],['intended_takeaway',`第 ${i+1} 页要点`]],pages));
  const reason=field('修订理由',el('textarea',{rows:2,required:true},saved.reason)),status=el('div',{class:'stack',role:'status'});
  const submit=button('保存修订候选',send,true),fresh=button('保留草稿并核对当前版本',refresh);
  const dialog=modal('修订固定业务框架',el('div',{class:'stack'},el('p',{},'生成新的主线与匹配计划候选，保留原稿。本操作不调用模型。'),...topicFields,
    el('details',{},el('summary',{},'修正主张与页面职责'),el('p',{},'材料事实保留原文；事实变化可在任务与材料中更新。'),...nodeFields,...pageFields),reason.node,status),[submit,fresh],{protectDraft:true});
  reason.input.addEventListener('input',()=>{saved.reason=reason.input.value;retainDraft(persist,saved,status);});
  function paint(){submit.disabled=busy||Boolean(saved.complete);fresh.disabled=busy;for(const input of [...inputs,reason.input])input.disabled=busy||Boolean(saved.pending)||Boolean(saved.complete);submit.textContent=saved.pending?'核实原修订操作':'保存修订候选';}
  function edits(rows){return rows.flatMap(({row,idKey,fields})=>{const changed=Object.fromEntries(Object.entries(fields).filter(([k,f])=>f.input.value!==row[k]).map(([k,f])=>[k,f.input.value]));return Object.keys(changed).length?[{[idKey]:row[idKey],...changed}]:[];});}
  function show(result){const refs=result.proposal_refs;if(!refs?.length)throw Error('修订回执缺少固定对象，请核实原操作。');saved.complete={revision_id:result.revision_id,ref:refs[0]};saved.pending=null;persist();status.replaceChildren(el('p',{},'修订候选已保存，原稿保留，尚未采用。'),button('阅读并比较修订候选',()=>{dialog.close();app.go({proposal:refs[0].sha256,compare_proposal:g.narrative_ref.sha256,revision:result.revision_id});}));}
  async function send(){if(busy)return;for(const input of [...inputs,reason.input])if(!input.reportValidity())return;busy=true;paint();try{
    let result;if(saved.pending)result=await recover(saved.pending);else{
      const group=current.data.business_group;if(!group?.can_revise||group.plan_ref?.sha256!==g.plan_ref.sha256)throw Error('任务依据或匹配计划已变化，请核对后再保存。');
      const payload={project_id:app.info.project_id,base_revision:group.assessed_control_revision,operation_id:crypto.randomUUID(),narrative_ref:g.narrative_ref,plan_ref:g.plan_ref,
        reason:reason.input.value,topic_edits:edits(topics),node_edits:edits(nodes),page_edits:edits(pages)};
      if(!payload.topic_edits.length&&!payload.node_edits.length&&!payload.page_edits.length)throw Error('内容没有变化，未生成新候选。');
      saved={...saved,reason:reason.input.value,pending:{kind:'revision',path:'/api/content/outline-revisions',payload}};persist();result=outcome(await post(saved.pending.path,payload));
    }show(result);
  }catch(e){status.replaceChildren(el('p',{role:'alert'},'修订尚未确认完成；草稿和原操作已保留。'),detail('核对依据',readableError(e)));}finally{busy=false;paint();}}
  async function refresh(){if(busy)return;busy=true;paint();try{
    if(saved.pending){try{const result=outcome(await get('/api/operations/'+saved.pending.payload.operation_id));show(result);return;}catch(e){if(e.code!=='operation_not_found')throw e;}
      saved.previous_attempts=[...(saved.previous_attempts||[]),saved.pending];saved.pending=null;}
    current=await get('/api/content/arguments/'+g.narrative_ref.sha256);
    if(!current.data.business_group?.can_revise||current.data.business_group.plan_ref?.sha256!==g.plan_ref.sha256)throw Error('任务依据已变，原草稿保留；请核对任务与材料。');
    persist();status.replaceChildren(el('p',{},'当前准入已核对，原草稿保留；请明确保存以创建新操作。'));
  }catch(e){status.replaceChildren(el('p',{role:'alert'},readableError(e)));}finally{busy=false;paint();}}
  if(saved.complete)status.append(el('p',{},'原修订候选已保存。'),button('阅读原修订候选',()=>{dialog.close();app.go({proposal:saved.complete.ref.sha256,revision:saved.complete.revision_id});}));
  paint();
}
