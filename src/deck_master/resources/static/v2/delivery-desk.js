import {historyLabel} from './history-labels.js';
import {get, post, revisionQuery, readableError} from './api.js';
import {el, button, modal, version} from './dom.js';
import {DraftEditor} from './drafts.js';
import {productionView} from './production-view.js';

const names = {review: '审阅包', delivery: '正式交付包', engineering: '内部工程包'};
const descriptions = {
  review: '可读正文、已有图稿与缺项说明。尚无 PPT 也可生成，不包含内部材料与完整提示词。',
  delivery: '使用所选版本的质量检查、输入对齐和交付政策。存在未解决项时拒绝生成。',
  engineering: '包含原材料、完整提示词和恢复所需历史，仅供内部恢复；不含认证文件和个人草稿。',
};
const layerNames = {content: '逐页稿', page: '逐页稿', blueprint: '原图', svg: 'SVG', svg_preview: 'SVG 预览', ppt: '整稿 PPT', ppt_preview: 'PPT 预览',
  blueprint_content: '原图内容检查', blueprint_fidelity: '原图一致性检查', conversion: '转换检查', readability: '阅读检查', privacy: '隐私检查', professional_use: '专业使用评估', page_limit: '页数限制', render_report: '制作报告'};
const panel = (title, ...children) => el('section', {class: 'panel'}, el('div', {class: 'panel-head'}, el('h2', {}, title)), el('div', {class: 'panel-body stack'}, children));
const exportURL = (record, name) => '/api/exports/' + encodeURIComponent(record.export_id) + '/files/' + name.split('/').map(encodeURIComponent).join('/');

// Each gap names the rule it actually broke and the honest next step. A locate
// action is never renamed into a repair, toolchain steps say they happen outside
// the page, and a reason this app cannot classify keeps its raw detail instead of
// being flattened into "待检查".
const gapRules = {
  not_recorded: {label: '对应产物未记录', next: '先更新对应预览或编译整稿，再重新检查'},
  input_reconciliation_pending: {label: '输入待协调', next: '进入输入协调流程；导出用途与固定版本保持不变'},
  needs_reconciliation: {label: '输入待协调', next: '进入输入协调流程；导出用途与固定版本保持不变'},
  basis_changed: {label: '制作或检查依据已变化', next: '定位受影响对象，重新计划对应更新或检查'},
  not_evaluated: {label: '此维度尚未评估', next: '完成对应质量检查；未评估不能当作通过'},
  unresolved: {label: '仍有未解决问题', next: '查看具体问题，处理后重新检查'},
  page_limit_violation: {label: '不符合页数规则', next: '按该规则调整页数或提供对应证据'},
};
const toolchainLayers = new Set(['ppt', 'ppt_preview', 'deck_outputs', 'render_report', 'conversion']);
const locateLayer = layer => layer === 'blueprint' || String(layer).startsWith('blueprint_') ? 'original_image'
  : String(layer).startsWith('svg') ? 'svg' : String(layer).startsWith('ppt') || layer === 'conversion' ? 'ppt' : 'content';

function gapsView(app, gaps, revision) {
  if (!gaps?.length) return el('p', {class: 'muted'}, '未列出缺项；正式交付仍由服务核对所选快照。');
  const pageMap = new Map(app.summary.pages.map((p, i) => [p.page_id, `${i + 1}. ${p.title || p.page_id}`]));
  const node = el('div', {class: 'stack export-gaps'}); let count = 20;
  function render() {
    node.replaceChildren(el('ul', {class: 'gap-list'}, gaps.slice(0, count).map(gap => {
      const rule = gapRules[gap.reason];
      const actions = el('div', {class: 'row wrap'});
      if (gap.page_id) actions.append(button('定位此页', () => app.go({surface: 'page', page_id: gap.page_id, revision, layer: locateLayer(gap.layer)})));
      actions.append(button('查看任务与交付', () => app.go({surface: 'runs', revision})));
      return el('li', {},
        el('p', {}, `${pageMap.get(gap.page_id) || gap.page_id || '整稿'} · ${layerNames[gap.layer] || gap.layer || '整稿'} · ${rule ? rule.label : '暂无法自动处理'}`),
        el('p', {class: 'muted'}, rule ? rule.next : '保留原始原因与范围，查看证据或交给制作工具核查后处理；这里不猜测修复动作。'),
        !rule && el('p', {class: 'muted'}, `原始原因：${gap.reason || '未记录'}${gap.dimension ? ` · ${gap.dimension}` : ''}`),
        toolchainLayers.has(gap.layer) ? el('p', {class: 'muted'}, '这一步由制作工具链完成（编译与渲染），网页不会代替执行；缺工具时按任务与交付里的工具说明恢复环境后重新编译。') : null,
        actions, !rule && el('details', {}, el('summary', {}, '原始缺项记录'), el('code', {}, JSON.stringify(gap))));
    })));
    if (gaps.length > count) node.append(button(`继续查看缺项（还有 ${gaps.length - count} 项）`, () => { count += 30; render(); }));
  }
  render(); return node;
}

