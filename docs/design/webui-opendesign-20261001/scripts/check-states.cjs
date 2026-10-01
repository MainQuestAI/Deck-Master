const fs=require('fs'),vm=require('vm'),assert=require('assert');
process.chdir(require('path').resolve(__dirname,'..'));
const store={};
function boot(hash='#text'){
 const handlers={},nodes={};const element=()=>({innerHTML:'',textContent:'',value:'',open:false,style:{},dataset:{},classList:{add(){},remove(){},toggle(){}},addEventListener(){},setAttribute(){},removeAttribute(){},focus(){},showModal(){this.open=true},close(){this.open=false},querySelector(){return null},querySelectorAll(){return []},append(){},setPointerCapture(){},getBoundingClientRect(){return {left:0,top:0,width:100,height:100}}});
 const document={activeElement:null,querySelector:s=>nodes[s]||(nodes[s]=element()),querySelectorAll:()=>[],createElement:element,addEventListener:(name,f)=>handlers[name]=f};
 const ctx={document,location:{hash},history:{replaceState(){}},localStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v},navigator:{clipboard:{writeText:async()=>{}}},setTimeout:()=>0,clearTimeout(){},console};ctx.window=ctx;ctx.addEventListener=()=>{};vm.createContext(ctx);for(const f of ['icons.js','states.js'])vm.runInContext(fs.readFileSync(f,'utf8'),ctx);
 return {ctx,handlers,nodes,run:s=>vm.runInContext(s,ctx)};
}
(async()=>{
 const b=boot();for(const scene of b.run('scenes')){b.run(`scene='${scene}';render()`);assert(b.nodes['#state-main'].innerHTML.length>500,scene)}
 b.run("scene='marquee';render()");await b.run("handle('save-marquee',{})");assert.equal(b.run('sample.marquee.notes.length'),0);assert(b.nodes['#marquee-error'].textContent);
 for(const [k,v] of Object.entries({x:90,y:10,w:20,h:40})){b.run(`document.querySelector('#marquee-${k}')`);b.nodes['#marquee-'+k].value=String(v);}
 await b.run("handle('apply-marquee',{})");assert.equal(b.run('sample.marquee.selection'),null);
 b.nodes['#marquee-x'].value='10';await b.run("handle('apply-marquee',{})");
 b.handlers.input({target:{id:'marquee-note',value:'保留责任说明'}});await b.run("handle('save-marquee',{})");assert.equal(b.run('sample.marquee.notes[0].selection.x'),.1);
 await b.run("handle('clear-marquee',{})");assert.equal(b.run('sample.marquee.notes[0].selection.x'),.1);
 b.run("document.querySelector('#marquee-canvas')");const canvas=b.nodes['#marquee-canvas'];b.handlers.pointerdown({target:{closest:()=>canvas},button:0,pointerId:1,clientX:10,clientY:20});b.handlers.pointermove({pointerId:1,clientX:70,clientY:80});b.handlers.pointerup({pointerId:1});assert.equal(b.run('sample.marquee.selection.w'),.6);
 b.handlers.pointerdown({target:{closest:()=>canvas},button:0,pointerId:2,clientX:10,clientY:20});b.handlers.pointermove({pointerId:2,clientX:100,clientY:100});b.handlers.pointercancel({pointerId:2});assert.equal(b.run('sample.marquee.selection.w'),.6);
 await b.run("handle('check-connection',{})");await b.run("handle('connection-fail',{})");assert.equal(b.run('sample.connection.status'),'failed');
 await b.run("handle('check-export',{})");assert.equal(b.run('sample.export.phase'),'idle');b.handlers.change({target:{dataset:{exportItem:'svg'},checked:true}});await b.run("handle('check-export',{})");assert.equal(b.run('sample.export.phase'),'reviewed');
 await b.run("handle('start-loading',{})");await b.run("handle('fail-loading',{})");await b.run("handle('start-loading',{})");await b.run("handle('finish-loading',{})");assert.equal(b.run('sample.loading.phase'),'done');

 const restored=boot('#marquee');assert.equal(restored.run('sample.marquee.notes.length'),1);assert.equal(restored.run('sample.marquee.selection.w'),.6);
 // Invalid and repeated transitions must preserve facts and drafts.
 b.run('sample=seed()');await b.run("handle('replay-original',{})");assert.equal(b.run('sample.unknown.status'),'unknown');
 b.run("sample.unknown.outcome='not_committed';sample.unknown.later='后写草稿'");await b.run("handle('check-unknown',{})");await b.run("handle('replay-original',{})");await b.run("handle('replay-original',{})");assert.equal(b.run('sample.unknown.history.length'),2);assert.equal(b.run('sample.unknown.later'),'后写草稿');
 await b.run("handle('new-later',{})");await b.run("handle('new-later',{})");assert.equal(b.run('sample.unknown.history.length'),3);
 await b.run("handle('rebase-conflict',{})");b.run("sample.conflict.newDraft='已经修改的新草稿'");await b.run("handle('rebase-conflict',{})");assert.equal(b.run('sample.conflict.newDraft'),'已经修改的新草稿');
 await b.run("handle('save-text',{})");assert.equal(b.run('sample.text.version'),16);b.run("sample.text.draft.title='修改标题'");await b.run("handle('save-text',{})");await b.run("handle('save-text',{})");assert.equal(b.run('sample.text.version'),17);
 await b.run("handle('new-batch-handoff',{})");assert.equal(b.run('sample.batch.newHandoff'),false);
 await b.run("handle('keep-batch',{})");await b.run("handle('adopt-batch',{})");assert.equal(b.run('sample.batch.adopted'),false);
 await b.run("handle('verify-batch',{})");await b.run("handle('cancel-batch',{})");await b.run("handle('close-dialog',{})");await b.run("handle('confirm-cancel-batch',{})");assert.equal(b.run('sample.batch.cancelled'),false);
 await b.run("handle('cancel-batch',{})");await b.run("handle('confirm-cancel-batch',{})");await b.run("handle('confirm-cancel-batch',{})");await b.run("handle('new-batch-handoff',{})");await b.run("handle('new-batch-handoff',{})");assert.equal(b.run('sample.batch.events.filter(x=>x.includes("Q34")).length'),1);
 await b.run("handle('return-structure',{})");assert.equal(b.run('sample.structure.candidate'),null);
 b.run("sample.structure.selected=['p-a1','p-b2']");await b.run("handle('request-structure',{})");await b.run("handle('confirm-request-structure',{})");const fixed=b.run('JSON.stringify(sample.structure.pages)');await b.run("handle('move-down',{dataset:{page:'p-a1'}})");assert.equal(b.run('JSON.stringify(sample.structure.pages)'),fixed);
 await b.run("handle('return-structure',{})");await b.run("handle('adopt-structure',{})");await b.run("handle('confirm-adopt-structure',{})");await b.run("handle('confirm-adopt-structure',{})");assert.equal(b.run('sample.structure.pages.length'),5);assert.equal(b.run('sample.structure.pages[0].sources.length'),2);
 await b.run("handle('confirm-restore',{})");assert.equal(b.run('sample.history.current'),18);const records=b.run('JSON.stringify(sample.history.records)');await b.run("handle('view-history',{})");await b.run("handle('compare-history',{})");await b.run("handle('restore-history',{})");await b.run("handle('confirm-restore',{})");assert.equal(b.run('sample.history.current'),19);assert.equal(b.run('JSON.stringify(sample.history.records)'),records);
 console.log('通过：非法/重复状态迁移、确认取消、重组锁定、历史恢复记录保留；10 场景初始化/渲染，空意见与越界校验，拖动及取消，意见固定快照，本地恢复，连接失败、导出清单及加载重试');
})().catch(e=>{console.error(e);process.exitCode=1});
