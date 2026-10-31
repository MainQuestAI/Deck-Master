import React from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';
import { chapters, materialsList } from '../../constants/data';

export default function ContentView() {
  const {
    contentTab,
    setContentTab,
    chapterFilter,
    setChapterFilter,
    query,
    setQuery,
    order,
    savedOrder,
    orderDirty,
    movePage,
    undoOrder,
    selected,
    toggleSelect,
    clearSelection,
    openPage,
    openDrawer,
    getPageNumStr,
    getPage,
    notify
  } = useDeckMaster();

  const currentChapterPages = order.map(getPage).filter((p) => {
    if (!p) return false;
    if (chapterFilter >= 0 && p.chapter !== chapterFilter) return false;
    if (query && !p.title.includes(query)) return false;
    return true;
  });

  return (
    <div>
      <div className="view-head">
        <div>
          <h1>内容与页序</h1>
          <p>管理 30 页商业表达方案的论证主线、章节结构与来源依据。</p>
        </div>
        <div className="head-actions">
          <button className="button" onClick={() => openDrawer('brief')}>
            <Icon name="file" />
            查看任务要求
          </button>
          <button className="button" onClick={() => openDrawer('argument')}>
            <Icon name="layers" />
            章节内容计划
          </button>
        </div>
      </div>

      {/* Partition Tabs */}
      <div className="tab-row" role="tablist">
        <button
          className={contentTab === 'structure' ? 'active' : ''}
          onClick={() => setContentTab('structure')}
        >
          <Icon name="content" />逐页稿与页序
        </button>
        <button
          className={contentTab === 'chapters' ? 'active' : ''}
          onClick={() => setContentTab('chapters')}
        >
          <Icon name="layers" />章节与大纲计划
        </button>
        <button
          className={contentTab === 'materials' ? 'active' : ''}
          onClick={() => setContentTab('materials')}
        >
          <Icon name="file" />材料与来源依据 (4)
        </button>
      </div>

      {/* Tab: Materials */}
      {contentTab === 'materials' && (
        <div style={{ maxWidth: '980px' }}>
          <div className="row between" style={{ marginBottom: '20px' }}>
            <div>
              <h2>本轮关联的 4 份事实材料</h2>
              <p className="muted">来源事实始终约束后续正文、视觉样板与交付核对。</p>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
            {materialsList.map((m, i) => (
              <div
                key={i}
                style={{
                  border: '1px solid var(--dm-color-border)',
                  borderRadius: 'var(--dm-radius-panel)',
                  padding: '22px',
                  background: 'var(--dm-color-surface)',
                  boxShadow: 'var(--dm-elevation-card)'
                }}
              >
                <div className="row between">
                  <span className="badge neutral">{m.lines}</span>
                  <small className="muted">{m.chapters}</small>
                </div>
                <h3 style={{ margin: '14px 0 8px' }}>{m.title}</h3>
                <p style={{ fontSize: '13px', color: 'var(--dm-color-text-secondary)', lineHeight: 1.65 }}>
                  {m.desc}
                </p>
                <div style={{ marginTop: '18px', paddingTop: '14px', borderTop: '1px solid var(--dm-color-border-subtle)' }}>
                  <button className="button tiny" onClick={() => openDrawer('source', { id: 16 })}>
                    <Icon name="file" />查看材料摘录与关联页
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Chapters */}
      {contentTab === 'chapters' && (
        <div style={{ maxWidth: '920px' }}>
          <h2>5 个章节的大纲目标与论证主线</h2>
          <p className="muted" style={{ marginBottom: '24px' }}>
            每个章节组织 6 页逐页稿，层层递进完成商业方案推演。
          </p>
          {chapters.map((ch, i) => (
            <div
              key={i}
              style={{
                border: '1px solid var(--dm-color-border)',
                borderRadius: 'var(--dm-radius-panel)',
                padding: '20px 24px',
                marginBottom: '16px',
                background: 'var(--dm-color-surface)',
                boxShadow: 'var(--dm-elevation-card)'
              }}
              className="row between"
            >
              <div>
                <div className="row" style={{ marginBottom: '6px' }}>
                  <span className="badge neutral">第 {i + 1} 章</span>
                  <strong style={{ fontSize: '15px' }}>{ch}</strong>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--dm-color-text-secondary)' }}>
                  包含第 {i * 6 + 1}–{i * 6 + 6} 页 · {i === 4 ? '目标待最终确认' : '大纲目标已锁定'}
                </p>
              </div>
              <button
                className="button tiny"
                onClick={() => {
                  setChapterFilter(i);
                  setContentTab('structure');
                  notify(`已筛选至第 ${i + 1} 章 6 页逐页稿`);
                }}
              >
                <Icon name="arrow" />筛选本章 6 页
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Tab: Structure */}
      {contentTab === 'structure' && (
        <div className="content-grid-layout">
          {/* Left Chapter Nav Rail */}
          <aside className="chapter-nav-rail">
            <h3>章节大纲</h3>
            <button
              className={chapterFilter < 0 ? 'active' : ''}
              onClick={() => setChapterFilter(-1)}
            >
              <Icon name="content" />
              整稿结构 <span className="count num">30</span>
            </button>
            {chapters.map((ch, idx) => (
              <button
                key={idx}
                className={chapterFilter === idx ? 'active' : ''}
                onClick={() => setChapterFilter(idx)}
              >
                <Icon name="file" />
                <span className="ch-name">{ch}</span> <span className="count num">6</span>
              </button>
            ))}

            <div style={{ marginTop: '24px', borderTop: '1px solid var(--dm-color-border-subtle)', paddingTop: '14px' }}>
              <h3>辅助工具</h3>
              <button className="button quiet" onClick={() => openDrawer('argument')}>
                <Icon name="arrow" />论证主线核对
              </button>
              <button className="button quiet" onClick={() => openDrawer('methods')}>
                <Icon name="arrow" />方法与参考案例
              </button>
            </div>
          </aside>

          {/* Right Page Ordering List */}
          <section className="grow">
            <div className="toolbar" style={{ marginTop: 0 }}>
              <label className="search-box">
                <Icon name="search" />
                <input
                  id="content-search"
                  type="text"
                  placeholder="搜索本视图页面"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  aria-label="搜索页面"
                />
              </label>
              <div className="row">
                <span className="muted" style={{ fontSize: '12px' }}>
                  已显示 {currentChapterPages.length} 页 · 支持键盘 <kbd className="dm-kbd">Alt+↑/↓</kbd> 调序
                </span>
              </div>
            </div>

            {/* Order Alert Banner if dirty */}
            {orderDirty && (
              <div className="order-alert">
                <span>
                  <strong>页序已在当前样页中调整。</strong> 可以撤销或预览本次调整对章节的影响。
                </span>
                <div className="row">
                  <button className="button tiny" onClick={undoOrder}>
                    <Icon name="reset" />撤销调整
                  </button>
                  <button className="primary tiny" onClick={() => openDrawer('order-review')}>
                    <Icon name="check" />预览并应用调整
                  </button>
                </div>
              </div>
            )}

            {/* Batch Action Toolbar if pages selected */}
            {selected.size > 0 && (
              <div className="batch-toolbar">
                <span>已选 <strong>{selected.size}</strong> 页</span>
                <div className="row">
                  <button className="button tiny" onClick={() => openDrawer('source', { id: 16 })}>
                    <Icon name="file" />批量查看来源
                  </button>
                  <button className="button tiny quiet" onClick={clearSelection}>
                    <Icon name="close" />取消选择
                  </button>
                </div>
              </div>
            )}

            {/* Page List */}
            <div className="page-list-container">
              {currentChapterPages.map((p, idx) => {
                const isFirstInChapter = idx === 0 || p.chapter !== currentChapterPages[idx - 1].chapter;
                const pOrderIdx = order.indexOf(p.id);
                const canMoveUp = pOrderIdx > 0 && getPage(order[pOrderIdx - 1])?.chapter === p.chapter;
                const canMoveDown = pOrderIdx < order.length - 1 && getPage(order[pOrderIdx + 1])?.chapter === p.chapter;

                return (
                  <React.Fragment key={p.id}>
                    {isFirstInChapter && (
                      <div
                        style={{
                          padding: '16px 4px 8px',
                          borderBottom: '2px solid var(--dm-color-border)',
                          marginTop: '14px'
                        }}
                        className="row between"
                      >
                        <strong style={{ fontSize: '14px' }}>
                          第 {p.chapter + 1} 章 · {chapters[p.chapter]}
                        </strong>
                        <small className="muted">共 6 页</small>
                      </div>
                    )}
                    <div className="page-item-row" id={`row-${p.id}`}>
                      <input
                        type="checkbox"
                        checked={selected.has(p.id)}
                        onChange={() => toggleSelect(p.id)}
                        aria-label={`选择第 ${getPageNumStr(p.id)} 页`}
                      />
                      <span className="p-no num">{getPageNumStr(p.id)}</span>
                      <div className="row-body">
                        <button className="title-btn" onClick={() => openPage(p.id)}>
                          <Icon name="page" />
                          {p.title}
                        </button>
                        <p>{p.goal}</p>
                        <div className="row">
                          <button
                            className="button tiny quiet"
                            onClick={() => openDrawer('source', { id: p.id })}
                          >
                            <Icon name="link" />依据 2 处
                          </button>
                          {p.review ? (
                            <span className="badge warn">待确认</span>
                          ) : (
                            <span className="badge ok">已确认</span>
                          )}
                          {p.candidate && <span className="badge warn pulse">有候选</span>}
                        </div>
                      </div>
                      <div className="row-actions">
                        <button className="button tiny" onClick={() => openPage(p.id)}>
                          <Icon name="read" />读正文
                        </button>
                        <button
                          className="button tiny icon-only"
                          onClick={() => openDrawer('rename', { id: p.id })}
                          title="修改页名"
                          aria-label="修改页名"
                        >
                          <Icon name="edit" />
                        </button>
                        <button
                          className="button tiny icon-only"
                          onClick={() => movePage(p.id, -1)}
                          disabled={!canMoveUp}
                          title="上移本页"
                          aria-label="上移本页"
                        >
                          <Icon name="up" />
                        </button>
                        <button
                          className="button tiny icon-only"
                          onClick={() => movePage(p.id, 1)}
                          disabled={!canMoveDown}
                          title="下移本页"
                          aria-label="下移本页"
                        >
                          <Icon name="down" />
                        </button>
                      </div>
                    </div>
                  </React.Fragment>
                );
              })}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
