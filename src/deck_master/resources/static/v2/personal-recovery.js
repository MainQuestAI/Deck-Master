import {get, post, readableError} from './api.js';
import {el, button, modal, actionGroup} from './dom.js';

const actions = {restore:'恢复空记录', copy:'另存一份草稿，保留当前稿', keep:'保留当前记录'};
function fields(value, prefix = '') {
  if(value == null)return prefix?[[prefix,'无']]:[];
  if(typeof value !== 'object')return [[prefix,String(value)]];
  return Object.entries(value).filter(([key])=>!['schema_version','digest','etag','updated_sequence','sequence','updated_at','project_id','project_identity','draft_id'].includes(key)).flatMap(([key, child])=>fields(child,prefix?`${prefix}.${key}`:key));
}
function difference(row) {
  const current = new Map(fields(row.current)), saved = new Map(fields(row.backup));
  const keys = [...new Set([...current.keys(), ...saved.keys()])].filter(key=>current.get(key)!==saved.get(key));
  const root=el('div',{class:'stack'});let offset=0;
  function draw(){root.replaceChildren(el('p',{},`${keys.length} 个不同字段 · 第 ${Math.floor(offset/40)+1} 页`),
    el('table',{class:'data-table recovery-differences'},el('thead',{},el('tr',{},['字段','当前记录','备份记录'].map(label=>el('th',{},label)))),
      el('tbody',{},keys.slice(offset,offset+40).map(key=>el('tr',{},el('td',{},key),el('td',{},current.get(key)||'无'),el('td',{},saved.get(key)||'无'))))),
    actionGroup(button('上一组字段',()=>{offset-=40;draw();},false,{disabled:offset===0}),button('下一组字段',()=>{offset+=40;draw();},false,{disabled:offset+40>=keys.length})));}
  draw();return root;
}
function summary(record) {
  if(!record)return '没有已保存记录';
  if(record.unreadable)return '现有记录无法核实，将完整保留';
  if(record.draft){const text=record.draft.content.text;return text?(text.length>120?text.slice(0,120)+'…':text):'包含意见、选择或任务阅读设置';}
  if(record.seen)return `${record.seen.length} 项已读记录`;
  if(record.states)return `${record.states.length} 份版本阅读设置`;
  if(record.position)return `阅读 ${record.position.page_id||'工作面'} · ${record.position.surface}`;
  return `${record.state?.selected_page_ids?.length||0} 页选择 · ${record.state?.references?.length||0} 份参考`;
}
function recordCard(row) {
  const body=el('div',{class:'panel-body stack'}),card=el('section',{class:'panel'},body);
  function read(){body.replaceChildren(...[el('strong',{},`${row.label} · ${actions[row.action]}`),
    el('p',{},`当前：${summary(row.current)}`),el('p',{},`备份：${summary(row.backup)}`),
    row.existing_copy?el('p',{class:'muted'},'这份备份已恢复为独立草稿，现有副本保留。'):null,
    button('查看逐字段差异',()=>body.replaceChildren(el('strong',{},row.label),button('返回记录摘要',read),difference(row)))].filter(Boolean));}
  read();return card;
}
export function personalBackupButton(app) {
  return button('查看清理备份', async()=>{
    const content=el('div',{class:'stack'}), status=el('p',{role:'status'});
    const dialog=modal('个人状态备份',el('div',{class:'stack'},
      el('p',{},'备份属于本项目。已完成清理的备份可预览恢复：只补回空记录，同名草稿另存，已有阅读设置保留。已结束旧操作的恢复记录可下载核对；结束不代表清理成功。项目内容、任务与候选不会改变。'),content,status));
    async function load() {
      try {
        const [listing, ended]=await Promise.all([get('/api/ui-state/backups'), get('/api/ui-state/clear-recovery')]);
        if(!dialog.open)return;
        content.replaceChildren(...listing.backups.map(row=>el('article',{class:'panel'},el('div',{class:'panel-body stack'},
          el('strong',{},`${row.cleared_at} · ${row.available?`${row.count} 项记录`:'备份待核实'}`),
          row.available?actionGroup(el('a',{class:'download-link',href:`/api/ui-state/backups/${row.backup_id}/download`,download:''},'下载清理备份'),
            button('预览恢复这份备份',()=>preview(row.backup_id),false,{disabled:app.readonly})):el('p',{},row.reason)))));
        content.append(...ended.recoveries.map(row=>el('article',{class:'panel'},el('div',{class:'panel-body stack'},
          el('strong',{},'已结束的旧清理操作'),
          el('p',{},row.available?`${row.ended_at} · 保留 ${row.count} 项备份记录；结束不代表清理成功。`:row.reason),
          row.available?el('a',{class:'download-link',href:`/api/ui-state/clear-recovery/${encodeURIComponent(row.operation_id)}/download`,download:''},'下载旧操作恢复记录'):null))));
        if(!listing.backups.length && !ended.recoveries.length)content.append(el('p',{},'尚无清理备份。确认清理后会在这里保留。'));
      }catch(error){status.replaceChildren(el('p',{},readableError(error)),button('重新读取备份',load));}
    }
    async function preview(backup_id) {
      status.textContent='正在核对当前记录…';
      try {
        const plan=await post('/api/ui-state/plan-restore',{backup_id});
        if(!dialog.open)return;
        const review=el('div',{class:'stack'},el('h3',{},'恢复前核对'),plan.records.map(recordCard));
        const confirm=button('确认恢复并保留当前记录',async()=>{
          confirm.disabled=true;
          try {
            const result=await post('/api/ui-state/restore',{backup_id,plan_digest:plan.plan_digest});
            if(!dialog.open)return;
            const restored=result.records.filter(row=>row.status==='restored').length,kept=result.records.filter(row=>row.status==='kept').length;
            status.textContent=`已恢复 ${restored} 项，保留当前 ${kept} 项。`+(result.status==='partial'?'仍有未恢复项，请重新预览核对。':'');
            content.replaceChildren(el('p',{},'原清理备份继续保留。'),
              ...result.records.filter(row=>row.status==='failed').map(row=>el('p',{class:'field-error'},`${row.id}：${row.reason}`)),
              actionGroup(button('重新预览核对',()=>preview(backup_id)),button('返回备份列表',()=>{status.textContent='';load();})));
          }catch(error){status.textContent=readableError(error)+' 当前新记录保留。请重新预览。';confirm.disabled=true;}
        },true,{disabled:!plan.records.some(row=>row.action!=='keep')});
        content.replaceChildren(actionGroup(confirm,button('返回备份列表',()=>{status.textContent='';load();}),button('重新预览核对',()=>preview(backup_id))),review);
        status.textContent='确认前不写入。记录若在核对后变化，会要求重新预览。';
        dialog.scrollTo(0,0);
      }catch(error){status.textContent=readableError(error);}
    }
    await load();
  });
}
