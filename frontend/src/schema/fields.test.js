import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import {
  ARGUMENT_FIELDS,
  BRIEF_FIELDS,
  CONTENT_FIELDS,
  EVIDENCE_FIELDS,
  FRAMING_FIELDS,
  NARRATOR_FIELDS,
  PAGE_AUTHOR_FIELDS,
  PAGE_FIELDS,
  PAGE_KINDS,
  buildEvidenceItem,
  evidenceMode,
} from './fields.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const modelSource = readFileSync(path.resolve(here, '../../../rust/src/model.rs'), 'utf8');

function rustStructFields(structName) {
  const pattern = new RegExp(`pub struct ${structName} \\{([\\s\\S]*?)\\n\\}`);
  const match = modelSource.match(pattern);
  assert.ok(match, `struct ${structName} not found in rust/src/model.rs`);
  return [...match[1].matchAll(/^\s*pub\s+(?:r#)?([a-z_]+)\s*:/gm)].map(entry => entry[1]);
}

test('schema field registry matches rust/src/model.rs structs completely', () => {
  assert.deepEqual(Object.keys(BRIEF_FIELDS).sort(), rustStructFields('Brief').sort());
  assert.deepEqual(Object.keys(NARRATOR_FIELDS).sort(), rustStructFields('Narrator').sort());
  assert.deepEqual(Object.keys(FRAMING_FIELDS).sort(), rustStructFields('Framing').sort());
  assert.deepEqual(Object.keys(CONTENT_FIELDS).sort(), rustStructFields('Content').sort());
  assert.deepEqual(Object.keys(ARGUMENT_FIELDS).sort(), rustStructFields('Argument').sort());
  assert.deepEqual(Object.keys(EVIDENCE_FIELDS).sort(), rustStructFields('Evidence').sort());

  const nonAuthorPageFields = new Set(['id', 'image', 'svg', 'native', 'preview', 'legacy_revision']);
  const rustAuthorPageFields = rustStructFields('Page').filter(name => !nonAuthorPageFields.has(name));
  assert.deepEqual(Object.keys(PAGE_AUTHOR_FIELDS).sort(), rustAuthorPageFields.sort());
  assert.deepEqual(
    ['content', ...Object.keys(PAGE_FIELDS)].sort(),
    Object.keys(PAGE_AUTHOR_FIELDS).sort(),
  );

  const kindsMatch = modelSource.match(/pub const PAGE_KINDS: &\[&str\] = &\[([^\]]+)\];/);
  assert.ok(kindsMatch, 'PAGE_KINDS not found in rust/src/model.rs');
  const rustKinds = [...kindsMatch[1].matchAll(/"([^"]+)"/g)].map(entry => entry[1]);
  assert.deepEqual(PAGE_KINDS, rustKinds);
});

test('evidence helper guarantees mutual exclusion between ref and gap', () => {
  const refItem = buildEvidenceItem('试点样本', 'ref', 'm1 第 1 页');
  assert.deepEqual(refItem, { text: '试点样本', ref: 'm1 第 1 页' });
  assert.equal(Object.hasOwn(refItem, 'gap'), false);
  assert.equal(evidenceMode(refItem), 'ref');

  const gapItem = buildEvidenceItem('缺少对照数据', 'gap', '需补充去年同期基线');
  assert.deepEqual(gapItem, { text: '缺少对照数据', gap: '需补充去年同期基线' });
  assert.equal(Object.hasOwn(gapItem, 'ref'), false);
  assert.equal(evidenceMode(gapItem), 'gap');
});
