import {el} from './dom.js';

// Exact line comparison (including CRLF). Large input retains both full sides
// without a quadratic line diff; it never rewrites either stored prompt.
export function diffText(left, right) {
  if (left === right) return {mode: 'exact', rows: [{kind: 'same', text: left}]};
  const a = left.match(/[^\n]*\n|[^\n]+$/g) || [], b = right.match(/[^\n]*\n|[^\n]+$/g) || [];
  if (a.length * b.length > 250000 || left.length + right.length > 200000) {
    return {mode: 'full_sides', rows: [{kind: 'removed', text: left}, {kind: 'added', text: right}]};
  }
  const width = b.length + 1, table = new Uint32Array((a.length + 1) * width);
  for (let i = a.length - 1; i >= 0; i--) for (let j = b.length - 1; j >= 0; j--)
    table[i * width + j] = a[i] === b[j] ? 1 + table[(i + 1) * width + j + 1] : Math.max(table[(i + 1) * width + j], table[i * width + j + 1]);
  const rows = []; let i = 0, j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) rows.push({kind: 'same', text: a[i++]}), j++;
    else if (i < a.length && (j === b.length || table[(i + 1) * width + j] >= table[i * width + j + 1])) rows.push({kind: 'removed', text: a[i++]});
    else rows.push({kind: 'added', text: b[j++]});
  }
  return {mode: 'lines', rows};
}
export function diffView(left, right, leftLabel, rightLabel) {
  const result = diffText(left, right);
  return el('section', {class: 'prompt-diff stack', 'aria-label': '提示词原文差异'},
    el('p', {}, `${leftLabel} → ${rightLabel}`),
    el('p', {class: 'muted'}, result.mode === 'exact' ? '原文完全一致；一致不代表已经实际提交。' : result.mode === 'full_sides' ? '文本较长，保留双方全文对照，未计算逐行差异。' : '按原文逐行比较；－为左侧独有，＋为右侧独有。未归一换行或组合字符。'),
    el('div', {class: 'diff-lines'}, result.rows.map(row => el('div', {class: 'diff-row ' + row.kind},
      el('span', {'aria-label': row.kind === 'removed' ? '左侧独有' : row.kind === 'added' ? '右侧独有' : '相同'}, {removed: '－', added: '＋', same: '＝'}[row.kind]), el('pre', {}, row.text)))));
}
