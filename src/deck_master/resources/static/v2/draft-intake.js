import {el, field} from './dom.js';
import {pageText} from './page-text.js';

// Only editable source bytes are held here. The server validates the manuscript
// and computes its actual write scope; this preview never grants authority.
export function draftIntake({required = false, onChange = () => {}, value = null} = {}) {
  const file = field(`确认稿 JSON 文件（${required ? '必填' : '可选'}）`,
    el('input', {type: 'file', accept: '.json,application/json', required}),
    '选择完整稿件 JSON。保留全部 pages；page_order 如有填写，须恰好包含每个页面。原文件只读，选择不会写入项目。');
  const notice = el('p', {role: 'status'}), preview = el('div', {class: 'stack'});
  let payload = null, pages = [], sequence = 0;
  const read = {node: el('div', {class: 'draft-intake stack'}, file.node, notice, preview), input: file.input,
    get payload() { return payload; }, get pages() { return pages; }};
  function accept(value) {
      if (!Array.isArray(value.pages) || !value.pages.length) throw new Error('确认稿需要完整的非空 pages 数组。');
      const ids = value.pages.map(page => page?.page_id);
      if (ids.some(id => typeof id !== 'string' || !id.trim()) || new Set(ids).size !== ids.length)
        throw new Error('每页需要非空且不重复的 page_id。');
      const order = value.page_order ?? ids;
      if (!Array.isArray(order) || order.length !== ids.length || new Set(order).size !== ids.length || order.some(id => !ids.includes(id)))
        throw new Error('page_order 必须恰好包含全部页面 ID，一页一次。');
      payload = value; pages = order.map(id => value.pages.find(page => page.page_id === id));
      file.input.setCustomValidity('');
      notice.textContent = `已读取完整稿件 ${pages.length} 页。以下为导入后的页序；尚未写入项目。`;
      preview.replaceChildren(el('ol', {}, pages.map(page => el('li', {}, page.customer_visible?.title || '未命名页面'))),
        el('details', {}, el('summary', {}, '完整源页 ID、正文与口播稿'),
          pages.map((page, index) => el('article', {class: 'stack'},
            el('h4', {}, `第 ${index + 1} 页 · ${page.page_id}`),
            el('pre', {class: 'read-text'}, pageText(page)),
            page.speaker_notes && el('pre', {class: 'read-text'}, page.speaker_notes))),
          el('details', {}, el('summary', {}, '原始完整 JSON'), el('pre', {class: 'evidence-json'}, JSON.stringify(value, null, 2)))));
  }
  file.input.setCustomValidity(required ? '请选择完整的确认稿 JSON 文件。' : '');
  file.input.addEventListener('change', async () => {
    const current = ++sequence;
    payload = null; pages = []; preview.replaceChildren(); onChange(null);
    file.input.required = required;
    const selected = file.input.files[0];
    file.input.setCustomValidity(selected || required ? '请选入有效的完整稿件。' : '');
    notice.textContent = '';
    if (!selected) return;
    file.input.setCustomValidity('正在读取完整稿件，请稍候。');
    try {
      if (selected.size > 1_800_000) throw new Error('确认稿超过本次可接收大小，请减少文件内容后重试。');
      const value = JSON.parse(await selected.text());
      if (current !== sequence) return;
      accept(value);
      onChange(value);
    } catch (error) {
      if (current !== sequence) return;
      file.input.setCustomValidity(error.message); notice.textContent = error.message + ' 原文件保持，请修正或重新选择。';
    }
  });
  if(value) { accept(value); file.input.required=false; notice.append(' 使用前一步保留的完整稿件；可重新选择替换。'); }
  return read;
}
