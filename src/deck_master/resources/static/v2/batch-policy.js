// Action eligibility is separate from the overview's attention filter.
export const batchNames = {blueprint: '原图试作', reconstruct: 'SVG 重建', repair: 'SVG 修复', style: '风格校准'};

export function batchExclusion(app, page, action, reference = null) {
  if (!page) return '所选页面不在这个版本中';
  if (app.readonly || app.info.sample?.readonly) return '历史版本或只读示例不能提交制作';
  if (app.latest?.revision_id && app.latest.revision_id !== app.route.revision) return '项目已有新版本，先明确重新选择制作范围';
  if (!app.business || !app.health.ui_capabilities?.includes('ui_draft.v1')) return '当前核心未提供可恢复的业务提交';
  const family = action === 'style' ? 'styles' : 'changes';
  const availability = app.info.effective_actions?.find(item => item.action === family);
  if (!availability?.supported || !availability.writable) return '当前核心或项目格式不支持这个动作';
  if (app.business?.entries.size || app.business?.loadWarning || app.business?.preparing) return '先核实上一次业务保存';
  const currentPage = app.latest?.pages?.find(item => item.page_id === page.page_id) || page;
  if (app.summary.unreadable_tasks || app.latest?.unreadable_tasks || currentPage.attention?.items?.some(item => item.kind === 'verify_execution'))
    return '制作记录或调用待核实，未安排新的试作';
  if (page.stages.content?.existence !== 'recorded' || !page.stages.content.ref) return '逐页稿暂不可读';
  if (action === 'style' && page.page_id === reference?.page_id) return '参考页同时在目标中，请明确取消这页目标';
  if (action === 'reconstruct' || action === 'repair') {
    if (page.stages.blueprint?.existence !== 'recorded' || !page.stages.blueprint.file) return '需要可读的原图';
    if (page.stages.blueprint.applicability?.status !== 'current') return '原图依据已变化或尚未核实';
    if (action === 'repair' && (page.stages.svg?.existence !== 'recorded' || !page.stages.svg.ref)) return '没有可修复的 SVG，请先选择重建';
    if (action === 'repair' && page.stages.svg.applicability?.status !== 'current') return 'SVG 依据已变化或尚未核实，请先选择重建';
  }
  return null;
}

export function batchInput(summary, pageIds, action, instruction, maxCalls, reference) {
  if (!['blueprint', 'reconstruct', 'repair'].includes(action)) throw new Error('请选择明确的试作动作。');
  const pages = pageIds.map(id => summary.pages.find(page => page.page_id === id));
  if (!pages.length || pages.some(page => !page)) throw new Error('所选页面范围已变化，请重新选择。');
  const image = action === 'blueprint', slot = image ? 'blueprint' : 'svg';
  return {schema_version: 'change_intent.v1', project_id: summary.project_id, base_revision: summary.revision_id,
    mode: 'trial', intent: image ? 'reference_correction' : 'svg_repair', instruction, annotation_refs: [],
    max_calls: image ? maxCalls : 0,
    targets: pages.map(page => ({page_id: page.page_id, page_ref: page.stages.content.ref,
      layer: image ? 'original_image' : 'svg', stage: action, artifact_ref: page.stages[slot].ref || null})),
    references: image && reference ? [{page_id: reference.page_id, revision_id: reference.revision_id, artifact_ref: reference.artifact_ref, role: 'reference'}] : []};
}
