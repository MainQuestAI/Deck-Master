import React, { useState } from 'react';
import Icon from '../common/Icon';
import { contextUnitPatch } from '../../api.js';
import { BRIEF_FIELDS, FRAMING_FIELDS, PAGE_KIND_LABELS, missingContextHints } from '../../schema/fields.js';
import FieldConflictDiff from '../common/FieldConflictDiff';
import HostHandoffCard from '../common/HostHandoffCard';
import ReviewPanel from '../common/ReviewPanel';
import { useDeckMaster } from '../../context/DeckMasterContext';

function Field({ label, value, onChange, multiline = false, ...props }) {
  return <label className="form-group s4-field"><span>{label}</span>{multiline
    ? <textarea rows={3} value={value ?? ''} onChange={event => onChange(event.target.value)} {...props} />
    : <input type="text" value={value ?? ''} onChange={event => onChange(event.target.value)} {...props} />}</label>;
}

function move(items, index, offset) {
  const next = [...items];
  [next[index], next[index + offset]] = [next[index + offset], next[index]];
  return next;
}

function ListActions({ label, items, index, change }) {
  return <div className="row head-actions">
    <button className="button" type="button" aria-label={`${label}上移`} disabled={index === 0} onClick={() => change(move(items, index, -1))}>上移</button>
    <button className="button" type="button" aria-label={`${label}下移`} disabled={index === items.length - 1} onClick={() => change(move(items, index, 1))}>下移</button>
    <button className="button" type="button" aria-label={`移除${label}`} onClick={() => change(items.filter((_, i) => i !== index))}>移除</button>
  </div>;
}

function TextList({ label, items = [], change, hint = '' }) {
  return <section className="form-group">
    <h3>{label}</h3>
    {hint && <p className="muted">{hint}</p>}
    {items.map((item, index) => <div className="s4-panel" key={index}>
      <Field label={`${label} ${index + 1}`} value={item} onChange={text => change(items.map((value, i) => i === index ? text : value))} />
      <ListActions label={`${label} ${index + 1}`} items={items} index={index} change={change} />
    </div>)}
    <button className="button" type="button" onClick={() => change([...items, ''])}>添加{label}</button>
  </section>;
}

function ReadList({ label, items }) {
  return <section><h3>{label}</h3>{items.length ? <ul>{items.map((item, index) => <li key={index}>{item || '（空条目）'}</li>)}</ul> : <p className="muted">尚未填写</p>}</section>;
}

function BriefReading({ value }) {
  const narrator = [value.narrator?.role, value.narrator?.tone].filter(Boolean).join(' · ');
  return <div className="s4-reading">
    {[
      ['作品标题', value.title],
      ['本次面向谁', value.audience],
      ['本次任务', value.task_type],
      ['希望对方理解或做出什么判断', value.goal],
      ['待决事项', value.decision],
      ['讲述人与语气', narrator],
    ].map(([label, text]) => <section key={label}><h3>{label}</h3><p>{text || '尚未填写'}</p></section>)}
    <ReadList label="读者关注点" items={value.concerns || []} />
    <ReadList label="已有决定与实际约束" items={value.constraints || []} />
    <section><h3>页数上限</h3><p>{value.page_limit ?? '未设置'}</p></section>
  </div>;
}

function FramingReading({ value, expanded = false }) {
  return <div className="s4-reading">
    <section><h3>中心主张</h3><p>{value.thesis || '尚未填写中心主张'}</p></section>
    <ReadList label="故事主线" items={value.storyline || []} />
    <section><h3>业务框架分组</h3>{(value.pillars || []).length ? value.pillars.map((pillar, index) => <section key={index}><h4>{pillar.title || '未命名分组'}</h4>{pillar.points.length ? <ul>{pillar.points.map((point, i) => <li key={i}>{point || '（空支持点）'}</li>)}</ul> : <p className="muted">尚无支持点</p>}</section>) : <p className="muted">尚无框架分组，可直接添加</p>}</section>
    <details open={expanded}><summary>事实、假设与待回答问题</summary>
      <ReadList label="已知事实" items={value.facts || []} />
      <ReadList label="当前假设" items={value.assumptions || []} />
      <ReadList label="待回答问题" items={value.questions || []} />
    </details>
  </div>;
}

