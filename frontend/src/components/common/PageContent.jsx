import React from 'react';

function Items({ items = [] }) {
  return <ul>{items.map((item, index) => <li key={item.id || index}>{item.text}{item.children?.length > 0 && <Items items={item.children} />}</li>)}</ul>;
}

export default function PageContent({ content }) {
  return <div className="s4-reading">
    <h2>{content.title || '未命名页面'}</h2>
    {content.subtitle && <p className="lead-text">{content.subtitle}</p>}
    {(content.body_blocks || []).map((block, index) => <section key={block.id || index}>
      {block.type === 'paragraph' && <p>{block.text}</p>}
      {block.type === 'bullets' && <><h3>{block.heading}</h3><Items items={block.items} /></>}
      {block.type === 'table' && <><h3>{block.title}</h3><div className="matrix-container"><table className="matrix-table"><thead><tr>{block.columns.map(column => <th key={column.id}>{column.label}</th>)}</tr></thead><tbody>{block.rows.map(row => <tr key={row.id}>{block.columns.map(column => <td key={column.id}>{row.cells.find(cell => cell.column_id === column.id)?.display_text}</td>)}</tr>)}</tbody></table></div></>}
    </section>)}
    {['labels', 'callouts', 'footnotes'].map(key => content[key]?.length > 0 && <Items key={key} items={content[key]} />)}
  </div>;
}
