import {get, post, canonical, readableError, revisionQuery} from './api.js';
import {el, button, modal, version} from './dom.js';

export const contentPanel = (title, ...body) => el('section', {class:'panel'}, el('div', {class:'panel-head'}, el('h2', {}, title)), el('div', {class:'panel-body stack'}, body));
export const inputField = (label, value = '', rows = 3) => {
  const input = el('textarea', {rows, value, 'aria-label':label});
  return {input, node:el('label', {class:'stack'}, label, input)};
};

// One editor owns the recovery copy; every request freezes the original payload.
export function contentOperation(app, slot, read, hydrate, ref, onDone) {
  let loaded = false, disposed = false, serial = 0, pending = null; const guards = [];
  const notice = el('p', {role:'status', class:'content-operation-note'}), impact = el('div', {class:'stack'});
  const submit = button('确认内容变更', async () => {
    if (!pending || !canWrite() || !currentBasis()) return;
    const frozen = pending, typed = canonical(read()); submit.disabled = true;
    try {
      await app.business.submit(app.editor, frozen.action, frozen.request, frozen.basis, async result => {
        if (disposed) return;
        pending = null; impact.replaceChildren();
        notice.textContent = result.status === 'dispatched' || result.pending_tasks?.length ? '已保存，内容仍待制作工具阅读并判断影响。' : '修改已保存；保留的原图需按新内容核对。';
        if (canonical(read()) === typed) onDone?.(result);
        else notice.append(el('span', {}, ' 后写输入仍保留在原基准草稿中。'), button('查看已保存版本', () => app.go({revision:result.revision_id})));
      });
    } catch (error) { notice.textContent = readableError(error); }
    finally { controls(); }
  }, true, {disabled:true});
  function canWrite() { return loaded && !disposed && !app.readonly && !app.editor?.readonly && canonical(app.editor?.draft.base_ref) === canonical(ref) && (!app.editor.exactRevision || app.editor.draft.base_revision === app.route.revision); }
  function currentBasis() { return app.latest?.revision_id === app.route.revision; }
  function controls() { for (const guard of guards) guard.disabled = !canWrite(); submit.disabled = !canWrite() || !currentBasis() || !pending || Boolean(app.business.entries.size || app.business.loadWarning); }
  function versionChanged() {
    if (currentBasis() || disposed) return;
    serial++; pending = null; impact.replaceChildren();
    notice.textContent = '项目已有新版本，旧内容计划已禁用。当前输入仍保留为草稿；读取当前版本并核对后重新预览。';
    controls();
  }
  function changed() {
    serial++; pending = null; impact.replaceChildren(); controls();
    if (!canWrite()) return;
    app.editor.draft.content[slot] = structuredClone(read()); app.editor.changed();
  }
  function bind() {
    loaded = false; serial++; pending = null; impact.replaceChildren(); controls();
    const editor = app.editor;
    editor.ready.then(() => {
      if (disposed || editor !== app.editor) return;
      if (editor.draft.content[slot]) hydrate(structuredClone(editor.draft.content[slot]));
      loaded = true;
      if (!canWrite() && !app.readonly) notice.textContent = '草稿绑定另一份内容基准；输入已保留，请回到对应版本核对后编辑。';
      controls();
    });
  }
  async function preview(input) {
    if (!canWrite()) return;
    if (!currentBasis()) { versionChanged(); return; }
    const token = ++serial; pending = null; controls();
    try {
      await app.business.available();
      const value = {schema_version:'content_operation_input.v1', project_id:app.info.project_id, base_revision:app.route.revision, ...input};
      const result = await post('/api/content/plan', {input:value});
      if (disposed || token !== serial) return;
      if (!currentBasis()) { versionChanged(); return; }
      pending = {action:'content.commit', request:{plan_id:result.plan_id, base_revision:value.base_revision}, basis:{plan_id:result.plan_id, plan:result.plan}};
      const info = result.plan.impact;
      impact.replaceChildren(el('strong', {}, '本次影响预览'),
        el('p', {}, `修改 ${info.changed_pages.length} 页，移除或替换 ${info.removed_pages.length} 个旧页身份；${info.superseded_tasks.length} 项未完任务将失效。`),
        el('p', {}, info.host_required ? '仅交接选定页，制作工具返回后才更新正文。不会在此生成图片。' : '确认后保存内容，未改页及历史对象保留。'),
        el('p', {class:'muted'}, '旧意见保留旧基准，不自动迁移。' + (info.deck_outputs_invalidated ? '实际稿件变更后整稿文件需要更新。' : '') + (info.preserved_originals_need_review ? '旧原图保留，但需要核对新内容适用性。' : '')));
      impact.append(el('p', {}, [...new Set([...info.changed_pages,...info.removed_pages])].map(id => app.summary.pages.find(p=>p.page_id===id)?.title || id).join('、')));
      impact.scrollIntoView({block:'center'});
      submit.textContent = info.host_required ? '确认并交接内容调整' : '确认内容变更'; notice.textContent = '';
    } catch (error) { if (!disposed && token === serial) notice.textContent = readableError(error); }
    controls();
  }
  function previewInputs(input, differences = []) {
    if (!canWrite()) return;
    if (!currentBasis()) { versionChanged(); return; }
    pending = {action:'content.inputs', request:{input, base_revision:app.route.revision}, basis:{input}};
    impact.replaceChildren(el('strong', {}, '材料与任务要求变更'), el('p', {}, '确认后旧材料版本保留，输入进入待协调；原有未完任务会由新内容整理接续。只有制作工具判断并采用后才说明内容已对齐，不默认整套重制。'));
    impact.append(el('ul', {}, differences.map(text=>el('li',{},text)))); impact.scrollIntoView({block:'center'});
    submit.textContent = '确认输入并交接判断'; notice.textContent = ''; controls();
  }
  const reject = event => { if (event.detail.action.startsWith('content.')) { pending = null; controls(); } };
  app.root.addEventListener('draft-editor-replaced', bind); app.root.addEventListener('business-state-changed', controls); app.root.addEventListener('business-rejected', reject);
  app.root.addEventListener('summary-refreshed', versionChanged);
  app.disposables.push(() => { disposed = true; serial++; app.root.removeEventListener('summary-refreshed', versionChanged); app.root.removeEventListener('draft-editor-replaced', bind); app.root.removeEventListener('business-state-changed', controls); app.root.removeEventListener('business-rejected', reject); });
  bind();
  return {changed, preview, previewInputs, canWrite, guard(node) { const fieldset = el('fieldset', {class:'content-form-fields', disabled:!canWrite()}, node); guards.push(fieldset); return fieldset; }, node:el('div', {class:'content-operation stack'}, notice, impact, submit)};
}

