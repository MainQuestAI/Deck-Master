import React from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function OverviewView() {
  const { pages, workspace, query, setQuery, openPage, createPage, busy, openDrawer, setScene, getPageNumStr } = useDeckMaster();
  const status = workspace.artifact_status;
  const filtered = pages.filter(page => page.content.title.includes(query));
  return <div>
    <div className="view-head"><div><h1>制作总览</h1><p>浏览当前作品，修改内容并继续制作。</p></div><div className="head-actions"><button className="button" onClick={() => openDrawer('history')}><Icon name="layers" />版本历史记录</button><button className="primary" onClick={createPage} disabled={busy.create}>新增页面</button></div></div>
    <div className="metric-summary">
      {[[pages.length, '逐页稿'], [pages.filter(page => page.image).length, '原图'], [pages.filter(page => page.svg).length, 'SVG'], [workspace.runs.filter(run => run.status === 'open').length, '进行中任务']].map(([value, label]) => <div className="metric-item" key={label}><strong>{value}</strong><p>{label}</p></div>)}
    </div>
    <section className="next-banner"><div className="mark-icon"><Icon name="page" /></div><div className="grow"><h2>{pages.length ? '查看逐页稿并继续制作' : '作品还是空的'}</h2><p>{pages.length ? '正文、讲稿与产物按页保存。' : '新增第一页，开始写正文与讲稿。'}</p></div><button className="primary" disabled={busy.create} onClick={() => pages.length ? openPage(pages[0].id) : createPage()}>进入制作</button></section>
    {pages.length > 0 && <>
      <div className="toolbar"><label className="search-box"><Icon name="search" /><input aria-label="搜索页面" placeholder="搜索页名" value={query} onChange={event => setQuery(event.target.value)} /></label><button className="button" onClick={() => setScene('delivery')}>任务与下载</button></div>
      <div className="matrix-container"><table className="matrix-table"><thead><tr><th>页面</th><th>原图</th><th>SVG</th><th>操作</th></tr></thead><tbody>{filtered.map(page => <tr key={page.id}>
        <td><button className="page-entry-link" onClick={() => openPage(page.id)}><span className="p-no num">{getPageNumStr(page.id)}</span>{page.content.title || '未命名页面'}</button></td>
        <td><span className={`badge ${status.stale_images.includes(page.id) ? 'warn' : 'neutral'}`}>{!page.image ? '未制作' : status.stale_images.includes(page.id) ? '已过期' : '已采用'}</span></td>
        <td><span className={`badge ${status.stale_pages.includes(page.id) ? 'warn' : 'neutral'}`}>{!page.svg ? '未制作' : status.stale_pages.includes(page.id) ? '已过期' : '已采用'}</span></td>
        <td><button className="button tiny quiet" onClick={() => openPage(page.id)}>打开</button></td>
      </tr>)}</tbody></table>{filtered.length === 0 && <p className="s4-empty">没有匹配的页面</p>}</div>
    </>}
  </div>;
}
