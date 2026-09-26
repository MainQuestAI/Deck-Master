// User text is always a text node. The only parsed markup is our bundled icon.
export function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'class') node.className = value;
    else if (key === 'value' || key === 'checked' || key === 'disabled' || key === 'readOnly') node[key] = value;
    else node.setAttribute(key, value === true ? '' : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}
export const button = (text, action, primary = false, props = {}) => el('button', {
  type: 'button', class: primary ? 'primary' : '', onclick: action, ...props,
}, text);
export function icon(name) {
  const svg = new DOMParser().parseFromString(window.uiIcon(name).replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" '), 'image/svg+xml').documentElement;
  return document.importNode(svg, true);
}
export function toast(message) {
  const target = document.querySelector('#toast');
  target.textContent = message;
  target.classList.add('visible');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => target.classList.remove('visible'), 4500);
}
export function announce(message) { document.querySelector('#route-status').textContent = message; }
export function modal(title, body, actions = []) {
  const dialog = document.querySelector('#modal');
  const trigger = document.activeElement;
  const heading = el('h2', {id: 'dialog-title'}, title);
  dialog.replaceChildren(el('div', {class: 'modal-body'}, heading, body,
    el('div', {class: 'modal-actions'}, button('关闭', () => dialog.close()), actions)));
  dialog.setAttribute('aria-labelledby', heading.id);
  dialog.className = '';
  if (!dialog.open) dialog.showModal();
  dialog.onclose = () => { if (trigger?.isConnected) trigger.focus(); };
  return dialog;
}
export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast('已复制，尚未开始。请在制作工具中发送。'); }
  catch { modal('复制制作要求', el('textarea', {'aria-label': '制作要求', readOnly: true, rows: 10, value: text})); }
}
export const version = (revision) => revision ? `R ${revision.slice(0, 8)}` : '当前版本';
export function field(label, input, help = '') {
  input.id ||= `field-${crypto.randomUUID()}`;
  const error = el('p', {class: 'field-error', role: 'alert', id: `${input.id}-error`});
  const helpNode = el('p', {class: 'muted field-help', id: `${input.id}-help`}, help);
  input.setAttribute('aria-describedby', `${helpNode.id} ${error.id}`);
  return {node: el('div', {class: 'field'}, el('label', {for: input.id}, label), input, helpNode, error), input, error};
}
export function heading(title, explanation, action) {
  return el('div', {class: 'page-head'}, el('div', {},
    el('h1', {id: 'view-title', tabindex: '-1'}, title), explanation && el('p', {}, explanation)), action);
}
export function empty(title, detail, action) {
  return el('section', {class: 'zero-state stack'}, el('h2', {}, title), el('p', {class: 'muted'}, detail), action);
}
export function downloadJSON(value, name) {
  const objectURL = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2) + '\n'], {type: 'application/json'}));
  const link = el('a', {href: objectURL, download: name});
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(objectURL), 1000);
}
