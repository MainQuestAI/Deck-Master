import {el, button} from './dom.js';

// Reuse the mounted immutable canvas and its annotation overlay. The legacy
// route.zoom remains a container multiplier; native-pixel zoom is view-local.
export function pageReading(reading, {identity, legacyZoom = 1} = {}) {
  const viewport = reading.querySelector('.page-image-viewport');
  if (!viewport?.querySelector('.pooled-image')) return {dispose() {}};
  reading.classList.add('studio-page-reading');
  const caption = el('p', {class:'studio-reading-identity'}, identity);
  const status = el('output', {'aria-live':'polite'});
  let canvas = null, disposed = false, frame = 0, wasFullscreen = false;
  let mode = legacyZoom === 1 ? 'fit' : 'legacy', zoom = legacyZoom;
  const fit = button('适应窗口', () => change('fit', 1), false, {'aria-pressed':'false'});
  const native = button('100%', () => change('native', 1), false, {'aria-label':'原生 100% 阅读','aria-pressed':'false'});
  const smaller = button('−', () => change('native', currentScale()/1.25), false, {'aria-label':'缩小图稿'});
  const larger = button('+', () => change('native', currentScale()*1.25), false, {'aria-label':'放大图稿'});
  const fullscreen = button('全屏阅读', async () => {
    try {
      if (document.fullscreenElement === reading) await document.exitFullscreen();
      else await reading.requestFullscreen();
    } catch { status.textContent = '当前窗口未允许全屏；仍可适应窗口或放大阅读。'; }
  }, false, {'aria-pressed':'false'});
  const controls = el('div', {class:'studio-reading-controls',role:'group','aria-label':'单页图稿阅读'}, fit,native,smaller,larger,status,fullscreen);
  reading.prepend(caption,controls);
  function currentScale() { return canvas ? canvas.getBoundingClientRect().width/canvas.width : 1; }
  function center() {
    if (!canvas) return {x:.5,y:.5};
    const box=canvas.getBoundingClientRect(), view=viewport.getBoundingClientRect();
    return {x:Math.max(0,Math.min(1,(view.left+viewport.clientWidth/2-box.left)/box.width)),y:Math.max(0,Math.min(1,(view.top+viewport.clientHeight/2-box.top)/box.height))};
  }
  function redraw(point = null) {
    if (disposed || !reading.isConnected) return;
    const next=viewport.querySelector('canvas.page-image');
    if(next!==canvas)canvas=next;
    for(const control of [fit,native,smaller,larger,fullscreen])control.disabled=!canvas;
    if(!canvas){status.textContent=viewport.querySelector('[data-image-state="failed"]')?'图片暂不可读，请使用下方的重试图片。':'图片读取完成后可调整阅读。';return;}
    const top=viewport.getBoundingClientRect().top;
    const height=Math.max(180,Math.min(document.fullscreenElement===reading?innerHeight:innerHeight*.65,innerHeight-top-20));
    viewport.style.height=`${height}px`;
    const style=getComputedStyle(viewport), padX=parseFloat(style.paddingLeft)+parseFloat(style.paddingRight), padY=parseFloat(style.paddingTop)+parseFloat(style.paddingBottom);
    const width=Math.max(1,viewport.clientWidth-padX), availableHeight=Math.max(1,viewport.clientHeight-padY);
    const scale=mode==='fit'?Math.min(width/canvas.width,availableHeight/canvas.height):mode==='legacy'?width*zoom/canvas.width:zoom;
    const holder=canvas.parentElement;
    holder.style.width=`${canvas.width*scale}px`;holder.style.height=`${canvas.height*scale}px`;
    canvas.style.width=`${canvas.width*scale}px`;canvas.style.height=`${canvas.height*scale}px`;
    viewport.dataset.readingMode=mode;viewport.dataset.readingScale=String(scale);
    fit.setAttribute('aria-pressed',String(mode==='fit'));native.setAttribute('aria-pressed',String(mode==='native'&&zoom===1));
    status.textContent=mode==='fit'?`适应窗口 · ${Math.round(scale*100)}%`:mode==='legacy'?`已恢复版面比例 ${Math.round(zoom*100)}%`:`原生像素 ${Math.round(zoom*100)}%`;
    if(point)viewport.scrollTo(Math.max(0,point.x*canvas.width*scale-width/2),Math.max(0,point.y*canvas.height*scale-availableHeight/2));
    else if(mode==='fit')viewport.scrollTo(0,0);
  }
  function schedule(){if(disposed||frame)return;frame=requestAnimationFrame(()=>{frame=0;redraw();});}
  function change(nextMode,value){const point=center();mode=nextMode;zoom=Math.max(.1,Math.min(8,value));redraw(nextMode==='fit'?null:point);}
  const observed=new MutationObserver(schedule);observed.observe(viewport,{childList:true,subtree:true});
  const resize=new ResizeObserver(schedule);resize.observe(viewport);resize.observe(reading);
  const fullscreenChanged=()=>{
    const active=document.fullscreenElement===reading;
    fullscreen.textContent=active?'退出全屏':'全屏阅读';fullscreen.setAttribute('aria-pressed',String(active));
    if(wasFullscreen&&!active&&reading.isConnected&&!disposed)fullscreen.focus({preventScroll:true});
    wasFullscreen=active;
    schedule();
  };
  const escape=event=>{if(event.key==='Escape'&&document.fullscreenElement===reading&&!document.querySelector('dialog[open]')){event.preventDefault();event.stopPropagation();document.exitFullscreen().catch(()=>{});}};
  reading.addEventListener('keydown',escape,true);
  document.addEventListener('fullscreenchange',fullscreenChanged);
  addEventListener('resize',schedule);addEventListener('scroll',schedule,{passive:true});
  schedule();
  return {dispose(){disposed=true;cancelAnimationFrame(frame);observed.disconnect();resize.disconnect();reading.removeEventListener('keydown',escape,true);document.removeEventListener('fullscreenchange',fullscreenChanged);removeEventListener('resize',schedule);removeEventListener('scroll',schedule);if(document.fullscreenElement===reading)document.exitFullscreen().catch(()=>{});}};
}
