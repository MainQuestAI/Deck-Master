import {get, post, revisionQuery, readableError} from './api.js';
import {el, button, heading, empty, icon, version, announce, modal, copyText} from './dom.js';
import {localURL} from './launcher-ui.js';
import {readRoute, routeHash, position, surfaces, layers} from './routes.js';
import {DraftEditor} from './drafts.js';
import {overview, content, gallery, pageDetail, runs, style} from './views.js';

export class Project {
  constructor(root, health) { this.root = root; this.health = health; this.generation = 0; this.positionQueue = Promise.resolve(); }
  async start() {
    const [info, summary, state] = await Promise.all([get('/api/project'), get('/api/view/summary'), get('/api/ui-state')]);
    this.info = info; this.latest = summary; this.returnTo = state.record?.position;
    this.route = readRoute(info, this.returnTo, summary);
    addEventListener('hashchange', () => this.loadRoute());
    this.root.addEventListener('draft-restore-local', event => {
      const previous = this.editor;
      try {
        localStorage.setItem(previous.activeKey, JSON.stringify(event.detail));
        const editor = new DraftEditor(previous.info, previous.target, previous.baseRevision, previous.baseRef, {readonly: this.readonly});
        const section = event.target.closest('.personal-draft');
        this.editor = editor; section.replaceWith(editor.mount());
      } catch {
        this.setNotice('本机缓冲不可用，请先下载恢复文件。'); previous.disposed = false;
      }
    });
    addEventListener('beforeunload', () => this.editor?.persist());
    addEventListener('online', () => this.setNotice('网络已恢复。可核实草稿保存，或重新读取当前工作面。'));
    await this.loadRoute(this.route, false);
  }
  async loadRoute(initial = null, focus = true) {
    const serial = ++this.generation;
    try {
      const [info, latest] = await Promise.all([get('/api/project'), get('/api/view/summary')]);
      if (info.project_identity !== this.info.project_identity) throw new Error('项目身份已改变。旧输入仍保留，请从项目列表重新打开。');
      const route = initial || readRoute(this.info, null, latest);
      route.revision ||= latest.revision_id;
      const summary = route.revision === latest.revision_id ? latest : await get('/api/view/summary' + revisionQuery(route.revision));
      if (summary.project_id !== this.info.project_id) throw new Error('服务中的项目与当前窗口不一致，未替换已读内容。');
      const q = revisionQuery(summary.revision_id);
      let data = {};
      if (route.surface === 'page') data = await get('/api/pages/' + encodeURIComponent(route.page_id) + '/lineage' + q);
      else if (route.surface === 'content') {
        const plan = await get('/api/content-plan' + q);
        data = {plan: plan.content_plan, inputs: route.revision === latest.revision_id ? await get('/api/inputs') : null};
        if (data.inputs && data.inputs.revision_id !== route.revision) data.inputs = null;
      } else if (route.surface === 'runs') {
        const [tasks, history] = await Promise.all([get('/api/tasks' + q), get('/api/history')]);
        data = {tasks: tasks.tasks, history};
        if (route.task_id && !tasks.tasks.some(task => task.task_id === route.task_id)) throw new Error('此版本没有链接中的任务。请检查任务与版本，未跳到其它任务。');
      }
      if (serial !== this.generation) return;
      this.editor?.dispose(); this.editor = null;
      this.info = info; this.latest = latest; this.summary = summary; this.route = route;
      this.historical = summary.revision_id !== latest.revision_id;
      this.readonly = this.historical || Boolean(info.sample?.readonly);
      history.replaceState(null, '', routeHash(this.info, route));
      this.render(data);
      this.savePosition();
      if (focus) document.querySelector('#view-title')?.focus();
      announce(`${route.surface === 'page' ? '单页 · ' + layers[route.layer] : surfaces[route.surface]}，${version(route.revision)}`);
    } catch (error) {
      if (serial !== this.generation) return;
      if (this.main) this.setNotice(readableError(error) + ' 已显示的工作面仍属于顶栏标明的版本。', true);
      else {
        this.root.replaceChildren(el('main', {id: 'main', class: 'workspace'}, empty('无法读取这个位置', readableError(error),
          button('打开项目当前版本', () => { history.replaceState(null, '', location.pathname + location.search); this.loadRoute({...this.route, surface: 'overview', page_id: null, task_id: null, revision: null}); }))));
      }
    }
  }
  go(patch) {
    const route = {...this.route, ...patch};
    if (patch.surface && patch.surface !== 'runs') route.task_id = null;
    if (patch.surface && patch.surface !== 'page' && !('page_id' in patch)) route.page_id = null;
    const hash = routeHash(this.info, route);
    if (location.hash === hash) this.loadRoute(route); else location.hash = hash;
  }
  current() { this.go({revision: this.latest.revision_id, task_id: null}); }
  savePosition() {
    const saved = position(this.info, this.route);
    this.positionQueue = this.positionQueue.catch(() => {}).then(async () => {
      if (saved.revision !== this.route.revision || saved.surface !== this.route.surface || saved.page_id !== this.route.page_id || saved.layer !== this.route.layer || saved.zoom !== this.route.zoom || saved.task_id !== this.route.task_id) return;
      try { await post('/api/ui-state', {position: saved}); }
      catch (error) { this.setNotice('阅读位置尚未保存到项目。' + readableError(error)); }
    });
  }
  setNotice(message, retry = false) {
    if (!this.notice) return;
    this.notice.replaceChildren(el('span', {}, message)); this.notice.hidden = !message;
    if (retry) this.notice.append(button('重试读取', () => this.loadRoute()));
  }
  render(data) {
    const nav = el('nav', {class: 'nav', 'aria-label': '项目工作区'});
    for (const [key, label] of Object.entries(surfaces)) nav.append(button([icon(key), el('span', {class: 'nav-label'}, label)], () => this.go({surface: key}), false,
      {class: (this.route.surface === key || this.route.surface === 'page' && key === 'gallery') ? 'active' : '',
        'aria-current': (this.route.surface === key || this.route.surface === 'page' && key === 'gallery') ? 'page' : null, title: label}));
    const launcher = localURL(new URLSearchParams(location.search).get('launcher'));
    const aside = el('aside', {class: 'sidebar'}, el('div', {class: 'logo'}, el('span', {class: 'mark', 'aria-hidden': true}, 'D'), el('span', {class: 'brand-name'}, 'Deck Master')),
      nav, el('div', {class: 'side-project'}, el('span', {class: 'muted'}, '当前项目'), el('strong', {}, this.info.title),
        this.info.sample && el('span', {class: 'status'}, infoSampleLabel(this.info))),
      el('div', {class: 'sidebar-footer stack'}, launcher ? el('a', {href: launcher.href}, '返回项目列表') : el('p', {class: 'muted'}, '当前为项目独立入口'),
        el('a', {href: '/'}, '原有工作区')));
    this.notice = el('div', {class: 'notice', role: 'status', hidden: true});
    const banners = el('div', {class: 'banners'}, this.notice);
    if (this.historical) banners.append(el('div', {class: 'history-banner'}, el('strong', {}, '历史版本 · 只读'),
      el('span', {}, `正在看 ${version(this.route.revision)}，当前为 ${version(this.latest.revision_id)}。阅读位置与个人草稿仍绑定原基准。`), button('查看当前版本', () => this.current())));
    if (this.info.sample) banners.append(el('div', {class: 'sample-banner'}, this.info.sample.readonly ? '这是合成的只读示例，未调用模型，也未进行专业质量验收。' : '这是可编辑的合成验证项目，未调用模型，也未进行专业质量验收。'));
    banners.append(el('p', {class: 'compact-note'}, '此宽度保留阅读与个人意见；多页比较和精细编辑请使用更宽的窗口。'));
    this.main = el('main', {id: 'main', class: 'workspace', tabindex: '-1'});
    const view = {overview, content, gallery, page: pageDetail, runs, style}[this.route.surface];
    this.main.append(view(this, data));
    const pending = this.summary.task_counts.awaiting_host || 0;
    const top = el('header', {class: 'topbar'}, el('div', {class: 'crumb'}, el('strong', {}, this.info.title), el('span', {class: 'version'}, version(this.route.revision))),
      button(`待交接 ${pending}`, () => this.go({surface: 'runs', task_id: null}), false, {'aria-label': `查看待交接任务，${pending} 项` }));
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
      modal('交接内容整理', el('div', {class: 'stack'}, el('p', {}, status), el('p', {class: 'muted'}, `任务 ${handoff.task_id} · ${version(handoff.revision_id)}`), text),
        [button('复制交接说明', () => copyText(handoff.handoff), true)]);
    } catch (error) { this.setNotice(readableError(error)); }
  }
}

function infoSampleLabel(info) { return info.sample.readonly ? '合成示例 · 只读' : '合成验证项目'; }
