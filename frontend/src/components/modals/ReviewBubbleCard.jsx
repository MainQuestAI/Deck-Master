import React, { useState } from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function ReviewBubbleCard({ blockId, blockLabel, onClose }) {
  const {
    annotations,
    submitComment,
    adoptComment,
    toggleResolveComment,
    deleteComment,
    openDrawer,
    currentPage
  } = useDeckMaster();

  const comments = annotations[blockId] || [];
  const pendingComments = comments.filter((c) => c.status === 'pending');
  const hasPending = pendingComments.length > 0;

  const [text, setText] = useState('');
  const [roleSelection, setRoleSelection] = useState('业务架构师|李凡');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    const [role, author] = roleSelection.split('|');
    submitComment(blockId, { text, author, role });
    setText('');
  };

  return (
    <div className="review-bubble-card" role="region" aria-label="段落审阅批注详情">
      <div className="review-bubble-card-head">
        <strong>
          <Icon name="comment" />
          段落审阅批注 · <span className="muted" style={{ fontWeight: 'normal' }}>{blockLabel}</span>
        </strong>
        <div className="row" style={{ gap: '8px' }}>
          <span className={`badge ${hasPending ? 'warn pulse' : 'ok'}`} style={{ fontSize: '11px' }}>
            {hasPending ? `${pendingComments.length} 条待处理` : '已全部解决'}
          </span>
          <button
            className="button icon-only tiny quiet"
            onClick={onClose}
            title="收起批注面板"
          >
            <Icon name="close" />
          </button>
        </div>
      </div>

      <div className="review-bubble-card-body">
        {comments.length > 0 ? (
          comments.map((c) => (
            <div className="comment-thread-item" key={c.id} id={`comment-${c.id}`}>
              <div className="comment-author-row">
                <div className="row" style={{ gap: '8px' }}>
                  <div className="comment-avatar">{c.author.slice(0, 1)}</div>
                  <div>
                    <strong style={{ fontSize: '13px' }}>{c.author}</strong>
                    <span
                      className="badge neutral"
                      style={{ fontSize: '10px', marginLeft: '4px', padding: '1px 5px' }}
                    >
                      {c.role}
                    </span>
                  </div>
                </div>
                <div className="row" style={{ gap: '6px' }}>
                  <span className="muted" style={{ fontSize: '11px' }}>{c.time}</span>
                  <span
                    className={`badge ${c.status === 'pending' ? 'warn' : c.status === 'adopted' ? 'ok' : 'neutral'}`}
                    style={{ fontSize: '10px' }}
                  >
                    {c.status === 'pending' ? '待处理' : c.status === 'adopted' ? '已采纳' : '已解决'}
                  </span>
                </div>
              </div>

              <p className="comment-text">{c.text}</p>

              {c.suggestedText && (
                <div className="suggested-diff-box">
                  <div className="suggested-diff-header">
                    <Icon name="sparkles" /> 建议修改为：
                  </div>
                  <div className="suggested-diff-body">{c.suggestedText}</div>
                  {c.status === 'pending' ? (
                    <button
                      className="button tiny primary"
                      onClick={() => adoptComment(blockId, c.id)}
                      style={{ marginTop: '8px' }}
                    >
                      <Icon name="check" />直接采纳并更新正文
                    </button>
                  ) : (
                    <span className="badge ok" style={{ fontSize: '10px', marginTop: '6px', display: 'inline-block' }}>
                      <Icon name="check" />修改已采纳并同步正文
                    </span>
                  )}
                </div>
              )}

              {c.replies && c.replies.length > 0 && (
                <div className="comment-replies">
                  {c.replies.map((r, i) => (
                    <div key={i} style={{ fontSize: '12px', lineHeight: 1.5 }}>
                      <strong style={{ color: 'var(--dm-color-text)' }}>{r.author}</strong>
                      <span className="muted" style={{ fontSize: '11px', marginLeft: '4px' }}>
                        {r.time}
                      </span>
                      <p style={{ color: 'var(--dm-color-text-secondary)', marginTop: '2px' }}>
                        {r.text}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              <div className="comment-actions-bar">
                <button
                  className="button tiny quiet"
                  onClick={() => toggleResolveComment(blockId, c.id)}
                >
                  <Icon name="check" />
                  {c.status === 'resolved' ? '恢复为待处理' : '标记已解决'}
                </button>
                <button
                  className="button tiny quiet"
                  onClick={() => openDrawer('editor', { id: currentPage })}
                >
                  <Icon name="edit" />在抽屉中编辑
                </button>
                <button
                  className="button tiny quiet"
                  onClick={() => deleteComment(blockId, c.id)}
                  style={{ color: 'var(--dm-color-danger)' }}
                >
                  <Icon name="trash" />删除
                </button>
              </div>
            </div>
          ))
        ) : (
          <p className="muted" style={{ fontSize: '13px', textAlign: 'center', padding: '12px 0' }}>
            当前段落暂无批注，可在下方直接发表意见。
          </p>
        )}
      </div>

      <div className="review-bubble-card-foot">
        <form onSubmit={handleSubmit} className="new-comment-box">
          <textarea
            className="new-comment-textarea"
            rows={2}
            placeholder="在此段落记录修改建议、审阅意见或回复..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="row between">
            <div className="row" style={{ gap: '6px' }}>
              <span className="muted" style={{ fontSize: '11px' }}>身份：</span>
              <select
                className="select-filter"
                value={roleSelection}
                onChange={(e) => setRoleSelection(e.target.value)}
                style={{ minHeight: '24px', padding: '1px 20px 1px 8px', fontSize: '11px' }}
              >
                <option value="业务架构师|李凡">李凡 (业务架构师)</option>
                <option value="视觉审核|陈林">陈林 (视觉审核)</option>
                <option value="项目决策者|赵总">赵总 (项目决策者)</option>
                <option value="策划编排|张工">张工 (策划编排)</option>
              </select>
            </div>
            <button type="submit" className="button tiny primary">
              <Icon name="send" />发送批注
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
