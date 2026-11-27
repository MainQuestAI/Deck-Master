import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function ArtifactStatus({ status }) {
  const { getPage, getPageNumStr } = useDeckMaster();
  if (!status) return null;
  const names = ids => ids?.length ? ids.map(id => getPage(id) ? `第 ${getPageNumStr(id)} 页` : id).join('、') : '无';
  const mode = status.build_mode;
  const missingLabel = mode === 'native'
    ? '缺原生还原'
    : mode === 'mixed'
      ? '混合构建 · 缺可编辑页'
      : '缺 SVG';
  const staleLabel = mode === 'native'
    ? '原生还原依据已变'
    : mode === 'mixed'
      ? '可编辑页依据已变'
      : 'SVG 依据已变';
  const incompleteLabel = mode === 'native'
    ? '旧原生还原依据未记录目的和布局'
    : mode === 'mixed'
      ? '旧可编辑页依据未记录目的和布局'
      : '旧 SVG 依据未记录目的和布局';
  return <div className="s4-status" aria-live="polite">
    {Array.isArray(status.missing_pages) && Array.isArray(status.stale_pages) && <p>{missingLabel}：{names(status.missing_pages)}；{staleLabel}：{names(status.stale_pages)}</p>}
    {status.stale_images?.length > 0 && <p>原图制作依据已变：{names(status.stale_images)}</p>}
    {status.incomplete_basis_pages?.length > 0 && <p>{incompleteLabel}：{names(status.incomplete_basis_pages)}</p>}
    {status.input_changed && <p className="s4-message">{status.warning || '当前作品已改变，下载的是最近一次构建；可重新构建。'}</p>}
    {status.build_missing_pages?.length > 0 && <p>该次构建未包含：{names(status.build_missing_pages)}</p>}
  </div>;
}
