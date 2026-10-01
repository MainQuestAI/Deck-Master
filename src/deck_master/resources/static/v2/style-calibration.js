import {get, post, canonical, readableError} from './api.js';
import {el, button, heading, empty, version} from './dom.js';
import {DraftEditor} from './drafts.js';
import {imageView} from './images.js';
import {textObject} from './text-selection.js';
import {observerLabels} from './request-view.js';
import {openCandidate} from './trial-actions.js';

const names = {palette: '配色', typography: '文字层级', density: '密度', lines: '线条', composition: '构图'};
const defaults = {palette: '借用参考页配色', typography: '借用参考页文字层级'};
const section = (title, ...body) => el('section', {class: 'panel'}, el('div', {class: 'panel-head'}, el('h2', {}, title)), el('div', {class: 'panel-body stack'}, body));
const detail = (title, ...body) => el('details', {}, el('summary', {}, title), el('div', {class: 'stack'}, body));
const json = value => el('pre', {class: 'evidence-json'}, JSON.stringify(value, null, 2));

export function style(app) {
  if (!app.health.ui_capabilities?.includes('style_recipes.v1')) return empty('核心需要升级', '风格校准需要支持固定配方与候选试作的核心。');
  app.editor = new DraftEditor(app.info, {scope: 'project', page_id: null, layer: 'notes'}, app.route.revision, null, {readonly: app.readonly});
  const draftNode = app.editor.mount();
  let disposed = false, loaded = false, busy = false, serial = 0, sourceSerial = 0, proposal = null, plan = null, recipe = null;
  let fixed = null, selected = new Set(), resolutions = {}, promptSelection = null, parent = null, release;
  const options = new Map(), pages = app.summary.pages;
  const label = id => {
    const index = pages.findIndex(p => p.page_id === id);
    return index < 0 ? id : `第 ${index + 1} 页 · ${pages[index].title || '未命名页面'}`;
  };
  const reference = el('select', {'aria-label': '风格参考原图'}, el('option', {value: ''}, '选择一页已有原图'));
  for (const page of pages) if (page.stages.blueprint.existence === 'recorded') {
    options.set(page.page_id, {page_id: page.page_id, revision_id: app.route.revision, artifact_ref: page.stages.blueprint.ref, file: page.stages.blueprint.file, role: 'reference'});
    reference.append(el('option', {value: page.page_id}, label(page.page_id)));
  }
  const referenceView = el('div', {class: 'style-reference'}), sourceView = el('div', {class: 'stack'});
  const targets = el('div', {class: 'style-targets'});
  const instruction = el('textarea', {rows: 3, maxLength: 4000, 'aria-label': '风格短要求', value: '借用参考页配色和文字层级，保留目标页标题、事实、数字与构图。'});
  const targetSource = el('select', {'aria-label':'核对目标页提示词'}, el('option', {value:''}, '选择目标页，读取同一阅读版本的原文'), ...pages.map(p => el('option', {value:p.page_id}, label(p.page_id))));
  const targetSourceView = el('div', {class:'stack'}); let targetSourceSerial = 0;
  targetSource.addEventListener('change', async () => {
    const token = ++targetSourceSerial; targetSourceView.replaceChildren(); if (!targetSource.value) return;
    try {
      const data = await get('/api/pages/'+encodeURIComponent(targetSource.value)+'/lineage?'+new URLSearchParams({revision:app.route.revision}));
      if (disposed || token !== targetSourceSerial) return;
      targetSourceView.append(el('p', {}, '目标页原文 · '+version(data.revision_id)), el('p', {class:'muted'}, observerLabels[data.prompts.submitted.observer] || observerLabels.unknown));
      for (const [layer,title] of [['submitted_prompt','目标实际提交原文'],['prepared_prompt','目标预备与冻结原文']]) {
        const sources = data.text_sources?.[layer] || [];
        targetSourceView.append(detail(title, sources.length ? sources.map(source => el('pre', {class:'read-text'}, source.text)) : el('p', {}, '未知，未用推测补入。')));
      }
    } catch (error) { if (!disposed && token === targetSourceSerial) targetSourceView.append(el('p', {class:'field-error'}, readableError(error))); }
  });
  const dimensions = new Map();
  const dimensionFields = Object.entries(names).map(([key, title]) => {
    const check = el('input', {type: 'checkbox', checked: key in defaults, 'aria-label': '借用' + title});
    const text = el('input', {value: defaults[key] || '借用参考页' + title, 'aria-label': title + '要求'});
    dimensions.set(key, {check, text}); check.addEventListener('change', changed); text.addEventListener('input', changed);
    return el('div', {class: 'row wrap'}, el('label', {class: 'inline-control'}, check, title), text);
  });
  const suggestion = el('textarea', {rows: 3, maxLength: 12000, 'aria-label': '未确认的 Host 风格建议', placeholder: '可粘贴制作工具给出的风格建议；建议不会冒充历史实际提示词。'});
  const excerpt = el('div', {class: 'stack'}), preview = el('div', {class: 'stack'}), notice = el('p', {role: 'status'});
  const proposeButton = button('检查风格要求', propose, true);
  const confirmButton = button('确认这版风格要求', confirm, true, {disabled: true});
  const recipes = el('select', {'aria-label': '已确认的风格版本'}, el('option', {value: ''}, '选择已确认版本'));
  const recipeView = el('div', {class: 'stack'}), trialPage = el('select', {'aria-label': '先试哪一页'});
  const adoptedCandidate = el('input', {'aria-label': '已采用的风格候选编号', placeholder: '选择下方已采用候选，或粘贴候选编号'});
  const expansionTargets = el('div', {class: 'style-targets'}), expansion = new Set();
  const calls = el('input', {type: 'number', min: 1, value: 1, 'aria-label': '扩展图像调用上限'});
  const firstButton = button('预览单页试作', () => planTrial(false));
  const expandButton = button('预览明确选页的扩展', () => planTrial(true));
  const dispatchButton = button('保存并交接风格试作', dispatch, true, {disabled: true});
  const impact = el('div', {class: 'stack'}), candidateRows = el('div', {class: 'stack'});
  const node = el('div', {class: 'style-calibration stack'}, heading('风格校准', '固定一张参考原图，保留目标内容。先试一页，比较采用后再扩展。'),
    section('1 · 选择参考与目标', el('label', {}, '固定参考原图', reference), referenceView,
      el('p', {class: 'muted'}, '参考版本持续固定；目标勾选只限定可试作范围，不会同时开始生成。'), targets,
      el('label', {}, '一句话要求', instruction), detail('高级：借用维度、原文选段与建议',
        dimensionFields, el('p', {class: 'muted'}, '构图须单独选择。生成仍可能偏离，返回后逐项核对。'),
        sourceView, excerpt, detail('对照目标页原文', targetSource, targetSourceView), el('label', {}, '制作工具建议（待你确认）', suggestion)),
      el('div', {class: 'row wrap'}, proposeButton, confirmButton), notice, preview),
    section('2 · 确认版本与单页试作', el('div', {class: 'row wrap'}, recipes, button('刷新风格版本', loadRecipes)), recipeView,
      el('label', {}, '先试一页', trialPage), firstButton,
      detail('采用满意候选后，扩到明确选择的其它页',
        el('label', {}, '已采用候选', adoptedCandidate), expansionTargets,
        el('label', {}, '本次调用上限', calls), expandButton),
      impact, dispatchButton),
    section('3 · 比较候选，再决定采用', el('p', {class: 'muted'}, '候选返回不替换当前稿；到固定比较中逐页核对文字、配色及未选择的维度。'),
      button('刷新风格目标候选', loadCandidates), candidateRows), draftNode);
  function editor() { return app.editor; }
  function state() { return {reference: fixed, targets: [...selected], instruction: instruction.value, dimensions: Object.fromEntries([...dimensions].filter(([,v]) => v.check.checked).map(([k,v]) => [k,v.text.value])), host_suggestion: suggestion.value, prompt_selection: promptSelection, resolutions, parent_recipe_id: parent}; }
  function controls() {
    const blocked = !loaded || busy || app.readonly || editor()?.readonly || app.business.entries.size || app.business.loadWarning;
    const referenceConflict = fixed && selected.has(fixed.page_id);
    proposeButton.disabled = blocked || referenceConflict; confirmButton.disabled = blocked || referenceConflict || !proposal || proposal.proposal.conflicts.some(c => !c.resolution);
    firstButton.disabled = blocked || !recipe; expandButton.disabled = blocked || !recipe; dispatchButton.disabled = blocked || !plan;
    for (const input of [reference, instruction, suggestion, ...targets.querySelectorAll('input'), ...dimensions.values()].flatMap(v => v.check ? [v.check, v.text] : [v])) input.disabled = !loaded || app.readonly || busy || (input.dataset.reference === 'true' && !input.checked);
    if (referenceConflict) notice.textContent = '参考页同时在目标中。目标未被自动移除，请明确取消这页目标后再检查要求。';
  }
  function persist() { if (loaded && !editor().readonly && !editor().disposed) { editor().draft.content.style_calibration = state(); editor().changed(); } }
  function changed() { serial++; proposal = null; preview.replaceChildren(); confirmButton.disabled = true; persist(); controls(); }
  function persistTrial() {
    if (!loaded || app.readonly || editor().disposed) return;
    editor().draft.content.style_trial = {recipe_id:recipe?.recipe_id || null, trial_page:trialPage.value, expansion:[...expansion], adopted_candidate_id:adoptedCandidate.value, max_calls:calls.value}; editor().changed();
  }
  function invalidatePlan(save = true) { serial++; plan = null; impact.replaceChildren(); if (save) persistTrial(); controls(); }
  function renderTargets() {
    targets.replaceChildren(...pages.map(p => {
      const check = el('input', {type: 'checkbox', checked: selected.has(p.page_id), 'aria-label': '风格目标 ' + label(p.page_id)});
      check.dataset.reference = String(p.page_id === fixed?.page_id);
      check.addEventListener('change', () => { check.checked ? selected.add(p.page_id) : selected.delete(p.page_id); resolutions = {}; notice.textContent = ''; changed(); });
      return el('label', {class: 'inline-control'}, check, label(p.page_id) + (p.page_id === fixed?.page_id ? ' · 固定参考，不作为试作目标' : ''));
    }));
  }
  async function showReference() {
    const token = ++sourceSerial; release?.(); release = null; referenceView.replaceChildren(); sourceView.replaceChildren();
    if (!fixed) return;
    referenceView.append(el('p', {}, `${label(fixed.page_id)} · ${version(fixed.revision_id)} · 已固定`));
    try {
      const data = await get('/api/pages/' + encodeURIComponent(fixed.page_id) + '/lineage?' + new URLSearchParams({revision: fixed.revision_id}));
      if (disposed || token !== sourceSerial) return;
      if (canonical(data.stages.blueprint.ref) !== canonical(fixed.artifact_ref)) throw new Error('参考原图与固定版本不一致，未替换参考。');
      const view = imageView(app, data.stages.blueprint, '固定风格参考原图', {kind: 'large'}); release = () => view.dispose(); referenceView.prepend(view.node);
      sourceView.append(el('p', {class: 'muted'}, observerLabels[data.prompts.submitted.observer] || observerLabels.unknown));
      for (const [layer, title] of [['submitted_prompt', '实际提交原文'], ['prepared_prompt', '预备与冻结原文']]) {
        const sources = data.text_sources?.[layer] || [];
        if (!sources.length) { sourceView.append(el('p', {}, title + '：未知，未用推测补入。')); continue; }
        const chooser = el('select', {'aria-label': title + '对象'}, sources.map((s,i) => el('option', {value:i}, `${i + 1} · ${s.text.slice(0,36)}`)));
        const slot = el('div');
        const show = () => slot.replaceChildren(textObject(app, sources[Number(chooser.value)], {revision: fixed.revision_id, pageId: fixed.page_id, layer, label: title}));
        slot.addEventListener('text-range-validated', event => { if (app.readonly) return; promptSelection = {layer, selection: event.detail.selection}; renderExcerpt(); changed(); });
        chooser.addEventListener('change', show); show(); sourceView.append(detail(title, chooser, slot));
      }
    } catch (error) { if (!disposed && token === sourceSerial) sourceView.replaceChildren(el('p', {class: 'field-error'}, readableError(error))); }
  }
  function renderExcerpt() { excerpt.replaceChildren(...(promptSelection ? [el('p', {}, '仅借用已校验选段：'), el('blockquote', {}, promptSelection.selection.excerpt), button('移除风格选段', () => { promptSelection = null; renderExcerpt(); changed(); })] : [])); }
  reference.addEventListener('change', () => { fixed = options.get(reference.value) || null; promptSelection = null; resolutions = {}; renderExcerpt(); renderTargets(); showReference(); changed(); });
  instruction.addEventListener('input', changed); suggestion.addEventListener('input', changed);
  async function propose() {
    if (busy) return; busy = true; const token = ++serial; proposal = null; controls();
    try {
      await app.business.available(); if (!fixed || !selected.size) throw new Error('请选择一张参考原图和至少一页目标。');
      const latest = await get('/api/view/summary'); if (disposed || token !== serial) return;
      for (const id of selected) {
        const old = pages.find(p => p.page_id === id), current = latest.pages.find(p => p.page_id === id);
        if (!current || canonical(old.stages.content.ref) !== canonical(current.stages.content.ref) || canonical(old.stages.blueprint.ref) !== canonical(current.stages.blueprint.ref)) throw new Error(label(id) + ' 的内容或原图已改变，请查看当前版本后重新选择。输入与固定参考仍保留。');
      }
      const value = state();
      const input = {schema_version:'style_input.v1', project_id:app.info.project_id, base_revision:latest.revision_id,
        reference: Object.fromEntries(Object.entries(fixed).filter(([k]) => k !== 'file')), target_page_ids: value.targets,
        instruction:value.instruction, dimensions:value.dimensions, resolutions};
      if (promptSelection) input.prompt_selection = promptSelection;
      if (suggestion.value.trim()) input.host_suggestion = suggestion.value;
      if (parent) input.parent_recipe_id = parent;
      const result = await post('/api/styles/propose', {input}); if (disposed || token !== serial) return;
      proposal = result; notice.textContent = '要求已检查；确认版本不会调用模型。';
      preview.replaceChildren(el('p', {}, `保留 ${result.proposal.targets.length} 页内容；默认先试其中 1 页。`), ...result.proposal.conflicts.map(c => {
        const choice = el('select', {'aria-label': label(c.page_id) + ' 密度取舍'}, el('option', {value:''}, '明确选择取舍'), el('option', {value:'keep_target'}, '保留目标页密度'), el('option', {value:'use_reference'}, '允许参考密度替代目标'));
        choice.value = c.resolution || ''; choice.addEventListener('change', () => { if (choice.value) resolutions[c.conflict_id] = choice.value; else delete resolutions[c.conflict_id]; proposal = null; serial++; persist(); controls(); notice.textContent = '取舍已保留，请重新检查要求。'; });
        return el('div', {class:'notice stack'}, el('strong', {}, label(c.page_id) + '：极简与高密度要求冲突'), choice, detail('查看冲突原文', json(c)));
      }), detail('相对上一版的差异', json(result.proposal.diff)), suggestion.value && el('p', {}, '确认后才使用上述制作工具建议；它不是历史实际提交记录。'));
    } catch (error) { if (!disposed && token === serial) notice.textContent = readableError(error); }
    finally { busy = false; if (!disposed) controls(); }
  }
  async function confirm() {
    if (!proposal || busy) return; busy = true; const value = proposal; controls();
    try { await app.business.submit(editor(), 'styles.confirm', {proposal_id:value.proposal_id, base_revision:value.proposal.base_revision}, {proposal_ref:value.proposal_ref}, async result => {
      proposal = null; notice.textContent = '这版风格要求已确认，尚未开始生成。'; await loadRecipes(result.recipe_id);
    }); } catch (error) { notice.textContent = readableError(error); }
    finally { busy = false; if (!disposed) controls(); }
  }
  let recipeRecords = new Map(), recipeSerial = 0;
  async function loadRecipes(chosen) {
    const token = ++recipeSerial;
    try {
      const result = await get('/api/styles' + (app.readonly ? '?' + new URLSearchParams({revision:app.route.revision}) : '')); if (disposed || token !== recipeSerial) return;
      await editor().ready; if (disposed || token !== recipeSerial) return;
      const keep = typeof chosen === 'string' ? chosen : recipes.value || editor().draft.content.style_trial?.recipe_id;
      recipeRecords = new Map(result.recipes.map(v => [v.recipe.recipe_id,v.recipe]));
      recipes.replaceChildren(el('option', {value:''}, '选择已确认版本'), ...result.recipes.map(({recipe:r},i) => el('option', {value:r.recipe_id}, `${i+1} · V${r.version} · ${r.input.instruction.slice(0,45)}`)));
      recipes.value = recipeRecords.has(keep) ? keep : ''; selectRecipe(true);
    } catch (error) { if (!disposed) notice.textContent = readableError(error); }
  }
  function selectRecipe(restore = false) {
    recipe = recipeRecords.get(recipes.value) || null; expansion.clear(); adoptedCandidate.value = ''; invalidatePlan(false); recipeView.replaceChildren(); trialPage.replaceChildren(); expansionTargets.replaceChildren();
    if (!recipe) return;
    recipeView.append(el('p', {}, `V${recipe.version} · 参考 ${label(recipe.input.reference.page_id)} · ${version(recipe.input.reference.revision_id)}`), el('p', {}, recipe.input.instruction),
      el('p', {class:'muted'}, '借用：' + Object.keys(recipe.dimensions).map(k => names[k]).join('、')),
      button('以此版本修改要求', () => {
        if (app.readonly) return; hydrateState({...recipe.input, reference: recipe.input.reference, targets:recipe.input.target_page_ids, parent_recipe_id:recipe.recipe_id}); changed();
      }), detail('固定版本差异与约束', json(recipe.diff), json(recipe.conflicts)));
    const saved = restore && editor().draft.content.style_trial?.recipe_id === recipe.recipe_id ? editor().draft.content.style_trial : null;
    if (saved) { adoptedCandidate.value = saved.adopted_candidate_id || ''; calls.value = saved.max_calls || 1; for (const id of saved.expansion || []) if (recipe.input.target_page_ids.includes(id)) expansion.add(id); }
    for (const id of recipe.input.target_page_ids) {
      trialPage.append(el('option', {value:id}, label(id)));
      const check = el('input', {type:'checkbox', checked:expansion.has(id), 'aria-label':'扩展到 '+label(id)});
      check.addEventListener('change', () => { check.checked ? expansion.add(id) : expansion.delete(id); invalidatePlan(); });
      expansionTargets.append(el('label', {class:'inline-control'}, check, label(id)));
    }
    if (saved?.trial_page && recipe.input.target_page_ids.includes(saved.trial_page)) trialPage.value = saved.trial_page;
    if (!restore) persistTrial(); loadCandidates(); controls();
  }
  recipes.addEventListener('change', () => selectRecipe());
  for (const input of [trialPage, adoptedCandidate, calls]) input.addEventListener('input', () => invalidatePlan());
  async function planTrial(expanding) {
    if (busy || !recipe) return; busy = true; const token = ++serial; plan = null; controls();
    try {
      await app.business.available(); const ids = expanding ? [...expansion] : [trialPage.value];
      if (!ids.length) throw new Error('请明确勾选本次扩展页。');
      const input = {recipe_id:recipe.recipe_id, page_ids:ids, max_calls:expanding ? Number(calls.value) : 1};
      if (expanding) { if (!adoptedCandidate.value.trim()) throw new Error('先在比较中采用满意候选，再选择该候选扩展。'); input.adopted_candidate_id = adoptedCandidate.value.trim(); }
      const result = await post('/api/styles/plan', {input}); if (disposed || token !== serial) return;
      plan = result; impact.replaceChildren(el('p', {}, `仅试作 ${ids.length} 页：${ids.map(label).join('、')}。最多 ${result.plan.max_calls} 次图像调用。`),
        el('p', {class:'muted'}, `返回候选不替换当前稿；采用后目标页下游产物需更新。计划基准 ${version(result.plan.base_revision)}。`));
    } catch (error) { if (!disposed && token === serial) impact.replaceChildren(el('p', {class:'field-error'}, readableError(error)), ...(error.details?.items || []).map(item => el('p', {}, `${label(item.page_id)}：目标基准已变，未替换新内容。可取消勾选后另建计划。`))); }
    finally { busy = false; if (!disposed) controls(); }
  }
  async function dispatch() {
    if (!plan || busy) return; busy = true; const value = plan; controls();
    try { await app.business.submit(editor(), 'changes.commit', {plan_id:value.plan_id, base_revision:value.plan.base_revision}, {plan_id:value.plan_id, plan:value.plan}, result => app.go({surface:'runs', revision:result.revision_id, task_id:result.task_ids[0], candidate_id:null})); }
    catch (error) { impact.replaceChildren(el('p', {class:'field-error'}, readableError(error))); }
    finally { busy = false; if (!disposed) controls(); }
  }
  let candidateSerial = 0;
  async function loadCandidates() {
    const token = ++candidateSerial, chosen = recipe;
    candidateRows.replaceChildren(); if (!chosen) return;
    try {
      const result = await get('/api/candidates' + (app.readonly ? '?' + new URLSearchParams({revision:app.route.revision}) : '')); if (disposed || token !== candidateSerial) return;
      const entries = result.candidates.filter(v => chosen.input.target_page_ids.includes(v.candidate.page_id) && v.candidate.stage === 'blueprint').slice(-30);
      candidateRows.append(...entries.map(v => el('div', {class:'row wrap'}, el('span', {}, label(v.candidate.page_id) + (v.status === 'adopted' ? ' · 曾采用' : ' · 待比较')),
        button('比较候选 '+v.candidate.candidate_id.slice(-6), () => openCandidate(app, v.candidate, result.revision_id)),
        v.status === 'adopted' && button('从此候选扩展', () => { adoptedCandidate.value = v.candidate.candidate_id; invalidatePlan(); }))));
      candidateRows.append(el('p', {class:'muted'}, '显示最近一批目标页候选。是否属于这版风格、仍被采用及依据有效，由扩展计划再次核对。'), button('到任务页查看全部候选', () => app.go({surface:'runs', revision:result.revision_id, task_id:null})));
    } catch (error) { if (!disposed && token === candidateSerial) candidateRows.append(el('p', {class:'field-error'}, readableError(error))); }
  }
  function hydrateState(value) {
    fixed = value.reference || null; selected = new Set(value.targets || []); instruction.value = value.instruction || ''; promptSelection = value.prompt_selection || null; parent = value.parent_recipe_id || null; resolutions = value.resolutions || {}; suggestion.value = value.host_suggestion || '';
    reference.querySelector('option[value="saved"]')?.remove();
    if (fixed) { options.set('saved', fixed); reference.append(el('option', {value:'saved'}, label(fixed.page_id)+' · '+version(fixed.revision_id))); reference.value = 'saved'; } else reference.value = '';
    for (const [key,v] of dimensions) { v.check.checked = key in (value.dimensions || defaults); v.text.value = value.dimensions?.[key] || defaults[key] || '借用参考页'+names[key]; }
    renderTargets(); renderExcerpt(); showReference();
  }
  function hydrate() {
    const current = editor(); loaded = false; serial++; proposal = null; plan = null; preview.replaceChildren(); impact.replaceChildren(); controls(); current.ready.then(() => {
      if (disposed || current !== editor()) return; loaded = true;
      const saved = current.draft.content.style_calibration;
      if (saved) hydrateState(saved); else renderTargets();
      if (app.styleSelection && !app.readonly) {
        const seed = app.styleSelection; delete app.styleSelection;
        const validContext = (!seed.project_identity || seed.project_identity === app.info.project_identity) && (!seed.revision || seed.revision === app.route.revision);
        const validTargets = (seed.target_ids || []).every(id => pages.some(page => page.page_id === id)) && (!seed.target_refs || seed.target_refs.length === seed.target_ids.length && seed.target_refs.every(ref => canonical(ref.page_ref) === canonical(pages.find(page => page.page_id === ref.page_id)?.stages.content.ref)));
        if (validContext && validTargets) {
          hydrateState({...state(), reference:seed.reference ?? null, targets:seed.target_ids || [], instruction:seed.instruction ?? state().instruction}); persist();
        } else notice.textContent = '带入的选页属于其它项目或版本，未替换当前输入。请返回原总览明确重选。';
      }
      loadRecipes(); controls();
    });
  }
  const sync = () => controls();
  app.root.addEventListener('business-state-changed', sync); app.root.addEventListener('draft-editor-replaced', hydrate);
  app.disposables.push(() => { disposed = true; serial++; sourceSerial++; candidateSerial++; recipeSerial++; release?.(); app.root.removeEventListener('business-state-changed', sync); app.root.removeEventListener('draft-editor-replaced', hydrate); });
  hydrate(); controls(); return node;
}
