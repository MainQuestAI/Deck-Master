import React, { useEffect } from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
import PageArtwork from '../common/PageArtwork';
import useDialogFocus, { presentationMove } from './useDialogFocus';

export default function PresentationModal() {
  const { presentation, setPresentation, pages, getPage, getPageNumStr, galleryLayer } = useDeckMaster();
  const index = pages.findIndex(page => page.id === presentation);
  const move = direction => setPresentation(pages[Math.max(0, Math.min(pages.length - 1, index + direction))]?.id);
  const page = getPage(presentation);
  const dialog = useDialogFocus(!!page, () => setPresentation(null));
  useEffect(() => {
    if (!presentation) return;
    const listener = event => {
      const step = presentationMove(event);
      if (!step) return;
      event.preventDefault();
      move(step);
    };
    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [presentation, pages]);
  if (!page) return null;
  return <div ref={dialog} tabIndex={-1} className="presentation-stage s4-presentation" data-theme="dark" role="dialog" aria-modal="true" aria-label="整稿放映">
    <div className="row between"><h2>第 {getPageNumStr(page.id)} 页 · {page.content.title}</h2><button className="button" data-dialog-initial-focus onClick={() => setPresentation(null)}>退出放映</button></div>
    <div className={`s4-projection${galleryLayer === 'text' ? ' text' : ''}`}><PageArtwork page={page} layer={galleryLayer} /></div>
    <div className="row"><button className="button" disabled={index <= 0} onClick={() => move(-1)}>上一页</button><span>{index + 1} / {pages.length}</span><button className="button" disabled={index >= pages.length - 1} onClick={() => move(1)}>下一页</button></div>
  </div>;
}
