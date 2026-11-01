import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
import PageArtwork from '../common/PageArtwork';

export default function GalleryView() {
  const { pages, galleryLayer, setGalleryLayer, galleryView, setGalleryView, openPage, createPage, busy, setPresentation, getPageNumStr } = useDeckMaster();
  return <div>
    <div className="view-head"><div><h1>整稿画廊</h1><p>原图与编译预览对应当前页面，过期产物会标明。</p></div><button className="button" disabled={!pages.length} onClick={() => setPresentation(pages[0].id)}>全屏放映预览</button></div>
    <div className="toolbar"><div className="segmented-control">{[['grid', '网格画板'], ['continuous', '长卷阅读']].map(([key, label]) => <button key={key} className={galleryView === key ? 'active' : ''} onClick={() => setGalleryView(key)}>{label}</button>)}</div><select className="select-filter" aria-label="展示产物层" value={galleryLayer} onChange={event => setGalleryLayer(event.target.value)}><option value="original">原图</option><option value="svg">SVG 预览</option><option value="text">逐页稿</option></select></div>
    {!pages.length && <div className="s4-empty"><p>尚无页面或原图</p><button className="primary" onClick={createPage} disabled={busy.create}>进入制作</button></div>}
    <div className={galleryView === 'grid' ? 'gallery-grid' : 's4-continuous'}>{pages.map(page => <article className="slide-card" key={page.id}><PageArtwork page={page} layer={galleryLayer} /><div className="card-foot"><span>第 {getPageNumStr(page.id)} 页 · {page.content.title || '未命名页面'}</span><button className="button tiny" onClick={() => openPage(page.id)}>打开</button></div></article>)}</div>
  </div>;
}