export function sourceReader(app, link, revision = app.route.revision) {
  const node = el('div', {class:'stack'}, el('p', {}, '正在读取固定材料版本…'));
  const dialog = modal('材料原文与定位', node), controller = new AbortController();
  const close = () => controller.abort();
  dialog.addEventListener('close', close, {once:true});
  app.disposables.push(() => { controller.abort(); dialog.removeEventListener('close',close); if (dialog.contains(node) && dialog.open) dialog.close(); });
  const query = new URLSearchParams({revision});
  if (link.locator) query.set('locator', link.locator);
  if (link.source_version?.extract?.sha256) query.set('extract_sha256', link.source_version.extract.sha256);
  get('/api/content/sources/' + encodeURIComponent(link.source_id) + '?' + query, {signal:controller.signal}).then(data => {
    if (controller.signal.aborted || !node.isConnected) return;
    node.replaceChildren(el('h3', {}, data.name), el('p', {class:'muted'}, version(data.revision_id) + ' · 提取状态：' + data.extraction_status),
      el('p', {}, data.location === 'exact' ? `已定位：${data.requested_locator}` : '仅定位到材料版本，未找到可核验的精确位置。'),
      el('p', {class:'muted'}, '这是提取原文；打开材料不表示制作工具已经阅读或判断影响。'),
      ...data.matches.map(match => el('pre', {class:'read-text'}, match.text || JSON.stringify(match))),
      el('details', {open:!data.matches.length}, el('summary', {}, '材料全文'), el('pre', {class:'read-text'}, data.text || '没有可读文本，请保留原文件并查看提取状态。')));
  }).catch(error => { if (!controller.signal.aborted && node.isConnected) node.replaceChildren(el('p', {class:'field-error'}, readableError(error)),el('p', {class:'muted'}, '稿件与已保存材料引用保留。请关闭后重试，或恢复对应材料版本。')); });
}

