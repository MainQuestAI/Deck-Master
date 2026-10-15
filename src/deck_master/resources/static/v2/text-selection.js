import {post, readableError} from './api.js';
import {el, button, field, modal, actionGroup} from './dom.js';

export function boundaries(text) {
  const offsets = [0]; let position = 0;
  for (const point of text) { position += point.length; offsets.push(position); }
  return offsets;
}
export function codePointOffset(text, utf16) {
  const index = boundaries(text).indexOf(utf16);
  if (index < 0) throw new Error('选区落在字符内部，请重新选择完整字符。');
  return index;
}
export function makeRange(source, start, end) {
  const points = Array.from(source.text);
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || start >= end || end > points.length)
    throw new Error('请输入有效范围：起点小于终点，且位于原文长度内。');
  return {schema_version: 'text_range.v1', ref: source.ref, locator: source.locator,
    text_sha256: source.text_sha256, start, end, excerpt: points.slice(start, end).join('')};
}
// A single original text node preserves CRLF and combining marks; no textarea
// normalization or DOM-rendered innerText is used for contract coordinates.
export function selectionRange(pre, source, selection = getSelection()) {
  if (!selection?.rangeCount || selection.isCollapsed) return null;
  const range = selection.getRangeAt(0);
  const offset = (node, value) => {
    if (node === pre.firstChild && node.nodeType === Node.TEXT_NODE) return value;
    if (node === pre && (value === 0 || value === 1)) return value ? source.text.length : 0;
    throw new Error('请选择同一个原文对象内的文本。');
  };
  if (!pre.contains(range.startContainer) || !pre.contains(range.endContainer)) return null;
  return makeRange(source, codePointOffset(source.text, offset(range.startContainer, range.startOffset)),
    codePointOffset(source.text, offset(range.endContainer, range.endOffset)));
}

