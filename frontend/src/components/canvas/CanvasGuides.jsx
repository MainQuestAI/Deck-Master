import React from 'react';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function CanvasGuides() {
  const { canvasGuides } = useDeckMaster();

  if (!canvasGuides.safeArea && !canvasGuides.thirds && !canvasGuides.grid) {
    return null;
  }

  return (
    <div className="canvas-guides-container" aria-hidden="true">
      {canvasGuides.safeArea && (
        <div className="guide-safe-area">
          <span className="guide-safe-area-tag">80% 核心安全区</span>
        </div>
      )}
      {canvasGuides.thirds && (
        <div className="guide-thirds">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="guide-third-cell"></div>
          ))}
        </div>
      )}
      {canvasGuides.grid && (
        <div className="guide-grid-columns">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="guide-col-bar"></div>
          ))}
        </div>
      )}
    </div>
  );
}
