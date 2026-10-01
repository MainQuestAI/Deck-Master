import {get, readableError, revisionQuery} from './api.js';
import {el, button, heading, empty, version} from './dom.js';
import {DraftEditor} from './drafts.js';
import {contentOperation, contentPanel as panel, inputField, sourceReader} from './content-edit.js';

export function content(app, data) {
  if (!app.health.ui_capabilities?.includes('content_ops.v1')) return empty('核心需要升级', '内容与来源编辑需要支持内容操作的核心；已存稿件和原有命令仍可读取。');
  const plan = data.plan, inputs = data.inputs, pages = app.summary.pages, pageMap = new Map(pages.map(p => [p.page_id,p]));
  const ref = plan?.ref || null;
  app.editor = new DraftEditor(app.info, {scope:'project',page_id:null,layer:'outline'}, app.route.revision, ref, {readonly:app.readonly,exactRevision:true});
  const draftNode = app.editor.mount();
  const brief = inputField('汇报用途', inputs?.task.brief || ''), audience = inputField('汇报受众', inputs?.task.audience || '', 2);
  const decisions = inputField('既定决定（每行一条）', (inputs?.task.existing_decisions || []).join('\n'));
  const reason = inputField('本次输入变化说明', '', 2), additions = inputField('新增材料完整路径（每行一个）', '', 2);
  let sourceRows = (inputs?.sources || []).map(s => ({source_id:s.source_id, name:s.name || s.source_id, usage_note:s.usage_note || '', action:'keep', path:'', extract:s.extract}));
  let order = pages.map(p => p.page_id), selected = new Set();
  const instruction = inputField('选页调整要求', '', 3);
  const summary = inputField('内容整合结论', plan?.input_summary || '', 3);
  let goals = (plan?.goals || []).map(g => ({goal_id:g.goal_id,page_id:g.page_id,purpose:g.purpose || '',source_links:(g.source_links || []).map(l => ({source_id:l.source_id,source_version:l.source_version,locator:l.locator})),unresolved_facts:g.unresolved_facts || []}));
  let chapters = structuredClone(plan?.chapters || []);
  const sourceList = el('div', {class:'stack'}), pageList = el('ol', {class:'content-order', 'aria-label':'调整逐页稿顺序'}), goalList = el('div', {class:'stack'});
  let operation, completedAction = null;
  function read() { return {brief:brief.input.value,audience:audience.input.value,decisions:decisions.input.value,reason:reason.input.value,additions:additions.input.value,sources:sourceRows,order,selected:[...selected],instruction:instruction.input.value,summary:summary.input.value,goals,chapters}; }
  function hydrate(s) {
    for (const [key,field] of Object.entries({brief,audience,decisions,reason,additions,instruction,summary})) if (key in s) field.input.value=s[key];
    if (s.sources) sourceRows=s.sources;
    if (s.order && s.order.length===pages.length && s.order.every(id=>pageMap.has(id)) && new Set(s.order).size===pages.length) order=s.order;
    selected=new Set((s.selected || []).filter(id=>pageMap.has(id)));
    if (s.goals) goals=s.goals; if (s.chapters) chapters=s.chapters;
    drawSources(); drawPages(); drawGoals();
  }
  operation=contentOperation(app,'content_sources',read,hydrate,ref,result=>{
    if (result.task_ids?.length || result.pending_tasks?.length) app.go({surface:'runs',revision:result.revision_id,task_id:result.task_ids?.[0] || result.pending_tasks?.[0]?.task_id});
    else if (completedAction==='remove') {
      const first=order.findIndex(id=>selected.has(id)); const remaining=order.filter(id=>!selected.has(id));
      app.go({surface:'page',page_id:remaining[Math.min(first,remaining.length-1)],layer:'content',revision:result.revision_id});
    } else { app.contentFocusPage=app.contentFocusPage || order[0]; app.go({surface:'content',revision:result.revision_id}); }
  });
  const changed=()=>operation.changed();
  for (const field of [brief,audience,decisions,reason,additions,instruction,summary]) field.input.addEventListener('input',changed);
  function drawSources() {
    sourceList.replaceChildren(...sourceRows.map(source=>{
      const action=el('select',{'aria-label':'材料操作 '+source.name},el('option',{value:'keep'},'保留材料'),el('option',{value:'replace'},'替换为新版本'),el('option',{value:'remove'},'从当前输入移除'));
      action.value=source.action;
      const note=inputField('材料用途 '+source.name,source.usage_note,2),path=inputField('替换路径 '+source.name,source.path,2);
      path.node.hidden=source.action!=='replace';
      action.addEventListener('change',()=>{source.action=action.value;path.node.hidden=source.action!=='replace';changed();});
      note.input.addEventListener('input',()=>{source.usage_note=note.input.value;changed();});path.input.addEventListener('input',()=>{source.path=path.input.value;changed();});
      return el('article',{class:'source-card stack'},el('strong',{},source.name),
        el('p',{class:'muted'},source.extract?'已读取 · 提取不等于制作工具已阅读并判断影响。':'已登记 · 尚未读取。'),
        el('span',{class:'status '+(source.extract?'ok':'')},source.extract?'制作工具已读取':'等待读取'),
        button('读取材料原文 '+source.name,()=>sourceReader(app,{source_id:source.source_id,source_version:{extract:source.extract}}),false,{class:'text-link'}),
        app.readonly?el('p',{},source.usage_note):[action,note.node,path.node]);
    }));
  }
  function move(id, next) {
    const from=order.indexOf(id);if (next<0 || next>=order.length || from<0 || app.readonly) return;
    order.splice(from,1);order.splice(next,0,id);app.contentFocusPage=id;drawPages();changed();
    pageList.querySelector('[data-page-id="'+CSS.escape(id)+'"] .order-handle')?.focus();
  }
  function drawPages() {
    pageList.replaceChildren(...order.map((id,index)=>{
      const page=pageMap.get(id),title=page.title || id;
      const check=el('input',{type:'checkbox',checked:selected.has(id),disabled:app.readonly,'aria-label':'选定内容页 '+title});
      check.addEventListener('change',()=>{check.checked?selected.add(id):selected.delete(id);changed();});
      const handle=button((index+1)+' · '+title,()=>app.go({surface:'page',page_id:id,layer:'content'}),false,{class:'order-handle',draggable:!app.readonly,'aria-label':'打开内容页 '+title});
      handle.addEventListener('keydown',event=>{if(event.altKey && ['ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();move(id,index+(event.key==='ArrowUp'?-1:1));}});
      handle.addEventListener('dragstart',event=>event.dataTransfer.setData('text/plain',id));
      const row=el('li',{'data-page-id':id,class:'content-order-row'},check,handle,
        !app.readonly && button('向前移动 '+title,()=>move(id,index-1),false,{disabled:index===0}),
        !app.readonly && button('向后移动 '+title,()=>move(id,index+1),false,{disabled:index===order.length-1}));
      row.addEventListener('dragover',event=>event.preventDefault());row.addEventListener('drop',event=>{event.preventDefault();const source=event.dataTransfer.getData('text/plain');if(order.includes(source))move(source,index);});
      return row;
    }));
  }
  function outlineBlocks() {
    // 设计大纲块：章节编号、页范围与来源关联导航；编辑仍在下方内容计划面板。
    return chapters.map((chapter, index) => {
      const ids = [...chapterPages(chapter)].sort();
      const chapterPagesList = ids.map(id => pageMap.get(id)).filter(Boolean);
      if (!chapterPagesList.length) return null;
      const first = chapterPagesList[0], last = chapterPagesList[chapterPagesList.length - 1];
      const links = [...new Set(goals.filter(goal => ids.includes(goal.page_id))
        .flatMap(goal => goal.source_links.map(link => link.locator || '材料')))];
      return el('div', {class: 'outline-block'},
        el('span', {class: 'mono'}, String(index + 1).padStart(2, '0')),
        el('div', {},
          el('h3', {}, chapter.title),
          el('p', {}, goals.find(goal => ids.includes(goal.page_id))?.purpose || ''),
          el('p', {class: 'small-text', style: 'margin-top:7px'},
            chapterPagesList.length > 1 ? `第 ${order.indexOf(first.page_id) + 1}–${order.indexOf(last.page_id) + 1} 页` : `第 ${order.indexOf(first.page_id) + 1} 页`,
            links.length ? ` · ${links.join('、')}` : ' · 未记录来源关联'),
          app.summary.pages.some(p => ids.includes(p.page_id)) && button('看逐页稿', () => app.go({surface: 'page', page_id: first.page_id, layer: 'content'}), false, {class: 'quiet'})));
    }).filter(Boolean);
  }
  function chapterPages(chapter) {
    const chapterGoals = new Set(chapter.goal_ids);
    return new Set(goals.filter(goal => chapterGoals.has(goal.goal_id)).map(goal => goal.page_id));
  }
  function drawGoals() {
    const chapterFields=chapters.map(chapter=>{
      const name=inputField('章节名称 '+(chapters.indexOf(chapter)+1),chapter.title,2);
      name.input.addEventListener('input',()=>{chapter.title=name.input.value;changed();});return name.node;
    });
    goalList.replaceChildren(...chapterFields,...goals.map(goal=>{
      const page=pageMap.get(goal.page_id);const purpose=inputField('页面目标 '+(page?.title || goal.page_id),goal.purpose,2);
      const unresolved=inputField('待确认事实 '+(page?.title || goal.page_id),goal.unresolved_facts.join('\n'),2);
      purpose.input.addEventListener('input',()=>{goal.purpose=purpose.input.value;changed();});unresolved.input.addEventListener('input',()=>{goal.unresolved_facts=unresolved.input.value.split('\n').filter(v=>v.trim());changed();});
      return el('div',{class:'goal-editor stack'},purpose.node,unresolved.node,goal.source_links.map(link=>button('查看目标来源 '+(link.locator || '材料'),()=>sourceReader(app,link))));
    }));
    if(app.readonly) for(const input of goalList.querySelectorAll('textarea'))input.readOnly=true;
  }
  function inputPreview() {
    const source_changes={add:additions.input.value.split('\n').map(p=>p.trim()).filter(Boolean).map(path=>({path})),replace:[],remove:[],metadata:[]};
    for(const source of sourceRows){
      if(source.action==='replace')source_changes.replace.push({source_id:source.source_id,path:source.path,usage_note:source.usage_note});
      else if(source.action==='remove')source_changes.remove.push(source.source_id);
      else if(source.usage_note!==(inputs.sources.find(s=>s.source_id===source.source_id)?.usage_note || ''))source_changes.metadata.push({source_id:source.source_id,usage_note:source.usage_note});
    }
    const differences=[];
    if(brief.input.value!==inputs.task.brief)differences.push('用途：'+brief.input.value);
    if(audience.input.value!==inputs.task.audience)differences.push('受众：'+audience.input.value);
    if(decisions.input.value!==(inputs.task.existing_decisions || []).join('\n'))differences.push('既定决定：'+decisions.input.value);
    for(const source of sourceRows)if(source.action!=='keep')differences.push((source.action==='remove'?'移除：':'替换：')+source.name);
    if(source_changes.add.length)differences.push('新增 '+source_changes.add.length+' 份本机材料');
    if(source_changes.metadata.length)differences.push('更新 '+source_changes.metadata.length+' 份材料用途');
    completedAction='inputs';operation.previewInputs({reason:reason.input.value,task_patch:{brief:brief.input.value,audience:audience.input.value,existing_decisions:decisions.input.value.split('\n').filter(v=>v.trim())},source_changes},differences);
  }
  function preview(action) {
    completedAction=action;
    const targets=['reorder','outline'].includes(action)?[]:[...selected].map(id=>({page_id:id,page_ref:pageMap.get(id).stages.content.ref}));
    const value={content_plan_ref:ref,action,targets,instruction:instruction.input.value || ({reorder:'调整逐页稿顺序',remove:'移除明确选定的页面',outline:'调整内容计划中的章节和页面目标'}[action] || '')};
    if(action==='reorder')value.page_order=order;
    if(action==='outline')value.content_plan={schema_version:'content_plan_input.v1',input_summary:summary.input.value,chapters,goals,unresolved_facts:plan.unresolved_facts || []};
    operation.preview(value);
  }
  drawSources();drawPages();drawGoals();
  const hostImpact=el('div',{class:'stack'});
  const resolved=inputs?.content_basis?.resolved_by_task_id;
  if(resolved) get('/api/tasks/'+encodeURIComponent(resolved)+revisionQuery(app.route.revision)).then(async result=>{
    if(result.task.status!=='completed')return;
    const receipt=await get('/api/operations/'+encodeURIComponent(result.task.operation_id));
    const adopted=receipt.operation_result;
    hostImpact.replaceChildren(el('strong',{},app.summary.input_alignment==='current'?'已采用的 Host 影响判断':'此前采用的 Host 判断（最新输入仍待协调）'),
      el('p',{},adopted.impact_summary || adopted.unchanged_reason || '该回合未记录可读的影响说明，不能补造理由。'),
      ...[adopted.impact_summary && adopted.unchanged_reason && el('p',{},'无正文变化依据：'+adopted.unchanged_reason)].filter(Boolean),
      el('p',{class:'muted'},'这是制作工具提交并采用的判断，仍需核对业务事实。'),
      button('查看这次内容整理',()=>app.go({surface:'runs',task_id:resolved})));
  }).catch(error=>hostImpact.replaceChildren(el('p',{class:'muted'},'影响说明暂不可读：'+readableError(error))));
  const aligned=app.summary.input_alignment==='current';
  const editable = node => app.readonly ? node : operation.guard(node);
  // 材料四态分呈（G15）：已登记（无提取）、制作工具已读取（有提取）、影响判断（Host 已采用/待协调）、采用对齐（input_alignment）。
  // 历史修订不加载当前输入的材料清单：不显示虚假的 0 份断言（评审 reading-P2）。
  const materialAside=el('aside',{class:'panel materials-aside','aria-label':'使用中的材料'},
    el('div',{class:'panel-head'},el('h2',{},'使用中的材料'),el('span',{class:'status'},inputs?(inputs.sources.length+' 份'):'历史版本')),
    el('div',{class:'panel-body stack'},inputs?sourceList:el('p',{class:'muted'},'材料清单按当前输入读取；正在看历史版本，未加载材料列表。'),
      el('p',{class:'muted'},aligned?'当前输入已由内容结果对齐；这不是独立事实核验。':'输入待协调：制作工具尚需按最新材料判断影响。'),
      !app.readonly&&inputs&&el('details',{},el('summary',{},'调整任务要求与材料'),editable(el('div',{class:'stack'},brief.node,audience.node,decisions.node,el('p',{class:'muted'},'保留已明确的决定；需要改变时在此修改，并说明原因。'),
        additions.node,reason.node,button('预览材料与任务变化',inputPreview)))),
      el('p',{class:'footer-note muted'},'更新材料后，先确认受影响的页面，再比较修改结果。')));
  const node=el('div',{class:'content-sources stack'},heading('内容与来源','先看材料与论证，再改逐页稿。直接改内容和交接制作分别保存。',!app.readonly&&button('添加材料或调整要求',()=>{const details=node.querySelector('.materials-aside details');details.open=true;details.querySelector('textarea,input,select')?.focus();},!app.readonly)),
    el('div',{class:aligned?'notice':'history-banner'},el('strong',{},aligned?'当前输入已由内容结果对齐':'输入待协调'),el('p',{},aligned?'已有内容结果采用了这一版输入；这不是独立事实核验。':'已保存的稿件仍可阅读。制作工具尚需按最新材料、受众和用途判断影响。')),
    hostImpact,
    el('div',{class:'content-layout'},
      el('section',{class:'stack'},
        ref?el('div',{class:'stack'},el('div',{class:'section-head'},el('h2',{},'方案大纲'),el('span',{class:'status'},'内容基准 '+version(ref?.sha256 || ref))),...outlineBlocks()):panel('方案大纲',el('p',{},'尚未记录完整内容计划，当前仅能按逐页稿阅读。请交接内容整理。')),
        panel('逐页稿与顺序',editable(el('div',{class:'stack'},el('p',{class:'muted'},'打开页面可改标题和正文。用移动按钮、拖动标题，或聚焦标题后按 Alt + ↑/↓ 调整顺序，再预览保存。'),pageList,
          !app.readonly&&el('div',{class:'stack'},button('预览页序变更',()=>preview('reorder')),instruction.node,el('div',{class:'row wrap'},button('预览移除选页',()=>preview('remove')),button('预览选页改写',()=>preview('rewrite')),button('预览合并选页',()=>preview('merge')),button('预览拆分选页',()=>preview('split'))),el('p',{class:'muted'},'改写保留页身份；合并/拆分由制作工具返回新页，旧标注仍保留在原基准。'))))),
        ref?panel('内容计划',el('p',{},plan.input_summary || ''),el('ol',{},goals.map(g=>el('li',{},g.purpose))),el('details',{},el('summary',{},'编辑内容计划'),editable(el('div',{class:'stack'},el('p',{class:'muted'},'这里编辑章节、目标与待确认事实；正文请进入对应页面修改。'),summary.node,goalList,!app.readonly&&button('预览内容计划变更',()=>preview('outline')))))):panel('内容计划',el('p',{},'尚未记录完整内容计划。')),
        inputs?null:panel('历史材料',el('p',{},'此处只读固定版本的内容目标与来源，不混入当前任务要求。'))),
      materialAside),
    !app.readonly&&operation.node,draftNode);
  if(app.readonly) for(const item of node.querySelectorAll('textarea'))item.readOnly=true;
  if(app.contentFocusPage){const focus=app.contentFocusPage;delete app.contentFocusPage;requestAnimationFrame(()=>pageList.querySelector('[data-page-id="'+CSS.escape(focus)+'"] .order-handle')?.focus());}
  return node;
}
