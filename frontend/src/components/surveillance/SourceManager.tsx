import React from 'react';
import { 
  Plus, 
  RefreshCw, 
  Layers, 
  Maximize2, 
  LayoutGrid
} from 'lucide-react';
import { GridLayoutMode } from './CameraGrid';

export interface SourceManagerProps {
  activeView: 'standard_cctv' | 'tracking_view';
  floors: string[];
  activeFloorFilter: string;
  onFloorFilterChange: (floor: string) => void;
  layoutMode: GridLayoutMode;
  onLayoutModeChange: (mode: GridLayoutMode) => void;
  totalSources: number;
  onlineSources: number;
  isRefreshing: boolean;
  onRefresh: () => void | Promise<void>;
  onOpenAddModal: () => void;
}

export const SourceManager: React.FC<SourceManagerProps> = ({
  activeView,
  floors,
  activeFloorFilter,
  onFloorFilterChange,
  layoutMode,
  onLayoutModeChange,
  totalSources,
  onlineSources,
  isRefreshing,
  onRefresh,
  onOpenAddModal,
}) => {
  const isTracking = activeView === 'tracking_view';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        padding: '12px 18px',
        background: '#ffffff',
        border: '1px solid var(--border-subtle, #e2e8f0)',
        borderRadius: 'var(--radius-xl, 16px)',
        boxShadow: 'var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05))',
        marginBottom: '20px',
      }}
    >
      {/* Floor Filter Tabs & Online Summary */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Layers size={13} />
          <span>FLOOR FILTER:</span>
        </span>

        <button
          onClick={() => onFloorFilterChange('ALL')}
          style={{
            padding: '5px 12px',
            borderRadius: '999px',
            fontSize: '0.74rem',
            fontWeight: 700,
            border: 'none',
            background: activeFloorFilter === 'ALL' ? '#1e293b' : '#f1f5f9',
            color: activeFloorFilter === 'ALL' ? '#ffffff' : '#64748b',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          All Floors ({totalSources})
        </button>

        {floors.map((floor) => (
          <button
            key={floor}
            onClick={() => onFloorFilterChange(floor)}
            style={{
              padding: '5px 12px',
              borderRadius: '999px',
              fontSize: '0.74rem',
              fontWeight: 700,
              border: 'none',
              background: activeFloorFilter === floor ? 'var(--accent-primary, #3b82f6)' : '#f1f5f9',
              color: activeFloorFilter === floor ? '#ffffff' : '#64748b',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {floor}
          </button>
        ))}

        <span style={{ fontSize: '0.72rem', color: '#10b981', fontWeight: 600, marginLeft: '6px' }}>
          • {onlineSources} Online
        </span>
      </div>

      {/* Right Controls: Layout Selector & Add Feed Button */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        {/* Layout Switcher */}
        <div style={{ display: 'flex', background: '#f1f5f9', padding: '2px', borderRadius: '8px' }}>
          <button
            onClick={() => onLayoutModeChange('single')}
            title="Single Focus (1x)"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '5px 10px',
              borderRadius: '6px',
              fontSize: '0.72rem',
              fontWeight: 600,
              background: layoutMode === 'single' ? '#ffffff' : 'transparent',
              color: layoutMode === 'single' ? '#0f172a' : '#64748b',
              border: 'none',
              cursor: 'pointer',
              boxShadow: layoutMode === 'single' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
            }}
          >
            <Maximize2 size={12} />
            <span>Single</span>
          </button>
          <button
            onClick={() => onLayoutModeChange('grid')}
            title="Multi-Camera Grid (Nx)"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '5px 10px',
              borderRadius: '6px',
              fontSize: '0.72rem',
              fontWeight: 600,
              background: layoutMode === 'grid' ? '#ffffff' : 'transparent',
              color: layoutMode === 'grid' ? '#0f172a' : '#64748b',
              border: 'none',
              cursor: 'pointer',
              boxShadow: layoutMode === 'grid' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
            }}
          >
            <LayoutGrid size={12} />
            <span>Grid</span>
          </button>
        </div>

        {/* Refresh button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh feeds"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px',
            padding: '7px 12px',
            background: '#ffffff',
            border: '1px solid var(--border-medium, #cbd5e1)',
            borderRadius: 'var(--radius-md, 8px)',
            fontSize: '0.76rem',
            fontWeight: 600,
            color: '#0f172a',
            cursor: isRefreshing ? 'not-allowed' : 'pointer',
          }}
        >
          <RefreshCw size={13} className={isRefreshing ? 'spin' : ''} />
          <span>Refresh</span>
        </button>

        {/* Add Feed Button */}
        <button
          id={isTracking ? 'btn-add-tracking-source' : 'btn-add-cctv-feed'}
          onClick={onOpenAddModal}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '7px 16px',
            background: 'var(--accent-primary, #3b82f6)',
            color: '#ffffff',
            border: 'none',
            borderRadius: 'var(--radius-md, 8px)',
            fontSize: '0.76rem',
            fontWeight: 700,
            cursor: 'pointer',
            boxShadow: '0 2px 4px rgba(37, 99, 235, 0.25)',
          }}
        >
          <Plus size={14} />
          <span>{isTracking ? 'Add Tracking Footage' : 'Add CCTV Feed'}</span>
        </button>
      </div>
    </div>
  );
};

export default React.memo(SourceManager);
