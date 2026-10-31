import React from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';
import { chapters } from '../../constants/data';

export default function GalleryView() {
  const {
    galleryView,
    setGalleryView,
    galleryLayer,
    setGalleryLayer,
    galleryFilter,
    setGalleryFilter,
    order,
    openPage,
    openDrawer,
    startPresentation,
    getPageNumStr,
    getPage
  } = useDeckMaster();

  const currentPages = order.map(getPage).filter((p) => {
    if (!p) return false;
    if (galleryFilter === 'original') return p.original;
    if (galleryFilter === 'svg') return p.svg;
    if (galleryFilter === 'pending') return p.candidate;
    return true;
  });

  return (
    <div>
      {/* S03 Streamlined Unified Toolbar */}
      <div
        className="gallery-toolbar row between"
        style={{ marginBottom: '24px', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}
      >
        <div className="row" style={{ gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Segmented Control */}
          <div className="segmented-control" role="group" aria-label="画廊视图模式">
            <button
              className={galleryView === 'grid' ? 'active' : ''}
              onClick={() => setGalleryView('grid')}
            >
              <Icon name="grid" />网格缩略画板
            </button>
            <button
              className={galleryView === 'continuous' ? 'active' : ''}
              onClick={() => setGalleryView('continuous')}
            >
              <Icon name="read" />长卷阅读模式
            </button>
          </div>

          <div className="tool-sep"></div>

          <div className="row" style={{ gap: '6px', fontSize: '12px' }}>
            <span className="muted">展示产物层：</span>
            <select
              className="select-filter"
              id="gallery-layer-select"
              value={galleryLayer}
              onChange={(e) => setGalleryLayer(e.target.value)}
              style={{ minHeight: '28px', padding: '2px 24px 2px 10px', fontSize: '12px' }}
            >
              <option value="original">原图 (12 已生成)</option>
              <option value="svg">SVG 矢量 (8 已生成)</option>
              <option value="text">逐页稿排版预览 (30)</option>
            </select>
          </div>

          <div className="row" style={{ gap: '6px', fontSize: '12px' }}>
            <span className="muted">筛选：</span>
            <select
              className="select-filter"
              id="gallery-filter-select"
              value={galleryFilter}
              onChange={(e) => setGalleryFilter(e.target.value)}
              style={{ minHeight: '28px', padding: '2px 24px 2px 10px', fontSize: '12px' }}
            >
              <option value="all">全量 30 页</option>
              <option value="original">仅显示有原图 (12 页)</option>
              <option value="svg">仅显示有 SVG (8 页)</option>
              <option value="pending">仅显示候选待决 (3 页)</option>
            </select>
          </div>
        </div>

        <div className="row" style={{ gap: '8px', alignItems: 'center' }}>
          <span className="badge neutral" style={{ fontSize: '11px' }}>30 页 · 5 章节</span>
          <button
            className="button primary"
            onClick={() => startPresentation(1)}
            title="开启全屏放映预览 (快捷键 P)"
          >
            <Icon name="play" />全屏放映预览
            <kbd
              className="dm-kbd"
              style={{
                marginLeft: '4px',
                background: 'rgba(255,255,255,0.2)',
                borderColor: 'rgba(255,255,255,0.3)',
                color: '#fff'
              }}
            >
              P
            </kbd>
          </button>
          <button
            className="button quiet"
            onClick={() => openDrawer('style-preview')}
            title="查看当前整稿风格基准"
          >
            <Icon name="style" />风格基准
          </button>
        </div>
      </div>

      {/* Mode 1: Grid Mode */}
      {galleryView === 'grid' ? (
        <div className="gallery-grid">
          {currentPages.map((p) => (
            <article
              key={p.id}
              className="slide-card"
              onClick={() => openPage(p.id)}
              tabIndex={0}
              aria-label={`第 ${getPageNumStr(p.id)} 页 ${p.title}`}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  openPage(p.id);
                }
              }}
            >
              <button
                className="button tiny quiet slide-quick-play"
                onClick={(e) => {
                  e.stopPropagation();
                  startPresentation(p.id);
                }}
                title={`从第 ${getPageNumStr(p.id)} 页开始放映`}
              >
                <Icon name="play" />放映
              </button>
              <div className="slide-canvas">
                <div className="canvas-head">
                  <span>第 {getPageNumStr(p.id)} 页 / 30</span>
                  <span>{chapters[p.chapter]}</span>
                </div>
                <div>
                  <h3>{p.title}</h3>
                  <p>{p.goal.slice(0, 36)}...</p>
                </div>
                <div className="canvas-cols">
                  <div>业务目标</div>
                  <div>依据核对</div>
                  <div>结果采用</div>
                </div>
              </div>
              <div className="card-foot">
                <span className="num">
                  {getPageNumStr(p.id)} · {p.review ? '待确认' : '已确认'}
                </span>
                {p.candidate ? (
                  <span className="badge warn pulse">候选待比对</span>
                ) : p.original ? (
                  <span className="badge ok">原图已就绪</span>
                ) : (
                  <span className="badge neutral">草稿</span>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : (
        /* Mode 2: Continuous Reading Stream */
        <div className="continuous-stream">
          {currentPages.map((p) => (
            <article key={p.id} className="continuous-item">
              <div className="row between" style={{ marginBottom: '10px' }}>
                <span className="badge neutral">
                  第 {getPageNumStr(p.id)} 页 · {chapters[p.chapter]}
                </span>
                <button className="button tiny quiet" onClick={() => openPage(p.id)}>
                  <Icon name="edit" />单页处理
                </button>
              </div>
              <h3>{p.title}</h3>
              <p style={{ whiteSpace: 'pre-line' }}>{p.body}</p>
              <div className="row between" style={{ fontSize: '12px', color: 'var(--dm-color-text-muted)' }}>
                <span>目标：{p.goal}</span>
                <button
                  className="button tiny quiet"
                  onClick={() => openDrawer('source', { id: p.id })}
                >
                  <Icon name="link" />来源核对
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