function exportFiles(record) {
  const archive = record.files[record.archive];
  const node = el('section', {class: 'export-result stack'}, el('h3', {}, `${names[record.purpose]} · ${version(record.revision_id)}`),
    el('p', {}, record.archive), el('a', {class: 'download-link', href: exportURL(record, record.archive), download: record.archive}, '下载 ZIP'),
    el('p', {class: 'muted hash-line'}, `ZIP SHA256 ${archive.sha256}`),
    el('p', {class: 'muted'}, '文件已生成。下载由浏览器完成；中断后可继续使用同一链接。'));
  const details = el('details', {}, el('summary', {}, `查看文件与哈希（${record.manifest.files.length} 项）`));
  let shown = 0; const list = el('ul', {class: 'export-file-list'}); const more = button('继续显示文件', append);
  function append() {
    for (const item of record.manifest.files.slice(shown, shown + 30)) list.append(el('li', {},
      el('a', {href: exportURL(record, item.path), download: item.path.split('/').at(-1)}, item.path),
      el('small', {class: 'hash-line'}, item.sha256)));
    shown += 30; more.hidden = shown >= record.manifest.files.length;
  }
  details.append(list, more); details.addEventListener('toggle', () => { if (details.open && !shown) append(); }); node.append(details); return node;
}

