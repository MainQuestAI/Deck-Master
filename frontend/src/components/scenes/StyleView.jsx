import React from 'react';
import Icon from '../common/Icon';
import CanvasToolbar from '../canvas/CanvasToolbar';
import CanvasGuides from '../canvas/CanvasGuides';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function StyleView() {
  const { stylePhase, setStylePhase, notify } = useDeckMaster();

  const handleRunCalibration = () => {
    setStylePhase(3);
    notify('已发起第 04 与第 16 页的视觉试作，进入第 3 阶段！(AI 试作样板)');
  };

  return (
    <div>
      <div className="view-head">
        <div>
          <h1>风格校准</h1>
          <p>确认整稿商业表达的视觉基准、字体层级、色彩约束与局部试作结果。</p>
        </div>
        <div className="head-actions">
          <button className="primary" onClick={handleRunCalibration}>
            <Icon name="check" />
            对第 04/16 页发起试作校准
            <span className="badge neutral" style={{ fontSize: '10px', padding: '1px 5px', marginLeft: '4px' }}>
              试作
            </span>
          </button>
        </div>
      </div>

      {/* 4 Phases of Calibration */}
      <div className="phase-strip">
        <div className={`phase-pill ${stylePhase >= 1 ? 'active' : ''}`}>
          01 参考与目标 (已锁定)
        </div>
        <div className={`phase-pill ${stylePhase >= 2 ? 'active' : ''}`}>
          02 确认规范与 Token (当前)
        </div>
        <div className={`phase-pill ${stylePhase >= 3 ? 'active' : ''}`}>
          03 试作与采用 (第 13–15 页)
        </div>
        <div className={`phase-pill ${stylePhase >= 4 ? 'active' : ''}`}>
          04 全稿扩展 (待执行)
        </div>
      </div>

      <div className="style-layout">
        {/* Left: 16:9 Canvas Benchmark Preview */}
        <div>
          <div
            style={{
              background: 'var(--dm-color-surface)',
              border: '1px solid var(--dm-color-border)',
              borderRadius: 'var(--dm-radius-panel)',
              padding: '28px',
              boxShadow: 'var(--dm-elevation-canvas)'
            }}
          >
            <div className="row between" style={{ marginBottom: '16px' }}>
              <strong>整稿基准样板 · 16:9 画板 (第 04 页示意)</strong>
              <span className="badge ok pulse">基准 S 01 已通过</span>
            </div>

            <CanvasToolbar />

            <div
              className="slide-canvas"
              style={{
                aspectRatio: '16 / 9',
                padding: '32px',
                borderRadius: '8px',
                position: 'relative'
              }}
            >
              <CanvasGuides />
              <div className="canvas-head" style={{ fontSize: '13px' }}>
                <strong>企业内容运营方案</strong>
                <span>04 / 30 · 现状与问题</span>
              </div>
              <div style={{ margin: '24px 0' }}>
                <h2 style={{ fontSize: '25px', lineHeight: 1.35, marginBottom: '12px' }}>
                  以任务为中心，连接内容与行动
                </h2>
                <p
                  style={{
                    fontSize: '14px',
                    lineHeight: 1.75,
                    color: 'var(--dm-color-text-secondary)',
                    maxWidth: '42rem'
                  }}
                >
                  以任务作为团队协作的共同入口，保持材料、判断、动作与结果之间的对应关系。工作人员先核对任务事实，再执行当前可行动作。
                </p>
              </div>
              <div className="canvas-cols" style={{ marginTop: '22px' }}>
                <div style={{ borderTopWidth: '3px', paddingTop: '8px' }}>
                  <strong style={{ fontSize: '13px' }}>01 需求入口</strong>
                  <p style={{ fontSize: '12px', marginTop: '4px' }}>完整理解业务背景</p>
                </div>
                <div style={{ borderTopWidth: '3px', paddingTop: '8px' }}>
                  <strong style={{ fontSize: '13px' }}>02 任务协同</strong>
                  <p style={{ fontSize: '12px', marginTop: '4px' }}>明确阶段责任人</p>
                </div>
                <div style={{ borderTopWidth: '3px', paddingTop: '8px' }}>
                  <strong style={{ fontSize: '13px' }}>03 结果回写</strong>
                  <p style={{ fontSize: '12px', marginTop: '4px' }}>沉淀企业知识资产</p>
                </div>
              </div>
            </div>

            <div
              className="row between"
              style={{ marginTop: '18px', fontSize: '12px', color: 'var(--dm-color-text-muted)' }}
            >
              <span>排版示意基准：浅色纯净背景，深色主行动，无意义装饰减至最低，保证高密度文字下的极佳可读性。</span>
              <span className="badge ok">WCAG AAA 21:1</span>
            </div>
          </div>
        </div>

        {/* Right: Token Specifications Audit */}
        <aside className="spec-box">
          <h3 style={{ marginBottom: '14px' }}>整稿视觉规范规格</h3>
          <dl>
            <div className="spec-row">
              <dt>画布比例</dt>
              <dd>16 : 9 (标准宽屏商业幻灯)</dd>
            </div>
            <div className="spec-row">
              <dt>版式风格</dt>
              <dd>中性桌面生产力 · 白底浅灰表面</dd>
            </div>
            <div className="spec-row">
              <dt>排版字系</dt>
              <dd>系统无衬线 (PingFang SC / SF Pro)</dd>
            </div>
            <div className="spec-row">
              <dt>标题行高</dt>
              <dd>1.35 – 1.4 (严格保证 CJK 不粘连)</dd>
            </div>
            <div className="spec-row">
              <dt>主行动色</dt>
              <dd>深墨色 #0f172a (严禁纯文字按钮)</dd>
            </div>
            <div className="spec-row">
              <dt>圆角尺度</dt>
              <dd>控件 6px · 面板 10px · 浮层 12px</dd>
            </div>
          </dl>

          <div
            style={{
              marginTop: '22px',
              padding: '16px',
              background: 'var(--dm-color-surface-subtle)',
              border: '1px solid var(--dm-color-border)',
              borderRadius: '6px'
            }}
          >
            <strong style={{ display: 'block', fontSize: '12px', marginBottom: '6px' }}>偏离检查发现</strong>
            <p style={{ fontSize: '12px', color: 'var(--dm-color-text-secondary)', lineHeight: 1.65 }}>
              当前稿件未检测到违反对比度或字体层级的异常。试作样页将遵循此基准执行。
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
