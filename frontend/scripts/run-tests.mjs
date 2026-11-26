import { readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const srcDir = path.join(root, 'src');

function discoverTests(dir) {
  const results = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...discoverTests(full));
    } else if (entry.isFile() && entry.name.endsWith('.test.js')) {
      results.push(path.relative(root, full));
    }
  }
  return results;
}

const files = discoverTests(srcDir).sort();
if (files.length === 0) {
  console.error('No *.test.js files found under src/');
  process.exit(1);
}

const result = spawnSync(
  process.execPath,
  ['--import', './src/test/register-jsx.js', '--test', ...files],
  { cwd: root, stdio: 'inherit' },
);
process.exit(result.status ?? 1);
