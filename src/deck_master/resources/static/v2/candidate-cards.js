import {get, canonical, readableError} from './api.js';
import {el, button, shortRef} from './dom.js';
import {imageView} from './images.js';
import {pageText} from './page-text.js';
import {openCandidate} from './trial-actions.js';

const kinds = {blueprint:'原图', svg:'SVG', content:'正文'};
export function candidateState(row) {
  if (row.generation_basis?.status === 'changed' || row.content_basis?.status === 'changed') return '依据已变化';
  if (row.adoption_target?.current_ref && canonical(row.adoption_target.current_ref) === canonical(row.candidate.result_ref)) return '当前采用';
  if (row.status === 'adopted') return '曾采用';
  return row.decision?.state === 'keep_current' ? '已保留当前' : '待决定';
}

// Details remain tied to the fixed revision/ref. Only visible cards acquire images.
export function candidateCards(app) {
  let epoch = 0, disposed = false;
  const details = new Map(), cards = new Map(), pending = new Set();
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      const card = cards.get(entry.target);
      if (!card) continue;
      if (entry.isIntersecting) { card.visible = true; load(card); }
      else { card.visible = false; card.view?.dispose(); card.view = null; }
    }
  });
  function reset() {
    epoch++; observer.disconnect();
    cards.forEach(card => card.view?.dispose()); cards.clear();
    pending.forEach(controller => controller.abort()); pending.clear();
  }
  async function load(card) {
    if (card.loading || card.view || disposed) return;
    card.loading = true; const token = epoch, controller = new AbortController(); pending.add(controller);
    try {
      let value = details.get(card.key);
      if (!value) {
        value = await get('/api/candidates/' + encodeURIComponent(card.row.candidate.candidate_id) + '?' + new URLSearchParams({revision:card.revision}), {signal:controller.signal});
        if (value.candidate_ref?.sha256 !== card.row.ref?.sha256 || value.revision_id !== card.revision) throw new Error('候选引用与固定列表不一致，未展示其它作品。');
        if (disposed || token !== epoch) return;
        details.set(card.key, value);
        if (details.size > 60) details.delete(details.keys().next().value);
      }
      if (disposed || token !== epoch || !card.visible) return;
      if (value.result_kind === 'artifact') {
        card.view = imageView(app, value.artifact, card.title + ' · 候选缩略图');
        card.preview.replaceChildren(card.view.node);
      } else {
        const text = value.page ? pageText(value.page) : (value.content_update?.upsert_pages || []).map(pageText).join('\n');
        card.preview.replaceChildren(el('p', {class:'candidate-text-summary'}, text ? text.slice(0,320) : '此候选未记录可读正文摘要。'));
      }
    } catch (error) {
      if (!disposed && token === epoch && error.name !== 'AbortError') card.preview.replaceChildren(el('p', {class:'field-error'}, readableError(error)), button('重试候选摘要', () => load(card)));
    } finally { card.loading = false; pending.delete(controller); }
  }
  function render(rows, revision, {selection = null, extra = null, namedComparison = false} = {}) {
    reset(); const groups = new Map();
    rows.forEach((row,index) => {
      const record = row.candidate, page = app.summary.pages.find(p => p.page_id === record.page_id);
      const number = app.summary.pages.indexOf(page) + 1;
      const title = record.page_id ? (page ? `第 ${number} 页 · ${page.title || '未命名页面'}` : record.page_id) : '整稿正文变更集';
      const preview = el('div', {class:'candidate-card-preview'}, el('p', {class:'muted'}, '候选摘要在进入阅读区时加载。'));
      const created = record.created_at && Number.isFinite(Date.parse(record.created_at)) ? new Date(record.created_at).toLocaleString('zh-CN', {hour12:false}) : '返回时间未记录';
      const node = el('article', {class:'candidate-batch-row candidate-card', 'data-candidate-id':record.candidate_id},
        selection?.(row,index), el('h4', {}, kinds[record.stage] || (row.result_kind === 'content_update' ? '整稿正文变更集' : '正文')),
        preview, el('p', {class:'muted'}, `${created} · ${candidateState(row)} · ${shortRef(row.ref?.sha256)}`),
        el('div', {class:'row wrap'}, button(namedComparison ? `比较 ${title} · ${shortRef(row.ref?.sha256)}` : '比较这个候选', () => openCandidate(app,record,revision)), extra?.(row)));
      const card = {node,preview,row,revision,title,key:revision + ':' + row.ref?.sha256,visible:false};
      cards.set(node,card); observer.observe(node);
      const groupKey = record.page_id || 'content_update';
      if (!groups.has(groupKey)) groups.set(groupKey, el('section', {class:'candidate-page-group stack','data-candidate-page':groupKey},el('h3',{},title)));
      groups.get(groupKey).append(node);
    });
    return [...groups.values()];
  }
  return {render, reset, dispose() { disposed = true; reset(); details.clear(); }};
}
