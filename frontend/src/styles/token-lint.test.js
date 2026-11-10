import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, mkdirSync, writeFileSync, copyFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { lintCssSources } from '../../scripts/lint-css-tokens.mjs';

const file = 'src/styles/sample.css';
const config = { maxImportant: 13, whitelist: [] };
const lint = (css, options = config) => lintCssSources([{ file, css }], options);
const exemption = { file, selector: '.card', literal: '#abc', reason: 'Fixed color in an embedded diagram' };

test('the real app stylesheet and the CLI pass the checked-in configuration', () => {
  const options = JSON.parse(readFileSync(new URL('../../css-token-lint.config.json', import.meta.url), 'utf8'));
  const css = readFileSync(new URL('./app.css', import.meta.url), 'utf8');
  const result = lintCssSources([{ file: 'src/styles/app.css', css }], options);
  assert.deepEqual(result.errors, []);
  assert.equal(result.literalsOutside, 0);
  assert.ok(result.importantCount <= options.maxImportant);
  const run = spawnSync(process.execPath, [fileURLToPath(new URL('../../scripts/lint-css-tokens.mjs', import.meta.url))], {
    cwd: tmpdir(), encoding: 'utf8',
  });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
});

test('component colors fail with their original file, line, and literal', () => {
  for (const literal of ['#abc', '#aabbccdd', 'rgb(1, 2, 3)', 'rgba(1, 2, 3, .5)', 'hsl(0 0% 50%)', 'hsla(0, 0%, 50%, .5)']) {
    const result = lint(`/* #fff is only a comment */\n.card {\n  color: ${literal};\n}`);
    assert.equal(result.errors.length, 1);
    assert.ok(result.errors[0].includes(`${file}:3:${literal}`));
  }
});

test('only an entire token selector exempts its own declarations, including inside media rules', () => {
  for (const selector of [':root', '[data-theme="dark"]', 'html[data-theme="dark"]']) {
    assert.deepEqual(lint(`@media (min-width: 10px) { ${selector} { --dm-color: #fff; } }`).errors, []);
  }
  for (const selector of [':root .card', '[data-theme="dark"] .dm-kbd', ':root, .card', ':root, [data-theme="dark"]']) {
    assert.equal(lint(`${selector} { color: #fff; }`).literalsOutside, 1);
  }
  assert.equal(lint(':root { --dm-color: #fff; .card { color: #000; } }').literalsOutside, 1);
  assert.deepEqual(lint(':root { @media (min-width: 10px) { --dm-color: #fff; } }').errors, []);
});

test('nested at-rules and keyframes do not exempt component or animation colors', () => {
  const result = lint(`@media (min-width: 1px) {
  @supports (display: grid) {
    :root { --dm-color: #fff; }
    .card { background: rgba(1, 2, 3, .5); }
  }
}
@keyframes pulse { from { box-shadow: 0 0 1px #abc; } }
@font-face { font-family: example; color: #123; }`);
  assert.equal(result.literalsOutside, 3);
  assert.ok(result.errors[0].includes(`${file}:4:rgba(1, 2, 3, .5)`));
  assert.ok(result.errors[1].includes(`${file}:7:#abc`));
  assert.ok(result.errors[2].includes(`${file}:8:#123`));
  assert.equal(lint('@supports (color: rgb(1, 2, 3)) { .card { color: var(--dm-color); } }').literalsOutside, 1);
});

test('comments, strings, and selector IDs do not masquerade as declarations or braces', () => {
  const result = lint(`/* .card { color: #fff !important; } */
#abc[data-label="}"] { content: "/* #fff */ { rgba(1,2,3,.5) !important"; background: var(--dm-color); }`);
  assert.deepEqual(result.errors, []);
  assert.equal(result.importantCount, 0);
});

test('a whitelist exempts only its exact file, selector, and literal', () => {
  assert.deepEqual(lint('.card { color: #abc; }', { ...config, whitelist: [exemption] }).errors, []);
  for (const entry of [{ ...exemption, file: 'src/other.css' }, { ...exemption, selector: '.other' }, { ...exemption, literal: '#fff' }]) {
    const result = lint('.card { color: #abc; }', { ...config, whitelist: [entry] });
    assert.equal(result.errors.length, 2);
    assert.ok(result.errors.some(error => error.includes(`${file}:1:#abc`)));
  }
});

test('whitelist entries without reasons, with unknown fields, or unused entries fail', () => {
  for (const reason of ['', '  ', undefined]) {
    assert.ok(lint('.card { color: #abc; }', { ...config, whitelist: [{ ...exemption, reason }] }).errors.length);
  }
  assert.ok(lint('.card { color: #abc; }', { ...config, whitelist: [{ ...exemption, extra: true }] }).errors.length);
  assert.ok(lint('.card { color: var(--dm-color); }', { ...config, whitelist: [exemption] }).errors.length);
});

test('important requires a nonempty reason comment on the same or preceding line', () => {
  for (const css of [
    '.card { color: var(--dm-color) !important; }',
    '.card {\n/* */\ncolor: var(--dm-color) !important;\n}',
    '.card { /* Too far away */\n\ncolor: var(--dm-color) !important;\n}',
    '.card { content: "/* a string is not a comment */"; color: var(--dm-color) !important; }',
  ]) {
    assert.equal(lint(css).errors.length, 1);
  }
  for (const css of [
    '.card { color: var(--dm-color) !important; /* Override inline color. */ }',
    '.card {\n/* Override inline color. */\ncolor: var(--dm-color) !important;\n}',
  ]) {
    assert.deepEqual(lint(css).errors, []);
  }
});

test('important limits apply to the aggregate across stylesheets, excluding comments', () => {
  const css = '.card { color: var(--dm-color) !important; /* Override inline color. */ }';
  const result = lintCssSources([{ file, css }, { file: 'src/other.css', css }], { ...config, maxImportant: 1 });
  assert.equal(result.importantCount, 2);
  assert.equal(result.errors.length, 1);
  assert.deepEqual(lint('/* !important */', { ...config, maxImportant: 0 }).errors, []);
});

test('the CLI scans nested CSS files and returns exit 1 for violations', () => {
  const directory = mkdtempSync(join(tmpdir(), 'deck-css-lint-'));
  try {
    mkdirSync(join(directory, 'scripts'));
    mkdirSync(join(directory, 'src/nested'), { recursive: true });
    copyFileSync(new URL('../../scripts/lint-css-tokens.mjs', import.meta.url), join(directory, 'scripts/lint-css-tokens.mjs'));
    writeFileSync(join(directory, 'css-token-lint.config.json'), JSON.stringify(config));
    writeFileSync(join(directory, 'src/nested/sample.css'), '.card {\n  color: #abc;\n}');
    const run = spawnSync(process.execPath, [join(directory, 'scripts/lint-css-tokens.mjs')], { encoding: 'utf8' });
    assert.ifError(run.error);
    assert.equal(run.status, 1);
    assert.ok(run.stderr.includes('src/nested/sample.css:2:#abc'), run.stderr);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
