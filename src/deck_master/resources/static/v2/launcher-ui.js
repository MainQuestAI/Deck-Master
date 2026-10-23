import {get, post, readableError} from './api.js';
import {el, button, heading, empty, field, modal, version, toast} from './dom.js';
import {surfaces, layers} from './routes.js';
import {externalReviewForm} from './collaboration-desk.js';
import {draftIntake} from './draft-intake.js';

export function localURL(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) &&
      !url.username && !url.password && ['/', '/v2/', '/studio/'].includes(url.pathname) ? url : null;
  } catch { return null; }
}
export async function launcher(root, health) {
  root.className = 'launcher';
  const list = el('section', {class: 'stack', 'aria-label': '最近项目'});
  const message = el('p', {role: 'status', class: 'field-error'});
  const search = el('input', {type: 'search', placeholder: '搜索项目名称', 'aria-label': '搜索项目名称', autocomplete: 'off'});
  const count = el('span', {class: 'muted', role: 'status'});
  let entries = [];
  const surfaceLabels = {...surfaces, page: '单页'};
  const positionText = entry => {
    const position = entry.position?.position;
    if (!position) return version(entry.revision_id);
    const surface = surfaceLabels[position.surface] || position.surface;
    const layer = position.surface === 'page' && layers[position.layer] ? ' · ' + layers[position.layer] : '';
    return `可继续上次阅读 · ${surface}${layer}${position.page_id ? ' · ' + position.page_id : ''} · ${version(position.revision || entry.revision_id)}`;
  };
  const renderList = () => {
    const term = search.value.trim().toLowerCase();
    const visible = entries.filter(entry => !term || entry.title.toLowerCase().includes(term));
    count.textContent = entries.length ? (term ? `${visible.length} / ${entries.length} 个项目` : `${entries.length} 个项目`) : '';
    list.replaceChildren();
    if (!entries.length) list.append(empty('从一个项目开始', '选入材料，阅读整稿，追溯每一页的制作依据。项目保存在你选择的本机目录。'));
    else if (!visible.length) list.append(empty('没有匹配的项目', '换一个名称关键词，或清除搜索查看全部项目。'));
    for (const entry of visible) {
      const rowError = el('p', {class: 'field-error', role: 'alert'});
      list.append(el('article', {class: 'project-card'},
        el('div', {class: 'project-card-main'}, el('h2', {}, entry.title),
          el('p', {class: 'muted'}, entry.available ? positionText(entry) : '位置不可用 · 请重新选择目录'),
          el('div', {class: 'row wrap'},
            entry.available && el('span', {class: 'status'}, entry.position?.position ? '有阅读进度' : '尚未打开过'),
            typeof entry.page_count === 'number' && el('span', {class: 'status'}, `${entry.page_count} 页`),
            entry.sample?.readonly && el('span', {class: 'status'}, '示例 · 只读')),
          el('details', {}, el('summary', {}, '保存位置'), el('p', {class: 'path'}, entry.path)), rowError),
        el('div', {class: 'row wrap'}, button('打开项目', async event => {
          const trigger = event.currentTarget; trigger.disabled = true;
          try { await open(entry.entry_id); } catch (error) { rowError.textContent = readableError(error); trigger.disabled = false; }
        }, false, {disabled: !entry.available}), button('从列表移除', () => {
          const dialog = modal('从最近项目移除', el('p', {}, `仅取消“${entry.title}”的注册，项目文件和历史继续保留。`),
            [button('移除条目', async () => {
              try {
                await post('/api/projects/remove', {entry_id: entry.entry_id});
                // Remove the confirmed entry before close restores focus. Waiting
                // for the later list read can otherwise detach the restored trigger.
                entries = entries.filter(item => item.entry_id !== entry.entry_id);
                renderList();
                closeRemoval();
                await refresh();
              }
              catch (error) { rowError.textContent = readableError(error); closeRemoval(); }
            })]);
          const content = dialog.firstElementChild;
          const closeRemoval = () => {
            // A late reply belongs to this confirmation, not a subsequently opened form.
            if (dialog.open && dialog.firstElementChild === content) dialog.close();
          };
        }, false, {class: 'quiet'}))));
    }
  };
  search.addEventListener('input', renderList);
  const refresh = async () => {
    try {
      const data = await get('/api/projects');
      entries = data.projects || [];
      renderList();
      message.textContent = '';
    } catch (error) { message.textContent = readableError(error); }
  };
  async function open(entry_id) {
    const result = await post('/api/projects/open', {entry_id, ui:document.documentElement.dataset.workbenchUi === 'studio' ? 'studio' : 'v2'});
    const url = localURL(result.url);
    if (!url) throw new Error('项目服务返回的位置无效，请从工作台重新打开。');
    location.assign(url.href);
  }
  root.replaceChildren(el('header', {class: 'launcher-brand'}, el('img', {class: 'brand-logo', src: '/v2/assets/deck-master-logo/logo-horizontal-light.svg', alt: 'Deck Master', width: 176, height: 46}), el('span', {class: 'muted'}, '本机制作工作台')),
    el('main', {id: 'main'}, heading('项目', '打开正在制作的方案。材料、逐页内容、制作依据和每版产物，都在同一个地方。', button('新建项目', createForm, true)),
      el('div', {class: 'toolbar'}, el('div', {class: 'row wrap'}, button('选择项目文件夹', registerForm),
        health.ui_capabilities?.includes('external_review.v1')&&button('只读审阅稿件',()=>externalReviewForm()),button('打开只读示例', async event => {
        const trigger = event.currentTarget; trigger.disabled = true;
        try { const data = await post('/api/projects/sample', {}); await open(data.project.entry_id); }
        catch (error) { message.textContent = readableError(error); trigger.disabled = false; }
      }), button('刷新项目列表', refresh)), el('div', {class: 'row wrap'}, search, count)), message, list,
      el('footer', {class: 'launcher-foot muted'}, `本机服务 ${health.service_version} · 项目目录仅按你的选择登记。`)));
  await refresh();
  async function picker(input, error, trigger) {
    trigger.disabled = true;
    try {
      const data = await post('/api/directories/pick', {});
      if (data.status === 'selected') { error.textContent='';input.value = data.path; input.dispatchEvent(new Event('input')); }
      else if (['manual_path_required','timed_out','failed','busy'].includes(data.status)) { error.textContent = (data.diagnostic?.message||'当前环境无法打开目录选择器。')+' 当前输入保留，可直接填写完整路径。'; input.focus(); }
      else toast('已取消选择，当前项目保持。');
    } catch (failure) { error.textContent = readableError(failure)+' 当前输入保留，请手动填写路径或重试。'; input.focus(); }
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
    const brief = field('用途（必填）', el('textarea', {required: true, rows: 3, placeholder: '希望受众理解、判断、学习或完成什么？'}));
    const audience = field('受众（必填）', el('input', {required: true, placeholder: '例如：学员、研究同行、工程评审者或业务负责人'}));
    const work = field('本次约定产物', el('select', {}, el('option', {value:'full_deck'}, '完整方案'),
      el('option', {value:'plan_only'}, '论证与大纲'), el('option', {value:'write_only'}, '上屏稿'),
      el('option', {value:'speech_only'}, '已有稿件的口播稿'), el('option', {value:'content_full'}, '完整内容')),
      '内容工作完成后正常返回约定产物，不自动继续原图制作。口播工作须选入已有完整稿件。');
    const manuscript = draftIntake();
    const mode = field('阅读方式（可选）', el('select', {}, el('option', {value:''}, '尚未明确指定'),
      el('option', {value:'live'}, '现场讲述'), el('option', {value:'read_alone'}, '独立阅读'), el('option', {value:'mixed'}, '讲述与独立阅读')));
    const parent = field('保存到哪个文件夹（必填）', el('input', {required: true, autocomplete: 'off', placeholder: '现有父目录的完整路径'}));
    const folder = field('新项目文件夹名（必填）', el('input', {required: true, placeholder: '例如：我的方案', pattern: '[^/\\\\]+', autocomplete: 'off'}), '将在上述位置创建新目录；不能覆盖已有目录。');
    const limit = field('页数目标（可选）', el('input', {type: 'number', min: 1, step: 1}));
    const error = el('p', {class: 'field-error', role: 'alert'});
    const form = el('form', {class: 'stack launcher-create-form'}, title.node, brief.node, audience.node, manuscript.node, work.node, mode.node,
      el('div', {class: 'form-pair'}, parent.node, folder.node), button('选择保存文件夹', event => picker(parent.input, parent.error, event.currentTarget)),
      limit.node, el('p', {class: 'muted'}, '可从用途开始，也可选入完整确认稿；确认稿按明确页序建立导入映射，保留来源。创建项目不会启动模型或授予制作权限。'), error);
    const submit = button('创建项目', () => form.requestSubmit(), true);
    const dialog = modal('新建项目', form, [submit], {protectDraft:true});
    // 创建成功后关闭对话框也要刷新列表：新项目出现在列表里，而不是邀请用户
    // 在同一路径再次创建（F13/N14 的另一半）。
    dialog.addEventListener('close', refresh, {once:true});
    form.addEventListener('submit', async event => {
      event.preventDefault(); submit.disabled = true; error.textContent = '';
      const path = parent.input.value.trim().replace(/\/+$/, '') + '/' + folder.input.value.trim();
      const data = {path, title: title.input.value.trim(), brief: brief.input.value.trim(), audience: audience.input.value.trim()};
      if (manuscript.payload) data.draft = manuscript.payload;
      if (work.input.value==='speech_only'&&!manuscript.payload) {
        error.textContent='口播工作需要已有完整稿件，请先选择确认稿 JSON 文件。'; submit.disabled=false; manuscript.input.focus(); return;
      }
      if (mode.input.value) data.presentation_mode=mode.input.value;
      if (work.input.value!=='full_deck') data.request_input={intent:'content_only',content_intent:work.input.value,
        scope:{subject:'deck',page_ids:manuscript.pages.map(page=>page.page_id),page_manifest_ref:null,external_artifact_ref:null,
          layers:work.input.value==='plan_only'?['narrative','plan']:work.input.value==='write_only'?['narrative','plan','page_copy']:work.input.value==='speech_only'?['speech']:['narrative','plan','page_copy','speech'],
          allow_page_membership_change:work.input.value!=='speech_only',allow_page_order_change:work.input.value!=='speech_only',purpose:'working'}};
      if (limit.input.value) data.page_limit = Number(limit.input.value);
      // 依据已发生事实恢复（F13/N14 + UX-06b）：创建成功后无论登记还是打开失败，
      // 主动作都是「登记并打开这个位置」——登记按路径幂等，不会重复创建或覆盖；
      // 创建响应本身丢失时同样只核实这个位置，绝不再次创建。
      const recovery = known => button('登记并打开这个位置', async trigger => {
        // 事件派发结束后 currentTarget 会变 null：先捕获按钮引用再进入 await。
        const control = trigger.currentTarget;
        control.disabled = true;
        const note = el('span', {}, '');
        error.append(note);
        try {
          const entry = await post('/api/projects/register', {path: known ? known.path : path});
          await open(entry.project.entry_id);
        } catch (openFailure) {
          note.textContent = readableError(openFailure) + ' 没有创建或覆盖任何目录。';
          control.disabled = false;
        }
      }, Boolean(known));
      let created = null;
      try {
        const result = await post('/api/projects/create', data);
        created = result.project;
        if (!result.registered) throw new Error('项目已完整建立，但未能登记；请重新登记并打开这个位置，不要重复创建。');
        await open(result.project.entry_id);
      } catch (failure) {
        // Translate only the known hard-limit failure and its safe integer.
        // Arbitrary exception prose may contain private paths or identities.
        const hardLimit=(failure.path||failure.field)==='draft/page_order'&&
          /^actual manuscript exceeds the provided hard maximum page_limit=(\d+)$/.exec(failure.message);
        error.textContent=hardLimit&&Number.isSafeInteger(Number(hardLimit[1]))&&Number(hardLimit[1])>0?
          `确认稿有 ${manuscript.pages.length} 页，超过本次明确页数上限 ${hardLimit[1]} 页。原文件与输入保留。请调整完整稿件或页数上限后重试。`:
          readableError(failure);
        const lost = !created && (!failure.status || failure.status >= 500 || failure.code === 'invalid_response');
        if (created) error.append(' ', recovery(created));
        else if (lost) {
          // 请求可能已被执行：保留位置，用登记动作按事实核实，不再重复创建。
          error.append(el('span', {}, ' 未能核实这次创建的结果；下面的动作只登记已存在的位置。'));
          error.append(' ', recovery(null));
          submit.disabled = true;
        } else submit.disabled = false;
      }
    });
  }
}
