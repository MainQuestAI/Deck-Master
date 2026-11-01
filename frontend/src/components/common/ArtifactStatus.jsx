import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function ArtifactStatus({ status }) {
  const { getPage, getPageNumStr } = useDeckMaster();
  if (!status) return null;
  const names = ids => ids?.length ? ids.map(id => getPage(id) ? `第 ${getPageNumStr(id)} 页` : id).join('、') : '无';
  return <div className="s4-status" aria-live="polite">
    <p>缺 SVG：{names(status.missing_pages)}；SVG 已过期：{names(status.stale_pages)}</p>
    {status.input_changed && <p className="s4-message">{status.warning || '当前作品已改变，下载的是最近一次构建；可重新构建。'}</p>}
    {status.build_missing_pages?.length > 0 && <p>该次构建未包含：{names(status.build_missing_pages)}</p>}
  </div>;
}
