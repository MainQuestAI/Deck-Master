import {fileURL} from './api.js';
import {el, button} from './dom.js';

class Gate {
  constructor(limit) { this.limit = limit; this.active = 0; this.peak = 0; this.pending = []; }
  run(work, priority = 0) {
    return new Promise((resolve, reject) => { this.pending.push({work, priority, resolve, reject}); this.pump(); });
  }
  pump() {
    this.pending.sort((a, b) => a.priority - b.priority);
    while (this.active < this.limit && this.pending.length) {
      const task = this.pending.shift(); this.active++; this.peak = Math.max(this.peak, this.active);
      Promise.resolve().then(task.work).then(task.resolve, task.reject).finally(() => { this.active--; this.pump(); });
    }
  }
}

// All gallery, comparison and page images share these gates and resident limits.
// Canvas views hold no Blob URL; decoded ImageBitmaps are closed on LRU eviction.
export class ImagePool {
  constructor() {
    this.network = new Gate(6); this.decode = new Gate(2); this.entries = new Map();
    this.hits = 0; this.evictions = 0; this.closed = 0; this.urls = 0;
    this.peakThumbs = 0; this.peakLarge = 0;
  }
  counts(kind) { return [...this.entries.values()].filter(entry => entry.kind === kind).length; }
  remove(entry) {
    if (this.entries.get(entry.key) !== entry) return;
    this.entries.delete(entry.key); entry.controller.abort();
    if (entry.bitmap) { entry.bitmap.close(); this.closed++; entry.bitmap = null; }
    this.evictions++;
  }
  acquire(project, ref, kind = 'thumb', priority = 0, retry = false) {
    if (!fileURL(ref)) throw new Error('图片引用无效，未读取其它图片。');
    const vector = ref.path.endsWith('.svg');
    const variant = kind === 'large' ? 'original-image-v1' : vector ? 'svg-browser-preview-v1' : 'thumb-480-png-v1';
    const key = `${project}:${ref.sha256}:${variant}`;
    let entry = this.entries.get(key);
    if (entry) this.hits++;
    else {
      if (this.counts(kind) >= (kind === 'thumb' ? 60 : 4)) {
        const victim = [...this.entries.values()].filter(item => item.kind === kind && !item.pins).sort((a, b) => a.touched - b.touched)[0];
        if (!victim) throw new Error('当前图片阅读位已满，请关闭一张比较图后重试。');
        this.remove(victim);
      }
      entry = {key, kind, pins: 0, touched: performance.now(), controller: new AbortController(), bitmap: null};
      this.entries.set(key, entry);
      this.peakThumbs = Math.max(this.peakThumbs, this.counts('thumb'));
      this.peakLarge = Math.max(this.peakLarge, this.counts('large'));
      entry.ready = this.load(entry, ref, vector, priority, retry).catch(error => { entry.failed = true; throw error; });
    }
    entry.pins++; entry.touched = performance.now();
    let released = false;
    return {ready: entry.ready, release: () => {
      if (released) return; released = true; entry.pins--; entry.touched = performance.now();
      if (!entry.pins && (!entry.bitmap || entry.failed)) this.remove(entry);
    }};
  }
  async fetch(entry, url, asJSON, priority) {
    return this.network.run(async () => {
      entry.controller.signal.throwIfAborted();
      // Finish an already-started loopback response; ignore its bytes if the
      // view was released. This also keeps network accounting exact on abort.
      const response = await fetch(url, {credentials: 'same-origin', cache: asJSON ? 'no-store' : 'default'});
      if (!response.ok) throw new Error('此版本的图片暂不可读，请重试。');
      const result = await (asJSON ? response.json() : response.blob());
      entry.controller.signal.throwIfAborted();
      if (!asJSON && result.size > 64 * 1024 * 1024) throw new Error('图片超过当前阅读大小限制。');
      return result;
    }, priority);
  }
  async load(entry, ref, vector, priority, retry) {
    let url = fileURL(ref);
    if (entry.kind === 'thumb' && !vector) {
      const query = new URLSearchParams({...ref, retry: retry ? '1' : '0'});
      let status;
      for (let attempt = 0; attempt < 80; attempt++) {
        status = await this.fetch(entry, '/api/thumbnails?' + query, true, priority);
        query.set('retry', '0');
        if (status.status === 'ready') break;
        if (!['queued', 'running', 'busy'].includes(status.status)) throw new Error('此层缩略图暂不可读，可重试或打开单页。');
        await new Promise(resolve => setTimeout(resolve, status.retry_after_ms || 100));
        entry.controller.signal.throwIfAborted();
      }
      if (status.status !== 'ready') throw new Error('缩略图仍在准备，请稍后重试。');
      if (!/^\/api\/thumbnail-file\?cache_key=[a-f0-9]{64}$/.test(status.url)) throw new Error('缩略图地址无效。');
      url = status.url;
    }
    const blob = await this.fetch(entry, url, false, priority);
    const bitmap = await this.decode.run(async () => {
      entry.controller.signal.throwIfAborted();
      if (!vector) return createImageBitmap(blob);
      // SVG is rendered as an inert image, never injected as inline markup.
      const objectURL = URL.createObjectURL(blob); this.urls++;
      const image = new Image();
      try {
        image.src = objectURL; await image.decode(); entry.controller.signal.throwIfAborted();
        const scale = entry.kind === 'thumb' ? Math.min(1, 480 / Math.max(image.naturalWidth, image.naturalHeight)) : 1;
        if (image.naturalWidth * image.naturalHeight > 32_000_000) throw new Error('图片像素超过阅读限制。');
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(image.naturalWidth * scale)); canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
        canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
        try { return await createImageBitmap(canvas); } finally { canvas.width = canvas.height = 0; }
      } finally { image.src = ''; URL.revokeObjectURL(objectURL); this.urls--; }
    }, priority);
    if (entry.controller.signal.aborted || this.entries.get(entry.key) !== entry) { bitmap.close(); this.closed++; throw new DOMException('Image left viewport', 'AbortError'); }
    if (bitmap.width * bitmap.height > 32_000_000) { bitmap.close(); this.closed++; throw new Error('图片像素超过阅读限制。'); }
    entry.bitmap = bitmap; return bitmap;
  }
  snapshot() {
    return {network: this.network.active, network_peak: this.network.peak, decode: this.decode.active, decode_peak: this.decode.peak,
      thumbnails: this.counts('thumb'), large: this.counts('large'), thumbnails_peak: this.peakThumbs, large_peak: this.peakLarge,
      pinned: [...this.entries.values()].filter(entry => entry.pins).length, hits: this.hits, evictions: this.evictions,
      closed_bitmaps: this.closed, active_object_urls: this.urls};
  }
}
export const imagePool = new ImagePool();

