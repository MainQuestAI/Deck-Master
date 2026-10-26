import {canonical} from './api.js';

// Only the one personal-clear recovery record lives here. Transactions finish
// before HTTP begins; there is no lease, background writer or network lock.
export function personalClearStore(info) {
  const identity = info.project_identity, legacyKey = `deck-master:v3:personal-clear:${identity}`;
  const sameRequest = (a, b) => Boolean(a && b && a.project_identity === identity &&
    b.project_identity === identity && canonical(a.request) === canonical(b.request));
  const invalid = () => new Error('本机清理恢复记录暂不可核实，原记录保留；未发起新清理。');
  const validate = value => {
    const r = value?.request, input = r?.input, ids = input?.draft_ids;
    if (!value || value.project_identity !== identity || !r ||
        Object.keys(r).some(k => !['operation_id','input','plan_id','manifest_digest'].includes(k)) ||
        typeof r.operation_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(r.operation_id) ||
        typeof r.manifest_digest !== 'string' || !/^[a-f0-9]{64}$/.test(r.manifest_digest) ||
        r.plan_id !== 'clear-plan-' + r.manifest_digest.slice(0,16) ||
        !input || input.project_id !== info.project_id || input.scope !== 'current_project' ||
        typeof input.reading_preferences !== 'boolean' ||
        Object.keys(input).some(k => !['project_id','scope','draft_ids','reading_preferences'].includes(k)) ||
        !(ids === undefined || ids === 'all' || (Array.isArray(ids) &&
          ids.every(id => typeof id === 'string' && id.length) && new Set(ids).size === ids.length)) ||
        (value.end_inspection_digest !== undefined &&
          (typeof value.end_inspection_digest !== 'string' || !/^[a-f0-9]{64}$/.test(value.end_inspection_digest)))) throw invalid();
    return value;
  };
  const requireOwner = (current, expected) => {
    if (!sameRequest(current, expected) || current.end_inspection_digest !== expected.end_inspection_digest)
      throw new Error('恢复记录已变化，请核实当前保留的请求。');
  };
  const open = () => new Promise((resolve, reject) => {
    const request = indexedDB.open('deck-master:personal-clear', 1);
    let blocked = false;
    request.onupgradeneeded = () => request.result.createObjectStore('records');
    request.onerror = () => reject(request.error || invalid());
    request.onblocked = () => { blocked = true; reject(invalid()); };
    request.onsuccess = () => {
      if (blocked) request.result.close(); else resolve(request.result);
    };
  });
  async function transaction(change) {
    const db = await open();
    return new Promise((resolve, reject) => {
      let tx, result, failure;
      try { tx = db.transaction('records', 'readwrite'); }
      catch (error) { db.close(); reject(error); return; }
      tx.oncomplete = () => { db.close(); resolve(result); };
      tx.onabort = () => { db.close(); reject(failure || tx.error || invalid()); };
      try {
        const records = tx.objectStore('records'), request = records.get(identity);
        request.onsuccess = () => {
          try {
            const legacy = localStorage.getItem(legacyKey);
            let row = request.result;
            const initialize = row === undefined;
            if (initialize) {
              const pending = legacy === null ? null : validate(JSON.parse(legacy));
              row = {initialized:true, pending, legacy};
            } else {
              if (row?.initialized !== true || !('pending' in row) ||
                  !(row.legacy === null || typeof row.legacy === 'string')) throw invalid();
              if (row.pending !== null) validate(row.pending);
              // Old JS is refused by commit-clear's protocol admission. If it
              // still writes its old key, preserve both sources and stop rather
              // than overwrite an unknown recovery request during migration.
              if (legacy !== row.legacy) throw new Error('旧页面的清理恢复记录已变化。两份记录均保留，请关闭旧页面并核实恢复记录；未发起新清理。');
            }
            result = change ? change(row.pending) : row.pending;
            if (result !== null) validate(result);
            if (initialize || change) records.put({...row, pending:result}, identity);
          } catch (error) { failure = error; tx.abort(); }
        };
      } catch (error) { failure = error; tx.abort(); }
    });
  }
  return {
    read: () => transaction(),
    claimIfEmpty: next => transaction(current => {
      if (current) throw new Error('本机已有待核实记录，请先处理原清理请求。');
      return validate(next);
    }),
    compareUpdate: (expected, next) => transaction(current => {
      requireOwner(current, expected);
      if (!sameRequest(expected, next)) throw invalid();
      return validate(next);
    }),
    compareClear: expected => transaction(current => { requireOwner(current, expected); return null; }),
  };
}
