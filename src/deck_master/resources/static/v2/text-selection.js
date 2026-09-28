import {post, readableError} from './api.js';
import {el, button, field} from './dom.js';

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
