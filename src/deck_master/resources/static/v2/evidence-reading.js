import {el, button} from './dom.js';
import {revisionQuery} from './api.js';
import {reader, details, issues} from './insight-reading.js';
import {sourceReader} from './content-edit.js';
import {DraftEditor} from './drafts.js';

export function pageEvidence(app,data){
  const query=new URLSearchParams({revision:data.revision_id});if(app.route.atom)query.set('element_ref',app.route.atom);
  return reader(app,'/api/content/evidence/'+encodeURIComponent(data.page_id)+'?'+query,value=>{
    if(!value.data)return el('p',{},'本页依据暂不可读。');const d=value.data;
    return el('div',{class:'stack'},el('h3',{},'正文与证据'),
      el('p',{},({current:'页面绑定当前主线。',bound_to_older_narrative:'此页绑定较早主线，以下按原绑定读取。',not_recorded:'此页未记录原子映射，仍可通过页面来源阅读。'})[d.alignment]),
      app.route.atom&&button('查看本页全部原子',()=>app.go({atom:null})),
      d.elements.map(atom=>el('section',{class:'insight-node stack',tabindex:'0'},button('定位这段正文',()=>app.go({atom:atom.element_ref})),el('p',{class:'read-text'},atom.text),
        el('p',{class:'muted'},({recorded:'已记录映射',not_recorded:'未记录映射',unreadable:'映射依据暂不可读'})[atom.mapping_status]),
        atom.nodes.map(n=>el('p',{},n.statement)),atom.qualifications.map(n=>el('p',{},'限定条件：'+n.statement)),
        [...atom.direct_source_links,...atom.node_source_links].map(link=>button('阅读原始来源',()=>sourceReader(app,link,data.revision_id))),details('原子、关系与原始定位',atom))),
      app.route.review_id&&button('返回原审阅问题',()=>app.go({surface:'runs',page_id:null,review_id:app.route.review_id,review_sha256:app.route.review_sha256,finding:app.route.finding,finding_index:app.route.finding_index,atom:null})),issues(value));
  });
}
export function designRequirements(app,data){return reader(app,'/api/content/requirements/'+encodeURIComponent(data.page_id)+revisionQuery(data.revision_id),value=>{
  const d=value.data;if(!d)return el('div',{},el('h3',{},'内容到设计要求'),el('p',{},'这版设计要求暂不可读。'),issues(value));
  return el('section',{class:'stack'},el('h3',{},'内容到设计要求'),el('p',{},d.origin==='frozen_task'?'来自同版本任务冻结的内容要求。':'从所读快照推导，尚未冻结到制作任务。'),
    el('p',{},'保留正文与限定条件。空间不足时请返回内容流程提出修改，不会自动删减或启动生图。'),details('页面职责、限定条件与结构关系',d.content_requirements),details('真实内容依据',d.content_basis),issues(value));});}
const statusLabels={fixed:'已记录解决',open:'尚未解决',needs_review:'待审阅',not_evaluated:'未评估',not_applicable:'不适用',pass:'该项通过',fail:'该项未通过',blocked:'受阻'};
export function reviewReading(app){
  const q=new URLSearchParams({revision:app.route.revision});if(app.route.review_sha256)q.set('review_sha256',app.route.review_sha256);
  return reader(app,'/api/reviews/'+encodeURIComponent(app.route.review_id)+'/reading?'+q,value=>{
    const d=value.data;if(!d)return el('div',{},el('p',{},'所选审阅暂不可读。'),issues(value));
    const review=d.review.data;
    const chosen=app.route.finding==null?null:d.targets.find(t=>t.finding_id===app.route.finding&&String(t.source_index)===String(app.route.finding_index));
    if(app.route.finding!=null&&!chosen)return el('p',{role:'alert'},'原问题定位不匹配，未自动选中其他问题。请返回原审阅记录核对。');
    return el('div',{class:'stack'},el('h1',{},'审阅问题与范围交接'),el('p',{},statusLabels[review.status]||review.status),el('p',{class:'muted'},'阅读、修稿返回或采用都不会自动把旧问题标为解决。'),
      (chosen?[chosen]:d.targets).map(t=>{const finding=review.findings[t.source_index];const identity={review_id:review.review_id,review_sha256:d.review_ref.sha256,finding:t.finding_id,finding_index:t.source_index};
        return el('article',{class:'panel stack insight-finding',tabindex:'0'},el('h2',{},finding.message),el('p',{},'预期：'+finding.expected),el('p',{},'实际：'+finding.actual),
          el('p',{},'影响：'+(statusLabels[finding.impact]||JSON.stringify(finding.impact))),el('p',{},'解决记录：'+(statusLabels[finding.resolution?.status||finding.resolution]||JSON.stringify(finding.resolution))),
          button('固定此问题链接',()=>app.go(identity)),
          t.page_ref&&button(t.locator_status==='exact'?'定位原页面文字':'阅读相关页（精确位置不可用）',()=>app.go({surface:'page',page_id:t.page_id,layer:'content',...identity,atom:t.locator_status==='exact'?t.element_refs[0]:null})),
          button('准备范围交接草稿',()=>repairDraft(app,value,t,finding)),details('完整问题、证据与定位',finding),details('修订范围准入',t));}),issues(value));
  });
}
function repairDraft(app,value,target,finding){
  const ref=target.page_ref||null;
  const draft=new DraftEditor(app.info,{scope:target.page_ref?'page':'project',page_id:target.page_ref?target.page_id:null,layer:'notes'},value.revision_id,ref,{exactRevision:true,contextKey:`review:${value.data.review_ref.sha256}:${target.finding_id}:${target.source_index}`});
  draft.onRestore=copy=>draft.restoreInPlace(copy);
  const node=draft.mount();draft.input.id='review-draft-'+crypto.randomUUID();node.querySelector('label[for=personal-draft]')?.setAttribute('for',draft.input.id);draft.input.setAttribute('aria-label','审阅交接备注');draft.stateNode.className='review-draft-state';const body=el('div',{class:'stack'},el('p',{},'仅准备个人草稿，不派发、不修稿、不改变审阅结论。正文、口播、设计、来源按原请求分别处理。'),node);
  // Dynamic import avoids creating a cycle with the existing content editor.
  import('./dom.js').then(({modal})=>{const dialog=modal('准备范围交接',body,[],{protectDraft:true});dialog.addEventListener('close',()=>draft.dispose(),{once:true});});
  draft.ready.then(()=>{if(draft.disposed)return;if(!draft.input.value){draft.input.value=finding.message+'\n预期：'+finding.expected+'\n实际：'+finding.actual;draft.draft.content.review_handoff={review_ref:value.data.review_ref,revision:value.revision_id,finding_id:target.finding_id,source_index:target.source_index,page_ref:target.page_ref,element_refs:target.element_refs,repair_layer:target.repair_layer};draft.changed();}
    if(target.page_ref&&target.repair_layer==='content'&&target.repair_allowed)body.append(button('保存草稿后进入原正文编辑',async()=>{await draft.save();if(draft.status!=='saved'||draft.staleBasis()||!draft.draft.content.review_handoff)return;app.reviewHandoff={...draft.draft.content.review_handoff,text:draft.input.value};document.querySelector('#modal')?.close();app.go({surface:'page',page_id:target.page_id,layer:'content',revision:value.revision_id,review_id:null,atom:null});}));});
}
