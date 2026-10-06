import {get, post, canonical, fileURL, readableError} from './api.js';
import {el, button, field, version} from './dom.js';
import {layers} from './routes.js';
import {imagePool} from './images.js';

// Coordinates are relative to the contained image, not the scroll viewport or
// canvas CSS box. DOM markup from user SVGs is never inserted into the page.
export function imageRect(canvas) {
  const box = canvas.getBoundingClientRect();
  const scale = Math.min(box.width / canvas.width, box.height / canvas.height);
  const width = canvas.width * scale, height = canvas.height * scale;
  return {left: box.left + (box.width - width) / 2, top: box.top + (box.height - height) / 2, width, height};
}
export class Annotations {
  constructor(app, data, layer, reading, draftSlot) {
    this.app = app; this.data = data; this.layer = layer; this.reading = reading;
    this.mode = 'read'; this.selected = new Map(); this.records = []; this.regions = [];
    this.node = el('section', {class: 'panel annotations-panel', 'aria-label': '版本绑定意见'});
    this.error = el('p', {class: 'field-error', role: 'status'});
    this.basis = el('p', {class: 'muted'});
    this.regionList = el('div', {class: 'annotation-regions stack'});
    this.savedList = el('div', {class: 'saved-annotations stack'});
    this.listState = 'loading';
    this.listNotice = el('p', {class: 'muted annotation-list-state', role: 'status'});
    this.listRetry = button('重新读取已保存意见', () => this.loadSaved(), false, {hidden: true});
    this.preview = el('div', {class: 'change-plan-preview stack'});
    this.intent = field('意见目的', el('input', {value: '修改建议', maxlength: 256}));
    this.scope = el('select', {'aria-label': '意见作用范围'}, ['artifact', 'page', 'chapter', 'project'].map((value, i) => el('option', {value}, ['当前图层', '整页', '章节', '项目'][i])));
    this.chapter = el('select', {'aria-label': '意见所属章节'}, (data.content_plan.chapters || []).map(c => el('option', {value: c.chapter_id}, c.title)));
    this.chapter.hidden = true;
    this.scope.querySelector('[value=chapter]').disabled = !data.content_plan.ref || !this.chapter.options.length;
    const image = ['original_image', 'svg', 'ppt'].includes(layer);
    // 设计 annotation-form：segmented 模式切换 + 行为提示（阅读不产生标注）。
    this.tools = el('div', {class: 'segmented annotation-tools', role: 'group', 'aria-label': '画面操作模式'});
    this.modeHint = el('p', {class: 'form-hint'});
    this.modes = [['read', '阅读模式'], ['whole', '整页意见'], ...(image ? [['point', '点标注'], ['rect', '框选模式']] : [['text', '文本意见']])];
    for (const [mode, label] of this.modes.filter(([mode]) => mode !== 'whole')) this.tools.append(button(label, () => this.chooseMode(mode), false, {'data-mode': mode}));
    this.fields = Object.fromEntries(['x', 'y', 'width', 'height'].map((key, i) => [key, field(['横向起点 %', '纵向起点 %', '区域宽度 %', '区域高度 %'][i], el('input', {type: 'number', min: 0, max: 100, step: .1, value: i < 2 ? 10 : 20}))]));
    this.geometry = el('details', {class: 'geometry-fields', hidden: true}, el('summary', {}, '用百分比定位区域'),
      el('div', {class: 'range-fields'}, Object.values(this.fields).map(f => f.node)), button('添加百分比区域', () => this.keyboardRegion()));
    this.saveButton = button('保存意见', () => this.save(), true);
    this.newButton = button('写新意见', () => this.newOpinion());
    this.copyNoteButton = button('从私人笔记复制', () => this.copyNote());
    this.planButton = button('预览修改影响', () => this.plan());
    this.requirementField = field('修改要求', el('textarea', {id: 'change-requirement', rows: 3, 'aria-label': '修改要求',
      placeholder: '这段要求会成为制作依据。默认填入所选意见原文，可继续编辑或补充说明。'}));
    this.requirementField.input.addEventListener('input', () => { this.requirementTouched = true; this.persistRequirement(); this.update(); });
    this.requirementRefs = el('div', {class: 'requirement-refs stack'});
    this.requirementTarget = el('p', {class: 'muted'});
    this.requirementNote = el('p', {class: 'muted field-help'});
    this.requirementSection = el('section', {class: 'change-requirement stack', hidden: true},
      el('h3', {}, '修改要求'), this.requirementTarget, this.requirementRefs, this.requirementField.node,
      this.planButton, this.requirementNote);
    this.scopeLabel = el('label', {}, '意见作用范围 ', this.scope);
    this.bodyField = field('意见正文', el('textarea', {id: 'opinion-body', rows: 3, 'aria-label': '意见正文',
      placeholder: '写下这条意见要改什么。输入会自动保留；保存后进入正式记录。'}));
    this.bodyField.input.addEventListener('input', () => this.changed());
    this.notice = el('p', {class: 'muted annotation-notice', hidden: true});
    const secondaryActions = el('details', {class: 'opinion-secondary'}, el('summary', {}, '草稿操作'),
      el('div', {class: 'stack'}, this.newButton, this.copyNoteButton));
    this.actions = el('div', {class: 'row wrap opinion-actions'}, this.saveButton, secondaryActions);
    const annotationSettings = el('details', {class: 'annotation-settings'}, el('summary', {}, '范围与标注工具'),
      el('div', {class: 'stack'}, el('div', {class: 'row wrap opinion-meta'}, this.scopeLabel, this.intent.node, this.chapter),
        el('p', {class: 'muted annotation-mobile-note'}, '点标注与框选需要桌面宽度；窄屏可用「整页意见」或选择原文描述位置。'),
        this.tools, this.geometry, this.regionList));
    this.startOpinion = button('整页意见', () => { this.chooseMode('whole'); this.bodyField.input.focus(); }, false,
      {class: 'opinion-start'});
    this.noteEntry = el('details', {class: 'note-entry'},
      el('summary', {}, '私人笔记（不进入意见与制作）'), draftSlot);
    this.node.append(el('div', {class: 'panel-head'}, el('h2', {}, '标注与意见')),
      el('div', {class: 'panel-body stack'}, this.basis, this.notice,
        this.startOpinion,
        this.bodyField.node,
        // The save row sits with the input it saves, before the optional region
        // tools, so writing and saving stay in one screen.
        this.actions, this.error, this.modeHint,
        annotationSettings, this.noteEntry,
        el('p', {class: 'muted field-help'}, '保存意见不启动制作；选入已保存意见后再预览修改计划。'),
        el('h3', {}, '已保存意见'), this.listNotice, this.listRetry, this.savedList,
        this.requirementSection, this.preview));
    this.scope.addEventListener('change', () => { if (this.scope.value !== 'artifact') this.setMode('whole'); this.changed(); });
    this.chapter.addEventListener('change', () => this.changed()); this.intent.input.addEventListener('input', () => this.changed());
    this.textListener = event => {
      const value = event.detail;
      if (this.mode !== 'text' || value.revision_id !== data.revision_id || value.page_id !== data.page_id || value.layer !== layer) return;
      if (canonical(value.selection.ref) !== canonical(this.ref)) { this.error.textContent = '选段属于另一份原文，请先切换到对应基准。'; return; }
      this.add({kind: 'text', range: value.selection});
    };
    reading.addEventListener('text-range-validated', this.textListener);
    this.escape = event => {
      if (event.key !== 'Escape' || this.mode === 'read') return;
      event.stopPropagation(); event.preventDefault();
      if (this.drag) this.drag = null; else this.regions.pop();
      this.setMode('read'); this.changed();
    };
    reading.parentElement?.addEventListener('keydown', this.escape);
    this.node.addEventListener('keydown', this.escape);
    this.businessListener = () => this.update();
    app.root.addEventListener('business-state-changed', this.businessListener);
    this.committedListener = () => this.loadSaved(); app.root.addEventListener('business-committed', this.committedListener);
    this.replacedListener = event => this.bind(event.detail, this.ref); app.root.addEventListener('draft-editor-replaced', this.replacedListener);
    this.observer = new MutationObserver(() => this.attachCanvas()); this.observer.observe(reading, {childList: true, subtree: true});
    this.loadSaved();
  }
  bind(editor, ref) {
    this.editor?.input.removeEventListener('draft-state-changed', this.editorListener);
    this.editor = editor; this.editorReady = false; this.ref = ref; this.selected.clear(); this.requirementField.input.value = ''; this.requirementTouched = false; this.requirementMissing = false; this.savedMetadata = null; this.planRecord = null; this.savedSubmission = null; this.newRefs = new Set();
    if (!editor) { this.regions = []; this.setMode('read'); this.renderRegions(); return; }
    // The draft owns "write a new opinion on the current basis". It belongs next
    // to the opinion actions, not inside the collapsed personal note.
    this.actions.querySelector('.rebase-action')?.remove();
    if (editor.rebaseButton) this.actions.append(editor.rebaseButton);
    this.editorListener = () => { this.syncFromDraft(); this.update(); }; editor.input.addEventListener('draft-state-changed', this.editorListener);
    this.setMode('read');
    editor.ready.then(() => {
      if (this.disposed || this.editor !== editor) return;
      this.editorReady = true; this.syncFromDraft(true); this.update();
    });
  }
  syncFromDraft(force = false) {
    const content = this.editor?.draft.content || {}, state = content.annotation, key = canonical({annotation: state, requirement: content.requirement});
    if (!force && key === this.savedMetadata) return;
    this.savedMetadata = key; this.regions = structuredClone(state?.regions || []);
    if (this.bodyField.input.value !== (state?.body || '')) this.bodyField.input.value = state?.body || '';
    this.scope.value = state?.scope || (this.ref ? 'artifact' : 'page'); this.intent.input.value = state?.intent || '修改建议';
    this.chapter.value = state?.chapter_id || this.chapter.options[0]?.value || '';
    this.restoreRequirement();
    this.renderRegions();
  }
  basisMatches() { return this.editor && this.editor.draft.base_revision === this.data.revision_id && canonical(this.editor.draft.base_ref) === canonical(this.ref); }
  changed() {
    if (!this.canEditDraft()) return;
    this.editor.draft.content.annotation = {body: this.bodyField.input.value, regions: structuredClone(this.regions), scope: this.scope.value, chapter_id: this.chapter.value, intent: this.intent.input.value};
    this.editor.changed(); this.renderRegions(); this.update();
  }
  // What this panel would send right now. Identical content, scope and basis never
  // create a second record; a different scope or region set is a new opinion.
  submissionKey() { return canonical({body: this.bodyField.input.value, regions: this.regions, scope: this.scope.value, chapter: this.chapter.value, intent: this.intent.input.value, ref: this.ref}); }
  // The requirement is its own editable text, filled from the selected opinions.
  // It replaces the old flow where the plan silently reused whatever happened to
  // sit in the drafting box.
  requirementBasis() {
    return {page_id: this.data.page_id, layer: this.layer, revision_id: this.data.revision_id,
      page_ref: this.data.stages.content.ref, artifact_ref: this.ref};
  }
  canEditDraft() {
    return Boolean(this.editorReady && this.editor && !this.editor.disposed && !this.editor.readonly &&
      this.editor.status !== 'loading' && this.basisMatches());
  }
  applicable(record) {
    const note = record.annotation;
    return note.page_id === this.data.page_id && canonical(note.page_ref) === canonical(this.data.stages.content.ref) &&
      (note.scope === 'page' || note.scope === 'artifact' && note.layer === this.layer && canonical(note.artifact_ref) === canonical(this.ref));
  }
  listReady() { return this.listState === 'ready' && this.loadedListRevision === this.listRevisionId(); }
  renderListState() {
    this.listNotice.hidden = this.listReady();
    this.listNotice.textContent = this.listState === 'error'
      ? `已保存意见尚未读取：${this.listError} 文字与原引用仍保留，可继续写要求；请重试后预览计划。`
      : '正在读取已保存意见；文字可继续编辑，读取完成后再预览修改计划。';
    this.listRetry.hidden = this.listState !== 'error';
  }
  restoreRequirement() {
    const state = this.editor?.draft.content.requirement;
    this.selected.clear(); this.requirementMissing = false;
    this.requirementField.input.value = typeof state?.text === 'string' ? state.text : '';
    this.requirementTouched = Boolean(state?.edited);
    const refs = Array.isArray(state?.annotation_refs) ? state.annotation_refs : [];
    const matching = state && canonical(state.basis) === canonical(this.requirementBasis());
    for (const ref of refs) {
      const record = this.listReady() && this.records.find(row => canonical(row.ref) === canonical(ref));
      if (matching && record && this.applicable(record)) this.selected.set(ref.sha256, record);
      else if (this.listReady()) this.requirementMissing = true;
    }
    if (state && !matching) this.requirementMissing = true;
    this.syncRequirement();
  }
  persistRequirement(selectionChanged = false) {
    if (!this.canEditDraft()) return;
    // Unresolved references belong to the saved draft. Editing text is not a
    // selection change, nor permission to move an old requirement to this basis.
    const state = this.editor.draft.content.requirement || {annotation_refs: [], basis: this.requirementBasis()};
    this.editor.draft.content.requirement = {...state, text: this.requirementField.input.value,
      edited: Boolean(this.requirementTouched), ...(selectionChanged ? {
        annotation_refs: [...this.selected.values()].map(row => row.ref), basis: this.requirementBasis()} : {})};
    this.editor.changed();
  }
  syncRequirement() {
    const rows = [...this.selected.values()];
    this.requirementSection.hidden = !rows.length && !this.requirementField.input.value && !this.requirementMissing;
    if (!rows.length) { this.planRecord = null; this.preview.replaceChildren(); }
    this.requirementRefs.replaceChildren(...rows.map(row => el('p', {class: 'requirement-ref'},
      `${this.scopeName(row.annotation)}｜${row.annotation.body}`)));
    this.requirementTarget.textContent = `目标：本页 ${layers[this.layer]} · 底稿 ${version(this.data.revision_id)}`;
    this.requirementNote.textContent = !this.listReady()
      ? '意见尚未读取完成；文字与原引用保留，读取成功后再核对选择并预览。'
      : this.requirementMissing
      ? '恢复的要求或意见属于其它依据，文字与原引用已保留；请重新选择适用意见并预览。'
      : !rows.length ? '修改要求已保留；请先选择适用意见，再预览修改影响。'
      : this.layer === 'content' ? '正文修改按协议的 content 类型记录；你的意见目的仍保留在意见记录里。'
      : '结果会先作为候选返回；比较并明确采用后才会替换当前作品。';
  }
  targetName() {
    const target = {project: '整稿（项目范围）', chapter: '所选章节', page: '本页整页', artifact: `本页 ${layers[this.layer]}`}[this.scope.value] || this.scope.value;
    return target + (this.regions.length ? ` · ${this.regions.length} 个区域` : '');
  }
  // The protocol marks a page-slot change as `content`; the user's own purpose
  // stays on the opinion records instead of being overwritten here.
  protocolIntent() { return this.layer === 'content' ? 'content' : (this.intent.input.value.trim() || '修改建议'); }
  signature() { return canonical({body: this.bodyField.input.value, requirement: this.requirementField.input.value, regions: this.regions, scope: this.scope.value, chapter: this.chapter.value, intent: this.intent.input.value, selected: [...this.selected.keys()], ref: this.ref}); }
  update() {
    const editable = this.canEditDraft();
    this.bodyField.input.readOnly = this.requirementField.input.readOnly = !editable;
    const blocked = !editable || !this.editor || this.editor.readonly || !this.basisMatches() || ['loading', 'unknown', 'conflict'].includes(this.editor.status) || this.app.business.entries.size || this.app.business.loadWarning;
    // An unchanged submission is not a new opinion: keep the save disabled and say
    // so, instead of appending a duplicate record for text the user already saved.
    const unchanged = this.savedSubmission !== null && this.savedSubmission === this.submissionKey();
    // An empty body keeps the button pressable: the click explains what is
    // missing instead of leaving a dead control with no visible reason.
    this.saveButton.disabled = Boolean(blocked || this.mode === 'read' || unchanged);
    this.planButton.disabled = Boolean(blocked || !this.listReady() || !this.selected.size || this.requirementMissing);
    this.newButton.disabled = !editable;
    this.startOpinion.disabled = !editable;
    this.copyNoteButton.disabled = Boolean(!editable || !this.editor.input.value.trim());
    this.chapter.hidden = this.scope.value !== 'chapter';
    if (unchanged) {
      this.error.dataset.success = 'true';
      this.error.textContent = '这条意见已保存；未发生变化时不会重复新增。改动正文、范围或区域后可保存为新意见，或点「写新意见」。';
    } else if (this.error.dataset.success) { delete this.error.dataset.success; this.error.textContent = ''; }
    // The effective target stays above the input: object, scope and the basis
    // version the note will be written against.
    const target = {project: '整稿意见（项目范围）', chapter: '章节意见', page: '本页整页意见', artifact: `当前图稿（${layers[this.layer]}）`}[this.scope.value] || this.scope.value;
    this.basis.textContent = `${target} · 底稿 ${version(this.data.revision_id)} · 草稿区域 ${this.regions.length} 个` + (this.editor && !this.basisMatches() ? '。恢复稿属于其它基准：先回原版本，或用「对当前版本写新意见」复制文字后保存；原有范围不迁移。' : this.app.historical && this.editor && !this.editor.readonly ? '。原内容只读；新意见仍绑定这里的原版本。' : '');
    const editorNotice = this.editor?.noticeText?.() || (!this.editor ? '先选择明确的原文基准，再填写意见。'
      : this.editor.readonly ? '此处只读，输入不会保存；可下载已有草稿，或回到可编辑的当前版本。'
      : !this.editorReady || this.editor.status === 'loading' ? '正在读取草稿；读取完成后即可编辑。' : '');
    this.notice.textContent = editorNotice; this.notice.hidden = !editorNotice;
    for (const control of this.tools.querySelectorAll('button')) {
      const active = control.dataset.mode === this.mode;
      control.setAttribute('aria-pressed', String(active));
      control.classList.toggle('active', active);
      control.disabled = !editable;
    }
    this.scope.disabled = this.intent.input.disabled = this.chapter.disabled = !editable;
    if (this.planRecord && this.planSignature !== this.signature()) { this.planRecord = null; this.preview.replaceChildren(el('p', {}, '要求已改变，请重新预览影响后提交。')); }
    this.savedList.querySelectorAll('.saved-opinion').forEach(article => {
      const check = article.querySelector('input[type=checkbox]');
      const row = this.records.find(row => row.ref.sha256 === article.dataset.ref);
      check.disabled = !editable || !this.listReady() || !row || !this.applicable(row);
      check.checked = Boolean(row && this.selected.has(row.ref.sha256));
    });
    this.draw();
  }
  // The user pressing a mode button also states the target: 「整页意见」means the
  // page, point/rect/text bind to the current artwork. Programmatic mode changes
  // (selecting 章节/项目, restoring a draft) never move the scope.
  chooseMode(mode) {
    if (mode === 'whole') this.scope.value = 'page';
    else if (['point', 'rect', 'text'].includes(mode)) this.scope.value = 'artifact';
    this.setMode(mode);
  }
  setMode(mode) {
    this.mode = mode; this.drag = null;
    this.modeHint.textContent = mode === 'read' ? '先选「整页意见」，或打开标注工具，再保存意见。'
      : mode === 'rect' ? '拖动框选；Esc 取消并返回阅读。'
      : mode === 'point' ? '点击放置标注点；Esc 移除并返回阅读。'
      : mode === 'text' ? '在原文中选择文本；Esc 移除并返回阅读。'
      : '针对整页写意见，不绑定区域。';
    // Region tools stay bound to the artwork; the 「整页意见」impulse lives in
    // chooseMode so an explicit 章节/项目 scope is never overridden here.
    if (['point', 'rect', 'text'].includes(mode)) this.scope.value = 'artifact';
    this.geometry.hidden = !['point', 'rect'].includes(mode);
    for (const key of ['width', 'height']) this.fields[key].node.hidden = mode === 'point';
    const zoom = this.reading.closest('.page-workbench')?.querySelector('[aria-label="阅读缩放"]'); if (zoom) zoom.disabled = mode !== 'read';
    this.reading.classList.toggle('annotating', ['point', 'rect'].includes(mode)); this.update();
  }
  async attachCanvas() {
    const canvas = this.reading.querySelector('canvas.page-image'); if (!canvas || canvas === this.canvas || this.disposed) return;
    this.canvas = canvas; this.dimensions = {width: canvas.width, height: canvas.height};
    if (this.layer === 'svg') {
      try {
        const raw = await imagePool.network.run(async () => {
          const response = await fetch(fileURL(this.data.stages.svg.file)); if (!response.ok) throw new Error('SVG 原画布不可读。');
          return response.text();
        });
        if (/<!\s*(DOCTYPE|ENTITY)/i.test(raw)) throw new Error('SVG 声明不适用于区域定位。');
        const root = new DOMParser().parseFromString(raw, 'image/svg+xml').documentElement;
        const box = (root.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
        if (box.length !== 4 || !box.every(Number.isFinite) || Math.min(box[2], box[3]) <= 0) throw new Error('SVG 缺少有效原画布尺寸。');
        this.dimensions = {width: box[2], height: box[3]};
      } catch (error) { this.dimensions = null; this.error.textContent = readableError(error); }
    }
    if (this.disposed || this.canvas !== canvas) return;
    this.overlay?.remove(); this.overlay = el('div', {class: 'annotation-overlay', 'aria-label': '原图标注范围'});
    canvas.parentElement.append(this.overlay);
    this.overlay.addEventListener('pointerdown', event => {
      if (!['point', 'rect'].includes(this.mode) || event.button !== 0 || !this.basisMatches() || !this.dimensions) return;
      const point = this.point(event); if (!point) return; event.preventDefault();
      if (this.mode === 'point') this.add({kind: 'point', canvas: {...this.dimensions}, ...point});
      else { this.drag = point; this.overlay.setPointerCapture(event.pointerId); }
    });
    this.overlay.addEventListener('pointerup', event => {
      if (!this.drag) return;
      const start = this.drag; this.drag = null; const end = this.point(event); if (!end) return;
      const x = Math.min(start.x, end.x), y = Math.min(start.y, end.y);
      if (Math.abs(end.x - start.x) < .001 || Math.abs(end.y - start.y) < .001) return;
      this.add({kind: 'rect', canvas: {...this.dimensions}, x, y, width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y)});
    });
    this.resize?.disconnect(); this.resize = new ResizeObserver(() => this.draw()); this.resize.observe(canvas); this.draw();
  }
  point(event) {
    const rect = imageRect(this.canvas), x = (event.clientX - rect.left) / rect.width, y = (event.clientY - rect.top) / rect.height;
    return x < 0 || y < 0 || x > 1 || y > 1 ? null : {x, y};
  }
  draw() {
    if (!this.canvas || !this.overlay) return;
    const rect = imageRect(this.canvas), parent = this.canvas.parentElement.getBoundingClientRect();
    Object.assign(this.overlay.style, {left: `${rect.left - parent.left}px`, top: `${rect.top - parent.top}px`, width: `${rect.width}px`, height: `${rect.height}px`, pointerEvents: ['point', 'rect'].includes(this.mode) ? 'auto' : 'none'});
    const visible = [...this.regions.map((location, i) => ({location, label: String(i + 1), saved: false})), ...this.records.flatMap((r, i) => {
      const n = r.annotation;
      // F10/N11：画布叠层与意见列表用同一产物身份规则（artifact_ref 相等即同
      // 一产物，几何有效）；不再要求快照 revision 相等，否则列表里"适用"的
      // 意见在画布上消失。
      return n.layer === this.layer && canonical(n.artifact_ref) === canonical(this.ref) ? [{location: n.location, label: `已存 ${i + 1}`, saved: true}] : [];
    })];
    this.overlay.replaceChildren(...visible.filter(r => ['point', 'rect'].includes(r.location.kind)).map(r => {
      const n = r.location, mark = el('span', {class: `annotation-mark ${n.kind}${r.saved ? ' saved' : ''}`}, r.label);
      Object.assign(mark.style, {left: `${n.x * 100}%`, top: `${n.y * 100}%`});
      if (n.kind === 'rect') Object.assign(mark.style, {width: `${n.width * 100}%`, height: `${n.height * 100}%`});
      return mark;
    }));
  }
  keyboardRegion() {
    try {
      if (!this.dimensions || !this.canvas) throw new Error('先等待此版本图像读取完成。');
      const value = Object.fromEntries(Object.entries(this.fields).map(([key, f]) => [key, Number(f.input.value) / 100]));
      if (!Object.values(value).every(Number.isFinite) || value.x < 0 || value.x > 1 || value.y < 0 || value.y > 1 || this.mode === 'rect' && (value.width <= 0 || value.height <= 0 || value.x + value.width > 1 || value.y + value.height > 1)) throw new Error('百分比范围需位于原画布内，宽高须大于零。');
      this.add({kind: this.mode, canvas: {...this.dimensions}, x: value.x, y: value.y, ...(this.mode === 'rect' ? {width: value.width, height: value.height} : {})});
    } catch (error) { this.error.textContent = error.message; }
  }
  add(location) { if (!this.basisMatches() || this.editor.readonly) return; this.regions.push(location); this.error.textContent = ''; this.changed(); }
  renderRegions() {
    this.regionList.replaceChildren(...this.regions.map((location, index) => el('div', {class: 'annotation-region'},
      el('p', {}, `${index + 1} · ${location.kind === 'text' ? location.range.excerpt : location.kind === 'rect' ? '框选区域' : '点标注'}`),
      button(`删除区域 ${index + 1}`, () => { this.regions.splice(index, 1); this.changed(); }, false, {disabled: !this.basisMatches() || this.editor?.readonly})))); this.draw();
  }
  scopeName(note) {
    if (note.scope === 'project') return '整稿意见';
    if (note.scope === 'chapter') return '章节意见';
    if (note.scope === 'page') return '本页整页意见';
    return `当前图稿（${layers[note.layer] || note.layer}）`;
  }
  // Opinions are grouped by what they actually talk about, so a note about
  // another page or the whole deck is never read as this artwork's requirement.
  savedGroups() {
    const page = this.data.page_id, layer = this.layer;
    const notes = this.records.map(record => ({record, note: record.annotation}));
    const groups = [
      {key: 'page', title: '本页整页意见', open: true, selectable: true,
       rows: notes.filter(row => row.note.scope === 'page' && row.note.page_id === page)},
      {key: 'artifact', title: `当前图稿意见 · ${layers[layer]}`, open: true, selectable: true,
       rows: notes.filter(row => row.note.scope === 'artifact' && row.note.page_id === page && row.note.layer === layer)},
      {key: 'other_layers', title: '本页其它图层', open: false, selectable: true,
       rows: notes.filter(row => row.note.scope === 'artifact' && row.note.page_id === page && row.note.layer !== layer)},
      {key: 'other_pages', title: '其它页面的局部意见', open: false, selectable: false,
       reason: '此意见属于其它页面，不能选入本页的修改计划。',
       rows: notes.filter(row => ['page', 'artifact'].includes(row.note.scope) && row.note.page_id && row.note.page_id !== page)},
      {key: 'whole_deck', title: '整稿意见与章节意见', open: false, selectable: false,
       reason: '整稿意见是范围记录，不表示已认可整稿，也不是本页的修改要求；如要修改本页，请另写本页意见。',
       rows: notes.filter(row => ['project', 'chapter'].includes(row.note.scope))},
    ];
    for (const group of groups) if (!group.selectable) for (const row of group.rows) this.selected.delete(row.record.ref.sha256);
    return groups;
  }
  savedCard(record, group, index) {
    const note = record.annotation, isNew = this.newRefs.has(record.ref.sha256);
    const check = el('input', {type: 'checkbox', checked: this.selected.has(record.ref.sha256), 'aria-label': `选入意见 ${index}`, disabled: !group.selectable || !this.applicable(record) || !this.canEditDraft() || !this.listReady()});
    check.addEventListener('change', () => {
      if (!this.canEditDraft() || !this.listReady()) { check.checked = this.selected.has(record.ref.sha256); return; }
      if (check.checked) this.selected.set(record.ref.sha256, record); else this.selected.delete(record.ref.sha256);
      this.requirementMissing = false;
      if (!this.requirementTouched && this.selected.size) this.requirementField.input.value = [...this.selected.values()].map(row => row.annotation.body).join('\n\n');
      this.persistRequirement(true); this.syncRequirement(); this.update();
    });
    const article = el('article', {class: `saved-opinion${isNew ? ' is-new' : ''}`, 'data-ref': record.ref.sha256},
      el('label', {}, check, `意见 ${index} · ${note.intent}`),
      isNew && el('span', {class: 'status'}, '本次新增'),
      el('p', {class: 'saved-meta muted'}, `${this.scopeName(note)} · 底稿 ${version(note.base_revision)} · ${note.status === 'resolved' ? '已解决' : '待处理'}`),
      el('p', {}, note.body),
      group.reason && el('p', {class: 'muted field-help'}, group.reason),
      button(`回到意见 ${index} 的原版本`, () => this.app.go({surface: note.page_id ? 'page' : 'content', revision: note.base_revision, page_id: note.page_id || null, layer: note.layer || 'content'})));
    if (isNew) article.scrollIntoView({block: 'nearest'});
    return article;
  }
  // Which snapshot the saved list is read from. Historical reads stay fixed to
  // their own version; current reads follow the project, including the revision a
  // save just returned (the page it was written on may already be older).
  listRevisionId() {
    if (this.app.historical) return this.data.revision_id;
    return this.listRevision || this.app.latest?.revision_id || this.data.revision_id;
  }
  async loadSaved() {
    const serial = this.listSerial = (this.listSerial || 0) + 1, revision = this.listRevisionId();
    const active = () => !this.disposed && serial === this.listSerial && revision === this.listRevisionId();
    this.listState = 'loading'; this.listError = ''; this.planRecord = null; this.preview.replaceChildren();
    this.restoreRequirement(); this.renderListState(); this.update();
    try {
      const response = await get('/api/annotations?' + new URLSearchParams({revision})); if (!active()) return;
      this.records = response.annotations; this.loadedListRevision = revision; this.listState = 'ready';
      this.restoreRequirement();
      const nodes = []; let index = 0;
      for (const group of this.savedGroups()) {
        if (!group.rows.length && !group.open) continue;
        const cards = group.rows.map(row => this.savedCard(row.record, group, ++index));
        if (group.open) nodes.push(el('section', {class: 'saved-group'}, el('h4', {}, `${group.title}（${group.rows.length}）`),
          ...(cards.length ? cards : [el('p', {class: 'muted'}, '此范围暂无意见。')])));
        else nodes.push(el('details', {class: 'saved-group'}, el('summary', {}, `${group.title}（${group.rows.length}）`), ...cards));
      }
      if (!this.records.length) nodes.push(el('p', {class: 'muted'}, '尚无已保存意见。'));
      this.savedList.replaceChildren(...nodes);
      this.syncRequirement(); this.renderListState();
      this.update();
    } catch (error) {
      if (!active()) return;
      this.listState = 'error'; this.listError = readableError(error);
      this.restoreRequirement(); this.renderListState(); this.update();
    }
  }
  async save() {
    delete this.error.dataset.success;
    try {
      await this.app.business.available(); if (!this.basisMatches()) throw new Error('草稿绑定的是其它基准：请回到原版本，或用「对当前版本写新意见」复制文字后再保存。');
      const body = this.bodyField.input.value, intent = this.intent.input.value;
      if (!body.trim()) throw new Error('请填写意见正文。');
      if (!intent.trim()) throw new Error('请填写意见目的。');
      const key = this.submissionKey();
      if (this.savedSubmission === key) throw new Error('这条意见已保存；未发生变化时不会重复新增。');
      const scope = this.scope.value, fixed = this.data.revision_id;
      const locations = scope === 'artifact' && this.regions.length ? this.regions : [{kind: 'whole'}];
      if (this.mode !== 'whole' && !this.regions.length) throw new Error('请先添加区域，或选择整页意见。');
      const annotations = locations.map(location => ({schema_version: 'annotation.v1', project_id: this.app.info.project_id, base_revision: fixed, scope, intent, body, status: 'open', location,
        ...(scope === 'chapter' ? {chapter_id: this.chapter.value, content_plan_ref: this.data.content_plan.ref} : {}),
        ...(['page', 'artifact'].includes(scope) ? {page_id: this.data.page_id, page_ref: this.data.stages.content.ref} : {}),
        ...(scope === 'artifact' ? {layer: this.layer, artifact_ref: this.ref} : {})}));
      const input = {schema_version: 'annotation_batch.v1', project_id: this.app.info.project_id, annotations};
      const current = await get('/api/view/summary');
      await this.app.business.submit(this.editor, 'annotations.save', {input, base_revision: current.revision_id}, input, async result => {
        this.savedSubmission = key;
        this.listRevision = result?.revision_id || this.listRevision;
        this.newRefs = new Set((result?.annotations || []).map(item => item.ref?.sha256).filter(Boolean));
        this.error.dataset.success = 'true';
        await this.loadSaved();
      });
    } catch (error) { this.error.textContent = readableError(error); }
  }
  // Writing the next opinion starts from an empty body and region set; scope and
  // intent stay, because they usually carry over to the next note.
  newOpinion() {
    if (!this.editor || this.editor.readonly) return;
    this.regions = []; this.newRefs = new Set(); this.savedSubmission = null;
    this.bodyField.input.value = ''; this.error.textContent = ''; delete this.error.dataset.success;
    this.changed(); this.bodyField.input.focus();
  }
  copyNote() {
    if (!this.editor || this.editor.readonly) return;
    const note = this.editor.input.value;
    if (!note.trim()) { this.error.textContent = '私人笔记为空，没有可复制的内容。'; return; }
    this.bodyField.input.value = note;
    this.error.textContent = '已从私人笔记复制到意见正文；保存前仍可修改，私人笔记本身不变。';
    this.changed(); this.bodyField.input.focus();
  }
  async plan() {
    delete this.error.dataset.success;
    try {
      await this.app.business.available();
      if (!this.listReady()) throw new Error('先重新读取已保存意见，再预览修改计划。');
      if (this.requirementMissing) throw new Error('恢复的要求依据不适用，请重新选择意见。');
      if (!this.selected.size) throw new Error('先在上方选入至少一条已保存意见。');
      if (!this.basisMatches()) throw new Error('先回到草稿绑定的原版本，再预览影响。');
      const instruction = this.requirementField.input.value.trim();
      if (!instruction) throw new Error('请先写明修改要求，再预览影响。');
      if (['svg', 'ppt'].includes(this.layer) && this.data.stages.blueprint.existence !== 'recorded')
        throw new Error('这一页还没有可用的原图；SVG 修复与重建需要先有当前原图。请先生成或更新原图，再计划修改。');
      const signature = this.signature(), listSerial = this.listSerial, current = await get('/api/view/summary');
      if (this.disposed || !this.listReady() || listSerial !== this.listSerial || signature !== this.signature()) return;
      const input = {schema_version: 'change_intent.v1', project_id: this.app.info.project_id, base_revision: current.revision_id,
        targets: [{page_id: this.data.page_id, page_ref: this.data.stages.content.ref, layer: this.layer, artifact_ref: this.ref}],
        intent: this.protocolIntent(), instruction, annotation_refs: [...this.selected.values()].map(r => r.ref),
        mode: 'trial',
        max_calls: ['original_image', 'prepared_prompt', 'submitted_prompt'].includes(this.layer) ? 1 : 0};
      const response = await post('/api/changes/plan', {input}); if (this.disposed || !this.listReady() || listSerial !== this.listSerial || signature !== this.signature()) return;
      this.planRecord = response; this.planSignature = signature; this.planContext = {instruction, annotation_refs: input.annotation_refs, targets: input.targets};
      const names = {page: '逐页稿', blueprint: '原图', svg: '可编辑 SVG', svg_preview: 'SVG 预览', ppt_preview: 'PPT 逐页预览', deck_outputs: '整稿交付文件', quality_applicability: '质量检查依据'};
      this.preview.replaceChildren(el('h3', {}, '修改影响预览'),
        el('p', {}, `最多 ${response.plan.max_calls} 次图像调用 · ${version(response.plan.base_revision)} · 尚未执行`),
        el('p', {}, '结果先作为候选返回；比较并明确采用后才会替换当前作品，未采用的候选不改动作品。'),
        ...response.plan.actions.map(a => el('section', {}, el('p', {}, `${this.data.page.customer_visible.title} · ${layers[a.layer]}`),
          el('p', {}, `将修改：${a.write_slots.map(s => names[s] || s).join(' / ')}；后续需更新：${a.downstream.map(s => names[s] || s).join(' / ')}`),
          el('p', {class: 'muted'}, '未列出的图层与已有记录保持不变。'),
          el('details', {}, el('summary', {}, '核对固定基准'), el('code', {}, a.page_ref.sha256)))),
        button('确认计划并创建交接', () => this.commit(), true)); this.error.textContent = '';
    } catch (error) {
      this.error.textContent = readableError(error) + ' 原输入与意见保留，请阅读当前版本后重新计划。';
      if (error.status === 409) {
        try { await this.app.business.conflict({editor: this.editor, note: this.error.textContent}, error); }
        catch (recoveryError) { this.error.textContent += ' ' + readableError(recoveryError); }
      }
    }
  }
  async commit() {
    delete this.error.dataset.success;
    try {
      const record = this.planRecord;
      if (!this.listReady() || this.requirementMissing) throw new Error('先核对已保存意见并重新预览。');
      if (!record || this.planSignature !== this.signature()) throw new Error('要求已改变，请重新预览。');
      await this.app.business.submit(this.editor, 'changes.commit', {plan_id: record.plan_id, base_revision: record.plan.base_revision}, {plan_id: record.plan_id, plan: record.plan}, result => {
        this.app.go({surface: 'runs', revision: result.revision_id, task_id: result.task_ids[0]});
      }, this.planContext);
    } catch (error) { this.error.textContent = readableError(error); }
  }
  dispose() {
    this.disposed = true; this.observer.disconnect(); this.resize?.disconnect(); this.overlay?.remove();
    this.editor?.input.removeEventListener('draft-state-changed', this.editorListener);
    this.reading.removeEventListener('text-range-validated', this.textListener);
    this.reading.parentElement?.removeEventListener('keydown', this.escape);
    this.app.root.removeEventListener('business-state-changed', this.businessListener);
    this.app.root.removeEventListener('business-committed', this.committedListener);
    this.app.root.removeEventListener('draft-editor-replaced', this.replacedListener);
  }
}
