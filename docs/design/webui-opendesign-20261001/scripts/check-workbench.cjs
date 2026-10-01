const fs=require('fs'),vm=require('vm'),assert=require('assert');
process.chdir(require('path').resolve(__dirname,'..'));
const store={},handlers={};
const el=()=>({innerHTML:'',textContent:'',open:false,dataset:{},events:{},classList:{add(){},remove(){}},addEventListener(name,f){this.events[name]=f},setAttribute(){},closest(){return null},focus(){document.activeElement=this},querySelector(){return null},querySelectorAll(){return []}});
const nodes={};const document={activeElement:null,querySelector:s=>nodes[s]||(nodes[s]=el()),getElementById:id=>nodes['#'+id]||null,querySelectorAll:()=>[],addEventListener:(n,f)=>handlers[n]=f};
const ctx={document,location:{hash:'#overview'},localStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v},navigator:{clipboard:{writeText:async()=>{}}},console,setTimeout:()=>0,clearTimeout(){},requestAnimationFrame:f=>f(),getComputedStyle:()=>({paddingLeft:'24px',paddingRight:'24px'}),innerWidth:1440};ctx.window=ctx;ctx.addEventListener=()=>{};ctx.scrollTo=()=>{};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('icons.js','utf8'),ctx);vm.runInContext(fs.readFileSync('app.js','utf8'),ctx);
// Focus identity supports controls without IDs and preserves text selection.
const control=el();control.dataset={odId:'select-gallery-filter'};document.activeElement=control;
const replacement=el();replacement.dataset={odId:'select-gallery-filter'};document.querySelectorAll=s=>s==='[data-od-id]'?[replacement]:[];
const identity=vm.runInContext('focusIdentity()',ctx);assert.equal(identity.odId,'select-gallery-filter');ctx.testIdentity=identity;assert(vm.runInContext('restoreFocus(testIdentity)',ctx));assert.equal(document.activeElement,replacement);
replacement.disabled=true;assert.equal(vm.runInContext('restoreFocus(testIdentity)',ctx),false);replacement.disabled=false;
const text=el();text.id='focus-text';text.selectionStart=2;text.selectionEnd=5;nodes['#focus-text']=text;document.activeElement=text;ctx.testIdentity=vm.runInContext('focusIdentity()',ctx);text.setSelectionRange=(a,b)=>{assert.equal(a,2);assert.equal(b,5)};assert(vm.runInContext('restoreFocus(testIdentity)',ctx));
// Missing controls fall back to the page title.
document.activeElement=control;document.querySelectorAll=()=>[];vm.runInContext('render()',ctx);assert.equal(document.activeElement,nodes['#view-title']);
// Native control arrow keys and modified shortcuts do not turn the page.
vm.runInContext("state.route='page';state.page=8",ctx);
for(const tagName of ['INPUT','TEXTAREA','SELECT','BUTTON','SUMMARY','A'])handlers.keydown({key:'ArrowRight',target:{tagName},preventDefault(){throw Error('native key intercepted')}});
assert.equal(vm.runInContext('state.page',ctx),8);handlers.keydown({key:'ArrowRight',altKey:true,target:{tagName:'MAIN'},preventDefault(){throw Error('shortcut intercepted')}});assert.equal(vm.runInContext('state.page',ctx),8);
let prevented=false;handlers.keydown({key:'ArrowRight',target:{tagName:'MAIN'},preventDefault(){prevented=true}});assert(prevented);assert.equal(vm.runInContext('state.page',ctx),9);
// Modal Escape must not switch annotation mode underneath it.
nodes['#modal'].open=true;vm.runInContext('state.marking=true',ctx);handlers.keydown({key:'Escape',target:{tagName:'BUTTON'},preventDefault(){throw Error('modal Escape intercepted')}});assert(vm.runInContext('state.marking',ctx));nodes['#modal'].open=false;vm.runInContext('state.marking=false',ctx);
// Closing a dialog after navigation must not steal the new page focus.
vm.runInContext("dialogReturnRoute='page/8/image';dialogReturnFocus={odId:'select-gallery-filter'}",ctx);const newFocus=el();document.activeElement=newFocus;nodes['#modal'].events.close();assert.equal(document.activeElement,newFocus);
// Tab wraps inside the dialog in both directions.
const first=el(),last=el();for(const item of [first,last]){item.tabIndex=0;item.getClientRects=()=>[{}]}nodes['#modal'].querySelectorAll=()=>[first,last];document.activeElement=last;let wrapped=false;nodes['#modal'].events.keydown({key:'Tab',shiftKey:false,preventDefault(){wrapped=true}});assert(wrapped);assert.equal(document.activeElement,first);nodes['#modal'].events.keydown({key:'Tab',shiftKey:true,preventDefault(){}});assert.equal(document.activeElement,last);
// Same-page close returns to the surviving trigger.
document.querySelectorAll=s=>s==='[data-od-id]'?[replacement]:[];vm.runInContext("dialogReturnRoute=[state.route,state.page,state.stage].join('/');dialogReturnFocus={odId:'select-gallery-filter'}",ctx);nodes['#modal'].events.close();assert.equal(document.activeElement,replacement);document.querySelectorAll=()=>[];
for(const route of ['projects','overview','content','gallery','style','runs','page']){vm.runInContext(`state.route='${route}';render()`,ctx);assert(nodes['#app'].innerHTML.length>500,route)}
vm.runInContext(`state.route='page';state.page=8;const checkTask=addTask('验证请求','保持现稿');`,ctx);
(async()=>{const index=vm.runInContext('state.tasks.indexOf(checkTask)',ctx);for(const action of ['task-copy-'+index,'task-cancel-'+index]){await handlers.click({target:{closest:()=>({dataset:{action}})}})}assert.equal(vm.runInContext('checkTask.status',ctx),'cancelled');assert(store['deck-master-v3-demo']);const before=vm.runInContext('checkTask.id',ctx);vm.runInContext('retryTask(checkTask)',ctx);assert.equal(vm.runInContext('state.tasks[0].retryOf',ctx),before);assert.equal(vm.runInContext('checkTask.status',ctx),'cancelled');console.log('通过：焦点身份/文本选区/标题回退/控件方向键/弹窗关闭；7 个路由渲染；保存→复制→取消→新建重试；本地持久化。')})().catch(e=>{console.error(e);process.exitCode=1});
