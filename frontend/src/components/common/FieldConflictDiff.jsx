import React, { useMemo, useState } from 'react';
import {
  ARGUMENT_FIELDS,
  BRIEF_FIELDS,
  CONTENT_FIELDS,
  FRAMING_FIELDS,
  NARRATOR_FIELDS,
  PAGE_FIELDS,
  PAGE_KIND_LABELS,
  evidenceMode,
} from '../../schema/fields.js';
import PageContent from './PageContent';

function deepEqual(left, right) {
  return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
}

function getPath(obj, path) {
  let cursor = obj;
  for (const seg of path) {
    if (cursor == null || typeof cursor !== 'object') return undefined;
    cursor = cursor[seg];
  }
  return cursor;
}

function setPath(target, path, value) {
  if (path.length === 1) {
    if (value === undefined) delete target[path[0]];
    else target[path[0]] = structuredClone(value);
    return;
  }
  let cursor = target;
  for (let i = 0; i < path.length - 1; i++) {
    const seg = path[i];
    if (cursor[seg] == null || typeof cursor[seg] !== 'object') {
      cursor[seg] = {};
    }
    cursor = cursor[seg];
  }
  const leaf = path[path.length - 1];
  if (value === undefined) delete cursor[leaf];
  else cursor[leaf] = structuredClone(value);
}

export function conflictDescriptors(schemaKind, base = {}, server = {}, mine = {}) {
  if (schemaKind === 'brief') {
    return [
      { key: 'title', path: ['title'], label: BRIEF_FIELDS.title, format: 'text' },
      { key: 'audience', path: ['audience'], label: BRIEF_FIELDS.audience, format: 'text' },
      { key: 'task_type', path: ['task_type'], label: BRIEF_FIELDS.task_type, format: 'text' },
      { key: 'goal', path: ['goal'], label: BRIEF_FIELDS.goal, format: 'text' },
      { key: 'decision', path: ['decision'], label: BRIEF_FIELDS.decision, format: 'text' },
      { key: 'concerns', path: ['concerns'], label: BRIEF_FIELDS.concerns, format: 'string-list' },
      { key: 'narrator.role', path: ['narrator', 'role'], label: NARRATOR_FIELDS.role, format: 'text' },
      { key: 'narrator.tone', path: ['narrator', 'tone'], label: NARRATOR_FIELDS.tone, format: 'text' },
      { key: 'constraints', path: ['constraints'], label: BRIEF_FIELDS.constraints, format: 'string-list' },
      { key: 'page_limit', path: ['page_limit'], label: BRIEF_FIELDS.page_limit, format: 'text' },
    ];
  }
  if (schemaKind === 'framing') {
    return [
      { key: 'thesis', path: ['thesis'], label: FRAMING_FIELDS.thesis, format: 'text' },
      { key: 'storyline', path: ['storyline'], label: FRAMING_FIELDS.storyline, format: 'string-list' },
      { key: 'pillars', path: ['pillars'], label: FRAMING_FIELDS.pillars, format: 'pillars' },
      { key: 'facts', path: ['facts'], label: FRAMING_FIELDS.facts, format: 'string-list' },
      { key: 'assumptions', path: ['assumptions'], label: FRAMING_FIELDS.assumptions, format: 'string-list' },
      { key: 'questions', path: ['questions'], label: FRAMING_FIELDS.questions, format: 'string-list' },
    ];
  }
  if (schemaKind === 'page') {
    const bothArgsAreObjects = Boolean(server?.argument && mine?.argument && typeof server.argument === 'object' && typeof mine.argument === 'object');
    const argumentDescriptors = bothArgsAreObjects
      ? [
          { key: 'argument.reasons', path: ['argument', 'reasons'], label: `${PAGE_FIELDS.argument} · ${ARGUMENT_FIELDS.reasons}`, format: 'string-list' },
          { key: 'argument.evidence', path: ['argument', 'evidence'], label: `${PAGE_FIELDS.argument} · ${ARGUMENT_FIELDS.evidence}`, format: 'evidence-list' },
          { key: 'argument.reasoning', path: ['argument', 'reasoning'], label: `${PAGE_FIELDS.argument} · ${ARGUMENT_FIELDS.reasoning}`, format: 'text' },
          { key: 'argument.rebuttal', path: ['argument', 'rebuttal'], label: `${PAGE_FIELDS.argument} · ${ARGUMENT_FIELDS.rebuttal}`, format: 'text' },
        ]
      : [{ key: 'argument', path: ['argument'], label: PAGE_FIELDS.argument, format: 'argument' }];
    return [
      { key: 'content.title', path: ['content', 'title'], label: CONTENT_FIELDS.title, format: 'text' },
      { key: 'content.subtitle', path: ['content', 'subtitle'], label: CONTENT_FIELDS.subtitle, format: 'text' },
      { key: 'content.body_blocks', path: ['content', 'body_blocks'], label: CONTENT_FIELDS.body_blocks, format: 'body-blocks' },
      { key: 'content.labels', path: ['content', 'labels'], label: CONTENT_FIELDS.labels, format: 'text-items' },
      { key: 'content.callouts', path: ['content', 'callouts'], label: CONTENT_FIELDS.callouts, format: 'text-items' },
      { key: 'content.footnotes', path: ['content', 'footnotes'], label: CONTENT_FIELDS.footnotes, format: 'text-items' },
      { key: 'kind', path: ['kind'], label: PAGE_FIELDS.kind, format: 'page-kind' },
      ...argumentDescriptors,
      { key: 'purpose', path: ['purpose'], label: PAGE_FIELDS.purpose, format: 'text' },
      { key: 'layout', path: ['layout'], label: PAGE_FIELDS.layout, format: 'text' },
      { key: 'notes', path: ['notes'], label: PAGE_FIELDS.notes, format: 'text' },
      { key: 'todo', path: ['todo'], label: PAGE_FIELDS.todo, format: 'string-list' },
      { key: 'refs', path: ['refs'], label: PAGE_FIELDS.refs, format: 'string-list' },
    ];
  }
  return [];
}

