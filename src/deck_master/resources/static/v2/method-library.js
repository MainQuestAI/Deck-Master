import {el,button,copyText} from './dom.js';
import {get,post,readableError} from './api.js';
import {details} from './insight-reading.js';
import {DraftEditor} from './drafts.js';
export function methodLibrary(app){
  const root=el('section',{class:'stack'},el('h2',{},'方法与案例准备'),el('p',{},'这里准备阅读与交接，不改变已有任务，也不启动制作。方法案例不是客户来源。'));
  const select=new Set(),status=el('p',{role:'status'}),list=el('div',{class:'method-catalog'}),result=el('div',{class:'stack'}),body=el('pre',{class:'read-text',tabindex:'0'});
  const kinds={instruction:'方法说明',example:'案例',template:'模板',data:'数据',script:'脚本（只读）'};
  const search=el('input',{type:'search','aria-label':'筛选方法或案例',placeholder:'按资源名称或 ID 筛选'});
  search.addEventListener('input',()=>{for(const row of list.children)row.hidden=!row.textContent.toLowerCase().includes(search.value.toLowerCase());});
  const role=el('select',{'aria-label':'方法阅读角色'},['deck-content','deck-review','deck-design','deck-master'].map(r=>el('option',{value:r},r)));
  const mode=el('select',{'aria-label':'准备上下文'},el('option',{value:'project'},'本项目的下一内容阶段'),el('option',{value:'independent'},'独立阅读，不产生项目许可'));
  const phase=el('select',{'aria-label':'方法阅读阶段'},['argument','page_copy','speech','review','production'].map(r=>el('option',{value:r},({argument:'论证策划',page_copy:'正文写作',speech:'口播',review:'审阅',production:'设计制作'})[r])));
  const reviewScopes={argument:['argument'],page_copy:['page_copy'],speech:['speech'],review:['argument','page_copy','progression'],production:['blueprint_content','blueprint_fidelity','readability']};
  const unitNames={argument:'论证',page_copy:'正文',progression:'衔接',speech:'口播',content:'内容',blueprint_content:'画面内容',blueprint_fidelity:'忠实度',conversion:'转换',readability:'可读性',privacy:'隐私'};
  let reviewUnits=[...reviewScopes[phase.value]];
  const scopeNote=el('p',{class:'muted',hidden:true});
  function showScope(){scopeNote.hidden=mode.value!=='independent'||role.value!=='deck-review';scopeNote.textContent='审阅范围：'+reviewUnits.map(unit=>unitNames[unit]||unit).join('、')+'。只准备这些范围，不发起审阅。';}
  for(const input of [mode,role,phase])input.disabled=true;
  const draft=new DraftEditor(app.info,{scope:'project',page_id:null,layer:'notes'},app.route.revision,null,{exactRevision:true,contextKey:'method-preparation'});const draftNode=draft.mount();draft.input.id='method-draft-'+crypto.randomUUID();draftNode.querySelector('label[for=personal-draft]')?.setAttribute('for',draft.input.id);draft.input.setAttribute('aria-label','方法准备备注');draft.stateNode.className='method-draft-state';draftNode.querySelector('h2').textContent='个人准备稿';draft.saveButton.textContent='保存方法准备稿';
  let disposed=false,serial=0,bodySerial=0,current=null;app.disposables.push(()=>{disposed=true;serial++;bodySerial++;draft.dispose();});
  function context(){return mode.value==='project'?{mode:'project',revision:app.route.revision}:{mode:'independent',role:role.value,phase:phase.value,review_units:role.value==='deck-review'?[...reviewUnits]:[]};}
  function retain(){draft.draft.content.method_preparation={ids:[...select],context:context()};draft.changed();current=null;result.replaceChildren();body.textContent='';}
  for(const input of [mode,role,phase])input.addEventListener('change',()=>{if(input===phase||input===role)reviewUnits=[...reviewScopes[phase.value]];showScope();retain();load();});
  async function load(){bodySerial++;body.textContent='';const ticket=++serial;status.textContent='正在核对目录与范围…';try{const value=await post('/api/method-library/preview',{context:context(),selected_resource_ids:[...select]});if(disposed||ticket!==serial)return;current=value;status.textContent=value.browse_status==='partial'?'部分资源暂不可读，选择已保留；核实完备前不可复制。':value.selection_status==='validated'?'准备已核对，尚未应用。':'目录可浏览；当前没有可准备的新阶段。';
    // Keep the clicked checkbox alive while its dependent preview returns.
    const rows=new Map([...list.children].map(row=>[row.dataset.resourceId,row]));
    list.replaceChildren(...value.entries.filter(e=>e.kind!=='instruction'||e.selectable||select.has(e.id)).map(entry=>{
      const signature=JSON.stringify([entry.display_name,entry.kind,entry.reason_codes]);
      let row=rows.get(entry.id);
      if(!row||row.dataset.signature!==signature){
        const checkbox=row?.querySelector('input')||el('input',{type:'checkbox',onchange:event=>{event.target.checked?select.add(entry.id):select.delete(entry.id);retain();load();}});
        row=el('label',{class:'method-entry','data-resource-id':entry.id,'data-signature':signature},checkbox,el('span',{},entry.display_name+' · '+kinds[entry.kind]),entry.reason_codes.length?details('不可选原因',entry.reason_codes):null);
      }
      const input=row.querySelector('input');input.checked=select.has(entry.id);input.disabled=!entry.selectable&&!select.has(entry.id);
      row.hidden=!row.textContent.toLowerCase().includes(search.value.toLowerCase());return row;
    }));
    result.replaceChildren(details('默认、显式、依赖与字节',value),...value.resolved_manifest.map(r=>button('阅读 '+r.id,()=>readResource(value,r))),button('重新核对后复制准备要求',async()=>{try{const checked=await post('/api/method-library/preview',{context:value.context,selected_resource_ids:value.explicit_ids,expected_basis:{catalog_digest:value.catalog_digest,context_digest:value.context_digest}});if(disposed||current!==value)return;if(!checked.handoff.copy_allowed)throw Error('所选资源尚未完整核验，请保留选择并重新预览。');if(checked.preview_digest!==value.preview_digest){current=null;result.replaceChildren();throw Error('资源字节已变化，请保留选择并重新预览。');}await copyText(checked.handoff.text);}catch(e){status.textContent=readableError(e);}},false,{disabled:!value.handoff.copy_allowed}));
  }catch(error){if(!disposed&&ticket===serial){current=null;status.textContent=readableError(error);result.replaceChildren();}}}
  async function readResource(value,r){const ticket=++bodySerial;body.textContent='';try{const text=await get('/api/method-library/resources/'+encodeURIComponent(r.id)+'?'+new URLSearchParams({catalog_digest:value.catalog_digest,sha256:r.sha256}));if(!disposed&&current===value&&ticket===bodySerial){body.textContent=text.content;body.focus();}}catch(error){if(!disposed&&current===value&&ticket===bodySerial)status.textContent=readableError(error);}}
  root.append(el('div',{class:'row wrap'},mode,role,phase,button('重新核对准备',load)),scopeNote,status,search,list,result,body,el('details',{},el('summary',{},'保存与恢复个人准备稿'),draftNode));
  function hydratePreparation(){if(disposed)return;serial++;current=null;result.replaceChildren();body.textContent='';select.clear();const saved=draft.draft.content.method_preparation;for(const id of saved?.ids||[])select.add(id);mode.value=saved?.context?.mode==='independent'?'independent':'project';if(mode.value==='independent'){role.value=saved.context.role;phase.value=saved.context.phase;reviewUnits=saved.context.review_units?.length?[...saved.context.review_units]:[...(reviewScopes[phase.value]||reviewScopes.review)];}showScope();load();}
  draft.onRestore=copy=>{if(!draft.restoreInPlace(copy))return false;hydratePreparation();return true;};
  draft.onRebase=(next,previous)=>{const saved=previous.content.method_preparation;if(saved)next.content.method_preparation={ids:[...saved.ids],context:saved.context.mode==='project'?{mode:'project',revision:draft.baseRevision}:structuredClone(saved.context)};};
  draft.onRebased=hydratePreparation;
  draft.ready.then(()=>{if(disposed)return;hydratePreparation();for(const input of [mode,role,phase])input.disabled=false;});return root;
}