export function deliveryDesk(app) {
  const revision = app.route.revision, key = `deck-master:v3:exports:${app.info.project_identity}`;
  const status = el('p', {role: 'status'}), results = el('div', {class: 'stack export-results'}), facts = el('div', {class: 'stack'});
  let disposed = false; app.disposables.push(() => { disposed = true; });
  // UX-05b：文件区按「版本—用途—结果」组织：版本先固定，正式用途（交付/审阅）
  // 在先，工程恢复包退到辅助位置；生成结果按同一用途与版本列出。
  const purposeCard = (purpose, primary) => el('article', {class: 'export-purpose stack'},
    el('h3', {}, names[purpose]), el('p', {}, descriptions[purpose]),
    button('生成' + names[purpose], event => create(purpose, event.currentTarget), primary, {disabled: Boolean(app.info.sample?.readonly)}));
  const node = panel('版本与文件', el('p', {class: 'export-version'}, `本次文件固定为 ${version(revision)}。后台新结果不会改变已经生成的包。`),
    el('section', {class: 'export-group stack'}, el('h3', {class: 'export-group-title'}, '正式用途（按此版本生成）'),
      el('div', {class: 'export-purpose-grid'}, purposeCard('delivery', true), purposeCard('review', false))),
    el('details', {class: 'export-group export-recovery'}, el('summary', {}, '工程恢复包（辅助，仅在需要恢复或交付内部材料时使用）'),
      el('div', {class: 'stack'}, purposeCard('engineering', false))),
    app.info.sample?.readonly && el('p', {class: 'muted'}, '只读示例不生成文件包。请在自己的项目操作。'), status,
    el('h3', {class: 'export-group-title'}, '生成结果'), results);
  node.id = 'delivery-desk'; node.querySelector('h2').tabIndex = -1;
  function read() {
    const value = JSON.parse(localStorage.getItem(key) || '[]');
    if (!Array.isArray(value) || value.some(v => !/^export-[a-f0-9-]{36}$/.test(v.export_id) || !names[v.purpose] || !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(v.revision)))
      throw new Error('浏览器中的导出记录暂不可读，请保留现有记录。');
    return value;
  }
  function remember(request) {
    const saved = read().filter(v => v.export_id !== request.export_id); saved.unshift(request);
    localStorage.setItem(key, JSON.stringify(saved.slice(0, 20)));
  }
  function pending(request, note) {
    const row = el('section', {class: 'export-result stack'}, el('h3', {}, `${names[request.purpose]} · ${version(request.revision)}`), el('p', {role: 'status'}, note));
    const verify = button('核实这个文件包', async () => {
      verify.disabled = true;
      try { const record = await get('/api/exports/' + request.export_id); if (!disposed) row.replaceWith(exportFiles(record)); }
      catch (error) {
        if (!disposed) row.append(el('p', {class: 'field-error'}, readableError(error)),
          error.code === 'export_not_found' && button('按原版本重试生成', () => generate(request, row)));
      } finally { verify.disabled = false; }
    });
    row.append(verify); return row;
  }
  async function generate(request, row) {
    if (!disposed) { row.replaceChildren(el('p', {role: 'status'}, `正在生成${names[request.purpose]} · ${version(request.revision)}，读取位置保持不变。`)); }
    try {
      const record = await post('/api/exports', request);
      if (!disposed) row.replaceWith(exportFiles(record));
    } catch (error) {
      if (disposed) return;
      if (!error.status || error.status >= 500 || error.code === 'invalid_response') row.replaceWith(pending(request, '生成结果待核实；原版本、用途与编号已保留，勿改成当前新版本重试。'));
      else row.replaceChildren(el('h3', {}, `${names[request.purpose]}未生成 · ${version(request.revision)}`),
        el('p', {class: 'field-error', role: 'alert'}, readableError(error)), gapsView(app, error.details?.gaps, request.revision));
    }
  }
  async function create(purpose, trigger) {
    if (trigger.disabled) return; trigger.disabled = true;
    status.textContent = '';
    const request = {purpose, revision, export_id: 'export-' + crypto.randomUUID()};
    try { remember(request); }
    catch (error) { status.textContent = readableError(error) + ' 尚未发送生成请求。'; trigger.disabled = false; return; }
    const row = el('section', {class: 'export-result'}); results.prepend(row); try { await generate(request, row); } finally { trigger.disabled = Boolean(app.info.sample?.readonly); }
  }
  try {
    const saved = read();
    for (const request of saved.slice(0, 6)) results.append(pending(request, '已保存导出请求，可核实并重新取得同一版本的文件。'));
  } catch (error) { status.textContent = readableError(error); }
  const detail = el('details', {class: 'export-facts'}, el('summary', {}, '查看此版本的交付缺项与制作证据'), facts); let loaded = false;
  async function loadFacts() {
    if (loaded) return; loaded = true; facts.replaceChildren(el('p', {role: 'status'}, '正在读取固定版本的检查记录。'));
    try {
      const value = await get('/api/export-facts' + revisionQuery(revision)); if (disposed) return;
      facts.replaceChildren(el('p', {}, `工程检查：${{pass: '记录为通过', fail: '存在未通过项', needs_review: '待判断', not_evaluated: '未完成评估'}[value.check_summary.status] || '未知'}。输入：${value.input_alignment === 'needs_reconciliation' ? '待协调' : '按此快照记录'}。`),
        gapsView(app, value.gaps, revision));
      if (value.production.length) {
        const choice = el('select', {'aria-label': '制作证据页'}, value.production.map((p, i) => el('option', {value: String(i)}, `${i + 1}. ${app.summary.pages[i]?.title || p.page_id}`)));
        const evidence = el('div'); const show = () => evidence.replaceChildren(productionView({production: value.production[Number(choice.value)]}));
        choice.addEventListener('change', show); show(); facts.append(el('label', {}, '逐页制作与可编辑性记录', choice), evidence);
      }
      facts.append(el('p', {class: 'muted'}, '工程检查、可编辑声明、专业评估和桌面编辑分别记录。没有实际证据的项目保持未评估。'));
    } catch (error) { loaded = false; if (!disposed) facts.replaceChildren(el('p', {class: 'field-error'}, readableError(error)), button('重读交付缺项', loadFacts)); }
  }
  detail.addEventListener('toggle', () => { if (detail.open) loadFacts(); }); node.append(detail); return node;
}