function normalizedValue(format, value) {
  if (format === 'text' || format === 'page-kind') return value ?? '';
  if (format === 'string-list' || format === 'pillars' || format === 'evidence-list' || format === 'body-blocks' || format === 'text-items') {
    return Array.isArray(value) ? value : [];
  }
  return value ?? null;
}

export function analyzeThreeWayConflict(base = {}, server = {}, mine = {}, descriptors = []) {
  const autoServer = [];
  const autoMine = [];
  const conflicts = [];

  for (const desc of descriptors) {
    const b = normalizedValue(desc.format, getPath(base, desc.path));
    const s = normalizedValue(desc.format, getPath(server, desc.path));
    const m = normalizedValue(desc.format, getPath(mine, desc.path));
    const baseEqMine = deepEqual(b, m);
    const baseEqServer = deepEqual(b, s);
    const mineEqServer = deepEqual(m, s);
    if (mineEqServer) continue;
    if (baseEqMine && !baseEqServer) {
      autoServer.push({ ...desc, base: b, server: s, mine: m });
    } else if (baseEqServer && !baseEqMine) {
      autoMine.push({ ...desc, base: b, server: s, mine: m });
    } else {
      conflicts.push({ ...desc, base: b, server: s, mine: m });
    }
  }

  return { autoServer, autoMine, conflicts };
}

export function mergeThreeWay(base = {}, server = {}, mine = {}, descriptors = [], choices = {}) {
  const merged = structuredClone(server);
  for (const desc of descriptors) {
    const rawB = getPath(base, desc.path);
    const rawS = getPath(server, desc.path);
    const rawM = getPath(mine, desc.path);
    const b = normalizedValue(desc.format, rawB);
    const s = normalizedValue(desc.format, rawS);
    const m = normalizedValue(desc.format, rawM);
    if (deepEqual(m, s)) continue;
    if (deepEqual(b, m)) {
      // Only server modified this field; keep server value.
      continue;
    }
    if (deepEqual(b, s)) {
      // Only author modified this field; carry author's value over server edits to other fields.
      setPath(merged, desc.path, rawM);
      continue;
    }
    const pick = choices[desc.key] || 'mine';
    if (pick === 'mine') {
      setPath(merged, desc.path, rawM);
    }
  }
  return merged;
}

function TextItemsPreview({ items = [] }) {
  if (!items.length) return <span className="muted">（空）</span>;
  return <ul>{items.map((item, idx) => <li key={item.id || idx}>
    {item.text || '（空条目）'}
    {item.children?.length > 0 && <TextItemsPreview items={item.children} />}
  </li>)}</ul>;
}

function EvidencePreview({ items = [] }) {
  if (!items.length) return <span className="muted">（空列表）</span>;
  return <ul>{items.map((item, idx) => {
    const mode = evidenceMode(item);
    return <li key={idx}>
      {item.text || '（空证据）'}（{mode === 'gap' ? `缺口：${item.gap || '未填'}` : `出处：${item.ref || '未填'}`}）
    </li>;
  })}</ul>;
}

function ArgumentPreview({ value }) {
  if (!value) return <span className="muted">（无论证结构）</span>;
  return <div className="s4-reading">
    {(value.reasons || []).length > 0 && <p>理由：{value.reasons.join('；')}</p>}
    {(value.evidence || []).length > 0 && <EvidencePreview items={value.evidence} />}
    {value.reasoning && <p>推理：{value.reasoning}</p>}
    {value.rebuttal && <p>反驳与边界：{value.rebuttal}</p>}
    {!(value.reasons?.length || value.evidence?.length || value.reasoning || value.rebuttal) && <span className="muted">（空论证结构）</span>}
  </div>;
}

