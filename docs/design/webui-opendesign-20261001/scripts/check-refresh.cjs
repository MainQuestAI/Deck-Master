const fs=require('fs'),vm=require('vm'),assert=require('assert');
process.chdir(require('path').resolve(__dirname,'..'));
const store={};
function boot(hash=''){
const handlers={};
const el=()=>({innerHTML:'',textContent:'',open:false,dataset:{},events:{},classList:{add(){},remove(){}},addEventListener(name,f){this.events[name]=f},setAttribute(){},closest(){return null},focus(){document.activeElement=this},querySelector(){return null},querySelectorAll(){return []}});
const nodes={};const document={activeElement:null,querySelector:s=>nodes[s]||(nodes[s]=el()),getElementById:id=>nodes['#'+id]||null,querySelectorAll:()=>[],addEventListener:(n,f)=>handlers[n]=f};
const ctx={document,location:{hash},localStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v},navigator:{clipboard:{writeText:async()=>{}}},console,setTimeout:()=>0,clearTimeout(){},requestAnimationFrame:f=>f(),getComputedStyle:()=>({paddingLeft:'24px',paddingRight:'24px'}),innerWidth:1440};ctx.window=ctx;ctx.addEventListener=()=>{};ctx.scrollTo=()=>{};

vm.createContext(ctx);for(const name of ['icons.js','app.js'])vm.runInContext(fs.readFileSync(name,'utf8'),ctx);return {ctx,nodes,document,run:s=>vm.runInContext(s,ctx)};
}
const first=boot('#gallery');first.run("state.galleryStage='svg';state.galleryColumns=4;state.layout='continuous';state.filter='missing';state.search='服务';state.right='note';state.styleRequirement='';state.page=12;state.stage='svg';state.notes[noteKey()]='保留箭头';state.regions[noteKey()]={x:.1,y:.1,w:.2,h:.3};addTask('刷新测试','固定要求');render()");
const second=boot('#gallery');assert.equal(second.run('state.galleryStage'),'svg');assert.equal(second.run('state.filter'),'missing');assert.equal(second.run('state.search'),'服务');assert.equal(second.run('state.styleRequirement'),'');assert.equal(second.run('state.tasks[0].status'),'queued');assert.equal(second.document.activeElement,second.nodes['#view-title']);assert.equal(second.run('state.marking'),false);
const page=boot('#page/12/svg');assert.equal(page.run('state.page'),12);assert.equal(page.run('state.notes[noteKey()]'),'保留箭头');assert.equal(page.run('state.region.w'),.2);assert.equal(page.run('state.right'),'note');assert.equal(page.run('state.search'),'');
const noHash=boot();assert.equal(noHash.run('state.route'),'page');assert.equal(noHash.run('state.page'),12);
store['deck-master-v3-demo']=JSON.stringify({dataVersion:2,view:{route:'invalid',page:99,stage:'broken',galleryColumns:100,filter:'invalid'}});const invalid=boot();assert.equal(invalid.run('state.route'),'overview');assert.equal(invalid.run('state.page'),8);assert.equal(invalid.run('state.galleryColumns'),3);
store['deck-master-v3-demo']='null';assert.equal(boot().run('state.route'),'overview');store['deck-master-v3-demo']='broken';assert.equal(boot().run('state.route'),'overview');
console.log('通过：新上下文刷新恢复、URL 优先、无 URL 恢复、草稿/选区/任务不推进、标题焦点、无效存储回退');
