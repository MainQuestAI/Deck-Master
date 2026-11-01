import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
const labels = { overview: '制作总览', content: '内容与页序', gallery: '整稿画廊', delivery: '任务与交付', page: '单页工作区' };
export default function Topbar() {
  const { scene, activeProject } = useDeckMaster();
  return <header className="topbar"><div className="crumb"><span>作品</span><span>/</span><span>{activeProject}</span><span>/</span><strong>{labels[scene]}</strong></div></header>;
}