function BriefFields({ value, change }) {
  const field = key => next => change({ ...value, [key]: next });
  const narratorField = key => next => change({
    ...value,
    narrator: { role: value.narrator?.role ?? '', tone: value.narrator?.tone ?? '', [key]: next },
  });
  return <>
    <Field label="作品标题" value={value.title} onChange={field('title')} />
    <Field label="本次面向谁" value={value.audience} onChange={field('audience')} multiline />
    <Field label="本次任务" value={value.task_type} onChange={field('task_type')} list="context-task-types" />
    <datalist id="context-task-types">{['首提', '竞标', '汇报'].map(text => <option key={text} value={text} />)}</datalist>
    <Field label="希望对方理解或做出什么判断" value={value.goal} onChange={field('goal')} multiline />
    <Field label="待决事项" value={value.decision} onChange={field('decision')} multiline />
    <TextList
      label="读者关注点"
      items={value.concerns || []}
      change={field('concerns')}
      hint="建议聚焦 1–3 条核心关注点，不限制保存。"
    />
    <Field label="讲述人角色" value={value.narrator?.role ?? ''} onChange={narratorField('role')} />
    <Field label="讲述语气" value={value.narrator?.tone ?? ''} onChange={narratorField('tone')} />
    <TextList label="已有决定与实际约束" items={value.constraints || []} change={field('constraints')} />
    <Field label="页数上限（可留空）" type="number" min="0" max="4294967295" step="1" value={value.page_limit} onChange={text => field('page_limit')(text === '' ? null : Number(text))} />
  </>;
}

function FramingFields({ value, change }) {
  const field = key => next => change({ ...value, [key]: next });
  return <>
    <Field label="中心主张" value={value.thesis} onChange={field('thesis')} multiline />
    <TextList label="故事主线" items={value.storyline || []} change={field('storyline')} />
    <h3>业务框架分组</h3>
    {(value.pillars || []).map((pillar, index) => {
      const changePillar = next => field('pillars')(value.pillars.map((item, i) => i === index ? next : item));
      return <section className="s4-panel" key={index}>
        <Field label={`分组 ${index + 1} 标题`} value={pillar.title} onChange={title => changePillar({ ...pillar, title })} />
        <TextList label={`分组 ${index + 1} 支持点`} items={pillar.points} change={points => changePillar({ ...pillar, points })} />
        <ListActions label={`分组 ${index + 1}`} items={value.pillars} index={index} change={field('pillars')} />
      </section>;
    })}
    <button className="button" type="button" onClick={() => field('pillars')([...(value.pillars || []), { title: '', points: [] }])}>添加分组</button>
    <details><summary>编辑事实、假设与待回答问题</summary>
      <TextList label="已知事实" items={value.facts || []} change={field('facts')} />
      <TextList label="当前假设" items={value.assumptions || []} change={field('assumptions')} />
      <TextList label="待回答问题" items={value.questions || []} change={field('questions')} />
    </details>
  </>;
}

function DerivedSummaryPanel({ workspace, openPage, getPageNumStr }) {
  const writingBrief = workspace.writing_brief || '';
  const outline = workspace.outline || [];
  const gapList = workspace.gap_list || [];
  return <details className="s4-panel" aria-label="写作简报、提纲与缺口汇总">
    <summary>写作简报、提纲与缺口汇总（只读）</summary>
    <div className="s4-reading">
      <section>
        <h3>写作简报</h3>
        {writingBrief ? <pre className="s4-reading">{writingBrief}</pre> : <p className="muted">尚未生成写作简报（补齐讲述人、待决事项或读者关注点后自动生成）。</p>}
      </section>
      <section>
        <h3>提纲</h3>
        {outline.length ? <ul>{outline.map((item, index) => <li key={item.page_id || index}>
          <button className="page-entry-link" type="button" onClick={() => openPage(item.page_id)}>
            <span className="p-no num">{getPageNumStr(item.page_id)}</span>
            {item.title || '未命名页面'}
          </button>
          {item.kind && <span className="badge neutral">{PAGE_KIND_LABELS[item.kind] || item.kind}</span>}
        </li>)}</ul> : <p className="muted">暂无页面提纲。</p>}
      </section>
      <section>
        <h3>缺口清单</h3>
        {gapList.length ? <ul>{gapList.map((item, index) => <li key={`${item.page_id}-${item.source}-${index}`}>
          <button className="button tiny quiet" type="button" onClick={() => openPage(item.page_id)}>第 {getPageNumStr(item.page_id)} 页</button>
          {' '}
          <span className="badge warn">{item.source === 'evidence' ? '证据缺口' : '待补'}</span>
          {' '}
          <span>{item.text}{item.gap ? ` — ${item.gap}` : ''}</span>
        </li>)}</ul> : <p className="muted">当前无待补缺口。</p>}
      </section>
    </div>
  </details>;
}

