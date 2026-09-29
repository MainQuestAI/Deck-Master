import {get, post, canonical, readableError, revisionQuery} from './api.js';
import {el, button, heading, empty, modal, version} from './dom.js';
import {DraftEditor} from './drafts.js';
import {imageView} from './images.js';
import {routeHash} from './routes.js';
import {openCandidate} from './trial-actions.js';

const stageName = stage => stage === 'blueprint' ? '原图' : 'SVG';
const clock = value => new Date(value).toLocaleString('zh-CN', {hour12: false});
function operationDraft(app) {
  app.editor = new DraftEditor(app.info, {scope: 'project', page_id: null, layer: 'notes'}, app.route.revision, null, {readonly: app.readonly});
  const node = app.editor.mount();
  return el('details', {class: 'candidate-recovery'}, el('summary', {}, '个人记录与操作恢复'), node);
}
function picture(app, stage, label, releases, kind = 'large') {
  if (!stage?.file) return empty('尚无这一层的当前产物', '这里保留空位，不用其它图层代替。');
  const view = imageView(app, stage, label, {kind}); releases.push(() => view.dispose()); return view.node;
}
function errorItems(error) {
  return error.details?.items?.length ? el('ul', {}, error.details.items.map(item => el('li', {},
    `${item.page_id || '候选'}：${item.cause === 'generation_basis_changed' ? '生成依据已变化' : item.cause === 'one_candidate_per_page' ? '每页只能选择一个候选' : '采用条件不满足'}`))) : null;
}
function impactBox(plan) {
  return el('div', {class: 'stack'}, el('strong', {}, `本次采用 ${plan.selections.length} 页 · 不调用图像工具`),
    el('ul', {}, plan.selections.map(item => el('li', {}, `${item.page_id}：采用${stageName(item.stage)}；${item.stage === 'blueprint' ? '本页 SVG、' : ''}预览与整稿 PPT 需要更新。`))),
    el('p', {class: 'muted'}, `全部成功或全部不采用 · 提交基准 ${version(plan.base_revision)} · 采用不代表质量通过。`));
}
function blocked(app, busy) { return busy || app.readonly || Boolean(app.business?.entries.size || app.business?.loadWarning); }