export function historyDesk(app, history) {
  const revision = app.route.revision;
  const pageLabels = new Map(app.summary.pages.map((page, index) => [page.page_id, `第 ${index + 1} 页`]));
  const selected = el('select', {'aria-label': '阅读历史版本'});
  const allRecords = el('input', {type: 'checkbox', 'aria-label': '显示全部历史记录'});
  const notice = el('p', {role: 'status'});
  let cursor = history.pagination?.next_cursor || null, disposed = false, serial = 0, busy = false, showingAll = false;
  const rows = new Map();
  const restore = button('预览恢复此版本', preview, false, {disabled: !app.historical || Boolean(app.info.sample?.readonly)});
  const more = button('更早的修改', () => load(false), false, {disabled: !cursor});
  // UX-05b：版本区把三个身份分开说清（对账 AC17 的选 A/读 B/当前 C）：
  // 选中＝下一步操作的目标，已读＝正在查看的版本，当前版本＝项目最新记录。
  const identity = el('p', {class: 'row wrap history-identity'});
  const nameFor = rev => {
    const record = rows.get(rev);
    if (record) return historyLabel(record, pageLabels);
    return rev === revision ? (app.historical ? '正在阅读的历史版本' : '当前项目版本') : version(rev);
  };
  function stateIdentity() {
    identity.replaceChildren(
      el('span', {class: 'state-chip'}, `选中：${nameFor(selected.value)}`),
      el('span', {class: 'state-chip'}, `已读：${nameFor(revision)}`),
      el('span', {class: 'state-chip'}, `当前版本：${nameFor(history.current)}`));
  }
  function append(records, reset = false) {
    const chosen = reset ? revision : selected.value;
    if (reset) rows.clear();
    records.forEach(item => rows.set(item.revision_id, item));
    const options = [...rows.values()].map(item => el('option', {value: item.revision_id}, historyLabel(item, pageLabels) + (item.revision_id === history.current ? ' · 当前阅读版本' : '')));
    if (!rows.has(revision)) options.unshift(el('option', {value: revision}, app.historical ? '正在阅读的历史版本' : '当前项目版本'));
    selected.replaceChildren(...options); selected.value = chosen;
    if (!selected.value) selected.value = revision;
    restore.disabled = selected.value !== revision || !app.historical || Boolean(app.info.sample?.readonly);
    stateIdentity();
  }
  selected.addEventListener('change', () => { restore.disabled = selected.value !== revision || !app.historical || Boolean(app.info.sample?.readonly); stateIdentity(); });
  allRecords.addEventListener('change', () => load(true));
  async function load(reset) {
    if (busy || disposed) { allRecords.checked = showingAll; return; }
    const requestedAll = allRecords.checked, token = ++serial;
    const query = new URLSearchParams({revision, limit: 20, related_only: requestedAll ? '0' : '1'});
    if (!reset && cursor) query.set('cursor', cursor);
    busy = true; more.disabled = true; allRecords.disabled = true;
    notice.textContent = '正在读取版本记录；已有选择与比较保持固定。';
    try {
      const value = await get('/api/history?' + query);
      if (disposed || token !== serial) return;
      append(value.revisions, reset); cursor = value.pagination?.next_cursor || null; showingAll = requestedAll;
      notice.textContent = showingAll ? '已显示全部类型的记录；任务和个人状态记录也会列出。' : '优先显示正文、产物和页面顺序的修改。';
    } catch (error) {
      if (!disposed && token === serial) { allRecords.checked = showingAll; notice.textContent = readableError(error) + ' 已加载的版本仍保留。'; }
    } finally { if (!disposed && token === serial) { busy = false; more.disabled = !cursor; allRecords.disabled = false; } }
  }
  append(history.revisions, true);
  const node = panel('版本记录', identity, el('div', {class: 'row wrap history-reading-controls'}, selected,
    button('读取所选版本', () => app.go({revision: selected.value, task_id: null})), more,
    app.summary.pages.length > 0 && button('逐页查看与固定比较', () => app.go({surface: 'page', page_id: app.summary.pages[0].page_id, layer: 'content', revision})), restore),
    el('label', {class: 'inline-control'}, allRecords, '全部记录（包括执行与个人状态）'), notice,
    el('p', {class: 'muted'}, '先读取历史版本并查看差异，再预览恢复影响。恢复会创建新版本，当前执行与调用记录不会回滚。'));
  app.disposables.push(() => { disposed = true; serial++; });
  async function preview() {
    restore.disabled = true;
    try {
      await app.business.available();
      const current = await get('/api/view/summary');
      const planned = await post('/api/history/plan-restore', {revision_id: revision, base_revision: current.revision_id});
      const impact = planned.plan.impact;
      const editor = new DraftEditor(app.info, {scope: 'project', page_id: null, layer: 'notes'}, current.revision_id, planned.plan_ref, {exactRevision: true});
      const draft = editor.mount(); draft.querySelector('h2').textContent = '恢复请求的个人副本';
      editor.input.id = 'restore-draft-' + crypto.randomUUID(); editor.input.setAttribute('aria-label', '恢复请求个人备注');
      draft.querySelector('label[for]').htmlFor = editor.input.id;
      const status = el('p', {role: 'status'});
      const body = el('div', {class: 'stack restore-impact'},
        el('div', {class: 'conflict-panes'}, el('section', {}, el('h3', {}, '来源版本'), el('p', {}, version(revision))), el('section', {}, el('h3', {}, '当前基准'), el('p', {}, version(current.revision_id)))),
        el('p', {}, `恢复后 ${impact.page_order.length} 页；替换或恢复 ${impact.changed_pages.length} 页，移除 ${impact.removed_pages.length} 页。`),
        el('p', {}, `${impact.outputs_changed ? '整稿输出将换为来源版本的记录。' : '整稿输出记录相同。'} ${impact.superseded_tasks.length} 项待办或运行任务将失效，晚到结果不能覆盖恢复后的稿件。`),
        el('p', {}, '保留当前任务要求、政策、已发生调用、取消记录和用户停止状态；恢复本身不调用模型。'),
        impact.input_alignment_after === 'needs_reconciliation' && el('p', {class: 'field-error'}, '恢复内容与当前要求不同，恢复后仍需协调输入，不能直接正式交付。'),
        el('details', {}, el('summary', {}, '查看具体页与任务'), el('pre', {class: 'evidence-json'}, JSON.stringify({changed_pages: impact.changed_pages, removed_pages: impact.removed_pages, superseded_tasks: impact.superseded_tasks}, null, 2))),
        el('details', {}, el('summary', {}, '恢复请求与草稿保护'), draft), status);
      const confirm = button('确认恢复并创建新版本', async () => {
        confirm.disabled = true; status.textContent = '正在保存可恢复的原请求。';
        try {
          await editor.ready;
          if (!editor.input.value) editor.input.value = `将 ${version(revision)} 的内容恢复到 ${version(current.revision_id)} 之后的新版本；保留执行与停止事实。`; editor.changed();
          await app.business.submit(editor, 'history.restore', {plan_id: planned.plan_id, base_revision: current.revision_id}, {plan_id: planned.plan_id, plan: planned.plan}, result => {
            dialog.close(); app.go({surface: 'runs', revision: result.revision_id, task_id: null});
          });
          status.textContent = app.business.entries.size ? '结果待核实；原请求已保留，可关闭后在顶部核实。' : '请求已处理；若基准变化，请先比较后重新预览。';
        } catch (error) { status.textContent = readableError(error); }
        finally { confirm.disabled = false; }
      }, true);
      const dialog = modal('确认历史恢复影响', body, [button('取消恢复', () => dialog.close()), confirm]);
      dialog.addEventListener('close', () => editor.dispose(), {once: true}); app.disposables.push(() => editor.dispose());
    } catch (error) { modal('暂不能预览恢复', el('p', {class: 'field-error'}, readableError(error))); }
    finally { restore.disabled = !app.historical || Boolean(app.info.sample?.readonly); }
  }
  return node;
}
