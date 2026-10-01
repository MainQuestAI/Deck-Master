// 完整正文文本化（无 DOM 依赖，供候选比较与回归测试共用）。
// 覆盖 Page 合同 customer_visible 的全部字段：title/subtitle、body_blocks
// （段落/嵌套列表/含表头的表格）、labels、footnotes、callouts。块类型带可读
// 前缀，字段级修改（如表头单位、脚注口径）必然改变输出（终审补丁 P2）。
const bulletItems = items => (items || []).map(item => typeof item === 'string' ? item
  : [item.text, item.children?.length ? bulletItems(item.children).join('；') : ''].filter(Boolean).join('：'));

const blockText = block => {
  if (block.type === 'paragraph') return ['[段落]', block.text];
  if (block.type === 'bullets') return ['[列表]', block.heading, ...bulletItems(block.items)];
  if (block.type === 'table') return ['[表格]', block.title,
    ...((block.columns || []).map(col => col.label).filter(Boolean).length ? ['表头：' + block.columns.map(col => col.label || '').join(' | ')] : []),
    ...(block.rows || []).map(row => (row.cells || []).map(cell => cell.display_text || '').join(' | '))];
  return ['[块]', JSON.stringify(block)];
};

export function pageText(page) {
  const visible = page?.customer_visible;
  if (!visible) return '（正文暂不可读）';
  const lines = [];
  if (visible.title !== undefined) lines.push('[标题]', visible.title);
  if (visible.subtitle) lines.push('[副标题]', visible.subtitle);
  for (const block of visible.body_blocks || []) lines.push(...blockText(block));
  for (const key of ['callouts', 'labels', 'footnotes'])
    for (const item of visible[key] || []) lines.push(`[${{callouts: '强调', labels: '标签', footnotes: '脚注'}[key]}]`, item.text);
  return lines.filter(line => line !== '' && line !== undefined).join('\n');
}