export function candidateDesk(app, data) {
  if (!app.health.ui_capabilities?.includes('candidates.v1')) return empty('核心需要升级', '候选读取与采用需要匹配的核心版本。');
  const stage = app.route.layer === 'original_image' ? 'blueprint' : 'svg';
  const pageNumber = app.summary.pages.findIndex(page => page.page_id === data.page_id) + 1;
  const root = el('div', {class: 'candidate-desk stack'}), title = heading(`第 ${pageNumber} 页 · ${stageName(stage)}候选`, '当前采用与候选固定比较；参考原图作为辅助。');
  const select = el('select', {'aria-label': '选择本页候选'}), status = el('div', {role: 'status', class: 'candidate-state'});
  const columns = el('div', {class: 'candidate-columns'}), sources = el('div', {class: 'candidate-reference-row'}), evidence = el('div'), impact = el('div', {class: 'candidate-impact stack'});
  const draft = operationDraft(app);
  let selected, live, list = [], disposed = false, busy = false, polling = false, serial = 0, currentPlan = null, planInvalid = false, lastSync = null;
  const releases = [], auxReleases = [], modalReleases = [];
  const choosePlan = button('预览采用这个候选', planAdoption, false), adopt = button('采用这个候选', adoptSelected, true, {disabled: true});
  const keep = button('保留当前，返回本页', () => app.go({candidate_id: null}));
  const retry = button('回本页调整并再试', () => app.go({candidate_id: null, revision: live?.revision_id || app.route.revision}));
  root.append(title, el('div', {class: 'toolbar'}, el('label', {}, '候选 ', select), button('刷新候选与当前状态', refresh)), status, columns, sources, evidence,
    el('div', {class: 'row wrap'}, choosePlan, adopt, keep, retry), impact, draft);
  function controls() {
    select.disabled = busy;
    const unavailable = !selected || selected.candidate.page_id !== data.page_id;
    const changed = live?.generation_basis.status === 'changed';
    const alreadyCurrent = selected && canonical(live?.adoption_target.current_ref) === canonical(selected.candidate.result_ref);
    choosePlan.disabled = blocked(app, busy) || unavailable || changed || alreadyCurrent;
    adopt.disabled = blocked(app, busy) || !currentPlan || planInvalid || changed || alreadyCurrent;
    choosePlan.textContent = currentPlan && planInvalid ? '重新预览采用影响' : '预览采用这个候选';
  }
  function renderState() {
    if (!selected) return;
    const candidate = selected.candidate;
    const current = canonical(live?.adoption_target.current_ref) === canonical(candidate.result_ref);
    status.replaceChildren(el('div', {class: 'stack'}, el('strong', {}, current ? '这个候选已是当前采用' : live?.generation_basis.status === 'changed' ? '生成依据已变化，暂不能采用' : '候选可比较，采用前请检查事实与数字'),
      el('span', {}, ` · ${candidate.page_id} · ${stageName(candidate.stage)} · 返回 ${clock(candidate.created_at)}`),
      live?.generation_basis.status === 'changed' && el('p', {class: 'field-error'}, `Page、设计、输入或原图依据已变化（${live.generation_basis.changed_fields.join('、')}）。固定比较仍保留；请按新依据重新试作。`),
      live?.adoption_target.status === 'changed' && !current && el('p', {}, '当前采用产物已更新。这里仍显示原固定比较，重新预览后才能决定是否覆盖新的采用目标。'),
      planInvalid && el('p', {class: 'field-error'}, '项目版本已前进，旧采用计划已禁用。请重新预览；不会重新生成候选。'),
      candidate.status === 'available' && live?.adopted_revisions.length > 0 && el('p', {class: 'muted'}, '曾采用到：' + live.adopted_revisions.map(version).join('、')),
      lastSync && el('p', {class: 'muted'}, '最后同步：' + lastSync.toLocaleTimeString('zh-CN', {hour12: false}))));
    controls();
  }
  function drawColumns(leftStage, leftRevision, label = '当前采用（原固定基准）') {
    releases.splice(0).forEach(fn => fn());
    columns.replaceChildren(el('section', {class: 'candidate-column', 'data-side': 'current', 'data-revision': leftRevision},
      el('h2', {}, label), el('p', {class: 'muted'}, version(leftRevision)), picture(app, leftStage, '固定当前采用', releases)),
      el('section', {class: 'candidate-column', 'data-side': 'candidate', 'data-candidate-id': selected.candidate_id},
        el('h2', {}, '所选候选'), el('p', {class: 'muted'}, `${stageName(selected.candidate.stage)} · ${clock(selected.candidate.created_at)}`),
        picture(app, selected.artifact, '所选候选图像', releases)));
  }
  function drawEvidence(attempt, base) {
    auxReleases.splice(0).forEach(fn => fn()); sources.replaceChildren();
    const referenceSources = [...(selected.reference_sources || [])];
    if (stage === 'svg' && base.stages.blueprint?.file) referenceSources.unshift({page_id: data.page_id, revision_id: base.revision_id, file: base.stages.blueprint.file});
    for (const source of referenceSources) {
      sources.append(el('section', {class: 'candidate-reference'}, el('h3', {}, `固定参考 ${source.page_id}`),
        picture(app, {file: source.file}, '固定参考原图', auxReleases, 'thumb'), el('p', {class: 'muted'}, version(source.revision_id)),
        button('放大固定参考图', () => {
          const views = []; const dialog = modal('固定参考原图 · ' + source.page_id,
            picture(app, {file: source.file}, '固定参考原图放大', views));
          const release = () => views.splice(0).forEach(fn => fn());
          modalReleases.push(() => { release(); if (dialog.contains(dialogImage)) dialog.close(); });
          const dialogImage = dialog.querySelector('.pooled-image');
          dialog.addEventListener('close', release, {once: true});
        })));
    }
    const observations = attempt?.observations || [];
    const actual = observations.find(record => record.observer === 'tool_observed' && record.output?.sha256 === selected.artifact.file.sha256);
    evidence.replaceChildren(el('details', {class: 'panel candidate-basis'}, el('summary', {}, '所选候选的生成依据'),
      el('div', {class: 'panel-body stack'},
        el('p', {}, selected.request ? `已绑定请求与 Attempt · ${selected.attempt?.attempt_id || '未记录'}` : 'SVG 重建结果；没有新增图像调用。原图与实际提示词保留。'),
        selected.request && el('div', {}, el('h3', {}, '冻结的请求全文'), el('pre', {class: 'prompt-copy'}, selected.request.input.prompt)),
        selected.request && el('div', {}, el('h3', {}, '当次实际提交'), actual ? el('pre', {class: 'prompt-copy'}, actual.submitted.prompt) : el('p', {}, '当次实际提交未能读取；不会用预备稿补造。')),
        actual && el('p', {class: 'muted'}, '来源：本机原生工具事件；不代表独立质量验收。'),
        el('details', {}, el('summary', {}, '请求、Attempt 与结果身份'), el('pre', {class: 'evidence-json'}, JSON.stringify({candidate_id: selected.candidate_id,
          request_id: selected.request?.request_id || null, attempt_id: selected.attempt?.attempt_id || null, result_ref: selected.candidate.result_ref,
          generation_basis: selected.candidate.generation_basis, references: selected.reference_sources, observed_coverage: actual?.coverage || null}, null, 2))))));
  }
  async function choose(id) {
    const token = ++serial, routeAtStart = location.hash; busy = true; currentPlan = null; planInvalid = false; controls();
    impact.replaceChildren(el('p', {}, '正在读取所选候选；已读比较在新数据完整前保持不变。'));
    try {
      const value = await get('/api/candidates/' + encodeURIComponent(id));
      if (disposed || token !== serial || location.hash !== routeAtStart) return;
      if (value.candidate.page_id !== data.page_id || value.candidate.stage !== stage) throw new Error('候选不属于这页或这一层，未替换比较画面。');
      const [base, attempt] = await Promise.all([
        get('/api/pages/' + encodeURIComponent(data.page_id) + '/lineage' + revisionQuery(value.candidate.base_revision)),
        value.attempt ? get('/api/attempts/' + encodeURIComponent(value.attempt.attempt_id) + revisionQuery(value.revision_id)) : Promise.resolve(null)]);
      if (disposed || token !== serial || location.hash !== routeAtStart) return;
      if (canonical(base.stages[stage].ref) !== canonical(value.candidate.target_ref)) throw new Error('固定采用目标与候选记录不一致，保留旧比较。');
      selected = value; live = value; lastSync = new Date(); select.value = id;
      root.dataset.candidateId = id; app.route.candidate_id = id; history.replaceState(null, '', routeHash(app.info, app.route));
      drawColumns(base.stages[stage], base.revision_id); drawEvidence(attempt, base); impact.replaceChildren(); renderState();
    } catch (error) { if (!disposed && token === serial) { impact.replaceChildren(el('p', {class: 'field-error'}, readableError(error))); select.value = selected?.candidate_id || ''; } }
    finally { if (token === serial) { busy = false; if (!disposed) controls(); } }
  }
  select.addEventListener('change', () => choose(select.value));
  async function refresh() {
    if (busy || disposed || polling) return; polling = true; const token = serial;
    try {
      const result = await get('/api/candidates?' + new URLSearchParams({page_id: data.page_id})); if (disposed || busy) return;
      list = result.candidates.filter(row => row.candidate.stage === stage);
      select.replaceChildren(...list.map((row, index) => el('option', {value: row.candidate.candidate_id}, `候选 ${index + 1} · ${clock(row.candidate.created_at)}`)));
      select.value = selected?.candidate_id || app.route.candidate_id;
      if (!selected) { await choose(app.route.candidate_id); return; }
      const id = selected.candidate_id, state = await get('/api/candidates/' + encodeURIComponent(id));
      if (disposed || busy || token !== serial || selected.candidate_id !== id) return;
      if (canonical(state.candidate_ref) !== canonical(selected.candidate_ref)) throw new Error('候选身份发生异常变化，比较仍固定。');
      live = state; lastSync = new Date();
      if (currentPlan && currentPlan.base_revision !== state.revision_id) planInvalid = true;
      renderState();
    } catch (error) { if (!disposed) impact.replaceChildren(el('p', {class: 'field-error'}, readableError(error) + ' 已读的固定比较仍保留。')); }
    finally { polling = false; }
  }
  async function planAdoption() {
    if (!selected || busy) return; busy = true; controls(); const id = selected.candidate_id;
    try {
      await app.business.available();
      const latest = await get('/api/candidates/' + encodeURIComponent(id));
      const input = {schema_version: 'candidate_selection.v1', project_id: app.info.project_id, base_revision: latest.revision_id, candidate_ids: [id]};
      const result = await post('/api/candidates/plan', {input});
      const page = await get('/api/pages/' + encodeURIComponent(data.page_id) + '/lineage' + revisionQuery(result.plan.base_revision));
      if (disposed || selected.candidate_id !== id) return;
      currentPlan = result.plan; planInvalid = false; live = latest;
      drawColumns(page.stages[stage], page.revision_id, '本次采用目标（新固定基准）');
      impact.replaceChildren(impactBox(currentPlan)); renderState();
    } catch (error) { currentPlan = null; if (!disposed) impact.replaceChildren(el('div', {class: 'stack'}, el('p', {class: 'field-error'}, readableError(error)), errorItems(error))); }
    finally { busy = false; if (!disposed) controls(); }
  }
  async function adoptSelected() {
    if (busy || !currentPlan || planInvalid) return; busy = true; controls(); const value = structuredClone(currentPlan);
    try {
      await app.business.submit(app.editor, 'candidates.adopt', {input: value, base_revision: value.base_revision}, value, async result => {
        currentPlan = null; planInvalid = false;
        const prior = selected?.candidate_id !== value.selections[0].candidate_id;
        impact.replaceChildren(el('p', {class: 'success-note'}, `${prior ? '先前提交的候选' : '这个候选'}已采用到 ${version(result.revision_id)}。${prior ? '当前比较选择未变。' : ''}本页下游与整稿待更新，请继续单页预览、审图和整稿制作。`),
          button('查看任务与交付', () => app.go({surface: 'runs', revision: result.revision_id, candidate_id: null})));
        const id = selected?.candidate_id, state = await get('/api/candidates/' + encodeURIComponent(id));
        if (!disposed && selected?.candidate_id === id) { live = state; renderState(); }
      });
    } catch (error) { if (!disposed) impact.replaceChildren(el('p', {class: 'field-error'}, readableError(error))); }
    finally { busy = false; if (!disposed) controls(); }
  }
  const rejected = event => { if (event.detail.action === 'candidates.adopt') { currentPlan = null; controls(); } };
  app.root.addEventListener('business-rejected', rejected);
  const sync = () => controls(); app.root.addEventListener('business-state-changed', sync);
  const timer = setInterval(() => { if (!document.hidden) refresh(); }, 5000);
  app.disposables.push(() => { disposed = true; serial++; clearInterval(timer); releases.forEach(fn => fn()); auxReleases.forEach(fn => fn()); modalReleases.forEach(fn => fn()); app.root.removeEventListener('business-state-changed', sync); app.root.removeEventListener('business-rejected', rejected); });
  refresh(); controls(); return root;
}

