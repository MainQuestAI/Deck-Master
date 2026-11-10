import { isPageDraftDirty } from '../../api.js';
import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
import PageContent from '../common/PageContent';
import ContentEditor from '../editor/ContentEditor';
import { Field, TextList } from '../editor/EditorFields';
import useDialogFocus from './useDialogFocus';
import HistoryPanel from '../history/HistoryPanel.jsx';

export default function DrawerPanel() {
  const { drawer, closeDrawer, drafts, currentPage, updateDraft, saveDraft, rebaseDraft, discardDraft, workspace, busy, actionError } = useDeckMaster();
  const panel = useDialogFocus(!!(drawer && workspace), closeDrawer);
  if (!drawer || !workspace) return null;
  const draft = drafts[currentPage];
  const page = draft?.page;
  const deleted = page && !workspace.deck.pages.some(item => item.id === page.id);
  const title = drawer === 'history' ? '版本历史与正文对比' : deleted ? '查看未保存输入' : '修改正文与讲稿';
  return <div className="drawer-backdrop open"><section ref={panel} tabIndex={-1} className="drawer-panel open wide" role="dialog" aria-modal="true" aria-label={title}>
    <div className="drawer-head"><h2>{title}</h2><button className="button" onClick={closeDrawer}>{drawer === 'editor' ? '收起并保留输入' : '关闭'}</button></div>
    <div className="drawer-body">
      {actionError && <p className="s4-message" role="alert">{actionError}</p>}
      {drawer === 'history' ? <HistoryPanel /> : deleted ? <>
        <p className="s4-message">当前页面已不存在。以下输入只读，可选中复制，转移后再放弃。</p>
        <PageContent content={page.content} />
        <Field label="本页目的" value={page.purpose} multiline readOnly />
        <Field label="版式要求" value={page.layout} multiline readOnly />
        <Field label="讲稿" value={page.notes} multiline readOnly />
      </> : page && <>
        {draft.conflict && <section className="s4-message" role="alert"><h3>保存冲突，您的输入仍保留</h3><p>当前内容已被修改。比较后，可基于当前版本再次保存；不会自动覆盖。</p>
          {(() => { const current = workspace.deck.pages.find(item => item.id === page.id); return <details><summary>查看当前保存内容（版本 {workspace.version}）</summary>{current ? <><PageContent content={current.content} /><p>讲稿：{current.notes}</p><p>目的：{current.purpose}</p><p>布局：{current.layout}</p></> : <p>页面已移除或页序已改变。请保留输入，返回作品核对。</p>}</details>; })()}
          <p>继续保存会用您打开时的正文替换当前正文，请先在上方对比。</p>
          <button className="button" disabled={!workspace.deck.pages.some(item => item.id === page.id)} onClick={rebaseDraft}>保留我的修改，以当前版本继续</button>
        </section>}
        <fieldset disabled={busy.save} className="s4-fieldset"><ContentEditor content={page.content} change={content => updateDraft({ ...page, content })} />
          <Field label="本页目的" value={page.purpose} onChange={purpose => updateDraft({ ...page, purpose })} />
          <Field label="版式要求" value={page.layout} onChange={layout => updateDraft({ ...page, layout })} />
          <Field label="讲稿" value={page.notes} multiline onChange={notes => updateDraft({ ...page, notes })} />
          <TextList label="待补" items={page.todo} change={todo => updateDraft({ ...page, todo })} />
          <TextList label="出处" items={page.refs} change={refs => updateDraft({ ...page, refs })} />
        </fieldset>
      </>}
    </div>
    {drawer === 'editor' && page && <div className="drawer-foot"><button className="button" disabled={busy.save} onClick={() => { if ((!deleted && !draft.conflict && !isPageDraftDirty(draft)) || window.confirm('确定放弃本地修改？未保存的输入将丢失。')) discardDraft(); }}>放弃本地修改</button>{!deleted && <button className="primary" disabled={busy.save || !!draft.conflict} onClick={saveDraft}>{busy.save ? '正在保存…' : '保存正文与讲稿'}</button>}</div>}
  </section></div>;
}
