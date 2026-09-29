// One in-flight read; polling never dispatches, retries calls, or adopts results.
export class SummaryPoll {
  constructor(read, onValue, onError, initial) {
    this.read = read; this.onValue = onValue; this.onError = onError;
    this.delay = this.interval(initial); this.busy = false; this.stopped = true; this.again = false; this.generation = 0;
    this.visible = () => {
      if (document.hidden) { clearTimeout(this.timer); this.again = false; this.controller?.abort(); }
      else this.refresh();
    };
    this.focus = () => this.refresh();
  }
  interval(value) {
    return ['queued', 'awaiting_host', 'running'].some(key => value?.task_counts?.[key] > 0) ? 3000 : 15000;
  }
  start() {
    if (!this.stopped) return;
    this.stopped = false; this.generation++;
    document.addEventListener('visibilitychange', this.visible); window.addEventListener('focus', this.focus);
    this.schedule();
  }
  schedule() {
    clearTimeout(this.timer);
    if (!this.stopped && !document.hidden) this.timer = setTimeout(() => this.refresh(), this.delay);
  }
  async refresh() {
    if (this.stopped || document.hidden) return;
    if (this.busy) { this.again = true; return; }
    clearTimeout(this.timer); this.busy = true; this.controller = new AbortController();
    const generation = this.generation;
    try {
      const value = await this.read(this.controller.signal);
      if (this.stopped || document.hidden || generation !== this.generation) return;
      this.onValue(value); this.delay = this.interval(value);
    } catch (error) {
      if (error.name !== 'AbortError' && !this.stopped && generation === this.generation) {
        this.delay = Math.min(30000, this.delay * 2); this.onError(error);
      }
    } finally {
      this.busy = false; this.controller = null;
      if (this.again && !this.stopped && !document.hidden) {
        this.again = false; clearTimeout(this.timer); this.timer = setTimeout(() => this.refresh(), 0);
      } else { this.again = false; this.schedule(); }
    }
  }
  stop() {
    this.stopped = true; this.generation++; this.again = false; clearTimeout(this.timer); this.controller?.abort();
    document.removeEventListener('visibilitychange', this.visible); window.removeEventListener('focus', this.focus);
  }
}
