// Starting point: the project's own produce_page.cjs (first-party).
// Generic pixel-coordinate primitives; page composition belongs in each plan.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const PptxGenJS = require('pptxgenjs');

const DEFAULT_FONT = 'Noto Sans CJK SC';
const color = value => String(value).replace(/^#/, '');
const box = ([x, y, w, h]) => ({ x: x / 96, y: y / 96, w: w / 96, h: h / 96 });
const line = (value = {}) => ({
  color: color(value.color || '000000'), width: (value.width ?? 1) * 0.75,
  transparency: value.color === 'none' ? 100 : 0,
  beginArrowType: value.arrowheads?.start, endArrowType: value.arrowheads?.end,
});
function textStyle(op) {
  return {
    fontSize: (op.size ?? 16) * 0.75, fontFace: op.font || DEFAULT_FONT,
    color: color(op.color || '000000'), bold: op.weight === 'bold' || op.weight >= 600,
    align: op.align || 'left', valign: { center: 'mid', bottom: 'bottom', top: 'top' }[op.valign || 'top'],
    margin: 0, paraSpaceAfterPt: 0, breakLine: false,
  };
}
function draw(pptx, slide, op, index, page, iconsDir) {
  const objectName = `native_${index}`;
  switch (op.op) {
    case 'text':
      slide.addText(op.text, { ...box(op.bbox), ...textStyle(op), objectName });
      break;
    case 'shape': {
      // Custom geometry is written by the shared Python XML postprocessor.
      const type = op.type === 'custom' ? 'rect' : op.type;
      if (!pptx.ShapeType[type]) throw new Error(`不支持的形状：${type}`);
      const options = {
        ...box(op.bbox), objectName,
        fill: { color: color(op.fill === 'none' ? 'FFFFFF' : op.fill || 'FFFFFF'),
          transparency: op.fill === 'none' ? 100 : op.transparency ?? 0 },
        line: op.line ? line(op.line) : { transparency: 100 },
        flipH: op.flip?.h || false, flipV: op.flip?.v || false,
      };
      slide.addShape(pptx.ShapeType[type] || type, options);
      break;
    }
    case 'arrow': {
      const [x1, y1] = op.start, [x2, y2] = op.end;
      slide.addShape(pptx.ShapeType.line, {
        ...box([Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1)]),
        flipH: x1 > x2, flipV: y1 > y2, objectName,
        line: line({ color: op.color, width: op.width, arrowheads: op.arrowheads }),
      });
      break;
    }
    case 'icon': {
      const name = op.icon_id.slice('tabler-outline/'.length);
      const svg = fs.readFileSync(path.join(iconsDir, `${name}.svg`), 'utf8')
        .replaceAll('currentColor', `#${color(op.color || '000000')}`);
      slide.addImage({ data: `image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`,
        ...box(op.bbox), objectName });
      break;
    }
    case 'image':
      slide.addImage({ path: path.resolve(path.dirname(page.plan), op.file), ...box(op.bbox), objectName });
      break;
    case 'table': {
      const rows = op.cells.map((row, r) => row.map(cell => ({
        text: cell.text,
        options: { ...textStyle({ ...op, ...(r === 0 ? op.header_style : {}), ...cell }),
          ...(r === 0 && op.header_style?.fill ? { fill: color(op.header_style.fill) } : {}) },
      })));
      slide.addTable(rows, {
        ...box(op.bbox), ...textStyle(op), objectName, autoPage: false,
        colW: op.col_widths.map(w => w / 96), rowH: op.row_heights.map(h => h / 96),
        border: { type: 'solid', color: color(op.line?.color || '000000'), pt: (op.line?.width ?? 1) * 0.75 },
      });
      break;
    }
    default: throw new Error(`不支持的原语：${op.op}`);
  }
}
function scaleOp(op, sx, sy) {
  const result = structuredClone(op);
  if (op.bbox) result.bbox = op.bbox.map((v, i) => v * (i % 2 ? sy : sx));
  if (op.start) result.start = [op.start[0] * sx, op.start[1] * sy];
  if (op.end) result.end = [op.end[0] * sx, op.end[1] * sy];
  if (op.size) result.size = op.size * sy;
  if (op.col_widths) result.col_widths = op.col_widths.map(v => v * sx);
  if (op.row_heights) result.row_heights = op.row_heights.map(v => v * sy);
  if (op.header_style?.size) result.header_style.size *= sy;
  if (op.cells) result.cells.forEach(row => row.forEach(cell => { if (cell.size) cell.size *= sy; }));
  if (op.width) result.width *= sy;
  if (op.line?.width) result.line.width *= sy;
  return result;
}
async function main() {
  const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  if (!['single', 'deck'].includes(job.mode) || !job.pages.length || (job.mode === 'single' && job.pages.length !== 1)) {
    throw new Error('请选择单页或整套模式并传入对应页面');
  }
  const pptx = new PptxGenJS();
  const canvas = JSON.parse(fs.readFileSync(job.pages[0].plan, 'utf8')).canvas_px;
  pptx.defineLayout({ name: 'native', width: canvas.w / 96, height: canvas.h / 96 });
  pptx.layout = 'native';
  pptx.lang = 'zh-CN';
  pptx.theme = { headFontFace: DEFAULT_FONT, bodyFontFace: DEFAULT_FONT, lang: 'zh-CN' };
  for (const page of job.pages) {
    const plan = JSON.parse(fs.readFileSync(page.plan, 'utf8'));
    const slide = pptx.addSlide();
    slide.background = { color: color(plan.background) };
    plan.ops.forEach((op, i) => draw(pptx, slide, scaleOp(op, canvas.w / plan.canvas_px.w, canvas.h / plan.canvas_px.h), i, page, job.icons_dir));
    slide.addNotes(page.notes || '');
  }
  await pptx.writeFile({ fileName: job.output });
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
