import React from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function OverviewView() {
  const {
    pages,
    order,
    query,
    setQuery,
    filter,
    setFilter,
    openPage,
    openCompare,
    openDrawer,
    getPageNumStr,
    getPage
  } = useDeckMaster();

  const filteredPages = order.map(getPage).filter((p) => {
    if (!p) return false;
    const matchQuery = !query || p.title.includes(query);
    if (!matchQuery) return false;
    if (filter === 'candidate') return p.candidate;
    if (filter === 'review') return p.review;
    if (filter === 'svg-ready') return p.original && !p.svg;
    return true;
  });

  return (
    <div>
      <div className="view-head">
        <div>
          <h1>制作总览</h1>
          <p>当前商业表达方案的全链路生产进度、关键待办与下一推荐动作。</p>
        </div>
        <div className="head-actions">
          <button className="button" onClick={() => openDrawer('history')}>
            <Icon name="layers" />
            版本历史记录
          </button>
          <button className="button" onClick={() => openDrawer('todos')}>
            <Icon name="check" />
            查看全部事项
          </button>
        </div>
      </div>

      {/* Metric Summary Strip */}
      <div className="metric-summary">
        <div className="metric-item">
          <strong>30<small>/ 30</small></strong>
          <p>逐页稿：24 已确认 · 6 待确认</p>
        </div>
        <div className="metric-item">
          <strong>12<small>/ 30</small></strong>
          <p>原图：12 已采用 · 3 候选待比对</p>
        </div>
        <div className="metric-item">
          <strong>8<small>/ 30</small></strong>
          <p>SVG 矢量：8 已采用 · 4 页可转换</p>
        </div>
        <div className="metric-item">
          <strong>0<small>/ 30</small></strong>
          <p>PPT 幻灯：等待上游产物就绪</p>
        </div>
      </div>

      {/* Primary Next Action Banner */}
      <section className="next-banner" aria-label="首要任务">
        <div className="mark-icon">
          <Icon name="layers" className="ico-lg" />
        </div>
        <div className="grow">
          <h2>3 页原图候选已返回，等待比对与采用决定</h2>
          <p>第 13–15 页 · 基于 R 08 基准生成；比对差异后决定采用并升级版本，或保留当前稿。</p>
        </div>
        <button className="primary" onClick={() => openCompare(13)}>
          <Icon name="arrow" />立即比对第 13 页候选
        </button>
      </section>

      {/* Secondary Fast Action Badges */}
      <div className="secondary-actions">
        <button className="button tiny" onClick={() => setFilter('review')}>
          <Icon name="alert" />6 页内容待确认
        </button>
        <button className="button tiny" onClick={() => setFilter('svg-ready')}>
          <Icon name="file" />4 页可继续转换 SVG
        </button>
        <button className="button tiny" onClick={() => openPage(16)}>
          <Icon name="read" />继续上次阅读 (第 16 页)
        </button>
        <button
          className="button tiny quiet"
          style={{ marginLeft: 'auto' }}
          onClick={() => openDrawer('todos')}
        >
          <Icon name="more" />全部 4 项待办
        </button>
      </div>

      {/* Table Toolbar */}
      <div className="toolbar">
        <div className="row">
          <label className="search-box">
            <Icon name="search" />
            <input
              id="matrix-search"
              type="text"
              placeholder="搜索页名或关键词 (或按 ⌘K)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="搜索页面"
            />
          </label>
          <select
            className="select-filter"
            id="matrix-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            aria-label="筛选页面状态"
          >
            <option value="all">全部状态 ({pages.length})</option>
            <option value="candidate">候选待比较 (3)</option>
            <option value="review">内容待确认 (6)</option>
            <option value="svg-ready">可转换 SVG (4)</option>
          </select>
        </div>
        <span className="muted" style={{ fontSize: '12px' }}>
          共 {filteredPages.length} 页 · 点击页名直接进入单页制作
        </span>
      </div>

      {/* Progress Matrix Table */}
      <div className="matrix-container">
        <table className="matrix-table" aria-label="逐页制作进度矩阵">
          <thead>
            <tr>
              <th>页面与章节</th>
              <th>逐页稿</th>
              <th>原图产物</th>
              <th>SVG 矢量</th>
              <th>PPT 导出</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {filteredPages.map((p) => (
              <tr key={p.id}>
                <td>
                  <button className="page-entry-link" onClick={() => openPage(p.id)}>
                    <span className="p-no num">{getPageNumStr(p.id)}</span>
                    <Icon name="page" />
                    <span style={{ fontWeight: 520 }}>{p.title}</span>
                  </button>
                </td>
                <td>
                  {p.review ? (
                    <span className="badge warn">待确认</span>
                  ) : (
                    <span className="badge ok">已确认</span>
                  )}
                </td>
                <td>
                  {p.candidate ? (
                    <span className="badge warn pulse">候选待比对</span>
                  ) : p.original ? (
                    <span className="badge ok">已采用</span>
                  ) : (
                    <span className="muted">— 未制作</span>
                  )}
                </td>
                <td>
                  {p.svg ? (
                    <span className="badge ok">已采用</span>
                  ) : p.original ? (
                    <span className="badge neutral">就绪可转</span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td>
                  <span className="muted" title="等待前置流水完成">
                    — 等待前置
                  </span>
                </td>
                <td>
                  {p.candidate ? (
                    <button className="button tiny primary" onClick={() => openCompare(p.id)}>
                      <Icon name="compare" />比对
                    </button>
                  ) : (
                    <button className="button tiny quiet" onClick={() => openPage(p.id)}>
                      <Icon name="arrow" />打开
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
