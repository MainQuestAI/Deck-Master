import React from 'react';
import HistoryBody, { SnapshotMeta } from './HistoryBody.jsx';

export default function HistoryViewer({ snapshot, meta }) {
  return <section aria-label="历史正文">
    <SnapshotMeta label="历史正文" version={snapshot.version} meta={meta} />
    <HistoryBody deck={snapshot.deck} />
  </section>;
}
