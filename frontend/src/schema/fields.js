// Single author field registry kept in sync with rust/src/model.rs.

export const BRIEF_FIELDS = {
  title: '作品名称',
  audience: '受众',
  task_type: '本次任务',
  goal: '要达成的结果',
  decision: '待决事项',
  concerns: '读者关注点',
  narrator: '讲述人与语气',
  constraints: '已知约束',
  page_limit: '页数要求',
};

export const NARRATOR_FIELDS = {
  role: '讲述人角色',
  tone: '讲述语气',
};

export const FRAMING_FIELDS = {
  thesis: '中心主张',
  storyline: '故事主线',
  pillars: '框架分组',
  facts: '已知事实',
  assumptions: '当前假设',
  questions: '待回答问题',
};

export const PAGE_FIELDS = {
  kind: '页型',
  purpose: '本页目的',
  layout: '版式要求',
  notes: '讲稿',
  todo: '待补',
  refs: '出处',
  argument: '论证结构',
};

export const PAGE_AUTHOR_FIELDS = {
  content: '页面正文',
  purpose: PAGE_FIELDS.purpose,
  layout: PAGE_FIELDS.layout,
  notes: PAGE_FIELDS.notes,
  todo: PAGE_FIELDS.todo,
  refs: PAGE_FIELDS.refs,
  kind: PAGE_FIELDS.kind,
  argument: PAGE_FIELDS.argument,
};

export const CONTENT_FIELDS = {
  title: '页面标题',
  subtitle: '副标题',
  body_blocks: '正文块',
  labels: '标签',
  callouts: '补充',
  footnotes: '脚注',
};

export const ARGUMENT_FIELDS = {
  reasons: '理由',
  evidence: '证据',
  reasoning: '推理',
  rebuttal: '反驳与边界',
};

export const EVIDENCE_FIELDS = {
  text: '证据内容',
  ref: '出处',
  gap: '证据缺口',
};

export const PAGE_KINDS = ['judgment', 'explanation', 'reference', 'teaching'];

export const PAGE_KIND_OPTIONS = [
  { value: '', label: '留空（未指定）' },
  { value: 'judgment', label: '判断页（judgment）' },
  { value: 'explanation', label: '说明页（explanation）' },
  { value: 'reference', label: '查阅页（reference）' },
  { value: 'teaching', label: '教学页（teaching）' },
];

export const PAGE_KIND_LABELS = {
  judgment: '判断页',
  explanation: '说明页',
  reference: '查阅页',
  teaching: '教学页',
};

export function emptyArgument() {
  return {
    reasons: [],
    evidence: [],
    reasoning: '',
    rebuttal: '',
  };
}

export function evidenceMode(item) {
  if (item && typeof item.gap === 'string' && !item.ref) return 'gap';
  if (item && Object.hasOwn(item, 'gap') && !Object.hasOwn(item, 'ref')) return 'gap';
  return 'ref';
}

export function buildEvidenceItem(text, mode, detail) {
  if (mode === 'gap') {
    return { text: text ?? '', gap: detail ?? '' };
  }
  return { text: text ?? '', ref: detail ?? '' };
}

export function missingContextHints(kind, value = {}) {
  const missing = [];
  if (kind === 'brief') {
    if (!value.audience?.trim()) missing.push('受众');
    if (!value.decision?.trim()) missing.push('待决事项');
    if (!(value.concerns || []).some(item => item?.trim())) missing.push('读者关注点');
    if (!value.narrator?.role?.trim()) missing.push('讲述人角色');
    if (!value.narrator?.tone?.trim()) missing.push('讲述语气');
  } else if (kind === 'framing') {
    if (!value.thesis?.trim()) missing.push('中心主张');
    if (!(value.storyline || []).some(item => item?.trim())) missing.push('故事主线');
  }
  return missing;
}

export function missingPageHints(page = {}) {
  const missing = [];
  if (!page.content?.title?.trim()) missing.push('页面标题');
  if (!page.purpose?.trim()) missing.push('本页目的');
  if (page.kind === 'judgment' && !page.argument) {
    missing.push('论证结构（判断页建议补充理由与证据）');
  }
  return missing;
}
