import React from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function Reviewbar() {
  const { theme, toggleTheme, activeProject, pages, revision } = useDeckMaster();
  return <div className="reviewbar">
    <div className="brand-inline"><Icon name="logo" /><span>Deck Master</span><div className="tool-sep" /><span>{activeProject}</span><span className="muted">{pages.length} 页</span></div>
    <div className="row"><span className="badge neutral">{revision ? `版本 ${revision}` : '连接中'}</span><button className="button tiny quiet" onClick={toggleTheme}><Icon name={theme === 'dark' ? 'sun' : 'moon'} />{theme === 'dark' ? '工作室' : '暗室'}</button></div>
  </div>;
}
