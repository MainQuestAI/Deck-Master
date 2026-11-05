import { test } from 'node:test';
import assert from 'node:assert/strict';
import { diffDecks } from './historyDiff.js';

function page(id, title = id) {
  return {
    id, purpose: '', layout: '', notes: '', todo: [], refs: [],
    content: { title, subtitle: '', body_blocks: [{ id: 'b1', type: 'paragraph', text: '原文' }], labels: [], callouts: [], footnotes: [] },
    image: null, svg: null, preview: null,
  };
}
function deck() {
  return {
    brief: { title: '合成方案', task_type: '首提', goal: '明确范围', constraints: [], page_limit: null },
    framing: { thesis: '先试点', pillars: [], facts: [], assumptions: [], questions: [] },
    pages: [page('p1'), page('p2'), page('p3')],
  };
}
function flatten(changes) {
  return changes.flatMap(change => [change, ...flatten(change.children || [])]);
}
function allChanges(diff) {
  return flatten([...diff.brief, ...diff.framing, ...diff.pages]);
}

test('stable page identities reorder by relative position without additions or removals', () => {
  const before = deck();
  const after = structuredClone(before);
  after.pages = [after.pages[2], after.pages[0], after.pages[1]];
  const changes = allChanges(diffDecks(before, after));
  assert.equal(changes.filter(item => item.kind === 'moved').length, 3);
  assert.equal(changes.filter(item => ['added', 'removed'].includes(item.kind)).length, 0);
  assert.deepEqual(changes.filter(item => item.kind === 'moved').map(item => [item.before, item.after]), [[3, 1], [1, 2], [2, 3]]);
});

test('inserting or removing a page does not report later pages as reordered', () => {
  const before = deck();
  const after = structuredClone(before);
  after.pages.splice(1, 0, page('new'));
  let changes = allChanges(diffDecks(before, after));
  assert.equal(changes.filter(item => item.kind === 'added').length, 1);
  assert.equal(changes.some(item => item.kind === 'moved'), false);
  changes = allChanges(diffDecks(after, before));
  assert.equal(changes.filter(item => item.kind === 'removed').length, 1);
  assert.equal(changes.some(item => item.kind === 'moved'), false);
});

test('task, framing, page fields, body, nested items and notes retain before and after values', () => {
  const before = deck();
  before.pages[0].content.labels = [{ id: 'l1', text: '标签', children: [{ id: 'i1', text: '原子项' }] }];
  const after = structuredClone(before);
  after.brief.goal = '确认范围';
  after.framing.pillars = [{ title: '范围', points: ['试点'] }];
  after.pages[0].purpose = '新目的';
  after.pages[0].layout = '双栏';
  after.pages[0].notes = '新讲稿';
  after.pages[0].todo = ['确认时间'];
  after.pages[0].refs = ['公开材料'];
  after.pages[0].content.title = '新标题';
  after.pages[0].content.subtitle = '新副标题';
  after.pages[0].content.body_blocks[0].text = '修改正文';
  after.pages[0].content.labels[0].children[0].text = '新子项';
  const unchanged = structuredClone(before);
  const diff = diffDecks(before, after);
  assert.equal(diff.hasChanges, true);
  const values = allChanges(diff).filter(item => !item.children).map(item => [item.before, item.after]);
  for (const pair of [['明确范围', '确认范围'], ['', '新讲稿'], ['原文', '修改正文'], ['原子项', '新子项'], ['p1', '新标题'], ['', '新副标题'], ['', '新目的'], ['', '双栏']]) {
    assert.ok(values.some(value => JSON.stringify(value) === JSON.stringify(pair)), JSON.stringify(pair));
  }
  assert.deepEqual(before, unchanged);
  assert.deepEqual(diffDecks(before, after), diff);
});

test('missing or duplicate identities fall back to full values without fuzzy pairing', () => {
  for (const invalid of ['', undefined, 'duplicate']) {
    const before = deck();
    before.pages[0].content.body_blocks = [
      { type: 'paragraph', id: invalid, text: '相似正文' },
      { type: 'paragraph', id: invalid, text: '其他正文' },
    ];
    const after = structuredClone(before);
    after.pages[0].content.body_blocks[0].text = '相似正文已改';
    const changes = allChanges(diffDecks(before, after)).filter(item => item.kind === 'full');
    assert.equal(changes.length, 1);
    assert.deepEqual(changes[0].before, before.pages[0].content.body_blocks);
    assert.deepEqual(changes[0].after, after.pages[0].content.body_blocks);
  }
  const before = deck();
  delete before.pages[0].id;
  const after = structuredClone(before);
  after.pages[0].notes = '新讲稿';
  assert.equal(diffDecks(before, after).pages[0].kind, 'full');
});

test('block type changes are replacements and table structure, text, value and unit are distinct', () => {
  const before = deck();
  before.pages[0].content.body_blocks = [{
    id: 'table', type: 'table', title: '预算', columns: [{ id: 'c1', label: '金额' }],
    rows: [{ id: 'r1', cells: [{ id: 's1', column_id: 'c1', display_text: '10 元', value: 10, unit: '元' }] }],
  }];
  const after = structuredClone(before);
  const table = after.pages[0].content.body_blocks[0];
  table.columns[0].label = '成本';
  table.columns.push({ id: 'c2', label: '说明' });
  table.rows.push({ id: 'r2', cells: [] });
  Object.assign(table.rows[0].cells[0], { display_text: '20 万元', value: 20, unit: '万元' });
  const changes = allChanges(diffDecks(before, after));
  assert.ok(changes.some(item => item.before === '10 元' && item.after === '20 万元'));
  assert.deepEqual(changes.filter(item => item.kind === 'metadata').map(item => [item.before, item.after]), [[10, 20], ['元', '万元']]);
  assert.equal(changes.filter(item => item.kind === 'added').length, 2);
  table.type = 'paragraph';
  assert.ok(allChanges(diffDecks(before, after)).some(item => item.kind === 'replaced'));
});

test('removed table cells retain the deleted column label and column changes use each snapshot', () => {
  const before = deck();
  before.pages[0].content.body_blocks = [{
    id: 'table', type: 'table', columns: [{ id: 'c0', label: '税费' }, { id: 'c1', label: '金额' }, { id: 'c2', label: '说明' }],
    rows: [{ id: 'r1', cells: [
      { id: 's1', column_id: 'c0', display_text: '10 元' },
      { id: 's2', column_id: 'c1', display_text: '补充' },
    ] }],
  }];
  const after = structuredClone(before);
  const table = after.pages[0].content.body_blocks[0];
  table.columns.splice(0, 2);
  table.rows[0].cells.shift();
  table.rows[0].cells[0].column_id = 'c2';
  const changes = allChanges(diffDecks(before, after));
  const removed = changes.find(item => item.kind === 'removed' && item.before.id === 's1');
  assert.equal(removed.label, '单元格 1：税费');
  assert.ok(changes.some(item => item.label === '所属列' && item.before === '金额' && item.after === '说明'));
});

test('artifact and workspace presentation churn alone is not a body change', () => {
  const before = deck();
  const after = structuredClone(before);
  Object.assign(after.pages[0], { image: { file: 'new.png' }, svg: { file: 'new.svg' }, preview: 'preview.png', open_reviews: 2 });
  after.materials = [{ id: 'm1', file: 'material.pdf' }];
  after.style = { palette: ['#ffffff'] };
  assert.deepEqual(diffDecks(before, after), { brief: [], framing: [], pages: [], hasChanges: false });
});
