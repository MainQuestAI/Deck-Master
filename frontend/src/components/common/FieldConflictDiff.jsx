import React, { useMemo, useState } from 'react';

function deepEqual(left, right) {
  return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
}

export function analyzeThreeWayConflict(base = {}, server = {}, mine = {}, fieldLabels = {}) {
  const keys = Object.keys(fieldLabels);
  const autoServer = [];
  const autoMine = [];
  const conflicts = [];

  for (const key of keys) {
    const b = base?.[key];
    const s = server?.[key];
    const m = mine?.[key];
    const baseEqMine = deepEqual(b, m);
    const baseEqServer = deepEqual(b, s);
    const mineEqServer = deepEqual(m, s);
    if (mineEqServer) continue;
    if (baseEqMine && !baseEqServer) {
      autoServer.push({ key, label: fieldLabels[key], base: b, server: s, mine: m });
    } else if (baseEqServer && !baseEqMine) {
      autoMine.push({ key, label: fieldLabels[key], base: b, server: s, mine: m });
    } else {
      conflicts.push({ key, label: fieldLabels[key], base: b, server: s, mine: m });
    }
  }

  return { autoServer, autoMine, conflicts };
}

export function mergeThreeWay(base = {}, server = {}, mine = {}, fieldLabels = {}, choices = {}) {
  const merged = structuredClone(server);
  for (const key of Object.keys(fieldLabels)) {
    const b = base?.[key];
    const s = server?.[key];
    const m = mine?.[key];
    if (deepEqual(m, s)) continue;
    if (deepEqual(b, m)) {
      // Only server changed this key; keep server value.
      continue;
    }
    if (deepEqual(b, s)) {
      // Only author changed this key; keep author value without overwriting server edits to other keys.
      if (m === undefined) delete merged[key];
      else merged[key] = structuredClone(m);
      continue;
    }
    // Both changed this key: follow explicit per-field choice (default to mine).
    const pick = choices[key] || 'mine';
    if (pick === 'mine') {
      if (m === undefined) delete merged[key];
      else merged[key] = structuredClone(m);
    }
  }
  return merged;
}

function previewValue(value) {
  if (value === null || value === undefined || value === '') return '（空）';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return '（空列表）';
    if (value.every(item => typeof item === 'string')) return value.join(' / ');
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export default function FieldConflictDiff({
  base,
  server,
  mine,
  fieldLabels,
  disabled = false,
  applyLabel = '按所选字段合并并继续',
  onApply,
}) {
  const analysis = useMemo(
    () => analyzeThreeWayConflict(base, server, mine, fieldLabels),
    [base, server, mine, fieldLabels],
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
            <p className="muted">原始值：{previewValue(item.base)}</p>
            <p>服务器当前：{previewValue(item.server)}</p>
            <p>我的修改：{previewValue(item.mine)}</p>
          </div>;
        })}
      </>
    )}
    <div className="head-actions">
      <button
        type="button"
        className="primary"
        disabled={disabled}
        onClick={() => onApply(mergeThreeWay(base, server, mine, fieldLabels, choices))}
      >
        {applyLabel}
      </button>
    </div>
  </section>;
}
