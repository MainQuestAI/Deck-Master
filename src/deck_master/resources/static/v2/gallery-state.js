import {get, post, canonical} from './api.js';

// This is personal reading state. No business update or generation request.
export class GalleryMemory {
  constructor(app, saved) {
    this.app = app; this.etag = saved.record?.etag || null; this.listeners = new Set();
    this.state = saved.record?.state || {schema_version: 'ui_gallery.v1', project_id: app.info.project_id,
      project_identity: app.info.project_identity, revision_id: app.route.revision, layer: 'original_image', mode: 'grid', columns: 3,
      selected_page_ids: [], references: [], filter: {chapter_id: null, status: 'all'}, anchor: {page_id: null, offset: 0},
      zoom: {synchronized: true, scale: 1}};
    this.message = saved.issues?.length ? '已保留选页；部分固定参考不可读，可移除失效参考后继续。' : '个人画廊状态';
  }
  subscribe(callback) { this.listeners.add(callback); callback(); return () => this.listeners.delete(callback); }
  notify() { this.listeners.forEach(callback => callback()); }
  update(patch) {
    this.state = {...this.state, ...patch}; this.dirty = true;
    if (!this.error) this.message = '画廊选择待保存';
    this.notify(); clearTimeout(this.timer);
    if (!this.error) this.timer = setTimeout(() => this.flush(), 300);
  }
  async flush() {
    clearTimeout(this.timer);
    if (this.saving || this.error || !this.dirty) return;
    this.pending ||= {state: structuredClone(this.state), expected_etag: this.etag};
    this.saving = true; this.message = '正在保存画廊选择…'; this.notify();
    try {
      const result = await post('/api/gallery', this.pending);
      this.etag = result.record.etag;
      this.dirty = canonical(this.state) !== canonical(this.pending.state);
      this.pending = null; this.message = this.dirty ? '后续选择待保存' : '画廊选择已保存';
    } catch (error) {
      this.error = error;
      this.message = error.code === 'local_state_conflict' ? '另一个窗口保存了不同选择；此窗口的选择仍保留。' :
        (!error.status || error.status >= 500) ? '保存结果待核实；此窗口的选择仍保留。' : '画廊选择未保存，请检查失效参考后重试。';
      if (error.status && error.status < 500) this.pending = null;
    } finally {
      this.saving = false; this.notify();
      if (this.dirty && !this.error) this.timer = setTimeout(() => this.flush(), 300);
    }
  }
  retry() { this.error = null; this.flush(); }
  async compareSaved() { return get('/api/gallery'); }
  useWindow(record) { this.etag = record?.etag || null; this.pending = null; this.error = null; this.dirty = true; this.flush(); }
  useSaved(record) {
    if (!record) return;
    this.state = structuredClone(record.state); this.etag = record.etag;
    this.pending = null; this.error = null; this.dirty = false; this.message = '已读取项目保存的选择'; this.notify();
  }
}
