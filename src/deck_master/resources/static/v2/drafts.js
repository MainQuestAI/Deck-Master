import {get, post, readableError, canonical, digest} from './api.js';
import {el, button, modal, toast, downloadJSON, version, actionGroup} from './dom.js';
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
const clearedKey = copy => `deck-master:v3:cleared:${copy.draft.project_identity}:${copy.draft.draft_id}:${copy.etag}`;
const wasCleared = copy => copy?.status === 'saved' && !copy.pendingSave && copy.etag &&
  localStorage.getItem(clearedKey(copy)) === '1';

// Match ui_journal._portable locally: recovery must remain usable while offline.
const recoveryContentError = '恢复文件包含当前导入入口不接受的内容，尚不能确认保管并离开';
const recoveryForbiddenKeys = new Set(['token', 'authorization', 'x-deck-token', 'cookie', 'command', 'cwd', 'absolute_path', 'file_path']);
export function validateRecoveryContent(value) {
  const pending = [value];
  while (pending.length) {
    const item = pending.pop();
    if (Array.isArray(item)) {
      for (const child of item) pending.push(child);
    } else if (item && typeof item === 'object') {
      for (const [key, child] of Object.entries(item)) {
        if (recoveryForbiddenKeys.has(key.toLowerCase())) throw new Error(recoveryContentError);
        pending.push(child);
      }
    } else if (typeof item === 'string') {
      // Python's [:4] counts Unicode characters, not JavaScript UTF-16 units.
      let prefix = '', count = 0;
      for (const character of item) { prefix += character; if (++count === 4) break; }
      if (item.startsWith('/') || item.startsWith('file://') || item.startsWith('\\\\') || prefix.includes(':\\'))
        throw new Error(recoveryContentError);
    }
  }
}

export function retireClearedDrafts(identity, receipt, editors = []) {
  for (const item of receipt.cleared) if (item.kind === 'draft') {
    localStorage.setItem(clearedKey({draft: {project_identity: identity, draft_id: item.id}, etag: item.etag}), '1');
  }
  for (const editor of editors) editor.retireCleared();
}