function FieldValuePreview({ format, value }) {
  if (format === 'page-kind') {
    return <span>{PAGE_KIND_LABELS[value] || value || '（未指定）'}</span>;
  }
  if (format === 'string-list') {
    if (!value?.length) return <span className="muted">（空列表）</span>;
    return <ul>{value.map((item, idx) => <li key={idx}>{item || '（空条目）'}</li>)}</ul>;
  }
  if (format === 'pillars') {
    if (!value?.length) return <span className="muted">（无分组）</span>;
    return <div>{value.map((pillar, idx) => <div key={idx}>
      <strong>{pillar.title || `未命名分组 ${idx + 1}`}</strong>
      {pillar.points?.length ? <ul>{pillar.points.map((pt, i) => <li key={i}>{pt || '（空支持点）'}</li>)}</ul> : <span className="muted">（无支持点）</span>}
    </div>)}</div>;
  }
  if (format === 'body-blocks') {
    if (!value?.length) return <span className="muted">（空正文）</span>;
    return <PageContent content={{ title: '', subtitle: '', body_blocks: value, labels: [], callouts: [], footnotes: [] }} />;
  }
  if (format === 'text-items') {
    return <TextItemsPreview items={value} />;
  }
  if (format === 'evidence-list') {
    return <EvidencePreview items={value} />;
  }
  if (format === 'argument') {
    return <ArgumentPreview value={value} />;
  }
  if (value === null || value === undefined || value === '') {
    return <span className="muted">（空）</span>;
  }
  return <span>{String(value)}</span>;
}

export default function FieldConflictDiff({
  schemaKind,
  base,
  server,
  mine,
  disabled = false,
  applyLabel = '按所选字段合并并继续',
  onApply,
}) {
  const descriptors = useMemo(
    () => conflictDescriptors(schemaKind, base, server, mine),
    [schemaKind, base, server, mine],
  );
  const analysis = useMemo(
    () => analyzeThreeWayConflict(base, server, mine, descriptors),
    [base, server, mine, descriptors],
  );
  const [choices, setChoices] = useState({});

  if (!server) return null;

  const pick = (key, side) => setChoices(prev => ({ ...prev, [key]: side }));
  const currentChoice = key => choices[key] || 'mine';

  return <section className="s4-panel" aria-label="字段级三方冲突对照">
    <h4>字段级三方冲突对照</h4>
    {analysis.conflicts.length === 0 ? (
      <p className="muted">
        双方改动位于不同字段，合并后互不覆盖。
        {analysis.autoServer.length > 0 && `（保留服务器改动：${analysis.autoServer.map(item => item.label).join('、')}）`}
        {analysis.autoMine.length > 0 && `（保留我的改动：${analysis.autoMine.map(item => item.label).join('、')}）`}
      </p>
    ) : (
      <>
        <p className="muted">以下字段同时被修改，请逐项选择“保留我的”或“采用当前”；其余无冲突字段将自动合并保留。</p>
        {analysis.conflicts.map(item => {
          const selected = currentChoice(item.key);
          return <div className="s4-panel" key={item.key} data-conflict-field={item.key}>
            <div className="row between">
              <strong>{item.label}</strong>
              <div className="row head-actions">
                <button
                  type="button"
                  className={`button tiny ${selected === 'mine' ? 'primary' : ''}`}
                  aria-pressed={selected === 'mine'}
                  aria-label={`${item.label}：保留我的`}
                  disabled={disabled}
                  onClick={() => pick(item.key, 'mine')}
                >
                  保留我的
                </button>
                <button
                  type="button"
                  className={`button tiny ${selected === 'server' ? 'primary' : ''}`}
                  aria-pressed={selected === 'server'}
                  aria-label={`${item.label}：采用当前`}
                  disabled={disabled}
                  onClick={() => pick(item.key, 'server')}
                >
                  采用当前
                </button>
              </div>
            </div>
            <div className="s4-reading">
              <div><small className="muted">原始值：</small><FieldValuePreview format={item.format} value={item.base} /></div>
              <div><small>服务器当前：</small><FieldValuePreview format={item.format} value={item.server} /></div>
              <div><small>我的修改：</small><FieldValuePreview format={item.format} value={item.mine} /></div>
            </div>
          </div>;
        })}
      </>
    )}
    <div className="head-actions">
      <button
        type="button"
        className="primary"
        disabled={disabled}
        onClick={() => onApply(mergeThreeWay(base, server, mine, descriptors, choices))}
      >
        {applyLabel}
      </button>
    </div>
  </section>;
}
