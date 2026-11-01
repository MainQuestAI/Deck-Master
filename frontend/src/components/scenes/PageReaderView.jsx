import React from 'react';
import Icon from '../common/Icon';
import CanvasToolbar from '../canvas/CanvasToolbar';
import CanvasGuides from '../canvas/CanvasGuides';
import ReviewBubbleCard from '../modals/ReviewBubbleCard';
import { useDeckMaster } from '../../context/DeckMasterContext';
import { chapters } from '../../constants/data';

export default function PageReaderView() {
  const {
    currentPage,
    getPage,
    getPageNumStr,
    order,
    pageView,
    setPageView,
    pageLayer,
    setPageLayer,
    openPage,
    openCompare,
    openDrawer,
    startPresentation,
    activeCommentBlock,
    setActiveCommentBlock,
    annotations,
    setScene,
    notify
  } = useDeckMaster();

  const p = getPage(currentPage) || getPage(16);
  const currIdx = order.indexOf(p.id);

  // Compute comments for current page
  const pageComments = [];
  ['goal', 'point1', 'point2', 'point3', 'point4', 'body'].forEach((key) => {
    const blockId = `${p.id}-${key}`;
    const labels = {
      goal: '核心目标与论点',
      point1: '要点 01·业务目标',
      point2: '要点 02·来源事实',
      point3: '要点 03·执行要求',
      point4: '要点 04·比较采用',
      body: '正文讲述与陈述重点'
    };
    (annotations[blockId] || []).forEach((c) => {
      pageComments.push({ ...c, blockId, blockLabel: labels[key] });
    });
  });

  const totalComments = pageComments.length;
  const pendingCount = pageComments.filter((c) => c.status === 'pending').length;
  const adoptedCount = pageComments.filter((c) => c.status === 'adopted').length;
  const resolvedCount = pageComments.filter((c) => c.status === 'resolved').length;

  const renderAnnotatableBlock = (blockId, blockLabel, children) => {
    const comments = annotations[blockId] || [];
    const hasPending = comments.some((c) => c.status === 'pending');
    const isActive = activeCommentBlock === blockId;

    return (
      <div className={`annotatable-block ${isActive ? 'active' : ''}`} data-block-id={blockId}>
        <div className="block-content">{children}</div>
        <div className="annotation-gutter">
          {comments.length > 0 ? (
            <button
              className={`annot-bubble-btn ${hasPending ? 'has-pending' : 'is-resolved'}`}
              onClick={() => setActiveCommentBlock(isActive ? null : blockId)}
              title={`查看 ${comments.length} 条批注 (${hasPending ? '待处理' : '已解决'})`}
            >
              <Icon name="comment" />
              <span className="annot-count">{comments.length}</span>
              <span className={`annot-status-tag ${hasPending ? 'tag-warn' : 'tag-ok'}`}>
                {hasPending ? '待处理' : '已解决'}
              </span>
            </button>
          ) : (
            <button
              className="button tiny quiet annot-add-btn"
              onClick={() => setActiveCommentBlock(blockId)}
              title="添加段落批注"
            >
              <Icon name="plus" />批注
            </button>
          )}
        </div>

        {isActive && (
          <ReviewBubbleCard
            blockId={blockId}
            blockLabel={blockLabel}
            onClose={() => setActiveCommentBlock(null)}
          />
        )}
      </div>
    );
  };

  return (
    <div>
      <div className="view-head">
        <div>
          <div className="row" style={{ marginBottom: '8px', fontSize: '12px' }}>
            <button className="button tiny quiet" onClick={() => setScene('content')}>
              <Icon name="back" />返回内容与页序
            </button>
            <span className="muted">/</span>
            <span className="muted">
              第 {p.chapter + 1} 章 · {chapters[p.chapter]}
            </span>
          </div>
          <h1>第 {getPageNumStr(p.id)} 页 · {p.title}</h1>
        </div>
        <div className="head-actions">
          <button
            className="button tiny quiet"
            onClick={() => {
              const card = document.querySelector('.review-summary-card');
              if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' });
              notify('已定位至右侧审阅与批注面板');
            }}
            title="本页审阅批注统计"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}
          >
            <Icon name="comment" />
            <span>审阅批注</span>
            <span
              className={`num ${pendingCount > 0 ? 'badge warn pulse' : 'badge ok'}`}
              style={{ fontSize: '11px', padding: '1px 6px' }}
            >
              {totalComments} 条{pendingCount > 0 ? ` (${pendingCount} 待处理)` : ' (已解决)'}
            </span>
          </button>
          <button
            className="button"
            onClick={() => currIdx > 0 && openPage(order[currIdx - 1])}
            disabled={currIdx === 0}
          >
            <Icon name="back" />上一页
          </button>
          <span className="num muted" style={{ fontSize: '13px' }}>
            {getPageNumStr(p.id)} / 30
          </span>
          <button
            className="button"
            onClick={() => currIdx < order.length - 1 && openPage(order[currIdx + 1])}
            disabled={currIdx === order.length - 1}
          >
            <Icon name="arrow" />下一页
          </button>
          <button
            className="button"
            onClick={() => startPresentation(p.id)}
            title="进入本页全屏放映预览"
          >
            <Icon name="play" />全屏放映
          </button>
          <button
            className="primary"
            onClick={() => openDrawer('editor', { id: p.id })}
          >
            <Icon name="edit" />修改正文 (抽屉)
          </button>
        </div>
      </div>

      {/* Candidate Notification Banner */}
      {p.candidate && (
        <div
          className="order-alert"
          style={{ background: '#f0f9ff', borderColor: '#bae6fd', color: '#0369a1' }}
        >
          <span>
            <strong>本页有 1 版原图与正文候选待比对。</strong> 当前正文与候选之间存在 2 处优化调整。
          </span>
          <button className="primary tiny" onClick={() => openCompare(p.id)}>
            <Icon name="compare" />进入比对工作台
          </button>
        </div>
      )}

      <div className="reader-container">
        {/* Main Content Reader / Canvas */}
        <section>
          {/* View Toggle & Layer Bar */}
          <div
            className="row between"
            style={{
              marginBottom: '18px',
              paddingBottom: '12px',
              borderBottom: '1px solid var(--dm-color-border)',
              flexWrap: 'wrap',
              gap: '10px'
            }}
          >
            <div className="segmented-control" role="group" aria-label="工作模式切换">
              <button
                className={pageView === 'read' ? 'active' : ''}
                onClick={() => setPageView('read')}
              >
                <Icon name="read" />正文阅读模式
              </button>
              <button
                className={pageView === 'preview' ? 'active' : ''}
                onClick={() => setPageView('preview')}
              >
                <Icon name="gallery" />16:9 画板预览
              </button>
            </div>

            <div className="row" style={{ gap: '8px' }}>
              <span className="muted" style={{ fontSize: '12px' }}>产物层：</span>
              <div className="segmented-control" role="group" aria-label="产物层切换">
                <button
                  className={pageLayer === 'text' ? 'active' : ''}
                  onClick={() => setPageLayer('text')}
                >
                  <Icon name="content" />逐页稿
                </button>
                <button
                  className={pageLayer === 'original' ? 'active' : ''}
                  onClick={() => setPageLayer('original')}
                >
                  <Icon name="gallery" />原图 ({p.original ? '1' : '0'})
                </button>
                <button
                  className={pageLayer === 'svg' ? 'active' : ''}
                  onClick={() => setPageLayer('svg')}
                >
                  <Icon name="layers" />SVG ({p.svg ? '1' : '0'})
                </button>
              </div>
            </div>
          </div>

          {pageView === 'read' ? (
            /* Manuscript Document Card */
            <article className="manuscript-card">
              <p className="eyebrow">
                第 {p.chapter + 1} 章 · {chapters[p.chapter]} · 第 {getPageNumStr(p.id)} 页
              </p>
              <h2>{p.title}</h2>

              {/* Block 1: Goal */}
              {renderAnnotatableBlock(
                `${p.id}-goal`,
                '核心目标与论点',
                <p className="lead-text" style={{ marginBottom: 0 }}>
                  {p.goal}
                </p>
              )}

              <div className="points-grid" style={{ marginTop: '24px' }}>
                {renderAnnotatableBlock(
                  `${p.id}-point1`,
                  '要点 01 · 明确业务目标',
                  <>
                    <h4>01 · 明确业务目标</h4>
                    <p>以具体的业务收益为起点，阐述本页所促成的管理层共识，拒绝空洞概念。</p>
                  </>
                )}
                {renderAnnotatableBlock(
                  `${p.id}-point2`,
                  '要点 02 · 组织来源事实',
                  <>
                    <h4>02 · 组织来源事实</h4>
                    <p>关联真实访谈与盘点材料，确保每一条关键结论均有可追溯的证据支撑。</p>
                  </>
                )}
                {renderAnnotatableBlock(
                  `${p.id}-point3`,
                  '要点 03 · 形成执行要求',
                  <>
                    <h4>03 · 形成执行要求</h4>
                    <p>明确页面焦点与呈现关系，为后续原图生成和排版工具提供确定性的输入。</p>
                  </>
                )}
                {renderAnnotatableBlock(
                  `${p.id}-point4`,
                  '要点 04 · 比较后再采用',
                  <>
                    <h4>04 · 比较后再采用</h4>
                    <p>返回结果作为独立候选展示，通过并排比对确认无偏离后，再升级为新当前版本。</p>
                  </>
                )}
              </div>

              <h3 style={{ marginTop: '28px' }}>正文讲述与陈述重点</h3>
              {renderAnnotatableBlock(
                `${p.id}-body`,
                '正文讲述与陈述重点',
                <p style={{ fontSize: '14px', lineHeight: 1.8, color: '#334155', marginTop: '6px', marginBottom: 0, whiteSpace: 'pre-line' }}>
                  {p.body}
                </p>
              )}

              <div
                className="row between"
                style={{
                  marginTop: '36px',
                  paddingTop: '18px',
                  borderTop: '1px solid var(--dm-color-border-subtle)'
                }}
              >
                <div className="row" style={{ gap: '8px' }}>
                  <button className="button tiny" onClick={() => openDrawer('note', { id: p.id })}>
                    <Icon name="note" />记录本页调整意见
                  </button>
                  <button
                    className="button tiny quiet"
                    onClick={() => setActiveCommentBlock(`${p.id}-body`)}
                  >
                    <Icon name="comment" />添加段落批注
                  </button>
                </div>
                <button
                  className="button tiny primary"
                  onClick={() => notify('已根据当前逐页稿与规范整理好制作要求，准备进入生成流水。')}
                >
                  <Icon name="file" />准备制作要求
                </button>
              </div>
            </article>
          ) : (
            /* 16:9 Canvas View */
            <div
              style={{
                background: 'var(--dm-color-surface)',
                border: '1px solid var(--dm-color-border)',
                borderRadius: 'var(--dm-radius-panel)',
                padding: '32px 36px',
                boxShadow: 'var(--dm-elevation-canvas)'
              }}
            >
              <CanvasToolbar />
              <div
                className="slide-canvas"
                style={{
                  aspectRatio: '16 / 9',
                  padding: '36px',
                  borderRadius: '8px',
                  position: 'relative'
                }}
              >
                <CanvasGuides />
                <div className="canvas-head">
                  <span>企业内容运营方案 · 第 {getPageNumStr(p.id)} 页</span>
                  <span>{chapters[p.chapter]}</span>
                </div>
                <div style={{ margin: '32px 0' }}>
                  <h2 style={{ fontSize: '27px', lineHeight: 1.35, marginBottom: '14px' }}>
                    {p.title}
                  </h2>
                  <p style={{ fontSize: '15px', lineHeight: 1.7, color: 'var(--dm-color-text-secondary)' }}>
                    {p.goal}
                  </p>
                </div>
                <div className="canvas-cols">
                  <div>目标聚焦</div>
                  <div>来源依据</div>
                  <div>结果流转</div>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Non-modal Side Fact & Source Rail */}
        <aside className="side-fact-rail">
          <div className="fact-card">
            <h3>本页关联事实与依据</h3>
            <strong>业务需求访谈纪要 §2</strong>
            <blockquote>
              “内容确认之后，设计和制作仍会反复沟通相同要求。希望每一次修改都能明确依据与受影响的页面范围。”
            </blockquote>
            <button
              className="button tiny"
              onClick={() => openDrawer('source', { id: p.id })}
              style={{ width: '100%', marginTop: '10px' }}
            >
              <Icon name="file" />展开完整依据
            </button>
          </div>

          <div className="fact-card">
            <h3>本页制作产物进度</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px', marginTop: '10px' }}>
              <div className="row between">
                <span>逐页稿</span>
                {p.review ? <span className="badge warn">待确认</span> : <span className="badge ok">已确认</span>}
              </div>
              <div className="row between">
                <span>原图生成</span>
                {p.candidate ? (
                  <span className="badge warn pulse">候选待比对</span>
                ) : p.original ? (
                  <span className="badge ok">已采用</span>
                ) : (
                  <span className="muted">未制作</span>
                )}
              </div>
              <div className="row between">
                <span>SVG 矢量</span>
                {p.svg ? <span className="badge ok">已采用</span> : <span className="muted">未转换</span>}
              </div>
            </div>
          </div>

          {/* Section 3: Review & Annotation Summary Card */}
          <div className="fact-card review-summary-card">
            <div className="row between">
              <h3>本页审阅与批注</h3>
              {pendingCount > 0 ? (
                <span className="badge warn pulse">{pendingCount} 待处理</span>
              ) : (
                <span className="badge ok">全部解决</span>
              )}
            </div>

            <div className="review-stats-bar">
              <div className="stat-pill warn">
                <strong>{pendingCount}</strong> 待处理
              </div>
              <div className="stat-pill ok">
                <strong>{adoptedCount}</strong> 已采纳
              </div>
              <div className="stat-pill neutral">
                <strong>{resolvedCount}</strong> 已解决
              </div>
            </div>

            {pageComments.length > 0 ? (
              <div className="review-comments-mini-list">
                {pageComments.map((c) => (
                  <div
                    key={c.id}
                    className="mini-comment-item"
                    onClick={() => {
                      setActiveCommentBlock(c.blockId);
                      const el = document.querySelector(`[data-block-id="${c.blockId}"]`);
                      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }}
                  >
                    <div className="row between">
                      <strong style={{ fontSize: '12px' }}>
                        {c.author}{' '}
                        <span className="muted" style={{ fontWeight: 'normal' }}>
                          ({c.role})
                        </span>
                      </strong>
                      <span
                        className={`badge ${c.status === 'pending' ? 'warn' : c.status === 'adopted' ? 'ok' : 'neutral'}`}
                        style={{ fontSize: '10px', padding: '1px 5px' }}
                      >
                        {c.status === 'pending' ? '待处理' : c.status === 'adopted' ? '已采纳' : '已解决'}
                      </span>
                    </div>
                    <p className="mini-comment-text">{c.text}</p>
                    <div className="row between" style={{ fontSize: '11px', color: 'var(--dm-color-text-muted)', marginTop: '4px' }}>
                      <span>{c.blockLabel}</span>
                      <span className="num">{c.time}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted" style={{ fontSize: '12px', margin: '10px 0' }}>
                当前段落暂无待处理审阅批注。
              </p>
            )}

            <button
              className="button tiny"
              onClick={() => setActiveCommentBlock(`${p.id}-body`)}
              style={{ width: '100%', marginTop: '12px' }}
            >
              <Icon name="plus" />添加段落批注
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}
