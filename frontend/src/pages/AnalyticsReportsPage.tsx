import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Clock, 
  TrendingUp, 
  AlertTriangle, 
  FileSpreadsheet, 
  RefreshCw, 
  ShieldCheck, 
  ShieldAlert, 
  ArrowUpRight, 
  UtensilsCrossed,
  X
} from 'lucide-react';
import { 
  Table, 
  StaffUser, 
  AnalyticsSummary, 
  AnalyticsBreakdown, 
  AnalyticsFilterParams
} from '../types';
import { 
  fetchAnalyticsSummary, 
  fetchAnalyticsBreakdown, 
  getExportCsvUrl 
} from '../services/api';

interface AnalyticsReportsPageProps {
  tables: Table[];
  currentActor: StaffUser;
  onRefresh?: () => void;
}

type TimePreset = 'today' | '24h' | '7d' | '30d' | 'all';
type ReportTab = 'tables' | 'waiters' | 'hourly';

export const AnalyticsReportsPage: React.FC<AnalyticsReportsPageProps> = ({
  tables,
  currentActor,
  onRefresh: parentRefresh,
}) => {
  // Filter States
  const [timePreset, setTimePreset] = useState<TimePreset>('today');
  const [selectedSection, setSelectedSection] = useState<string>('all');
  const [selectedTable, setSelectedTable] = useState<string>('all');
  const [selectedWaiter, setSelectedWaiter] = useState<string>('all');
  const [anonymizeStaff, setAnonymizeStaff] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<ReportTab>('tables');

  // Data States
  const [loading, setLoading] = useState<boolean>(true);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [breakdown, setBreakdown] = useState<AnalyticsBreakdown | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showExportModal, setShowExportModal] = useState<boolean>(false);

  // Extract distinct sections from tables
  const sections = useMemo(() => {
    const set = new Set<string>();
    tables.forEach(t => {
      if (t.section) set.add(t.section);
    });
    return Array.from(set);
  }, [tables]);

  // Compute start/end timestamps based on timePreset
  const filterTimes = useMemo(() => {
    const now = new Date();
    let startTime: Date | undefined;
    let endTime: Date | undefined = now;

    if (timePreset === 'today') {
      startTime = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
    } else if (timePreset === '24h') {
      startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    } else if (timePreset === '7d') {
      startTime = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    } else if (timePreset === '30d') {
      startTime = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    } else {
      startTime = undefined;
      endTime = undefined;
    }

    return {
      start_time: startTime ? startTime.toISOString() : undefined,
      end_time: endTime ? endTime.toISOString() : undefined,
    };
  }, [timePreset]);

  // Construct active filter parameters
  const currentFilters = useMemo<AnalyticsFilterParams>(() => {
    return {
      ...filterTimes,
      section: selectedSection !== 'all' ? selectedSection : undefined,
      table_id: selectedTable !== 'all' ? selectedTable : undefined,
      waiter_id: selectedWaiter !== 'all' ? selectedWaiter : undefined,
      include_estimates: false,
      anonymize: anonymizeStaff,
    };
  }, [filterTimes, selectedSection, selectedTable, selectedWaiter, anonymizeStaff]);

  // Load analytics and breakdowns
  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumData, brkData] = await Promise.all([
        fetchAnalyticsSummary(currentFilters),
        fetchAnalyticsBreakdown(currentFilters),
      ]);
      setSummary(sumData);
      setBreakdown(brkData);
    } catch (err: any) {
      console.error('Failed to load analytics reports:', err);
      setError(err.message || 'Error loading analytics reports');
    } finally {
      setLoading(false);
    }
  }, [currentFilters]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  const formatSeconds = (sec: number | null | undefined): string => {
    if (sec === null || sec === undefined) return 'N/A';
    const m = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    if (m === 0) return `${s}s`;
    return `${m}m ${s > 0 ? `${s}s` : ''}`.trim();
  };

  const isManagerOrAdmin = currentActor.role === 'MANAGER' || currentActor.role === 'ADMIN';

  return (
    <div className="page-wrapper" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. Header & Actions Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em', margin: 0 }}>
            Operational Analytics & Reports
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.84rem', margin: '4px 0 0 0' }}>
            Service speed milestones, table turnover performance, staff efficiency, and operational exports.
          </p>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Privacy Masking Toggle */}
          <button
            onClick={() => setAnonymizeStaff(!anonymizeStaff)}
            title="Toggle staff name privacy masking for external auditing"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: 'var(--radius-md)',
              background: anonymizeStaff ? 'var(--status-vacant-bg)' : '#fef2f2',
              border: `1px solid ${anonymizeStaff ? 'var(--status-vacant-border)' : '#fecaca'}`,
              color: anonymizeStaff ? 'var(--status-vacant)' : '#b91c1c',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            {anonymizeStaff ? <ShieldCheck size={16} /> : <ShieldAlert size={16} />}
            <span>{anonymizeStaff ? 'Staff Privacy: ON' : 'Staff Privacy: OFF'}</span>
          </button>

          {/* Export CSV Hub */}
          <button
            onClick={() => setShowExportModal(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--accent-primary)',
              border: 'none',
              color: '#ffffff',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <FileSpreadsheet size={16} />
            <span>Export CSV</span>
          </button>

          {/* Refresh Action */}
          <button
            onClick={() => {
              loadAnalytics();
              if (parentRefresh) parentRefresh();
            }}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 12px',
              borderRadius: 'var(--radius-md)',
              background: '#ffffff',
              border: '1px solid var(--border-medium)',
              color: 'var(--text-muted)',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <RefreshCw size={15} style={{ transform: loading ? 'rotate(180deg)' : 'none', transition: 'transform 0.4s' }} />
          </button>
        </div>
      </div>

      {/* 2. Filter Bar */}
      <div className="white-card" style={{
        padding: '14px 18px',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '14px',
      }}>
        {/* Time Presets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)', fontWeight: 700, marginRight: '4px' }}>
            RANGE:
          </span>
          {(['today', '24h', '7d', '30d', 'all'] as TimePreset[]).map((preset) => {
            const labels: Record<TimePreset, string> = {
              today: 'Today',
              '24h': 'Last 24h',
              '7d': 'Last 7 Days',
              '30d': 'Last 30 Days',
              all: 'All Time',
            };
            const active = timePreset === preset;
            return (
              <button
                key={preset}
                onClick={() => setTimePreset(preset)}
                style={{
                  padding: '5px 12px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: active ? 'var(--accent-primary)' : '#f8fafc',
                  border: `1px solid ${active ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
                  color: active ? '#ffffff' : 'var(--text-muted)',
                  boxShadow: active ? 'var(--shadow-sm)' : 'none',
                }}
              >
                {labels[preset]}
              </button>
            );
          })}
        </div>

        {/* Dropdown Selectors */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {/* Section Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '0.76rem', color: 'var(--text-dim)', fontWeight: 600 }}>SECTION:</span>
            <select
              value={selectedSection}
              onChange={(e) => setSelectedSection(e.target.value)}
              style={{ fontSize: '0.8rem' }}
            >
              <option value="all">All Sections</option>
              {sections.map((sec) => (
                <option key={sec} value={sec}>{sec}</option>
              ))}
            </select>
          </div>

          {/* Table Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '0.76rem', color: 'var(--text-dim)', fontWeight: 600 }}>TABLE:</span>
            <select
              value={selectedTable}
              onChange={(e) => setSelectedTable(e.target.value)}
              style={{ fontSize: '0.8rem' }}
            >
              <option value="all">All Tables</option>
              {tables.map((t) => (
                <option key={t.id} value={t.id}>{t.code}</option>
              ))}
            </select>
          </div>

          {/* Waiter Filter */}
          {isManagerOrAdmin && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '0.76rem', color: 'var(--text-dim)', fontWeight: 600 }}>STAFF:</span>
              <select
                value={selectedWaiter}
                onChange={(e) => setSelectedWaiter(e.target.value)}
                style={{ fontSize: '0.8rem' }}
              >
                <option value="all">All Staff</option>
                {breakdown?.waiters.map((w) => (
                  <option key={w.waiter_id} value={w.waiter_id}>{w.staff_name}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Error Alert Banner */}
      {error && (
        <div style={{
          background: '#fef2f2',
          border: '1px solid #fecaca',
          borderRadius: 'var(--radius-md)',
          padding: '12px 16px',
          color: '#b91c1c',
          fontSize: '0.85rem',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* 3. Operational Performance KPI Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
        gap: '16px',
      }}>
        {/* First Response Time */}
        <div className="white-card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>Waiter Response Time</span>
            <Clock size={16} color="var(--accent-primary)" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)' }}>
              {summary ? formatSeconds(summary.kpis.median_first_attendance_sec) : '--'}
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>(Median)</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <span>Avg: <strong>{summary ? formatSeconds(summary.kpis.average_first_attendance_sec) : '--'}</strong></span>
            <span style={{ background: '#ecfdf5', color: '#047857', padding: '1px 6px', borderRadius: '4px', fontWeight: 600 }}>
              Target &lt; 3m
            </span>
          </div>
        </div>

        {/* Food Delivery Time */}
        <div className="white-card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>Kitchen Food Delivery</span>
            <UtensilsCrossed size={16} color="var(--status-food)" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)' }}>
              {summary ? formatSeconds(summary.kpis.median_food_delivery_sec) : '--'}
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>(Median)</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <span>Avg: <strong>{summary ? formatSeconds(summary.kpis.average_food_delivery_sec) : '--'}</strong></span>
            <span style={{ background: '#f5f3ff', color: '#6d28d9', padding: '1px 6px', borderRadius: '4px', fontWeight: 600 }}>
              Target &lt; 15m
            </span>
          </div>
        </div>

        {/* Table Utilization */}
        <div className="white-card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>Floor Utilization</span>
            <TrendingUp size={16} color="var(--status-vacant)" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)' }}>
              {summary ? `${summary.kpis.table_utilization_percent.toFixed(1)}%` : '--'}
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>seated</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <span>Turnover: <strong>{summary ? `${summary.kpis.table_turnover_rate} / hr` : '--'}</strong></span>
            <span>Avg: {summary ? formatSeconds(summary.kpis.average_occupancy_duration_sec) : '--'}</span>
          </div>
        </div>

        {/* Service Delay Rate */}
        <div className="white-card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>Service Delay Rate</span>
            <AlertTriangle size={16} color={summary && summary.kpis.delay_rate_percent > 15 ? 'var(--status-critical)' : 'var(--status-warning)'} />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: summary && summary.kpis.delay_rate_percent > 15 ? 'var(--status-critical)' : 'var(--text-main)' }}>
              {summary ? `${summary.kpis.delay_rate_percent.toFixed(1)}%` : '--'}
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>breaches</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <span>Active Alerts: <strong style={{ color: 'var(--status-warning)' }}>{summary ? summary.alerts.active_alerts : 0}</strong></span>
            <span>Critical: <strong style={{ color: 'var(--status-critical)' }}>{summary ? summary.alerts.critical_alerts : 0}</strong></span>
          </div>
        </div>
      </div>

      {/* 4. Detailed Breakdown Tabs & Table Container */}
      <div className="white-card" style={{ overflow: 'hidden' }}>
        {/* Tab Headers */}
        <div style={{
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          background: '#f8fafc',
        }}>
          {[
            { id: 'tables' as ReportTab, label: 'Table & Zone Turnover', count: breakdown?.tables.length },
            { id: 'waiters' as ReportTab, label: 'Staff Efficiency & Delays', count: breakdown?.waiters.length },
            { id: 'hourly' as ReportTab, label: 'Hourly Dining Traffic Heatmap' },
          ].map((tab) => {
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: '14px 18px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: active ? '2px solid var(--accent-primary)' : '2px solid transparent',
                  color: active ? 'var(--accent-primary)' : 'var(--text-muted)',
                  fontSize: '0.85rem',
                  fontWeight: active ? 700 : 500,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span style={{
                    fontSize: '0.7rem',
                    background: active ? 'var(--accent-light)' : '#e2e8f0',
                    color: active ? 'var(--accent-primary)' : 'var(--text-muted)',
                    padding: '1px 6px',
                    borderRadius: '10px',
                    fontWeight: 700,
                  }}>
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Tab Content Area */}
        <div style={{ padding: '20px' }}>
          {/* TAB 1: Table Performance Table */}
          {activeTab === 'tables' && (
            <div>
              {breakdown && breakdown.tables.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)', fontSize: '0.72rem', textTransform: 'uppercase' }}>
                        <th style={{ padding: '10px 12px' }}>Table Code</th>
                        <th style={{ padding: '10px 12px' }}>Section</th>
                        <th style={{ padding: '10px 12px' }}>Capacity</th>
                        <th style={{ padding: '10px 12px' }}>Sessions</th>
                        <th style={{ padding: '10px 12px' }}>Completed</th>
                        <th style={{ padding: '10px 12px' }}>Median Occ.</th>
                        <th style={{ padding: '10px 12px' }}>Average Occ.</th>
                        <th style={{ padding: '10px 12px' }}>Turnover</th>
                        <th style={{ padding: '10px 12px' }}>Utilization</th>
                        <th style={{ padding: '10px 12px' }}>Delays</th>
                      </tr>
                    </thead>
                    <tbody>
                      {breakdown.tables.map((t, idx) => (
                        <tr key={t.table_id} style={{ borderBottom: '1px solid #f1f5f9', background: idx % 2 === 0 ? '#ffffff' : '#fafafa' }}>
                          <td style={{ padding: '12px', fontWeight: 700, color: 'var(--text-main)' }}>
                            {t.table_code}
                          </td>
                          <td style={{ padding: '12px', color: 'var(--text-muted)' }}>
                            {t.section}
                          </td>
                          <td style={{ padding: '12px', color: 'var(--text-dim)' }}>
                            {t.capacity} seats
                          </td>
                          <td style={{ padding: '12px', color: 'var(--text-main)', fontWeight: 600 }}>
                            {t.sessions_count}
                          </td>
                          <td style={{ padding: '12px', color: 'var(--status-food)', fontWeight: 600 }}>
                            {t.completed_sessions_count}
                          </td>
                          <td style={{ padding: '12px', color: 'var(--text-main)' }}>
                            {formatSeconds(t.median_occupancy_sec)}
                          </td>
                          <td style={{ padding: '12px', color: 'var(--text-muted)' }}>
                            {formatSeconds(t.average_occupancy_sec)}
                          </td>
                          <td style={{ padding: '12px', color: 'var(--status-vacant)', fontWeight: 600 }}>
                            {t.turnover_rate} turns
                          </td>
                          <td style={{ padding: '12px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <div style={{
                                width: '60px',
                                height: '6px',
                                background: '#e2e8f0',
                                borderRadius: '3px',
                                overflow: 'hidden',
                              }}>
                                <div style={{
                                  width: `${Math.min(100, t.utilization_percent)}%`,
                                  height: '100%',
                                  background: t.utilization_percent > 80 ? '#059669' : '#2563eb',
                                }} />
                              </div>
                              <span style={{ fontSize: '0.78rem', color: 'var(--text-main)', fontWeight: 500 }}>
                                {t.utilization_percent.toFixed(1)}%
                              </span>
                            </div>
                          </td>
                          <td style={{ padding: '12px' }}>
                            {t.delays_count > 0 ? (
                              <span style={{
                                background: '#fef2f2',
                                color: '#b91c1c',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                fontWeight: 700,
                              }}>
                                {t.delays_count}
                              </span>
                            ) : (
                              <span style={{ color: 'var(--text-dim)' }}>0</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-dim)' }}>
                  No table performance data available for this range.
                </div>
              )}
            </div>
          )}

          {/* TAB 2: Staff / Waiter Performance Table */}
          {activeTab === 'waiters' && (
            <div>
              {breakdown && breakdown.waiters.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)', fontSize: '0.72rem', textTransform: 'uppercase' }}>
                        <th style={{ padding: '10px 12px' }}>Staff ID</th>
                        <th style={{ padding: '10px 12px' }}>Staff Name</th>
                        <th style={{ padding: '10px 12px' }}>Tables Handled</th>
                        <th style={{ padding: '10px 12px' }}>Median Response</th>
                        <th style={{ padding: '10px 12px' }}>Average Response</th>
                        <th style={{ padding: '10px 12px' }}>On-Time Rate %</th>
                        <th style={{ padding: '10px 12px' }}>Service Delays</th>
                      </tr>
                    </thead>
                    <tbody>
                      {breakdown.waiters.map((w, idx) => (
                        <tr key={w.waiter_id} style={{ borderBottom: '1px solid #f1f5f9', background: idx % 2 === 0 ? '#ffffff' : '#fafafa' }}>
                          <td style={{ padding: '12px', fontFamily: 'monospace', color: 'var(--accent-primary)', fontWeight: 600 }}>
                            {w.waiter_id}
                          </td>
                          <td style={{ padding: '12px', fontWeight: 700, color: 'var(--text-main)' }}>
                            {w.staff_name}
                          </td>
                          <td style={{ padding: '12px', color: 'var(--text-main)', fontWeight: 600 }}>
                            {w.tables_handled}
                          </td>
                          <td style={{ padding: '12px', color: 'var(--status-vacant)', fontWeight: 600 }}>
                            {formatSeconds(w.median_response_sec)}
                          </td>
                          <td style={{ padding: '12px', color: 'var(--text-muted)' }}>
                            {formatSeconds(w.average_response_sec)}
                          </td>
                          <td style={{ padding: '12px' }}>
                            <span style={{
                              background: w.on_time_attendance_rate >= 90 ? '#ecfdf5' : '#fef2f2',
                              color: w.on_time_attendance_rate >= 90 ? '#047857' : '#b91c1c',
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontWeight: 700,
                            }}>
                              {w.on_time_attendance_rate.toFixed(1)}%
                            </span>
                          </td>
                          <td style={{ padding: '12px' }}>
                            {w.delays_count > 0 ? (
                              <span style={{ color: '#b91c1c', fontWeight: 700 }}>{w.delays_count}</span>
                            ) : (
                              <span style={{ color: 'var(--text-dim)' }}>0</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-dim)' }}>
                  No staff activity records found for this query.
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Hourly Traffic Heatmap */}
          {activeTab === 'hourly' && (
            <div>
              <div style={{ marginBottom: '16px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Distribution of dining room table occupancy across each hour of the day.
              </div>
              {breakdown && breakdown.hourly ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(24, 1fr)',
                    gap: '4px',
                    height: '140px',
                    alignItems: 'flex-end',
                    padding: '10px 0',
                    borderBottom: '1px solid var(--border-subtle)',
                  }}>
                    {breakdown.hourly.map((h) => {
                      const maxCount = Math.max(...breakdown.hourly.map(item => item.session_count), 1);
                      const heightPct = Math.round((h.session_count / maxCount) * 100);
                      const isPeak = h.session_count > 0 && h.session_count === maxCount;

                      return (
                        <div
                          key={h.hour_of_day}
                          title={`${h.hour_of_day}:00 - ${h.session_count} dining sessions`}
                          style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            height: '100%',
                            justifyContent: 'flex-end',
                          }}
                        >
                          <div style={{
                            width: '100%',
                            height: `${Math.max(6, heightPct)}%`,
                            background: isPeak ? '#dc2626' : h.session_count > 0 ? '#2563eb' : '#e2e8f0',
                            borderRadius: '3px 3px 0 0',
                            transition: 'height 0.3s ease',
                          }} />
                        </div>
                      );
                    })}
                  </div>
                  {/* Hour labels */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: '4px', textAlign: 'center' }}>
                    {breakdown.hourly.map((h) => (
                      <span key={h.hour_of_day} style={{ fontSize: '0.65rem', color: 'var(--text-dim)', fontWeight: 500 }}>
                        {h.hour_of_day}h
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>

      {/* 5. Clean White Export Modal */}
      {showExportModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(15, 23, 42, 0.45)',
          backdropFilter: 'blur(3px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100,
          padding: '20px',
        }}>
          <div className="white-card" style={{
            width: '100%',
            maxWidth: '500px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
            boxShadow: 'var(--shadow-xl)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <FileSpreadsheet size={22} color="var(--accent-primary)" />
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                  Export Service Operational Reports
                </h3>
              </div>
              <button
                onClick={() => setShowExportModal(false)}
                style={{ color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0 }}>
              Download official CSV datasets for spreadsheet reporting, payroll, and dining room audit logs.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <a
                href={getExportCsvUrl('sessions', currentFilters)}
                download
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 16px',
                  borderRadius: 'var(--radius-md)',
                  background: '#f8fafc',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-main)',
                  textDecoration: 'none',
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>Complete Table Sessions Log CSV</div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Session start, waiter greeting, food delivery timestamps, and guest counts.
                  </div>
                </div>
                <ArrowUpRight size={16} color="var(--accent-primary)" />
              </a>

              <a
                href={getExportCsvUrl('summary', currentFilters)}
                download
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 16px',
                  borderRadius: 'var(--radius-md)',
                  background: '#f8fafc',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-main)',
                  textDecoration: 'none',
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>Executive KPI Summary CSV</div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Turnover rates, median response metrics, and capacity utilization.
                  </div>
                </div>
                <ArrowUpRight size={16} color="var(--status-vacant)" />
              </a>

              <a
                href={getExportCsvUrl('waiters', currentFilters)}
                download
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 16px',
                  borderRadius: 'var(--radius-md)',
                  background: '#f8fafc',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-main)',
                  textDecoration: 'none',
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>Staff & Waiter Efficiency CSV</div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Attended tables, on-time rates, and service milestone records.
                  </div>
                </div>
                <ArrowUpRight size={16} color="var(--status-food)" />
              </a>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '6px' }}>
              <button
                onClick={() => setShowExportModal(false)}
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-md)',
                  background: '#f1f5f9',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-muted)',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalyticsReportsPage;
