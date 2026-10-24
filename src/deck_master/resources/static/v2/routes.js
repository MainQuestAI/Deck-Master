export const surfaces = {overview: '制作总览', content: '内容与页序', gallery: '整稿画廊', style: '风格校准', runs: '任务与交付'};
export const layers = {source: '来源', content: '逐页稿', original_image: '原图', svg: 'SVG', ppt: 'PPT', prepared_prompt: '预备提示词', submitted_prompt: '实际提示词'};
// R4（深度复审）：任务与交付的四个子区是工作区上下文，随链接保存与恢复。
export const runsAreas = ['tasks', 'decisions', 'versions', 'files'];
export function readRoute(info, position, summary, hash = location.hash) {
  const params = new URLSearchParams(hash.slice(1));
  if (!params.size) {
    if (position && position.project_identity === info.project_identity) return {...position};
    return {surface: summary.page_count ? 'overview' : 'content', page_id: null, layer: 'original_image',
      revision: summary.revision_id, zoom: 1, task_id: null};
  }
  if (params.get('project') !== info.project_identity) throw new Error('这个链接属于另一个项目。请从项目列表打开原项目，当前内容未替换。');
  const route = {surface: params.get('surface') || (params.get('task') ? 'runs' : params.has('page') ? 'page' : 'overview'),
    page_id: params.get('page'), layer: params.get('layer') || 'original_image', revision: params.get('revision') === 'null' ? null : params.get('revision'),
    candidate_id: params.get('candidate'), zoom: params.has('zoom') ? Number(params.get('zoom')) : 1, task_id: params.get('task'),
    action_id: params.get('action'), review_id: params.get('review'), runs_area: runsAreas.includes(params.get('area')) ? params.get('area') : null};
  route.from = params.get('from');
  if (params.getAll('from').length > 1 || (route.from && !Object.hasOwn(surfaces, route.from))) throw Error('来源工作面无效。');
  route.content_q = params.get('content_q') || '';
  if (params.getAll('content_q').length > 1 || route.content_q.length > 200 || /[\u0000-\u001f\u007f]/.test(route.content_q))
    throw new Error('逐页稿搜索链接无效，当前内容保留。');
  for(const key of ['content_area','proposal','compare_proposal','atom','review_sha256','finding','finding_index']){
    if(params.getAll(key).length>1)throw Error('阅读链接参数重复。');
    route[key]=params.get(key);
  }
  if(route.content_area&&!['overview','pages','plan','notes','arguments','methods'].includes(route.content_area))throw Error('内容子区无效。');
  if([route.proposal,route.compare_proposal,route.review_sha256].some(v=>v&&!/^[a-f0-9]{64}$/.test(v)))throw Error('固定引用无效。');
  if(route.compare_proposal&&(!route.proposal||route.compare_proposal===route.proposal))throw Error('比较需要两份不同主线。');
  if(route.finding!==null&&(!route.review_id||!route.review_sha256||!route.revision||!/^\d+$/.test(route.finding_index||'')))throw Error('审阅定位必须包含完整固定身份。');
  if(route.atom&&(!route.atom.startsWith('atom:')||route.atom.length>512||route.surface!=='page'))throw Error('正文定位无效。');
  if (params.has('batch') || params.has('batchPages')) {
    const pageIds=(params.get('batchPages')||'').split(',');
    if(route.surface!=='overview'||!route.revision||route.action_id||route.task_id||route.review_id||route.candidate_id||
      params.getAll('batch').length!==1||params.getAll('batchPages').length!==1||
      !['blueprint','reconstruct','repair','style'].includes(params.get('batch'))||
      pageIds.length<1||pageIds.length>300||new Set(pageIds).size!==pageIds.length||
      pageIds.some(id=>!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(id)))
      throw new Error('画廊制作链接的动作、选页或固定版本无效，原选择保留。');
    route.batch_action=params.get('batch'); route.batch_page_ids=pageIds;
  }
  if (['q','filter','sort'].some(key => params.has(key))) {
    if (route.surface !== 'overview' || ['q','filter','sort'].some(key => params.getAll(key).length > 1) || (params.get('q') || '').length > 200 || (params.has('filter') && !['all','todo'].includes(params.get('filter'))) || (params.has('sort') && !['ascending','descending'].includes(params.get('sort'))))
      throw new Error('总览链接中的搜索、筛选或排序无效，当前内容保留。');
    route.overview_preferences = {search:params.get('q') || '', filter:params.get('filter') || 'all', sort:params.get('sort') || 'ascending'};
  }
  if ((!surfaces[route.surface] && route.surface !== 'page') || !layers[route.layer] ||
      !Number.isFinite(route.zoom) || route.zoom < .25 || route.zoom > 3 ||
      (route.surface === 'page' && !route.page_id) ||
      (route.action_id && (route.surface !== 'overview' || !/^[a-f0-9]{32}$/.test(route.action_id))) ||
      (route.review_id && !['runs','page'].includes(route.surface)) ||
      (route.candidate_id && !['page', 'content'].includes(route.surface)) ||
      [route.action_id, route.review_id, route.candidate_id, route.task_id].filter(Boolean).length > 1 ||
      ((route.action_id || route.review_id || route.candidate_id) && !route.revision) ||
      [route.page_id, route.task_id, route.review_id, route.candidate_id, route.revision].some(id => id !== null && !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(id)))
    throw new Error('链接中的页面、对象、层或版本无效，请检查链接。');
  return route;
}
export function routeHash(info, route) {
  const params = new URLSearchParams({project: info.project_identity, surface: route.surface, layer: route.layer, zoom: route.zoom || 1});
  for(const key of ['content_area','proposal','compare_proposal','atom','review_sha256','finding','finding_index'])if(route[key]!==null&&route[key]!==undefined)params.set(key,route[key]);
  if (route.surface === 'page' && route.from) params.set('from', route.from);
  if (route.content_q) params.set('content_q', route.content_q);
  if (route.revision != null) params.set('revision', route.revision);
  if (route.page_id) params.set('page', route.page_id);
  if (route.candidate_id) params.set('candidate', route.candidate_id);
  if (route.task_id) params.set('task', route.task_id);
  if (route.action_id) params.set('action', route.action_id);
  if (route.review_id) params.set('review', route.review_id);
  // 子区上下文随链接全程保留：跨面返回再进任务与交付时仍落在同一工作区。
  if (route.runs_area) params.set('area', route.runs_area);
  if(route.surface==='overview'&&route.revision&&route.batch_action&&route.batch_page_ids?.length){
    params.set('batch',route.batch_action);params.set('batchPages',route.batch_page_ids.join(','));
  }
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
