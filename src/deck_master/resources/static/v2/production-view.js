import {el, version} from './dom.js';
const statuses = {pass: '记录为通过', fail: '记录为未通过', needs_review: '待判断', not_evaluated: '未评估', not_applicable: '不适用'};
const reviewers = {tool: '工具', host_self: '制作工具自评', independent_host: '独立工具', human_internal: '内部人员', human_external: '外部人员'};
export function productionView(data) {
  const value = data.production;
  if (!value) return el('p', {class: 'muted'}, '制作摘要未记录，请升级核心后读取。');
  const report = value.render_report, trace = value.object_trace;
  const facts = el('dl', {class: 'facts production-facts'});
  const row = (label, content) => facts.append(el('dt', {}, label), el('dd', {}, content));
  row('读取快照', version(value.revision_id));
  row('SVG 可编辑性记录', {unknown: '未知', not_applicable: '不适用', editable_shapes_and_text: '已记录形状与文本可编辑'}[value.svg.editability] || '未知');
  row('PPT 可编辑性', value.pptx.editability === 'editable_shapes_and_text' ? '已记录为形状与文本可编辑；未因此证明桌面实际编辑通过。' : value.pptx.editability === 'not_applicable' ? '不适用' : '未知');
  row('PPT 适用性', {current: '输入与此快照一致', basis_changed: '制作输入已变化，保留旧输出记录', unknown: '未知'}[value.pptx.applicability] || '未知');
  row('文本运行段', report.text_runs === null ? '未知' : `${report.text_runs}（text_runs；不是文本框数量）`);
  row('原生形状', report.native_shapes === null ? '未知' : `${report.native_shapes}（native_shapes；包含文本形状）`);
  row('SVG 输入图像元素（推导）', trace.svg_input_image_elements === null ? '未知' : `${trace.svg_input_image_elements}；由输入 SVG hash 匹配的 trace 推导`);
  row('PPT 光栅化比例', '未知，未计算'); row('OCR 文字层', '未记录；图片不能按文字选段');
  row('桌面字体替换', '未知；声明 fallback 不表示已成功替换');
  const node = el('details', {class: 'panel production-detail'}, el('summary', {}, '制作与可编辑性'), el('div', {class: 'panel-body stack'}, facts,
    el('p', {class: 'muted'}, '形状与文本编辑能力不等于 Office Edit Data、原生表格或浏览器直接修改 PPT。'),
    ['professional_use', 'desktop_editing'].map(kind => {
      const record = value.evaluations[kind];
      return el('p', {}, `${kind === 'professional_use' ? '专业使用评估' : '桌面实际编辑'}：${statuses[record.status] || '未知'}${record.reviewer_type ? ' · ' + (reviewers[record.reviewer_type] || '来源未知') : ''}`);
    }), value.unreadable_reviews && el('p', {class: 'field-error'}, '有评估记录无法读取；当前摘要不构成完整质量结论。'),
    el('details', {}, el('summary', {}, '声明字体与制作输入'),
      el('h3', {}, '快照中的声明字体'), value.declared_fonts.length ? el('ul', {}, value.declared_fonts.map(font => el('li', {}, `${font.family} · ${font.face} · 声明 fallback：${font.fallback_font_ids.join('、') || '无'}`))) : el('p', {}, '未记录'),
      el('h3', {}, '编译输入字体文件'), trace.compiler_fonts.length ? el('ul', {}, trace.compiler_fonts.map(font => el('li', {}, `${font.family_key} · SHA256 ${font.sha256}`))) : el('p', {}, '未记录'),
      el('p', {class: 'muted'}, '这些是声明和编译输入，不是 PowerPoint 桌面的字体替换结果。')),
    el('details', {}, el('summary', {}, '计数来源与发现'),
      el('p', {class: 'muted'}, `报告：${report.state}；与输出的关联：${report.pptx_relation === 'shared_inputs' ? '同快照共享输入，未直接记录 PPTX 父对象' : '未知'}。`),
      el('pre', {class: 'evidence-json'}, JSON.stringify({revision: value.revision_id, report_ref: report.ref, trace_ref: trace.ref, findings: report.findings, diagnostics: trace.diagnostics}, null, 2)))));
  return node;
}
