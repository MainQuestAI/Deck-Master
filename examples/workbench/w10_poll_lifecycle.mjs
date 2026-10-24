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
// A slow follow-up control read is part of the poll, not a detached workload.
let releaseControl, followed = 0;
const slow = new SummaryPoll(async () => ({task_counts:{running:1}}),
  () => { followed++; return new Promise(resolve => { releaseControl = resolve; }); }, () => {}, {task_counts:{running:1}});
slow.start(); await tick(3000);
window.dispatchEvent(new Event('focus')); window.dispatchEvent(new Event('focus'));
assert.equal(followed, 1); assert.equal(timers.size, 0);
releaseControl(); await flush(); await tick(0);
assert.equal(followed, 2); slow.stop(); releaseControl(); await flush();
assert.equal(timers.size, 0);

// A route can change while onValue awaits control. Retire both writes and timing.
let releaseOld, acceptedOld = false;
const guarded = new SummaryPoll(async () => ({task_counts:{completed:1}}), async (value, valid) => {
  await new Promise(resolve => { releaseOld = resolve; });
  if (valid?.()) acceptedOld = true;
}, () => {}, {task_counts:{running:1}});
guarded.start(); await tick(3000);
guarded.useSnapshot({task_counts:{running:1}});
releaseOld(); await flush();
assert.equal(acceptedOld, false);
assert.equal(guarded.delay, 3000, 'obsolete callback cannot reset the new route interval');
guarded.stop();

// Navigation must obtain post-write control facts without overlapping reads.
const {Project} = await import('../../src/deck_master/resources/static/v2/project.js');
let reads = [], inFlight = 0, controlPeak = 0;
globalThis.fetch = path => new Promise(resolve => {
  assert.equal(path, '/api/project');
  controlPeak = Math.max(controlPeak, ++inFlight);
  reads.push(value => { inFlight--; resolve({ok:true, json:async () => value}); });
});
const app = new Project({}, {});
const first = app.readControl(), shared = app.readControl(), afterWrite = app.readControl(true);
assert.equal(reads.length, 1);
reads.shift()({revision_id:'before'});
assert.equal((await first).revision_id, 'before');
assert.equal((await shared).revision_id, 'before');
await flush(); assert.equal(reads.length, 1);
reads.shift()({revision_id:'after'});
assert.equal((await afterWrite).revision_id, 'after');
assert.equal(controlPeak, 1);
// The Project callback must not write after a route has replaced its scope.
app.health = {ui_capabilities:['collaboration.v1']};
app.info = {project_id:'same',project_identity:'identity',revision_id:'B'};
app.route = {revision:'B'}; app.latest = {revision_id:'B'};
app.root = new EventTarget(); let events = 0, notices = 0;
app.root.addEventListener('summary-refreshed', () => events++);
app.syncState = () => notices++;
app.pendingButton = {textContent:'待交接 2',setAttribute(){throw new Error('stale count write');}};
const old = app.applySummary({project_id:'same',revision_id:'A'});
await flush(); assert.equal(reads.length, 1);
app.generation++; app.controlRead++; // B navigation wins while A awaits control.
reads.shift()({project_id:'same',project_identity:'identity',revision_id:'A'});
await old;
assert.equal(app.info.revision_id,'B'); assert.equal(app.latest.revision_id,'B');
assert.equal(app.pendingButton.textContent,'待交接 2'); assert.equal(events,0); assert.equal(notices,0);
app.health.ui_capabilities.push('project_control_light.v1');
globalThis.fetch = async path => {
  assert.equal(path,'/api/project?light=1');
  return {ok:true,json:async()=>({revision_id:'light'})};
};
assert.equal((await app.readControl()).revision_id,'light');
const lifecycleResult = {passed: true, checks: ['active_3s', 'idle_15s', 'failure_backoff_max_30s', 'single_inflight', 'focus_coalesced', 'hidden_pauses_aborts', 'visible_immediate', 'late_hidden_response_ignored', 'bfcache_old_generation_ignored', 'stop_removes_listeners']};

// RP-00 follow-up: route snapshots must fence the awaited control phase too.
let releaseDeferred;
const delayed = new SummaryPoll(async () => ({task_counts:{running:1}}),
  () => new Promise(resolve => { releaseDeferred = resolve; }), () => {}, {task_counts:{running:1}});
delayed.start(); await tick(3000);
delayed.useSnapshot({task_counts:{completed:1}});
releaseDeferred(); await flush();
assert.equal(delayed.delay, 15000, 'late onValue must not replace the newer route interval');
assert.equal([...timers.values()][0].delay, 15000);
delayed.stop();

// Exercise Project's actual async consumer, including its control assignment.
for (const interrupt of ['route', 'stop', 'hide_resume']) {
  document.hidden = false;
  const root = new EventTarget(); const events = [], sync = [], banners = [];
  root.addEventListener('summary-refreshed', event => events.push(event.detail));
  const project = new Project(root, {ui_capabilities:['collaboration.v1']});
  const initial = {project_id:'p', project_identity:'identity', revision_id:'initial'};
  project.info = initial; project.route = {revision:'newer'}; project.latest = {revision_id:'initial'};
  project.pendingButton = {textContent:'current pending', setAttribute() { throw new Error('stale pending update'); }};
  project.syncState = value => sync.push(value);
  project.controlSlot = {replaceChildren(...values) { banners.push(values); }};
  let release;
  project.readControl = () => new Promise(resolve => { release = resolve; });
  const old = {project_id:'p', revision_id:'old', task_counts:{awaiting_host:9}};
  const currentPoll = new SummaryPoll(async () => old,
    (value, isCurrent) => project.applySummary(value, isCurrent), error => { throw error; }, old);
  currentPoll.start(); await tick(3000); assert.equal(typeof release, 'function');
  if (interrupt === 'route') {
    project.generation++;
    project.latest = {revision_id:'newer', task_counts:{completed:1}};
    currentPoll.useSnapshot(project.latest);
  } else if (interrupt === 'stop') currentPoll.stop();
  else {
    document.hidden = true; document.dispatchEvent(new Event('visibilitychange'));
    document.hidden = false; document.dispatchEvent(new Event('visibilitychange'));
  }
  release({...initial, revision_id:'old-control'}); await flush();
  assert.equal(project.info, initial, `${interrupt}: stale control must not publish`);
  assert.equal(project.latest.revision_id, interrupt === 'route' ? 'newer' : 'initial');
  assert.equal(project.pendingButton.textContent, 'current pending');
  assert.equal(events.length, 0); assert.equal(sync.length, 0); assert.equal(banners.length, 0);
  if (interrupt === 'hide_resume') {
    // A visible refresh is still queued and can publish its own current facts.
    project.pendingButton.setAttribute = () => {};
    await tick(0);
    release({...initial, revision_id:'fresh-control'}); await flush();
    assert.equal(events.length, 1); assert.equal(project.info.revision_id, 'fresh-control');
  }
  currentPoll.stop(); assert.equal(timers.size, 0);
}
console.log(JSON.stringify({passed:true, checks:[...lifecycleResult.checks,'deferred_control_route_fenced','deferred_control_stop_fenced','hide_show_retires_old_callback','new_visible_refresh_recovers','new_snapshot_interval_preserved']}));
