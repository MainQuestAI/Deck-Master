import React, { useEffect, useState } from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
import { fileUrl } from '../../api.js';

export default function CompareView() {
  const { comparison, workspace, getPage, compareCandidate, adoptCandidate, setScene, busy } = useDeckMaster();
  const [note, setNote] = useState('');
  useEffect(() => { setNote(''); }, [comparison?.runId, comparison?.pageId, comparison?.candidateFile]);
  if (!comparison) return <p className="s4-empty">请从制作任务中选择候选</p>;
  const page = getPage(comparison.pageId);
  const run = workspace.runs.find(item => item.id === comparison.runId);
  const result = run?.pages.find(item => item.page_id === comparison.pageId);
  const isNative = comparison.kind === 'native';
  const currentFile = page?.[comparison.kind]?.file || null;
  const adopted = currentFile === comparison.candidateFile
    || (!!comparison.adoptedFile && currentFile === comparison.adoptedFile);
  const selected = result?.result_file === comparison.candidateFile
    || (adopted && result?.result_file === comparison.adoptedFile);
  const currentChanged = currentFile !== comparison.currentFile && !adopted;
  // current_basis is the task's own inputs. A deck version bump alone is not a conflict.
  const basisDrifted = (result?.current_basis ?? null) !== (comparison.currentBasis ?? null);
  const label = comparison.kind === 'image' ? '原图' : isNative ? '原生还原' : 'SVG';
  const leftTitle = isNative ? '原图' : '打开时的作品';
  const rightTitle = isNative ? '原生渲染预览' : '选中的候选';
  const leftViewLabel = isNative ? '原图' : comparison.kind === 'svg' ? 'SVG 预览' : '原图';
  const rightViewLabel = isNative ? '原生渲染预览' : comparison.kind === 'svg' ? 'SVG 预览' : '原图';
  const warnings = comparison.adoptedWarnings || [];
  const canAdopt = !!page && selected && !currentChanged && !busy.adopt && (!isNative || note.trim().length > 0);
  return <div>
    <div className="view-head"><div><h1>{comparison.title || '未命名页面'} · {label}比对</h1><p>{isNative ? '左侧为原图，右侧为原生还原渲染预览。核对后填写对照结论即可采用。' : '左侧为打开时的作品，右侧为选中的候选。'}</p></div><button className="button" onClick={() => setScene('delivery')}>返回制作任务</button></div>
    {!page && <p className="s4-message">页面已移除，无法采用此候选。</p>}
    {(!selected || currentChanged || basisDrifted) && <div className="s4-message">{!selected ? '候选已更新。' : '当前作品已变化。'}本次比对画面保持不变，请重新打开后决定。{page && result?.result_file && <button className="button" onClick={() => compareCandidate(run, result)}>打开最新比对</button>}</div>}
    {comparison.reason && <p className="muted">交回时：{comparison.reason}{comparison.basisChanged ? ' · 制作依据已变，请核对内容。' : ''}</p>}
    <div className="compare-grid-board">
      {[[leftTitle, comparison.currentView, leftViewLabel], [rightTitle, comparison.candidateView, rightViewLabel]].map(([title, file, altLabel]) => <section className="s4-panel" key={title}><h2>{title}</h2><div className="s4-artwork">{file ? <img src={fileUrl(file)} alt={`${title} · ${altLabel}`} /> : <p className="s4-empty">尚无{altLabel}</p>}</div></section>)}
    </div>
    {isNative && !adopted && <label className="form-group s4-field">
      <span>本页对照结论（采用原生还原必填）</span>
      <textarea
        rows={3}
        value={note}
        disabled={busy.adopt}
        placeholder="请描述原图与原生渲染预览的对照结果，例如：标题、双栏数据与图例位置一致，小字清晰"
        onChange={event => setNote(event.target.value)}
      />
    </label>}
    {warnings.length > 0 && <section className="s4-message" role="status" aria-label="采用警告">
      <h3>采用提醒</h3>
      <ul>{warnings.map((item, index) => <li key={index}>{item.message || item.code}</li>)}</ul>
    </section>}
    <div className="head-actions s4-actions">
      {adopted ? <p role="status">当前作品已采用此候选</p> : <button className="primary" disabled={!canAdopt} onClick={() => adoptCandidate(isNative ? note.trim() : undefined)}>{busy.adopt ? '正在采用…' : '采用此候选'}</button>}
      <button className="button" disabled={busy.adopt} onClick={() => setScene('delivery')}>{adopted ? '返回制作任务' : '保留当前作品'}</button>
    </div>
  </div>;
}
