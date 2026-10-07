import {SummaryPoll} from './summary-poll.js';
import {get, post, revisionQuery, readableError} from './api.js';
import {el, button, heading, empty, icon, version, announce, modal} from './dom.js';
import {localURL} from './launcher-ui.js';
import {readRoute, routeHash, position, surfaces, layers} from './routes.js';
import {DraftEditor} from './drafts.js';
import {overview, content, pageDetail, runs, style} from './views.js';
import {gallery} from './gallery.js';
import {BusinessOperations} from './business-operations.js';
import {actionTargets} from './action-targets.js';
import {changesetDesk} from './changeset-desk.js';

export class Project {
  constructor(root, health) { this.root = root; this.health = health; this.generation = 0; this.positionQueue = Promise.resolve(); this.disposables = []; }
  summaryURL(revision=null){const q=new URLSearchParams();if(revision)q.set('revision',revision);if(this.health.ui_capabilities?.includes('result_reading.v1'))q.set('personal','1');return '/api/view/summary'+(q.size?'?'+q:'');}
  // Bind lists to the supplied projection. A fallback summary without an etag
  // must not inherit the previous work surface's personal-reading snapshot.
  readingQuery(summary=this.summary){const etag=summary?.reading_etag;return this.health.ui_capabilities?.includes('result_reading.v1')&&etag?'&'+new URLSearchParams({personal:'1',reading_etag:etag}):'';}
  async start() {
    const [info, summary, state] = await Promise.all([get('/api/project'), get(this.summaryURL()), get('/api/ui-state')]);
    this.info = info; this.latest = summary; this.returnTo = state.record?.position;
    if (this.health.ui_capabilities?.includes('operations.v1')) this.business = new BusinessOperations(this);
    this.root.addEventListener('draft-state-changed', () => {
      const editor = this.editor;
      if (editor && this.business) this.business.ready.then(() => this.business.observe(editor));
    });
    this.route = readRoute(info, this.returnTo, summary);
    addEventListener('hashchange', () => this.loadRoute());
    this.root.addEventListener('draft-restore-local', event => {
      const previous = this.editor;
      try {
        localStorage.setItem(previous.activeKey, JSON.stringify(event.detail));
        const editor = new DraftEditor(previous.info, previous.target, previous.baseRevision, previous.baseRef, {readonly: previous.readonly, exactRevision: previous.exactRevision});
        const section = event.target.closest('.personal-draft');
        this.editor = editor; section.replaceWith(editor.mount());
        this.root.dispatchEvent(new CustomEvent('draft-editor-replaced', {detail: editor}));
      } catch {
        this.setNotice('本机缓冲不可用，请先下载恢复文件。'); previous.disposed = false;
      }
    });
    this.root.addEventListener('business-committed', event => {
      if (event.detail.action !== 'history.restore') return;
      const revision = event.detail.result.revision_id;
      this.setNotice(`历史恢复已确认，已创建 ${version(revision)}。当前阅读位置保持不变。`);
      this.notice?.append(button('查看恢复后的版本', () => this.go({surface: 'runs', revision, task_id: null, runs_area: 'versions'})));
    });
    addEventListener('beforeunload', () => this.editor?.persist());
    addEventListener('online', () => this.setNotice('网络已恢复。可核实草稿保存，或重新读取当前工作面。'));
    await this.loadRoute(this.route, false);
    if (this.health.ui_capabilities?.includes('run_desk.v1')) {
      this.summaryPoll = new SummaryPoll(signal => get(this.summaryURL(), {signal}), value => {
        if (value.project_id !== this.info.project_id) throw new Error('服务项目已变化，请重新打开项目。');
        this.latest = value;
        const count = value.task_counts.awaiting_host || 0;
        if (this.pendingButton) {
          this.pendingButton.textContent = `待交接 ${count}`;
          this.pendingButton.setAttribute('aria-label', `查看待交接任务，${count} 项`);
        }
        this.syncState(value.revision_id !== this.route.revision ? '项目有新状态。当前页面仍按顶栏版本阅读。' : '');
        this.root.dispatchEvent(new CustomEvent('summary-refreshed', {detail: value}));
      }, error => this.syncState('运行状态同步中断。' + readableError(error) + ' 固定阅读与草稿仍保留。'), this.latest);
      this.summaryPoll.start();
      this.root.addEventListener('business-state-changed', () => this.summaryPoll.refresh());
      addEventListener('pagehide', () => this.summaryPoll.stop());
      addEventListener('pageshow', event => { if (event.persisted) { this.summaryPoll.start(); this.summaryPoll.refresh(); } });
    }
  }
  async loadRoute(initial = null, focus = true) {
    const serial = ++this.generation;
    try {
      const [info, latest] = await Promise.all([get('/api/project'), get(this.summaryURL())]);
      if (info.project_identity !== this.info.project_identity) throw new Error('项目身份已改变。旧输入仍保留，请从项目列表重新打开。');
      const route = initial || readRoute(this.info, null, latest);
      route.revision ||= latest.revision_id;
      const summary = route.revision === latest.revision_id ? latest : await get(this.summaryURL(route.revision));
      if (summary.project_id !== this.info.project_id) throw new Error('服务中的项目与当前窗口不一致，未替换已读内容。');
      const q = revisionQuery(summary.revision_id);
      let data = {};
      if (route.action_id) data = await get('/api/actions/' + encodeURIComponent(route.action_id) + '/targets' + q + this.readingQuery(summary));
      else if (route.surface === 'overview' && this.health.ui_capabilities?.includes('ui_overview.v1')) {
        try { data = {overview:await get('/api/overview' + q)}; }
        catch (error) { data = {overview:{error}}; }
      }
      else if (route.surface === 'page') data = await get('/api/pages/' + encodeURIComponent(route.page_id) + '/lineage' + q);
      else if (route.surface === 'content') {
        if (route.candidate_id) {
          data = await get('/api/candidates/' + encodeURIComponent(route.candidate_id) + q);
          if (data.result_kind !== 'content_update') throw new Error('这个候选不是整稿正文变更集，未替换为其它候选。');
        } else {
          const plan = await get('/api/content-plan' + q);
          data = {plan: plan.content_plan, inputs: route.revision === latest.revision_id ? await get('/api/inputs') : null};
          if (data.inputs && data.inputs.revision_id !== route.revision) data.inputs = null;
        }
      } else if (route.surface === 'gallery') {
        if (!this.health.ui_capabilities?.includes('ui_gallery.v1')) data = {unsupported: true};
        else {
          const [saved, plan, drafts] = await Promise.all([get('/api/gallery'), get('/api/content-plan' + q), get('/api/drafts')]);
          data = {saved, plan: plan.content_plan, drafts};
        }
      } else if (route.surface === 'runs') {
        const modern = this.health.ui_capabilities?.includes('run_desk.v1');
        const [tasks, history, detail] = await Promise.all([get('/api/tasks' + q + (modern ? '&limit=30'+this.readingQuery(summary) : '')), get('/api/history?' + new URLSearchParams({revision:summary.revision_id,limit:20})),
          modern && route.task_id ? get('/api/tasks/' + encodeURIComponent(route.task_id) + q) : Promise.resolve(null)]);
        data = {tasks: tasks.tasks, runPage: modern ? tasks : null, runDetail: detail, history};
        if (route.task_id && !(detail || tasks.tasks.some(task => task.task_id === route.task_id))) throw new Error('此版本没有链接中的任务。请检查任务与版本，未跳到其它任务。');
        if (route.review_id) {
          const result = await get('/api/reviews' + q);
          data.review = result.reviews.find(review => review.review_id === route.review_id);
          if (!data.review) throw new Error('此版本没有链接中的质量记录，未替换为其它记录。');
        }
      }
      if (serial !== this.generation) return;
      this.editor?.dispose(); this.editor = null;
      this.disposables.forEach(dispose => dispose()); this.disposables = [];
      this.info = info; this.latest = latest; this.summary = summary; this.route = route;
      this.historical = summary.revision_id !== latest.revision_id;
      this.readonly = this.historical || Boolean(info.sample?.readonly);
      history.replaceState(null, '', routeHash(this.info, route));
      this.render(data);
      if(summary.reading_unavailable)this.setNotice('个人已读记录暂不可用，已显示未过滤的业务记录；损伤文件保留，请先核实恢复资料。',true);
      this.savePosition();
      if (focus) document.querySelector('#view-title')?.focus();
      announce(`${route.surface === 'page' ? '单页 · ' + layers[route.layer] : surfaces[route.surface]}，${version(route.revision)}`);
    } catch (error) {
      if (serial !== this.generation) return;
      if (this.main) {this.setNotice(readableError(error) + ' 已显示的工作面仍属于顶栏标明的版本。', true);if(this.health.ui_capabilities?.includes('result_reading.v1'))this.notice?.append(button('重新读取待办',()=>this.go({surface:'overview',action_id:null})));}
      else {
        this.root.replaceChildren(el('main', {id: 'main', class: 'workspace'}, empty('无法读取这个位置', readableError(error),
          button('打开项目当前版本', () => { history.replaceState(null, '', location.pathname + location.search); this.loadRoute({...this.route, surface: 'overview', page_id: null, task_id: null, revision: null}); }))));
      }
    }
  }
  go(patch) {
    const route = {...this.route, ...patch};
    if (patch.surface && patch.surface !== 'overview' || patch.revision && patch.revision !== this.route.revision) route.overview_preferences = null;
    // A plain surface switch starts that surface on its own first screen: no task
    // detail from an earlier visit, and no page layer that another surface could
    // mistake for "the user asked for delivery".
    if (patch.surface && (!('task_id' in patch) || patch.surface !== 'runs')) route.task_id = null;
    if (patch.surface && patch.surface !== 'page' && !('layer' in patch)) route.layer = 'original_image';
    if (!('action_id' in patch) && (patch.surface || patch.page_id || patch.layer || patch.task_id)) route.action_id = null;
    if (!('review_id' in patch) && (patch.surface || patch.page_id || patch.layer || patch.task_id)) route.review_id = null;
    if (!('candidate_id' in patch) && (patch.surface || patch.page_id || patch.layer)) route.candidate_id = null;
    if (patch.surface && patch.surface !== 'page' && !('page_id' in patch)) route.page_id = null;
    // R4（深度复审）：显式打开某一项任务时落到「正在进行」；读取版本、面返回等
    // 只带 task_id: null 的导航保留记住的子区（链接里的 area）。
    if (patch.task_id && !('runs_area' in patch)) route.runs_area = 'tasks';
    const hash = routeHash(this.info, route);
    if (location.hash === hash) this.loadRoute(route); else location.hash = hash;
  }
  current() { this.loadRoute({...this.route, revision: null, overview_preferences: null, task_id: null, action_id: null, review_id: null, candidate_id: null}); }
  savePosition() {
    const saved = position(this.info, this.route);
    this.positionQueue = this.positionQueue.catch(() => {}).then(async () => {
      if (saved.revision !== this.route.revision || saved.surface !== this.route.surface || saved.page_id !== this.route.page_id || saved.layer !== this.route.layer || saved.zoom !== this.route.zoom || saved.task_id !== this.route.task_id) return;
      try { await post('/api/ui-state', {position: saved}); }
      catch (error) { this.setNotice('阅读位置尚未保存到项目。' + readableError(error)); }
    });
  }
  syncState(message) {
    if (!this.syncNotice || !this.syncRow) return;
    this.syncNotice.textContent = message; this.syncRow.hidden = !message;
  }
  setNotice(message, retry = false) {
    if (!this.notice) return;
    this.notice.replaceChildren(el('span', {}, message)); this.notice.hidden = !message;
    if (retry) this.notice.append(button('重试读取', () => this.loadRoute()));
  }
  connectionInfo() {
    // 连接面板按真实事实显示（DESIGN-ADAPTATION）：分开服务可达、当前项目可做动作、
    // 制作工具实际接手与导出真实可用性；云端同步当前不提供。
    // 历史视图的 fixed_revision 由前端按路由组合，服务端不产生该原因。
    const reasons = {sample_readonly: '只读示例，请新建自己的项目后编辑。',
      unsupported_project_format: '旧格式项目，该动作需要 workbench.v3 项目。',
      reader_upgrade_required: '项目指针需要更新的核心读取，请用匹配的核心打开。',
      writer_upgrade_required: '项目由更新的核心写入，请用匹配的核心继续。',
      fixed_revision: '正在看历史版本，只读；回到当前版本后可操作。'};
    const actions = (this.info.effective_actions || []).map(item => {
      // 历史视图的 fixed_revision 组合：个人草稿与按固定版本导出不受影响——
      // 交付面在同一路由真实提供按该历史版本固定的导出（服务端按 revision 生成）。
      const fixed = this.historical && item.writable && !['drafts', 'exports'].includes(item.action);
      return {action: item.action, supported: item.supported,
        writable: fixed ? false : item.writable, reason: fixed ? 'fixed_revision' : item.reason_code};
    });
    const blocked = actions.filter(item => !item.writable);
    const writable = actions.filter(item => item.writable);
    const fact = (term, value) => el('div', {}, el('dt', {}, term), el('dd', {}, value));
    const exportsAction = actions.find(item => item.action === 'exports');
    modal('连接状态', el('div', {class: 'stack'},
      el('p', {}, '本机工作区，项目数据仅保存在这台电脑。服务可达不等于制作工具已接手；生成任务仍需复制制作要求后交接。'),
      el('dl', {class: 'request-facts stack'},
        fact('本机服务', `已连接 · ${this.health.service_version || '本机核心'}`),
        fact('当前项目动作', writable.length ? `${writable.length} 项可用（${writable.map(item => actionLabels[item.action] || item.action).join('、')}）` : '没有可写动作'),
        fact('制作工具', '需交接 · 复制制作要求后到制作工具执行，不会自动开始'),
        fact('文件导出', exportsAction && exportsAction.writable
          ? (this.historical ? '可用（按正在阅读的历史版本固定导出）' : '可用（按当前版本固定导出）')
          : `不可用 · ${exportsAction && !exportsAction.supported ? '该核心未提供此能力' : (reasons[exportsAction?.reason] || exportsAction?.reason || '')}`),
        fact('云端同步', '不提供')),
      blocked.length > 0 && el('details', {}, el('summary', {}, `受限动作 ${blocked.length} 项`),
        el('div', {class: 'stack'}, blocked.map(item => el('p', {class: 'muted'},
          `${actionLabels[item.action] || item.action}：${item.supported ? (reasons[item.reason] || item.reason || '该核心未提供此能力') : '该核心未提供此能力'}`)))),
      el('p', {class: 'muted'}, '能力为当前核心与项目的实时投影；写操作仍由服务端独立校验。')));
  }
  render(data) {
    const nav = el('nav', {class: 'nav', 'aria-label': '项目工作区'});
    for (const [key, label] of Object.entries(surfaces)) nav.append(button([icon(key), el('span', {class: 'nav-label'}, label)], () => this.go({surface: key}), false,
      {class: (this.route.surface === key || this.route.surface === 'page' && key === 'gallery') ? 'active' : '',
        'aria-current': (this.route.surface === key || this.route.surface === 'page' && key === 'gallery') ? 'page' : null, title: label}));
    const launcher = localURL(new URLSearchParams(location.search).get('launcher'));
    const aside = el('aside', {class: 'sidebar'}, el('div', {class: 'logo'}, el('img', {class: 'brand-logo', src: '/v2/assets/deck-master-logo/logo-horizontal-light.svg', alt: 'Deck Master', width: 176, height: 46})),
      nav, el('div', {class: 'side-project'}, el('span', {class: 'muted'}, '当前项目'), el('strong', {}, this.info.title),
        this.info.sample && el('span', {class: 'status'}, infoSampleLabel(this.info))),
      el('div', {class: 'sidebar-footer stack'}, launcher ? el('a', {href: launcher.href}, '返回项目列表') : el('p', {class: 'muted'}, '当前为项目独立入口'),
        button('连接状态', () => this.connectionInfo(), false, {class: 'text-link'})));
    this.notice = el('div', {class: 'notice', role: 'status', hidden: true});
    const banners = el('div', {class: 'banners'}, this.notice);
    if (this.business) banners.append(this.business.node);
    this.syncNotice = el('p', {class: 'runtime-sync muted', role: 'status'});
    this.syncRow = el('div', {class: 'runtime-sync-row', hidden: true}, this.syncNotice, button('读取项目最新状态', () => this.current()));
    if (this.health.ui_capabilities?.includes('run_desk.v1')) banners.append(this.syncRow);
    if (this.historical) banners.append(el('div', {class: 'history-banner'}, el('strong', {}, '历史版本 · 只读'),
      el('span', {}, '你正在阅读过去保存的稿件；内容与比较保持固定。'), button('查看当前版本', () => this.current()), el('details', {}, el('summary', {}, '版本身份'), el('p', {}, `阅读 ${version(this.route.revision)} · 当前 ${version(this.latest.revision_id)}`))));
    if (this.info.sample) banners.append(el('div', {class: 'sample-banner'}, this.info.sample.readonly ? '这是合成的只读示例，未调用模型，也未进行专业质量验收。' : '这是可编辑的合成验证项目，未调用模型，也未进行专业质量验收。'));
    this.main = el('main', {id: 'main', class: 'workspace', tabindex: '-1'});
    const view = this.route.action_id ? actionTargets : this.route.surface === 'content' && this.route.candidate_id ? changesetDesk :
      {overview, content, gallery, page: pageDetail, runs, style}[this.route.surface];
    this.main.append(view(this, data));
    if (this.route.surface === 'page') this.main.addEventListener('keydown', event => {
      const typing = event.target.closest('textarea,input,select,button,a,summary,[contenteditable]');
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || document.querySelector('dialog[open]')) return;
      // An element in fullscreen consumes Escape to leave fullscreen: the same
      // keypress must not also navigate the work surface away.
      if (event.key === 'Escape' && !typing && !document.fullscreenElement) { event.preventDefault(); this.go({surface: 'gallery'}); return; }
      // ←/→ 切换页（输入与可滚动阅读区除外），与单页制作链的上一页/下一页一致。
      if ((event.key === 'ArrowLeft' || event.key === 'ArrowRight') && !typing && !event.target.closest('.page-image-viewport,.icon-crop-scroll,.selectable-text,.evidence-json,.diff-lines')) {
        const index = this.summary.pages.findIndex(p => p.page_id === this.route.page_id);
        const next = this.summary.pages[index + (event.key === 'ArrowRight' ? 1 : -1)];
        if (next) { event.preventDefault(); this.go({page_id: next.page_id}); }
      }
    });
    const pending = this.summary.task_counts.awaiting_host || 0;
    // 顶栏入口承诺的是"查看待交接任务"：显式落到「正在进行」，不被记住的子区劫持。
    this.pendingButton = button(`待交接 ${pending}`, () => this.go({surface: 'runs', task_id: null, runs_area: 'tasks'}), false, {'aria-label': `查看待交接任务，${pending} 项`});
    const top = el('header', {class: 'topbar'}, el('div', {class: 'crumb'}, el('strong', {}, this.info.title), el('span', {class: 'version', title: '版本身份可在任务与交付的版本记录中查看'}, this.historical ? '历史稿' : '当前稿')),
      this.pendingButton);
    this.root.className = 'shell';
    this.root.replaceChildren(aside, el('div', {class: 'content'}, top, banners, this.main));
  }
  async handoff(expectedTaskId = null) {
    try {
      const handoff = await get('/api/compose/handoff');
      if (handoff.status === 'no_pending_compose') {
        modal('尚无待交接的内容整理', el('p', {}, '现有项目没有可交接的内容整理任务。可到任务与交付查看已记录的状态。')); return;
      }
      if (expectedTaskId && expectedTaskId !== handoff.task_id) {
        modal('内容整理任务已更新', el('p', {}, '这项任务已由新任务接续。请先查看当前任务，再决定是否交接。'), [button('查看当前任务', () => { document.querySelector('#modal').close(); this.go({surface: 'runs', revision: handoff.revision_id, task_id: handoff.task_id}); })]);
        return;
      }
      const status = handoff.status === 'running' ? '制作工具已记录处理中，请先核实原任务，避免重复执行。' : '待交接 · 尚未开始。将下面的说明复制到 Codex 后发送。';
      const text = el('textarea', {'aria-label': '交接说明', readOnly: true, value: handoff.handoff, rows: 7});
      const note = el('p', {role: 'status'}, status);
      modal('交给 Deck Master Agent', el('div', {class: 'stack'}, note, el('details', {}, el('summary', {}, '完整交接说明与任务身份'), el('p', {class: 'muted'}, `任务 ${handoff.task_id} · ${version(handoff.revision_id)}`), text)),
        [button('复制给 Deck Master Agent', async () => {
          try { await navigator.clipboard.writeText(handoff.handoff); note.textContent = '交接说明已复制 · 待接手。请在 Codex 中发送；复制不会开始制作。'; }
          catch { note.textContent = '自动复制未完成；请打开完整交接说明后选中复制。任务仍待接手。'; text.closest('details').open = true; text.focus(); text.select(); }
        }, true)]);
    } catch (error) { this.setNotice(readableError(error)); }
  }
}

function infoSampleLabel(info) { return info.sample.readonly ? '合成示例 · 只读' : '合成验证项目'; }
const actionLabels = {drafts: '个人草稿', annotations: '标注与意见', changes: '修改任务', candidates: '候选采用',
  content: '内容与结构', inputs: '输入更新', styles: '风格校准', run_desk: '任务操作', exports: '文件导出', restoration: '历史恢复'};
