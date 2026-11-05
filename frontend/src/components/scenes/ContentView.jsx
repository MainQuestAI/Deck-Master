import React, { useState } from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';

function PageRow({ page, index }) {
  const { pages, openPage, editPage, movePage, removePage, busy, getPageNumStr, currentPage, drafts } = useDeckMaster();
  const [target, setTarget] = useState(null);
  const position = Math.min(target ?? index, pages.length - 1);
  const title = page.content.title || '未命名页面';
  const move = async toIndex => {
    if (await movePage(page.id, toIndex)) setTarget(null);
  };
  return <article className="s4-panel" aria-label={`第 ${index + 1} 页 · ${title}`} aria-current={currentPage === page.id ? 'true' : undefined}>
    <div className="row between"><h2>第 {getPageNumStr(page.id)} 页 · {title}</h2><div className="row"><button className="button" onClick={() => openPage(page.id)}>阅读</button><button className="button" onClick={() => editPage(page.id)}>修改正文与讲稿</button></div></div>
    <p className="muted">{page.purpose || '尚未填写本页目的'}{drafts[page.id] && ' · 有未保存的修改'}</p>
    <div className="row">
      <button className="button" disabled={busy['page-order'] || index === 0} onClick={() => move(index - 1)}>上移</button>
      <button className="button" disabled={busy['page-order'] || index === pages.length - 1} onClick={() => move(index + 1)}>下移</button>
      <form className="row" onSubmit={event => { event.preventDefault(); move(position); }}>
        <label>移动到 <select className="select-filter" aria-label={`将「${title}」移动到`} value={position} disabled={busy['page-order']} onChange={event => setTarget(Number(event.target.value))}>
          {pages.map((item, toIndex) => <option key={item.id} value={toIndex}>第 {toIndex + 1} 页</option>)}
        </select></label>
        <button className="button" type="submit" disabled={busy['page-order'] || position === index}>应用</button>
      </form>
      <button className="button" disabled={busy['page-order']} onClick={() => {
        if (window.confirm(`从当前稿件移除「${title}」？历史版本中仍保留。`)) removePage(page.id);
      }}>从当前稿件移除</button>
    </div>
  </article>;
}

export default function ContentView() {
  const { pages, createPage, editPage, drafts, getPage, busy, actionError } = useDeckMaster();
  const removedDrafts = Object.values(drafts).filter(draft => !getPage(draft.page.id));
  return <div>
    <div className="view-head"><div><h1>内容与页序</h1><p>按当前页序阅读正文与讲稿。</p></div><button className="primary" onClick={createPage} disabled={busy.create}>新增页面</button></div>
    {actionError && <p className="s4-message" role="alert">{actionError}</p>}
    {!pages.length && <div className="s4-empty">尚无页面；新增第一页开始制作。</div>}
    {pages.map((page, index) => <PageRow key={page.id} page={page} index={index} />)}
    {removedDrafts.length > 0 && <section className="s4-panel" aria-label="已移除页面的未保存输入">
      <h2>已移除页面的未保存输入</h2>
      {removedDrafts.map(draft => <div key={draft.page.id}><p className="s4-wrap">{draft.page.content.title || '未命名页面'}</p><button className="button" onClick={() => editPage(draft.page.id)}>查看未保存输入</button></div>)}
    </section>}
  </div>;
}
