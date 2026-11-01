import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';

const crumbMap = {
  projects: '所有项目',
  overview: '制作总览',
  content: '内容与页序',
  gallery: '整稿画廊',
  style: '风格校准',
  delivery: '任务与交付',
  page: '单页工作区',
  compare: '候选比较'
};

export default function Topbar() {
  const { scene, activeProject, revision, currentPage, getPageNumStr } = useDeckMaster();

  const currentLabel = scene === 'page'
    ? `单页工作区 (第 ${getPageNumStr(currentPage)} 页)`
    : crumbMap[scene] || '工作台';

  return (
    <header className="topbar">
      <div className="crumb">
        <span>工程</span>
        <span>/</span>
        <span id="crumb-project-name">{activeProject}</span>
        <span>/</span>
        <strong id="crumb-current">{currentLabel}</strong>
      </div>
      <div className="row">
        <span className="badge ok" id="top-revision-badge">基准 R 0{revision}</span>
        <span className="muted" style={{ fontSize: '11px' }}>
          按 <kbd className="dm-kbd">⌘K</kbd> 呼出指挥台
        </span>
      </div>
    </header>
  );
}
