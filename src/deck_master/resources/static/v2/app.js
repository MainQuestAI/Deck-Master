import {get, readableError} from './api.js';
import {el, button, empty} from './dom.js';
import {launcher} from './launcher-ui.js';
import {Project} from './project.js';
const root = document.querySelector('#app');
async function start() {
  try {
    const health = await get('/api/health');
    if (health.protocol_version !== 'workbench-service.v1' || !health.instance_id || !health.build_id || !['project', 'launcher'].includes(health.role)) {
      root.replaceChildren(el('main', {id: 'main', class: 'workspace'}, empty('当前核心尚不支持新版工作台',
        '请升级项目服务后重新打开。已停止新版写入，原项目没有迁移。', el('a', {href: '/'}, '打开原有入口'))));
      return;
    }
    if (health.role === 'launcher') await launcher(root, health);
    else await new Project(root, health).start();
  } catch (error) {
    root.replaceChildren(el('main', {id: 'main', class: 'workspace'}, empty('暂时无法打开工作台', readableError(error), button('重新连接', start))));
  }
}
start();
document.querySelector('.skip').addEventListener('click', event => {
  event.preventDefault();
  const main = document.querySelector('#main');
  if (main) { main.tabIndex = -1; main.focus(); main.scrollIntoView({block: 'start'}); }
});
