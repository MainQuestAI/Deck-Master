import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';

const methods = { human: '人工意见', self_check: 'Host 自检', other_model: '其他模型复核' };

export default function ReviewPanel({ pageId }) {
  const { workspace, addReview, resolveReview, reviewDrafts, setReviewDrafts, busy } = useDeckMaster();
  const scope = pageId ? `page:${pageId}` : 'deck';
  const text = reviewDrafts[scope] || '';
  const reviews = (workspace.reviews || []).filter(review => review.page_id === (pageId || null));
  const saving = busy[`review-add-${scope}`];
  return <section className="s4-panel">
    <h2>{pageId ? '本页意见' : '整稿意见'}（{reviews.length} 条待处理）</h2>
    {reviews.length ? <ul className="s5-reviews">{reviews.map(review => <li key={review.id}>
      <p className="muted">{methods[review.method] || review.method} · 版本 {review.version_id}</p>
      <p className="s4-reading">{review.text}</p>
      <button className="button tiny" disabled={busy[`review-resolve-${review.id}`]} onClick={() => resolveReview(review.id)}>标记已处理</button>
    </li>)}</ul> : <p className="muted">暂无待处理意见</p>}
    <form onSubmit={event => { event.preventDefault(); if (text.trim()) addReview(text, pageId); }}>
      <label className="s4-field">{pageId ? '添加本页意见' : '添加整稿意见'}
        <textarea rows="3" value={text} disabled={saving} onChange={event => setReviewDrafts(value => ({ ...value, [scope]: event.target.value }))} />
      </label>
      <button className="button" type="submit" disabled={saving || !text.trim()}>{saving ? '正在保存…' : '保存意见'}</button>
    </form>
  </section>;
}
