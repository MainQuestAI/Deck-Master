import React, { useRef, useEffect } from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function CompareView() {
  const {
    compareMode,
    setCompareMode,
    compareCurtainPos,
    setCompareCurtainPos,
    candidateDiffData,
    adoptCandidate,
    keepCurrent,
    setScene,
    getPage,
    getPageNumStr
  } = useDeckMaster();

  const page = getPage(candidateDiffData.pageId);
  const boardRef = useRef(null);
  const innerRef = useRef(null);

  // Sync the inner width of clipped curtain layer with the container width
  useEffect(() => {
    const syncWidth = () => {
      if (boardRef.current && innerRef.current) {
        innerRef.current.style.width = `${boardRef.current.clientWidth}px`;
      }
    };
    syncWidth();
    window.addEventListener('resize', syncWidth);
    return () => window.removeEventListener('resize', syncWidth);
  }, [compareMode]);

  return (
    <div>
      <div className="view-head">
        <div>
          <div className="row" style={{ marginBottom: '8px', fontSize: '12px' }}>
            <button className="button tiny quiet" onClick={() => setScene('overview')}>
              <Icon name="back" />返回制作总览
            </button>
            <span className="muted">/</span>
            <span className="muted">候选比对工作区</span>
          </div>
          <h1>比对第 {getPageNumStr(page.id)} 页 · 原图与正文候选</h1>
          <p>支持并排视图与交互式卷帘滑块双模式，精准透视新旧版面微观排版差异与下游影响。</p>
        </div>
        <div className="head-actions">
          {candidateDiffData.status === 'adopted' ? (
            <span className="badge ok pulse">已采用此候选为 R 09</span>
          ) : candidateDiffData.status === 'kept' ? (
            <span className="badge neutral">已决定保留当前稿 R 08</span>
          ) : (
            <span className="badge warn pulse">待决定 · 尚未采用</span>
          )}
        </div>
      </div>

      <div className="compare-container">
        {/* Mode Switcher Segmented Bar */}
        <div className="row between" style={{ marginBottom: '20px', flexWrap: 'wrap', gap: '10px' }}>
          <div className="segmented-control" role="group" aria-label="比对模式切换">
            <button
              className={compareMode === 'side-by-side' ? 'active' : ''}
              onClick={() => setCompareMode('side-by-side')}
            >
              <Icon name="compare" />并排视图 (Side-by-Side)
            </button>
            <button
              className={compareMode === 'curtain' ? 'active' : ''}
              onClick={() => setCompareMode('curtain')}
            >
              <Icon name="layers" />卷帘滑块透视 (Curtain Split)
            </button>
          </div>
          <div className="row" style={{ fontSize: '12px', color: 'var(--dm-color-text-muted)' }}>
            <span className="badge neutral" style={{ fontSize: '11px' }}>
              生成候选 C 02 对比基准 R 08
            </span>
          </div>
        </div>

        {compareMode === 'side-by-side' ? (
          /* Mode 1: Side by Side Board */
          <div className="compare-grid-board">
            {/* Left: Benchmark R08 */}
            <div className="compare-col">
              <header>
                <strong>基准 · 当前稿 R 08</strong>
                <span className="badge ok">当前稳定版</span>
              </header>
              <div className="col-body">
                <h3 style={{ marginBottom: '14px' }}>{page.title}</h3>
                <p style={{ fontSize: '14px', lineHeight: 1.8, color: 'var(--dm-color-text-secondary)', whiteSpace: 'pre-wrap' }}>
                  把一次创作转化为可复用的生产流程。
                  {'\n\n'}
                  <span className="diff-removed">
                    当前内容制作往往停留在单次项目的交付，制作完成后素材与上下文即被搁置。
                  </span>
                  {'\n\n'}
                  <span className="diff-removed">
                    这导致下一次面临相似业务需求时，团队仍需从零寻找素材、重新对齐要求，造成极大的重复消耗。
                  </span>
                  {'\n\n'}
                  建立可复用机制后，单次投入将转化为长期可复用的企业资产。
                </p>

                <div
                  style={{
                    marginTop: '28px',
                    padding: '16px',
                    background: 'var(--dm-color-surface-subtle)',
                    borderRadius: '6px',
                    fontSize: '12px'
                  }}
                >
                  <strong>基准属性</strong>
                  <p className="muted" style={{ marginTop: '4px' }}>
                    由内容团队于 10月23日 10:00 确认锁定，关联 2 处事实来源。
                  </p>
                </div>
              </div>
            </div>

            {/* Right: Candidate C02 */}
            <div className="compare-col" style={{ borderColor: '#059669' }}>
              <header style={{ background: 'var(--dm-color-surface-subtle)', borderColor: 'var(--dm-color-border)' }}>
                <strong style={{ color: '#059669' }}>候选 · 新候选版本 C 02</strong>
                <span className="badge warn pulse">等待决策</span>
              </header>
              <div className="col-body">
                <h3 style={{ marginBottom: '14px' }}>
                  把一次创作转化为可持续复用的企业生产闭环
                </h3>
                <p style={{ fontSize: '14px', lineHeight: 1.8, color: 'var(--dm-color-text-secondary)', whiteSpace: 'pre-wrap' }}>
                  把一次创作转化为可持续复用的企业生产闭环。
                  {'\n\n'}
                  <span className="diff-added">
                    当前制作停留于单次孤岛交付，完成即归档，上下文与核心素材未能结构化留存。
                  </span>
                  {'\n\n'}
                  <span className="diff-added">
                    跨团队流转时缺少明确的标准接手记录，相似需求每次都要重新挖掘背景与授权。
                  </span>
                  {'\n\n'}
                  通过将制作要求、过程决策与最终产物统一入库，让每一次产出都成为后续创作的高价值资产。
                </p>

                <div
                  style={{
                    marginTop: '28px',
                    padding: '16px',
                    background: 'var(--dm-color-surface-subtle)',
                    borderLeft: '3px solid #059669',
                    borderRadius: '6px',
                    fontSize: '12px'
                  }}
                >
                  <strong style={{ color: '#059669' }}>差异分析与影响预警</strong>
                  <p className="muted" style={{ marginTop: '4px', lineHeight: 1.6 }}>
                    论证更加紧扣企业中台价值。采用后将更新当前正文并产生新版本 R 09，历史基准 R 08 完整归档，下游原图需标记为待重新渲染。
                  </p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Mode 2: Interactive Split Curtain Slider Board */
          <div className="curtain-wrapper" style={{ marginBottom: '24px' }}>
            <div className="curtain-board" id="curtain-slider-board" ref={boardRef}>
              <span className="curtain-badge-top curtain-badge-left">
                <Icon name="check" /> 左层：基准 R 08
              </span>
              <span className="curtain-badge-top curtain-badge-right">
                <Icon name="sparkles" /> 右层：候选 C 02
              </span>

              {/* Underneath Layer: Candidate C02 */}
              <div className="curtain-layer candidate">
                <div>
                  <div className="canvas-head" style={{ marginBottom: '18px' }}>
                    <strong style={{ color: '#059669' }}>企业内容运营方案 · 候选 C 02</strong>
                    <span className="badge ok">新版叙事闭环</span>
                  </div>
                  <h2
                    style={{
                      fontSize: '23px',
                      lineHeight: 1.35,
                      marginBottom: '14px',
                      color: 'var(--dm-color-text)'
                    }}
                  >
                    把一次创作转化为可持续复用的企业生产闭环
                  </h2>
                  <p
                    style={{
                      fontSize: '14px',
                      lineHeight: 1.8,
                      color: 'var(--dm-color-text-secondary)',
                      maxWidth: '50rem'
                    }}
                  >
                    当前制作停留于单次孤岛交付，完成即归档，上下文与核心素材未能结构化留存。
                    <br />
                    <br />
                    跨团队流转时缺少明确的标准接手记录，相似需求每次都要重新挖掘背景与授权。
                    <br />
                    <br />
                    通过将制作要求、过程决策与最终产物统一入库，让每一次产出都成为后续创作的高价值资产。
                  </p>
                </div>
                <div
                  className="row between"
                  style={{
                    paddingTop: '14px',
                    borderTop: '1px solid var(--dm-color-border-subtle)',
                    fontSize: '12px'
                  }}
                >
                  <span style={{ color: '#059669', fontWeight: 520 }}>
                    候选 C 02 · 引入闭环理念与中台复用价值
                  </span>
                  <span className="num muted">16:9 排版画幅</span>
                </div>
              </div>

              {/* Top Layer: Benchmark R08 (Clipped dynamically by width: compareCurtainPos%) */}
              <div
                className="curtain-layer benchmark"
                style={{ width: `${compareCurtainPos}%` }}
              >
                <div className="curtain-inner-fixed" id="curtain-inner-benchmark" ref={innerRef}>
                  <div>
                    <div className="canvas-head" style={{ marginBottom: '18px' }}>
                      <strong>企业内容运营方案 · 基准 R 08</strong>
                      <span className="badge ok">当前稳定稿</span>
                    </div>
                    <h2
                      style={{
                        fontSize: '23px',
                        lineHeight: 1.35,
                        marginBottom: '14px',
                        color: 'var(--dm-color-text)'
                      }}
                    >
                      把一次创作转化为可复用的生产流程
                    </h2>
                    <p
                      style={{
                        fontSize: '14px',
                        lineHeight: 1.8,
                        color: 'var(--dm-color-text-secondary)',
                        maxWidth: '50rem'
                      }}
                    >
                      当前内容制作往往停留在单次项目的交付，制作完成后素材与上下文即被搁置。
                      <br />
                      <br />
                      这导致下一次面临相似业务需求时，团队仍需从零寻找素材、重新对齐要求，造成极大的重复消耗。
                      <br />
                      <br />
                      建立可复用机制后，单次投入将转化为长期可复用的企业资产。
                    </p>
                  </div>
                  <div
                    className="row between"
                    style={{
                      paddingTop: '14px',
                      borderTop: '1px solid var(--dm-color-border-subtle)',
                      fontSize: '12px'
                    }}
                  >
                    <span className="muted">基准 R 08 · 初始大纲表述</span>
                    <span className="num muted">16:9 排版画幅</span>
                  </div>
                </div>
              </div>

              {/* Center Divider Handle */}
              <div
                className="curtain-divider-handle"
                style={{ left: `${compareCurtainPos}%` }}
              >
                <Icon name="drag" />
              </div>

              {/* Invisible Range Slider */}
              <input
                type="range"
                min="3"
                max="97"
                value={compareCurtainPos}
                onChange={(e) => setCompareCurtainPos(Number(e.target.value))}
                className="curtain-range-input"
                aria-label="左右拖拽卷帘对比两版排版差异"
              />
            </div>

            {/* Quick Presets */}
            <div
              className="row between"
              style={{
                marginTop: '12px',
                fontSize: '12px',
                color: 'var(--dm-color-text-muted)',
                flexWrap: 'wrap',
                gap: '8px'
              }}
            >
              <div className="row" style={{ gap: '8px' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Icon name="more" /> 快捷透视：
                </span>
                <button
                  className="button tiny quiet"
                  onClick={() => setCompareCurtainPos(12)}
                >
                  <Icon name="back" />透视候选 C 02 (12%)
                </button>
                <button
                  className="button tiny quiet"
                  onClick={() => setCompareCurtainPos(50)}
                >
                  <Icon name="compare" />中线 50% 卷帘对比
                </button>
                <button
                  className="button tiny quiet"
                  onClick={() => setCompareCurtainPos(88)}
                >
                  <Icon name="arrow" />呈现基准 R 08 (88%)
                </button>
              </div>
              <span className="num muted">
                当前分割线：<strong id="curtain-pos-val">{compareCurtainPos}%</strong> · 拖拽中央把手实时透视微观版面
              </span>
            </div>
          </div>
        )}

        {/* Decision Action Bar */}
        <div className="decision-action-bar">
          <div>
            <strong style={{ fontSize: '15px' }}>决策确认区</strong>
            <p className="muted" style={{ fontSize: '13px', marginTop: '4px' }}>
              决定只保存在当前样页。采用候选会更新本页并沉淀版本记录。
            </p>
          </div>
          <div className="row">
            <button
              className="button"
              onClick={keepCurrent}
              disabled={candidateDiffData.status !== 'pending'}
            >
              <Icon name="close" />保留当前基准 R 08
            </button>
            <button
              className="primary"
              onClick={adoptCandidate}
              disabled={candidateDiffData.status !== 'pending'}
            >
              <Icon name="check" />采用此候选 (升级为 R 09)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
