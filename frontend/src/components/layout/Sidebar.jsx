import React from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function Sidebar() {
  const { scene, setScene, activeProject, revision, pages, currentPage, getPageNumStr } = useDeckMaster();
  return <aside className="sidebar" aria-label="项目导航">
    <div className="project-card">
      <small>当前作品</small><strong>{activeProject}</strong>
      <span className="badge neutral">{revision ? `版本 ${revision}` : '连接中'}</span>
      <p className="muted">{pages.length} 页</p>
    </div>
    <nav className="nav" aria-label="主工作面">
      {[['overview', '制作总览'], ['content', '内容与页序'], ['gallery', '整稿画廊'], ['delivery', '任务与交付']].map(([key, label]) =>
        <button key={key} id={`nav-${key}`} className={scene === key ? 'active' : ''} onClick={() => setScene(key)}><Icon name={key} />{label}</button>)}
      {currentPage && <button className={scene === 'page' ? 'active' : ''} onClick={() => setScene('page')}><Icon name="page" />单页工作区（第 {getPageNumStr(currentPage)} 页）</button>}
    </nav>
  </aside>;
}
