import {get, post, readableError, canonical, digest} from './api.js';
import {el, button, modal, toast, downloadJSON, version} from './dom.js';
import {layers} from './routes.js';

// sessionStorage is copied by same-origin window.open. It is a recovery hint,
// never ownership of a writable buffer. Every document gets a fresh identity.
const windowBufferId = crypto.randomUUID();
let previousWindowBufferId;
try {
  previousWindowBufferId = sessionStorage.getItem('deck-master:v3:window');
  sessionStorage.setItem('deck-master:v3:window', windowBufferId);
} catch { /* Local copies and downloadable recovery remain available. */ }

// A personal recovery copy. No edit, task, call, or adoption endpoint is used.
export class DraftEditor {
  constructor(info, target, baseRevision, baseRef, {readonly = false, exactRevision = false} = {}) {
    this.info = info; this.target = target; this.baseRevision = baseRevision; this.baseRef = baseRef;
    this.readonly = readonly; this.exactRevision = exactRevision; this.etag = null; this.status = 'loading'; this.pendingSave = null;
    this.bufferKey = `deck-master:v3:draft:${info.project_identity}:${canonical(target)}:${baseRef?.sha256 || 'none'}:${baseRevision}`;
    this.activeKey = `${this.bufferKey}:window:${windowBufferId}`;
    this.draft = this.fresh(); this.storageError = ''; this.restoreNotice = ''; this.disposed = false;
  }
  fresh() {
    return {schema_version: 'ui_draft.v1', project_id: this.info.project_id, project_identity: this.info.project_identity,
      draft_id: 'draft-' + crypto.randomUUID(), target: this.target, base_revision: this.baseRevision,
      base_ref: this.baseRef, content: {text: ''}, pending: null};
  }
  mount() {
    this.input = el('textarea', {id: 'personal-draft', rows: 7, 'aria-label': '个人草稿', readOnly: this.readonly,
      placeholder: '记录这一页、这一层需要继续考虑的事。保存草稿不会提交制作任务。',
      oninput: () => this.changed(), onblur: () => this.save()});
    this.stateNode = el('p', {role: 'status', class: 'draft-state'});
    this.basisNode = el('p', {class: 'muted draft-basis'});
    this.storageNode = el('p', {class: 'field-error', role: 'alert'});
    this.saveButton = button('保存个人草稿', () => this.save(), false, {disabled: this.readonly});
    this.verifyButton = button('核实草稿保存', () => this.verify());
    this.conflictButton = button('比较两份草稿', () => this.conflict());
    this.rebaseButton = button('对当前版本写新意见', () => this.writeNewOnCurrent(), false, {class: 'rebase-action'});
    const file = el('input', {type: 'file', accept: 'application/json,.json', 'aria-label': '导入草稿恢复文件',
      disabled: this.readonly, onchange: () => this.importFile(file)});
    this.importInput = file;
    this.restoreNode = el('div', {class: 'draft-restore'});
    this.localRestoreNode = el('div', {class: 'draft-restore'});
    this.noticeNode = el('p', {class: 'muted draft-notice', hidden: true});
    const node = el('section', {class: 'panel personal-draft'},
      el('div', {class: 'panel-head'}, el('h2', {}, '个人草稿'), el('span', {class: 'status'}, '不提交制作任务')),
      el('div', {class: 'panel-body stack'}, el('label', {for: this.input.id}, '留给自己的内容与意见'), this.input,
        this.basisNode, this.noticeNode, this.stateNode, this.storageNode,
        el('div', {class: 'row wrap'}, this.saveButton, this.rebaseButton, this.verifyButton, this.conflictButton,
          button('下载草稿恢复文件', () => this.download())),
        el('label', {class: 'recovery-import'}, '导入草稿恢复文件', file),
        el('p', {class: 'muted field-help'}, '恢复文件可能包含内部提示词。已保存到项目的内容可跨端口恢复；未同步内容请下载保管。'),
        this.restoreNode, this.localRestoreNode));
    this.updateStatus(); this.ready = this.load();
    return node;
  }
  async load() {
    let buffered;
    try {
      const raw = localStorage.getItem(this.activeKey) || (previousWindowBufferId &&
        localStorage.getItem(`${this.bufferKey}:window:${previousWindowBufferId}`));
      buffered = raw ? JSON.parse(raw) : null;
      if (buffered && (buffered.draft?.project_identity !== this.info.project_identity ||
          canonical(buffered.draft?.target) !== canonical(this.target))) buffered = null;
    } catch { this.storageError = '浏览器缓冲无法读取。项目中已保存的草稿仍可读取。'; }
    if (buffered) {
      this.draft = buffered.draft; this.etag = buffered.etag || null;
      this.pendingSave = buffered.pendingSave || null;
      this.status = this.pendingSave ? 'unknown' : buffered.status === 'saved' ? 'saved' : 'dirty';
      this.input.value = this.draft.content.text || '';
      this.persist(); // Claim a new writable copy; the inherited copy remains intact.
    }
    try {
      const result = await get('/api/drafts');
      if (this.disposed) return;
      const records = result.records.filter(record => canonical(record.draft.target) === canonical(this.target));
      const exact = records.filter(record => record.draft.base_ref?.sha256 === this.baseRef?.sha256 && (!this.exactRevision || record.draft.base_revision === this.baseRevision));
      if (!buffered && exact.length === 1) this.adoptRecord(exact[0]);
      else if (!buffered) this.status = 'empty';
      // Restoring an older revision's text as if it were current would bind this
      // editor to a stale basis and block saving against the current one. Older
      // text stays in the restore list; it is copied forward explicitly.
      if (!buffered && exact.length > 1) this.restoreNotice = `当前版本有 ${exact.length} 份个人草稿，未自动打开；请从下方选择要恢复的一份。`;
      else if (!buffered && !exact.length && records.length) this.restoreNotice = `当前版本没有个人草稿；${records.length} 份旧版本草稿可从下方恢复，再用「对当前版本写新意见」复制文字。`;
      if (buffered && this.status === 'saved') {
        const record = records.find(record => record.draft.draft_id === this.draft.draft_id);
        if (!record || canonical(record.draft) !== canonical(this.draft)) this.status = 'dirty';
      }
      this.showRestore(records, result.errors.length);
    } catch (error) {
      this.note = readableError(error);
      if (!buffered) this.status = 'empty';
    }
    if (this.disposed) return;
    this.showLocalCopies(); this.updateStatus();
  }
  // A draft is labelled by whichever text it actually carries: the personal note,
  // or the opinion body when the note is empty.
  static summary(draft) {
    return String(draft?.content?.text || draft?.content?.annotation?.body || draft?.content?.requirement?.text || '空白草稿').slice(0, 45);
  }
  showLocalCopies() {
    this.localRestoreNode.replaceChildren();
    try {
      const copies = [];
      for (let index = 0; index < localStorage.length; index++) {
        const key = localStorage.key(index);
        if (!key.startsWith(this.bufferKey + ':copy:')) continue;
        const value = JSON.parse(localStorage.getItem(key));
        if (key !== `${this.bufferKey}:copy:${windowBufferId}:${this.draft.draft_id}` && value.draft?.project_identity === this.info.project_identity && canonical(value.draft.target) === canonical(this.target)) copies.push(value);
      }
      if (!copies.length) return;
      const select = el('select', {'aria-label': '恢复本机保留的草稿副本'}, el('option', {value: ''}, '选择本机保留的草稿副本'));
      copies.forEach((copy, index) => select.append(el('option', {value: String(index)}, DraftEditor.summary(copy.draft))));
      select.addEventListener('change', () => {
        if (!select.value) return;
        const copy = copies[Number(select.value)];
        // Retire this instance before restoring, so a late ACK cannot reach the new copy.
        if (!this.archiveLocal()) { this.updateStatus(); return; }
        this.persist(); this.disposed = true; clearTimeout(this.timer);
        this.input.dispatchEvent(new CustomEvent('draft-restore-local', {bubbles: true, detail: copy}));
      });
      this.localRestoreNode.append(select);
    } catch { this.storageError = '部分本机副本无法读取，请保留当前内容并下载恢复文件。'; }
  }
  showRestore(records, unreadable) {
    this.restoreNode.replaceChildren();
    if (unreadable) this.restoreNode.append(el('p', {class: 'field-error'}, `${unreadable} 份草稿暂不可读，其余内容已保留。`));
    if (!records.length) return;
    const select = el('select', {'aria-label': '恢复项目中的个人草稿'}, el('option', {value: ''}, '选择已保存在项目中的草稿'));
    for (const record of records) select.append(el('option', {value: record.draft.draft_id},
      `${version(record.draft.base_revision)} · ${DraftEditor.summary(record.draft)}`));
    select.addEventListener('change', () => {
      const record = records.find(item => item.draft.draft_id === select.value);
      if (!record) return;
      const restore = () => {
        if (!this.archiveLocal()) { this.updateStatus(); return; }
        this.persist(); this.disposed = true; clearTimeout(this.timer);
        this.input.dispatchEvent(new CustomEvent('draft-restore-local', {bubbles: true, detail: {draft: record.draft, etag: record.etag, status: 'saved', pendingSave: null}}));
      };
      if (['dirty', 'unknown', 'conflict', 'saving'].includes(this.status)) {
        modal('保留当前输入再恢复', el('p', {}, '当前本机稿仍保留在浏览器缓冲。建议先下载恢复文件，再打开项目中的另一份草稿。'),
          [button('下载当前稿', () => this.download()), button('打开所选草稿', () => { restore(); document.querySelector('#modal').close(); })]);
      } else restore();
    });
    this.restoreNode.append(select);
  }
  adoptRecord(record) {
    this.draft = structuredClone(record.draft); this.etag = record.etag;
    this.status = 'saved'; this.pendingSave = null; this.sequence = record.updated_sequence;
    this.restoreNotice = '';
    this.input.value = this.draft.content.text || '';
  }
  // True when the draft's basis is not the basis this editor was mounted for.
  staleBasis() {
    return Boolean(this.draft) && (this.draft.base_revision !== this.baseRevision ||
      this.draft.base_ref?.sha256 !== this.baseRef?.sha256);
  }
  // Start a new draft on this editor's basis, keeping the older record and its
  // local copy. Both texts move forward: the personal note and the opinion body.
  // Regions, scope and intent describe the old artifact's selection state, so the
  // old targeting is dropped and never migrated silently.
  writeNewOnCurrent() {
    if (this.readonly || this.disposed || !this.staleBasis()) return;
    if (!this.archiveLocal()) { this.updateStatus(); return; }
    const text = this.input.value;
    const annotation = this.draft.content?.annotation;
    const draft = this.fresh();
    const requirement = this.draft.content?.requirement;
    draft.content = {text, ...(annotation ? {annotation: {body: annotation.body, scope: 'page', regions: [], intent: '修改建议'}} : {}),
      ...(requirement ? {requirement: {text: requirement.text || '', edited: true, annotation_refs: [], basis: null}} : {})};
    this.draft = draft; this.etag = null; this.pendingSave = null; this.sequence = undefined;
    this.status = text || annotation?.body ? 'dirty' : 'empty'; this.note = ''; this.restoreNotice = '';
    this.persist(); this.updateStatus();
    this.input.dispatchEvent(new CustomEvent('draft-state-changed', {bubbles: true}));
  }
  // The text a pending operation was about. An editor that carries an opinion
  // body must show that body in recovery panes, not the personal note that now
  // has its own box.
  pendingText(payload) {
    if (payload) return payload.display_context?.instruction ?? JSON.stringify(payload.request || {});
    const requirement = this.draft?.content?.requirement?.text;
    if (requirement) return requirement;
    const opinion = this.draft?.content?.annotation?.body;
    return opinion && opinion.trim() ? opinion : (this.input?.value || '');
  }
  // Visible reason plus next action: either recoverable drafts exist for this
  // target, or the text on screen belongs to an older basis. Shared by the note
  // panel and the opinion panel so both surfaces explain the same state.
  noticeText() {
    if (this.restoreNotice) return this.restoreNotice;
    if (this.staleBasis()) return `当前草稿绑定的是原基准 ${version(this.draft.base_revision)}，不能直接用于当前版本。可用「对当前版本写新意见」复制文字，原有范围不迁移。`;
    return '';
  }
  changed() {
    this.draft.content = {...this.draft.content, text: this.input.value};
    if (!['unknown', 'conflict', 'saving'].includes(this.status)) this.status = 'dirty';
    this.persist(); this.updateStatus();
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.save(), 600);
  }
  archiveLocal() {
    try {
      localStorage.setItem(`${this.bufferKey}:copy:backup-${crypto.randomUUID()}`, JSON.stringify({draft: this.draft, etag: this.etag, status: this.status, pendingSave: this.pendingSave}));
      return true;
    } catch { this.storageError = '本机副本未保存，请先下载恢复文件。'; return false; }
  }
  persist() {
    if (this.disposed) return;
    try {
      const value = {draft: this.draft, etag: this.etag, status: this.status, pendingSave: this.pendingSave};
      // Separate per-draft copies preserve an unsent draft when selecting another.
      localStorage.setItem(`${this.bufferKey}:copy:${windowBufferId}:${this.draft.draft_id}`, JSON.stringify(value));
      localStorage.setItem(this.activeKey, JSON.stringify(value));
      this.storageError = '';
    } catch { this.storageError = '浏览器缓冲未保存。输入仍在此页，请立即下载恢复文件或复制内容。'; }
  }
  updateStatus() {
    if (!this.stateNode || this.disposed) return;
    const text = {loading: '正在读取个人草稿…', empty: '尚无个人草稿', dirty: '仅在本机缓冲，尚未保存到项目',
      saving: '正在保存到项目…', saved: '已保存到项目，可跨端口恢复', unknown: '保存结果待核实，后写内容仅在本机保留',
      conflict: '保存冲突，你的本机稿与项目中的稿件都已保留', error: '未保存到项目，输入仍保留'};
    this.stateNode.textContent = this.readonly ? '历史或示例只读，可下载已有个人草稿。' : text[this.status];
    // A visible reason and a next action whenever the text on screen belongs to
    // an older basis: the collapsed details already carry the full explanation.
    const notice = this.noticeText();
    this.noticeNode.textContent = notice;
    this.noticeNode.hidden = !notice;
    this.basisNode.textContent = `基准 ${version(this.draft.base_revision)} · ${this.info.page_label || '整个项目'} · ${layers[this.target.layer] || '项目笔记'}` +
      (this.staleBasis() ? '。草稿仍绑定原基准，未自动改到新版；可用「对当前版本写新意见」复制文字，原有范围不迁移。' : '');
    this.storageNode.textContent = this.storageError || this.note || '';
    this.rebaseButton.hidden = this.readonly || !this.staleBasis();
    this.saveButton.disabled = this.readonly || ['loading', 'empty', 'saved', 'saving', 'unknown', 'conflict'].includes(this.status);
    this.input.readOnly = this.readonly || this.status === 'loading';
    this.importInput.disabled = this.readonly || this.status === 'loading';
    this.verifyButton.hidden = this.status !== 'unknown';
    this.conflictButton.hidden = this.status !== 'conflict';
    this.input.dispatchEvent(new CustomEvent('draft-state-changed', {bubbles: true}));
  }
  async save() {
    clearTimeout(this.timer);
    if (this.readonly || this.disposed || !['dirty', 'error'].includes(this.status)) return;
    this.pendingSave = {draft: structuredClone(this.draft), expected_etag: this.etag};
    await this.submitPending();
  }
  async submitPending() {
    if (this.pendingWrite) return this.pendingWrite;
    this.pendingWrite = this.writePending();
    try { return await this.pendingWrite; } finally { this.pendingWrite = null; }
  }
  async writePending() {
    const pending = this.pendingSave;
    if (!pending || this.status === 'saving') return;
    this.status = 'saving'; this.note = ''; this.persist(); this.updateStatus();
    try {
      const result = await post('/api/drafts/save', pending);
      this.confirm(result.record);
    } catch (error) {
      if (error.status === 409) { this.status = 'conflict'; this.pendingSave = null; }
      else if (!error.status || error.status >= 500 || ['invalid_response', 'local_io_failed'].includes(error.code)) this.status = 'unknown';
      else { this.status = 'error'; this.pendingSave = null; }
      this.note = readableError(error); this.persist(); this.updateStatus();
    }
  }
  confirm(record) {
    this.etag = record.etag; this.sequence = record.updated_sequence; this.pendingSave = null;
    this.status = canonical(this.draft) === canonical(record.draft) ? 'saved' : 'dirty';
    this.note = ''; this.persist(); this.updateStatus();
    if (this.status === 'dirty' && !this.disposed) this.timer = setTimeout(() => this.save(), 600);
  }
  async verify() {
    if (!this.pendingSave) return;
    const pending = structuredClone(this.pendingSave);
    this.note = '正在核实已发送的内容…'; this.updateStatus();
    try {
      const result = await get('/api/drafts/' + encodeURIComponent(pending.draft.draft_id));
      if (result.record && canonical(result.record.draft) === canonical(pending.draft)) this.confirm(result.record);
      else if (!result.record || result.record.etag === pending.expected_etag) {
        this.note = '项目中尚未发现本次保存。后写草稿保持独立，可以重试已发送的原内容。';
        modal('原草稿尚未确认保存', el('p', {}, this.note), [button('重试已发送的内容', () => {
          document.querySelector('#modal').close(); this.submitPending();
        })]); this.updateStatus();
      } else { this.status = 'conflict'; this.pendingSave = null; this.persist(); this.updateStatus(); }
    } catch (error) { this.note = readableError(error); this.updateStatus(); }
  }
  async conflict() {
    try {
      const result = await get('/api/drafts/' + encodeURIComponent(this.draft.draft_id));
      const local = el('textarea', {readOnly: true, 'aria-label': '你的本机草稿', value: this.draft.content.text || ''});
      const saved = el('textarea', {readOnly: true, 'aria-label': '项目中已保存的草稿', value: result.record?.draft.content.text || ''});
      modal('保留两份个人草稿', el('div', {class: 'conflict-panes'},
        el('section', {}, el('h3', {}, '你的本机草稿'), local), el('section', {}, el('h3', {}, '项目中已保存的草稿'), saved)),
        [button('下载本机稿', () => this.download()), button('另存为个人草稿', () => {
          this.persist(); this.draft.draft_id = 'draft-' + crypto.randomUUID(); this.etag = null;
          this.pendingSave = null; this.status = 'dirty'; this.persist(); this.updateStatus();
          document.querySelector('#modal').close(); this.save();
        })]);
    } catch (error) { this.note = readableError(error); this.updateStatus(); }
  }
  async download() {
    const value = structuredClone(this.draft);
    // W03 content is text. This file never includes HTTP/session metadata.
    const recovery = {schema_version: 'ui_draft_recovery.v1', draft: value, digest: await digest(value)};
    downloadJSON(recovery, 'deck-master-personal-draft.json');
    toast('恢复文件已下载。它可能包含内部提示词，请妥善保管。');
  }
  async importFile(input) {
    const file = input.files[0];
    if (!file || this.readonly) return;
    try {
      if (file.size > 2_000_000) throw new Error('恢复文件超过 2 MB，当前输入仍保留。');
      const recovery = JSON.parse(await file.text());
      const result = await post('/api/drafts/import', {recovery});
      if (canonical(result.record.draft.target) === canonical(this.target) && !['dirty', 'unknown', 'saving', 'conflict'].includes(this.status)) {
        if (this.disposed) return;
      this.adoptRecord(result.record); this.persist(); this.updateStatus();
      }
      toast(result.imported_from ? '已另存为独立草稿，项目中的原稿保持。' : '已导入项目，可在对应页面恢复。');
      const records = (await get('/api/drafts')).records.filter(record => canonical(record.draft.target) === canonical(this.target));
      this.showRestore(records, 0);
    } catch (error) { this.note = readableError(error); this.updateStatus(); }
    finally { input.value = ''; }
  }
  dispose() {
    if (this.status !== 'loading') if (!this.archiveLocal()) { this.updateStatus(); return; }
        this.persist(); this.disposed = true; clearTimeout(this.timer);
    // An in-flight request may still ACK its own copy; it cannot change a new editor.
  }
}
