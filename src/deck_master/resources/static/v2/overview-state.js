import {get, post, canonical} from './api.js';

const reading = state => ({search: state.search, filter: state.filter, sort: state.sort});

export class OverviewMemory {
  constructor(app, saved = {}) {
    app.overviewMemories ||= new Map();
    const key = app.info.project_identity + ':' + app.route.revision, previous = app.overviewMemories.get(key);
    if (previous && (previous.dirty || previous.error || previous.saving) && (!app.route.overview_preferences || canonical(reading(previous.state)) === canonical(app.route.overview_preferences))) {
      previous.disposed = false;
      return previous;
    }
    this.app = app; this.listeners = new Set(); this.etag = saved.etag ?? saved.record?.etag ?? null;
    this.supported = app.health.ui_capabilities?.includes('ui_overview.v1');
    this.key = app.info.project_identity + ':' + app.route.revision;
    app.overviewMemories.set(this.key, this);
    app.overviewSession ||= new Map();
    const initial = app.route.overview_preferences || saved.record?.state || ((!this.supported || saved.error) && app.overviewSession.get(this.key)) || {search:'', filter:'all', sort:'ascending'};
    // D1：批量选择随个人阅读状态持久化（ui_overview.v1 的可选字段）。URL 只承载
    // 阅读偏好，不承载选择；刷新后选择从已保存状态恢复。恢复选择只恢复"选中了
    // 谁"，不恢复可提交计划（计划仍需重新预览）。
    const savedSelection = saved.record?.state?.selected_page_ids;
    this.state = {schema_version:'ui_overview.v1', project_id:app.info.project_id, project_identity:app.info.project_identity,
      revision_id:app.route.revision, ...reading(initial),
      selected_page_ids: Array.isArray(savedSelection) ? savedSelection
        : Array.isArray(initial.selected_page_ids) ? initial.selected_page_ids : []};
    this.error = saved.error || null;
    this.message = this.error ? '总览偏好暂不可读；当前输入保留，可重试读取或下载。' : this.supported ? '个人总览阅读偏好' : '当前核心未提供偏好保存；仅保留本窗口会话。';
    // Opening a link only reads preferences. Explicit edits trigger saves.
  }
  subscribe(callback) { this.listeners.add(callback); return () => this.listeners.delete(callback); }
  notify() { if (!this.disposed) this.listeners.forEach(callback => callback()); }
  update(patch, {quiet = false} = {}) {
    this.state = {...this.state, ...patch}; this.app.overviewSession.set(this.key, reading(this.state));
    this.dirty = true;
    // 合并语义：只要自上次落盘以来有过一次"有声"改动，本次落盘就有声。
    if (!quiet) this.quietNext = false;
    else if (this.quietNext === undefined) this.quietNext = true;
    // 勾选变化等静默保存不驱动偏好状态行，避免每次点选都闪过保存提示。
    if (!quiet && !this.error) this.message = this.supported ? '总览阅读偏好待保存' : '仅保留本窗口会话，未写入项目。';
    this.notify(); clearTimeout(this.timer);
    if (this.supported && !this.error) this.timer = setTimeout(() => this.flush(), 300);
  }
  async flush() {
    clearTimeout(this.timer);
    if (!this.supported || this.saving || this.error || !this.dirty) return;
    const quiet = this.quietNext === true; this.quietNext = undefined;
    this.pending ||= {state:structuredClone(this.state), expected_etag:this.etag};
    this.saving = true; if (!quiet) { this.message = '正在保存总览阅读偏好…'; this.notify(); }
    try {
      const result = await post('/api/overview', this.pending);
      this.etag = result.record.etag; this.dirty = canonical(this.state) !== canonical(this.pending.state);
      this.pending = null; if (!quiet) this.message = this.dirty ? '后续输入待保存' : '总览阅读偏好已保存';
    } catch (error) {
      this.error = error;
      this.message = error.code === 'local_state_conflict' ? '另一个窗口修改或清理了偏好；此窗口输入保留。请核实后明确选择。' : '总览偏好保存尚未确认；此窗口输入保留，可核实或下载。';
      if (error.status && error.status < 500) this.pending = null;
    } finally {
      this.saving = false; this.notify();
      if (this.dirty && !this.error && !this.disposed) this.timer = setTimeout(() => this.flush(), 300);
      if (this.disposed && !this.dirty && !this.error && this.app.overviewMemories.get(this.key) === this) this.app.overviewMemories.delete(this.key);
    }
  }
  async compareSaved() { return get('/api/overview?' + new URLSearchParams({revision:this.state.revision_id})); }
  async verify() {
    const saved = await this.compareSaved();
    if (this.pending && canonical(saved.record?.state) === canonical(this.pending.state)) {
      this.etag = saved.etag; this.dirty = canonical(this.state) !== canonical(this.pending.state);
      this.pending = null; this.error = null; this.message = '原偏好保存已核实，当前后写输入保留。'; this.notify();
      if (this.dirty && !this.disposed) this.timer = setTimeout(() => this.flush(), 300);
      return {confirmed:true, saved};
    }
    return {confirmed:false, saved};
  }
  useWindow(saved) { this.etag = saved.etag; this.error = null; this.pending = null; this.dirty = true; this.flush(); }
  useSaved(saved) {
    const savedState = saved.record?.state || {search:'',filter:'all',sort:'ascending'};
    this.state = {...this.state, ...reading(savedState),
      selected_page_ids: Array.isArray(savedState.selected_page_ids) ? savedState.selected_page_ids : []};
    this.etag = saved.etag; this.pending = null; this.error = null; this.dirty = false;
    this.app.overviewSession.set(this.key, reading(this.state)); this.message = '已读取项目保存的总览偏好'; this.notify();
  }
  dispose() {
    clearTimeout(this.timer); this.disposed = true; this.listeners.clear(); if (!this.error) this.flush();
    if (!this.dirty && !this.error && !this.saving && this.app.overviewMemories.get(this.key) === this) this.app.overviewMemories.delete(this.key);
  }
}
