import React, { useState } from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';
import { formatFinding } from '../../api.js';
import PageArtwork from './PageArtwork';

const locatorLabels = [
  ['table_id', '表格'], ['row_id', '行'], ['column_id', '列'], ['element', 'SVG 元素'],
  ['atom_id', '文字对象'], ['node_id', '节点'], ['actual_node_id', '实际节点'],
  ['edge_id', '连线'], ['from', '起点'], ['to', '终点'],
  ['svg_elements', 'SVG 对象'], ['native_shape_ids', 'PPT 对象'],
  ['position', '位置（px）'], ['cell_bounds', '单元格区域（左、上、右、下，px）'],
  ['native_frame_perimeter', '表格边界（px）'],
  ['bounds', '对象边界（x、y、宽、高，EMU）'], ['slide', '页面尺寸（EMU）'],
];

function locationText(value) {
  return Array.isArray(value) ? value.map(locationText).join(', ') : String(value);
}

export default function PageComparison({ page }) {
  const { workspace, buildResult, buildError, getPageNumStr } = useDeckMaster();
  const [zoom, setZoom] = useState(100);
  const [horizontal, setHorizontal] = useState(50);
  const [vertical, setVertical] = useState(50);
  const canvas = workspace.deck.style?.canvas;
  const findings = (buildResult?.findings?.findings || []).filter(finding => finding.page_id === page.id);
  const hasPageReadback = buildResult?.readback_available !== false && buildResult?.pages?.some(item => item.page_id === page.id);
  const viewStyle = {
    aspectRatio: canvas ? `${canvas.width_px} / ${canvas.height_px}` : '16 / 9',
    '--compare-scale': zoom / 100,
    '--compare-left': `${-(zoom - 100) * horizontal / 100}%`,
    '--compare-top': `${-(zoom - 100) * vertical / 100}%`,
  };
  return <section className="page-comparison" aria-label="本页原图与编译预览对照">
    <p className="muted">两侧共用缩放和查看位置。放大后，调整横向、纵向位置查看同一区域。讲稿见正文层。</p>
    <div className="page-comparison-controls">
      <label>缩放 · {zoom}%<input type="range" aria-label="对照缩放" min="100" max="400" step="25" value={zoom} onChange={event => setZoom(Number(event.target.value))} /></label>
      <label>横向 · 左至右<input type="range" aria-label="横向查看位置" min="0" max="100" value={horizontal} disabled={zoom === 100} onChange={event => setHorizontal(Number(event.target.value))} /></label>
      <label>纵向 · 上至下<input type="range" aria-label="纵向查看位置" min="0" max="100" value={vertical} disabled={zoom === 100} onChange={event => setVertical(Number(event.target.value))} /></label>
      <button className="button" onClick={() => { setZoom(100); setHorizontal(50); setVertical(50); }}>查看整页</button>
    </div>
    <div className="page-comparison-panes">
      {[['original', '原图'], ['svg', '已采用的编译预览']].map(([layer, label]) => <section className="s4-panel" key={layer}>
        <h2>第 {getPageNumStr(page.id)} 页 · {label}</h2>
        <div className="page-comparison-viewport" style={viewStyle}><PageArtwork page={page} layer={layer} /></div>
      </section>)}
    </div>
    <section className="s4-panel page-comparison-readback">
      <h2>默认构建的本页回读发现{hasPageReadback && `（${findings.length}）`}</h2>
      {buildError && <p role="alert">回读结果不可读取：{buildError}</p>}
      {!buildResult ? <p className="muted">尚无可展示的构建回读；只有单页检查时，不代表已有整稿构建回读。</p> : <>
        <p className="muted">来源版本 {buildResult.version_id} · {buildResult.created_at} · {buildResult.readback_available === false ? '导入成品没有构建回读' : buildResult.readback_matches_current === true ? '检查输入仍匹配，未重新执行检查' : '历史检查不代表当前正文已检查'}。定位按构建时记录显示。</p>
        {!hasPageReadback ? <p className="muted">{buildResult.readback_available === false ? '该导入成品没有构建回读。' : '本页未参与该次构建，没有本页回读。'}</p> : findings.length ? <ul className="page-comparison-findings">{findings.map((finding, index) => <li key={index}>
          <p>构建时第 {buildResult.pages?.find(item => item.page_id === page.id)?.source_order ?? "未知"} 页 · {formatFinding(finding)}</p>
          <dl>{locatorLabels.filter(([key]) => finding[key] != null).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{locationText(finding[key])}</dd></div>)}</dl>
          {finding.native_carriers?.map((carrier, carrierIndex) => <dl key={carrierIndex}>
            {[
              ['native_shape_id', 'PPT 对象'], ['element', 'SVG 对象'],
              ['x', 'x（px）'], ['y', 'y（px）'], ['width', '宽（px）'], ['height', '高（px）'],
            ].filter(([key]) => carrier[key] != null).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{locationText(carrier[key])}</dd></div>)}
          </dl>)}
        </li>)}</ul> : <p className="muted">这次构建没有记录本页发现。</p>}
      </>}
    </section>
  </section>;
}
