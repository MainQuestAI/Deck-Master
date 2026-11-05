export function collectContentIds(value) {
  const ids = new Set();
  const collect = item => {
    if (Array.isArray(item)) item.forEach(collect);
    else if (item && typeof item === 'object') {
      if (typeof item.id === 'string') ids.add(item.id);
      Object.values(item).forEach(collect);
    }
  };
  collect(value);
  return ids;
}

export function createContentId(prefix, usedIds = new Set(), randomUUID = () => crypto.randomUUID()) {
  let id;
  do { id = `${prefix}${randomUUID().replaceAll('-', '').slice(0, 8)}`; } while (usedIds.has(id));
  return id;
}

function allocator(usedIds, randomUUID) {
  const used = new Set(usedIds);
  return prefix => {
    const id = createContentId(prefix, used, randomUUID);
    used.add(id);
    return id;
  };
}

export function moveIndex(list, from, to) {
  if (from < 0 || from >= list.length || !Number.isInteger(to)) return list;
  const target = Math.max(0, Math.min(list.length - 1, to));
  if (target === from) return list;
  const next = [...list];
  next.splice(target, 0, ...next.splice(from, 1));
  return next;
}

export function createParagraph(usedIds, randomUUID) {
  return { type: 'paragraph', id: createContentId('b', usedIds, randomUUID), text: '' };
}

export function createBulletItem(usedIds, randomUUID) {
  return { id: createContentId('i', usedIds, randomUUID), text: '' };
}

export function createBullets(usedIds = new Set(), randomUUID) {
  const id = allocator(usedIds, randomUUID);
  return { type: 'bullets', id: id('b'), heading: '', items: [{ id: id('i'), text: '' }] };
}

export function createTable(usedIds = new Set(), randomUUID) {
  const id = allocator(usedIds, randomUUID);
  const blockId = id('b');
  const columnId = id('c');
  return {
    type: 'table', id: blockId, title: '', columns: [{ id: columnId, label: '' }],
    rows: [{ id: id('r'), cells: [{ id: id('cell'), column_id: columnId, display_text: '' }] }],
  };
}

// Removing an item removes its whole subtree; siblings remain intact.
export function removeBulletItem(items, itemId) {
  return items.filter(item => item.id !== itemId);
}

export function addColumn(table, usedIds = new Set(), randomUUID) {
  const id = allocator(new Set([...usedIds, ...collectContentIds(table)]), randomUUID);
  const columnId = id('c');
  return {
    ...table, columns: [...table.columns, { id: columnId, label: '' }],
    rows: table.rows.map(row => ({ ...row, cells: [...row.cells, { id: id('cell'), column_id: columnId, display_text: '' }] })),
  };
}

export function removeColumn(table, columnId) {
  return {
    ...table, columns: table.columns.filter(column => column.id !== columnId),
    rows: table.rows.map(row => ({ ...row, cells: row.cells.filter(cell => cell.column_id !== columnId) })),
  };
}

export function moveColumn(table, columnId, toIndex) {
  return { ...table, columns: moveIndex(table.columns, table.columns.findIndex(column => column.id === columnId), toIndex) };
}

export function addRow(table, usedIds = new Set(), randomUUID) {
  const id = allocator(new Set([...usedIds, ...collectContentIds(table)]), randomUUID);
  const row = { id: id('r'), cells: table.columns.map(column => ({ id: id('cell'), column_id: column.id, display_text: '' })) };
  return { ...table, rows: [...table.rows, row] };
}

export function removeRow(table, rowId) {
  return { ...table, rows: table.rows.filter(row => row.id !== rowId) };
}

export function moveRow(table, rowId, toIndex) {
  return { ...table, rows: moveIndex(table.rows, table.rows.findIndex(row => row.id === rowId), toIndex) };
}

function patchCell(table, rowId, columnId, patch, usedIds, randomUUID) {
  return {
    ...table, rows: table.rows.map(row => {
      if (row.id !== rowId) return row;
      const cell = row.cells.find(item => item.column_id === columnId);
      return { ...row, cells: cell
        ? row.cells.map(item => item === cell ? { ...item, ...patch } : item)
        : [...row.cells, {
          id: createContentId('cell', new Set([...usedIds, ...collectContentIds(table)]), randomUUID),
          column_id: columnId, display_text: '', ...patch,
        }] };
    }),
  };
}

export function setCellDisplayText(table, rowId, columnId, text, usedIds = new Set(), randomUUID) {
  return patchCell(table, rowId, columnId, { display_text: text }, usedIds, randomUUID);
}

export function setCellValue(table, rowId, columnId, value, usedIds = new Set(), randomUUID) {
  return patchCell(table, rowId, columnId, { value }, usedIds, randomUUID);
}

export function setCellUnit(table, rowId, columnId, unit, usedIds = new Set(), randomUUID) {
  return patchCell(table, rowId, columnId, { unit }, usedIds, randomUUID);
}
