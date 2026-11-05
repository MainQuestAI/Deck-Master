import React from 'react';
import { createBulletItem, moveIndex, removeBulletItem } from '../../content-structure.js';

export function Field({ label, value, onChange, multiline = false, ...props }) {
  return <label className="form-group s4-field"><span>{label}</span>{multiline
    ? <textarea rows={3} value={value ?? ''} onChange={onChange && (event => onChange(event.target.value))} {...props} />
    : <input type="text" value={value ?? ''} onChange={onChange && (event => onChange(event.target.value))} {...props} />}</label>;
}

export function ListActions({ label, index, length, move, remove, removeLabel = `移除${label}` }) {
  return <div className="row head-actions">
    <button className="button" type="button" aria-label={`${label}上移`} disabled={index === 0} onClick={() => move(index - 1)}>上移</button>
    <button className="button" type="button" aria-label={`${label}下移`} disabled={index === length - 1} onClick={() => move(index + 1)}>下移</button>
    <button className="button" type="button" onClick={remove}>{removeLabel}</button>
  </div>;
}

function childCount(item) {
  return (item.children || []).reduce((count, child) => count + 1 + childCount(child), 0);
}

export function ItemFields({ items = [], change, label, usedIds }) {
  return <section className="form-group" aria-label={label}>
    {items.map((item, index) => {
      const itemLabel = `${label} ${index + 1}`;
      const count = childCount(item);
      const patch = fields => change(items.map((entry, i) => i === index ? { ...entry, ...fields } : entry));
      return <div className="s4-panel" key={item.id || index}>
        <Field label={itemLabel} value={item.text} multiline onChange={text => patch({ text })} />
        <ListActions label={itemLabel} index={index} length={items.length}
          move={to => change(moveIndex(items, index, to))}
          remove={() => change(item.id ? removeBulletItem(items, item.id) : items.filter((_, i) => i !== index))}
          removeLabel={count ? `移除${itemLabel}及其 ${count} 个子项` : `移除${itemLabel}`} />
        {count > 0 && <ItemFields items={item.children} label={`${itemLabel} 子项`} usedIds={usedIds} change={children => patch({ children })} />}
      </div>;
    })}
    <button className="button" type="button" onClick={() => change([...items, createBulletItem(usedIds)])}>添加{label}条目</button>
  </section>;
}

export function TextList({ label, items = [], change }) {
  return <section className="form-group" aria-label={label}>
    <h3>{label}</h3>
    {items.map((item, index) => <div className="s4-panel" key={index}>
      <Field label={`${label} ${index + 1}`} value={item} onChange={text => change(items.map((value, i) => i === index ? text : value))} />
      <ListActions label={`${label} ${index + 1}`} index={index} length={items.length}
        move={to => change(moveIndex(items, index, to))} remove={() => change(items.filter((_, i) => i !== index))} />
    </div>)}
    <button className="button" type="button" onClick={() => change([...items, ''])}>添加{label}</button>
  </section>;
}
