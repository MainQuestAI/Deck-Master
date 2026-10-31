import React from 'react';
import Icon from '../common/Icon';
import CanvasGuides from '../canvas/CanvasGuides';
import { useDeckMaster } from '../../context/DeckMasterContext';
import { chapters } from '../../constants/data';

export default function PresentationModal() {
  const {
    presentation,
    exitPresentation,
    presNext,
    presPrev,
    togglePresThumbnails,
    togglePresAutoPlay,
    toggleNativeFullscreen,
    setPresentation,
    order,
    getPage,
    getPageNumStr,
    activeProject,
    revision,
    canvasGuides,
    toggleGuide,
    openPage,
    openDrawer
  } = useDeckMaster();

  if (!presentation.open) return null;

  const page = getPage(presentation.pageId) || getPage(16);
  const currIdx = order.indexOf(page.id);

  const renderSlideContent = () => {
    if (presentation.layer === 'svg') {
      return (
        <>
          <div className="pres-canvas-head">
            <div className="row" style={{ gap: '8px' }}>
              <span className="badge neutral" style={{ fontSize: '11px' }}>SVG 矢量拓扑层</span>
              <strong style={{ color: 'var(--dm-color-text)' }}>{chapters[page.chapter]}</strong>
            </div>
            <div className="row" style={{ gap: '8px' }}>
              <span className="badge ok pulse">SVG 矢量图已生成</span>
              <span className="num muted">第 {getPageNumStr(page.id)} 页 / 30</span>
            </div>
          </div>
          <div className="pres-canvas-body">
            <h2>{page.title}</h2>
            <p className="pres-lead">{page.goal}</p>

            <div
              style={{
                marginTop: '24px',
                padding: '18px 20px',
                background: '#0f172a',
                borderRadius: '8px',
                color: '#f8fafc',
                border: '1px solid #334155'
              }}
            >
              <div
                className="row between"
                style={{ marginBottom: '12px', fontSize: '12px', color: '#94a3b8' }}
              >
                <span className="row" style={{ gap: '6px' }}>
                  <Icon name="layers" /> 矢量架构拓扑映射 (Vector Precision Graph)
                </span>
                <span
                  className="badge neutral"
                  style={{ fontSize: '10px', background: '#1e293b', color: '#38bdf8' }}
                >
                  1920×1080 矢量等比缩放
                </span>
              </div>
              <svg viewBox="0 0 800 120" style={{ width: '100%', height: 'auto', maxHeight: '120px' }}>
                <defs>
                  <linearGradient id="svgLineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#38bdf8" />
                    <stop offset="100%" stopColor="#818cf8" />
                  </linearGradient>
                </defs>
                <rect x="20" y="25" width="200" height="70" rx="6" fill="#1e293b" stroke="#38bdf8" strokeWidth="1.5" />
                <text x="120" y="55" fill="#ffffff" fontSize="13" fontWeight="600" textAnchor="middle">
                  业务需求结构化输入
                </text>
                <text x="120" y="75" fill="#94a3b8" fontSize="10" textAnchor="middle">
                  访谈事实 · 目标约束
                </text>

                <path d="M220 60 L300 60" stroke="url(#svgLineGrad)" strokeWidth="2" strokeDasharray="4 2" />
                <polygon points="300 60 292 56 292 64" fill="#38bdf8" />

                <rect x="300" y="25" width="200" height="70" rx="6" fill="#1e293b" stroke="#818cf8" strokeWidth="1.5" />
                <text x="400" y="55" fill="#ffffff" fontSize="13" fontWeight="600" textAnchor="middle">
                  智能排版与版式对齐
                </text>
                <text x="400" y="75" fill="#94a3b8" fontSize="10" textAnchor="middle">
                  16:9 画布 · 4px 网格
                </text>

                <path d="M500 60 L580 60" stroke="url(#svgLineGrad)" strokeWidth="2" strokeDasharray="4 2" />
                <polygon points="580 60 572 56 572 64" fill="#818cf8" />

                <rect x="580" y="25" width="200" height="70" rx="6" fill="#1e293b" stroke="#34d399" strokeWidth="1.5" />
                <text x="680" y="55" fill="#ffffff" fontSize="13" fontWeight="600" textAnchor="middle">
                  高价值数字资产入库
                </text>
                <text x="680" y="75" fill="#94a3b8" fontSize="10" textAnchor="middle">
                  版本可溯 · 复用沉淀
                </text>
              </svg>
            </div>
          </div>
          <div className="pres-canvas-foot">
            <span>企业内容运营方案 · SVG 矢量拓扑输出</span>
            <span>矢量精确坐标 · 纯路径渲染</span>
          </div>
        </>
      );
    }

    if (presentation.layer === 'text') {
      return (
        <>
          <div className="pres-canvas-head">
            <div className="row" style={{ gap: '8px' }}>
              <span className="badge neutral" style={{ fontSize: '11px' }}>逐页稿排版层</span>
              <strong style={{ color: 'var(--dm-color-text)' }}>{chapters[page.chapter]}</strong>
            </div>
            <div className="row" style={{ gap: '8px' }}>
              <span className="badge ok">逐页稿已确认</span>
              <span className="num muted">第 {getPageNumStr(page.id)} 页 / 30</span>
            </div>
          </div>
          <div className="pres-canvas-body">
            <h2>{page.title}</h2>
            <p className="pres-lead" style={{ marginBottom: '24px' }}>{page.goal}</p>

            <div
              style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                padding: '20px 24px'
              }}
            >
              <strong style={{ display: 'block', fontSize: '13px', color: '#090d16', marginBottom: '8px' }}>
                讲述与陈述要点
              </strong>
              <p style={{ fontSize: '14px', lineHeight: 1.8, color: '#334155', whiteSpace: 'pre-line' }}>
                {page.body}
              </p>
            </div>
          </div>
          <div className="pres-canvas-foot">
            <span>企业内容运营方案 · 逐页稿正文排印</span>
            <span>3-Weight 瑞士字体阶梯 · CJK 行高 1.35</span>
          </div>
        </>
      );
    }

    // Default: original
    return (
      <>
        <div className="pres-canvas-head">
          <div className="row" style={{ gap: '8px' }}>
            <span className="badge neutral" style={{ fontSize: '11px' }}>
              章节 {page.chapter + 1} / 5
            </span>
            <strong style={{ color: 'var(--dm-color-text)' }}>{chapters[page.chapter]}</strong>
          </div>
          <div className="row" style={{ gap: '8px' }}>
            <span className="badge ok pulse">原图画板已渲染</span>
            <span className="num muted">第 {getPageNumStr(page.id)} 页 / 30</span>
          </div>
        </div>
        <div className="pres-canvas-body">
          <h2>{page.title}</h2>
          <p className="pres-lead">{page.goal}</p>
          <div className="pres-canvas-cols">
            <div className="pres-col-card">
              <strong>01 业务目标对齐</strong>
              <p>以具体的业务收益为起点，阐述本阶段所促成的共识，拒绝空洞概念。</p>
            </div>
            <div className="pres-col-card">
              <strong>02 来源事实沉淀</strong>
              <p>关联真实访谈与盘点材料，确保每一条关键结论均有可追溯的证据支撑。</p>
            </div>
            <div className="pres-col-card">
              <strong>03 生产协同闭环</strong>
              <p>明确页面焦点与呈现关系，将制作产物结构化沉淀至企业内容资产中。</p>
            </div>
          </div>
        </div>
        <div className="pres-canvas-foot">
          <span>企业内容运营方案 · Deck Master Pro 放映模式</span>
          <span>基准版本：R 0{revision} · 经审核通过</span>
        </div>
      </>
    );
  };

  return (
    <div
      className={`presentation-stage ${presentation.showThumbnails ? 'with-thumbnails' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-label="幻灯片全屏放映预览"
    >
      {/* Top Floating Info Bar */}
      <div className="pres-topbar">
        <div className="row" style={{ gap: '12px' }}>
          <div className="pres-badge">
            <Icon
              name="logo"
              className="logo-svg ico-fill"
              style={{ width: '18px', height: '18px', flex: 'none' }}
            />
            <span>Deck Master 放映厅</span>
          </div>
          <span className="pres-crumb">{activeProject} · 基准 R 0{revision}</span>
          <span className="pres-page-title">
            第 {getPageNumStr(page.id)} 页 · {page.title}
          </span>
        </div>

        <div className="row" style={{ gap: '8px' }}>
          {/* Guides Switch */}
          <div
            className="row"
            style={{
              gap: '4px',
              background: 'rgba(255,255,255,0.06)',
              padding: '2px 6px',
              borderRadius: '6px'
            }}
          >
            <span className="muted" style={{ fontSize: '11px' }}>参考线：</span>
            <button
              className={`button tiny ${canvasGuides.safeArea ? 'active-guide' : 'quiet'}`}
              onClick={() => toggleGuide('safeArea')}
              title="开关 80% 核心安全区"
            >
              <Icon name="check" />80% 安全区
            </button>
            <button
              className={`button tiny ${canvasGuides.thirds ? 'active-guide' : 'quiet'}`}
              onClick={() => toggleGuide('thirds')}
              title="开关三分网格"
            >
              <Icon name="grid" />三分网格
            </button>
          </div>

          {/* Layer Switcher */}
          <div
            className="row"
            style={{
              gap: '4px',
              background: 'rgba(255,255,255,0.06)',
              padding: '2px 6px',
              borderRadius: '6px'
            }}
          >
            <button
              className={`button tiny ${presentation.layer === 'original' ? 'primary' : 'quiet'}`}
              onClick={() => setPresentation((prev) => ({ ...prev, layer: 'original' }))}
            >
              <Icon name="gallery" />原图
            </button>
            <button
              className={`button tiny ${presentation.layer === 'svg' ? 'primary' : 'quiet'}`}
              onClick={() => setPresentation((prev) => ({ ...prev, layer: 'svg' }))}
            >
              <Icon name="layers" />SVG
            </button>
            <button
              className={`button tiny ${presentation.layer === 'text' ? 'primary' : 'quiet'}`}
              onClick={() => setPresentation((prev) => ({ ...prev, layer: 'text' }))}
            >
              <Icon name="content" />逐页稿
            </button>
          </div>

          {/* Autoplay Toggle */}
          <button
            className={`button tiny ${presentation.autoPlay ? 'active-guide' : 'quiet'}`}
            onClick={togglePresAutoPlay}
            title="自动切页播放 (每4.5秒)"
          >
            <Icon name={presentation.autoPlay ? 'pause' : 'play'} />
            {presentation.autoPlay ? '停止轮播' : '自动放映'}
          </button>

          {/* Native Fullscreen */}
          <button
            className="button tiny quiet"
            onClick={toggleNativeFullscreen}
            title="进入或退出浏览器全屏"
          >
            <Icon name="fullscreen" />全屏
          </button>

          {/* Exit Presentation */}
          <button
            className="button tiny quiet"
            onClick={exitPresentation}
            title="退出放映模式 (Esc)"
            style={{ border: '1px solid rgba(255,255,255,0.2)' }}
          >
            <Icon name="close" />退出放映
          </button>
        </div>
      </div>

      {/* Main Stage Viewport */}
      <div className="pres-canvas-wrapper">
        <div className="slide-canvas pres-canvas" style={{ aspectRatio: '16 / 9', position: 'relative' }}>
          <CanvasGuides />
          {renderSlideContent()}
        </div>
      </div>

      {/* Thumbnail Strip Tray */}
      {presentation.showThumbnails && (
        <div className="pres-thumb-tray">
          <div className="pres-thumb-scroll" id="pres-thumb-scroll">
            {order.map((id) => {
              const sp = getPage(id);
              const isActive = id === page.id;
              return (
                <div
                  key={id}
                  className={`pres-thumb-item ${isActive ? 'active' : ''}`}
                  onClick={() => setPresentation((prev) => ({ ...prev, pageId: id }))}
                  title={`第 ${getPageNumStr(id)} 页 · ${sp.title}`}
                >
                  <span className="pres-thumb-num">第 {getPageNumStr(id)} 页</span>
                  <p className="pres-thumb-title">{sp.title}</p>
                  <div
                    className="row between"
                    style={{ fontSize: '10px', color: '#94a3b8', marginTop: '4px' }}
                  >
                    <span>{sp.original ? '原图就绪' : '逐页稿'}</span>
                    <span>{chapters[sp.chapter].slice(0, 4)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Bottom HUD Controller Capsule */}
      <div className="pres-hud">
        <button
          className="button tiny quiet"
          onClick={presPrev}
          disabled={currIdx === 0}
          title="上一页 (←)"
        >
          <Icon name="back" />上一页
        </button>
        <div className="pres-hud-counter">
          <span className="num">{getPageNumStr(page.id)}</span>
          <span className="muted">/</span>
          <span className="num">30</span>
        </div>
        <button
          className="button tiny quiet"
          onClick={presNext}
          disabled={currIdx === order.length - 1}
          title="下一页 (→ / Space)"
        >
          <Icon name="arrow" />下一页
        </button>

        <div className="pres-hud-divider"></div>

        <button
          className={`button tiny ${presentation.showThumbnails ? 'active-guide' : 'quiet'}`}
          onClick={togglePresThumbnails}
          title="开关幻灯缩略图导航导轨 (T)"
        >
          <Icon name="gallery" />缩略导轨
          <kbd className="dm-kbd" style={{ marginLeft: '4px' }}>T</kbd>
        </button>

        <button
          className="button tiny quiet"
          onClick={() => {
            exitPresentation();
            openPage(page.id);
            openDrawer('editor', { id: page.id });
          }}
          title="跳转进入单页深度制作"
        >
          <Icon name="edit" />单页编辑
        </button>

        <div className="pres-hud-tips">
          <kbd className="dm-kbd">←</kbd><kbd className="dm-kbd">→</kbd> 切页
          <kbd className="dm-kbd">Space</kbd> 步进
          <kbd className="dm-kbd">Esc</kbd> 退出
        </div>
      </div>
    </div>
  );
}
