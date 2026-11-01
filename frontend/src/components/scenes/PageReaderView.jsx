import React, { useState } from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
import PageArtwork from '../common/PageArtwork';
import PageContent from '../common/PageContent';

export default function PageReaderView() {
  const { currentPage, getPage, getPageNumStr, editPage, createPage, busy, drafts } = useDeckMaster();
  const [layer, setLayer] = useState('text');
  const page = getPage(currentPage);
  if (!page) return <div className="s4-empty"><p>当前页面已不存在，或尚无页面</p><button className="primary" onClick={createPage} disabled={busy.create}>新增页面</button></div>;
  return <div>
    <div className="view-head"><div><h1>第 {getPageNumStr(page.id)} 页 · {page.content.title || '未命名页面'}</h1><p>{page.purpose}</p></div><button className="primary" onClick={() => editPage(page.id)}>{drafts[page.id] ? '继续未保存的修改' : '修改正文与讲稿'}</button></div>
    <div className="toolbar"><div className="segmented-control">{[['text', '正文'], ['original', '原图'], ['svg', 'SVG 预览']].map(([key, label]) => <button key={key} className={layer === key ? 'active' : ''} onClick={() => setLayer(key)}>{label}</button>)}</div></div>
    <div className="reader-container"><article className="manuscript-card">{layer === 'text' ? <PageContent content={page.content} /> : <PageArtwork page={page} layer={layer} />}</article><aside className="s4-panel"><h2>讲稿</h2><p className="s4-reading">{page.notes || '尚未填写讲稿'}</p>{page.todo.length > 0 && <><h3>待补内容</h3><ul>{page.todo.map((todo, index) => <li key={index}>{todo}</li>)}</ul></>}</aside></div>
  </div>;
}
