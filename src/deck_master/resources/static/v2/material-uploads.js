import {get, postBinary, readableError} from './api.js';
import {el, button} from './dom.js';

// Staged bytes become project sources only after the normal input confirmation.
// Keep the original UUID and file digest across a lost response and later typing.
export function materialUploads(app, read, write, {single = false} = {}) {
  const node = el('section', {class:'material-uploads stack'});
  const files = new Map();
  const picker = el('input', {type:'file', multiple:!single, accept:'.txt,.md,.json,.pdf,.docx,.pptx,.png,.jpg,.jpeg,.svg,.webp,.gif', 'aria-label':single?'选择替换材料文件':'选择新增材料文件'});
  const message = el('p', {class:'field-error', role:'status'});
  const list = el('div', {class:'stack'});
  let disposed = false;
  app.disposables.push(() => { disposed = true; });
  // A previous document cannot still own an in-flight request after refresh.
  // Keep its identity recoverable instead of restoring permanently busy controls.
  if (read().some(item => ['uploading','checking'].includes(item.state))) write(read().map(item => ['uploading','checking'].includes(item.state) ? {...item,state:'unknown',error:'上次文件接收尚未核实，请沿原编号检查。'} : item));
  const update = (record, patch) => {
    const current = read().find(item => item.upload_id === record.upload_id);
    if (disposed || !current) return;
    Object.assign(record, patch);Object.assign(current,patch);write([...read()]);draw();
  };
  function accept(record, value) {
    if (value.status !== 'uploaded' || ['upload_id','name','size','sha256'].some(key => value[key] !== record[key])) throw new Error('材料回执与所选文件不一致，保留原编号继续核实。');
    update(record, {state:'ready', error:''});
  }
  async function verify(record) {
    update(record, {state:'checking', error:''});
    try { accept(record, await get('/api/content/uploads/' + encodeURIComponent(record.upload_id))); }
    catch (error) { update(record, {state:error.code === 'material_upload_not_found' ? 'not_found' : 'unknown', error:readableError(error)}); }
  }
  async function send(record) {
    const file = files.get(record.upload_id);
    if (!file) { message.textContent = '请重新选择原文件；文件内容一致时会沿原编号继续。'; picker.click(); return; }
    update(record, {state:'uploading', error:''});
    try { accept(record, await postBinary('/api/content/uploads?' + new URLSearchParams({upload_id:record.upload_id,name:record.name}), file)); }
    catch (error) { update(record, {state:!error.status || error.status >= 500 || error.code === 'invalid_response' ? 'unknown' : 'rejected', error:readableError(error)}); }
  }
  function draw() {
    list.replaceChildren(...read().map(record => el('article', {class:'material-upload-row stack'},
      el('strong', {}, record.name),
      el('p', {class:'muted'}, record.state === 'ready' ? '文件已接收 · 确认输入变化后才加入项目材料' : ['uploading','checking'].includes(record.state) ? '正在核实文件…' : record.state === 'rejected' ? '文件未接收，原材料保留' : '文件接收结果待核实 · 原编号保留'),
      record.error && el('p', {class:'field-error'}, record.error),
      el('div', {class:'row wrap'},
        !['ready','uploading','checking','rejected'].includes(record.state) && button('核实这份材料', () => verify(record)),
        record.state === 'not_found' && button(files.has(record.upload_id)?'继续传原文件':'重新选择原文件', () => send(record)),
        !['uploading','checking'].includes(record.state) && button('从本次选择移除', () => { files.delete(record.upload_id); write(read().filter(item => item.upload_id !== record.upload_id)); draw(); })))));
  }
  picker.addEventListener('change', async () => {
    message.textContent = ''; picker.disabled = true;
    try {
      for (const file of [...picker.files]) {
        if (!file.size || file.size > 64 * 1024 * 1024) { message.textContent = '请选择 64 MiB 以内的非空材料；已有文件保持。'; continue; }
        const bytes = await file.arrayBuffer();
        const sha256 = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
        if (disposed) return;
        let record = read().find(item => item.name === file.name && item.size === file.size && item.sha256 === sha256);
        if (record?.state === 'ready') { message.textContent='这份文件已经接收，本次选择保留一份。';continue; }
        if (!record) {
          record = {upload_id:'upload-'+crypto.randomUUID(),name:file.name,size:file.size,sha256,state:'unknown',error:''};
          write(single ? [record] : [...read(), record], {reason:'selected'});
        }
        files.set(record.upload_id, file); draw();
        // Exact re-selection first verifies the original receipt, then sends only
        // if the core says it has never received those bytes.
        await verify(record);
        if (record.state === 'not_found') await send(record);
      }
    } catch (error) { message.textContent = readableError(error); }
    finally { picker.value = ''; picker.disabled = false; }
  });
  node.append(el('label', {class:'stack'}, single?'选择新版本文件':'从电脑选入材料',picker), message, list);
  draw(); return node;
}
