const layers = {content: '正文', original_image: '原图', svg: 'SVG', svg_preview: 'SVG 预览', ppt: 'PPT', membership: '页面范围', basis: '制作依据'};
export function historyLabel(item, pageLabels = new Map()) {
  const date = item.committed_at ? new Date(item.committed_at) : null;
  const time = date && Number.isFinite(date.getTime()) ? date.toLocaleString('zh-CN', {hour12: false}) : '时间未记录';
  const pages = item.changed_pages || [];
  const changed = pages.slice(0, 3).map(row => {
    const label = pageLabels.get(row.page_id) || (/^p\d+$/.test(row.page_id) ? `第 ${Number(row.page_id.slice(1))} 页` : '页面');
    return `${label} ${(row.layers || []).map(key => layers[key] || '产物').join('/')}`;
  }).join('、');
  const scope = changed ? changed + (pages.length > 3 ? ` 等 ${pages.length} 页` : '') : item.outputs_changed ? '整稿输出' : item.order_changed ? '页面顺序' : '';
  return `${time} · ${item.action || '项目更新'}${scope ? ' · ' + scope : ''}`;
}
