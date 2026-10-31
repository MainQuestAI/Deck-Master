import React from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function Sidebar() {
  const {
    scene,
    setScene,
    activeProject,
    revision,
    currentPage,
    getPageNumStr
  } = useDeckMaster();

  return (
    <aside className="sidebar" aria-label="项目导航">
      <div className="project-card">
        <div className="row between">
          <small>当前工程</small>
          <button
            className="button tiny quiet"
            onClick={() => setScene('projects')}
            title="切换项目"
          >
            <Icon name="projects" />
            切换
          </button>
        </div>
        <strong id="sidebar-project-title">{activeProject}</strong>
        <div className="row" style={{ marginTop: '4px' }}>
          <span className="badge ok pulse">R 0{revision} 活动基准</span>
        </div>
        <p className="muted" style={{ fontSize: '11px', marginTop: '6px' }}>
          30 页 · 5 章节 · 24 页已确认
        </p>
      </div>

      <nav className="nav" aria-label="主工作面">
        <button
          className={scene === 'overview' ? 'active' : ''}
          onClick={() => setScene('overview')}
          id="nav-overview"
        >
          <Icon name="overview" />
          制作总览
        </button>

        <button
          className={scene === 'content' ? 'active' : ''}
          onClick={() => setScene('content')}
          id="nav-content"
        >
          <Icon name="content" />
          内容与页序
        </button>

        <button
          className={scene === 'gallery' ? 'active' : ''}
          onClick={() => setScene('gallery')}
          id="nav-gallery"
        >
          <Icon name="gallery" />
          整稿画廊
        </button>

        <button
          className={scene === 'style' ? 'active' : ''}
          onClick={() => setScene('style')}
          id="nav-style"
        >
          <Icon name="style" />
          风格校准
        </button>

        <button
          className={scene === 'delivery' ? 'active' : ''}
          onClick={() => setScene('delivery')}
          id="nav-delivery"
        >
          <Icon name="delivery" />
          任务与交付
        </button>

        <div className="nav-sep"></div>
        <div className="nav-subheading">深层工作台</div>

        <button
          className={scene === 'page' ? 'active' : ''}
          onClick={() => setScene('page')}
          id="nav-page"
        >
          <Icon name="page" />
          单页工作区 (第 {getPageNumStr(currentPage)} 页)
        </button>

        <button
          className={scene === 'compare' ? 'active' : ''}
          onClick={() => setScene('compare')}
          id="nav-compare"
        >
          <Icon name="compare" />
          候选比较 (第 13 页)
        </button>
      </nav>

      <div className="sidefoot">
        <div className="row" style={{ marginBottom: '6px' }}>
          <span className="badge ok">本地引擎已就绪</span>
        </div>
        <p>内存级状态实时生效，支持所有 8 大交互工作面及 Command Palette。</p>
      </div>
    </aside>
  );
}