function ContextSection({ kind, title, Reading, Fields }) {
  const { workspace, contextDrafts, openContextEdit, updateContextDraft, saveContext, refreshContextConflict, resolveContextConflict, busy } = useDeckMaster();
  const [editing, setEditing] = useState(false);
  const draft = contextDrafts[kind];
  const saving = busy[`save-${kind}`];
  const current = draft?.conflict?.snapshot?.deck[kind]
    ?? draft?.conflict?.conflicts?.find(conflict => conflict.unit === kind)?.current;
  return <section className="s4-panel" aria-label={title}>
    <div className="row between"><h2>{title}</h2><button className="button" aria-expanded={editing} aria-controls={`context-${kind}`} disabled={saving} onClick={() => { if (!editing) openContextEdit(kind); setEditing(value => !value); }}>{editing ? '收起编辑' : `编辑${title}`}</button></div>
    {!editing && <>
      <Reading value={workspace.deck[kind]} />
      {draft && contextUnitPatch(kind, draft) && <p role="status">有未保存的输入，打开编辑可继续。</p>}
    </>}
    {editing && draft && <div id={`context-${kind}`}>
      {draft.error && <p className="s4-message" role="alert">{draft.error}</p>}
      {draft.conflict && <section className="s4-message" role="alert">
        <h3>{title}保存冲突，您的输入仍保留</h3>
        <p>请核对差异字段。可逐项选择“保留我的”或“采用当前”合并，也可整单元处理后再保存。</p>
        <FieldConflictDiff
          base={draft.original}
          server={current}
          mine={draft.value}
          fieldLabels={kind === 'brief' ? BRIEF_FIELDS : FRAMING_FIELDS}
          disabled={saving || !draft.conflict.snapshot}
          applyLabel="按所选字段合并，核对后再保存"
          onApply={merged => resolveContextConflict(kind, true, merged)}
        />
        <details>
          <summary>查看完整单元对照</summary>
          <section className="s4-panel" aria-label="服务器当前整单元"><h4>服务器当前整单元</h4>{current ? <Reading value={current} expanded /> : <p>尚未读取当前内容，请重试读取。</p>}</section>
          <section className="s4-panel" aria-label="我的整单元"><h4>我的整单元</h4><Reading value={draft.value} expanded /></section>
        </details>
        <div className="head-actions">
          {!draft.conflict.snapshot && <button className="button" disabled={saving} onClick={() => refreshContextConflict(kind)}>重新读取服务器当前内容</button>}
          <button className="button" disabled={saving || !draft.conflict.snapshot} onClick={() => resolveContextConflict(kind, false)}>采用服务器当前整单元</button>
          <button className="button" disabled={saving || !draft.conflict.snapshot} onClick={() => resolveContextConflict(kind, true)}>保留我的整单元，核对后再保存</button>
        </div>
      </section>}
      <form onSubmit={event => { event.preventDefault(); saveContext(kind); }}>
        <fieldset className="s4-fieldset" disabled={saving}><Fields value={draft.value} change={next => updateContextDraft(kind, next)} /></fieldset>
        {(() => {
          const hints = missingContextHints(kind, draft.value);
          return hints.length > 0 && <p className="muted">待补提示（不影响保存）：{hints.join('、')}</p>;
        })()}
        <div className="head-actions s4-actions">
          <span role="status">{contextUnitPatch(kind, draft) ? '有未保存的输入' : '没有未保存的修改'}</span>
          <button className="button" type="submit" disabled={saving || !!draft.conflict || !contextUnitPatch(kind, draft)}>{saving ? '正在保存…' : `保存${title}`}</button>
        </div>
      </form>
    </div>}
  </section>;
}

