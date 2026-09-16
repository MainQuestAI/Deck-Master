import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const [modulePath,inputPath,outputPath]=process.argv.slice(2);
const {Presentation,PresentationFile}=await import(pathToFileURL(modulePath).href);
const input=JSON.parse(await fs.readFile(inputPath,'utf8'));
const pres=Presentation.create({slideSize:{width:input.width,height:input.height}});
function paint(color,alpha=1){
 if(color==='none')return 'none';
 if(alpha===1)return color;
 if(/^#[0-9a-f]{6}$/i.test(color))return color+Math.round(Math.max(0,Math.min(1,alpha))*255).toString(16).padStart(2,'0');
 throw Error('Unsupported translucent color '+color);
}
for(const page of input.pages){
 const slide=pres.slides.add(),k=input.width/page.width;
 for(const s of page.shapes){
  const cfg={name:s.atom_id||s.id,fill:paint(s.fill,s.opacity*s.fill_opacity),line:{fill:paint(s.stroke,s.opacity*s.stroke_opacity),width:s.stroke_width*k}};
  if(s.kind==='text'){
   // Native text uses top-aligned boxes; CJK em ascent is 0.88.
   const em=s.font_size*k;
   const estimated=[...s.text].reduce((n,c)=>n+(/[\u0000-\u007f]/.test(c)?0.61:1),0)*em;
   const width=Math.max(estimated+em*.35,em);
   let x=s.x*k;
   if(s.anchor==='middle')x-=width/2;
   if(s.anchor==='end')x-=width;
   const sh=slide.shapes.add({geometry:'textbox',name:cfg.name,position:{left:x,top:s.y*k-em*.88,width,height:em*1.45},fill:'none',line:{fill:'none',width:0}});
   sh.text=s.text;
   sh.text.style={typeface:s.font_family,fontSize:em,bold:s.bold,color:cfg.fill,alignment:s.anchor==='middle'?'center':s.anchor==='end'?'right':'left',verticalAlignment:'top',autoFit:'none',wrap:'none',insets:{top:0,right:0,bottom:0,left:0}};
  }else if(['rect','circle','ellipse'].includes(s.kind)){
   slide.shapes.add({...cfg,geometry:s.kind==='rect'?'rect':'ellipse',position:{left:s.x*k,top:s.y*k,width:s.width*k,height:s.height*k},...(s.rx?{borderRadius:s.rx*k}:{})});
  }else{
   const commands=s.commands||s.points.map((p,i)=>({[i?'lineTo':'moveTo']:{x:p[0],y:p[1]}}));
   if(s.kind==='polygon')commands.push({close:{}});
   const points=commands.flatMap(c=>c.moveTo?[c.moveTo]:c.lineTo?[c.lineTo]:[]);
   const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
   const left=Math.min(...xs),top=Math.min(...ys),w=Math.max(.01,Math.max(...xs)-left),h=Math.max(.01,Math.max(...ys)-top);
   const local=commands.map(c=>c.close?c:Object.fromEntries(Object.entries(c).map(([op,p])=>[op,{x:(p.x-left)*k,y:(p.y-top)*k}])));
   slide.shapes.add({...cfg,geometry:'custom',position:{left:left*k,top:top*k,width:w*k,height:h*k},customPaths:[{width:w*k,height:h*k,commands:local}]});
  }
 }
}
await (await PresentationFile.exportPptx(pres)).save(outputPath);
