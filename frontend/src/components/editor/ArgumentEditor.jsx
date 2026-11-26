import React from 'react';
import { moveIndex } from '../../content-structure.js';
import { PAGE_KIND_OPTIONS, buildEvidenceItem, emptyArgument, evidenceMode } from '../../schema/fields.js';
import { Field, ListActions, TextList } from './EditorFields';

function EvidenceList({ items = [], change }) {
  const updateItem = (index, next) => change(items.map((entry, i) => i === index ? next : entry));
  return <section className="form-group" aria-label="证据">
    <h3>证据</h3>
    <p className="muted">每条证据在“引用出处”和“待补缺口”之间二选一，避免二者同时填写。</p>
    {items.map((item, index) => {
      const mode = evidenceMode(item);
      const labelPrefix = `证据 ${index + 1}`;
      const detailValue = mode === 'gap' ? (item.gap ?? '') : (item.ref ?? '');
      return <div className="s4-panel" key={index}>
        <Field
          label={`${labelPrefix} 内容`}
          value={item.text ?? ''}
          multiline
          onChange={text => updateItem(index, buildEvidenceItem(text, mode, detailValue))}
        />
        <label className="form-group s4-field">
          <span>{labelPrefix} 依据方式</span>
          <select
            value={mode}
            onChange={event => {
              const nextMode = event.target.value;
              updateItem(index, buildEvidenceItem(item.text ?? '', nextMode, ''));
            }}
          >
            <option value="ref">引用出处（ref）</option>
            <option value="gap">待补缺口（gap）</option>
          </select>
        </label>
        <Field
          label={mode === 'gap' ? `${labelPrefix} 缺口说明` : `${labelPrefix} 出处`}
          value={detailValue}
          onChange={detail => updateItem(index, buildEvidenceItem(item.text ?? '', mode, detail))}
        />
        <ListActions
          label={labelPrefix}
          index={index}
          length={items.length}
          move={to => change(moveIndex(items, index, to))}
          remove={() => change(items.filter((_, i) => i !== index))}
        />
      </div>;
    })}
    <button
      className="button"
      type="button"
      onClick={() => change([...items, buildEvidenceItem('', 'ref', '')])}
    >
      添加证据
    </button>
  </section>;
}

export default function ArgumentEditor({ kind = '', onKindChange, argument = null, onArgumentChange }) {
  const updateArgument = patch => onArgumentChange({ ...(argument || emptyArgument()), ...patch });
  return <section className="s4-panel" aria-label="页型与论证结构">
    <h3>页型与论证结构</h3>
    <label className="form-group s4-field">
      <span>页型</span>
      <select value={kind ?? ''} onChange={event => onKindChange(event.target.value)}>
        {PAGE_KIND_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
    {!argument ? <div className="row between">
      <p className="muted">当前页尚未填写论证结构；判断页或关键结论页建议补充理由、证据与推理。</p>
      <button className="button" type="button" onClick={() => onArgumentChange(emptyArgument())}>添加论证结构</button>
    </div> : <>
      <div className="row between">
        <strong>论证结构</strong>
        <button className="button" type="button" onClick={() => onArgumentChange(null)}>清除论证结构</button>
      </div>
      <TextList label="理由" items={argument.reasons || []} change={reasons => updateArgument({ reasons })} />
      <EvidenceList items={argument.evidence || []} change={evidence => updateArgument({ evidence })} />
      <Field label="推理" value={argument.reasoning ?? ''} multiline onChange={reasoning => updateArgument({ reasoning })} />
      <Field label="反驳与边界" value={argument.rebuttal ?? ''} multiline onChange={rebuttal => updateArgument({ rebuttal })} />
    </>}
  </section>;
}
