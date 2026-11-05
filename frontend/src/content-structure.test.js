import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  collectContentIds, createContentId, createParagraph, createBullets, createBulletItem, createTable,
  moveIndex, removeBulletItem, addColumn, removeColumn, moveColumn, addRow, removeRow, moveRow,
  setCellDisplayText, setCellValue, setCellUnit,
} from './content-structure.js';

function sequence() {
  let n = 0;
  return () => (++n).toString(16).padStart(8, '0') + '-0000-0000-0000-000000000000';
}

function table() {
  return {
    type: 'table', id: 'table', title: '合成预算', columns: [{ id: 'name', label: '项' }, { id: 'amount', label: '预算' }],
    rows: [
      { id: 'first', cells: [
        { id: 'a', column_id: 'amount', display_text: '约20万元', value: 200000, unit: '元' },
        { id: 'b', column_id: 'name', display_text: '试点', value: false },
      ] },
      { id: 'second', cells: [
        { id: 'c', column_id: 'name', display_text: '后续', value: { range: [1, 2] } },
        { id: 'd', column_id: 'amount', display_text: '待定', value: 0, unit: '%' },
      ] },
    ],
  };
}

function allIds(value) {
  if (Array.isArray(value)) return value.flatMap(allIds);
  if (!value || typeof value !== 'object') return [];
  return [...(value.id ? [value.id] : []), ...Object.values(value).flatMap(allIds)];
}

test('factories and table additions allocate unique stable IDs across the full content draft', () => {
  const randomUUID = sequence();
  const content = { body_blocks: [], labels: [{ id: 'b00000001', text: '保留标签' }] };
  const before = structuredClone(content);
  const paragraph = createParagraph(collectContentIds(content), randomUUID);
  content.body_blocks.push(paragraph);
  content.body_blocks.push(createBullets(collectContentIds(content), randomUUID));
  content.body_blocks[1].items.push(createBulletItem(collectContentIds(content), randomUUID));
  content.body_blocks.push(createTable(collectContentIds(content), randomUUID));
  let current = addColumn(content.body_blocks[2], collectContentIds(content), randomUUID);
  content.body_blocks[2] = current;
  current = addRow(current, collectContentIds(content), randomUUID);
  content.body_blocks[2] = current;
  const ids = allIds(content);
  assert.equal(new Set(ids).size, ids.length);
  assert.ok(ids.every(Boolean));
  assert.equal(content.body_blocks[0], paragraph);
  assert.deepEqual(content.labels, before.labels);
  for (const row of current.rows) {
    assert.deepEqual(row.cells.map(cell => cell.column_id), current.columns.map(column => column.id));
    assert.ok(row.cells.every(cell => !Object.hasOwn(cell, 'value') && !Object.hasOwn(cell, 'unit')));
  }
  const used = new Set(['b12345678']);
  const candidates = ['12345678-0000', '87654321-0000'];
  assert.equal(createContentId('b', used, () => candidates.shift()), 'b87654321');
  assert.deepEqual([...used], ['b12345678']);
});

test('adding and moving columns preserves cell identity and mapping before save (B5)', () => {
  const original = table();
  const before = structuredClone(original);
  const added = addColumn(original, new Set(), sequence());
  const columnId = added.columns.at(-1).id;
  const edited = setCellDisplayText(added, 'first', columnId, '新增第一行');
  const moved = moveColumn(edited, columnId, 0);
  assert.deepEqual(moved.columns.map(column => column.id), [columnId, 'name', 'amount']);
  assert.equal(moved.rows, edited.rows);
  assert.deepEqual(moved.rows.map(row => moved.columns.map(column => row.cells.find(cell => cell.column_id === column.id).display_text)), [
    ['新增第一行', '试点', '约20万元'], ['', '后续', '待定'],
  ]);
  assert.deepEqual(original, before);
  assert.deepEqual(removeColumn(moved, columnId), original);
});

