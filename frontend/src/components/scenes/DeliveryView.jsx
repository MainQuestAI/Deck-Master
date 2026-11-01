import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
import { fileUrl } from '../../api.js';
import ArtifactStatus from '../common/ArtifactStatus';

const states = { open: '进行中', cancelled: '已停止', done: '已完成', pending: '等待执行', started: '结果未知', adopted: '已采用', unadopted: '未采用' };
const findingLabels = {
  notes_page_identity_mismatch: '讲稿对应的页面不一致', speaker_notes_mismatch: '讲稿内容不一致',
  slide_count_mismatch: '幻灯片数量不一致', missing_slide: '缺少幻灯片',
  unreadable_text: '文字不可读', svg_ppt_text_mismatch: 'SVG 与 PPTX 文字不一致',
  missing_visible_atom: '缺少正文文字', shape_outside_slide: '元素超出页面',
  missing_node: '缺少节点', missing_edge: '缺少连线',
  unverifiable_edge_geometry: '无法核对连线位置', reversed_arrow: '箭头方向相反', edge_not_connected: '连线未连接到节点',
  unverifiable_text_mapping: '无法核对文字对应关系', hidden_or_tiny_text: '文字隐藏或过小',
  unverifiable_table_ownership: '无法核对表格归属', table_cell_ownership_mismatch: '表格单元格归属不一致',
  node_atom_ownership_mismatch: '节点与正文归属不一致',
};
export default function DeliveryView() {
  const { workspace, stopRun, busy, build, buildResult, download, downloadStatus, openDrawer, getPage, getPageNumStr } = useDeckMaster();
  return <div>
    <div className="view-head"><div><h1>任务与交付</h1><p>停止进行中的任务，构建并下载当前作品。</p></div><button className="button" onClick={() => openDrawer('history')}>版本历史与恢复</button></div>
    <section className="s4-panel"><h2>构建与下载</h2><div className="head-actions s4-actions"><button className="primary" onClick={build} disabled={busy.build}>{busy.build ? '正在构建…' : '构建 PPTX'}</button><button className="button" onClick={() => download('md')} disabled={busy['export-md']}>下载 Markdown</button><button className="button" onClick={() => download('pptx')} disabled={busy['export-pptx']}>下载 PPTX</button></div>
      <ArtifactStatus status={workspace.artifact_status} />
      {downloadStatus && <><h3>最近构建或下载的状态</h3><ArtifactStatus status={downloadStatus} /></>}
      {buildResult && <details><summary>最近构建的回读发现（{buildResult.findings?.findings?.length ?? 0}）</summary><ul>{(buildResult.findings?.findings || []).map((finding, index) => <li key={index}>
        {finding.page_id ? (getPage(finding.page_id) ? `第 ${getPageNumStr(finding.page_id)} 页` : '已移除页面') : '整稿'} · {findingLabels[finding.code] || finding.code}{finding.text && `：${finding.text}`}{finding.element && `（${finding.element}）`}
      </li>)}</ul></details>}
    </section>
    <h2>制作任务</h2>
    {!workspace.runs.length && <p className="s4-empty">暂无制作任务。Host 开始制作后，进度将在这里显示。</p>}
    {workspace.runs.map(run => <section className="s4-panel" key={run.id}><div className="row between"><h3>{run.kind === 'image' ? '原图制作' : 'SVG 制作'} · {states[run.status] || run.status}</h3>{run.status === 'open' && <button className="button" disabled={busy[`cancel-${run.id}`]} onClick={() => stopRun(run.id)}>{busy[`cancel-${run.id}`] ? '正在停止…' : '停止任务'}</button>}</div>
      <ul>{run.pages.map(page => <li key={page.page_id}>{getPage(page.page_id) ? `第 ${getPageNumStr(page.page_id)} 页` : '已移除页面'} · {states[page.status] || page.status}{page.reason && ` · ${page.reason}`}{page.basis_changed && ' · 依据已变'}{page.result_file && <a className="button tiny quiet" href={fileUrl(page.result_file)} target="_blank" rel="noreferrer">查看结果</a>}</li>)}</ul>
    </section>)}
  </div>;
}
