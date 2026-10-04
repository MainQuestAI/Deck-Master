import {get, post, digest, readableError} from './api.js';
import {el, button, modal, version} from './dom.js';
import {canonicalAction, expectedRequestDigest, receiptTerminal} from './receipt-verdict.js';

const paths = {'styles.analyze':'/api/styles/analyze', 'icons.confirm':'/api/icons/confirm', 'history.restore':'/api/history/commit-restore', 'content.commit':'/api/content/commit', 'content.inputs':'/api/content/inputs', 'styles.confirm': '/api/styles/confirm', 'annotations.save': '/api/annotations/batch', 'changes.commit': '/api/changes/commit', 'candidates.adopt': '/api/candidates/adopt', 'candidates.decide': '/api/candidates/decision', 'stages.assemble': '/api/stages/assemble'};
// 升级前的待核实记录以旧 action 名冻结（digest 也用旧 kind）。规范化映射让它们
// 进入恢复/核实/重放路径：端点与显示走规范名，身份核对按兼容规则重算（见
// expectedRequestDigest），绝不可静默跳过或覆盖（终审补丁 P2）。
export class BusinessOperations {
  constructor(app) {
    this.app = app; this.entries = new Map(); this.completed = new Map();
    this.key = `deck-master:v3:pending-business:${app.info.project_identity}`;
    this.node = el('section', {class: 'business-pending stack', hidden: true, 'aria-label': '待核实的业务保存'});
    this.ready = this.restore();
  }
  async valid(pending) {
    return pending && paths[canonicalAction(pending.payload?.action)] && pending.operation_id === pending.payload.request?.operation_id &&
      pending.payload_digest === await digest(pending.payload) && /^[a-f0-9]{64}$/.test(pending.payload.request_digest || '');
  }
  async observe(editor) {
    if (editor.disposed) return;
    const pending = structuredClone(editor.draft.pending);
    if (!pending) return;
    const existing = this.entries.get(pending.operation_id);
    if (existing) {
      if ((!existing.editor || existing.editor.disposed) && existing.draft_id === editor.draft.draft_id) existing.editor = editor;
      return;
    }
    if (!await this.valid(pending) || editor.draft.pending?.operation_id !== pending.operation_id || this.entries.has(pending.operation_id)) return;
    this.entries.set(pending.operation_id, {pending, draft_id: editor.draft.draft_id, editor, state: 'unknown'});
    this.persist(); this.render();
  }
  async restore() {
    try {
      const local = JSON.parse(localStorage.getItem(this.key) || '[]');
      for (const entry of local) if (await this.valid(entry.pending)) this.entries.set(entry.pending.operation_id, {...entry, state: 'unknown'});
    } catch { this.storageWarning = '浏览器中的待核实副本暂不可读；请保留草稿恢复文件。'; }
    try {
      const saved = await get('/api/drafts');
      for (const record of saved.records) if (await this.valid(record.draft.pending) && !this.entries.has(record.draft.pending.operation_id))
        this.entries.set(record.draft.pending.operation_id, {pending: record.draft.pending, draft_id: record.draft.draft_id, state: 'unknown'});
    } catch { this.loadWarning = '项目中的待核实请求尚未读取；重新连接后再提交。'; }
    this.render();
  }
  persist() {
    try {
      localStorage.setItem(this.key, JSON.stringify([...this.entries.values()].map(({pending, draft_id, state}) => ({pending, draft_id, state}))));
      this.storageWarning = ''; return true;
    } catch { this.storageWarning = '浏览器未保存请求副本；只有项目草稿收到确认后才能发送。'; return false; }
  }
  render() {
    this.node.hidden = !this.entries.size && !this.storageWarning && !this.loadWarning;
    this.node.replaceChildren(el('div', {class: 'stack'}, el('strong', {}, this.entries.size ? '保存结果待核实 · 新的业务提交已暂停' : '恢复请求'),
      this.storageWarning && el('p', {}, this.storageWarning), this.loadWarning && el('p', {}, this.loadWarning),
      this.loadWarning && button('重新读取待核实请求', async () => { this.loadWarning = ''; this.ready = this.restore(); await this.ready; }),
      [...this.entries.values()].map(entry => el('div', {class: 'pending-operation stack'},
        el('p', {}, ({'icons.confirm':'图标范围确认', 'history.restore':'历史恢复', 'content.commit':'内容变更', 'content.inputs':'材料与任务要求', 'styles.confirm': '风格版本确认', 'annotations.save': '意见保存', 'changes.commit': '修改计划提交', 'candidates.adopt': '候选采用', 'candidates.decide': '候选决定', 'stages.assemble': '整稿制作'})[canonicalAction(entry.pending.payload.action)]),
        el('p', {role: 'status'}, entry.note || (entry.state === 'sending' ? '正在确认保存结果，输入仍可继续写。' : '保留原请求和编号，后写草稿不会替换它。')),
        el('div', {class: 'row wrap'}, button('核实保存结果', () => this.verify(entry), false, {disabled: ['preparing', 'sending', 'checking'].includes(entry.state)}),
          entry.state === 'not_found' && button('重放已保存的原请求', () => this.execute(entry)),
          button('查看原请求', () => modal('已冻结的原请求', el('pre', {class: 'evidence-json'}, JSON.stringify(entry.pending.payload.request, null, 2)))))))));
    this.app.root.dispatchEvent(new CustomEvent('business-state-changed'));
  }
  async available() {
    await this.ready;
    if (this.preparing) throw new Error('上一项请求正在保存副本，请稍候。');
    if (this.loadWarning) throw new Error('项目恢复状态尚未读取，请先重新连接。');
    if (this.entries.size) throw new Error('先核实上一次保存结果；当前输入会继续保留。');
  }
  async submit(editor, action, request, basisPayload, onComplete) {
    await this.available(); await editor.ready;
    if (this.entries.size || this.loadWarning) throw new Error('先核实上一次保存结果；当前输入会继续保留。');
    if (this.preparing) throw new Error('上一项请求正在保存副本，请稍候。');
    this.preparing = true;
    try {
    await editor.pendingWrite;
    if (editor.readonly || editor.disposed || ['loading', 'unknown', 'conflict', 'saving'].includes(editor.status))
      throw new Error('请先核实或保留当前个人草稿，再提交业务要求。');
    const operation_id = crypto.randomUUID();
    request = {...structuredClone(request), operation_id};
    const request_digest = await digest({protocol: 'changes.v1', kind: action, project_id: this.app.info.project_id,
      base_revision: request.base_revision, payload: basisPayload});
    const payload = {action, request, request_digest};
    const pending = {operation_id, payload, payload_digest: await digest(payload)};
    const entry = {pending, draft_id: editor.draft.draft_id, editor, onComplete, state: 'preparing'};
    editor.draft.pending = structuredClone(pending); editor.status = 'dirty'; editor.persist(); editor.updateStatus();
    this.entries.set(operation_id, entry); const localSaved = this.persist(); this.render();
    await editor.save();
    if (!localSaved && !(editor.status === 'saved' && editor.draft.pending?.operation_id === operation_id)) {
      entry.state = 'unknown'; entry.note = '请求副本未确认持久保存；请下载个人草稿恢复文件后核实。'; this.render(); return;
    }
    return this.execute(entry);
    } finally { this.preparing = false; }
  }
  async execute(entry) {
    if (['sending', 'checking'].includes(entry.state)) return;
    if (!await this.valid(entry.pending)) { entry.note = '请求副本校验失败，保留恢复文件并重新读取原项目。'; this.render(); return; }
    entry.state = 'sending'; entry.note = ''; this.persist(); this.render();
    try {
      const result = await post(paths[canonicalAction(entry.pending.payload.action)], entry.pending.payload.request);
      await this.accept(entry, result);
    } catch (error) {
      if (!error.status || error.status >= 500 || error.code === 'invalid_response') {
        entry.state = 'unknown'; entry.note = '尚未确认保存结果；可继续写草稿，请先核实原请求。' + readableError(error);
      } else {
        entry.state = 'rejected'; entry.note = readableError(error);
        await this.clear(entry); this.conflict(entry, error);
        this.app.root.dispatchEvent(new CustomEvent('business-rejected', {detail: {action: entry.pending.payload.action, error}}));
      }
      this.persist(); this.render();
    }
  }
  async verify(entry) {
    if (['preparing', 'sending', 'checking'].includes(entry.state)) return;
    entry.state = 'checking'; entry.note = '正在核实原编号…'; this.render();
    try { await this.accept(entry, await get('/api/operations/' + encodeURIComponent(entry.pending.operation_id))); }
    catch (error) {
      if (error.status === 404 && error.code === 'operation_not_found') {
        entry.state = 'not_found'; entry.note = '尚未发现已提交事实。只能重放下面保留的原请求，不能换成后写草稿。';
      } else { entry.state = 'unknown'; entry.note = '核实未完成，原编号保持不变。' + readableError(error); }
      this.persist(); this.render();
    }
  }
  async expectedRequestDigest(entry) {
    // decision 的收据核对基准即请求的 input（business.submit 的 basisPayload 与之同构）。
    return await expectedRequestDigest(entry.pending.payload, this.app.info.project_id);
  }
  async accept(entry, response) {
    // 确定终态有两种：已提交（committed，必须命名其修订）与无变化（unchanged，
    // 服务端未写入，但携带与请求一致的 operation 身份与摘要）。两者都做完整
    // 身份校验后清除收据；其余形状维持待核实（终审补丁 P1）。
    await this.expectedRequestDigest(entry);
    if (!await receiptTerminal(entry, response, this.app.info.project_id))
      throw new Error('回包与原请求不一致，继续保留待核实状态。');
    const result = response.operation_result || response;
    this.completed.set(entry.pending.operation_id, result);
    await this.clear(entry);
    if (!entry.editor?.disposed) {
      try { await entry.onComplete?.(result); }
      catch { this.app.setNotice('业务保存已确认；工作面暂未刷新，可从任务或意见列表重新打开。'); }
    }
    this.app.root.dispatchEvent(new CustomEvent('business-committed', {detail: {action: entry.pending.payload.action, result}}));
    this.render();
  }
  async clear(entry) {
    this.entries.delete(entry.pending.operation_id); this.persist();
    const editor = entry.editor;
    if (editor && !editor.disposed && editor.draft.pending?.operation_id === entry.pending.operation_id) {
      editor.draft.pending = null;
      if (!editor.readonly) { editor.changed(); await editor.save(); return; }
      editor.persist(); editor.updateStatus();
    }
    // Clear only this matching recovery pointer, preserving all later text.
    try {
      const {record} = await get('/api/drafts/' + encodeURIComponent(entry.draft_id));
      if (record?.draft.pending?.operation_id === entry.pending.operation_id) {
        const draft = structuredClone(record.draft); draft.pending = null;
        await post('/api/drafts/save', {draft, expected_etag: record.etag});
      }
    } catch { this.app.setNotice('业务保存已核实，草稿中的待核实标记暂未清除。下次可按原编号再次核实。'); }
  }
  async conflict(entry, error) {
    let latest;
    try { latest = await get('/api/view/summary'); } catch { /* Keep both the draft and the exact failure. */ }
    const editor = entry.editor;
    const payload = entry.pending?.payload;
    modal(payload?.action === 'candidates.adopt' ? '本次未采用任何页，选择已保留' : '本次未提交，输入已保留', el('div', {class: 'stack'}, el('p', {class: 'field-error'}, entry.note),
      error.details?.items?.length && el('ul', {}, error.details.items.map(item => el('li', {}, `${item.page_id || '候选'}：${item.cause === 'generation_basis_changed' ? '生成依据已变化' : item.cause === 'one_candidate_per_page' ? '同一页只能选择一个候选' : '请重新核对采用目标'}`))),
      el('div', {class: 'conflict-panes'},
        el('section', {}, el('h3', {}, '你的本机草稿'), el('textarea', {readOnly: true, value: editor?.pendingText?.() || JSON.stringify(payload?.request || {}), 'aria-label': '未提交的本机草稿'})),
        el('section', {}, el('h3', {}, '服务端新基准'), el('p', {}, latest ? version(latest.revision_id) : '暂时无法读取'),
          el('p', {}, '没有采用或覆盖任何页。重新阅读差异后，再建立新计划。')))),
      [editor && button('下载保留的草稿', () => editor.download()), latest && button('查看新的当前版本', () => {
        document.querySelector('#modal').close(); this.app.go({revision: latest.revision_id});
      })].filter(Boolean));
  }
}
