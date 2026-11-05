import React, { useLayoutEffect, useRef, useState } from 'react';
import {
  addColumn, removeColumn, moveColumn, addRow, removeRow, moveRow,
  setCellDisplayText, setCellValue, setCellUnit,
} from '../../content-structure.js';
import { Field, ListActions } from './EditorFields';

function CellMetadata({ cell, label, changeValue, changeUnit }) {
  const [scalarType] = useState(() => ['string', 'number', 'boolean'].includes(typeof cell.value) ? typeof cell.value : null);
  const complex = cell.value !== null && typeof cell.value === 'object';
  return <details>
    <summary>数值与单位</summary>
    <p className="muted">显示文字不会自动修改原始值或单位。</p>
    {complex ? <><p>复杂原始值仅供查看，修改请交给 Host。</p><pre className="s4-json">{JSON.stringify(cell.value, null, 2)}</pre></>
      : scalarType === 'boolean' ? <label className="form-group s4-field"><span>{label} 原始值（布尔）</span>
        <select value={cell.value == null ? '' : String(cell.value)} onChange={event => changeValue(event.target.value === '' ? null : event.target.value === 'true')}>
          <option value="">已清空</option><option value="true">真</option><option value="false">假</option>
        </select>
      </label>
        : scalarType ? <Field label={`${label} 原始值（${scalarType === 'number' ? '数字' : '文本'}）`} type={scalarType === 'number' ? 'number' : 'text'} step={scalarType === 'number' ? 'any' : undefined}
          value={cell.value} onChange={text => {
            if (scalarType === 'string') changeValue(text);
            else if (text === '') changeValue(null);
            else if (Number.isFinite(Number(text))) changeValue(Number(text));
          }} /> : <p>无原始值</p>}
    {!complex && scalarType && <button className="button" type="button" aria-label={`清空${label}原始值`} onClick={() => changeValue(null)}>清空原始值</button>}
    <Field label={`${label} 单位`} value={cell.unit} onChange={unit => changeUnit(unit === '' ? null : unit)} />
  </details>;
}

export default function TableEditor({ table, label, change, usedIds }) {
  const matrix = useRef(null);
  const focusTarget = useRef(null);
  useLayoutEffect(() => {
    if (!focusTarget.current) return;
    [...matrix.current.querySelectorAll('[data-editor-focus]')].find(node => node.dataset.editorFocus === focusTarget.current)?.focus();
    focusTarget.current = null;
  });
  return <>
    <Field label={`${label} 标题`} value={table.title} onChange={title => change({ ...table, title })} />
    <div className="matrix-container" ref={matrix}>
      <table className="matrix-table s4-structure-table" aria-label={`${label}结构`}>
        <thead><tr>
          {table.columns.map((column, c) => <th scope="col" key={column.id}>
            <Field label={`${label} 列标题 ${c + 1}`} value={column.label} data-editor-focus={column.id}
              onChange={text => change({ ...table, columns: table.columns.map(item => item.id === column.id ? { ...item, label: text } : item) })} />
            <div className="row head-actions">
              <button className="button" type="button" aria-label={`${label} 第 ${c + 1} 列左移`} disabled={c === 0} onClick={() => change(moveColumn(table, column.id, c - 1))}>左移</button>
              <button className="button" type="button" aria-label={`${label} 第 ${c + 1} 列右移`} disabled={c === table.columns.length - 1} onClick={() => change(moveColumn(table, column.id, c + 1))}>右移</button>
              <button className="button" type="button" aria-label={`${label} 删除第 ${c + 1} 列及其单元格`} onClick={() => change(removeColumn(table, column.id))}>删除列及单元格</button>
            </div>
          </th>)}
          <th scope="col">行操作</th>
        </tr></thead>
        <tbody>{table.rows.map((row, r) => <tr key={row.id}>
          {table.columns.map((column, c) => {
            const cell = row.cells.find(item => item.column_id === column.id);
            const cellLabel = `${label} 第 ${r + 1} 行 第 ${c + 1} 列`;
            return <td key={column.id}>
              <Field label={cellLabel} value={cell?.display_text} multiline data-editor-focus={`${row.id}/${column.id}`}
                onChange={text => change(setCellDisplayText(table, row.id, column.id, text, usedIds))} />
              {cell && (Object.hasOwn(cell, 'value') || Object.hasOwn(cell, 'unit')) && <CellMetadata key={cell.id} cell={cell} label={cellLabel}
                changeValue={value => change(setCellValue(table, row.id, column.id, value, usedIds))}
                changeUnit={unit => change(setCellUnit(table, row.id, column.id, unit, usedIds))} />}
            </td>;
          })}
          <td><span>第 {r + 1} 行</span><ListActions label={`${label} 第 ${r + 1} 行`} index={r} length={table.rows.length}
            move={to => change(moveRow(table, row.id, to))} remove={() => change(removeRow(table, row.id))} removeLabel={`删除${label} 第 ${r + 1} 行`} /></td>
        </tr>)}</tbody>
      </table>
    </div>
    {!table.columns.length && <p className="muted">暂无列，可添加列后填写单元格。</p>}
    {!table.rows.length && <p className="muted">暂无行，可添加行后填写单元格。</p>}
    <div className="row head-actions s4-actions">
      <button className="button" type="button" onClick={() => {
        const next = addColumn(table, usedIds);
        focusTarget.current = next.columns.at(-1).id;
        change(next);
      }}>添加列</button>
      <button className="button" type="button" onClick={() => {
        const next = addRow(table, usedIds);
        if (table.columns.length) focusTarget.current = `${next.rows.at(-1).id}/${table.columns[0].id}`;
        change(next);
      }}>添加行</button>
    </div>
  </>;
}
