// Deterministic timer/focus/visibility fault injection. No HTTP writes or models.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const code = await readFile(new URL('../../src/deck_master/resources/static/v2/summary-poll.js', import.meta.url), 'utf8');
const {SummaryPoll} = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));
globalThis.document = new EventTarget(); document.hidden = false;
globalThis.window = new EventTarget();
let timers = new Map(), next = 0;
globalThis.setTimeout = (callback, delay) => { timers.set(++next, {callback, delay}); return next; };
globalThis.clearTimeout = id => timers.delete(id);
let pending = [], seen = [], errors = [], peak = 0, active = 0;
const poll = new SummaryPoll(signal => new Promise((resolve, reject) => {
  active++; peak = Math.max(peak, active); pending.push({signal, resolve(value) { active--; resolve(value); }, reject(error) { active--; reject(error); }});
}), value => seen.push(value), error => errors.push(error.message), {task_counts: {running: 1}});
const flush = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); };
async function tick(delay) {
  assert.equal(timers.size, 1); const [id, timer] = [...timers][0]; assert.equal(timer.delay, delay);
  timers.delete(id); timer.callback(); await flush();
}
poll.start(); await tick(3000);
window.dispatchEvent(new Event('focus')); window.dispatchEvent(new Event('focus')); assert.equal(pending.length, 1);
pending.shift().resolve({task_counts: {running: 1}}); await flush(); await tick(0); assert.equal(peak, 1);
pending.shift().resolve({task_counts: {completed: 1}}); await flush(); await tick(15000);
pending.shift().reject(new Error('offline')); await flush(); await tick(30000);
pending.shift().reject(new Error('offline twice')); await flush(); assert.equal([...timers.values()][0].delay, 30000);
document.hidden = true; document.dispatchEvent(new Event('visibilitychange')); assert.equal(timers.size, 0);
window.dispatchEvent(new Event('focus')); assert.equal(pending.length, 0);
document.hidden = false; document.dispatchEvent(new Event('visibilitychange')); assert.equal(pending.length, 1);
document.hidden = true; document.dispatchEvent(new Event('visibilitychange')); assert.equal(pending[0].signal.aborted, true);
const count = seen.length; pending.shift().resolve({task_counts: {running: 1}}); await flush(); assert.equal(seen.length, count); assert.equal(timers.size, 0);
document.hidden = false; document.dispatchEvent(new Event('visibilitychange')); const stale = pending.shift();
poll.stop(); poll.start(); poll.refresh(); assert.equal(stale.signal.aborted, true);
stale.resolve({task_counts: {running: 9}}); await flush(); assert.equal(seen.length, count); await tick(0);
pending.shift().resolve({task_counts: {running: 1}}); await flush(); assert.equal([...timers.values()][0].delay, 3000);
poll.stop(); assert.equal(timers.size, 0); window.dispatchEvent(new Event('focus')); assert.equal(pending.length, 0);
assert.equal(peak, 1); assert.equal(errors.length, 2);
console.log(JSON.stringify({passed: true, checks: ['active_3s', 'idle_15s', 'failure_backoff_max_30s', 'single_inflight', 'focus_coalesced', 'hidden_pauses_aborts', 'visible_immediate', 'late_hidden_response_ignored', 'bfcache_old_generation_ignored', 'stop_removes_listeners']}));
