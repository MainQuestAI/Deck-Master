import {el, button, empty} from './dom.js';
import {imageView} from './images.js';

// Same immutable previews, one shared tool set. 100% means one preview pixel
// per CSS pixel; normalized image centers keep differently sized previews aligned.
export function comparisonCanvas(app, panels, {fullscreenTarget = null} = {}) {
  if (!document.querySelector('link[data-comparison-canvas]')) {
    const sheet=el('link',{rel:'stylesheet',href:new URL('./comparison-canvas.css',import.meta.url).href,'data-comparison-canvas':''});
    document.head.append(sheet);
  }
  const node=el('section',{class:'comparison-canvas','aria-label':'图稿比较画布'});
  const pair=el('div',{class:'comparison-pair'}),status=el('output',{'aria-live':'polite'});
  const sync=el('input',{type:'checkbox',checked:true,'aria-label':'同步缩放和平移'});
  const views=[];let active=0,disposed=false;
  const dimension=(item,axis)=>((axis==='x'?item.canvas?.width:item.canvas?.height)||0)*item.scale;
  const frame=(item,axis)=>axis==='x'?item.viewport.clientWidth:item.viewport.clientHeight;
  const padding=(item,axis)=>Math.max(0,frame(item,axis)-dimension(item,axis))/2;
  const center=item=>Object.fromEntries(['x','y'].map(axis=>[axis,Math.max(0,Math.min(1,((axis==='x'?item.viewport.scrollLeft:item.viewport.scrollTop)+frame(item,axis)/2-padding(item,axis))/Math.max(1,dimension(item,axis))))]));
  const move=(item,point)=>item.viewport.scrollTo(Math.max(0,point.x*dimension(item,'x')+padding(item,'x')-frame(item,'x')/2),Math.max(0,point.y*dimension(item,'y')+padding(item,'y')-frame(item,'y')/2));
  function redraw(item,point=null){
    if(!item.canvas)return;
    item.scale=item.mode==='fit'?Math.min(item.viewport.clientWidth/item.canvas.width,item.viewport.clientHeight/item.canvas.height):item.zoom;
    item.scale=Math.max(.000001,item.scale);
    item.canvas.style.width=`${item.scale*item.canvas.width}px`;item.canvas.style.height=`${item.scale*item.canvas.height}px`;
    item.viewport.dataset.zoom=String(item.scale);item.viewport.dataset.mode=item.mode;
    if(point)move(item,point);else if(item.mode==='fit')item.viewport.scrollTo(0,0);
  }
  function describe(){const item=views[active];if(item)status.textContent=(sync.checked?'':'仅 '+panels[active].label+' · ')+(item.mode==='fit'?'适应窗口':`${Math.round(item.zoom*100)}%`);}
  function changeZoom(value){
    const origin=views[active],point=origin.canvas?center(origin):{x:.5,y:.5};
    const mode=value==='fit'?'fit':'native',zoom=value==='fit'?1:Math.max(.1,Math.min(8,value));
    for(const item of sync.checked?views:[origin]){item.mode=mode;item.zoom=zoom;redraw(item,mode==='fit'?null:point);}
    describe();
  }
  const fullscreen=button('全屏比较',async()=>{
    try{if(document.fullscreenElement)await document.exitFullscreen();else await(fullscreenTarget||node).requestFullscreen();}
    catch{status.textContent='当前窗口不支持全屏，可使用100%与局部滚动。';}
  });
  const fullscreenChanged=()=>{fullscreen.textContent=document.fullscreenElement?'退出全屏':'全屏比较';views.forEach(v=>redraw(v));};
  document.addEventListener('fullscreenchange',fullscreenChanged);
  const controls=el('div',{class:'toolbar canvas-tools'},button('适应窗口',()=>changeZoom('fit')),button('100%',()=>changeZoom(1)),
    button('缩小',()=>changeZoom(views[active].scale/1.25)),button('放大',()=>changeZoom(views[active].scale*1.25)),status,
    el('label',{class:'inline-control'},sync,'同步'),fullscreen);
  sync.addEventListener('change',()=>{if(sync.checked)changeZoom(views[active].mode==='fit'?'fit':views[active].zoom);else describe();});
  panels.forEach((panel,index)=>{
    const column=el('section',{class:'candidate-column',...(panel.attributes||{})},el('h2',{},panel.label),panel.caption&&el('p',{class:'muted'},panel.caption));
    const viewport=el('div',{class:'comparison-viewport',tabindex:0,'aria-label':panel.label+' · 可放大并滚动'});
    const item={viewport,canvas:null,mode:'fit',zoom:1,scale:1};views.push(item);
    const activate=()=>{active=index;describe();};viewport.addEventListener('focus',activate);viewport.addEventListener('pointerdown',activate);
    if(panel.stage?.file){
      const view=imageView(app,panel.stage,panel.label,{kind:'large',onReady:canvas=>{item.canvas=canvas;redraw(item);describe();},onFailure:null});
      item.dispose=()=>view.dispose();viewport.append(view.node);
    }else viewport.append(empty('尚无'+panel.label,panel.missing||'此版本尚未生成这一层。'));
    viewport.addEventListener('scroll',()=>{
      if(disposed||!sync.checked||item.mode==='fit'||index!==active||!item.canvas)return;
      const point=center(item);for(const other of views){if(other===item||!other.canvas)continue;const current=center(other);
        if(Math.abs(current.x-point.x)>.001||Math.abs(current.y-point.y)>.001)move(other,point);
      }
    });
    let drag=null;
    viewport.addEventListener('pointerdown',event=>{if(item.mode==='fit'||event.button!==0||event.target.closest('button'))return;drag={id:event.pointerId,x:event.clientX,y:event.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};viewport.setPointerCapture(event.pointerId);});
    viewport.addEventListener('pointermove',event=>{if(drag?.id===event.pointerId)viewport.scrollTo(drag.left+drag.x-event.clientX,drag.top+drag.y-event.clientY);});
    const stop=()=>{drag=null;};viewport.addEventListener('pointerup',stop);viewport.addEventListener('pointercancel',stop);viewport.addEventListener('lostpointercapture',stop);
    viewport.addEventListener('keydown',event=>{if(event.ctrlKey||event.metaKey)return;if(event.key==='+'||event.key==='='){event.preventDefault();changeZoom(item.scale*1.25);}else if(event.key==='-'){event.preventDefault();changeZoom(item.scale/1.25);}else if(event.key==='0'){event.preventDefault();changeZoom('fit');}});
    column.append(viewport);pair.append(column);
  });
  const resize=new ResizeObserver(()=>{if(!disposed){views.forEach(v=>{if(v.mode==='fit')redraw(v);});describe();}});views.forEach(v=>resize.observe(v.viewport));
  node.append(controls,pair);describe();
  return {node,dispose(){disposed=true;resize.disconnect();document.removeEventListener('fullscreenchange',fullscreenChanged);views.forEach(v=>v.dispose?.());
    if(document.fullscreenElement===node||(fullscreenTarget&&document.fullscreenElement===fullscreenTarget))document.exitFullscreen().catch(()=>{});}};
}