export class DraftEditor {
  constructor(info, target, baseRevision, baseRef, {readonly = false, exactRevision = false, contextKey = null} = {}) {
    this.info = info; this.target = target; this.baseRevision = baseRevision; this.baseRef = baseRef;
    this.contextKey = contextKey;
    this.readonly = readonly; this.exactRevision = exactRevision; this.etag = null; this.status = 'loading'; this.pendingSave = null;
    this.bufferKey = `deck-master:v3:draft:${info.project_identity}:${canonical(target)}:${baseRef?.sha256 || 'none'}:${baseRevision}`;
    if(contextKey)this.bufferKey += `:context:${contextKey}`;
    this.activeKey = `${this.bufferKey}:window:${windowBufferId}`;
    this.draft = this.fresh(); this.storageError = ''; this.restoreNotice = ''; this.disposed = false;
  }
  fresh() {
    return {schema_version: 'ui_draft.v1', project_id: this.info.project_id, project_identity: this.info.project_identity,
      draft_id: 'draft-' + crypto.randomUUID(), target: this.target, base_revision: this.baseRevision,
      base_ref: this.baseRef, content: {text: '', ...(this.contextKey?{context_key:this.contextKey}:{})}, pending: null};
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
    this.recoveryConfirmButton = button('我已保管恢复文件，允许离开', () => {
      const snapshot = this.recoverySnapshot();
      if (this.downloadedRecovery !== snapshot) return;
      this.confirmedRecovery = snapshot; this.updateStatus();
      toast('已确认保管这份恢复内容，现在可以重试离开。继续编辑需要重新下载并确认。');
    }, false, {hidden: true});
    const node = el('section', {'data-container':'section', class: 'panel personal-draft'},
      el('div', {class: 'panel-head'}, el('h2', {}, '个人草稿'), el('span', {class: 'status'}, '不提交制作任务')),
      el('div', {class: 'panel-body stack'}, el('label', {for: this.input.id}, '留给自己的内容与意见'), this.input,
        this.basisNode, this.noticeNode, this.stateNode, this.storageNode,
        actionGroup(this.saveButton, this.rebaseButton, this.verifyButton, this.conflictButton,
          button('下载草稿恢复文件', () => this.download())), this.recoveryConfirmButton,
        el('label', {class: 'recovery-import'}, '导入草稿恢复文件', file),
        el('p', {class: 'muted field-help'}, '恢复文件可能包含内部提示词。已保存到项目的内容可跨端口恢复；未同步内容请下载保管。'),
        this.restoreNode, this.localRestoreNode));
    this.node = node; this.updateStatus(); this.ready = this.load();
    return node;
  }
  listURL() {
    return this.info.draft_reads === 'ui_draft_query.v1' ? '/api/drafts?' + new URLSearchParams({
      view: 'editor', target: JSON.stringify(this.target), context_key: this.contextKey || ''}) : '/api/drafts';
  }
  async fullRecord(entry) {
    if (entry.draft) return entry;
    const {record} = await get('/api/drafts/' + encodeURIComponent(entry.draft_id));
    if (!record || record.etag !== entry.etag || !this.matchesContext(record.draft))
      throw new Error('所选草稿已变化，当前输入仍保留；请重新读取工作面后再选择。');
    return record;
  }
  async load() {
    const epoch = this.loadEpoch || 0;
    let buffered;
    try {
      const raw = localStorage.getItem(this.activeKey) || (previousWindowBufferId &&
        localStorage.getItem(`${this.bufferKey}:window:${previousWindowBufferId}`));
      buffered = raw ? JSON.parse(raw) : null;
      if (buffered && !this.matchesContext(buffered.draft)) buffered = null;
      if (wasCleared(buffered)) {
        buffered = null;
        this.restoreNotice = '已清理的已保存草稿不会自动打开；本机恢复副本仍可明确选择。';
      }
    } catch { this.storageError = '浏览器缓冲无法读取。项目中已保存的草稿仍可读取。'; }
    if (buffered) {
      this.draft = buffered.draft; this.etag = buffered.etag || null;
      this.pendingSave = buffered.pendingSave || null;
      this.status = this.pendingSave ? 'unknown' : buffered.status === 'saved' ? 'saved' : 'dirty';
      this.input.value = this.draft.content.text || '';
      this.persist(); // Claim a new writable copy; the inherited copy remains intact.
    }
    try {
      const result = await get(this.listURL());
      if (this.disposed || epoch !== (this.loadEpoch || 0)) return;
      const records = result.entries || result.records.filter(record => this.matchesContext(record.draft));
      let editedDuringRead = !buffered && this.status !== 'loading';
      if (editedDuringRead) buffered = true;
      const exact = records.filter(record => (record.draft || record).base_ref?.sha256 === this.baseRef?.sha256 &&
        (!this.exactRevision || (record.draft || record).base_revision === this.baseRevision));
      if (!buffered && exact.length === 1) {
        const record = await this.fullRecord(exact[0]);
        if (this.disposed || epoch !== (this.loadEpoch || 0)) return;
        if (this.status === 'loading') this.adoptRecord(record);
        else { editedDuringRead = true; buffered = true; }
      }
      else if (!buffered) this.status = 'empty';
      // Restoring an older revision's text as if it were current would bind this
      // editor to a stale basis and block saving against the current one. Older
      // text stays in the restore list; it is copied forward explicitly.
      if (!buffered && exact.length > 1) this.restoreNotice = `当前版本有 ${exact.length} 份个人草稿，未自动打开；请从下方选择要恢复的一份。`;
      else if (!buffered && !exact.length && records.length) this.restoreNotice = `当前版本没有个人草稿；${records.length} 份旧版本草稿可从下方恢复，再用「对当前版本写新意见」复制文字。`;
      if (editedDuringRead) this.restoreNotice = '读取期间已编辑，当前输入已保留；项目中的原草稿仍可明确选择恢复。';
      if (buffered && !editedDuringRead && this.status === 'saved') {
        const record = records.find(record => (record.draft || record).draft_id === this.draft.draft_id);
        if (!record || (record.draft ? canonical(record.draft) !== canonical(this.draft) : record.digest !== await digest(this.draft))) this.status = 'dirty';
      }
      this.showRestore(records, result.errors.length);
    } catch (error) {
      if (this.disposed || epoch !== (this.loadEpoch || 0)) return;
      this.note = readableError(error);
      if (!buffered && this.status === 'loading') this.status = 'empty';
    }
    if (this.disposed || epoch !== (this.loadEpoch || 0)) return;
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
        if (key !== `${this.bufferKey}:copy:${windowBufferId}:${this.draft.draft_id}` && this.matchesContext(value.draft)) copies.push(value);
      }
      if (!copies.length) return;
      const select = el('select', {'aria-label': '恢复本机保留的草稿副本'}, el('option', {value: ''}, '选择本机保留的草稿副本'));
      copies.forEach((copy, index) => select.append(el('option', {value: String(index)}, DraftEditor.summary(copy.draft))));
      select.addEventListener('change', () => {
        if (!select.value) return;
        const copy = copies[Number(select.value)];
        this.restoreCopy(copy);
      });
      this.localRestoreNode.append(select);
    } catch { this.storageError = '部分本机副本无法读取，请保留当前内容并下载恢复文件。'; }
  }
  showRestore(records, unreadable) {
    this.restoreNode.replaceChildren();
    if (unreadable) this.restoreNode.append(el('p', {class: 'field-error'}, `${unreadable} 份草稿暂不可读，其余内容已保留。`));
    if (!records.length) return;
    const select = el('select', {'aria-label': '恢复项目中的个人草稿'}, el('option', {value: ''}, '选择已保存在项目中的草稿'));
    for (const record of records) select.append(el('option', {value: (record.draft || record).draft_id},
      `${version((record.draft || record).base_revision)} · ${record.draft ? DraftEditor.summary(record.draft) : record.summary}`));
    select.addEventListener('change', async () => {
      const selected = select.value, token = this.restoreSelection = (this.restoreSelection || 0) + 1;
      const entry = records.find(item => (item.draft || item).draft_id === selected);
      if (!entry) return;
      let copy, open, dialog;
      const needsConfirmation = () => ['dirty', 'unknown', 'conflict', 'saving'].includes(this.status);
      const offer = () => {
        open = button('打开所选草稿', () => {
          if (copy && token === this.restoreSelection && select.value === selected && this.restoreCopy(copy)) dialog?.close();
        }, false, {disabled: !copy});
        const cancel = button('取消恢复', () => {
          this.restoreSelection++; select.value = ''; this.restoreConfirm?.remove(); dialog?.close();
        });
        const body = el('div', {class:'draft-restore-confirm stack', role:'group', 'aria-label':'保留当前输入再恢复'},
          el('p', {}, '当前稿和待核实保存请求会保留在本机副本中，再打开所选草稿。'),
          button('下载当前稿', () => this.download()), cancel, open);
        if (!this.node.closest('#modal')) dialog = modal('保留当前输入再恢复', body, [], {protectDraft:true});
        else { this.restoreConfirm?.remove(); this.restoreConfirm = body; this.restoreNode.append(body); }
      };
      // Render the protection before the lazy body read. Cancel remains usable
      // during a slow read, and its generation rejects a late body response.
      if (needsConfirmation()) offer();
      let record;
      try { record = await this.fullRecord(entry); }
      catch (error) { if (!this.disposed && token === this.restoreSelection) { this.note = readableError(error); this.updateStatus(); } return; }
      if (this.disposed || token !== this.restoreSelection || select.value !== selected) return;
      copy = {draft: record.draft, etag: record.etag, status: 'saved', pendingSave: null};
      if (open) open.disabled = false;
      else if (needsConfirmation()) offer();
      else this.restoreCopy(copy);
    });
    this.restoreNode.append(select);
  }
  matchesContext(draft) {
    return draft?.project_identity === this.info.project_identity &&
      canonical(draft?.target) === canonical(this.target) &&
      (draft?.content?.context_key || null) === this.contextKey;
  }
  // Standalone context editors retain their controls and rehydrate explicitly.
  restoreInPlace(copy) {
    if (this.disposed || !this.matchesContext(copy?.draft)) return false;
    if (this.pendingWrite) { this.note='请等待当前草稿保存回执，再恢复所选副本。'; this.updateStatus(); return false; }
    if (!this.archiveLocal()) { this.updateStatus(); return false; }
    clearTimeout(this.timer);
    this.draft=structuredClone(copy.draft); this.etag=copy.etag||null;
    this.pendingSave=copy.pendingSave?structuredClone(copy.pendingSave):null;
    this.status=this.pendingSave?'unknown':copy.status||'dirty';
    this.input.value=this.draft.content.text||''; this.note=''; this.restoreNotice='';
    this.restoreConfirm?.remove(); this.persist(); this.showLocalCopies(); this.updateStatus();
    return true;
  }
  restoreCopy(copy) {
    if (this.disposed || !this.matchesContext(copy?.draft)) return;
    if (!this.onRestore) { this.note = '当前编辑器无法恢复，请保留原稿并重新打开工作面。'; this.updateStatus(); return; }
    try {
      if (wasCleared(copy)) copy = {...copy, draft: {...structuredClone(copy.draft), draft_id: crypto.randomUUID()}, etag: null, status: 'dirty'};
    } catch { /* Explicit recovery retains the selected input if markers are unreadable. */ }
    return this.onRestore(copy);
  }
  notifyState() {
    // Local consumers (annotations) observe the editor itself; Project owns the
    // root notification even when this node lives outside its DOM tree.
    this.input.dispatchEvent(new CustomEvent('draft-state-changed', {bubbles:!this.onStateChanged}));
    this.onStateChanged?.();
  }
  adoptRecord(record) {
    try {
      if (wasCleared({draft: record.draft, etag: record.etag, status: 'saved'})) {
        this.status = 'empty';
        this.restoreNotice = '这份已保存草稿已清理，本机副本仍可明确恢复。';
        return;
      }
    } catch { /* The project record still provides acknowledged content. */ }
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
    const previous = this.draft;
    const draft = this.fresh();
    const requirement = this.draft.content?.requirement;
    draft.content = {...draft.content, text, ...(annotation ? {annotation: {body: annotation.body, scope: 'page', regions: [], intent: '修改建议'}} : {}),
      ...(requirement ? {requirement: {text: requirement.text || '', edited: true, annotation_refs: [], basis: null}} : {})};
    this.onRebase?.(draft, previous);
    this.draft = draft; this.etag = null; this.pendingSave = null; this.sequence = undefined;
    this.status = [text, annotation?.body, requirement?.text].some(value => typeof value === 'string' && value.trim()) ? 'dirty' : 'empty'; this.note = ''; this.restoreNotice = '';
    this.persist(); this.updateStatus();
    this.notifyState(); this.onRebased?.();
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
    if (this.disposed || this.retireCleared()) return true;
    let recoverable = false, copySaved = false;
    try {
      const value = {draft: this.draft, etag: this.etag, status: this.status, pendingSave: this.pendingSave};
      const serialized = JSON.stringify(value);
      // Separate per-draft copies preserve an unsent draft when selecting another.
      localStorage.setItem(`${this.bufferKey}:copy:${windowBufferId}:${this.draft.draft_id}`, serialized);
      copySaved = true;
      localStorage.setItem(this.activeKey, serialized);
      recoverable = true;
      this.storageError = '';
    } catch { this.storageError = copySaved ? '当前稿已有本机副本，但自动恢复位置未更新。请保留此页并保存到项目或下载恢复文件。' : '浏览器缓冲未保存。输入仍在此页，请立即下载恢复文件或复制内容。'; }
    return recoverable;
  }
  updateStatus() {
    if (!this.stateNode || this.disposed) return;
    const recoveryState = this.recoverySnapshot();
    if (this.lastRecoveryState !== recoveryState) {
      this.downloadedRecovery = null; this.confirmedRecovery = null;
      this.lastRecoveryState = recoveryState;
    }
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
    this.storageNode.textContent = [this.storageError, this.note].filter(Boolean).join(' ');
    this.rebaseButton.hidden = this.readonly || !this.staleBasis();
    this.saveButton.disabled = this.readonly || ['loading', 'empty', 'saved', 'saving', 'unknown', 'conflict'].includes(this.status);
    this.input.readOnly = this.readonly || this.status === 'loading';
    this.importInput.disabled = this.readonly || this.status === 'loading';
    this.verifyButton.hidden = this.status !== 'unknown';
    this.conflictButton.hidden = this.status !== 'conflict';
    if (this.recoveryConfirmButton) this.recoveryConfirmButton.hidden = this.downloadedRecovery !== recoveryState || this.confirmedRecovery === recoveryState;
    this.notifyState();
  }
  async save() {
    do {
      // Another waiter may start the next save before this continuation runs.
      // Drain that write too; callers must not mistake saving for completion.
      while (this.pendingWrite) await this.pendingWrite;
      clearTimeout(this.timer);
      if (this.readonly || this.disposed || !['dirty', 'error'].includes(this.status)) return;
      this.pendingSave = {draft: structuredClone(this.draft), expected_etag: this.etag};
      await this.submitPending();
      // Acknowledged older text can leave newer input dirty. Save it before
      // returning, but never automatically retry unknown/conflict/error.
    } while (this.status === 'dirty');
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
        const dialog = modal('原草稿尚未确认保存', el('p', {}, this.note), [button('重试已发送的内容', () => {
          dialog.close(); this.submitPending();
        })], {protectDraft: true}); this.updateStatus();
      } else { this.status = 'conflict'; this.pendingSave = null; this.persist(); this.updateStatus(); }
    } catch (error) { this.note = readableError(error); this.updateStatus(); }
  }
  async conflict() {
    try {
      const local = structuredClone(this.draft);
      const result = await get('/api/drafts/' + encodeURIComponent(local.draft_id));
      if (this.disposed || this.draft.draft_id !== local.draft_id) return;
      const saved = result.record ? structuredClone(result.record.draft) : null;
      const pane = (prefix, title, draft) => {
        const content = draft?.content || {}, texts = [content.text, content.annotation?.body, content.requirement?.text];
        return el('section', {class: 'draft-conflict-pane stack'}, el('h3', {}, title),
          el('p', {class: 'muted'}, draft ? `${draft.target.page_id || '整个项目'} · ${layers[draft.target.layer] || '个人草稿'} · 基准 ${version(draft.base_revision)}` : '项目目前没有已保存的草稿'),
          ...['私人笔记', '意见正文', '修改要求'].map((purpose, index) => el('label', {class: 'stack'}, purpose,
            el('textarea', {rows: 3, readOnly: true, placeholder: '空白', 'aria-label': prefix + purpose,
              value: typeof texts[index] === 'string' ? texts[index] : ''}))),
          draft && el('details', {}, el('summary', {}, '固定依据与引用'), el('pre', {class: 'evidence-json'}, JSON.stringify({
            target: draft.target, base_revision: draft.base_revision, base_ref: draft.base_ref,
            requirement_basis: content.requirement?.basis ?? null, annotation_refs: content.requirement?.annotation_refs || []}, null, 2))));
      };
      const dialog = modal('保留两份个人草稿', el('div', {class: 'conflict-panes draft-conflict-panes'},
        pane('本机', '你的本机草稿', local), pane('项目', '项目中已保存的草稿', saved)),
        [button('下载本机稿', () => this.download(local)), button('另存为个人草稿', () => {
          if (!this.archiveLocal()) { this.updateStatus(); return; }
          this.persist(); this.draft = structuredClone(local); this.draft.draft_id = 'draft-' + crypto.randomUUID(); this.etag = null;
          this.input.value = this.draft.content.text || '';
          this.pendingSave = null; this.sequence = undefined; this.status = 'dirty'; this.persist(); this.updateStatus();
          dialog.close(); this.save();
        })], {protectDraft: true});
    } catch (error) { this.note = readableError(error); this.updateStatus(); }
  }
  recoverySnapshot() {
    return canonical({draft: this.draft, pendingSave: this.pendingSave});
  }
  recoveryLimits() {
    return this.info.recovery_limits || {draft_bytes:1_998_976, file_bytes:2_000_000, request_bytes:2_000_000};
  }
  async download(draft = this.draft) {
    try {
      const snapshot = this.recoverySnapshot();
      const value = structuredClone(draft);
      const pendingSave = this.pendingSave ? structuredClone(this.pendingSave) : null;
      try {
        validateRecoveryContent(value);
        validateRecoveryContent(pendingSave);
      } catch {
        throw new Error(recoveryContentError);
      }
      const limits = this.recoveryLimits();
      if ([value, ...(pendingSave ? [pendingSave.draft] : [])].some(item =>
        new TextEncoder().encode(canonical(item)).length > limits.draft_bytes))
        throw new Error('单份草稿超过容量限制，完整内容仍保留；请先处理容量，尚不能确认保管并离开。');
      // Preserve every content purpose and its basis, never HTTP/session metadata.
      const recovery = {schema_version: 'ui_draft_recovery.v1', draft: value, digest: await digest(value),
        ...(pendingSave ? {pending_save:pendingSave, pending_save_digest:await digest(pendingSave)} : {})};
      // A legacy core gives file and request the same limit. The import envelope
      // is larger than the compact file, so both must fit before custody opens.
      if (new Blob([JSON.stringify(recovery) + '\n']).size > limits.file_bytes)
        throw new Error('完整恢复文件超过容量限制，当前稿与待核实请求均保留；尚不能确认保管并离开。');
      if (new TextEncoder().encode(JSON.stringify({recovery})).length > limits.request_bytes)
        throw new Error('恢复导入请求超过容量限制，当前稿与待核实请求均保留；尚不能确认保管并离开。');
      downloadJSON(recovery, 'deck-master-personal-draft.json', {compact:true, maxBytes:limits.file_bytes});
      if (canonical(draft) === canonical(this.draft) && snapshot === this.recoverySnapshot()) this.downloadedRecovery = snapshot;
      this.updateStatus();
      toast('已发起恢复文件下载。请核对并保管文件，再明确确认允许离开。');
    } catch (error) {
      this.downloadedRecovery = null; this.confirmedRecovery = null;
      this.note = readableError(error); this.updateStatus();
    }
  }
  async importFile(input) {
    const file = input.files[0];
    if (!file || this.readonly) return;
    try {
      const limits = this.recoveryLimits();
      if (file.size > limits.file_bytes) throw new Error('恢复文件超过容量限制，当前输入仍保留。');
      const recovery = JSON.parse(await file.text());
      const result = await post('/api/drafts/import', {recovery}, {recoveryLimit:limits.request_bytes});
      if (this.matchesContext(result.record.draft) && !['dirty', 'unknown', 'saving', 'conflict'].includes(this.status)) {
        if (this.disposed) return;
        this.restoreCopy({draft:result.record.draft,etag:result.record.etag,status:'saved',pendingSave:null});
      }
      toast(result.preserved_pending_save ? '已导入当前稿。原保存结果仍需核实；原请求保留在恢复文件中，未自动重发。' : result.imported_from ? '已另存为独立草稿，项目中的原稿保持。' : '已导入项目，可在对应页面恢复。');
      const listed = await get(this.listURL());
      if (!this.disposed) this.showRestore(listed.entries || listed.records.filter(record => this.matchesContext(record.draft)), listed.errors.length);
    } catch (error) { this.note = readableError(error); this.updateStatus(); }
    finally { input.value = ''; }
  }
  retireCleared() {
    if (this.disposed) return false;
    try {
      if (!wasCleared(this)) return false;
    } catch { return false; }
    clearTimeout(this.timer);
    this.loadEpoch = (this.loadEpoch || 0) + 1;
    this.draft = this.fresh(); this.etag = null; this.pendingSave = null; this.status = 'empty';
    if (this.input) this.input.value = '';
    this.restoreNotice = '这份已保存草稿已清理，本机副本仍可明确恢复。';
    this.updateStatus(); this.onRetired?.();
    return true;
  }
  canLeave() {
    this.retireCleared();
    if (this.disposed || ['loading', 'empty', 'saved'].includes(this.status)) return true;
    if (this.confirmedRecovery === this.recoverySnapshot() || this.persist()) return true;
    this.updateStatus();
    return false;
  }
  dispose() {
    if (!this.canLeave()) return false;
    // Stable per-draft copies already preserve unsaved input. Only explicit
    // replacement/rebase needs archiveLocal() to preserve an older version.
    this.disposed = true; clearTimeout(this.timer);
    return true;
  }
}
