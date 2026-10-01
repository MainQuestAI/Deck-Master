import {get, revisionQuery, readableError} from './api.js';
import {el, button, heading, version} from './dom.js';
import {pageText} from './page-text.js';

export function changesetDesk(app, data) {
  const record = data.candidate, update = data.content_update;
  const basis = record.content_basis.page_sequence.map(item => item.page_id);
  const upserts = new Map((update.upsert_pages || []).map(page => [page.page_id, page]));
  const root = el('div', {class: 'stack changeset-desk', 'data-candidate-id': record.candidate_id},
    heading('整稿正文变更集比较', `基准 ${version(record.base_revision)}，候选固定在 ${version(data.revision_id)}；阅读不会采用或改稿。`,
      button('返回内容与来源', () => app.go({candidate_id: null}))),
    el('div', {class: 'panel'}, el('div', {class: 'panel-body stack'},
      el('p', {}, `基准 ${basis.length} 页 → 候选 ${update.page_order.length} 页；${upserts.size} 页新增或重写，${(update.remove_page_ids || []).length} 页移除。`),
      el('p', {}, '候选页序：' + update.page_order.map((id, index) => `第 ${index + 1} 页 · ${upserts.get(id)?.customer_visible.title || app.summary.pages.find(page => page.page_id === id)?.title || id}`).join('；')))),
    el('p', {class: 'muted'}, '展开页面读取基准与候选全文。保留页不重新生成；移除页在基准侧保留可读依据。'));
  let disposed = false;
  const relationNames = {rewritten: '重写', derived: '新增或派生', retained: '保留', removed: '移除'};
  for (const mapping of data.mapping) {
    const id = mapping.page_id, input = upserts.get(id), detail = el('details', {class: 'panel changeset-page'},
      el('summary', {}, (update.page_order.includes(id) ? `第 ${update.page_order.indexOf(id) + 1} 页` : '原第 ' + (basis.indexOf(id) + 1) + ' 页') +
        ' · ' + (input?.customer_visible.title || app.summary.pages.find(page => page.page_id === id)?.title || id) + ' · ' + relationNames[mapping.relation]));
    const body = el('div', {class: 'panel-body stack'});
    let loading = false, loaded = false;
    async function load() {
      if (loaded || loading || disposed) return;
      loading = true; body.replaceChildren(el('p', {role: 'status'}, '正在读取固定版本正文…'));
      try {
        const oldIds = mapping.source_page_ids.filter(pid => basis.includes(pid));
        const previous = await Promise.all(oldIds.map(pid => get('/api/pages/' + encodeURIComponent(pid) + revisionQuery(record.base_revision))));
        if (disposed) return;
        if (previous.some(page => page.error || !page.page)) throw new Error('基准页正文暂不可读，不能用空白替代。');
        const left = previous.length ? previous.map(page => pageText(page.page)).join('\n\n') : '基准中没有此页。';
        const right = mapping.relation === 'removed' ? '候选将移除此页；尚未采用。' : input ? pageText(input) : previous.map(page => pageText(page.page)).join('\n\n');
        body.replaceChildren(el('div', {class: 'candidate-columns'},
          el('section', {class: 'candidate-column', 'data-side': 'current'}, el('h2', {}, '固定基准正文'), el('p', {class: 'changeset-copy'}, left)),
          el('section', {class: 'candidate-column', 'data-side': 'candidate'}, el('h2', {}, '所选变更集正文'), el('p', {class: 'changeset-copy'}, right))));
        loaded = true;
      } catch (error) {
        if (!disposed) body.replaceChildren(el('p', {role: 'alert'}, readableError(error) + ' 候选与当前稿件均保留。'), button('重试读取正文', load));
      } finally { loading = false; }
    }
    detail.append(body); detail.addEventListener('toggle', () => { if (detail.open) load(); }); root.append(detail);
  }
  root.append(el('details', {}, el('summary', {}, '变更集身份与页映射'), el('pre', {class: 'evidence-json'}, JSON.stringify({candidate_id: record.candidate_id,
    base_revision: record.base_revision, revision_id: data.revision_id, mapping: data.mapping}, null, 2))),
    button('查看候选采用与交付工作面', () => app.go({surface: 'runs', candidate_id: null, task_id: null})));
  app.disposables.push(() => { disposed = true; });
  return root;
}
