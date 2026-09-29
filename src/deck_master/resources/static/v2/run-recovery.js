import {get, post} from './api.js';

// Personal pending markers prevent blind re-submission. Only Task reads confirm
// cancellation; this journal is never an execution fact or a second call ledger.
export function cancelRecovery(app) {
  if (app.cancelRecovery) return app.cancelRecovery;
  const key = `deck-master:v3:cancel-pending:${app.info.project_identity}`, pending = new Set(), sending = new Set();
  try { for (const id of JSON.parse(localStorage.getItem(key) || '[]')) if (typeof id === 'string') pending.add(id); } catch { /* Read original task to recover. */ }
  function persist() {
    let saved = false;
    try { localStorage.setItem(key, JSON.stringify([...pending])); saved = true; } catch { /* Project ACK can still preserve it. */ }
    const editor = app.editor;
    if (editor?.draft && !editor.readonly && !editor.disposed) {
      editor.draft.content.cancel_pending = [...pending]; editor.changed();
    }
    app.root.dispatchEvent(new CustomEvent('cancel-state-changed'));
    return saved;
  }
  const recovery = {
    pending, sending,
    hydrate(editor) {
      const ids = editor.draft.content.cancel_pending;
      if (Array.isArray(ids)) for (const id of ids) if (typeof id === 'string') pending.add(id);
      app.root.dispatchEvent(new CustomEvent('cancel-state-changed'));
    },
    observe(task) {
      if (['cancelled', 'completed', 'failed', 'superseded'].includes(task.status) && pending.delete(task.task_id)) persist();
    },
    async cancel(task, retry = false) {
      if (sending.has(task.task_id)) throw new Error('原取消请求仍在等待回包。');
      if (pending.has(task.task_id) && !retry) throw new Error('取消结果待核实，请先读取原任务。');
      sending.add(task.task_id);
      try {
      pending.add(task.task_id);
      const localSaved = persist(), editor = app.editor;
      if (!localSaved) {
        await editor?.pendingWrite;
        await editor?.save();
        if (!editor || editor.status !== 'saved' || !editor.draft.content.cancel_pending?.includes(task.task_id)) {
          pending.delete(task.task_id); persist(); throw new Error('取消恢复记录未保存，尚未发送取消请求。请恢复本机存储或保存个人记录后重试。');
        }
      }
      await post('/api/cancel', {task_id: task.task_id, reason: '用户在运行台取消'});
      // Do not infer a final task status from a transport acknowledgement.
      await recovery.verify(task.task_id);
      app.root.dispatchEvent(new CustomEvent('business-state-changed'));
      } finally { sending.delete(task.task_id); app.root.dispatchEvent(new CustomEvent('cancel-state-changed')); }
    },
    async verify(id) {
      const result = await get('/api/tasks/' + encodeURIComponent(id));
      recovery.observe(result.task); return result;
    },
  };
  app.cancelRecovery = recovery; return recovery;
}
