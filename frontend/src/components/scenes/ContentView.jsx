import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function ContentView() {
  const { pages, openPage, editPage, createPage, busy, getPageNumStr } = useDeckMaster();
  return <div>
    <div className="view-head"><div><h1>内容与页序</h1><p>按当前页序阅读正文与讲稿。</p></div><button className="primary" onClick={createPage} disabled={busy.create}>新增页面</button></div>
    {!pages.length && <div className="s4-empty">尚无页面；新增第一页开始制作。</div>}
    {pages.map(page => <article className="s4-panel" key={page.id}><div className="row between"><h2>第 {getPageNumStr(page.id)} 页 · {page.content.title || '未命名页面'}</h2><div className="row"><button className="button" onClick={() => openPage(page.id)}>阅读</button><button className="button" onClick={() => editPage(page.id)}>修改正文与讲稿</button></div></div><p className="muted">{page.purpose || '尚未填写本页目的'}</p></article>)}
  </div>;
}