test('removing a column only removes cells linked to that column', () => {
  const original = table();
  const removed = removeColumn(original, 'name');
  assert.deepEqual(removed.columns.map(column => column.id), ['amount']);
  removed.rows.forEach((row, index) => assert.equal(row.cells[0], original.rows[index].cells.find(cell => cell.column_id === 'amount')));
});

test('moving and deleting rows keeps other cells, values and units intact', () => {
  const original = table();
  const before = structuredClone(original);
  const moved = moveRow(original, 'second', 0);
  assert.equal(moved.rows[0], original.rows[1]);
  const removed = removeRow(moved, 'first');
  assert.deepEqual(removed.rows, [original.rows[1]]);
  assert.equal(removed.rows[0], original.rows[1]);
  assert.deepEqual(original, before);
});

test('display text editing never guesses or clears value/unit; missing cells are created only on input', () => {
  const original = table();
  const edited = setCellDisplayText(original, 'first', 'amount', '待定');
  assert.deepEqual(edited.rows[0].cells[0], { ...original.rows[0].cells[0], display_text: '待定' });
  assert.equal(edited.rows[0].cells[1], original.rows[0].cells[1]);
  assert.equal(edited.rows[1], original.rows[1]);
  const incomplete = { ...original, rows: [{ id: 'first', cells: [original.rows[0].cells[1]] }] };
  const patched = setCellDisplayText(incomplete, 'first', 'amount', '约20%', collectContentIds(original), sequence());
  assert.equal(patched.rows[0].cells[0], incomplete.rows[0].cells[0]);
  assert.deepEqual(patched.rows[0].cells[1], { id: 'cell00000001', column_id: 'amount', display_text: '约20%' });
});

test('explicit scalar value and unit edits affect only the selected metadata', () => {
  const original = table();
  const numeric = setCellValue(original, 'first', 'amount', 0);
  assert.deepEqual(numeric.rows[0].cells[0], { ...original.rows[0].cells[0], value: 0 });
  const cleared = setCellUnit(setCellValue(numeric, 'first', 'amount', null), 'first', 'amount', null);
  assert.deepEqual(cleared.rows[0].cells[0], { ...original.rows[0].cells[0], value: null, unit: null });
  assert.equal(cleared.rows[1], original.rows[1]);
});

test('removing a bullet item removes its subtree and preserves siblings including tone', () => {
  const items = [{ id: 'parent', text: '范围', children: [{ id: 'child', text: '细节', children: [{ id: 'grandchild', text: '说明' }] }] }, { id: 'sibling', text: '行动', tone: 'emphasis' }];
  assert.deepEqual(removeBulletItem(items, 'parent'), [items[1]]);
  assert.equal(removeBulletItem(items, 'parent')[0], items[1]);
  assert.equal(items.length, 2);
});

test('reordering blocks preserves the complete content including labels/callouts/footnotes', () => {
  const original = {
    title: '合成方案', subtitle: '试点', body_blocks: [createParagraph(new Set(), sequence()), table()],
    labels: [{ id: 'label', text: '标签' }], callouts: [{ id: 'callout', text: '补充' }], footnotes: [{ id: 'footnote', text: '脚注' }],
  };
  const reordered = { ...original, body_blocks: moveIndex(original.body_blocks, 0, 1) };
  assert.deepEqual(reordered, { ...original, body_blocks: [original.body_blocks[1], original.body_blocks[0]] });
  for (const key of ['labels', 'callouts', 'footnotes']) assert.equal(reordered[key], original[key]);
});

test('empty tables can gain rows and columns in either order', () => {
  const empty = { type: 'table', id: 'empty', title: '', columns: [], rows: [] };
  for (const rowFirst of [false, true]) {
    const uuid = sequence();
    const result = rowFirst ? addColumn(addRow(empty, new Set(), uuid), new Set(), uuid) : addRow(addColumn(empty, new Set(), uuid), new Set(), uuid);
    assert.equal(result.rows[0].cells[0].column_id, result.columns[0].id);
  }
});
