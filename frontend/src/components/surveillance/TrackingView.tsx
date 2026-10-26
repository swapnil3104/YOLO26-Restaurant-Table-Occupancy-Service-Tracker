import React from 'react';
import { Sparkles, Plus, RotateCcw } from 'lucide-react';
import { 
  TrackingFootageItem, 
  FloorAnalyticsResponse, 
  ReportingScope, 
  CVTelemetry 
} from '../../types';
import { resetToDemoFootage } from '../../services/trackingFootages';
import { CameraGrid, GridLayoutMode } from './CameraGrid';
import { TrackingSourceCard } from '../TrackingSourceCard';
import { CentralKpiPanel } from './CentralKpiPanel';
import { FloorKpiPanel } from './FloorKpiPanel';
import { MonitoringStatus } from './MonitoringStatus';
import { ErrorBoundary } from '../common/ErrorBoundary';

export interface TrackingViewProps {
  footages: TrackingFootageItem[];
  activeFootage?: TrackingFootageItem;
  onSelectFootage?: (footageId: string) => void;
  layoutMode: GridLayoutMode;
  onLayoutChange: (mode: GridLayoutMode) => void;
  telemetry: CVTelemetry | null;
  floorAnalytics: FloorAnalyticsResponse;
  reportingScope: ReportingScope;
  onReportingScopeChange: (scope: ReportingScope) => void;
  freshnessSeconds?: number;
  activeFloorFilter: string;
  onSelectFloor: (floor: string) => void;
  onPauseToggle: (sourceId: string) => void;
  onRemoveRequest: (source: TrackingFootageItem) => void;
  onOpenAddModal: () => void;
}

export const TrackingView: React.FC<TrackingViewProps> = ({
  footages,
  activeFootage,
  onSelectFootage,
  layoutMode,
  onLayoutChange,
  telemetry,
  floorAnalytics,
  reportingScope,
  onReportingScopeChange,
  freshnessSeconds = 0,
  activeFloorFilter,
  onSelectFloor,
  onPauseToggle,
  onRemoveRequest,
  onOpenAddModal,
}) => {
  const selectedIdx = Math.max(
    0,
    footages.findIndex((f) => f.id === activeFootage?.id)
  );

  return (
    <ErrorBoundary fallbackTitle="Tracking View Error">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* 1. Dynamic Central Restaurant KPIs Panel */}
        {floorAnalytics?.central && (
          <CentralKpiPanel
            central={floorAnalytics.central}
            shiftHistory={floorAnalytics.shift_history}
            scope={reportingScope}
            onScopeChange={onReportingScopeChange}
            freshnessSeconds={freshnessSeconds}
          />
        )}

        {/* 2. Dynamically Generated Floor-Level KPI Cards */}
        {floorAnalytics?.floors && floorAnalytics.floors.length > 0 && (
          <FloorKpiPanel
            floors={floorAnalytics.floors}
            selectedFloor={activeFloorFilter}
            onSelectFloor={onSelectFloor}
          />
        )}

        {/* 3. Real-Time YOLO26 Pipeline Telemetry & Health HUD */}
        <MonitoringStatus
          telemetry={telemetry}
          cameraName={activeFootage?.name || 'Multi-Floor Vision Pipeline'}
          floor={activeFootage?.floor || 'All Floors'}
          isModelLoaded={true}
        />

        {/* 4. Tracking Footage Feeds Grid */}
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={16} color="#3b82f6" />
              <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 800, color: '#0f172a' }}>
                Active Tracking Footage Sources ({footages.length})
              </h3>
            </div>

            <span style={{ fontSize: '0.74rem', color: '#64748b' }}>
              Inference Target: <strong>models/yolo26_restaurant_cctv.pt</strong>
            </span>
          </div>

          {footages.length === 0 ? (
            <div
              style={{
                padding: '60px 24px',
                background: '#ffffff',
                borderRadius: 'var(--radius-xl, 16px)',
                border: '2px dashed var(--border-medium, #cbd5e1)',
                textAlign: 'center',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '12px',
              }}
            >
              <div
                style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '50%',
                  background: 'rgba(59, 130, 246, 0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Sparkles size={28} color="#3b82f6" />
              </div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#0f172a' }}>
                No Tracking Sources Added
              </h3>
              <p style={{ margin: 0, fontSize: '0.84rem', color: '#64748b', maxWidth: '420px' }}>
                Add video footage or a live camera stream across any restaurant floor to initialize the fine-tuned YOLO26 model and patron occupancy tracker.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '8px' }}>
                <button
                  onClick={onOpenAddModal}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '9px 18px',
                    background: 'var(--accent-primary, #3b82f6)',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: 'var(--radius-md, 8px)',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  <Plus size={16} />
                  <span>Add Tracking Footage</span>
                </button>
                <button
                  onClick={() => resetToDemoFootage()}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '9px 18px',
                    background: '#f1f5f9',
                    color: '#334155',
                    border: '1px solid #cbd5e1',
                    borderRadius: 'var(--radius-md, 8px)',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                  title="Restore default project demo video (Cctv-Resturant-Demo)"
                >
                  <RotateCcw size={15} />
                  <span>Load Demo Video</span>
                </button>
              </div>
            </div>
          ) : (
            <CameraGrid
              layoutMode={layoutMode}
              onLayoutChange={onLayoutChange}
              selectedChildIndex={selectedIdx}
              totalFeeds={footages.length}
            >
              {footages.map((footage) => (
                <TrackingSourceCard
                  key={footage.id}
                  source={footage}
                  isSelected={footage.id === activeFootage?.id}
                  onSelect={() => onSelectFootage && onSelectFootage(footage.id)}
                  onFocus={() => {
                    if (onSelectFootage) onSelectFootage(footage.id);
                    onLayoutChange('single');
                  }}
                  onPauseToggle={onPauseToggle}
                  onRemoveRequest={onRemoveRequest}
                />
              ))}
            </CameraGrid>
          )}
        </div>
      </div>
    </ErrorBoundary>
  );
};

export default React.memo(TrackingView);
