export const surfaces = {overview: '制作总览', content: '内容与来源', gallery: '整稿画廊', style: '风格校准', runs: '任务与交付'};
export const layers = {content: '逐页稿', original_image: '原图', svg: 'SVG', ppt: 'PPT', prepared_prompt: '预备提示词', submitted_prompt: '实际提示词'};
export function readRoute(info, position, summary) {
  const params = new URLSearchParams(location.hash.slice(1));
  if (!params.size) {
    if (position && position.project_identity === info.project_identity) return {...position};
    return {surface: summary.page_count ? 'overview' : 'content', page_id: null, layer: 'original_image',
      revision: summary.revision_id, zoom: 1, task_id: null};
  }
  if (params.get('project') !== info.project_identity) throw new Error('这个链接属于另一个项目。请从项目列表打开原项目，当前内容未替换。');
  const route = {surface: params.get('surface') || (params.get('task') ? 'runs' : params.has('page') ? 'page' : 'overview'),
    page_id: params.get('page'), layer: params.get('layer') || 'original_image', revision: params.get('revision'),
    zoom: params.has('zoom') ? Number(params.get('zoom')) : 1, task_id: params.get('task')};
  if ((!surfaces[route.surface] && route.surface !== 'page') || !layers[route.layer] ||
      !Number.isFinite(route.zoom) || route.zoom < .25 || route.zoom > 3 ||
      (route.surface === 'page' && !route.page_id)) throw new Error('链接中的页面、层或缩放无效，请检查链接。');
  return route;
}
export function routeHash(info, route) {
  const params = new URLSearchParams({project: info.project_identity, surface: route.surface, layer: route.layer, revision: route.revision, zoom: route.zoom || 1});
  if (route.page_id) params.set('page', route.page_id);
  if (route.task_id) params.set('task', route.task_id);
  return '#' + params;
}
export function position(info, route) {
  return {schema_version: 'ui_position.v1', project_id: info.project_id, project_identity: info.project_identity,
    page_id: route.page_id || null, surface: route.surface, layer: route.layer, revision: route.revision,
    zoom: route.zoom || 1, task_id: route.task_id || null};
}
