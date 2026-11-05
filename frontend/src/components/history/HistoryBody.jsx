import React from 'react';
import { briefFields, framingFields, pageFields, contentFields, authorPage } from '../../historyDiff.js';

const labels = {
  ...briefFields, ...framingFields, ...pageFields, ...contentFields,
  content: '正文', title: '标题', text: '文字', heading: '要点标题', items: '要点', children: '子项',
  tone: '语气', points: '支持点', columns: '列', rows: '行', cells: '单元格', label: '列标题',
  display_text: '显示文字', value: '原始值', unit: '单位', column_id: '所属列', type: '类型',
};
const types = { paragraph: '段落', bullets: '要点', table: '表格' };

function TableValue({ table }) {
  const columns = table.columns || [];
  const rows = table.rows || [];
  const reliable = columns.every(column => column.id) && new Set(columns.map(column => column.id)).size === columns.length
    && rows.every(row => (row.cells || []).every(cell => columns.some(column => column.id === cell.column_id))
      && new Set((row.cells || []).map(cell => cell.column_id)).size === (row.cells || []).length);
  if (!reliable) return <HistoryValue value={table} plain />;
  return <div>
    <p>{table.title || '未命名表格'}</p>
    <div className="matrix-container"><table className="matrix-table"><thead><tr>{columns.map((column, index) => <th key={index}>{column.label || `列 ${index + 1}`}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{columns.map((column, columnIndex) => {
        const cell = row.cells?.find(item => item.column_id === column.id);
        return <td key={columnIndex}>{cell ? <><HistoryValue value={cell.display_text} />
          {(cell.value != null || cell.unit != null) && <details><summary>原始值 / 单位</summary><HistoryValue value={{ value: cell.value, unit: cell.unit }} /></details>}
        </> : '—'}</td>;
      })}</tr>)}</tbody>
    </table></div>
    {!rows.length && <p>暂无行</p>}
  </div>;
}

export function HistoryValue({ value, plain = false }) {
  if (value == null || value === '') return <span className="history-empty">（空）</span>;
  if (typeof value !== 'object') return <span className="history-text">{String(value)}</span>;
  if (Array.isArray(value)) return value.length ? <ol className="history-items">{value.map((item, index) => <li key={index}><HistoryValue value={item} /></li>)}</ol> : <span className="history-empty">（空）</span>;
  if (!plain && value.type === 'table') return <TableValue table={value} />;
  return <dl className="history-fields">{Object.entries(value).filter(([key]) => key !== 'id').map(([key, item]) => <div key={key}>
    <dt>{labels[key] || key}</dt><dd><HistoryValue value={key === 'type' ? types[item] || item : item} /></dd>
  </div>)}</dl>;
}

export function SnapshotMeta({ version, meta, label }) {
  return <header><h3>{label} · 版本 {version}</h3>{meta?.created_at && <p>{meta.created_at}</p>}{meta?.summary && <p className="s4-wrap">{meta.summary}</p>}</header>;
}

export default function HistoryBody({ deck }) {
  return <div className="s4-reading">
    <section className="s4-panel"><h3>任务信息</h3><HistoryValue value={deck.brief} /></section>
    <section className="s4-panel"><h3>业务框架</h3><HistoryValue value={deck.framing} /></section>
    {(deck.pages || []).map((page, index) => <section className="s4-panel" key={index}>
      <h3>第 {index + 1} 页 · {page.content?.title || '未命名页面'}</h3><HistoryValue value={authorPage(page)} />
    </section>)}
    {!deck.pages?.length && <p>此版本暂无页面</p>}
  </div>;
}
