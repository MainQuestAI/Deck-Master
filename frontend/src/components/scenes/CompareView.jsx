import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
import { fileUrl } from '../../api.js';

export default function CompareView() {
  const { comparison, workspace, getPage, compareCandidate, adoptCandidate, setScene, busy } = useDeckMaster();
  if (!comparison) return <p className="s4-empty">请从制作任务中选择候选</p>;
  const page = getPage(comparison.pageId);
  const run = workspace.runs.find(item => item.id === comparison.runId);
  const result = run?.pages.find(item => item.page_id === comparison.pageId);
  const selected = result?.result_file === comparison.candidateFile;
  const currentFile = page?.[comparison.kind]?.file || null;
  const adopted = currentFile === comparison.candidateFile;
  const currentChanged = currentFile !== comparison.currentFile && !adopted;
  const label = comparison.kind === 'image' ? '原图' : 'SVG';
  const viewLabel = comparison.kind === 'svg' ? '预览' : label;
  return <div>
    <div className="view-head"><div><h1>{comparison.title || '未命名页面'} · {label}比对</h1><p>左侧为打开时的作品，右侧为选中的候选。</p></div><button className="button" onClick={() => setScene('delivery')}>返回制作任务</button></div>
    {!page && <p className="s4-message">页面已移除，无法采用此候选。</p>}
    {(!selected || currentChanged) && <div className="s4-message">{!selected ? '候选已更新。' : '当前作品已变化。'}本次比对画面保持不变，请重新打开后决定。{page && result?.result_file && <button className="button" onClick={() => compareCandidate(run, result)}>打开最新比对</button>}</div>}
    {comparison.reason && <p className="muted">交回时：{comparison.reason}{comparison.basisChanged ? ' · 制作依据已变，请核对内容。' : ''}</p>}
    <div className="compare-grid-board">
      {[['打开时的作品', comparison.currentView], ['选中的候选', comparison.candidateView]].map(([title, file]) => <section className="s4-panel" key={title}><h2>{title}</h2><div className="s4-artwork">{file ? <img src={fileUrl(file)} alt={`${title} · ${viewLabel}`} /> : <p className="s4-empty">尚无{viewLabel}</p>}</div></section>)}
    </div>
    <div className="head-actions s4-actions">
      {adopted ? <p role="status">当前作品已采用此候选</p> : <button className="primary" disabled={!page || !selected || currentChanged || busy.adopt} onClick={adoptCandidate}>{busy.adopt ? '正在采用…' : '采用此候选'}</button>}
      <button className="button" disabled={busy.adopt} onClick={() => setScene('delivery')}>{adopted ? '返回制作任务' : '保留当前作品'}</button>
    </div>
  </div>;
}
