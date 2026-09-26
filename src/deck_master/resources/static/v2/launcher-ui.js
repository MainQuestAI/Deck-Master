import {get, post, readableError} from './api.js';
import {el, button, heading, empty, field, modal, version, toast} from './dom.js';

export function localURL(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) &&
      !url.username && !url.password && ['/', '/v2/'].includes(url.pathname) ? url : null;
  } catch { return null; }
}
export async function launcher(root, health) {
  root.className = 'launcher';
  const list = el('section', {class: 'stack', 'aria-label': '最近项目'});
  const message = el('p', {role: 'status', class: 'field-error'});
  const refresh = async () => {
    try {
      const data = await get('/api/projects');
      list.replaceChildren();
      if (!data.projects.length) list.append(empty('从一个项目开始', '选入材料，阅读整稿，追溯每一页的制作依据。项目保存在你选择的本机目录。'));
      for (const entry of data.projects) {
        const rowError = el('p', {class: 'field-error', role: 'alert'});
        const position = entry.position?.position;
        list.append(el('article', {class: 'project-card'},
          el('div', {class: 'project-card-main'}, el('h2', {}, entry.title),
            el('p', {class: 'muted'}, entry.available ? `${position ? '可继续上次阅读 · ' : ''}${version(position?.revision || entry.revision_id)}` : '位置不可用 · 请重新选择目录'),
            el('details', {}, el('summary', {}, '保存位置'), el('p', {class: 'path'}, entry.path)), rowError),
          el('div', {class: 'row wrap'}, button('打开项目', async event => {
            const trigger = event.currentTarget; trigger.disabled = true;
            try { await open(entry.entry_id); } catch (error) { rowError.textContent = readableError(error); trigger.disabled = false; }
          }, false, {disabled: !entry.available}), button('从列表移除', () => {
            const dialog = modal('从最近项目移除', el('p', {}, `仅取消“${entry.title}”的注册，项目文件和历史继续保留。`),
              [button('移除条目', async () => {
                try { await post('/api/projects/remove', {entry_id: entry.entry_id}); dialog.close(); await refresh(); }
                catch (error) { rowError.textContent = readableError(error); dialog.close(); }
              })]);
          }, false, {class: 'quiet'}))));
      }
      message.textContent = '';
    } catch (error) { message.textContent = readableError(error); }
  };
  async function open(entry_id) {
    const result = await post('/api/projects/open', {entry_id});
    const url = localURL(result.url);
    if (!url) throw new Error('项目服务返回的位置无效，请从工作台重新打开。');
    location.assign(url.href);
  }
  root.replaceChildren(el('header', {class: 'launcher-brand'}, el('strong', {}, 'Deck Master'), el('span', {class: 'muted'}, '本机制作工作台')),
    el('main', {id: 'main'}, heading('项目', '看整稿、追溯制作依据，保留每一次局部修改的来路。', button('新建项目', createForm, true)),
      el('div', {class: 'toolbar'}, el('div', {class: 'row wrap'}, button('选择项目文件夹', registerForm), button('打开只读示例', async event => {
        const trigger = event.currentTarget; trigger.disabled = true;
        try { const data = await post('/api/projects/sample', {}); await open(data.project.entry_id); }
        catch (error) { message.textContent = readableError(error); trigger.disabled = false; }
      })), button('刷新项目列表', refresh)), message, list,
      el('footer', {class: 'launcher-foot muted'}, `本机服务 ${health.service_version} · 项目目录仅按你的选择登记。`)));
  await refresh();
  async function picker(input, error, trigger) {
    trigger.disabled = true;
    try {
      const data = await post('/api/directories/pick', {});
      if (data.status === 'selected') { input.value = data.path; input.dispatchEvent(new Event('input')); }
      else if (data.status === 'manual_path_required') { error.textContent = '当前环境无法打开目录选择器，请在位置字段填写完整路径。'; input.focus(); }
      else toast('已取消选择，当前项目保持。');
    } catch (failure) { error.textContent = readableError(failure); }
    finally { trigger.disabled = false; }
  }
  function registerForm() {
    const path = field('项目文件夹', el('input', {required: true, placeholder: '填写现有项目的完整目录路径', autocomplete: 'off'}), '只读取你选中的目录，不搜索其它文件夹。');
    const select = button('浏览文件夹', event => picker(path.input, path.error, event.currentTarget));
    const form = el('form', {class: 'stack'}, path.node, select);
    const submit = button('登记并打开', () => form.requestSubmit(), true);
    const dialog = modal('打开项目', form, [submit]);
    form.addEventListener('submit', async event => {
      event.preventDefault(); submit.disabled = true; path.error.textContent = '';
      try { const result = await post('/api/projects/register', {path: path.input.value.trim()}); await open(result.project.entry_id); }
      catch (error) { path.error.textContent = readableError(error); submit.disabled = false; }
    });
    dialog.addEventListener('close', refresh, {once: true});
  }
  function createForm() {
    const title = field('项目名称（必填）', el('input', {required: true, maxlength: 200, autocomplete: 'off'}));
    const brief = field('用途（必填）', el('textarea', {required: true, rows: 3, placeholder: '这份方案要帮助听众作出什么判断？'}));
    const audience = field('受众（必填）', el('input', {required: true, placeholder: '例如：第一次了解这个方案的业务负责人'}));
    const parent = field('保存到哪个文件夹（必填）', el('input', {required: true, autocomplete: 'off', placeholder: '现有父目录的完整路径'}));
    const folder = field('新项目文件夹名（必填）', el('input', {required: true, placeholder: '例如：我的方案', pattern: '[^/\\\\]+', autocomplete: 'off'}), '将在上述位置创建新目录；不能覆盖已有目录。');
    const limit = field('页数目标（可选）', el('input', {type: 'number', min: 1, step: 1}));
    const error = el('p', {class: 'field-error', role: 'alert'});
    const form = el('form', {class: 'stack'}, title.node, brief.node, audience.node,
      el('div', {class: 'form-pair'}, parent.node, folder.node), button('选择保存文件夹', event => picker(parent.input, parent.error, event.currentTarget)),
      limit.node, el('p', {class: 'muted'}, '材料列表暂为空。创建后补充材料，再交接内容整理；创建项目不会启动模型。'), error);
    const submit = button('创建项目', () => form.requestSubmit(), true);
    modal('新建项目', form, [submit]);
    form.addEventListener('submit', async event => {
      event.preventDefault(); submit.disabled = true; error.textContent = '';
      const path = parent.input.value.trim().replace(/\/+$/, '') + '/' + folder.input.value.trim();
      const data = {path, title: title.input.value.trim(), brief: brief.input.value.trim(), audience: audience.input.value.trim()};
      if (limit.input.value) data.page_limit = Number(limit.input.value);
      try {
        const result = await post('/api/projects/create', data);
        if (!result.registered) throw new Error('项目已完整建立，但未能登记。请用“选择项目文件夹”重新登记此保存位置。');
        await open(result.project.entry_id);
      } catch (failure) { error.textContent = readableError(failure); submit.disabled = false; }
    });
  }
}
