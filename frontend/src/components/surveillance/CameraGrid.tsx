import React, { useState } from 'react';
import { LayoutGrid, Maximize2 } from 'lucide-react';

export type GridLayoutMode = 'single' | 'grid';
export type GridDensity = 'auto' | '2-col' | '3-col' | '4-col';

interface CameraGridProps {
  layoutMode: GridLayoutMode;
  onLayoutChange?: (mode: GridLayoutMode) => void;
  children: React.ReactNode[];
  selectedChildIndex?: number;
  totalFeeds: number;
}

export const CameraGrid: React.FC<CameraGridProps> = ({
  layoutMode,
  onLayoutChange,
  children,
  selectedChildIndex = 0,
  totalFeeds,
}) => {
  const [gridDensity, setGridDensity] = useState<GridDensity>('auto');

  // Compute CSS grid template columns based on total feeds and density selection
  const getGridTemplateColumns = () => {
    if (layoutMode === 'single') {
      return '1fr';
    }

    if (gridDensity === '2-col') return 'repeat(2, minmax(0, 1fr))';
    if (gridDensity === '3-col') return 'repeat(3, minmax(0, 1fr))';
    if (gridDensity === '4-col') return 'repeat(4, minmax(0, 1fr))';

    // Auto density: dynamic based on count
    if (totalFeeds <= 1) return '1fr';
    if (totalFeeds === 2) return 'repeat(2, minmax(0, 1fr))';
    if (totalFeeds === 3) return 'repeat(3, minmax(0, 1fr))';
    if (totalFeeds === 4) return 'repeat(2, minmax(0, 1fr))';
    // 5 or more feeds: fluid auto-fit without limit
    return 'repeat(auto-fit, minmax(360px, 1fr))';
  };

  if (totalFeeds === 0) {
    return (
      <div
        style={{
          padding: '48px 24px',
          background: '#ffffff',
          borderRadius: 'var(--radius-xl, 16px)',
          border: '1px dashed var(--border-medium, #cbd5e1)',
          textAlign: 'center',
          color: 'var(--text-muted, #64748b)',
        }}
      >
        <p style={{ margin: 0, fontSize: '0.9rem', fontWeight: 600 }}>
          No camera sources available for this view.
        </p>
      </div>
    );
  }

  // Single focus layout mode
  if (layoutMode === 'single') {
    const activeChild = children[selectedChildIndex] || children[0];
    const otherChildren = children.filter((_, idx) => idx !== selectedChildIndex);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Layout quick toggle */}
        {onLayoutChange && (
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={() => onLayoutChange('grid')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '5px 12px',
                background: '#f1f5f9',
                border: 'none',
                borderRadius: '6px',
                fontSize: '0.74rem',
                fontWeight: 600,
                color: '#475569',
                cursor: 'pointer',
              }}
            >
              <LayoutGrid size={13} />
              <span>Switch to Grid View ({totalFeeds} feeds)</span>
            </button>
          </div>
        )}

        {/* Main focused camera */}
        <div style={{ width: '100%', maxWidth: '1200px', margin: '0 auto' }}>
          {activeChild}
        </div>

        {/* Thumbnail strip of other feeds if more than 1 */}
        {children.length > 1 && (
          <div style={{ marginTop: '10px' }}>
            <h5
              style={{
                margin: '0 0 10px 0',
                fontSize: '0.76rem',
                fontWeight: 700,
                color: 'var(--text-muted, #64748b)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              Other Feeds ({otherChildren.length}) — Click to focus
            </h5>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                gap: '12px',
              }}
            >
              {children.map((child, idx) => {
                if (idx === selectedChildIndex) return null;
                return (
                  <div key={idx} style={{ opacity: 0.9, transform: 'scale(0.98)' }}>
                    {child}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Multi-camera grid layout mode
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Sub-toolbar for grid density preset when 3 or more feeds */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {onLayoutChange && (
          <button
            onClick={() => onLayoutChange('single')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '6px',
              fontSize: '0.72rem',
              fontWeight: 600,
              color: '#64748b',
              cursor: 'pointer',
            }}
          >
            <Maximize2 size={12} />
            <span>Single Focus</span>
          </button>
        )}

        {totalFeeds >= 3 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: 'auto' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim, #94a3b8)', fontWeight: 600 }}>
              Grid Density:
            </span>
            <div style={{ display: 'flex', background: '#f1f5f9', padding: '2px', borderRadius: '6px' }}>
              <button
                onClick={() => setGridDensity('auto')}
                style={{
                  background: gridDensity === 'auto' ? '#ffffff' : 'transparent',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '3px 8px',
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  color: gridDensity === 'auto' ? '#0f172a' : '#64748b',
                  cursor: 'pointer',
                }}
                title="Fluid Auto-fit (Adapts to screen & count)"
              >
                Auto ({totalFeeds})
              </button>
              <button
                onClick={() => setGridDensity('2-col')}
                style={{
                  background: gridDensity === '2-col' ? '#ffffff' : 'transparent',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '3px 8px',
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  color: gridDensity === '2-col' ? '#0f172a' : '#64748b',
                  cursor: 'pointer',
                }}
                title="2 Columns (2-Up)"
              >
                2-Up
              </button>
              {totalFeeds >= 3 && (
                <button
                  onClick={() => setGridDensity('3-col')}
                  style={{
                    background: gridDensity === '3-col' ? '#ffffff' : 'transparent',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    color: gridDensity === '3-col' ? '#0f172a' : '#64748b',
                    cursor: 'pointer',
                  }}
                  title="3 Columns (3-Up)"
                >
                  3-Up
                </button>
              )}
              {totalFeeds >= 4 && (
                <button
                  onClick={() => setGridDensity('4-col')}
                  style={{
                    background: gridDensity === '4-col' ? '#ffffff' : 'transparent',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    color: gridDensity === '4-col' ? '#0f172a' : '#64748b',
                    cursor: 'pointer',
                  }}
                  title="4 Columns (4-Up)"
                >
                  4-Up
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Dynamic Grid Container */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: getGridTemplateColumns(),
          gap: '16px',
          width: '100%',
        }}
      >
        {children}
      </div>
    </div>
  );
};

export default React.memo(CameraGrid);
