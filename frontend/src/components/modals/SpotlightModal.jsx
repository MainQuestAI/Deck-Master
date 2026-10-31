import React, { useRef, useEffect } from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

const allActions = [
  { type: 'scene', id: 'overview', title: '制作总览', desc: '查看全局生产进度与推荐动作', icon: 'overview' },
  { type: 'scene', id: 'content', title: '内容与页序', desc: '管理 30 页论证结构与章节', icon: 'content' },
  { type: 'scene', id: 'gallery', title: '整稿画廊', desc: '16:9 画板网格与连续长卷浏览', icon: 'gallery' },
  { type: 'scene', id: 'style', title: '风格校准', desc: '视觉 Token 与 4 阶段试作校准', icon: 'style' },
  { type: 'scene', id: 'delivery', title: '任务与交付', desc: '四大业务分区与审阅包导出', icon: 'delivery' },
  { type: 'scene', id: 'compare', title: '候选比较', desc: '比对第 13 页原图与正文候选', icon: 'compare' },
  { type: 'scene', id: 'projects', title: '所有项目', desc: '项目矩阵与本地目录切换', icon: 'projects' },
  { type: 'action', id: 'toggle-theme', title: '切换工作区质感 (工作室 / 暗室)', desc: '在 Studio Light 与 Pro Darkroom 间切换', icon: 'sparkles' },
  { type: 'action', id: 'new-project', title: '新建项目', desc: '创建新的商业表达方案 (演示)', icon: 'plus' },
  { type: 'action', id: 'export-review-pkg', title: '导出审阅包', desc: '生成当前逐页稿审阅 ZIP', icon: 'download' }
];

export default function SpotlightModal() {
  const {
    spotlightOpen,
    setSpotlightOpen,
    spotlightQuery,
    setSpotlightQuery,
    pages,
    getPageNumStr,
    setScene,
    openPage,
    toggleTheme,
    notify
  } = useDeckMaster();

  const inputRef = useRef(null);

  useEffect(() => {
    if (spotlightOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [spotlightOpen]);

  if (!spotlightOpen) return null;

  const q = spotlightQuery.toLowerCase().trim();
  const matchedPages = pages
    .filter((p) => !q || p.title.toLowerCase().includes(q) || String(p.id) === q)
    .slice(0, 5);

  const matchedActions = allActions.filter(
    (a) => !q || a.title.toLowerCase().includes(q) || a.desc.toLowerCase().includes(q)
  );

  const handleAction = (item) => {
    setSpotlightOpen(false);
    if (item.type === 'scene') {
      setScene(item.id);
    } else if (item.id === 'toggle-theme') {
      toggleTheme();
    } else if (item.id === 'new-project') {
      notify('进入短流程新建项目：任务说明 → 关联材料 → 保存位置 (前端样板演示)');
    } else if (item.id === 'export-review-pkg') {
      notify('已生成审阅包：企业内容运营方案_R08_Review.zip');
    }
  };

  const handlePageSelect = (pageId) => {
    setSpotlightOpen(false);
    openPage(pageId);
  };

  return (
    <div
      className="drawer-backdrop"
      onClick={() => setSpotlightOpen(false)}
      style={{ justifyContent: 'center', alignItems: 'flex-start' }}
    >
      <div className="spotlight-modal" onClick={(e) => e.stopPropagation()}>
        <div className="spotlight-input-wrap">
          <Icon name="search" />
          <input
            ref={inputRef}
            type="text"
            id="spotlight-input"
            placeholder="输入页名、编号或工作面..."
            value={spotlightQuery}
            onChange={(e) => setSpotlightQuery(e.target.value)}
            aria-label="全局快速查找"
          />
          <kbd className="dm-kbd">ESC</kbd>
        </div>
        <div className="spotlight-list">
          <div
            style={{
              padding: '6px 12px',
              fontSize: '11px',
              color: 'var(--dm-color-text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em'
            }}
          >
            工作面与动作
          </div>
          {matchedActions.map((a) => (
            <div
              key={a.id}
              className="spotlight-item"
              onClick={() => handleAction(a)}
            >
              <div className="row">
                <Icon name={a.icon} />
                <strong>{a.title}</strong>
              </div>
              <small>{a.desc}</small>
            </div>
          ))}

          {matchedPages.length > 0 && (
            <>
              <div
                style={{
                  padding: '10px 12px 6px',
                  fontSize: '11px',
                  color: 'var(--dm-color-text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em'
                }}
              >
                页面直达
              </div>
              {matchedPages.map((p) => (
                <div
                  key={p.id}
                  className="spotlight-item"
                  onClick={() => handlePageSelect(p.id)}
                >
                  <div className="row">
                    <span
                      className="p-no num"
                      style={{ fontSize: '12px', color: 'var(--dm-color-text-muted)', minWidth: '20px' }}
                    >
                      {getPageNumStr(p.id)}
                    </span>
                    <Icon name="page" />
                    <span>{p.title}</span>
                  </div>
                  <small>第 {p.chapter + 1} 章</small>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
