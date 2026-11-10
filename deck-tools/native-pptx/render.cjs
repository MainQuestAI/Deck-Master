// Starting point: the project's own produce_page.cjs (first-party).
// Generic pixel-coordinate primitives; page composition belongs in each plan.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const PptxGenJS = require('pptxgenjs');

const DEFAULT_FONT = 'Noto Sans CJK SC';
const color = value => String(value).replace(/^#/, '');
const SLIDE_WIDTH_IN = 13.333;
// Inches per source-image pixel; set once per job from the shared canvas width.
let IN_PX = 0;
const inch = px => px * IN_PX;
const pt = px => px * IN_PX * 72;
const box = ([x, y, w, h]) => ({ x: inch(x), y: inch(y), w: inch(w), h: inch(h) });
const line = (value = {}) => ({
  color: color(value.color || '000000'), width: pt(value.width ?? 1),
  transparency: value.color === 'none' ? 100 : 0,
  beginArrowType: value.arrowheads?.start, endArrowType: value.arrowheads?.end,
});
function textStyle(op) {
  return {
    fontSize: pt(op.size ?? 16), fontFace: op.font || DEFAULT_FONT,
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
        colW: op.col_widths.map(inch), rowH: op.row_heights.map(inch),
        border: { type: 'solid', color: color(op.line?.color || '000000'), pt: pt(op.line?.width ?? 1) },
      });
      break;
    }
    default: throw new Error(`不支持的原语：${op.op}`);
  }
}
async function main() {
  const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  if (!['single', 'deck'].includes(job.mode) || !job.pages.length || (job.mode === 'single' && job.pages.length !== 1)) {
    throw new Error('请选择单页或整套模式并传入对应页面');
  }
  const pptx = new PptxGenJS();
  const plans = job.pages.map(page => JSON.parse(fs.readFileSync(page.plan, 'utf8')));
  const canvas = plans[0].canvas_px;
  const mismatch = plans.findIndex(plan => plan.canvas_px.w !== canvas.w || plan.canvas_px.h !== canvas.h);
  if (mismatch >= 0) {
    throw new Error(`整套各页画布尺寸必须一致：第 1 页 ${canvas.w}×${canvas.h}，第 ${mismatch + 1} 页 ${plans[mismatch].canvas_px.w}×${plans[mismatch].canvas_px.h}`);
  }
  IN_PX = SLIDE_WIDTH_IN / canvas.w;
  pptx.defineLayout({ name: 'native', width: SLIDE_WIDTH_IN, height: SLIDE_WIDTH_IN * canvas.h / canvas.w });
  pptx.layout = 'native';
  pptx.lang = 'zh-CN';
  pptx.theme = { headFontFace: DEFAULT_FONT, bodyFontFace: DEFAULT_FONT, lang: 'zh-CN' };
  for (const [index, page] of job.pages.entries()) {
    const plan = plans[index];
    const slide = pptx.addSlide();
    slide.background = { color: color(plan.background) };
    plan.ops.forEach((op, i) => draw(pptx, slide, op, i, page, job.icons_dir));
    slide.addNotes(page.notes || '');
  }
  await pptx.writeFile({ fileName: job.output });
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
