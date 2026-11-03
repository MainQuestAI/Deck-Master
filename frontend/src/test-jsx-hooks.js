import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { transformSync } from 'esbuild';

export async function resolve(specifier, context, nextResolve) {
  if (!specifier.startsWith('.')) return nextResolve(specifier, context);
  let error;
  for (const candidate of [specifier, `${specifier}.jsx`, `${specifier}.js`]) {
    try {
      const resolved = await nextResolve(candidate, context);
      if (resolved.url.endsWith('.jsx')) return { ...resolved, format: 'module' };
      return resolved;
    } catch (caught) {
      error = caught;
    }
  }
  throw error;
}

export async function load(url, context, nextLoad) {
  if (!url.endsWith('.jsx')) return nextLoad(url, context);
  const source = await readFile(fileURLToPath(url), 'utf8');
  const transformed = transformSync(source, {
    loader: 'jsx',
    format: 'esm',
    jsx: 'automatic',
    sourcefile: url,
  });
  return { format: 'module', source: transformed.code, shortCircuit: true };
}
