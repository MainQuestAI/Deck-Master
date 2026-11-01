import React, { useEffect } from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
import PageArtwork from '../common/PageArtwork';

export default function PresentationModal() {
  const { presentation, setPresentation, pages, getPage, getPageNumStr, galleryLayer } = useDeckMaster();
  const index = pages.findIndex(page => page.id === presentation);
  const move = direction => setPresentation(pages[Math.max(0, Math.min(pages.length - 1, index + direction))]?.id);
  useEffect(() => {
    if (!presentation) return;
    const listener = event => {
      if (event.key === 'Escape') setPresentation(null);
      if (['ArrowRight', ' '].includes(event.key)) { event.preventDefault(); move(1); }
      if (event.key === 'ArrowLeft') { event.preventDefault(); move(-1); }
    };
    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [presentation, pages]);
  const page = getPage(presentation);
  if (!page) return null;
  return <div className="presentation-stage s4-presentation" data-theme="dark" role="dialog" aria-modal="true" aria-label="整稿放映">
    <div className="row between"><h2>第 {getPageNumStr(page.id)} 页 · {page.content.title}</h2><button className="button" autoFocus onClick={() => setPresentation(null)}>退出放映</button></div>
    <div className="s4-projection"><PageArtwork page={page} layer={galleryLayer} /></div>
    <div className="row"><button className="button" disabled={index <= 0} onClick={() => move(-1)}>上一页</button><span>{index + 1} / {pages.length}</span><button className="button" disabled={index >= pages.length - 1} onClick={() => move(1)}>下一页</button></div>
  </div>;
}