// Edit text leaves without replacing table, bullet, citation or block identities.
function textFields(value, path = [], out = []) {
  if (typeof value === 'string') {
    const key = path.at(-1), parent = path.at(-2);
    if (['title','subtitle','text','heading','label','display_text'].includes(key) || typeof key === 'number' && parent === 'items') out.push(path);
  } else if (value && typeof value === 'object') for (const [key, child] of Object.entries(value)) textFields(child, [...path, Array.isArray(value) ? Number(key) : key], out);
  return out;
}
const at = (value, path) => path.reduce((v,k) => v[k], value);
// F06/N04：字段标签必须表达作品位置，不能用全局序号——同文节点靠"块 + 块内
// 位置"区分，块标题（相邻文本）一并给出。
const leafNames = {title: '标题', subtitle: '副标题', heading: '小标题', label: '标签', text: '文字', display_text: '显示文字'};
const blockKeyNames = {body_blocks: '正文块', sections: '章节', paragraphs: '段落组', items: '条目组'};
const containerKeyNames = {items: '条目', rows: '行', columns: '列', cells: '单元格', children: '子条目'};
function blockAt(path) { return path.findIndex((segment, i) => i > 0 && typeof segment === 'number'); }
function blockHeading(value, path, arrayAt) {
  if (arrayAt < 1) return null;
  const container = at(value, path.slice(0, arrayAt + 1));
  const anchor = container && typeof container === 'object' && !Array.isArray(container)
    ? [container.title, container.heading, container.label].find(v => typeof v === 'string' && v.trim()) : null;
  const key = path[arrayAt - 1];
  const base = `${blockKeyNames[key] || key} ${path[arrayAt] + 1}`;
  return anchor ? `${base} · ${anchor.trim().slice(0, 24)}` : base;
}
function leafLabel(path, arrayAt) {
  const parts = [];
  for (let i = arrayAt + 1; i < path.length; i++) {
    const segment = path[i];
    if (typeof segment === 'number') parts.push(`${containerKeyNames[path[i - 1]] || '条目'} ${segment + 1}`);
    else if (i + 1 < path.length && typeof path[i + 1] === 'number') continue;
    else parts.push(leafNames[segment] || segment);
  }
  return parts.join(' · ') || '文字';
}
export function pageContentEditor(app, data) {
  if (app.readonly || !data.page?.customer_visible) return null;
  let value = structuredClone(data.page.customer_visible);
  let original = structuredClone(data.page.customer_visible);
  const fields = el('div', {class:'stack'});
  // UX-04b（对账 §5「具体文字差异」）：具体改动常驻显示「块位置：原文 → 改文」，
  // 与影响预览同屏；用户不必在整页文本框之间自行回忆改了什么。
  const changes = el('div', {class:'stack content-changes'});
  const reason = inputField('正文修改说明', '调整本页标题或正文', 2);
  let operation;
  function leafLabelFor(path) {
    if (path.length === 1) return ({title:'页面标题',subtitle:'页面副标题'}[path[0]] || '页面文字');
    const arrayAt = blockAt(path);
    return `${blockHeading(value, path, arrayAt) || '正文'} · ${leafLabel(path, arrayAt)}`;
  }
  function drawChanges() {
    const rows = textFields(value).filter(path => at(original, path) !== at(value, path)).map(path => el('li', {},
      el('span', {class:'content-change-label'}, leafLabelFor(path)),
      el('span', {class:'content-change-before'}, at(original, path) || '（空）'),
      el('span', {class:'content-change-arrow'}, ' → '),
      el('span', {class:'content-change-after'}, at(value, path) || '（空）')));
    changes.replaceChildren(el('h3', {}, `本次具体改动（${rows.length}）`),
      rows.length ? el('ul', {class:'content-change-list'}, rows)
        : el('p', {class:'muted'}, '尚未改动文字。这里逐条显示「原文 → 改文」，与下方影响预览同屏核对。'));
  }
  function draw() {
    fields.replaceChildren();
    const rank = path => path.length === 1 && path[0] === 'title' ? 0 : path.length === 1 && path[0] === 'subtitle' ? 1 : 2;
    let lastHeading = null;
    for (const path of textFields(value).sort((a,b)=>rank(a)-rank(b))) {
      if (path.length === 1) {
        const label = ({title:'页面标题',subtitle:'页面副标题'}[path[0]] || '页面文字');
        const item = inputField(label, at(value,path), 2);
        item.input.addEventListener('input', () => { const parent = at(value,path.slice(0,-1)); parent[path.at(-1)] = item.input.value; operation.changed(); drawChanges(); });
        fields.append(item.node);
        lastHeading = null;
        continue;
      }
      const arrayAt = blockAt(path);
      const head = blockHeading(value, path, arrayAt);
      if (head !== lastHeading) { fields.append(el('p', {class:'muted content-block-label'}, head || '正文')); lastHeading = head; }
      const label = `${head || '正文'} · ${leafLabel(path, arrayAt)}`;
      const item = inputField(label, at(value,path), 4);
      item.input.addEventListener('input', () => { const parent = at(value,path.slice(0,-1)); parent[path.at(-1)] = item.input.value; operation.changed(); drawChanges(); });
      fields.append(item.node);
    }
    drawChanges();
  }
  draw();
  operation = contentOperation(app, 'page_edit', () => ({visible:value,reason:reason.input.value}), saved => {
    // 保存后改文成为新的已保存原文，对照清单重新从零开始。
    if (saved.visible) value = saved.visible;
    original = structuredClone(value); reason.input.value = saved.reason || ''; draw();
  }, data.stages.content.ref,
    result => app.go({revision:result.revision_id, layer:'content'}));
  reason.input.addEventListener('input', operation.changed);
  const preview = button('预览正文修改影响', () => operation.preview({content_plan_ref:data.content_plan?.ref || null, action:'edit', instruction:reason.input.value,
    targets:[{page_id:data.page_id,page_ref:data.stages.content.ref}],customer_visible:value}));
  const derivations = el('div');
  get('/api/content/lineage/'+encodeURIComponent(data.page_id)+revisionQuery(data.revision_id)).then(result => {
    if (result.records.length) derivations.append(el('p', {class:'notice'}, '本页由合并或拆分产生。旧页意见仍留在旧身份，不会自动迁移到这里。'),
      ...result.records.map(r => button('查看来源页关系', () => modal('新页的来源', el('div', {class:'stack'},
        r.derivation.source_pages.map(p => button('打开来源页 '+p.page_id, () => { document.querySelector('#modal').close(); app.go({page_id:p.page_id,revision:r.derivation.source_revision,layer:'content'}); })))))));
  }).catch(error => derivations.append(el('p', {class:'field-error'}, readableError(error))));
  return el('details', {class:'content-editor'}, el('summary', {}, '编辑本页标题与正文'), el('div', {class:'stack'}, derivations, operation.guard(el('div', {class:'stack'}, changes, fields, reason.node, preview)), operation.node));
}
