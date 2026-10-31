import React from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function CanvasToolbar() {
  const { canvasGuides, toggleGuide } = useDeckMaster();

  return (
    <div className="canvas-toolbar">
      <div className="row" style={{ gap: '6px' }}>
        <span
          className="muted"
          style={{
            fontSize: '12px',
            fontWeight: 'var(--dm-weight-emphasize)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}
        >
          <Icon name="layers" /> 辅助参考线：
        </span>
        <button
          className={`button tiny ${canvasGuides.safeArea ? 'active-guide' : 'quiet'}`}
          onClick={() => toggleGuide('safeArea')}
          title="开关 80% 核心安全区框线"
        >
          <Icon name="check" />
          80% 安全区
        </button>
        <button
          className={`button tiny ${canvasGuides.thirds ? 'active-guide' : 'quiet'}`}
          onClick={() => toggleGuide('thirds')}
          title="开关三分法构图参考线"
        >
          <Icon name="grid" />
          三分网格
        </button>
        <button
          className={`button tiny ${canvasGuides.grid ? 'active-guide' : 'quiet'}`}
          onClick={() => toggleGuide('grid')}
          title="开关 12 列版心标尺与栅格"
        >
          <Icon name="ruler" />
          版心标尺
        </button>
      </div>
      <div className="row" style={{ fontSize: '11px', color: 'var(--dm-color-text-muted)' }}>
        <span className="num">16:9 演示画板</span>
        <span>·</span>
        <span className="badge neutral" style={{ fontSize: '10px', padding: '1px 6px' }}>
          1920 × 1080 渲染基准
        </span>
      </div>
    </div>
  );
}
