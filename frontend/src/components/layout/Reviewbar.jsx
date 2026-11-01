import React from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function Reviewbar() {
  const {
    theme,
    toggleTheme,
    activeProject,
    revision,
    setSpotlightOpen,
    openDrawer
  } = useDeckMaster();

  return (
    <div className="reviewbar">
      <div className="brand-inline">
        <Icon name="logo" className="logo-svg ico-fill" ariaHidden={false} />
        <span>Deck Master</span>
        <span className="badge neutral">PRO V3.3</span>
        <div className="tool-sep" style={{ margin: '0 4px' }}></div>
        <div className="row" style={{ gap: '6px', fontSize: '12px', color: 'var(--dm-color-text-secondary)' }}>
          <span className="badge ok pulse">R 0{revision} 活动基准</span>
          <span style={{ fontWeight: 'var(--dm-weight-emphasize)', color: 'var(--dm-color-text)' }}>
            {activeProject}
          </span>
          <span className="muted" style={{ fontSize: '11px' }}>(30 页 · 5 章节)</span>
        </div>
      </div>

      <div className="row" style={{ gap: '10px' }}>
        <div
          className="spotlight-trigger"
          onClick={() => setSpotlightOpen(true)}
          title="打开全局快速查找与命令面板 (⌘K)"
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setSpotlightOpen(true);
            }
          }}
        >
          <Icon name="search" />
          <span>快速查找</span>
          <kbd className="dm-kbd">⌘K</kbd>
        </div>

        <button
          className="button tiny quiet"
          onClick={toggleTheme}
          id="theme-toggle-btn"
          title={theme === 'dark' ? '当前为 Pro Darkroom 暗室模式，点击切换至 Studio Light 工作室' : '当前为 Studio Light 工作室模式，点击切换至 Pro Darkroom 暗室'}
        >
          <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
          {theme === 'dark' ? '工作室' : '暗室'}
        </button>

        <button
          className="button tiny quiet"
          onClick={() => openDrawer('design')}
          title="查看 UI 重构与设计规格说明"
        >
          <Icon name="alert" />
          设计规格
        </button>
      </div>
    </div>
  );
}
