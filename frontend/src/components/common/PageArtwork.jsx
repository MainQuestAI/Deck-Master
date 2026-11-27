import React, { useState } from 'react';
import { fileUrl, isNativePage } from '../../api.js';
import { useDeckMaster } from '../../context/DeckMasterContext';
import PageContent from './PageContent';

export default function PageArtwork({ page, layer }) {
  const { workspace, openHostHandoff } = useDeckMaster();
  const [failed, setFailed] = useState(null);
  if (layer === 'text') return <PageContent content={page.content} />;
  const reference = layer === 'original' ? page.image?.file : page.preview;
  const status = workspace.artifact_status;
  const stale = (layer === 'original' ? status.stale_images : status.stale_pages).includes(page.id);
  const isNativePreview = layer !== 'original' && isNativePage(page, status);
  const layerLabel = layer === 'original' ? '原图' : isNativePreview ? '原生渲染预览' : 'SVG 预览';
  const url = fileUrl(reference);
  return <div className="s4-artwork">
    {stale && <p><span className="badge warn">{layerLabel}依据已变</span></p>}
    {url ? failed === url ? <div className="s4-empty" role="alert"><p>附件加载失败，请检查本地服务后重试</p><button className="button" onClick={() => setFailed(null)}>重新加载附件</button></div> : <img src={url} alt={`${page.content.title || '页面'}${layerLabel}`} onError={() => setFailed(url)} /> : <div className="s4-empty"><p>尚无{layerLabel}</p><button className="button" onClick={() => openHostHandoff(page.id, layer === 'original' ? 'redraw_image' : 'rebuild_editable')}>进入制作</button></div>}
  </div>;
}
