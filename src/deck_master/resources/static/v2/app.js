import {get, readableError} from './api.js';
import {el, button, empty, canReloadWorkbench} from './dom.js';
const root = document.querySelector('#app');
let generation = 0;
async function start() {
  const serial = ++generation;
  let importing = false;
  try {
    const health = await get('/api/health');
    if (serial !== generation) return;
    if (health.protocol_version !== 'workbench-service.v1' || !health.instance_id || !health.build_id || !['project', 'launcher'].includes(health.role)) {
      root.replaceChildren(el('main', {id: 'main', class: 'workspace'}, empty('当前核心尚不支持新版工作台',
        '请升级项目服务后重新打开。项目文件仍保留，当前没有执行写入。', button('重新连接', event => {
          if (serial === generation && root.contains(event.currentTarget)) start();
        }))));
      return;
    }
    importing = true;
    if (health.role === 'launcher') {
      const {launcher} = await import('./launcher-ui.js');
      importing = false;
      if (serial !== generation) return;
      await launcher(root, health);
    } else {
      const {Project} = await import('./project.js');
      importing = false;
      if (serial !== generation) return;
      await new Project(root, health).start();
    }
  } catch (error) {
    if (serial !== generation) return;
    const failedURL = location.href;
    const panel = empty('暂时无法打开工作台', importing ? '工作台模块未能加载，连接恢复后请重新加载。当前输入仍保留。' : readableError(error),
      button(importing ? '重新加载工作台' : '重新连接', () => {
        if (serial !== generation || !panel.isConnected || location.href !== failedURL) return;
        if (!importing) start();
        else if (canReloadWorkbench()) location.reload();
      }));
    root.replaceChildren(el('main', {id: 'main', class: 'workspace'}, panel));
  }
}
start();
document.querySelector('.skip').addEventListener('click', event => {
  event.preventDefault();
  const main = document.querySelector('#main');
  if (main) { main.tabIndex = -1; main.focus(); main.scrollIntoView({block: 'start'}); }
});