export function candidateBatch(app) {
  if (!app.business || !app.health.ui_capabilities?.includes('candidates.v1')) return el('div');
  const root = el('section', {class: 'panel candidate-batch', 'aria-label': '候选集合采用'});
  const rows = el('div', {class: 'candidate-batch-rows stack'}), notice = el('p', {role: 'status'}), impact = el('div', {class: 'stack'});
  let records = [], selected = new Set(), currentPlan = null, disposed = false, busy = false, polling = false, revision = null, serial = 0;
  const draft = operationDraft(app);
  const preview = button('预览所选候选的采用影响', previewSelection), adopt = button('采用所选候选', adoptSelection, true, {disabled: true});
  const assemble = button('更新整稿 PPT', assembleDeck);
  root.append(el('div', {class: 'panel-head'}, el('h2', {}, '候选与当前稿'), button('刷新候选列表', refresh)),
    el('div', {class: 'panel-body stack'}, el('p', {}, '勾选要采用的候选；同一页只能选一个。任何冲突都会整批不采用，选择继续保留。'), notice, rows,
      el('div', {class: 'row wrap'}, preview, adopt), impact,
      el('details', {}, el('summary', {}, '采用后的整稿制作'), el('p', {}, '先由原有 continue 完成受影响页的 SVG 预览和逐页审图，再更新整稿。仍需最终审阅。'), assemble), draft));
  function persist() {
    if (!app.editor || app.editor.readonly || app.editor.disposed) return;
    app.editor.draft.content.candidate_selection = [...selected]; app.editor.changed();
  }
  function controls() {
    preview.disabled = blocked(app, busy) || selected.size === 0;
    adopt.disabled = blocked(app, busy) || !currentPlan || currentPlan.base_revision !== revision;
    assemble.disabled = blocked(app, busy);
    rows.querySelectorAll('input').forEach(input => { input.disabled = blocked(app, busy); });
  }
  function renderRows() {
    const missing = [...selected].filter(id => !records.some(row => row.candidate.candidate_id === id));
    notice.textContent = `${records.length} 个已返回候选 · 已选 ${selected.size} 个${missing.length ? `（${missing.length} 个暂未读到，选择仍保留）` : ''}`;
    rows.replaceChildren(...records.map((row, index) => {
      const record = row.candidate, id = record.candidate_id;
      const input = el('input', {type: 'checkbox', checked: selected.has(id), 'aria-label': `选择 ${record.page_id} 候选 ${index + 1}`});
      input.addEventListener('change', () => {
        serial++; currentPlan = null; impact.replaceChildren();
        if (input.checked) {
          for (const other of records) if (other.candidate.page_id === record.page_id) selected.delete(other.candidate.candidate_id);
          selected.add(id);
        } else selected.delete(id);
        persist(); renderRows();
      });
      return el('article', {class: 'candidate-batch-row', 'data-candidate-id': id}, el('label', {}, input,
        el('span', {}, `${record.page_id} · ${stageName(record.stage)}候选 ${index + 1}`)),
        el('p', {class: 'muted'}, `${clock(record.created_at)} · ${row.generation_basis.status === 'changed' ? '依据已变化' : canonical(row.adoption_target.current_ref) === canonical(record.result_ref) ? '当前采用' : row.status === 'adopted' ? '曾采用' : '待决定'}`),
        button('比较这个候选', () => openCandidate(app, record, revision)));
    }));
    if (!records.length) rows.append(el('p', {class: 'muted'}, '还没有候选。单页原图或 SVG 中可保存试作要求；正在运行或失败的任务仍在下方交接面板。'));
    controls();
  }
  async function refresh() {
    if (disposed || polling || busy) return; polling = true;
    try {
      const value = await get('/api/candidates'); if (disposed || busy) return;
      records = value.candidates; revision = value.revision_id;
      if (currentPlan && currentPlan.base_revision !== revision) {
        currentPlan = null;
        impact.replaceChildren(el('p', {class: 'field-error'}, '项目已更新，旧计划不可提交。所选候选仍保留，请重新预览采用影响。'));
      }
      renderRows();
    } catch (error) { if (!disposed) notice.textContent = readableError(error) + ' 已读列表与选择仍保留。'; }
    finally { polling = false; }
  }
  async function previewSelection() {
    if (busy || !selected.size) return; busy = true; const token = ++serial; controls(); currentPlan = null;
    try {
      await app.business.available();
      const latest = await get('/api/view/summary');
      const input = {schema_version: 'candidate_selection.v1', project_id: app.info.project_id, base_revision: latest.revision_id, candidate_ids: [...selected]};
      const result = await post('/api/candidates/plan', {input});
      if (disposed || serial !== token) return;
      currentPlan = result.plan; revision = result.plan.base_revision; impact.replaceChildren(impactBox(currentPlan));
    } catch (error) { if (!disposed) impact.replaceChildren(el('div', {class: 'stack'}, el('p', {class: 'field-error'}, readableError(error)), errorItems(error))); }
    finally { busy = false; if (!disposed) controls(); }
  }
  async function adoptSelection() {
    if (busy || !currentPlan || currentPlan.base_revision !== revision) return; busy = true; controls(); const value = structuredClone(currentPlan);
    try {
      await app.business.submit(app.editor, 'candidates.adopt', {input: value, base_revision: value.base_revision}, value, result => {
        currentPlan = null; revision = result.revision_id;
        for (const id of result.candidate_ids) selected.delete(id);
        persist(); impact.replaceChildren(el('p', {class: 'success-note'}, `已整批采用 ${result.candidate_ids.length} 页到 ${version(result.revision_id)}；其它页保留。下游预览、整稿与审阅待更新。`));
      });
    } catch (error) { if (!disposed) impact.replaceChildren(el('p', {class: 'field-error'}, readableError(error))); }
    finally { busy = false; if (!disposed) { controls(); refresh(); } }
  }
  async function assembleDeck() {
    if (busy) return; busy = true; controls();
    try {
      await app.business.available(); const latest = await get('/api/view/summary');
      await app.business.submit(app.editor, 'stages.assemble', {base_revision: latest.revision_id}, {}, result => {
        currentPlan = null; revision = result.revision_id;
        impact.replaceChildren(el('p', {class: 'success-note'}, `整稿已制作到 ${version(result.revision_id)}。转换回读${result.report.status === 'pass' ? '通过' : '发现问题'}，仍需最终审阅。`),
          button('读取制作后的当前版本', () => app.go({revision: result.revision_id})));
      });
    } catch (error) { if (!disposed) impact.replaceChildren(el('p', {class: 'field-error'}, readableError(error))); }
    finally { busy = false; if (!disposed) controls(); }
  }
  const rejected = event => { if (event.detail.action === 'candidates.adopt') { currentPlan = null; controls(); } };
  app.root.addEventListener('business-rejected', rejected);
  const sync = () => controls(); app.root.addEventListener('business-state-changed', sync);
  function hydrate() {
    const editor = app.editor;
    editor.ready.then(() => {
      if (disposed || editor !== app.editor) return;
      const saved = editor.draft.content.candidate_selection;
      selected = new Set(Array.isArray(saved) ? saved.filter(id => typeof id === 'string') : []);
      currentPlan = null; impact.replaceChildren(); renderRows(); refresh();
    });
  }
  app.root.addEventListener('draft-editor-replaced', hydrate); hydrate();
  const timer = setInterval(() => { if (!document.hidden) refresh(); }, 5000);
  app.disposables.push(() => { disposed = true; serial++; clearInterval(timer); app.root.removeEventListener('draft-editor-replaced', hydrate); app.root.removeEventListener('business-state-changed', sync); app.root.removeEventListener('business-rejected', rejected); });
  controls(); return root;
}
