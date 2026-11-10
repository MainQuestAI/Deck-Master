import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
import { fileUrl, formatFinding } from '../../api.js';
import ArtifactStatus from '../common/ArtifactStatus';

const states = { open: '进行中', cancelled: '已停止', done: '已完成', pending: '等待执行', started: '结果未知', adopted: '已采用', unadopted: '未采用' };
export default function DeliveryView() {
  const { workspace, stopRun, busy, build, buildResult, buildLoading, buildError, defaultBuild, download, downloadStatus, openDrawer, getPage, getPageNumStr, compareCandidate } = useDeckMaster();
  const runs = workspace.runs.filter(run => run.kind !== 'native');
  return <div>
    <div className="view-head"><div><h1>任务与交付</h1><p>停止进行中的任务，构建并下载当前作品。</p></div><button className="button" onClick={() => openDrawer('history')}>版本历史与恢复</button></div>
    <section className="s4-panel"><h2>构建与下载</h2><div className="head-actions s4-actions"><button className="primary" onClick={build} disabled={busy.build}>{busy.build ? '正在构建…' : '构建 PPTX'}</button><button className="button" onClick={() => download('md')} disabled={busy['export-md']}>下载 Markdown</button><button className="button" onClick={() => download('pptx')} disabled={busy['export-pptx']}>下载 PPTX</button></div>
      <ArtifactStatus status={workspace.artifact_status} />
      {defaultBuild && <><p>默认构建 #{defaultBuild.id} · 来源版本 {defaultBuild.version_id}</p><ArtifactStatus status={defaultBuild} /></>}
      {buildError && <p role="alert">回读结果不可读取：{buildError}</p>}
      {buildLoading && <p role="status">{buildResult ? `正在刷新构建回读；暂留构建 #${buildResult.id}（来源版本 ${buildResult.version_id}）的历史结果。` : '正在读取构建回读…'}</p>}
      {buildResult && <p>来源版本 {buildResult.version_id} · {buildResult.created_at} · {buildResult.readback_available === false ? '导入成品没有构建回读' : buildResult.readback_matches_current === true ? '该次检查输入仍匹配；未重新执行检查' : '历史检查，不代表当前正文已检查'}</p>}
      {downloadStatus && <><h3>最近构建或下载的状态</h3><ArtifactStatus status={downloadStatus} /></>}
      {buildResult && buildResult.readback_available !== false && <details><summary>{buildLoading ? `上次读取构建 #${buildResult.id} 的回读发现` : '默认构建的回读发现'}（{buildResult.findings?.findings?.length ?? 0}）</summary><ul>{(buildResult.findings?.findings || []).map((finding, index) => <li key={index}>
        {finding.page_id ? (buildResult.pages?.find(page => page.page_id === finding.page_id) ? `构建时第 ${buildResult.pages.find(page => page.page_id === finding.page_id).source_order} 页` : '历史页面') : '整稿'} · {formatFinding(finding)}
      </li>)}</ul></details>}
    </section>
    <h2>制作任务</h2>
    {!runs.length && <p className="s4-empty">暂无制作任务。Host 开始制作后，进度将在这里显示。</p>}
    {runs.map(run => <section className="s4-panel" key={run.id}><div className="row between"><h3>{run.kind === 'image' ? '原图制作' : 'SVG 制作'} · {states[run.status] || run.status}</h3>{run.status === 'open' && <button className="button" disabled={busy[`cancel-${run.id}`]} onClick={() => stopRun(run.id)}>{busy[`cancel-${run.id}`] ? '正在停止…' : '停止任务'}</button>}</div>
      <ul>{run.pages.map(page => <li key={page.page_id}>{getPage(page.page_id) ? `第 ${getPageNumStr(page.page_id)} 页` : '已移除页面'} · {states[page.status] || page.status}{page.reason && ` · ${page.reason}`}{page.basis_changed && ' · 依据已变'}{page.basis_incomplete && ' · 旧依据未记录目的和布局'}{page.result_file && <>{getPage(page.page_id) && <button className="button tiny" onClick={() => compareCandidate(run, page)}>比对与采用</button>}<a className="button tiny quiet" href={fileUrl(page.result_file)} target="_blank" rel="noreferrer">查看结果</a></>}</li>)}</ul>
    </section>)}
  </div>;
}
