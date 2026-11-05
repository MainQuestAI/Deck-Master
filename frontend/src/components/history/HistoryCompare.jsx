import React, { useMemo } from 'react';
import { diffDecks } from '../../historyDiff.js';
import { HistoryValue, SnapshotMeta } from './HistoryBody.jsx';

const kinds = { added: '新增', removed: '移除', moved: '位置变化', replaced: '替换', full: '完整前后值' };

function Changes({ changes }) {
  return changes.map((change, index) => <details className="history-change" key={index}>
    <summary>{change.label}{kinds[change.kind] ? ` · ${kinds[change.kind]}` : ''}</summary>
    {change.children ? <Changes changes={change.children} /> : <>
      {change.kind === 'full' && <p>缺少可靠的身份配对，显示完整前后值。</p>}
      <div className="history-columns">
        <section aria-label="修改前"><h4>修改前</h4><HistoryValue value={change.before} /></section>
        <section aria-label="修改后"><h4>修改后</h4><HistoryValue value={change.after} /></section>
      </div>
    </>}
  </details>);
}

export default function HistoryCompare({ left, right, leftMeta, rightMeta }) {
  const diff = useMemo(() => diffDecks(left.deck, right.deck), [left, right]);
  const pages = diff.pages[0]?.children || diff.pages;
  return <section aria-label="历史正文对比">
    <div className="history-columns">
      <SnapshotMeta label="修改前" version={left.version} meta={leftMeta} />
      <SnapshotMeta label="修改后" version={right.version} meta={rightMeta} />
    </div>
    {!diff.hasChanges ? <p className="s4-message" role="status">所选范围无正文变化</p> : <>
      <p className="s4-status">任务变化 {diff.brief.length} 项 · 框架变化 {diff.framing.length} 项 · 页面变化 {pages.length} 项</p>
      {diff.brief.length > 0 && <section className="s4-panel"><h3>任务信息</h3><Changes changes={diff.brief} /></section>}
      {diff.framing.length > 0 && <section className="s4-panel"><h3>业务框架</h3><Changes changes={diff.framing} /></section>}
      {diff.pages.length > 0 && <section className="s4-panel"><h3>页面与讲稿</h3><Changes changes={pages} /></section>}
    </>}
  </section>;
}
