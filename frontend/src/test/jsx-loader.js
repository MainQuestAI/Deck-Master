import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { transformSync } from 'esbuild';

// Vite resolves extensionless imports. Node's test runner does not, and it does not parse JSX.
export async function resolve(specifier, context, nextResolve) {
  if (!specifier.startsWith('.') && !specifier.startsWith('/')) return nextResolve(specifier, context);
  try {
    return await nextResolve(specifier, context);
  } catch (error) {
    for (const extension of ['.jsx', '.js']) {
      try {
        return await nextResolve(specifier + extension, context);
      } catch { /* The import may use the other extension. */ }
    }
    throw error;
  }
}

export async function load(url, context, nextLoad) {
  if (!url.startsWith('file:') || !url.endsWith('.jsx')) return nextLoad(url, context);
  const filename = fileURLToPath(url);
  const source = await readFile(filename, 'utf8');
  const result = transformSync(source, {
    loader: 'jsx',
    format: 'esm',
    jsx: 'automatic',
    sourcefile: filename,
    sourcemap: 'inline',
  });
  return { format: 'module', source: result.code, shortCircuit: true };
}
