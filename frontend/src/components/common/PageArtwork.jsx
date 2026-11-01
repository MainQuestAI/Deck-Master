import React, { useState } from 'react';
import { fileUrl } from '../../api.js';
import { useDeckMaster } from '../../context/DeckMasterContext';
import PageContent from './PageContent';

export default function PageArtwork({ page, layer }) {
  const { workspace, editPage, setPresentation } = useDeckMaster();
  const [failed, setFailed] = useState(null);
  if (layer === 'text') return <PageContent content={page.content} />;
  const reference = layer === 'original' ? page.image?.file : page.preview;
  const status = workspace.artifact_status;
  const stale = (layer === 'original' ? status.stale_images : status.stale_pages).includes(page.id);
  const url = fileUrl(reference);
  return <div className="s4-artwork">
    {stale && <p><span className="badge warn">{layer === 'original' ? '原图' : '预览'}已过期</span></p>}
    {url ? failed === url ? <div className="s4-empty" role="alert"><p>附件加载失败，请检查本地服务后重试</p><button className="button" onClick={() => setFailed(null)}>重新加载附件</button></div> : <img src={url} alt={`${page.content.title || '页面'}${layer === 'original' ? '原图' : '预览'}`} onError={() => setFailed(url)} /> : <div className="s4-empty"><p>{layer === 'original' ? '尚无原图' : '尚无预览'}</p><button className="button" onClick={() => { setPresentation(null); editPage(page.id); }}>进入制作</button></div>}
  </div>;
}
