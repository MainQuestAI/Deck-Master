import React from 'react';
import { collectContentIds, createParagraph, createBullets, createTable, moveIndex } from '../../content-structure.js';
import { Field, ItemFields, ListActions } from './EditorFields';
import TableEditor from './TableEditor';

export default function ContentEditor({ content, change }) {
  const blocks = content.body_blocks || [];
  const usedIds = collectContentIds(content);
  const changeBlocks = body_blocks => change({ ...content, body_blocks });
  const blockChange = (index, next) => changeBlocks(blocks.map((block, i) => i === index ? next : block));
  return <>
    <Field label="页面标题" value={content.title} onChange={title => change({ ...content, title })} />
    <Field label="副标题" value={content.subtitle} onChange={subtitle => change({ ...content, subtitle })} />
    {blocks.map((block, index) => <section className="s4-panel" key={block.id || index} aria-label={`正文块 ${index + 1}`}>
      <h3>{index + 1}. {{ paragraph: '段落', bullets: '要点', table: '表格' }[block.type]}</h3>
      <ListActions label={`正文块 ${index + 1}`} index={index} length={blocks.length}
        move={to => changeBlocks(moveIndex(blocks, index, to))}
        remove={() => changeBlocks(blocks.filter((_, i) => i !== index))} removeLabel={`移除正文块 ${index + 1}（含全部内容）`} />
      {block.type === 'paragraph' && <Field label={`正文段落 ${index + 1}`} value={block.text} multiline onChange={text => blockChange(index, { ...block, text })} />}
      {block.type === 'bullets' && <>
        <Field label={`要点标题 ${index + 1}`} value={block.heading} onChange={heading => blockChange(index, { ...block, heading })} />
        <ItemFields items={block.items} label={`要点组 ${index + 1}`} usedIds={usedIds} change={items => blockChange(index, { ...block, items })} />
      </>}
      {block.type === 'table' && <TableEditor table={block} label={`表格 ${index + 1}`} usedIds={usedIds} change={next => blockChange(index, next)} />}
    </section>)}
    <div className="row head-actions s4-actions">
      {[[createParagraph, '添加正文段落'], [createBullets, '添加要点'], [createTable, '添加表格']].map(([create, label]) =>
        <button type="button" className="button" key={label} onClick={() => changeBlocks([...blocks, create(usedIds)])}>{label}</button>)}
    </div>
    {['labels', 'callouts', 'footnotes'].map((key, index) => <section key={key}>
      <h3>{['标签', '补充', '脚注'][index]}</h3>
      <ItemFields items={content[key] || []} label={['标签', '补充', '脚注'][index]} usedIds={usedIds} change={items => change({ ...content, [key]: items })} />
    </section>)}
  </>;
}
