export const surfaces = {overview: '制作总览', content: '内容与来源', gallery: '整稿画廊', style: '风格校准', runs: '任务与交付'};
export const layers = {source: '来源', content: '逐页稿', original_image: '原图', svg: 'SVG', ppt: 'PPT', prepared_prompt: '预备提示词', submitted_prompt: '实际提示词'};
export function readRoute(info, position, summary) {
  const params = new URLSearchParams(location.hash.slice(1));
  if (!params.size) {
    if (position && position.project_identity === info.project_identity) return {...position};
    return {surface: summary.page_count ? 'overview' : 'content', page_id: null, layer: 'original_image',
      revision: summary.revision_id, zoom: 1, task_id: null};
  }
  if (params.get('project') !== info.project_identity) throw new Error('这个链接属于另一个项目。请从项目列表打开原项目，当前内容未替换。');
  const route = {surface: params.get('surface') || (params.get('task') ? 'runs' : params.has('page') ? 'page' : 'overview'),
    page_id: params.get('page'), layer: params.get('layer') || 'original_image', revision: params.get('revision') === 'null' ? null : params.get('revision'),
    candidate_id: params.get('candidate'), zoom: params.has('zoom') ? Number(params.get('zoom')) : 1, task_id: params.get('task'),
    action_id: params.get('action'), review_id: params.get('review')};
  if (['q','filter','sort'].some(key => params.has(key))) {
    if (route.surface !== 'overview' || ['q','filter','sort'].some(key => params.getAll(key).length > 1) || (params.get('q') || '').length > 200 || (params.has('filter') && !['all','todo'].includes(params.get('filter'))) || (params.has('sort') && !['ascending','descending'].includes(params.get('sort'))))
      throw new Error('总览链接中的搜索、筛选或排序无效，当前内容保留。');
    route.overview_preferences = {search:params.get('q') || '', filter:params.get('filter') || 'all', sort:params.get('sort') || 'ascending'};
  }
  if ((!surfaces[route.surface] && route.surface !== 'page') || !layers[route.layer] ||
      !Number.isFinite(route.zoom) || route.zoom < .25 || route.zoom > 3 ||
      (route.surface === 'page' && !route.page_id) ||
      (route.action_id && (route.surface !== 'overview' || !/^[a-f0-9]{32}$/.test(route.action_id))) ||
      (route.review_id && route.surface !== 'runs') ||
      (route.candidate_id && !['page', 'content'].includes(route.surface)) ||
      [route.action_id, route.review_id, route.candidate_id, route.task_id].filter(Boolean).length > 1 ||
      ((route.action_id || route.review_id || route.candidate_id) && !route.revision) ||
      [route.page_id, route.task_id, route.review_id, route.candidate_id, route.revision].some(id => id !== null && !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(id)))
    throw new Error('链接中的页面、对象、层或版本无效，请检查链接。');
  return route;
}
export function routeHash(info, route) {
  const params = new URLSearchParams({project: info.project_identity, surface: route.surface, layer: route.layer, zoom: route.zoom || 1});
  if (route.revision != null) params.set('revision', route.revision);
  if (route.page_id) params.set('page', route.page_id);
  if (route.candidate_id) params.set('candidate', route.candidate_id);
  if (route.task_id) params.set('task', route.task_id);
  if (route.action_id) params.set('action', route.action_id);
  if (route.review_id) params.set('review', route.review_id);
  if (route.surface === 'overview' && route.overview_preferences) {
    params.set('q', route.overview_preferences.search); params.set('filter', route.overview_preferences.filter); params.set('sort', route.overview_preferences.sort);
  }
  return '#' + params;
}
export function position(info, route) {
  return {schema_version: 'ui_position.v1', project_id: info.project_id, project_identity: info.project_identity,
    page_id: route.page_id || null, surface: route.surface, layer: route.layer, revision: route.revision,
    zoom: route.zoom || 1, task_id: route.task_id || null};
}