export default function OverviewView() {
  const { pages, workspace, query, setQuery, openPage, openPageReviews, createPage, busy, openDrawer, setScene, getPageNumStr } = useDeckMaster();
  const status = workspace.artifact_status;
  const filtered = pages.filter(page => page.content.title.includes(query));
  const openReviewCount = page => page.open_reviews ?? (workspace.reviews || []).filter(review => review.page_id === page.id).length;
  return <div>
    <div className="view-head"><div><h1>制作总览</h1><p>浏览当前作品，修改内容并继续制作。</p></div><div className="head-actions"><button className="button" onClick={() => openDrawer('history')}><Icon name="layers" />版本历史记录</button><button className="button" onClick={createPage} disabled={busy.create}>新增页面</button></div></div>
    <ContextSection kind="brief" title="任务信息" Reading={BriefReading} Fields={BriefFields} />
    <ContextSection kind="framing" title="业务框架" Reading={FramingReading} Fields={FramingFields} />
    <DerivedSummaryPanel workspace={workspace} openPage={openPage} getPageNumStr={getPageNumStr} />
    <div className="metric-summary">
      {[
        [pages.length, '逐页稿'],
        [pages.filter(page => page.image).length, '原图'],
        [pages.filter(page => page.svg || page.native).length, status.build_mode === 'native' ? '原生还原' : status.build_mode === 'mixed' ? '可编辑页（混合）' : 'SVG'],
        [workspace.runs.filter(run => run.status === 'open').length, '进行中任务'],
      ].map(([value, label]) => <div className="metric-item" key={label}><strong>{value}</strong><p>{label}</p></div>)}
    </div>
    <section className="next-banner"><div className="mark-icon"><Icon name="page" /></div><div className="grow"><h2>{pages.length ? '查看逐页稿并继续制作' : '作品还是空的'}</h2><p>{pages.length ? '正文、讲稿与产物按页保存。' : '新增第一页，开始写正文与讲稿。'}</p></div><button className="primary" disabled={busy.create} onClick={() => pages.length ? openPage(pages[0].id) : createPage()}>{pages.length ? '进入制作' : '新增第一页'}</button></section>
    <HostHandoffCard />
    {pages.length > 0 && <>
      <div className="toolbar"><label className="search-box"><Icon name="search" /><input aria-label="搜索页面" placeholder="搜索页名" value={query} onChange={event => setQuery(event.target.value)} /></label><button className="button" onClick={() => setScene('delivery')}>任务与下载</button></div>
      <div className="matrix-container"><table className="matrix-table"><thead><tr><th>页面</th><th>原图</th><th>{status.build_mode === 'native' ? '原生还原' : status.build_mode === 'mixed' ? '可编辑页' : 'SVG'}</th><th>待处理意见</th><th>操作</th></tr></thead><tbody>{filtered.map(page => {
        const count = openReviewCount(page);
        const editableLabel = !(page.svg || page.native)
          ? '未制作'
          : status.stale_pages.includes(page.id)
            ? '依据已变'
            : page.native && !page.svg
              ? '原生已采用'
              : page.native && page.svg
                ? '混合已采用'
                : '已采用';
        return <tr key={page.id}>
          <td><button className="page-entry-link" onClick={() => openPage(page.id)}><span className="p-no num">{getPageNumStr(page.id)}</span>{page.content.title || '未命名页面'}</button></td>
          <td><span className={`badge ${status.stale_images.includes(page.id) ? 'warn' : 'neutral'}`}>{!page.image ? '未制作' : status.stale_images.includes(page.id) ? '依据已变' : '已采用'}</span></td>
          <td><span className={`badge ${status.stale_pages.includes(page.id) ? 'warn' : 'neutral'}`}>{editableLabel}</span></td>
          <td>{count > 0 ? <button className="badge warn" type="button" aria-label={`查看第 ${getPageNumStr(page.id)} 页 ${count} 条待处理意见`} onClick={() => openPageReviews(page.id)}>{count} 条意见</button> : <span className="badge neutral">0 条</span>}</td>
          <td><button className="button tiny quiet" onClick={() => openPage(page.id)}>打开</button></td>
        </tr>;
      })}</tbody></table>{filtered.length === 0 && <p className="s4-empty">没有匹配的页面</p>}</div>
    </>}
    <ReviewPanel />
  </div>;
}
