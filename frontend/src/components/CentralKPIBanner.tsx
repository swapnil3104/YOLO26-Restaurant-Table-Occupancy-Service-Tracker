import React from 'react';
import { 
  Building2, 
  Activity, 
  Users, 
  Clock, 
  UtensilsCrossed, 
  AlertTriangle, 
  CheckCircle2, 
  Radio, 
  History,
  ShieldCheck,
  Layers
} from 'lucide-react';
import { CentralRestaurantKPIs, ReportingScope, ShiftHistoricalSummary } from '../types';

interface CentralKPIBannerProps {
  central: CentralRestaurantKPIs;
  shiftHistory: ShiftHistoricalSummary;
  scope: ReportingScope;
  onScopeChange: (scope: ReportingScope) => void;
  freshnessSeconds?: number;
}

function formatSeconds(sec?: number | null): string {
  if (sec == null) return '--';
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s > 0 ? `${s}s` : ''}`.trim();
}

export const CentralKPIBanner: React.FC<CentralKPIBannerProps> = ({
  central,
  shiftHistory,
  scope,
  onScopeChange,
  freshnessSeconds = 2,
}) => {
  const isHistorical = scope === 'HISTORICAL_SHIFT';
  const isCombined = scope === 'COMBINED';

  return (
    <div style={{
      background: '#ffffff',
      borderRadius: 'var(--radius-xl)',
      border: '1px solid var(--border-subtle)',
      padding: '20px 24px',
      marginBottom: '20px',
      boxShadow: 'var(--shadow-md)',
      position: 'relative',
    }}>
      {/* Top Header: Title, Scope Switcher, Freshness Pill */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '14px',
        marginBottom: '18px',
        paddingBottom: '16px',
        borderBottom: '1px solid var(--border-subtle)',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '28px',
              height: '28px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(37, 99, 235, 0.12)',
              color: 'var(--accent-primary)',
            }}>
              <Building2 size={16} />
            </span>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-main)', margin: 0 }}>
              Central Restaurant Operations & Real-Time KPIs
            </h2>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '4px 0 0 36px' }}>
            Unified multi-floor monitoring, canonical table occupancy, and fine-tuned YOLO26 diner tracking.
          </p>
        </div>

        {/* Scope Controls & Freshness Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* Live vs Shift Scope Selector */}
          <div style={{
            display: 'flex',
            background: '#f1f5f9',
            padding: '3px',
            borderRadius: 'var(--radius-md)',
            gap: '2px',
          }}>
            <button
              onClick={() => onScopeChange('LIVE_ACTIVE_SOURCES')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 12px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: scope === 'LIVE_ACTIVE_SOURCES' ? '#ffffff' : 'transparent',
                color: scope === 'LIVE_ACTIVE_SOURCES' ? 'var(--accent-primary)' : 'var(--text-muted)',
                fontWeight: scope === 'LIVE_ACTIVE_SOURCES' ? 700 : 500,
                fontSize: '0.74rem',
                cursor: 'pointer',
                boxShadow: scope === 'LIVE_ACTIVE_SOURCES' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}
            >
              <Radio size={12} color={scope === 'LIVE_ACTIVE_SOURCES' ? '#10b981' : undefined} />
              <span>Live Sources</span>
            </button>

            <button
              onClick={() => onScopeChange('HISTORICAL_SHIFT')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 12px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: scope === 'HISTORICAL_SHIFT' ? '#ffffff' : 'transparent',
                color: scope === 'HISTORICAL_SHIFT' ? 'var(--accent-primary)' : 'var(--text-muted)',
                fontWeight: scope === 'HISTORICAL_SHIFT' ? 700 : 500,
                fontSize: '0.74rem',
                cursor: 'pointer',
                boxShadow: scope === 'HISTORICAL_SHIFT' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}
            >
              <History size={12} />
              <span>Shift History</span>
            </button>

            <button
              onClick={() => onScopeChange('COMBINED')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 12px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: scope === 'COMBINED' ? '#ffffff' : 'transparent',
                color: scope === 'COMBINED' ? 'var(--accent-primary)' : 'var(--text-muted)',
                fontWeight: scope === 'COMBINED' ? 700 : 500,
                fontSize: '0.74rem',
                cursor: 'pointer',
                boxShadow: scope === 'COMBINED' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}
            >
              <Layers size={12} />
              <span>Combined</span>
            </button>
          </div>

          {/* Freshness Badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '5px 10px',
            borderRadius: 'var(--radius-full)',
            background: '#f8fafc',
            border: '1px solid var(--border-subtle)',
            fontSize: '0.72rem',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
          }}>
            <span style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: central.coverage_health === 'ALL_HEALTHY' ? '#10b981' : '#f59e0b',
              boxShadow: '0 0 6px rgba(16, 185, 129, 0.6)',
              animation: 'pulse 2s infinite',
            }} />
            <span>Sync: {freshnessSeconds}s ago</span>
          </div>
        </div>
      </div>

      {/* Partial Coverage / Health Warning Banner */}
      {central.coverage_warning && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '10px 14px',
          borderRadius: 'var(--radius-md)',
          background: central.coverage_health === 'NO_SOURCES' ? '#fef2f2' : '#fffbeb',
          border: central.coverage_health === 'NO_SOURCES' ? '1px solid #fecaca' : '1px solid #fde68a',
          color: central.coverage_health === 'NO_SOURCES' ? '#b91c1c' : '#b45309',
          fontSize: '0.78rem',
          fontWeight: 600,
          marginBottom: '16px',
        }}>
          <AlertTriangle size={16} />
          <span>{central.coverage_warning}</span>
        </div>
      )}

      {/* Scope Label Banner */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.72rem',
        color: 'var(--text-muted)',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        marginBottom: '12px',
      }}>
        <span>
          {isHistorical 
            ? '📊 Historical Shift Aggregate (Preserved independently of camera connections)' 
            : isCombined
            ? '⚡ Combined Active Feeds & Shift Totals'
            : '🟢 Currently Active Tracking Sources (Live Vision Scope)'}
        </span>
        <span>Canonical ID Deduplication Enforced</span>
      </div>

      {/* 6 Top Central Metric Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
        gap: '14px',
      }}>
        {/* Card 1: Monitored Floors & Sources */}
        <div style={{
          padding: '14px 16px',
          background: '#f8fafc',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              Coverage Scope
            </span>
            <ShieldCheck size={14} color="var(--accent-primary)" />
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-main)' }}>
            {central.total_monitored_floors} <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)' }}>Floors</span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            {central.total_active_sources} Active Tracking Feeds
          </div>
        </div>

        {/* Card 2: Central Table Occupancy Rate */}
        <div style={{
          padding: '14px 16px',
          background: '#f8fafc',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              Live Occupancy
            </span>
            <Activity size={14} color="#10b981" />
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 800, color: central.central_occupancy_rate_percent != null ? 'var(--text-main)' : '#94a3b8' }}>
            {central.central_occupancy_rate_percent != null ? `${central.central_occupancy_rate_percent}%` : 'Unavailable'}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            {central.total_occupied_tables} of {central.total_canonical_tables} Tables
          </div>
        </div>

        {/* Card 3: Tracked Diners (Patrons) */}
        <div style={{
          padding: '14px 16px',
          background: '#f8fafc',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              Tracked Diners
            </span>
            <Users size={14} color="var(--accent-primary)" />
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 800, color: central.total_detected_diners != null ? 'var(--accent-primary)' : '#94a3b8' }}>
            {central.total_detected_diners != null ? `${central.total_detected_diners}` : '--'}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            YOLO26 Table Association
          </div>
        </div>

        {/* Card 4: First Response Pace */}
        <div style={{
          padding: '14px 16px',
          background: '#f8fafc',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              Avg Attendance
            </span>
            <Clock size={14} color="#8b5cf6" />
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-main)' }}>
            {formatSeconds(isHistorical ? shiftHistory.historical_avg_response_sec : central.weighted_avg_response_time_sec)}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#10b981', marginTop: '4px' }}>
            Target: &le; 3m 00s
          </div>
        </div>

        {/* Card 5: Food Delivery Pace */}
        <div style={{
          padding: '14px 16px',
          background: '#f8fafc',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              Avg Food Delivery
            </span>
            <UtensilsCrossed size={14} color="#f59e0b" />
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-main)' }}>
            {formatSeconds(isHistorical ? shiftHistory.historical_avg_delivery_sec : central.weighted_avg_food_delivery_sec)}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#10b981', marginTop: '4px' }}>
            Target: &le; 15m 00s
          </div>
        </div>

        {/* Card 6: Active Alerts / Shift Turnover */}
        <div style={{
          padding: '14px 16px',
          background: isHistorical ? '#f8fafc' : central.total_active_alerts > 0 ? '#fffbeb' : '#f8fafc',
          borderRadius: 'var(--radius-lg)',
          border: isHistorical ? '1px solid var(--border-subtle)' : central.total_active_alerts > 0 ? '1px solid #fde68a' : '1px solid var(--border-subtle)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              {isHistorical ? 'Turnover Rate' : 'Active Alerts'}
            </span>
            {isHistorical ? (
              <CheckCircle2 size={14} color="#10b981" />
            ) : (
              <AlertTriangle size={14} color={central.critical_alerts_count > 0 ? '#ef4444' : '#f59e0b'} />
            )}
          </div>
          <div style={{
            fontSize: '1.35rem',
            fontWeight: 800,
            color: isHistorical ? 'var(--text-main)' : central.critical_alerts_count > 0 ? '#dc2626' : central.warning_alerts_count > 0 ? '#d97706' : '#10b981',
          }}>
            {isHistorical 
              ? `${shiftHistory.turnover_rate}x`
              : `${central.total_active_alerts} Alerts`}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            {isHistorical
              ? `${shiftHistory.completed_sessions} Completed Sessions`
              : `${central.critical_alerts_count} Critical, ${central.warning_alerts_count} Warning`}
          </div>
        </div>
      </div>
    </div>
  );
};
export default CentralKPIBanner;
