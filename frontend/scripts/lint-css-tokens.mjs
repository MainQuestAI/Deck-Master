import { readdir, readFile } from 'node:fs/promises';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const tokenSelectors = new Set([':root', '[data-theme="dark"]', 'html[data-theme="dark"]']);

// Preserve offsets so diagnostics still point at the original source after stripping comments.
function stripComments(source) {
  const comments = [];
  const css = source.replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\*[\s\S]*?\*\//g, (text, start) => {
    if (!text.startsWith('/*')) return text;
    comments.push({ start, end: start + text.length, reason: text.slice(2, -2).trim() });
    return text.replace(/[^\n\r]/g, ' ');
  });
  return { css, comments };
}

function lineAt(source, offset) {
  return source.slice(0, offset).split('\n').length;
}

function hasReason(source, comments, offset) {
  const line = lineAt(source, offset);
  return comments.some(comment => comment.reason && (
    lineAt(source, comment.start) === line || lineAt(source, comment.end) === line - 1
  ));
}

function inspectCss(file, source) {
  const { css, comments } = stripComments(source);
  const literals = [];
  const important = [];
  const stack = [];
  let start = 0;
  let quote = null;
  let depth = 0;

  function inspectValue(value, offset, rule) {
    // Strings can contain examples or URL fragments that are not CSS color values.
    const pattern = /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#[\da-f]{3,8}\b|\b(?:rgba?|hsla?)\([^)]*\)|!\s*important\b/gi;
    for (const match of value.matchAll(pattern)) {
      if (match[0].startsWith('"') || match[0].startsWith("'")) continue;
      const position = offset + match.index;
      const item = { file, selector: rule, literal: match[0], line: lineAt(source, position) };
      if (match[0].startsWith('!')) {
        important.push({ ...item, reason: hasReason(source, comments, position) });
      } else if (!tokenSelectors.has(rule)) {
        literals.push(item);
      }
    }
  }

  function declaration(end) {
    // Grouping at-rules preserve the enclosing selector in native CSS nesting.
    const rule = stack.findLast(selector => !/^@(media|supports|container|layer|scope|starting-style)\b/i.test(selector)) ?? stack.at(-1);
    if (!rule) return;
    const text = css.slice(start, end);
    const property = /^\s*(?:--[\w-]+|[\w-]+)\s*:\s*/.exec(text);
    if (!property) return;
    const offset = start + property[0].length;
    inspectValue(text.slice(property[0].length), offset, rule);
  }

  for (let i = 0; i < css.length; i += 1) {
    const char = css[i];
    if (char === '\\') {
      i += 1;
      continue;
    }
    if (quote) {
      if (char === quote) quote = null;
      continue;
    }
    if (char === '"' || char === "'") quote = char;
    else if (char === '(' || char === '[') depth += 1;
    else if (char === ')' || char === ']') depth -= 1;
    else if (depth === 0 && char === '{') {
      const selector = css.slice(start, i).trim();
      if (selector.startsWith('@')) inspectValue(css.slice(start, i), start, selector);
      stack.push(selector);
      start = i + 1;
    } else if (depth === 0 && (char === ';' || char === '}')) {
      declaration(i);
      if (char === '}') stack.pop();
      start = i + 1;
    }
  }
  return { literals, important };
}

export function lintCssSources(sources, config) {
  const errors = [];
  const used = new Set();
  const whitelist = config.whitelist ?? [];
  if (!Array.isArray(whitelist)) {
    return { errors: ['配置 whitelist 必须是数组'], importantCount: 0, literalsOutside: 0 };
  }
  const valid = whitelist.map((entry, index) => {
    const keys = ['file', 'selector', 'literal', 'reason'];
    const ok = entry && typeof entry === 'object' &&
      keys.every(key => typeof entry[key] === 'string' && entry[key].trim()) &&
      Object.keys(entry).every(key => keys.includes(key));
    if (!ok) errors.push(`白名单第 ${index + 1} 项必须包含 file、selector、literal 和非空 reason，且不能有未知字段`);
    return ok;
  });
  let importantCount = 0;
  let literalsOutside = 0;
  for (const { file, css } of sources) {
    const { literals, important } = inspectCss(file, css);
    importantCount += important.length;
    literalsOutside += literals.length;
    for (const item of literals) {
      const index = whitelist.findIndex((entry, i) => valid[i] &&
        entry.file === item.file && entry.selector === item.selector && entry.literal === item.literal);
      if (index >= 0) used.add(index);
      else errors.push(`${item.file}:${item.line}:${item.literal} — ${item.selector} 的颜色必须使用 token`);
    }
    for (const item of important) {
      if (!item.reason) errors.push(`${item.file}:${item.line}:${item.literal} — 同行或上一行缺少原因注释`);
    }
  }
  whitelist.forEach((entry, index) => {
    if (valid[index] && !used.has(index)) errors.push(`未使用的白名单项：${entry.file}:${entry.selector}:${entry.literal}`);
  });
  return { errors, importantCount, literalsOutside };
}

async function cssFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await cssFiles(path));
    else if (entry.isFile() && entry.name.endsWith('.css')) files.push(path);
  }
  return files;
}

async function main() {
  const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const config = JSON.parse(await readFile(join(frontend, 'css-token-lint.config.json'), 'utf8'));
  const sources = [];
  for (const path of await cssFiles(join(frontend, 'src'))) {
    sources.push({ file: relative(frontend, path).split('\\').join('/'), css: await readFile(path, 'utf8') });
  }
  const result = lintCssSources(sources, config);
  if (result.errors.length) {
    process.stderr.write(`${result.errors.join('\n')}\n`);
    process.exitCode = 1;
  } else {
    process.stdout.write(`CSS token 检查通过：${sources.length} 个文件，!important=${result.importantCount}，token 块外颜色=${result.literalsOutside}\n`);
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => {
    process.stderr.write(`CSS token 检查失败：${error.message}\n`);
    process.exitCode = 1;
  });
}
