import {get, readableError} from './api.js';
import {el, button, heading, version} from './dom.js';

const names = {task: '制作任务', page_layer: '页面产物', candidate: '页面候选', content_changeset: '整稿正文变更集',
  content_reconciliation: '输入协调', review: '质量与交付记录'};
const layerNames = {content: '正文', original_image: '原图', svg: 'SVG', ppt: 'PPT'};

export function targetRoute(target, revision) {
  if (!target.enabled) throw new Error('该目标暂不可读，未跳转到其它对象。');
  const base = {revision, action_id: null, review_id: null, candidate_id: null, task_id: null, page_id: null};
  if (target.kind === 'task') return {...base, surface: 'runs', task_id: target.object_id};
  if (target.kind === 'page_layer' || target.kind === 'candidate') {
    if (target.page_ids.length !== 1 || !target.layer) throw new Error('这个对象没有唯一页面与层，未跳转到第一项。');
    return {...base, surface: 'page', page_id: target.page_ids[0], layer: target.layer,
      candidate_id: target.kind === 'candidate' ? target.object_id : null};
  }
  if (target.kind === 'content_changeset') return {...base, surface: 'content', layer: 'content', candidate_id: target.object_id};
  if (target.kind === 'content_reconciliation') return {...base, surface: 'content', layer: 'content'};
  if (target.kind === 'review') return {...base, surface: 'runs', review_id: target.object_id, layer: target.layer || 'content'};
  throw new Error('该核心返回了无法识别的目标类型，未更换当前工作面。');
}

export async function openAction(app, action, fallback) {
  if (!app.health.ui_capabilities?.includes('action_targets.v1')) {
    app.go(fallback);
    return;
  }
  const serial = (app.actionNavigation || 0) + 1, generation = app.generation;
  app.actionNavigation = serial;
  try {
    const query = new URLSearchParams({revision: action.revision_id, limit: '30', offset: '0'});
    const result = await get('/api/actions/' + encodeURIComponent(action.action_id) + '/targets?' + query + (app.readingQuery?.()||''));
    if (serial !== app.actionNavigation || generation !== app.generation) return;
    if (result.project_id !== app.info.project_id || result.revision_id !== action.revision_id || result.action_id !== action.action_id)
      throw new Error('目标与当前待办版本不一致，未更换工作面。');
    if (result.total === 1 && result.targets[0]?.enabled) app.go(targetRoute(result.targets[0], result.revision_id));
    else app.go({surface: 'overview', action_id: action.action_id, revision: result.revision_id});
  } catch (error) {
    if (serial === app.actionNavigation && generation === app.generation)
      {app.setNotice(readableError(error) + ' 当前版本保留；请重新读取待办。');app.notice?.append(button('重新读取待办',()=>app.go({surface:'overview',action_id:null})));}
  }
}

export function actionTargets(app, data) {
  const root = el('div', {class: 'stack action-targets'}, heading('待办对象', `固定在 ${version(data.revision_id)}，共 ${data.total} 个对象；不会自动选第一项。`,
    button('返回制作总览', () => app.go({action_id: null}))));
  const rows = el('div', {class: 'stack'}), pager = el('div', {class: 'row wrap'}), notice = el('p', {role: 'status'});
  let current = data, disposed = false, busy = false;
  function draw() {
    rows.replaceChildren(...current.targets.map(target => {
      const pages = target.page_ids.map(id => app.summary.pages.findIndex(page => page.page_id === id) + 1);
      const scope = pages.length ? pages.every(n => n > 0) ? '第 ' + pages.join('、') + ' 页' : '页面未在此版本记录' : '项目级';
      return el('article', {class: 'panel action-target', 'data-target-id': target.target_id},
        el('div', {class: 'panel-body stack'}, el('h2', {}, names[target.kind]),
          el('p', {}, scope + (target.layer ? ' · ' + (layerNames[target.layer] || target.layer) : '')),
          el('p', {class: 'muted'}, target.enabled ? '按此版本查看对象；阅读不改变当前稿件。' : target.blocked_reason === 'target_identity_mismatch'
            ? '对象身份或页面范围不匹配，未跳转；其它对象仍可查看。' : '记录暂不可读，已隔离；其它对象仍可查看。'),
          el('details', {}, el('summary', {}, '对象与记录状态'), el('p', {}, target.object_id || '业务身份未能读取'), el('p', {}, target.status)),
          button('查看这个对象', () => app.go(targetRoute(target, current.revision_id)), false, {disabled: !target.enabled})));
    }));
    pager.replaceChildren(button('上一页对象', () => load(Math.max(0, current.offset - current.limit)), false, {disabled: busy || current.offset === 0}),
      el('span', {}, `第 ${Math.floor(current.offset / current.limit) + 1} 页`),
      button('下一页对象', () => load(current.offset + current.limit), false, {disabled: busy || current.offset + current.limit >= current.total}));
  }
  async function load(offset) {
    if (busy) return;
    busy = true; draw();
    try {
      const result = await get('/api/actions/' + encodeURIComponent(data.action_id) + '/targets?' +
        new URLSearchParams({revision: data.revision_id, limit: String(data.limit), offset: String(offset)})+(app.readingQuery?.()||''));
      if (!disposed) { current = result; notice.textContent = ''; }
    } catch (error) { if (!disposed) notice.replaceChildren(readableError(error)+' 已读对象列表仍保留。',button('重新读取待办',()=>app.go({surface:'overview',action_id:null})));  }
    finally { busy = false; if (!disposed) draw(); }
  }
  app.disposables.push(() => { disposed = true; });
  root.append(notice, rows, pager); draw(); return root;
}
