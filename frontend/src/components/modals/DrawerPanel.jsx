import React, { useEffect, useRef } from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
import PageContent from '../common/PageContent';

function Field({ label, value, onChange, multiline = false }) {
  return <label className="form-group s4-field"><span>{label}</span>{multiline ? <textarea rows={3} value={value || ''} onChange={event => onChange(event.target.value)} /> : <input value={value || ''} onChange={event => onChange(event.target.value)} />}</label>;
}
function ItemFields({ items, change, label }) {
  return items.map((item, index) => <div key={item.id || index}>
    <Field label={`${label} ${index + 1}`} value={item.text} multiline onChange={text => change(items.map((entry, i) => i === index ? { ...entry, text } : entry))} />
    {item.children?.length > 0 && <ItemFields items={item.children} label={`${label} ${index + 1} 子项`} change={children => change(items.map((entry, i) => i === index ? { ...entry, children } : entry))} />}
  </div>);
}
function ContentFields({ content, change }) {
  const blockChange = (index, patch) => change({ ...content, body_blocks: content.body_blocks.map((block, i) => i === index ? { ...block, ...patch } : block) });
  return <>
    <Field label="页面标题" value={content.title} onChange={title => change({ ...content, title })} />
    <Field label="副标题" value={content.subtitle} onChange={subtitle => change({ ...content, subtitle })} />
    {content.body_blocks.map((block, index) => <div key={block.id || index}>
      {block.type === 'paragraph' && <Field label={`正文段落 ${index + 1}`} value={block.text} multiline onChange={text => blockChange(index, { text })} />}
      {block.type === 'bullets' && <><Field label={`要点标题 ${index + 1}`} value={block.heading} onChange={heading => blockChange(index, { heading })} /><ItemFields items={block.items} label={`要点组 ${index + 1}`} change={items => blockChange(index, { items })} /></>}
      {block.type === 'table' && <><Field label={`表格标题 ${index + 1}`} value={block.title} onChange={title => blockChange(index, { title })} />
        {block.columns.map((column, c) => <Field key={column.id} label={`列标题 ${c + 1}`} value={column.label} onChange={label => blockChange(index, { columns: block.columns.map((item, i) => i === c ? { ...item, label } : item) })} />)}
        {block.rows.map((row, r) => row.cells.map((cell, c) => <Field key={cell.id} label={`表格 ${index + 1} 第 ${r + 1} 行 ${block.columns.find(column => column.id === cell.column_id)?.label || c + 1}`} value={cell.display_text} multiline onChange={display_text => blockChange(index, { rows: block.rows.map((item, i) => i === r ? { ...item, cells: item.cells.map((entry, j) => j === c ? { ...entry, display_text } : entry) } : item) })} />))}</>}
    </div>)}
    <button type="button" className="button" onClick={() => change({ ...content, body_blocks: [...content.body_blocks, { type: 'paragraph', text: '' }] })}>添加正文段落</button>
    {['labels', 'callouts', 'footnotes'].map((key, index) => <ItemFields key={key} items={content[key] || []} label={['标签', '强调', '脚注'][index]} change={items => change({ ...content, [key]: items })} />)}
  </>;
}

export default function DrawerPanel() {
  const { drawer, closeDrawer, drafts, currentPage, updateDraft, saveDraft, rebaseDraft, discardDraft, workspace, busy, restore, actionError } = useDeckMaster();
  const panel = useRef(null);
  useEffect(() => {
    if (!drawer) return;
    const previous = document.activeElement;
    panel.current?.focus();
    const keydown = event => {
      if (event.key === 'Escape') closeDrawer();
      if (event.key === 'Tab') {
        const controls = [...panel.current.querySelectorAll('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), summary')];
        const first = controls[0];
        const last = controls.at(-1);
        if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener('keydown', keydown);
    return () => { document.removeEventListener('keydown', keydown); previous?.focus(); };
  }, [drawer]);
  if (!drawer || !workspace) return null;
  const draft = drafts[currentPage];
  const page = draft?.page;
  return <div className="drawer-backdrop open"><section ref={panel} tabIndex={-1} className="drawer-panel open wide" role="dialog" aria-modal="true" aria-label={drawer === 'history' ? '版本历史与恢复' : '修改正文与讲稿'}>
    <div className="drawer-head"><h2>{drawer === 'history' ? '版本历史与恢复' : '修改正文与讲稿'}</h2><button className="button" onClick={closeDrawer}>{drawer === 'editor' ? '收起并保留输入' : '关闭'}</button></div>
    <div className="drawer-body">
      {actionError && <p className="s4-message" role="alert">{actionError}</p>}
      {drawer === 'history' ? <>{workspace.history.map(version => <article key={version.id} className="s4-panel"><h3>版本 {version.id}{version.id === workspace.version && ' · 当前'}</h3><p>{version.created_at}</p><p className="s4-wrap">{version.summary}</p><button className="button" disabled={busy.restore || version.id === workspace.version} onClick={() => restore(version.id)}>恢复此版本</button></article>)}</> : page && <>
        {draft.conflict && <section className="s4-message" role="alert"><h3>保存冲突，您的输入仍保留</h3><p>当前内容已被修改。比较后，可基于当前版本再次保存；不会自动覆盖。</p>
          {(() => { const current = workspace.deck.pages.find(item => item.id === page.id); return <details><summary>查看当前保存内容（版本 {workspace.version}）</summary>{current ? <><PageContent content={current.content} /><p>讲稿：{current.notes}</p><p>目的：{current.purpose}</p><p>布局：{current.layout}</p></> : <p>页面已移除或页序已改变。请保留输入，返回作品核对。</p>}</details>; })()}
          <button className="button" disabled={!workspace.deck.pages.some(item => item.id === page.id)} onClick={rebaseDraft}>保留我的修改，以当前版本继续</button>
        </section>}
        <fieldset disabled={busy.save} className="s4-fieldset"><ContentFields content={page.content} change={content => updateDraft({ ...page, content })} />
          <Field label="本页目的" value={page.purpose} onChange={purpose => updateDraft({ ...page, purpose })} />
          <Field label="版式要求" value={page.layout} onChange={layout => updateDraft({ ...page, layout })} />
          <Field label="讲稿" value={page.notes} multiline onChange={notes => updateDraft({ ...page, notes })} />
        </fieldset>
      </>}
    </div>
    {drawer === 'editor' && page && <div className="drawer-foot"><button className="button" disabled={busy.save} onClick={discardDraft}>放弃本地修改</button><button className="primary" disabled={busy.save || !!draft.conflict} onClick={saveDraft}>{busy.save ? '正在保存…' : '保存正文与讲稿'}</button></div>}
  </section></div>;
}
