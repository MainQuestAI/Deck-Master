import {
  ARGUMENT_FIELDS,
  BRIEF_FIELDS,
  CONTENT_FIELDS,
  FRAMING_FIELDS,
  NARRATOR_FIELDS,
  PAGE_FIELDS,
} from './schema/fields.js';

export const briefFields = BRIEF_FIELDS;
export const framingFields = FRAMING_FIELDS;
export const pageFields = PAGE_FIELDS;
export const contentFields = CONTENT_FIELDS;
const argumentFields = ARGUMENT_FIELDS;
const narratorFields = NARRATOR_FIELDS;

function equal(left, right) {
  if (left === right) return true;
  if (left == null || right == null || typeof left !== 'object' || typeof right !== 'object') return false;
  if (Array.isArray(left) !== Array.isArray(right)) return false;
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length && keys.every(key => Object.hasOwn(right, key) && equal(left[key], right[key]));
}

function field(label, before, after, kind = 'changed') {
  return equal(before, after) ? [] : [{ label, before, after, kind }];
}

function fields(before, after, labels) {
  return Object.entries(labels).flatMap(([key, label]) => field(label, before?.[key], after?.[key]));
}

function reliableIds(items) {
  return items.every(item => typeof item?.id === 'string' && item.id.length > 0)
    && new Set(items.map(item => item.id)).size === items.length;
}

// Compare common identities in relative order so an insertion alone is not a move.
function sequence(label, before = [], after = [], compare, name = (_, index) => `${label} ${index + 1}`) {
  if (equal(before, after)) return [];
  if (!reliableIds(before) || !reliableIds(after)) return [{ label, before, after, kind: 'full' }];
  const oldById = new Map(before.map((item, index) => [item.id, { item, index }]));
  const newById = new Map(after.map((item, index) => [item.id, { item, index }]));
  const oldCommon = before.filter(item => newById.has(item.id)).map(item => item.id);
  const newCommon = after.filter(item => oldById.has(item.id)).map(item => item.id);
  const changes = [];
  for (const [index, item] of before.entries()) {
    if (!newById.has(item.id)) changes.push({ label: name(item, index, 'before'), before: item, after: undefined, kind: 'removed' });
  }
  for (const [index, item] of after.entries()) {
    const old = oldById.get(item.id);
    if (!old) {
      changes.push({ label: name(item, index, 'after'), before: undefined, after: item, kind: 'added' });
      continue;
    }
    const children = compare(old.item, item);
    if (oldCommon.indexOf(item.id) !== newCommon.indexOf(item.id)) {
      children.unshift({ label: '位置变化', before: old.index + 1, after: index + 1, kind: 'moved' });
    }
    if (children.length) changes.push({ label: name(item, index, 'after'), kind: 'changed', children });
  }
  return changes.length ? [{ label, kind: 'changed', children: changes }] : [];
}

function textItems(label, before, after) {
  return sequence(label, before, after, (left, right) => [
    ...field('文字', left.text, right.text),
    ...field('语气', left.tone, right.tone),
    ...textItems('子项', left.children, right.children),
  ]);
}

function blockChanges(left, right) {
  if (left.type !== right.type) return [{ label: '正文块类型替换', before: left, after: right, kind: 'replaced' }];
  if (left.type === 'paragraph') return field('段落', left.text, right.text);
  if (left.type === 'bullets') return [
    ...field('要点标题', left.heading, right.heading),
    ...textItems('要点', left.items, right.items),
  ];
  if (left.type === 'table') return [
    ...field('表格标题', left.title, right.title),
    ...sequence('列', left.columns, right.columns, (a, b) => field('列标题', a.label, b.label), (column, index) => `列 ${index + 1}：${column.label || '未命名'}`),
    ...sequence('行', left.rows, right.rows, (a, b) => sequence('单元格', a.cells, b.cells, (old, next) => [
      ...field('所属列', left.columns?.find(column => column.id === old.column_id)?.label || old.column_id,
        right.columns?.find(column => column.id === next.column_id)?.label || next.column_id),
      ...field('显示文字', old.display_text, next.display_text),
      ...field('原始值变化', old.value, next.value, 'metadata'),
      ...field('单位变化', old.unit, next.unit, 'metadata'),
    ], (cell, index, side) => `单元格 ${index + 1}：${(side === 'before' ? left : right).columns?.find(column => column.id === cell.column_id)?.label || '未命名列'}`)),
  ];
  return field('正文块', left, right, 'full');
}

export function authorPage(page) {
  return {
    id: page.id, ...Object.fromEntries(Object.keys(pageFields).map(key => [key, page[key]])),
    content: Object.fromEntries(Object.keys(contentFields).map(key => [key, page.content?.[key]])),
  };
}

function objectFieldsChanges(label, before, after, fieldLabels) {
  if (equal(before, after)) return [];
  if (before && after && typeof before === 'object' && typeof after === 'object') {
    const children = fields(before, after, fieldLabels);
    return children.length ? [{ label, kind: 'changed', children }] : [];
  }
  return [{ label, before: before ?? null, after: after ?? null, kind: 'changed' }];
}

function pageChanges(left, right) {
  const { argument: _ignored, ...scalarPageFields } = pageFields;
  return [
    ...fields(left, right, scalarPageFields),
    ...objectFieldsChanges(pageFields.argument, left.argument, right.argument, argumentFields),
    ...fields(left.content, right.content, { title: '页面标题', subtitle: '副标题' }),
    ...sequence('正文块', left.content?.body_blocks, right.content?.body_blocks, blockChanges,
      (block, index) => `${block.type === 'table' ? '表格' : block.type === 'bullets' ? '要点组' : '段落'} ${index + 1}`),
    ...['labels', 'callouts', 'footnotes'].flatMap(key => textItems(contentFields[key], left.content?.[key], right.content?.[key])),
  ];
}

export function diffDecks(left, right) {
  const { narrator: _ignored, ...scalarBriefFields } = briefFields;
  const brief = [
    ...fields(left.brief, right.brief, scalarBriefFields),
    ...objectFieldsChanges(briefFields.narrator, left.brief?.narrator, right.brief?.narrator, narratorFields),
  ];
  const framing = fields(left.framing, right.framing, framingFields);
  const pages = sequence('页面', (left.pages || []).map(authorPage), (right.pages || []).map(authorPage), pageChanges,
    (page, index) => `第 ${index + 1} 页：${page.content?.title || '未命名页面'}`);
  return { brief, framing, pages, hasChanges: brief.length + framing.length + pages.length > 0 };
}
