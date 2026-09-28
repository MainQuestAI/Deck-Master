import {el, button, empty, version} from './dom.js';
import {imageView} from './images.js';
import {textObject} from './text-selection.js';
import {diffView} from './text-diff.js';

export const observerLabels = {
  core_frozen: '核心冻结 · 已保存要求，不代表已提交',
  host_reported: 'Host申报 · 制作工具报告，未独立核实',
  tool_observed: '工具观察 · 仅核实记录覆盖的字段',
  provider_receipt: '供应商回执 · 需可核验回执，当前没有此类记录',
  unknown: '未知 · 没有可核实的提交记录',
};
const details = (title, ...body) => el('details', {class: 'evidence-details'}, el('summary', {}, title), el('div', {class: 'stack'}, body));
const json = value => el('pre', {class: 'evidence-json'}, JSON.stringify(value, null, 2));
export function preparedRecords(data) {
  return [
    ...(data.generation?.requests || []).map((record, i) => ({ref: record.ref, text: record.input.prompt, label: `冻结请求 ${i + 1}`, request: record,
      source: data.text_sources?.prepared_prompt.find(s => s.ref.sha256 === record.ref.sha256), sections: null})),
    ...data.prompts.prepared.map((record, i) => ({...record, label: `预备稿 ${i + 1}`, source: data.text_sources?.prepared_prompt.find(s => s.ref.sha256 === record.ref.sha256)})),
  ];
}
function references(app, refs, label) {
  if (refs === null || refs === undefined) return el('p', {class: 'muted'}, label + '：未知，未从默认配置补入。');
  if (!refs.length) return el('p', {class: 'muted'}, label + '：记录为空。');
  return el('div', {class: 'reference-list'}, el('p', {}, label), refs.map((reference, i) => {
    const ref = reference.file || reference.ref || reference.artifact;
    const node = el('article', {class: 'reference-item'}, el('strong', {}, `参考 ${i + 1}`), el('p', {class: 'muted'}, reference.role || '角色未记录'));
    // Only explicitly recorded image file refs may be previewed. Metadata refs
    // are not guessed to be files, and current page slots are never substituted.
    if (ref?.path?.match(/\.(png|jpg|jpeg|webp)$/)) {
      const view = imageView(app, {existence: 'recorded', file: ref, media_type: 'image/' + ref.path.split('.').pop()}, `固定参考图 ${i + 1}`, {kind: 'thumb'});
      app.disposables.push(() => view.dispose()); node.append(view.node);
    }
    node.append(details('查看固定参考记录', json(reference))); return node;
  }));
}
export function generationBasis(app, data) {
  const generation = data.generation || {};
  const request = generation.requests?.find(r => r.ref.sha256 === generation.adopted_request_ref?.sha256);
  const attempt = generation.attempts?.find(a => a.ref.sha256 === generation.adopted_attempt_ref?.sha256);
  const observed = generation.adopted_observation;
  const actual = data.prompts.submitted;
  const node = el('details', {class: 'panel generation-basis', open: true}, el('summary', {}, '当次生成依据'),
    el('div', {class: 'panel-body stack'}, el('p', {class: 'muted'}, `依据版本：${version(data.revision_id)}`), el('p', {}, request ? '已绑定这张原图的冻结请求。' : '这张原图未记录可核对的绑定请求。'),
      el('p', {class: 'observer-label'}, observerLabels[actual.observer] || observerLabels.unknown),
      actual.text !== null ? button('查看实际提示词', () => app.go({layer: 'submitted_prompt', revision: data.revision_id, page_id: data.page_id})) : el('p', {class: 'muted'}, '这张图的实际提示词未记录。'),
      button('查看预备提示词', () => app.go({layer: 'prepared_prompt', revision: data.revision_id, page_id: data.page_id})),
      details('当次模型、参数与参考图',
        el('dl', {class: 'facts'}, el('dt', {}, '当次模型'), el('dd', {}, observed?.submitted?.model ?? '未知'),
          el('dt', {}, '当次随机种子'), el('dd', {}, observed?.submitted?.seed ?? '未知')),
        el('p', {class: 'muted'}, '以下只展示原图绑定观察记录覆盖的字段。冻结要求与项目默认值不代替当次实参。'),
        observed?.submitted?.parameters ? json(observed.submitted.parameters) : el('p', {}, '当次参数：未知'),
        references(app, observed?.submitted?.references, '当次参考图'),
        observed && details('字段覆盖范围', json(observed.coverage))),
      request && details('已冻结的要求', el('p', {class: 'muted'}, observerLabels.core_frozen), json(request.input.parameters), references(app, request.input.references, '请求参考图')),
      details('记录身份与证据含义', el('p', {class: 'muted'}, `固定 ${version(data.revision_id)}；内部记录可选取复制。`),
        json({request_id: request?.request_id ?? null, attempt_id: attempt?.attempt_id ?? null, request_ref: generation.adopted_request_ref ?? null, attempt_ref: generation.adopted_attempt_ref ?? null}),
        Object.entries(observerLabels).map(([key, meaning]) => el('p', {}, `${key}：${meaning}`))),
      generation.errors?.length > 0 && el('p', {class: 'field-error'}, '部分生成记录无法读取，未用其它记录补齐。')));
  return node;
}
export function promptView(app, data, layer, onBasis = () => {}) {
  const records = preparedRecords(data);
  const actual = data.prompts.submitted;
  const container = el('section', {class: 'prompt-workbench stack'});
  const body = el('div', {class: 'stack'}), diffSlot = el('div');
  const leases = []; const scoped = Object.create(app); scoped.disposables = leases;
  app.disposables.push(() => leases.splice(0).forEach(dispose => dispose()));
  const selectedRef = data.generation?.adopted_request_ref?.sha256;
  let selected = records.find(r => r.ref.sha256 === selectedRef) || (records.length === 1 || layer === 'submitted_prompt' ? records[0] : null);
  let selectedText = null;
  function render() {
    leases.splice(0).forEach(dispose => dispose());
    body.replaceChildren(); diffSlot.replaceChildren();
    const record = layer === 'submitted_prompt' ? {text: actual.text, ref: actual.ref, source: data.text_sources?.submitted_prompt[0]} : selected;
    selectedText = record?.text ?? null;
    onBasis(record?.ref || null, selectedText);
    body.append(el('p', {class: 'observer-label'}, layer === 'submitted_prompt' ? observerLabels[actual.observer] || observerLabels.unknown : observerLabels.core_frozen));
    if (selectedText === null) {
      body.append(empty(layer === 'submitted_prompt' ? '实际提示词未记录' : '尚无预备提示词', '未用另一份提示词替代。', button('查看逐页稿', () => app.go({layer: 'content', revision: data.revision_id, page_id: data.page_id})))); return;
    }
    body.append(record.source ? textObject(app, record.source, {pageId: data.page_id, revision: data.revision_id, layer, label: '提示词原文'}) : el('pre', {class: 'read-text'}, record.text));
    if (layer === 'prepared_prompt' && selected?.sections?.state === 'verified_core_projection') {
      body.append(details('可信结构段落', el('p', {class: 'muted'}, '以下段落来自已核对 hash 的核心结构化请求，范围仍指向上方完整原文。'),
        selected.sections.segments.map(segment => el('section', {}, el('h3', {}, segment.label === 'instructions' ? '制作说明' : '结构化输入'),
          el('pre', {class: 'read-text'}, Array.from(selected.text).slice(segment.start, segment.end).join(''))))));
    } else body.append(el('p', {class: 'muted'}, '没有可靠的结构段落记录，保留全文与原文选段。'));
    if (layer === 'prepared_prompt' && selected?.request) body.append(details('冻结参数与参考图',
      el('p', {class: 'muted'}, '仅表示请求要求，不表示当次实际使用。'), json(selected.request.input.parameters), references(scoped, selected.request.input.references, '请求参考图')));
  }
  if (layer === 'prepared_prompt' && records.length > 1) {
    const select = el('select', {'aria-label': '选择草稿绑定的预备提示词'}, el('option', {value: ''}, '先选择具体预备稿'), records.map(record => el('option', {value: record.ref.sha256}, `${record.label} · ${record.ref.sha256.slice(0, 8)}`)));
    select.value = selected?.ref.sha256 || '';
    select.addEventListener('change', () => { selected = records.find(r => r.ref.sha256 === select.value); render(); });
    container.append(el('label', {}, '固定预备记录 ', select));
  }
  container.append(el('h2', {}, layer === 'submitted_prompt' ? '这张原图的实际提示词' : '预备提示词'), body);
  const compare = button('比较预备与实际文本', () => {
    if (!selected || actual.text === null) { diffSlot.replaceChildren(el('p', {class: 'muted'}, '缺少一侧记录，保留已有原文，暂不能计算差异。')); return; }
    diffSlot.replaceChildren(diffView(selected.text, actual.text, selected.label + '（冻结）', '实际文本（' + (actual.observer === 'tool_observed' ? '工具观察' : 'Host申报') + '）'));
  });
  // The selection for the left side is always explicit, including while reading actual.
  if (layer === 'submitted_prompt' && records.length) {
    const select = el('select', {'aria-label': '选择差异比较的预备提示词'}, records.map(record => el('option', {value: record.ref.sha256}, record.label + ' · ' + record.ref.sha256.slice(0, 8))));
    select.value = selected.ref.sha256; select.addEventListener('change', () => { selected = records.find(r => r.ref.sha256 === select.value); diffSlot.replaceChildren(); });
    container.append(el('label', {}, '差异比较左侧 ', select));
  }
  container.append(compare, diffSlot, details('证据来源说明', Object.entries(observerLabels).map(([key, value]) => el('p', {}, `${key}：${value}`))));
  render(); return container;
}
