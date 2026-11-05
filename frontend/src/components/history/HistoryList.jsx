import React from 'react';

export default function HistoryList({ history, currentVersion, restoring, onView, onCompare, onRestore }) {
  return <section aria-label="历史版本列表">
    {history.map(version => <article key={version.id} className="s4-panel">
      <h3>版本 {version.id}{version.id === currentVersion && ' · 当前'}</h3>
      <p>{version.created_at}</p><p className="s4-wrap">{version.summary}</p>
      <div className="history-actions">
        <button className="button" onClick={() => onView(version.id)}>查看正文</button>
        <button className="button" onClick={() => onCompare(version.id)}>与当前稿对比</button>
        <button className="button" disabled={restoring || version.id === currentVersion} onClick={() => onRestore(version.id)}>整稿恢复到此版本</button>
      </div>
    </article>)}
    {!history.length && <p>暂无历史版本</p>}
  </section>;
}
