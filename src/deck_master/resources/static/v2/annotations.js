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
    this.preview = el('div', {class: 'change-plan-preview stack'});
    this.intent = field('意见目的', el('input', {value: '修改建议', maxlength: 256}));
    this.scope = el('select', {'aria-label': '意见作用范围'}, ['artifact', 'page', 'chapter', 'project'].map((value, i) => el('option', {value}, ['当前图层', '整页', '章节', '项目'][i])));
    this.chapter = el('select', {'aria-label': '意见所属章节'}, (data.content_plan.chapters || []).map(c => el('option', {value: c.chapter_id}, c.title)));
    this.chapter.hidden = true;
    this.scope.querySelector('[value=chapter]').disabled = !data.content_plan.ref || !this.chapter.options.length;
    const image = ['original_image', 'svg', 'ppt'].includes(layer);
    // 设计 annotation-form：segmented 模式切换 + 行为提示（阅读不产生标注）。
    this.tools = el('div', {class: 'row wrap annotation-tools', 'aria-label': '画面操作模式'});
    this.modeHint = el('p', {class: 'form-hint'});
    this.modes = [['read', '阅读模式'], ['whole', '整页意见'], ...(image ? [['point', '点标注'], ['rect', '框选模式']] : [['text', '文本意见']])];
    for (const [mode, label] of this.modes) this.tools.append(button(label, () => this.setMode(mode), false, {'data-mode': mode}));
    this.fields = Object.fromEntries(['x', 'y', 'width', 'height'].map((key, i) => [key, field(['横向起点 %', '纵向起点 %', '区域宽度 %', '区域高度 %'][i], el('input', {type: 'number', min: 0, max: 100, step: .1, value: i < 2 ? 10 : 20}))]));
    this.geometry = el('details', {class: 'geometry-fields', hidden: true}, el('summary', {}, '用百分比定位区域'),
      el('div', {class: 'range-fields'}, Object.values(this.fields).map(f => f.node)), button('添加百分比区域', () => this.keyboardRegion()));
    this.saveButton = button('保存意见', () => this.save(), true);
    this.planButton = button('加入修改计划', () => this.plan());
    this.node.append(el('div', {class: 'panel-head'}, el('h2', {}, '标注与意见')),
      el('div', {class: 'panel-body stack'}, this.basis, this.tools, this.modeHint, el('label', {}, '意见作用范围 ', this.scope), this.chapter, this.intent.node,
        el('p', {class: 'muted'}, '正文使用个人草稿。保存意见不会启动制作；选入已保存意见后再预览修改计划。'),
        this.geometry, this.regionList, draftSlot, this.error, this.saveButton, el('h3', {}, '已保存意见'), this.savedList, this.planButton, this.preview));
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
    this.editor = editor; this.ref = ref; this.planRecord = null;
    if (!editor) { this.regions = []; this.setMode('read'); this.renderRegions(); return; }
    this.editorListener = () => { this.syncFromDraft(); this.update(); }; editor.input.addEventListener('draft-state-changed', this.editorListener);
    this.setMode('read');
    editor.ready.then(() => {
      if (this.disposed || this.editor !== editor) return;
      this.syncFromDraft(true); this.update();
    });
  }
  syncFromDraft(force = false) {
    const state = this.editor?.draft.content.annotation, key = JSON.stringify(state);
    if (!force && key === this.savedMetadata) return;
    this.savedMetadata = key; this.regions = structuredClone(state?.regions || []);
    this.scope.value = state?.scope || (this.ref ? 'artifact' : 'page'); this.intent.input.value = state?.intent || '修改建议';
    if (state?.chapter_id) this.chapter.value = state.chapter_id;
    this.renderRegions();
  }
  basisMatches() { return this.editor && this.editor.draft.base_revision === this.data.revision_id && canonical(this.editor.draft.base_ref) === canonical(this.ref); }
  changed() {
    if (!this.editor || this.editor.readonly || !this.basisMatches()) return;
    this.editor.draft.content.annotation = {regions: structuredClone(this.regions), scope: this.scope.value, chapter_id: this.chapter.value, intent: this.intent.input.value};
    this.editor.changed(); this.renderRegions(); this.update();
  }
  signature() { return canonical({text: this.editor?.input.value, regions: this.regions, scope: this.scope.value, chapter: this.chapter.value, intent: this.intent.input.value, selected: [...this.selected.keys()], ref: this.ref}); }
  update() {
    const blocked = !this.editor || this.editor.readonly || !this.basisMatches() || ['loading', 'unknown', 'conflict'].includes(this.editor.status) || this.app.business.entries.size || this.app.business.loadWarning;
    this.saveButton.disabled = Boolean(blocked || this.mode === 'read'); this.planButton.disabled = Boolean(blocked || !this.selected.size);
    this.chapter.hidden = this.scope.value !== 'chapter';
    this.basis.textContent = `${version(this.data.revision_id)} · ${layers[this.layer]} · 草稿区域 ${this.regions.length} 个` + (this.editor && !this.basisMatches() ? '。恢复稿属于其它基准，请先回原版本；未迁移范围。' : this.app.historical && this.editor && !this.editor.readonly ? '。原内容只读；新意见仍绑定这里的原版本。' : '');
    for (const control of this.tools.querySelectorAll('button')) {
      const active = control.dataset.mode === this.mode;
      control.setAttribute('aria-pressed', String(active));
      control.classList.toggle('active', active);
      control.disabled = Boolean(this.editor?.readonly || !this.basisMatches());
    }
    this.scope.disabled = this.intent.input.disabled = this.chapter.disabled = Boolean(this.editor?.readonly || !this.basisMatches());
    if (this.planRecord && this.planSignature !== this.signature()) { this.planRecord = null; this.preview.replaceChildren(el('p', {}, '要求已改变，请重新预览影响后提交。')); }
    this.draw();
  }
  setMode(mode) {
    this.mode = mode; this.drag = null;
    this.modeHint.textContent = mode === 'read' ? '阅读不会产生标注；无需框选，也可以针对整页写意见。'
      : mode === 'rect' ? '拖动框选画面；按 Esc 取消框选，返回阅读。'
      : mode === 'point' ? '在画面上点击放置标注点；按 Esc 返回阅读。'
      : mode === 'text' ? '在逐页稿原文中选择文本，再校验保存；按 Esc 返回阅读。'
      : '针对整页写意见，不绑定具体区域。';
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
      return n.base_revision === this.data.revision_id && n.layer === this.layer && canonical(n.artifact_ref) === canonical(this.ref) ? [{location: n.location, label: `已存 ${i + 1}`, saved: true}] : [];
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
  async loadSaved() {
    try {
      const response = await get('/api/annotations'); if (this.disposed) return;
      this.records = response.annotations;
      this.savedList.replaceChildren(...this.records.map((record, index) => {
        const note = record.annotation;
        const check = el('input', {type: 'checkbox', checked: this.selected.has(record.ref.sha256), 'aria-label': `选入意见 ${index + 1}`});
        check.addEventListener('change', () => { if (check.checked) this.selected.set(record.ref.sha256, record); else this.selected.delete(record.ref.sha256); this.update(); });
        return el('article', {class: 'saved-opinion'}, el('label', {}, check, `意见 ${index + 1} · ${note.intent}`), el('p', {}, note.body),
          button(`回到意见 ${index + 1} 的原版本`, () => this.app.go({surface: note.page_id ? 'page' : 'content', revision: note.base_revision, page_id: note.page_id || null, layer: note.layer || 'content'})));
      }));
      if (!this.records.length) this.savedList.append(el('p', {class: 'muted'}, '尚无已保存意见。'));
      this.update();
    } catch (error) { if (!this.disposed) this.error.textContent = readableError(error); }
  }
  async save() {
    delete this.error.dataset.success;
    try {
      await this.app.business.available(); if (!this.basisMatches()) throw new Error('请回到草稿绑定的原版本。');
      const body = this.editor.input.value, intent = this.intent.input.value;
      if (!body.trim() || !intent.trim()) throw new Error('请填写意见目的与下方个人草稿正文。');
      const scope = this.scope.value, fixed = this.data.revision_id;
      const locations = scope === 'artifact' && this.regions.length ? this.regions : [{kind: 'whole'}];
      if (this.mode !== 'whole' && !this.regions.length) throw new Error('请先添加区域，或选择整页意见。');
      const annotations = locations.map(location => ({schema_version: 'annotation.v1', project_id: this.app.info.project_id, base_revision: fixed, scope, intent, body, status: 'open', location,
        ...(scope === 'chapter' ? {chapter_id: this.chapter.value, content_plan_ref: this.data.content_plan.ref} : {}),
        ...(['page', 'artifact'].includes(scope) ? {page_id: this.data.page_id, page_ref: this.data.stages.content.ref} : {}),
        ...(scope === 'artifact' ? {layer: this.layer, artifact_ref: this.ref} : {})}));
      const input = {schema_version: 'annotation_batch.v1', project_id: this.app.info.project_id, annotations};
      const current = await get('/api/view/summary');
      await this.app.business.submit(this.editor, 'annotations.save', {input, base_revision: current.revision_id}, input, async () => {
        this.error.dataset.success = 'true';
        this.error.textContent = '意见已保存，尚未提交修改计划。原草稿与范围继续保留。'; await this.loadSaved();
      });
    } catch (error) { this.error.textContent = readableError(error); }
  }
  async plan() {
    delete this.error.dataset.success;
    try {
      await this.app.business.available();
      if (!this.selected.size) throw new Error('先选入至少一条已保存意见。');
      if (!this.basisMatches()) throw new Error('先回到草稿绑定的原版本，再预览影响。');
      const signature = this.signature(), current = await get('/api/view/summary');
      const input = {schema_version: 'change_intent.v1', project_id: this.app.info.project_id, base_revision: current.revision_id,
        targets: [{page_id: this.data.page_id, page_ref: this.data.stages.content.ref, layer: this.layer, artifact_ref: this.ref}],
        intent: this.intent.input.value, instruction: this.editor.input.value, annotation_refs: [...this.selected.values()].map(r => r.ref),
        max_calls: ['original_image', 'prepared_prompt', 'submitted_prompt'].includes(this.layer) ? 1 : 0};
      const response = await post('/api/changes/plan', {input}); if (this.disposed || signature !== this.signature()) return;
      this.planRecord = response; this.planSignature = signature;
      const names = {page: '逐页稿', blueprint: '原图', svg: '可编辑 SVG', svg_preview: 'SVG 预览', ppt_preview: 'PPT 逐页预览', deck_outputs: '整稿交付文件', quality_applicability: '质量检查依据'};
      this.preview.replaceChildren(el('h3', {}, '修改影响预览'), el('p', {}, `最多 ${response.plan.max_calls} 次图像调用 · ${version(response.plan.base_revision)} · 尚未执行`),
        ...response.plan.actions.map(a => el('section', {}, el('p', {}, `${this.data.page.customer_visible.title} · ${layers[a.layer]}`),
          el('p', {}, `将修改：${a.write_slots.map(s => names[s] || s).join(' / ')}；后续需更新：${a.downstream.map(s => names[s] || s).join(' / ')}`),
          el('details', {}, el('summary', {}, '核对固定基准'), el('code', {}, a.page_ref.sha256)))),
        button('确认计划并创建交接', () => this.commit(), true)); this.error.textContent = '';
    } catch (error) {
      this.error.textContent = readableError(error) + ' 原输入与意见保留，请阅读当前版本后重新计划。';
      if (error.status === 409) this.app.business.conflict({editor: this.editor, note: this.error.textContent}, error);
    }
  }
  async commit() {
    delete this.error.dataset.success;
    try {
      const record = this.planRecord;
      if (!record || this.planSignature !== this.signature()) throw new Error('要求已改变，请重新预览。');
      await this.app.business.submit(this.editor, 'changes.commit', {plan_id: record.plan_id, base_revision: record.plan.base_revision}, {plan_id: record.plan_id, plan: record.plan}, result => {
        this.app.go({surface: 'runs', revision: result.revision_id, task_id: result.task_ids[0]});
      });
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
