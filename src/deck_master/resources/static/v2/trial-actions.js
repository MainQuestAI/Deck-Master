import {get, post, canonical, readableError} from './api.js';
import {el, button, version} from './dom.js';
import {imageView} from './images.js';

export function openCandidate(app, record, revision) {
  if (record.result_kind === 'content_update') {
    app.go({surface: 'content', layer: 'content', page_id: null, revision, candidate_id: record.candidate_id, task_id: null});
    return;
  }
  app.go({surface: 'page', page_id: record.page_id, layer: record.stage === 'blueprint' ? 'original_image' : record.stage === 'content' ? 'content' : 'svg',
    revision, candidate_id: record.candidate_id, task_id: null});
}
export function trialActions(app, data) {
  if (!app.business || !app.health.ui_capabilities?.includes('candidates.v1') || !['original_image', 'svg', 'ppt'].includes(app.route.layer)) return el('div');
  const image = app.route.layer === 'original_image', slot = image ? 'blueprint' : 'svg';
  const node = el('section', {class: 'panel trial-actions', 'aria-label': '本页试作与候选'});
  // The near-field entry names how much already waits here, so a returned
  // candidate is not hidden until the user happens to open the panel.
  const counts = el('span', {class: 'trial-counts muted'}, '');
  const entry = el('details', {class: 'page-trial-entry'}, el('summary', {}, el('span', {}, '本页候选与试作'), counts), node);
  const candidateList = el('div', {class: 'row wrap'}), notice = el('p', {role: 'status'});
  const instruction = el('textarea', {rows: 3, 'aria-label': '本页试作短要求', placeholder: image ? '例如：沿用参考图的分区和线条，保留本页事实与数字。' : '例如：修复右侧模块重叠，保留 Page、原图和实际提示词。'});
  const stage = el('select', {'aria-label': '本页试作阶段'}, image ? el('option', {value: 'blueprint'}, '原图试作') :
    [el('option', {value: 'repair'}, '仅修 SVG'), el('option', {value: 'reconstruct'}, '对照原图重新还原 SVG')]);
  const reference = el('select', {'aria-label': '固定参考原图'}, el('option', {value: ''}, '不使用参考图'));
  const options = new Map();
  for (const page of app.summary.pages) {
    const original = page.stages.blueprint;
    if (original?.existence !== 'recorded') continue;
    options.set(page.page_id, {page_id: page.page_id, revision_id: data.revision_id, artifact_ref: original.ref, file: original.file, role: 'reference'});
    reference.append(el('option', {value: page.page_id}, `${page.page_id} · ${page.title || '原图'} · ${version(data.revision_id)}`));
  }
  let fixedReference = image ? options.get(data.page_id) || null : null, preview = null, busy = false, loaded = false, disposed = false, serial = 0, refRelease;
  reference.value = fixedReference?.page_id || '';
  const refView = el('div', {class: 'trial-reference'}), impact = el('div', {class: 'stack'});
  const compare = button('刷新本页候选', loadCandidates);
  const planButton = button('预览本页试作', planTrial, false), commitButton = button('保存并交接这次试作', commitTrial, true, {disabled: true});
  const referenceArea = image ? el('div', {class: 'stack'}, el('label', {}, '参考原图（固定版本）', reference), refView) : null;
  const form = el('details', {class: 'trial-form'}, el('summary', {}, image ? '试作这页原图' : '仅重建或修复本页 SVG'),
    el('div', {class: 'panel-body stack'}, el('p', {}, image ? '保留目标页标题、事实与数字；返回候选后再决定是否采用。' : '保留 Page、原图及其实际提示词；这一阶段不调用图像工具。'),
      el('label', {}, '阶段', stage), referenceArea, el('label', {}, '一句话要求', instruction),
      el('p', {class: 'muted'}, '试作自身不替换当前稿；已有自动生产仍可继续。'),
      el('div', {class: 'row wrap'}, planButton, commitButton), impact));
  node.append(el('div', {class: 'panel-head'}, el('h2', {}, '本页候选'), compare), el('div', {class: 'panel-body stack'}, notice,
    el('p', {class: 'muted field-help'}, '列表固定在当前阅读版本；新返回的候选可在「任务与交付」中查看。'), candidateList), form);
  function editor() { return app.editor; }
  function state() { return {instruction: instruction.value, stage: stage.value, reference: fixedReference}; }
  function controls() {
    const blocked = Boolean(app.readonly || app.info.sample?.readonly || editor()?.readonly || busy || !loaded || !editor() || app.business.entries.size || app.business.loadWarning);
    planButton.disabled = blocked; commitButton.disabled = blocked || !preview;
    instruction.readOnly = Boolean(!loaded || app.readonly || app.info.sample?.readonly || editor()?.readonly); stage.disabled = instruction.readOnly; reference.disabled = instruction.readOnly;
  }
  function renderReference() {
    refRelease?.(); refRelease = null; refView.replaceChildren();
    if (!fixedReference) return;
    const view = imageView(app, {file: fixedReference.file, media_type: 'image/png'}, '固定参考原图', {kind: 'thumb'});
    refRelease = () => view.dispose();
    refView.append(view.node, el('p', {class: 'muted'}, `${fixedReference.page_id} · ${version(fixedReference.revision_id)} · 自动更新不会替换此图`));
  }
  function changed() {
    serial++; preview = null; impact.replaceChildren();
    const current = editor(); if (current && !current.readonly && !current.disposed) {
      current.draft.content.trial = state(); current.changed();
    }
    controls();
  }
  instruction.addEventListener('input', changed); stage.addEventListener('change', changed);
  reference.addEventListener('change', () => { fixedReference = options.get(reference.value) || null; renderReference(); changed(); });
  async function loadCandidates() {
    try {
      const value = await get('/api/candidates?' + new URLSearchParams({page_id: data.page_id, revision: data.revision_id})); if (disposed) return;
      const records = value.candidates.filter(item => item.candidate.stage === slot);
      candidateList.replaceChildren(...records.map((item, index) => button(`候选 ${index + 1}${item.status === 'adopted' ? ' · 曾采用' : ''}`, () => openCandidate(app, item.candidate, data.revision_id))));
      const pending = records.filter(item => item.pending).length;
      counts.textContent = records.length ? `候选 ${records.length} · 待比较 ${pending}` : '尚无候选';
      notice.textContent = records.length ? `${records.length} 个已返回候选；选择一个查看固定比较。` : '尚无本层候选。可以先保存一次明确范围的试作要求。';
    } catch (error) { if (!disposed) notice.textContent = readableError(error); }
  }
  async function planTrial() {
    if (busy) return; busy = true; const attempt = ++serial; preview = null; controls();
    try {
      await app.business.available(); await editor().ready;
      if (!instruction.value.trim()) throw new Error('请先写一句具体要求，输入会保留。');
      const latest = await get('/api/view/summary'); if (disposed || attempt !== serial) return;
      const target = latest.pages.find(p => p.page_id === data.page_id);
      if (!target || canonical(target.stages.content.ref) !== canonical(data.stages.content.ref) || canonical(target.stages[slot].ref) !== canonical(data.stages[slot].ref)) {
        impact.replaceChildren(el('p', {class: 'field-error'}, '目标页或当前产物已变化，未按旧图安排试作。要求与固定参考图已保留。'),
          button('查看新当前稿后重新计划', () => app.go({revision: latest.revision_id, candidate_id: null}))); return;
      }
      const input = {schema_version: 'change_intent.v1', project_id: latest.project_id, base_revision: latest.revision_id,
        mode: 'trial', intent: image ? 'reference_correction' : 'svg_repair', instruction: instruction.value, annotation_refs: [], max_calls: image ? 1 : 0,
        targets: [{page_id: data.page_id, page_ref: target.stages.content.ref, layer: image ? 'original_image' : 'svg', stage: stage.value, artifact_ref: target.stages[slot].ref}],
        references: image && fixedReference ? [{page_id: fixedReference.page_id, revision_id: fixedReference.revision_id, artifact_ref: fixedReference.artifact_ref, role: 'reference'}] : []};
      const result = await post('/api/changes/plan', {input}); if (disposed || attempt !== serial) return;
      preview = result;
      impact.replaceChildren(el('p', {}, `${data.page_id} 将产生一个${image ? '原图' : 'SVG'}候选，最多 ${result.plan.max_calls} 次图像调用。`),
        el('p', {class: 'muted'}, `采用后仅本页${image ? ' SVG、' : ''}预览和整稿 PPT 需要更新；计划基准 ${version(latest.revision_id)}。`));
    } catch (error) { if (!disposed && attempt === serial) impact.replaceChildren(el('p', {class: 'field-error'}, readableError(error))); }
    finally { busy = false; if (!disposed) controls(); }
  }
  async function commitTrial() {
    if (!preview || busy) return; busy = true; controls(); const selected = preview;
    try {
      await app.business.submit(editor(), 'changes.commit', {plan_id: selected.plan_id, base_revision: selected.plan.base_revision},
        {plan_id: selected.plan_id, plan: selected.plan}, result => {
          preview = null;
          app.go({surface: 'runs', revision: result.revision_id, task_id: result.task_ids[0], candidate_id: null});
        });
    } catch (error) { impact.replaceChildren(el('p', {class: 'field-error'}, readableError(error))); }
    finally { busy = false; if (!disposed) controls(); }
  }
  const sync = () => controls(); app.root.addEventListener('business-state-changed', sync); app.root.addEventListener('draft-state-changed', sync);
  function hydrate() {
    const current = editor(); loaded = false; serial++; preview = null; impact.replaceChildren(); controls();
    current?.ready.then(() => {
      if (disposed || current !== editor()) return;
      loaded = true; instruction.value = ''; stage.value = image ? 'blueprint' : 'repair';
      fixedReference = image ? options.get(data.page_id) || null : null;
      reference.querySelector('option[value="saved-reference"]')?.remove();
      const saved = current.draft.content.trial;
      if (saved && typeof saved.instruction === 'string') {
        instruction.value = saved.instruction;
        if ([...stage.options].some(option => option.value === saved.stage)) stage.value = saved.stage;
        fixedReference = image ? saved.reference || null : null;
        if (fixedReference) {
          const key = 'saved-reference'; options.set(key, fixedReference);
          reference.append(el('option', {value: key}, `${fixedReference.page_id} · ${version(fixedReference.revision_id)} · 已固定`));
          reference.value = key;
        } else reference.value = '';
      } else reference.value = fixedReference?.page_id || '';
      renderReference(); controls();
    });
  }
  app.root.addEventListener('draft-editor-replaced', hydrate);
  hydrate();
  loadCandidates(); controls();
  app.disposables.push(() => { disposed = true; serial++; refRelease?.(); app.root.removeEventListener('draft-editor-replaced', hydrate); app.root.removeEventListener('business-state-changed', sync); app.root.removeEventListener('draft-state-changed', sync); });
  return entry;
}