export function imageView(app, stage, title, {kind = 'thumb', priority = 0, onFailure = null} = {}) {
  const node = el('div', {class: 'pooled-image', 'data-image-state': 'loading'});
  let lease, canvas, disposed = false;
  const release = () => { lease?.release(); lease = null; if (canvas) { canvas.width = canvas.height = 0; canvas.remove(); canvas = null; } };
  function load(retry = false) {
    release(); node.dataset.imageState = 'loading'; node.replaceChildren(el('span', {class: 'muted image-loading'}, '正在读取图片…'));
    try {
      lease = imagePool.acquire(app.info.project_identity, stage.file, kind, priority, retry);
      lease.ready.then(bitmap => {
        if (disposed) return;
        canvas = el('canvas', {role: 'img', 'aria-label': title, class: kind === 'large' ? 'page-image' : 'thumbnail-image'});
        canvas.width = bitmap.width; canvas.height = bitmap.height;
        canvas.getContext('2d').drawImage(bitmap, 0, 0);
        canvas.dataset.imageReady = 'true'; node.dataset.imageState = 'ready'; node.replaceChildren(canvas);
      }).catch(failed);
    } catch (error) { failed(error); }
  }
  function failed(error) {
    if (disposed || error.name === 'AbortError') return;
    release(); node.dataset.imageState = 'failed';
    node.replaceChildren(el('p', {class: 'muted'}, error.message || '图片暂不可读，选页与固定版本仍保留。'));
    if (onFailure) onFailure(() => load(true));
    else node.append(button('重试图片', () => load(true)));
  }
  load();
  return {node, dispose() { disposed = true; release(); node.replaceChildren(); }};
}
