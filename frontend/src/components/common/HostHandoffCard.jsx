import React, { useEffect, useState } from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';

const PAGE_INTENTS = [
  { id: 'fill_content', label: '补齐内容/论证' },
  { id: 'redraw_image', label: '重绘原图' },
  { id: 'rebuild_editable', label: '按原图重做可编辑页' },
];

const DECK_INTENTS = [
  { id: 'fill_content', label: '补齐内容/论证' },
  { id: 'redraw_image', label: '重绘原图' },
  { id: 'rebuild_editable', label: '按原图重做可编辑页' },
];

export function buildHostInstruction({ pageId, pageTitle, pageNumStr, intentLabel, note, reviewId }) {
  const scope = pageId
    ? `第 ${pageNumStr || pageId} 页（${pageId}${pageTitle ? ` · ${pageTitle}` : ''}）`
    : '整份作品';
  const lines = [
    `请在当前项目中处理「${intentLabel}」（范围：${scope}）。`,
  ];
  if (note.trim()) {
    lines.push(`作者说明：${note.trim()}`);
  }
  if (reviewId != null) {
    lines.push(`已记录审阅意见 #${reviewId}，请用 deck review list 查看后执行。`);
  } else {
    lines.push('请先用 deck review list 查看最新未处理意见后再执行。');
  }
  return lines.join('\n');
}

export default function HostHandoffCard({ pageId = null, pageTitle = '', pageNumStr = '', defaultIntent = 'fill_content', autoExpand = false }) {
  const { addReview, busy } = useDeckMaster();
  const intents = pageId ? PAGE_INTENTS : DECK_INTENTS;
  const [open, setOpen] = useState(autoExpand);
  const [intent, setIntent] = useState(defaultIntent);
  const [note, setNote] = useState('');
  const [instruction, setInstruction] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (autoExpand) {
      setOpen(true);
      setIntent(defaultIntent);
    }
  }, [autoExpand, defaultIntent]);

  const scope = pageId ? `page:${pageId}` : 'deck';
  const saving = !!busy[`review-add-${scope}`];
  const currentIntent = intents.find(item => item.id === intent) || intents[0];

  const submitHandoff = async event => {
    event.preventDefault();
    const reviewText = `[交给 Host · ${currentIntent.label}]${note.trim() ? ` ${note.trim()}` : ''}`;
    const review = await addReview(reviewText, pageId || undefined);
    if (!review) return;
    setInstruction(buildHostInstruction({
      pageId,
      pageTitle,
      pageNumStr,
      intentLabel: currentIntent.label,
      note,
      reviewId: review.id,
    }));
    setCopied(false);
    setNote('');
  };

  const copyInstruction = async () => {
    try {
      await navigator.clipboard?.writeText(instruction);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return <section id="host-handoff" className="s4-panel" aria-label={pageId ? '本页交给 Host' : '整稿交给 Host'}>
    <div className="row between">
      <div>
        <h2>{pageId ? '交给 Host 处理本页' : '交给 Host 继续制作'}</h2>
        <p className="muted">选择制作意图并写入人工意见，生成可复制的 Host 指令。</p>
      </div>
      <button type="button" className="button" aria-expanded={open} onClick={() => setOpen(value => !value)}>
        {open ? '收起交给 Host' : '交给 Host'}
      </button>
    </div>
    {open && <>
      <form onSubmit={submitHandoff}>
        <label className="form-group s4-field">
          <span>交接意图</span>
          <select value={intent} disabled={saving} onChange={event => setIntent(event.target.value)}>
            {intents.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </label>
        <label className="form-group s4-field">
          <span>给 Host 的补充说明</span>
          <textarea
            rows={2}
            value={note}
            disabled={saving}
            placeholder="例如：把第二栏改成对比表，或重绘信息图并保留现有结论"
            onChange={event => setNote(event.target.value)}
          />
        </label>
        <div className="head-actions s4-actions">
          <button type="submit" className="primary" disabled={saving}>
            {saving ? '正在写入意见…' : '写入意见并生成 Host 指令'}
          </button>
        </div>
      </form>
      {instruction && <section className="s4-panel" aria-label="可复制的 Host 指令">
        <div className="row between">
          <strong>Host 指令</strong>
          <button type="button" className="button tiny" onClick={copyInstruction}>
            {copied ? '已复制指令' : '复制指令'}
          </button>
        </div>
        <pre className="s4-reading">{instruction}</pre>
        <p className="muted">注意：复制指令不会自动启动生成，请粘贴到当前 Host 会话中继续执行。</p>
      </section>}
    </>}
  </section>;
}