// A range edit is bound to one exact leaf and its current draft text. The
// content transaction still owns the immutable page basis and final CAS.
export function rangeReplacementEditor({label, draft, read, writable, save, apply, fallback}) {
  let value = structuredClone(draft), validated = null, replacementText = null, capturedRange = null;
  const original = el('pre', {class:'read-text selectable-text', tabindex:0, 'aria-label':'选段原文'}, value.source);
  const start = field('起始字符（从 1 计）', el('input',{type:'number',min:1,value:value.start+1}));
  const end = field('结束字符（含）', el('input',{type:'number',min:1,value:value.end}));
  const replacement = field('替换文字（留空删除选段）',el('textarea',{rows:3,value:value.replacement}));
  const status = el('p',{role:'status'}), review = el('div',{class:'stack',hidden:true});
  const form = el('div',{class:'stack'});
  // Focusing the capture button can collapse the browser's native selection.
  // Snapshot only a real selection made within this exact original text node.
  const captureNative = () => {
    try { const range=selectionRange(original,{text:value.source});if(range)capturedRange=range; }
    catch(error){capturedRange=null;status.textContent=error.message;}
  };
  original.addEventListener('pointerup',captureNative);original.addEventListener('keyup',captureNative);
  function current() {
    if(!writable())throw Error('当前版本已变化或暂不可编辑。范围草稿保留，请读取当前版本后重新定位。');
    if(read()!==value.source)throw Error('这个正文位置已被修改。范围草稿保留，请按当前文字重新定位。');
  }
  function changed() {
    value.start=Number(start.input.value)-1;value.end=Number(end.input.value);value.replacement=replacement.input.value;
    validated=null;replacementText=null;review.replaceChildren();review.hidden=true;form.hidden=false;compare.disabled=true;use.disabled=true;
    save(structuredClone(value));status.textContent='范围草稿已保留；校验后核对具体改动。';
  }
  const capture = button('使用当前选段',()=>{
    try {
      const selected=selectionRange(original,{text:value.source})||capturedRange;
      if(!selected)throw Error('先在上方原文选择同一个字段内的文字。');
      start.input.value=selected.start+1;end.input.value=selected.end;changed();
    }catch(error){status.textContent=error.message;}
  });
  const validate=button('校验替换选段',()=>{
    try {
      current();validated=makeRange({text:value.source},Number(start.input.value)-1,Number(end.input.value));
      status.textContent=`已校验第 ${validated.start+1}–${validated.end} 字：${validated.excerpt}`;
      compare.disabled=false;
    }catch(error){validated=null;compare.disabled=true;status.textContent=error.message;}
  });
  const compare=button('比较选段原文与改文',()=>{
    try {
      current();if(!validated)throw Error('请先校验当前选段。');
      const points=Array.from(value.source);
      replacementText=points.slice(0,validated.start).join('')+replacement.input.value+points.slice(validated.end).join('');
      review.replaceChildren(el('h3',{},'仅修改这个位置'),el('p',{},label),
        actionGroup(use,button('返回调整选段',()=>{review.hidden=true;form.hidden=false;use.disabled=true;dialog.scrollTo(0,0);start.input.focus();})),
        el('p',{},`第 ${validated.start+1}–${validated.end} 字 · 其余同文位置保持不变`),
        el('strong',{},'原文'),el('pre',{class:'read-text'},validated.excerpt),
        el('strong',{},'改文'),el('pre',{class:'read-text'},replacement.input.value||'（删除该选段）'));
      use.disabled=false;form.hidden=true;review.hidden=false;dialog.scrollTo(0,0);use.focus();
    }catch(error){use.disabled=true;status.textContent=error.message;}
  },false,{disabled:true});
  const use=button('应用到正文草稿并查看影响',async()=>{
    try {
      current();if(replacementText===null)throw Error('请先核对这次具体改动。');
      const next=replacementText;use.disabled=true;
      // apply rechecks the leaf before updating it and uses contentOperation.
      await apply(next,value.source);
      // #modal is shared. A newer editor may have replaced this one while
      // content planning was in flight; its inputs and focus belong to it.
      if(dialog.contains(body))dialog.close();
    }catch(error){status.textContent=error.message;use.disabled=true;}
  },true,{disabled:true});
  for(const input of [start.input,end.input,replacement.input])input.addEventListener('input',changed);
  const rebase=button('按当前文字重新定位',()=>{
    value.source=read();capturedRange=null;original.textContent=value.source;start.input.value=1;end.input.value=Math.min(1,Array.from(value.source).length);changed();
  });
  form.append(el('p',{},label),
    el('p',{class:'muted'},'拖选下方原文或填写字符范围。空替换会删除选段；确认内容变更前不会改动正式稿件。'),original,
    actionGroup(capture,rebase),el('div',{class:'range-fields'},start.node,end.node),replacement.node,
    actionGroup(validate,compare));
  const body=el('div',{class:'stack'},form,review,status);
  const dialog=modal('精确修改选段',body,[button('取消并保留范围草稿',()=>dialog.close())],{fallback,protectDraft:true});
  return {dispose(){if(dialog.open&&dialog.contains(body))dialog.close();}};
}
export function textObject(app, source, {revision, pageId, layer, label = '原始文本'} = {}) {
  const pre = el('pre', {class: 'read-text selectable-text', tabindex: '0', 'aria-label': label}, source.text);
  const note = el('p', {class: 'muted', role: 'status'});
  const excerpt = el('blockquote', {class: 'range-excerpt', hidden: true});
  const start = field('选段起点', el('input', {type: 'number', min: 0, max: source.code_point_length, value: 0}));
  const end = field('选段终点', el('input', {type: 'number', min: 1, max: source.code_point_length, value: Math.min(1, source.code_point_length)}));
  let serial = 0;
  const capture = () => {
    try { const selected = selectionRange(pre, source); if (selected) { start.input.value = selected.start; end.input.value = selected.end; note.textContent = '选段待校验，原文保持不变。'; } }
    catch (error) { note.textContent = error.message; }
  };
  pre.addEventListener('pointerup', capture); pre.addEventListener('keyup', capture);
  const validate = button('校验原文选段', async () => {
    const token = ++serial;
    try {
      const selection = makeRange(source, Number(start.input.value), Number(end.input.value));
      validate.disabled = true; note.textContent = '正在核对原始对象、版本与摘录…';
      const result = await post('/api/text-ranges/validate', {page_id: pageId, layer, revision_id: revision, selection});
      if (token !== serial || !pre.isConnected) return;
      excerpt.textContent = result.selection.excerpt; excerpt.hidden = false;
      note.textContent = `选段已校验 · [${selection.start}, ${selection.end}) · 仅定位原文，尚未保存意见。`;
      pre.dispatchEvent(new CustomEvent('text-range-validated', {bubbles: true, detail: result}));
    } catch (error) { if (token === serial) note.textContent = readableError(error); }
    finally { if (token === serial) validate.disabled = false; }
  });
  if (!app.health.ui_capabilities?.includes('text_range.v1')) validate.disabled = true;
  const controls = el('details', {class: 'text-range-tools'}, el('summary', {}, '定位原文选段'),
    el('p', {class: 'muted'}, `原文 ${source.code_point_length} 个 Unicode 码点。可用鼠标或键盘选择，也可输入起止位置；组合字和换行保留原样。`),
    el('div', {class: 'range-fields'}, start.node, end.node, validate), note, excerpt);
  return el('div', {class: 'text-object'}, pre, controls);
}
