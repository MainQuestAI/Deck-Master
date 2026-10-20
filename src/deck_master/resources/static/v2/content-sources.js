import {routeHash} from './routes.js';
import {argumentDesk,supportsInsights} from './insight-reading.js';
import {methodLibrary} from './method-library.js';
import {studioStyle, styleDisclosure} from './style-phases.js';
import {materialUploads} from './material-uploads.js';
import {get, readableError, revisionQuery, canonical} from './api.js';
import {el, button, heading, empty, version, icon, modal} from './dom.js';
import {DraftEditor} from './drafts.js';
import {contentOperation, contentPanel as panel, inputField, sourceReader} from './content-edit.js';

export function content(app, data) {
  if (!app.health.ui_capabilities?.includes('content_ops.v1')) return empty('核心需要升级', '内容与来源编辑需要支持内容操作的核心；已存稿件和原有命令仍可读取。');
  const plan = data.plan, inputs = data.inputs, pages = app.summary.pages, pageMap = new Map(pages.map(p => [p.page_id,p]));
  const modernPlan = plan?.input?.schema_version === 'content_plan_input.v2';
  const ref = plan?.ref || null;
  const readingRevision = app.route.revision, controller = new AbortController();
  let disposed = false, impactAdopted = false;
  const sourceFacts = new Map(), materialStatuses = new Map(), sourceCatalog = new Map();
  async function sourceForGoal(source) {
    const key=source.source_id+':'+(source.extract?.sha256||'');
    if(!sourceCatalog.has(key)){
      const query=new URLSearchParams({revision:readingRevision});if(source.extract?.sha256)query.set('extract_sha256',source.extract.sha256);
      sourceCatalog.set(key,get('/api/content/sources/'+encodeURIComponent(source.source_id)+'?'+query,{signal:controller.signal}).then(record=>{
        const expected={original_sha256:source.original_sha256??null,extract:source.extract??null};
        if(record.source_id!==source.source_id||record.revision_id!==readingRevision||canonical(record.source_version)!==canonical(expected))throw Error('材料版本与当前阅读基准不一致，请保留草稿并重新读取。');
        return record;
      }).catch(error=>{sourceCatalog.delete(key);throw error;}));
    }
    return sourceCatalog.get(key);
  }
  app.disposables.push(() => { disposed = true; controller.abort(); });
  app.editor = new DraftEditor(app.info, {scope:'project',page_id:null,layer:'outline'}, app.route.revision, ref, {readonly:app.readonly,exactRevision:true});
  const draftNode = app.editor.mount();
  const brief = inputField('用途与目标', inputs?.task.brief || ''), audience = inputField('受众', inputs?.task.audience || '', 2);
  const decisions = inputField('既定决定（每行一条）', (inputs?.task.existing_decisions || []).join('\n'));
  const reason = inputField('本次输入变化说明', '', 2), additions = inputField('新增材料完整路径（每行一个）', '', 2);
  let uploads = [];
  let sourceRows = (inputs?.sources || []).map(s => ({source_id:s.source_id, name:s.name || s.source_id, usage_note:s.usage_note || '', action:'keep', path:'', extract:s.extract}));
  let order = pages.map(p => p.page_id), selected = new Set();
  const instruction = inputField('选页调整要求', '', 3);
  const splitPoint=inputField('拆分位置与方式','',2),mergeTitle=inputField('合并后的页面标题','',1);
  let adjustmentAction='rewrite';
  const adjustmentError=el('p',{class:'field-error',role:'alert',hidden:true,id:'content-adjustment-error'});
  for(const field of [splitPoint,mergeTitle])field.input.setAttribute('aria-describedby','content-adjustment-error');
  const summary = inputField('内容整合结论', plan?.input_summary || '', 3);
  summary.input.readOnly = modernPlan;
  const retainedSummary = el('p',{class:'muted',hidden:true},'原草稿中的整合说明保留供核对，尚未写入当前内容计划；当前计划通过章节和逐页职责记录。');
  const showSummary = () => {summary.node.hidden=modernPlan&&!summary.input.value;retainedSummary.hidden=!modernPlan||!summary.input.value;};
  showSummary();
  let goals = (plan?.goals || []).map(g => ({goal_id:g.goal_id,page_id:g.page_id,purpose:g.purpose || '',source_links:(g.source_links || []).map(l => ({source_id:l.source_id,source_version:l.source_version,locator:l.locator})),
    unresolved_facts:modernPlan?(plan.input.issues||[]).filter(issue=>issue.affected_page_ids.includes(g.page_id)).map(issue=>issue.question):g.unresolved_facts || []}));
  let chapters = structuredClone(plan?.chapters || []);
  const studio=studioStyle(),orderReview=el('div',{class:'studio-content-review stack'}),planReview=el('div',{class:'studio-content-review stack'});
  const goalSearch=el('input',{type:'search','aria-label':'搜索页面目标',placeholder:'搜索页码、标题或页面目标'});
  const sourceList = el('div', {class:'stack'}), pageList = el('ol', {class:'content-order', 'aria-label':'调整逐页稿顺序'}), goalList = el('div', {class:'stack'});
  let operation, completedAction = null;
  const materialEditor = el('div',{class:'stack'});
  const retainedInputs = el('div',{class:'retained-inputs row wrap',role:'status',hidden:true});
  let editTrigger = null, editKind = 'task', editSourceId = null, editReturnScroll = null;
  function read() { return {brief:brief.input.value,audience:audience.input.value,decisions:decisions.input.value,reason:reason.input.value,additions:additions.input.value,sources:sourceRows,uploads,order,selected:[...selected],instruction:instruction.input.value,split_point:splitPoint.input.value,merge_title:mergeTitle.input.value,adjustment_action:adjustmentAction,summary:summary.input.value,goals,chapters}; }
  function hydrate(s) {
    for (const [key,field] of Object.entries({brief,audience,decisions,reason,additions,instruction,split_point:splitPoint,merge_title:mergeTitle,summary})) if (key in s) field.input.value=s[key];
    showSummary();
    if (s.sources) sourceRows=s.sources;
    if (Array.isArray(s.uploads)) uploads=s.uploads;
    if (s.order && s.order.length===pages.length && s.order.every(id=>pageMap.has(id)) && new Set(s.order).size===pages.length) order=s.order;
    selected=new Set((s.selected || []).filter(id=>pageMap.has(id)));
    if (s.goals) goals=s.goals; if (s.chapters) chapters=s.chapters;
    if(studio)showAdjustment(s.adjustment_action||'rewrite',false);
    drawSources(); drawPages(); drawGoals();
    if(adjustDetails&&!adjustDetails.hidden)openMaterialEditor(editKind,editSourceId,editTrigger);
  }
  operation=contentOperation(app,'content_sources',read,hydrate,ref,result=>{
    if (result.task_ids?.length || result.pending_tasks?.length) {
      const ids = result.task_ids || result.pending_tasks.map(task => task.task_id);
      app.go({surface:'runs',revision:result.revision_id,task_id:ids.length === 1 ? ids[0] : null,runs_area:'tasks'});
    }
    else if (completedAction==='remove') {
      const first=order.findIndex(id=>selected.has(id)); const remaining=order.filter(id=>!selected.has(id));
      app.go({surface:'page',page_id:remaining[Math.min(first,remaining.length-1)],layer:'content',revision:result.revision_id});
    } else { if(studio&&completedAction==='outline')app.contentArea='plan';else app.contentFocusPage=app.contentFocusPage || order[0];app.go({surface:'content',revision:result.revision_id}); }
  });
  const changed=()=>{operation.changed();showRetainedInputs();orderReview.querySelector('.content-request-review')?.remove();adjustmentError.hidden=true;for(const field of [splitPoint,mergeTitle])field.input.removeAttribute('aria-invalid');if(adjustDetails&&!adjustDetails.hidden){adjustDetails.dataset.step='edit';returnEdit.hidden=true;}};
  function showRetainedInputs() {
    const taskChanged=inputs && (brief.input.value!==inputs.task.brief || audience.input.value!==inputs.task.audience ||
      decisions.input.value!==(inputs.task.existing_decisions||[]).join('\n'));
    const materialsChanged=Boolean(additions.input.value.trim()||uploads.length||sourceRows.some(source=>source.action!=='keep'||
      source.usage_note!==(inputs?.sources.find(item=>item.source_id===source.source_id)?.usage_note||'')));
    const other=editKind==='task'?materialsChanged:taskChanged;
    retainedInputs.hidden=!other;
    retainedInputs.replaceChildren(...(other ? [el('span',{},editKind==='task'?'还保留了材料变更；预览会列出全部差异。':'还保留了要求修改；预览会列出全部差异。'),
      button(editKind==='task'?'返回材料变更':'返回要求修改',()=>openMaterialEditor(editKind==='task'?'add':'task'))] : []));
  }
  for (const field of [brief,audience,decisions,reason,additions,instruction,splitPoint,mergeTitle,summary]) field.input.addEventListener('input',changed);
  function sourceState(source, node) {
    const fact = sourceFacts.get(source.source_id);
    const extraction = fact?.data?.extraction_status;
    const text = fact?.error ? '提取：暂不可读' : extraction === 'read' ? '提取：原文可读' : extraction === 'pending_visual' ? '提取：待制作工具看图' : extraction === 'needs_tool' ? '提取：缺少读取工具' : source.extract ? '提取：记录待核实' : '提取：未记录';
    if(node.compact)node.compact.textContent='已登记 · '+text.replace('提取：','');
    node.replaceChildren(el('p', {class:'material-state'}, '登记：已在这版输入中登记'),
      el('p', {class:'material-state'}, text),
      el('p', {class:'material-state'}, impactAdopted ? '影响判断：已有制作工具判断被采用' : '影响判断：尚未核实可读的判断记录'),
      el('p', {class:'material-state'}, extraction === 'read' && impactAdopted && app.summary.input_alignment === 'current' ? '对齐：内容结果采用了这版输入' : '对齐：此材料版本仍需核实'),
      el('p', {class:'muted'}, '提取原文不等于制作工具已阅读或独立事实核验。'));
    if (fact?.error) node.append(el('p', {class:'field-error'}, readableError(fact.error)), el('p', {class:'muted'}, '已保存稿件与当前输入保留。可重试核实或恢复对应材料版本。'));
  }
  async function verifySource(source, node, control) {
    control.disabled = true;
    try {
      const query = new URLSearchParams({revision:readingRevision});
      if (source.extract?.sha256) query.set('extract_sha256', source.extract.sha256);
      const data = await get('/api/content/sources/' + encodeURIComponent(source.source_id) + '?' + query, {signal:controller.signal});
      if (disposed) return;
      // Keep status metadata only; the source reader owns full text display.
      sourceFacts.set(source.source_id, {data:{extraction_status:data.extraction_status}});
    } catch (error) { if (disposed) return; sourceFacts.set(source.source_id, {error}); }
    if (!disposed) { sourceState(source, node); control.disabled = false; }
  }
  function drawSources() {
    materialStatuses.clear();
    sourceList.replaceChildren(...sourceRows.map(source=>{
      const status = el('div', {class:'stack', role:'status'}); materialStatuses.set(source.source_id, {source,node:status}); sourceState(source, status);
      const verify = button('核实提取状态 '+source.name, () => verifySource(source,status,verify));
      if(studio){
        const compact=el('p',{class:'studio-source-status muted'});status.compact=compact;sourceState(source,status);
        return el('article',{class:'source-card studio-material-card stack'},el('span',{class:'studio-material-symbol','aria-hidden':'true'},icon('content')),el('h3',{},source.name),source.usage_note&&el('p',{},source.usage_note),compact,
          el('div',{class:'row wrap'},button('读取材料原文 '+source.name,()=>sourceReader(app,{source_id:source.source_id,source_version:{extract:source.extract}},readingRevision)),!app.readonly&&button('调整此材料 · '+source.name,event=>openMaterialEditor('source',source.source_id,event.currentTarget))),
          styleDisclosure('材料状态与依据',status,verify));
      }
      return el('article',{class:'source-card stack'},el('strong',{},source.name), status,
        el('div', {class:'row wrap'}, verify, button('读取材料原文 '+source.name,()=>sourceReader(app,{source_id:source.source_id,source_version:{extract:source.extract}},readingRevision),false,{class:'text-link'})),
        app.readonly?el('p',{},source.usage_note):button('调整此材料 · '+source.name,event=>openMaterialEditor('source',source.source_id,event.currentTarget)));
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
      const ids = order.filter(id => chapterPages(chapter).has(id));
      const chapterPagesList = ids.map(id => pageMap.get(id)).filter(Boolean);
      if (!chapterPagesList.length) return null;
      const first = chapterPagesList[0], last = chapterPagesList[chapterPagesList.length - 1];
      const chapterGoals = goals.filter(goal => ids.includes(goal.page_id));
      const links = [...new Set(chapterGoals.flatMap(goal => goal.source_links.map(link => link.locator || '材料')))];
      // UX-04b（对账 §5「章节指定页、就近来源」）：章节内明确指定要打开的页，
      // 目标来源按钮也放在该块内，不再只能进入"首个匹配页"并到别处找来源。
      const pageChoice = el('select', {'aria-label': `章节内页面 ${chapter.title}`},
        chapterPagesList.map(page => el('option', {value: page.page_id}, `第 ${order.indexOf(page.page_id) + 1} 页 · ${page.title || '未命名页面'}`)));
      const targets = chapterGoals.flatMap(goal => goal.source_links.map(link => ({goal, link})));
      return el('div', {class: 'outline-block'},
        el('span', {class: 'mono'}, String(index + 1).padStart(2, '0')),
        el('div', {},
          el('h3', {}, chapter.title),
          el('p', {}, chapterGoals[0]?.purpose || ''),
          el('p', {class: 'small-text outline-source-note'},
            chapterPagesList.length > 1 ? `第 ${order.indexOf(first.page_id) + 1}–${order.indexOf(last.page_id) + 1} 页` : `第 ${order.indexOf(first.page_id) + 1} 页`,
            links.length ? ` · ${links.join('、')}` : ' · 未记录来源关联'),
          el('div', {class: 'row wrap outline-actions'}, pageChoice,
            button('打开所选页', () => app.go({surface: 'page', page_id: pageChoice.value, layer: 'content'}), false, {class: 'quiet'}),
            ...targets.slice(0, 4).map(({goal, link}) => button(`查看目标来源 · ${pageMap.get(goal.page_id)?.title || goal.page_id} · ${link.locator || '材料'}`,
              () => sourceReader(app, link), false, {class: 'text-link'})))));
    }).filter(Boolean);
  }
  function chapterPages(chapter) {
    if (Array.isArray(chapter.page_ids)) return new Set(chapter.page_ids);
    const chapterGoals = new Set(chapter.goal_ids);
    return new Set(goals.filter(goal => chapterGoals.has(goal.goal_id)).map(goal => goal.page_id));
  }
  function drawGoals() {
    const chapterFields=chapters.map(chapter=>{
      const name=inputField('章节名称 '+(chapters.indexOf(chapter)+1),chapter.title,2);
      name.input.addEventListener('input',()=>{chapter.title=name.input.value;changed();});return name.node;
    });
    let openEditor=null;
    const cards=goals.map(goal=>{
      const page=pageMap.get(goal.page_id);const purpose=inputField('页面目标 '+(page?.title || goal.page_id),goal.purpose,2);
      const unresolved=inputField('待确认事实 '+(page?.title || goal.page_id),goal.unresolved_facts.join('\n'),2);
      unresolved.input.readOnly = modernPlan;
      const reading=el('p',{},goal.purpose),facts=el('p',{class:'muted'},goal.unresolved_facts.length?'待确认：'+goal.unresolved_facts.join('；'):'未记录待确认事实');
      const sourceLinks=el('div',{class:'studio-goal-linked row wrap'});
      const renderLinks=()=>sourceLinks.replaceChildren(...(goal.source_links.length?goal.source_links.map(link=>button('查看目标来源 '+((inputs?.sources||[]).find(s=>s.source_id===link.source_id)?.name||'材料')+' · '+link.locator,()=>sourceReader(app,link))):[el('p',{class:'muted'},modernPlan?'尚未关联材料；请核对本页来源和已记录的未决事项，登记材料后再关联。':'尚未关联材料；请在待确认事实中说明依据缺口。')]));
      const update=()=>{reading.textContent=goal.purpose;facts.textContent=goal.unresolved_facts.length?'待确认：'+goal.unresolved_facts.join('；'):'未记录待确认事实';renderLinks();changed();};
      purpose.input.addEventListener('input',()=>{goal.purpose=purpose.input.value;update();});unresolved.input.addEventListener('input',()=>{goal.unresolved_facts=unresolved.input.value.split('\n').filter(v=>v.trim());update();});
      renderLinks();
      if(!studio)return el('div',{class:'goal-editor stack'},purpose.node,unresolved.node,sourceLinks);
      const sourceChoices=el('div',{class:'studio-goal-source-choices stack'});
      let choicesLoaded=false;
      const loadChoices=async()=>{
        if(choicesLoaded)return;choicesLoaded=true;sourceChoices.replaceChildren();
        const registered=inputs?.sources||[];
        if(!registered.length){sourceChoices.append(el('p',{class:'muted'},'尚未登记材料。可以先保留页面目标与待确认事实，登记材料后再关联。'));return;}
        for(const source of registered){
          const row=el('div',{class:'studio-goal-source-choice stack'},el('p',{class:'muted'},'正在读取 '+source.name+' 的固定材料位置…'));sourceChoices.append(row);
          const render=async()=>{
            try{
              const record=await sourceForGoal(source);if(disposed||!sourceChoices.isConnected)return;
              const locations=[...new Map((record.locators||[]).filter(r=>typeof r.locator==='string'&&r.locator).map(r=>[r.locator,r])).values()];
              const existing=goal.source_links.filter(l=>l.source_id===source.source_id),pageLabel='第 '+(pages.findIndex(p=>p.page_id===goal.page_id)+1)+' 页';
              const check=el('input',{type:'checkbox',checked:existing.length>0,disabled:!locations.length,'aria-label':'关联材料 '+source.name+' 到'+pageLabel});
              const picker=el('select',{'aria-label':'材料位置 '+source.name+' · '+pageLabel,disabled:!locations.length},locations.map(r=>el('option',{value:r.locator},r.locator+(r.text?' · '+String(r.text).replaceAll('\n',' ').slice(0,60):''))));
              if(existing.length===1&&canonical(existing[0].source_version)===canonical(record.source_version)&&locations.some(r=>r.locator===existing[0].locator))picker.value=existing[0].locator;
              const detail=el('p',{class:'muted'},existing.length>1?'已保留 '+existing.length+' 个位置；改选一个位置后将替换这份材料的现有关联。':existing.some(l=>canonical(l.source_version)!==canonical(record.source_version))?'现有关联属于旧材料版本；明确改选位置后才更新为本版。':'材料版本 '+String(record.source_version.original_sha256||record.source_version.extract?.sha256||'').slice(0,8));
              const apply=()=>{goal.source_links=goal.source_links.filter(l=>l.source_id!==source.source_id);if(check.checked)goal.source_links.push({source_id:source.source_id,source_version:structuredClone(record.source_version),locator:picker.value});update();detail.textContent=check.checked?'已选定 '+picker.value+'；预览并确认内容计划后生效。':'已取消这份材料的关联；预览并确认后生效。';};
              check.addEventListener('change',apply);picker.addEventListener('change',()=>{check.checked=true;apply();});
              row.replaceChildren(el('label',{class:'inline-control'},check,source.name),detail,locations.length?picker:el('p',{class:'muted'},'这份材料尚无可核实的位置，不能建立来源关联。请先完成材料读取。'),button('读取这版材料',()=>sourceReader(app,{source_id:source.source_id,source_version:record.source_version},readingRevision)));
            }catch(error){if(!disposed&&sourceChoices.isConnected)row.replaceChildren(el('p',{class:'field-error'},'读取 '+source.name+' 未完成：'+readableError(error)),button('重试读取材料位置 '+source.name,()=>render()));}
          };render();
        }
      };
      const edit=el('div',{class:'studio-goal-edit stack',hidden:true},purpose.node,el('h4',{},'登记来源与目标页'),el('p',{class:'muted'},'将已登记的固定版本材料关联到本页，并选择实际依据位置。关联不代表事实已核验。'),sourceChoices,unresolved.node);
      const trigger=button('编辑页面目标',()=>{
        if(openEditor&&openEditor!==edit){openEditor.hidden=true;openEditor.trigger.setAttribute('aria-expanded','false');}
        edit.hidden=!edit.hidden;trigger.setAttribute('aria-expanded',String(!edit.hidden));openEditor=edit.hidden?null:edit;
        if(!edit.hidden){loadChoices();purpose.input.focus();}
      },false,{'aria-expanded':'false'});edit.trigger=trigger;
      return el('article',{class:'studio-goal-card stack','data-goal-page':goal.page_id},el('h3',{},`第 ${pages.findIndex(p=>p.page_id===goal.page_id)+1} 页 · ${page?.title||goal.page_id}`),reading,facts,el('div',{class:'row wrap'},!app.readonly&&trigger),sourceLinks,edit);
    });
    goalList.replaceChildren(studio?el('div',{class:'studio-chapter-fields'},chapterFields):chapterFields,studio?el('div',{class:'studio-goal-grid'},cards):cards);
    if(app.readonly) for(const input of goalList.querySelectorAll('textarea'))input.readOnly=true;
    filterGoals();
  }
  function filterGoals(){
    if(!studio)return;
    const query=goalSearch.value.trim().toLocaleLowerCase();
    goalList.querySelectorAll('.studio-goal-card').forEach(card=>{const goal=goals.find(g=>g.page_id===card.dataset.goalPage);card.hidden=Boolean(query&&!`${card.querySelector('h3').textContent} ${goal?.purpose||''}`.toLocaleLowerCase().includes(query));});
  }
  goalSearch.addEventListener('input',filterGoals);
  function inputPreview() {
    inputImpact.querySelector('.material-upload-error')?.remove();
    if ([...uploads,...sourceRows.flatMap(source=>source.action==='replace'&&source.upload?[source.upload]:[])].some(item=>item.state!=='ready')) {
      inputImpact.prepend(el('p',{class:'field-error material-upload-error',role:'alert'},'先核实材料文件是否已接收，或从本次选择移除未完成项。原材料与输入保持。'));return;
    }
    const source_changes={add:additions.input.value.split('\n').map(p=>p.trim()).filter(Boolean).map(path=>({path})).concat(uploads.map(item=>({upload_id:item.upload_id}))),replace:[],remove:[],metadata:[]};
    for(const source of sourceRows){
      if(source.action==='replace')source_changes.replace.push({source_id:source.source_id,...(source.upload?{upload_id:source.upload.upload_id}:{path:source.path}),usage_note:source.usage_note});
      else if(source.action==='remove')source_changes.remove.push(source.source_id);
      else if(source.usage_note!==(inputs.sources.find(s=>s.source_id===source.source_id)?.usage_note || ''))source_changes.metadata.push({source_id:source.source_id,usage_note:source.usage_note});
    }
    const differences=[];
    if(brief.input.value!==inputs.task.brief)differences.push('用途：'+inputs.task.brief+' → '+brief.input.value);
    if(audience.input.value!==inputs.task.audience)differences.push('受众：'+inputs.task.audience+' → '+audience.input.value);
    if(decisions.input.value!==(inputs.task.existing_decisions || []).join('\n'))differences.push('既定决定：'+(inputs.task.existing_decisions || []).join('；')+' → '+decisions.input.value);
    for(const source of sourceRows)if(source.action!=='keep')differences.push((source.action==='remove'?'移除：':'替换：')+source.name+(source.action==='replace'?' → '+(source.upload?.name || source.path):''));
    for(const source of source_changes.add)differences.push('新增材料：'+(source.path || uploads.find(item=>item.upload_id===source.upload_id)?.name || '已接收材料'));
    for(const source of source_changes.metadata){const previous=inputs.sources.find(s=>s.source_id===source.source_id);differences.push('材料用途 · '+(previous?.name || source.source_id)+'：'+(previous?.usage_note || '未填写')+' → '+(source.usage_note || '未填写'));}
    completedAction='inputs';operation.previewInputs({reason:reason.input.value,task_patch:{brief:brief.input.value,audience:audience.input.value,existing_decisions:decisions.input.value.split('\n').filter(v=>v.trim())},source_changes},differences);
    adjustDetails.dataset.step='review';
    returnEdit.hidden=false;
  }
  function preview(action) {
    closeMaterialEditor(false);
    if(studio&&['merge','split'].includes(action)){
      const field=action==='merge'?mergeTitle:splitPoint;
      if(!field.input.value.trim()){
        adjustmentError.hidden=false;adjustmentError.textContent=action==='merge'?'先填写合并后的页面标题，再核对本次调整。':'先说明从哪里拆分、各页分别保留什么，再核对本次调整。';
        field.input.setAttribute('aria-invalid','true');field.input.focus();return;
      }
    }
    completedAction=action;
    const targets=['reorder','outline'].includes(action)?[]:[...selected].map(id=>({page_id:id,page_ref:pageMap.get(id).stages.content.ref}));
    const baseInstruction=instruction.input.value || ({reorder:'调整逐页稿顺序',remove:'移除明确选定的页面',outline:'调整内容计划中的章节和页面目标'}[action] || '');
    const actionInstruction=studio&&action==='merge'?['合并后的页面标题：'+mergeTitle.input.value.trim(),baseInstruction].filter(Boolean).join('\n'):studio&&action==='split'?['拆分位置与方式：'+splitPoint.input.value.trim(),baseInstruction].filter(Boolean).join('\n'):baseInstruction;
    if(studio){
      const area=action==='outline'?'plan':'pages';showContentArea(area,false);
      const requestReview=['merge','split','rewrite','remove'].includes(action)?el('div',{class:'content-request-review stack'},el('strong',{},'本次内容调整'),el('p',{},'目标：'+targets.map(t=>'第 '+(order.indexOf(t.page_id)+1)+' 页 · '+pageMap.get(t.page_id).title).join('、')),el('p',{class:'read-text'},actionInstruction),el('p',{class:'muted'},action==='remove'?'确认后移除选定页，历史版本仍可查看。':'确认后交接制作；制作工具返回并通过校验后才产生新稿，当前核对不改变页面。')):null;
      (area==='plan'?planReview:orderReview).replaceChildren(...[requestReview,operation.node,button('取消本次核对，保留编辑',changed)].filter(Boolean));
    }
    const value={content_plan_ref:ref,action,targets,instruction:actionInstruction};
    if(action==='reorder')value.page_order=order;
    if(action==='outline') {
      if(modernPlan) {
        const edited=new Map(goals.map(goal=>[goal.page_id,goal]));
        value.content_plan={...structuredClone(plan.input),chapters:structuredClone(chapters),
          page_roles:plan.input.page_roles.map(role=>{
            const goal=edited.get(role.page_id);
            return goal?{...structuredClone(role),intended_takeaway:goal.purpose,source_links:structuredClone(goal.source_links)}:structuredClone(role);
          })};
      } else value.content_plan={schema_version:'content_plan_input.v1',input_summary:summary.input.value,chapters,goals,unresolved_facts:plan.unresolved_facts || []};
    }
    operation.preview(value);
  }
  drawSources();drawPages();drawGoals();
  const hostImpact=el('div',{class:'stack content-impact'});
  const resolved=inputs?.content_basis?.resolved_by_task_id;
  if(resolved) get('/api/tasks/'+encodeURIComponent(resolved)+revisionQuery(readingRevision), {signal:controller.signal}).then(async result=>{
    if(disposed || result.task.status!=='completed')return;
    const receipt=await get('/api/operations/'+encodeURIComponent(result.task.operation_id), {signal:controller.signal});
    if(disposed)return;
    const adopted=receipt.operation_result;
    if (!adopted || receipt.status !== 'committed' || receipt.operation_id !== result.task.operation_id) throw new Error('尚未找到已采用的影响判断记录。');
    impactAdopted = [adopted.impact_summary, adopted.unchanged_reason].some(value => typeof value === 'string' && value.trim());
    for (const {source,node} of materialStatuses.values()) sourceState(source,node);
    hostImpact.replaceChildren(el('strong',{},impactAdopted ? (app.summary.input_alignment==='current'?'已采用的制作工具影响判断':'此前采用的制作工具判断（最新输入仍待协调）') : '已有内容结果，未记录可读的影响判断'),
      el('p',{},adopted.impact_summary || adopted.unchanged_reason || '该回合未记录可读的影响说明，不能补造理由。'),
      ...[adopted.impact_summary && adopted.unchanged_reason && el('p',{},'无正文变化依据：'+adopted.unchanged_reason)].filter(Boolean),
      el('p',{class:'muted'},impactAdopted ? '这是提交并采用的影响判断，仍需核对业务事实。' : '采用内容结果不表示已有影响判断，未补造读取或判断记录。'),
      button('查看这次内容整理',()=>app.go({surface:'runs',task_id:resolved,revision:readingRevision})));
  }).catch(error=>{if(!disposed)hostImpact.replaceChildren(el('p',{class:'muted'},'影响说明暂不可读：'+readableError(error)),el('p',{class:'muted'},'稿件与当前输入保留。可打开内容整理任务核实，或重新读取这个工作面。'));});
  const aligned=app.summary.input_alignment==='current';
  const editable = node => app.readonly ? node : operation.guard(node);
  // Registration, verified extraction, adopted impact and alignment have
  // independent evidence. A stored extract ref alone makes no reading claim.
  // 历史修订不加载当前输入的材料清单：不显示虚假的 0 份断言（评审 reading-P2）。
  // 三类入口共用宽编辑区和固定请求机制；历史版本不呈现编辑入口。
  const editorTitle=el('h2',{},'调整任务要求与材料');
  const returnEdit=button('返回编辑',()=>{changed();adjustDetails.dataset.step='edit';returnEdit.hidden=true;materialEditor.querySelector('textarea,select')?.focus();},false,{hidden:true});
  const operationHome=el('div',{class:'content-operation-home'},!app.readonly&&operation.node);
  const inputImpact=el('div',{class:'material-input-impact stack'});
  const inputFields=editable(el('div',{class:'material-input-fields stack'},retainedInputs,materialEditor,reason.node,button('预览材料与任务变化',inputPreview)));
  const adjustDetails = !app.readonly&&inputs ? el('details', {'data-container':'section',class:'panel materials-adjust-form',hidden:true,'data-step':'edit'},el('summary',{class:'panel-head'},'调整任务要求与材料'),
    el('div',{class:'panel-body stack'},editorTitle,el('div',{class:'material-edit-context'},inputFields,inputImpact),el('div',{class:'row wrap'},returnEdit,button('关闭编辑并保留草稿',()=>closeMaterialEditor())))) : null;
  function openMaterialEditor(kind,sourceId=null,trigger=document.activeElement) {
    if(!adjustDetails)return;
    if(adjustDetails.hidden)editReturnScroll={x:window.scrollX,y:window.scrollY};
    editTrigger=trigger;editKind=kind;editSourceId=sourceId;
    changed();returnEdit.hidden=true;adjustDetails.dataset.step='edit';
    const source=sourceRows.find(s=>s.source_id===sourceId);
    materialEditor.replaceChildren();
    if(kind==='source'&&source){
      editorTitle.textContent='调整材料 · '+source.name;
      const action=el('select',{'aria-label':'材料操作 '+source.name},el('option',{value:'keep'},'保留材料'),el('option',{value:'replace'},'替换为新版本'),el('option',{value:'remove'},'从当前输入移除'));
      action.value=source.action;
      const note=inputField('材料用途 '+source.name,source.usage_note,2),path=inputField('替换路径 '+source.name,source.path,2);
      path.node.hidden=source.action!=='replace';
      action.addEventListener('change',()=>{source.action=action.value;path.node.hidden=source.action!=='replace';changed();});
      note.input.addEventListener('input',()=>{source.usage_note=note.input.value;changed();});path.input.addEventListener('input',()=>{source.path=path.input.value;source.upload=null;changed();});
      const upload = app.health.ui_capabilities?.includes('material_uploads.v1') ? materialUploads(app,()=>source.upload?[source.upload]:[], (records,event)=>{source.upload=records[0]||null;if(source.upload&&event?.reason==='selected'){source.path='';path.input.value='';source.action='replace';action.value='replace';path.node.hidden=false;}changed();},{single:true}) : null;
      materialEditor.append(...[action,note.node,upload,path.node].filter(Boolean));
    } else {
      editorTitle.textContent=kind==='add'?'添加材料':'修改任务要求';
      if(kind==='add') materialEditor.append(...[app.health.ui_capabilities?.includes('material_uploads.v1') ? materialUploads(app,()=>uploads,records=>{uploads=records;changed();}) : null,additions.node].filter(Boolean));
      else materialEditor.append(brief.node,audience.node,decisions.node,el('p',{class:'muted'},'保留已明确的决定；需要改变时在此修改，并说明原因。'));
    }
    if (!inputImpact.contains(operation.node)) inputImpact.replaceChildren(operation.node);adjustDetails.hidden=false;adjustDetails.open=true;
    adjustDetails.scrollIntoView({block:'start'});(kind==='add'?additions.input:materialEditor.querySelector('textarea,select'))?.focus({preventScroll:true});
  }
  function closeMaterialEditor(focus=true) {
    if(disposed||!adjustDetails||adjustDetails.hidden)return;
    changed();operationHome.append(operation.node);adjustDetails.open=false;adjustDetails.hidden=true;returnEdit.hidden=true;
    if(focus){
      if(editTrigger?.isConnected){if(editReturnScroll)window.scrollTo(editReturnScroll.x,editReturnScroll.y);editTrigger.focus({preventScroll:true});}
      else node.querySelector('#view-title')?.focus();
    }
  }
  if(adjustDetails)adjustDetails.addEventListener('toggle',()=>{if(!adjustDetails.open&&!adjustDetails.hidden)closeMaterialEditor();});
  const openAdjustForm = event => openMaterialEditor('add',null,event?.currentTarget);
  const materialAside=el('aside',{'data-container':'section',class:'panel materials-aside','aria-label':'使用中的材料'},
    el('div',{class:'panel-head'},el('h2',{},'使用中的材料'),el('span',{class:'status'},inputs?(inputs.sources.length+' 份'):'历史版本')),
    el('div',{class:'panel-body stack'},inputs?sourceList:el('p',{class:'muted'},'材料清单按当前输入读取；正在看历史版本，未加载材料列表。'),
      el('p',{class:'muted'},aligned?'当前输入已由内容结果对齐；这不是独立事实核验。':'输入待协调：制作工具尚需按最新材料判断影响。'),
      el('p',{class:'footer-note muted'},'更新材料后，先确认受影响的页面，再比较修改结果。')));
  const integrationSummary=panel('内容整合',el('p',{},modernPlan?'当前内容计划按章节、页面目标与逐页职责记录。':plan?.input_summary||'尚未记录整合结论，已保存的逐页稿仍可阅读。'),el('p',{class:'muted'},`${pages.length} 页 · ${chapters.length} 个章节 · ${goals.filter(goal=>goal.unresolved_facts.length).length} 页有待确认事实`));
  const overview=el('div',{class:'content-layout'},el('section',{class:'stack'},
    studio?null:integrationSummary,
    ref?el('div',{class:'stack'},el('div',{class:'section-head'},el('h2',{},'方案大纲'),el('span',{class:'status'},'内容基准 '+version(ref?.sha256||ref))),...outlineBlocks()):panel('方案大纲',el('p',{},'尚未记录完整内容计划，当前仅能按逐页稿阅读。请交接内容整理。'))),materialAside);
  const orderAction=!app.readonly&&button('预览页序变更',()=>preview('reorder'));
  const orderHelp=el('p',{class:'muted'},'打开页面可改标题和正文。用移动按钮、拖动标题，或聚焦标题后按 Alt + ↑/↓ 调整顺序，再预览保存。');
  const adjustmentNames=[['rewrite','改写','预览选页改写'],['merge','合并','预览合并选页'],['split','拆分','预览拆分选页'],['remove','移除','预览移除选页']];
  const adjustmentButtons=adjustmentNames.map(([key,title])=>button(title,()=>showAdjustment(key),false,{'aria-pressed':String(key===adjustmentAction)}));
  const adjustmentPreview=button('预览选页改写',()=>preview(adjustmentAction));
  const adjustmentHelp=el('p',{class:'muted'});
  function showAdjustment(next,save=true){
    if(!adjustmentNames.some(([key])=>key===next))next='rewrite';adjustmentAction=next;
    adjustmentButtons.forEach((control,i)=>control.setAttribute('aria-pressed',String(adjustmentNames[i][0]===next)));
    splitPoint.node.hidden=next!=='split';mergeTitle.node.hidden=next!=='merge';adjustmentPreview.textContent=adjustmentNames.find(([key])=>key===next)[2];
    adjustmentHelp.textContent=next==='merge'?'选定至少两页，填写合并后的标题与保留要求。确认后交接制作，当前不直接创建新页。':next==='split'?'选定一页，说明拆分位置与各页内容。确认后交接制作，返回新稿后才能核对新页序。':next==='remove'?'确认后移除明确选定的页面；原稿仍保留在历史版本。':'改写保留页面身份。明确需要改变和保留的内容，再预览交接。';
    if(save)changed();
  }
  showAdjustment(adjustmentAction,false);
  const adjustmentTools=!app.readonly&&el('div',{class:'studio-content-adjust stack'},
    studio?el('div',{role:'group','aria-label':'选页调整方式',class:'row wrap'},adjustmentButtons):null,
    studio?adjustmentHelp:null,studio?mergeTitle.node:null,studio?splitPoint.node:null,instruction.node,studio?adjustmentError:null,
    studio?adjustmentPreview:el('div',{class:'row wrap'},button('预览移除选页',()=>preview('remove')),button('预览选页改写',()=>preview('rewrite')),button('预览合并选页',()=>preview('merge')),button('预览拆分选页',()=>preview('split'))),
    el('p',{class:'muted'},'改写保留页身份；合并/拆分由制作工具返回新页，旧标注仍保留在原基准。'));
  const pageTools=editable(el('div',{class:'stack'},studio?null:orderHelp,
    !studio&&orderAction&&el('div',{class:'studio-content-commandbar row wrap'},orderAction),
    el('div',{class:'content-order-scroll'},pageList),studio?orderHelp:null,adjustmentTools));
  const planEvidence=styleDisclosure('查看完整页面目标与原始依据',el('ol',{},goals.map(g=>el('li',{},g.purpose))),el('pre',{class:'evidence-json'},JSON.stringify({chapters:plan?.chapters,unresolved_facts:plan?.unresolved_facts},null,2)));
  const planAction=!app.readonly&&button('预览内容计划变更',()=>preview('outline'));
  const planTools=editable(el('div',{class:'stack'},el('p',{class:'muted'},modernPlan?'这里编辑章节、页面目标与来源关联；已记录的篇幅、时长、口播安排和未决事项保持。正文请进入对应页面修改。':'这里编辑章节、目标与待确认事实；正文请进入对应页面修改。'),summary.node,retainedSummary,studio&&goalSearch,goalList,!studio&&planAction));
  const planPanel=ref?panel('内容计划',planTools,planReview,planEvidence):panel('内容计划',el('p',{},'尚未记录完整内容计划。'));
  if(studio&&ref&&planAction)planPanel.querySelector('.panel-head').append(planAction);
  const orderPanel=panel('逐页编辑与顺序',pageTools,orderReview);
  if(studio&&orderAction)orderPanel.querySelector('.panel-head').append(orderAction);
  const alignmentDetail=el('p',{},aligned?'已有内容结果采用了这一版输入；这不是独立事实核验。':'已保存的稿件仍可阅读。制作工具尚需按最新材料、受众和用途判断影响。');
  const judgment=studio?el('div',{class:'stack studio-input-judgment'},alignmentDetail,integrationSummary,hostImpact):null;
  let judgmentDialog;
  const alignmentView=studio?button('查看输入判断',()=>{judgmentDialog=modal('输入判断与依据',judgment,[],{fallback:document.querySelector('#view-title')});}):null;
  app.disposables.push(()=>{if(judgmentDialog?.open&&judgmentDialog.contains(judgment))judgmentDialog.close();});
  const alignment=el('div',{class:(aligned?'notice':'history-banner')+' content-alignment'},el('strong',{},aligned?'当前输入已由内容结果对齐':'输入待协调'),studio?alignmentView:alignmentDetail);
  let area='overview';
  const workAreas=studio?[
    el('section',{class:'studio-content-area stack',id:'content-area-overview','aria-label':'方案概览'},overview),
    el('section',{class:'studio-content-area',id:'content-area-pages','aria-label':'逐页编辑与顺序',hidden:true},orderPanel),
    el('section',{class:'studio-content-area',id:'content-area-plan','aria-label':'内容计划',hidden:true},planPanel),
    el('section',{class:'studio-content-area',id:'content-area-notes','aria-label':'工作笔记',hidden:true},panel('工作笔记',draftNode))
  ]:[];
  const extraAreas=supportsInsights(app)?[['arguments','论证主线',argumentDesk(app)],...(app.health.ui_capabilities?.includes('method_library_preview.v1')?[['methods','方法与案例',()=>methodLibrary(app)]]:[])]:[];
  for(const [key,title,body] of extraAreas){const section=el('section',{class:'studio-content-area stack',id:'content-area-'+key,'aria-label':title,hidden:true},typeof body==='function'?null:body);if(typeof body==='function')section.loadContent=()=>{section.append(body());section.loadContent=null;};workAreas.push(section);}
  const areaNames=[['overview','方案概览'],['pages','逐页编辑与顺序'],['plan','内容计划'],['notes','工作笔记'],...extraAreas.map(([key,title])=>[key,title])];
  const areaButtons=studio?areaNames.map(([key,title])=>button(title,()=>showContentArea(key),false,{'aria-pressed':String(key===area),'aria-controls':'content-area-'+key})):[];
  const areaNav=studio?el('nav',{class:'studio-content-areas','aria-label':'内容工作区'},areaButtons):null;
  function showContentArea(next,focus=true){
    if(!studio||!areaNames.some(([key])=>key===next))return;area=next;
    if(focus){app.route.content_area=next;history.replaceState(null,'',routeHash(app.info,app.route));}
    workAreas.find(panel=>panel.id==='content-area-'+next)?.loadContent?.();
    workAreas.forEach((panel,index)=>{panel.hidden=areaNames[index][0]!==next;areaButtons[index].setAttribute('aria-pressed',String(!panel.hidden));});
    if(focus){const title=workAreas.find(p=>!p.hidden)?.querySelector('h2');if(title){title.tabIndex=-1;title.focus();}}
  }
  if(studio)operationHome.hidden=true;
  const node=el('div',{class:'content-sources stack'},heading('内容与来源','先看材料与论证，再改逐页稿。直接改内容和交接制作分别保存。',!app.readonly&&el('div',{class:'row wrap'},button('添加材料',openAdjustForm,false,{disabled:!inputs}),button('修改任务要求',event=>openMaterialEditor('task',null,event.currentTarget),false,{disabled:!inputs}))),
    alignment,studio?null:hostImpact,adjustDetails,areaNav,
    studio?workAreas:el('div',{class:'stack'},overview,el('details',{class:'panel content-order-panel'},el('summary',{class:'panel-head'},'逐页稿与顺序 · '+pages.length+' 页'),el('div',{class:'panel-body'},pageTools)),
      ref?panel('内容计划与依据',planEvidence,el('details',{},el('summary',{},'编辑内容计划'),planTools)):panel('内容计划',el('p',{},'尚未记录完整内容计划。'))),
    inputs?null:panel('历史材料',el('p',{},'此处只读固定版本的内容目标与来源，不混入当前任务要求。')),
    !studio&&extraAreas.map(([,title,body])=>panel(title,typeof body==='function'?body():body)),operationHome,studio?null:draftNode);
  if(studio&&app.route.content_area)showContentArea(app.route.content_area,false);
  if(studio&&app.contentArea){showContentArea(app.contentArea,false);delete app.contentArea;}
  if(app.readonly) for(const item of node.querySelectorAll('textarea'))item.readOnly=true;
  if(app.contentFocusPage){if(studio)showContentArea('pages',false);const focus=app.contentFocusPage;delete app.contentFocusPage;requestAnimationFrame(()=>pageList.querySelector('[data-page-id="'+CSS.escape(focus)+'"] .order-handle')?.focus());}
  return node;
}
