import React from 'react';
import { 
  Layers, 
  CheckCircle2, 
  ChevronRight,
  ShieldAlert,
  Signal
} from 'lucide-react';
import { FloorKPIItem } from '../types';

interface FloorKPICardsProps {
  floors: FloorKPIItem[];
  activeFloorFilter: string;
  onSelectFloor: (floorName: string) => void;
}

function formatSeconds(sec?: number | null): string {
  if (sec == null) return '--';
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s > 0 ? `${s}s` : ''}`.trim();
}

export const FloorKPICards: React.FC<FloorKPICardsProps> = ({
  floors,
  activeFloorFilter,
  onSelectFloor,
}) => {
  return (
    <div style={{ marginBottom: '22px' }}>
      {/* Section Sub-header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '10px',
        marginBottom: '14px',
      }}>
        <div>
          <h3 style={{
            fontSize: '0.98rem',
            fontWeight: 800,
            color: 'var(--text-main)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            margin: 0,
          }}>
            <Layers size={17} color="var(--accent-primary)" />
            Floor-Level Operational KPI Panels ({floors.length} Floors)
          </h3>
          <p style={{ fontSize: '0.76rem', color: 'var(--text-muted)', margin: '2px 0 0 25px' }}>
            Per-floor monitored tables, patron density, and service timers with canonical table deduplication.
          </p>
        </div>
      </div>

      {/* Grid of Floor Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '16px',
      }}>
        {floors.map((fl) => {
          const isSelected = activeFloorFilter === fl.floor_name;
          const isFull = fl.coverage_status === 'FULL_COVERAGE';
          const isPartial = fl.coverage_status === 'PARTIAL_COVERAGE';
          const isOffline = fl.coverage_status === 'OFFLINE';

          return (
            <div
              key={fl.floor_name}
              onClick={() => onSelectFloor(fl.floor_name)}
              style={{
                background: '#ffffff',
                borderRadius: 'var(--radius-lg)',
                border: isSelected 
                  ? '2px solid var(--accent-primary)' 
                  : '1px solid var(--border-subtle)',
                padding: '16px 18px',
                boxShadow: isSelected ? '0 4px 14px rgba(37, 99, 235, 0.16)' : 'var(--shadow-sm)',
                cursor: 'pointer',
                transition: 'all 0.18s ease-in-out',
                position: 'relative',
              }}
            >
              {/* Floor Header */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '14px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    width: '28px',
                    height: '28px',
                    borderRadius: 'var(--radius-md)',
                    background: isSelected ? 'var(--accent-primary)' : '#f1f5f9',
                    color: isSelected ? '#ffffff' : 'var(--text-main)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 800,
                    fontSize: '0.8rem',
                  }}>
                    {fl.floor_name.replace('Floor ', 'F')}
                  </span>
                  <div>
                    <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: 'var(--text-main)' }}>
                      {fl.floor_name}
                    </h4>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                      {fl.monitored_sources_count} active source{fl.monitored_sources_count === 1 ? '' : 's'}
                      {fl.source_ids.length > 0 && ` (${fl.source_ids.join(', ')})`}
                    </span>
                  </div>
                </div>

                {/* Coverage Status Badge */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '3px 8px',
                  borderRadius: 'var(--radius-full)',
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  background: isFull ? '#f0fdf4' : isPartial ? '#fffbeb' : '#f1f5f9',
                  color: isFull ? '#16a34a' : isPartial ? '#b45309' : '#64748b',
                  border: isFull ? '1px solid #bbf7d0' : isPartial ? '1px solid #fde68a' : '1px solid #cbd5e1',
                }}>
                  {isFull ? (
                    <>
                      <CheckCircle2 size={12} />
                      <span>Full Coverage</span>
                    </>
                  ) : isPartial ? (
                    <>
                      <Signal size={12} />
                      <span>Partial Coverage</span>
                    </>
                  ) : (
                    <>
                      <ShieldAlert size={12} />
                      <span>Coverage Offline</span>
                    </>
                  )}
                </div>
              </div>

              {/* Floor Metrics 2x2 Grid */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '10px',
                background: '#f8fafc',
                padding: '12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}>
                {/* Metric 1: Tables Occupancy */}
                <div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                    Table Occupancy
                  </div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 800, color: isOffline ? '#94a3b8' : 'var(--text-main)', marginTop: '2px' }}>
                    {isOffline ? 'Offline' : `${fl.occupancy_rate_percent}%`}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                    {fl.occupied_tables} / {fl.total_tables} tables occupied
                  </div>
                </div>

                {/* Metric 2: Diners */}
                <div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                    Tracked Diners
                  </div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 800, color: isOffline ? '#94a3b8' : 'var(--accent-primary)', marginTop: '2px' }}>
                    {fl.detected_diners != null ? `${fl.detected_diners} Patrons` : '--'}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                    YOLO26 Person BBoxes
                  </div>
                </div>

                {/* Metric 3: First Response Time */}
                <div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                    First Response
                  </div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 800, color: isOffline ? '#94a3b8' : 'var(--text-main)', marginTop: '2px' }}>
                    {formatSeconds(fl.avg_response_time_sec)}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: '#10b981' }}>
                    Target: &le; 3m
                  </div>
                </div>

                {/* Metric 4: Alerts */}
                <div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                    Active Alerts
                  </div>
                  <div style={{
                    fontSize: '1.05rem',
                    fontWeight: 800,
                    color: fl.critical_alerts_count > 0 ? '#dc2626' : fl.warning_alerts_count > 0 ? '#d97706' : '#10b981',
                    marginTop: '2px',
                  }}>
                    {fl.active_alerts_count} Active
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                    {fl.critical_alerts_count} crit, {fl.warning_alerts_count} warn
                  </div>
                </div>
              </div>

              {/* Card Footer: Interactive Filter Link */}
              <div style={{
                marginTop: '12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '0.72rem',
                color: isSelected ? 'var(--accent-primary)' : 'var(--text-muted)',
                fontWeight: isSelected ? 700 : 500,
              }}>
                <span>{isSelected ? '● Currently Filtering View' : 'Click to filter tracking sources'}</span>
                <ChevronRight size={14} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
export default FloorKPICards;
