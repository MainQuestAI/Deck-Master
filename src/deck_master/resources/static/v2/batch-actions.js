import {get, post, readableError} from './api.js';
import {el, button, version} from './dom.js';
import {DraftEditor} from './drafts.js';
import {imageView} from './images.js';
import {batchNames, batchExclusion, batchInput} from './batch-policy.js';

export function batchActions(app, selected, onSelectionChange) {
  const pages = app.summary.pages, label = id => {
    const index = pages.findIndex(page => page.page_id === id);
    return index < 0 ? id : `第 ${index + 1} 页 · ${pages[index].title || '未命名页面'}`;
  };
  let serial = 0, disposed = false, busy = false, plan = null, fixed = null, referenceView;
  const action = el('select', {'aria-label': '批量动作'}, Object.entries(batchNames).map(([value, name]) => el('option', {value}, name)));
  const toolbar = el('label', {class: 'row'}, '选页用于', action);
  const notice = el('p', {role: 'status'}), excluded = el('div', {class: 'stack'}), impact = el('div', {class: 'stack batch-impact'});
  const instruction = el('textarea', {rows: 2, maxLength: 4000, 'aria-label': '所选页的制作要求', placeholder: '写明本次需要修改的内容和应保留的内容。'});
  // 返回/刷新后要求保留（F05/AC06）：要求是个人工作配置，保存在本机项目键下；
  // 它不是业务草稿，也不进入任何提交 payload，直到用户明确预览。
  const workingKey = 'deck-master:overview-working:' + app.info.project_identity;
  try { const storedWorking = JSON.parse(localStorage.getItem(workingKey) || '{}'); if (typeof storedWorking.instruction === 'string') instruction.value = storedWorking.instruction; } catch { /* 读取失败则从空要求开始 */ }
  const saveWorking = () => { try { localStorage.setItem(workingKey, JSON.stringify({instruction: instruction.value})); } catch { /* 要求保留在本页 */ } };
  instruction.addEventListener('input', saveWorking);
  const reference = el('select', {'aria-label': '批量固定参考原图'}, el('option', {value: ''}, '不指定参考，进入风格面后仍可确认'));
  const refs = new Map();
  for (const page of pages) if (page.stages.blueprint?.existence === 'recorded' && page.stages.blueprint.file) {
    refs.set(page.page_id, {page_id: page.page_id, revision_id: app.route.revision, artifact_ref: page.stages.blueprint.ref, file: page.stages.blueprint.file, role: 'reference'});
    reference.append(el('option', {value: page.page_id}, label(page.page_id)));
  }
  const refPicture = el('div', {class: 'batch-reference'});
  const budget = el('input', {type: 'number', min: 0, max: 300, value: 0, 'aria-label': '批量图像调用上限'});
  const exactBudget = button('按所选页设置调用上限', () => { budget.value = String(selected.size); invalidate(); render(); });
  const budgetArea = el('div', {class: 'row wrap'}, el('label', {}, '本次图像调用上限', budget), exactBudget);
  const preview = button('预览所选页试作', previewSelection);
  const commit = button('保存并交接所选试作', commitSelection, true, {disabled: true});
  const toStyle = button('带所选页进入风格校准', enterStyle, true);
  // F05/§4.1：空选页只提示如何选页，不展开整套调用参数；有选择时才显示
  // 配置区（所选页摘要—要求—可选参考—真实调用影响—预览/确认）。
  // OV-02：阻断原因就近贴在对应字段，而不是只汇成面板级一句话。
  const requirementError = el('p', {class: 'field-error', role: 'alert', hidden: true});
  const budgetError = el('p', {class: 'field-error', role: 'alert', hidden: true});
  const fields = el('div', {class: 'stack batch-fields'}, excluded,
    el('label', {}, '一句话要求', instruction), requirementError,
    el('label', {}, '固定参考原图（可选）', reference), refPicture,
    budgetArea, budgetError, el('div', {class: 'row wrap'}, preview, commit, toStyle), impact);
  const node = el('section', {class: 'panel batch-actions', 'aria-label': '所选页制作'},
    el('div', {class: 'panel-head'}, el('h2', {}, '所选页制作')),
    el('div', {class: 'panel-body stack'}, notice, fields));
  if (app.business && app.health.ui_capabilities?.includes('ui_draft.v1')) {
    app.editor = new DraftEditor(app.info, {scope: 'project', page_id: null, layer: 'notes'}, app.route.revision, null, {readonly: app.readonly});
    node.lastChild.append(el('details', {}, el('summary', {}, '个人记录与提交恢复'), app.editor.mount()));
  }
  let editor = app.editor;
  function exclusions() { return [...selected].map(id => ({id, reason: batchExclusion(app, pages.find(page => page.page_id === id), action.value, fixed)})).filter(item => item.reason); }
  function invalidate() { serial++; plan = null; impact.replaceChildren(); }
  function render() {
    const unavailable = exclusions(), image = action.value === 'blueprint', style = action.value === 'style';
    fields.hidden = !selected.size;
    const saving = !editor || editor.disposed || editor.readonly || ['loading', 'unknown', 'conflict', 'saving'].includes(editor.status);
    const calls = Number(budget.value), budgetInvalid = image && (!Number.isInteger(calls) || calls < selected.size || calls > 300);
    notice.textContent = selected.size ? `${selected.size} 页用于${batchNames[action.value]}${unavailable.length ? `，其中 ${unavailable.length} 页需要调整范围` : ''}。` : '先选择动作，再勾选此动作允许处理的页面。选页不会自动执行；已选范围随个人阅读状态保留，计划仍需重新预览。';
    excluded.replaceChildren(...(unavailable.length ? [el('p', {class: 'field-error'}, '未自动忽略任何页。明确调整范围后才可预览：'),
      el('ul', {}, unavailable.map(item => el('li', {}, label(item.id) + '：' + item.reason))),
      button('移除列出的受限页', () => { unavailable.forEach(item => selected.delete(item.id)); invalidate(); onSelectionChange(); })] : []));
    budgetArea.hidden = !image; exactBudget.disabled = !selected.size || busy;
    reference.disabled = busy || app.readonly || !['blueprint', 'style'].includes(action.value);
    refPicture.hidden = !['blueprint', 'style'].includes(action.value);
    instruction.readOnly = busy || app.readonly;
    const blocked = busy || saving || !selected.size || unavailable.length > 0;
    // §4.1「核对后才出现交接主动作」：没有当前有效计划时交接按钮不出现。
    const planReady = Boolean(plan) && plan.plan.base_revision === app.latest?.revision_id;
    preview.hidden = style; commit.hidden = style || !planReady; toStyle.hidden = !style;
    preview.disabled = blocked || budgetInvalid || !instruction.value.trim();
    commit.disabled = blocked || !planReady;
    toStyle.disabled = blocked;
    // 字段级原因：要求为空、原图上限不足时，原因贴在对应输入旁边。
    const missingRequirement = selected.size > 0 && !instruction.value.trim();
    requirementError.hidden = !missingRequirement;
    requirementError.textContent = missingRequirement ? '先写明本次要修改和要保留的内容，才能预览所选页试作。' : '';
    instruction.setAttribute('aria-invalid', String(missingRequirement));
    const badBudget = budgetInvalid && selected.size > 0;
    budgetError.hidden = !badBudget;
    budgetError.textContent = badBudget ? `原图需要 ${selected.size} 次调用；请填写允许的上限，当前为 ${budget.value}。` : '';
    budget.setAttribute('aria-invalid', String(badBudget));
    if (saving && selected.size) notice.textContent += ' 个人保存状态尚未就绪，请先核实。';
  }
  action.addEventListener('change', () => { invalidate(); onSelectionChange(); });
  instruction.addEventListener('input', () => { invalidate(); render(); });
  budget.addEventListener('input', () => { invalidate(); render(); });
  reference.addEventListener('change', () => {
    fixed = refs.get(reference.value) || null; referenceView?.dispose(); referenceView = null; refPicture.replaceChildren();
    if (fixed) { referenceView = imageView(app, {file: fixed.file, media_type: 'image/png'}, '批量固定参考原图', {kind: 'thumb'}); refPicture.append(referenceView.node, el('p', {}, label(fixed.page_id) + ' · ' + version(fixed.revision_id))); }
    invalidate(); onSelectionChange();
  });
  async function previewSelection() {
    if (preview.disabled || busy) return;
    busy = true; invalidate(); const token = serial; render();
    try {
      await app.business.available(); await editor.ready;
      const latest = await get('/api/view/summary');
      if (disposed || token !== serial) return;
      if (latest.revision_id !== app.route.revision) throw new Error('项目已有新版本。要求与选页仍保留，请先读取新版本后明确重选。');
      if (exclusions().length) throw new Error('所选页仍有受限项，未缩减或提交范围。');
      const ids = pages.filter(page => selected.has(page.page_id)).map(page => page.page_id);
      const input = batchInput(latest, ids, action.value, instruction.value, Number(budget.value), fixed);
      const result = await post('/api/changes/plan', {input});
      if (disposed || token !== serial) return;
      if (app.latest.revision_id !== input.base_revision) throw new Error('项目已有新版本，旧计划已失效；选页与要求保留。');
      if (result.plan.base_revision !== input.base_revision || new Set(result.plan.actions.map(item => item.page_id)).size !== ids.length || result.plan.actions.length !== ids.length || result.plan.actions.some(item => !ids.includes(item.page_id) || item.stage !== action.value)) throw new Error('服务计划与所选范围不一致，未允许提交。');
      plan = result;
      impact.replaceChildren(el('h3', {}, '确认本次范围'), el('p', {}, `${version(result.plan.base_revision)} · ${ids.length} 页 · ${batchNames[action.value]} · 图像调用 ${result.plan.max_calls} 次${action.value === 'blueprint' ? `（已明确允许最多 ${input.max_calls} 次）` : ''}。`),
        el('ul', {}, result.plan.actions.map(item => el('li', {}, label(item.page_id) + ' · ' + batchNames[item.stage] + ' · 采用后更新：' + item.downstream.map(key => ({svg:'SVG', svg_preview:'SVG 预览', ppt_preview:'PPT 预览', deck_outputs:'整稿产物', quality_applicability:'检查依据'})[key] || key).join('、')))),
        el('p', {}, fixed && action.value === 'blueprint' ? '固定参考：' + label(fixed.page_id) + ' · ' + version(fixed.revision_id) : '本次不使用参考原图。'),
        el('p', {class: 'muted'}, '保存只创建待交接任务；返回候选后再决定采用。采用后将使下游预览、整稿及相关检查依据失效。'),
        el('details', {}, el('summary', {}, '固定引用与完整影响'), el('pre', {class: 'evidence-json'}, JSON.stringify(result.plan, null, 2))));
    } catch (error) { if (!disposed && token === serial) impact.replaceChildren(el('p', {role: 'alert', class: 'field-error'}, readableError(error))); }
    finally { busy = false; if (!disposed) render(); }
  }
  async function commitSelection() {
    if (commit.disabled || !plan || busy) return;
    busy = true; render(); const approved = plan, token = serial;
    try {
      await app.business.submit(editor, 'changes.commit', {plan_id: approved.plan_id, base_revision: approved.plan.base_revision}, {plan_id: approved.plan_id, plan: approved.plan}, result => {
        if (disposed || token !== serial) return;
        plan = null;
        // D1（评审裁决）：交接成功即周期结束——清空制作要求，防止旧要求/旧预算
        // 预填进下一批页面。刷新与版本前进期间的留存语义不变（AC08）。
        instruction.value = '';
        try { localStorage.removeItem(workingKey); } catch { /* 存储不可用时以输入框为准 */ }
        impact.replaceChildren(el('p', {class: 'success-note'}, `已保存 ${result.task_ids.length} 项待交接任务，尚未开始制作。`),
          button('查看本次交接', () => app.go({surface: 'runs', revision: result.revision_id, task_id: result.task_ids.length === 1 ? result.task_ids[0] : null, candidate_id: null})));
      });
    } catch (error) { if (!disposed && token === serial) impact.replaceChildren(el('p', {role: 'alert'}, readableError(error))); }
    finally { busy = false; if (!disposed) render(); }
  }
  function enterStyle() {
    if (toStyle.disabled) return;
    app.styleSelection = {project_identity: app.info.project_identity, revision: app.route.revision,
      target_ids: pages.filter(page => selected.has(page.page_id)).map(page => page.page_id),
      target_refs: pages.filter(page => selected.has(page.page_id)).map(page => ({page_id: page.page_id, page_ref: page.stages.content.ref})),
      reference: fixed, instruction: instruction.value};
    app.go({surface: 'style', page_id: null, candidate_id: null, task_id: null, revision: app.route.revision});
  }
  const sync = () => { if (!disposed) { if (!busy && plan && plan.plan.base_revision !== app.latest.revision_id) invalidate(); onSelectionChange(); } };
  const replaced = () => { editor = app.editor; invalidate(); sync(); editor?.ready.then(sync); };
  app.root.addEventListener('summary-refreshed', sync); app.root.addEventListener('business-state-changed', sync); app.root.addEventListener('draft-state-changed', sync);
  app.root.addEventListener('draft-editor-replaced', replaced);
  app.disposables.push(() => { disposed = true; serial++; referenceView?.dispose(); app.root.removeEventListener('summary-refreshed', sync); app.root.removeEventListener('business-state-changed', sync); app.root.removeEventListener('draft-state-changed', sync); app.root.removeEventListener('draft-editor-replaced', replaced); });
  editor?.ready.then(() => { if (!disposed) { render(); onSelectionChange(); } });
  render();
  return {node, toolbar, render, invalidate, eligible: page => !batchExclusion(app, page, action.value, fixed),
    // AC06/§2.1（深度复审）：长列表里选择摘要与配置入口必须持续可达——
    // 概览用这两个方法渲染常驻选择条，并让「配置要求」把用户带回配置区。
    selectionSummary: hidden => selected.size ? `已选 ${selected.size} 页用于${batchNames[action.value]}${hidden ? ` · 筛选外 ${hidden} 页` : ''}` : '',
    selectedCount: () => selected.size,
    openConfig: () => { node.scrollIntoView({block: 'center'}); instruction.focus({preventScroll: true}); }};
}
