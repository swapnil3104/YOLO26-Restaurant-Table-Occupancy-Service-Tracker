import React, { useState, useEffect } from 'react';
import { Table, Alert, DashboardKPIs, TableStatus } from './types';
import { 
  Users, 
  Clock, 
  AlertTriangle, 
  Utensils, 
  Camera, 
  Activity, 
  RefreshCw, 
  CheckCircle2, 
  ShieldCheck, 
  Layers 
} from 'lucide-react';

const INITIAL_TABLES: Table[] = [
  {
    id: 'tbl-1',
    code: 'T01',
    capacity: 4,
    section: 'Main Dining',
    status: 'OCCUPIED',
    customerCount: 3,
    lastStateChangeAt: '5m ago',
    assignedWaiter: 'Carlos M.',
    timeSinceLastAttendanceSec: 320,
  },
  {
    id: 'tbl-2',
    code: 'T02',
    capacity: 2,
    section: 'Main Dining',
    status: 'ATTENDED',
    customerCount: 2,
    lastStateChangeAt: '12m ago',
    assignedWaiter: 'Sarah K.',
    timeSinceLastAttendanceSec: 120,
    timeSinceFoodDeliverySec: 680,
  },
  {
    id: 'tbl-3',
    code: 'T03',
    capacity: 6,
    section: 'Patio Terrace',
    status: 'FOOD_DELIVERED',
    customerCount: 5,
    lastStateChangeAt: '24m ago',
    assignedWaiter: 'Carlos M.',
    timeSinceFoodDeliverySec: 240,
  },
  {
    id: 'tbl-4',
    code: 'T04',
    capacity: 4,
    section: 'Patio Terrace',
    status: 'VACANT',
    customerCount: 0,
    lastStateChangeAt: '45m ago',
  },
  {
    id: 'tbl-5',
    code: 'T05',
    capacity: 4,
    section: 'Window Booth',
    status: 'CLEANING_REQUIRED',
    customerCount: 0,
    lastStateChangeAt: '3m ago',
    assignedWaiter: 'Sarah K.',
  },
  {
    id: 'tbl-6',
    code: 'T06',
    capacity: 8,
    section: 'Private Lounge',
    status: 'VACANT',
    customerCount: 0,
    lastStateChangeAt: '1h ago',
  },
];

const INITIAL_ALERTS: Alert[] = [
  {
    id: 'alt-1',
    tableCode: 'T01',
    type: 'ATTENDANCE_OVERDUE',
    severity: 'WARNING',
    message: 'Table T01 seated 5m ago with no recorded waiter greeting.',
    triggeredAt: '2m ago',
    isAcknowledged: false,
  },
];

export const App: React.FC = () => {
  const [tables, setTables] = useState<Table[]>(INITIAL_TABLES);
  const [alerts, setAlerts] = useState<Alert[]>(INITIAL_ALERTS);
  const [filterSection, setFilterSection] = useState<string>('ALL');
  const [selectedTable, setSelectedTable] = useState<Table | null>(tables[0]);

  const kpis: DashboardKPIs = {
    totalTables: tables.length,
    occupiedTables: tables.filter(t => t.status !== 'VACANT' && t.status !== 'CLEANING_REQUIRED').length,
    activeAlerts: alerts.filter(a => !a.isAcknowledged).length,
    avgResponseTimeMin: 3.4,
    avgDeliveryTimeMin: 18.2,
    cameraStatus: 'HEALTHY',
  };

  const getStatusBadgeClass = (status: TableStatus) => {
    switch (status) {
      case 'VACANT': return 'badge-vacant';
      case 'OCCUPIED': return 'badge-occupied';
      case 'ATTENDED': return 'badge-attended';
      case 'FOOD_DELIVERED': return 'badge-food';
      case 'CLEANING_REQUIRED': return 'badge-cleaning';
      default: return 'badge-occupied';
    }
  };

  const handleConfirmAttendance = (code: string) => {
    setTables(prev => prev.map(t => {
      if (t.code === code) {
        return { ...t, status: 'ATTENDED', timeSinceLastAttendanceSec: 0, lastStateChangeAt: 'Just now' };
      }
      return t;
    }));
    setAlerts(prev => prev.filter(a => a.tableCode !== code));
  };

  const filteredTables = filterSection === 'ALL' 
    ? tables 
    : tables.filter(t => t.section === filterSection);

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px' }}>
      {/* Top Header */}
      <header style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        marginBottom: '28px',
        paddingBottom: '20px',
        borderBottom: '1px solid var(--border-subtle)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '12px',
            background: 'var(--accent-gradient)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 20px var(--accent-glow)'
          }}>
            <Utensils size={22} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
              SmartServe <span style={{ color: 'var(--accent-primary)' }}>AI</span>
            </h1>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Real-Time Table Occupancy & Service Velocity Tracker
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 14px' }}>
            <div className="live-indicator" />
            <Camera size={16} color="var(--text-muted)" />
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>CAM-01 (1080p @ 5fps)</span>
          </div>

          <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 14px' }}>
            <Activity size={16} color="#34d399" />
            <span style={{ fontSize: '0.8rem', color: '#34d399', fontWeight: 600 }}>API Connected</span>
          </div>
        </div>
      </header>

      {/* KPI Cards */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', 
        gap: '16px', 
        marginBottom: '28px' 
      }}>
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>OCCUPANCY RATE</span>
            <Users size={18} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800 }}>
            {kpis.occupiedTables} <span style={{ fontSize: '1rem', color: 'var(--text-dim)', fontWeight: 500 }}>/ {kpis.totalTables} tables</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#34d399', marginTop: '6px' }}>
            ● {Math.round((kpis.occupiedTables / kpis.totalTables) * 100)}% active floor capacity
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>AVG FIRST ATTENDANCE</span>
            <Clock size={18} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800 }}>
            {kpis.avgResponseTimeMin} <span style={{ fontSize: '1rem', color: 'var(--text-dim)', fontWeight: 500 }}>min</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#34d399', marginTop: '6px' }}>
            Target: &lt; 5.0 min (On track)
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>AVG FOOD SERVING TIME</span>
            <Utensils size={18} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800 }}>
            {kpis.avgDeliveryTimeMin} <span style={{ fontSize: '1rem', color: 'var(--text-dim)', fontWeight: 500 }}>min</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#38bdf8', marginTop: '6px' }}>
            Target: &lt; 20.0 min (On track)
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>SERVICE ALERTS</span>
            <AlertTriangle size={18} color={kpis.activeAlerts > 0 ? '#f87171' : 'var(--text-muted)'} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: kpis.activeAlerts > 0 ? '#f87171' : 'inherit' }}>
            {kpis.activeAlerts}
          </div>
          <div style={{ fontSize: '0.75rem', color: kpis.activeAlerts > 0 ? '#f87171' : '#34d399', marginTop: '6px' }}>
            {kpis.activeAlerts > 0 ? 'Action required on overdue tables' : 'All tables within thresholds'}
          </div>
        </div>
      </div>

      {/* Main Floor Grid & Details */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
        {/* Table Floor Grid */}
        <section>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={18} color="var(--accent-primary)" />
              <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Live Floor Layout</h2>
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              {['ALL', 'Main Dining', 'Patio Terrace', 'Window Booth'].map((sec) => (
                <button
                  key={sec}
                  onClick={() => setFilterSection(sec)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    backgroundColor: filterSection === sec ? 'var(--accent-primary)' : 'rgba(255,255,255,0.05)',
                    color: filterSection === sec ? '#fff' : 'var(--text-muted)',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {sec}
                </button>
              ))}
            </div>
          </div>

          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', 
            gap: '16px' 
          }}>
            {filteredTables.map((tbl) => {
              const isSelected = selectedTable?.code === tbl.code;
              const hasAlert = alerts.some(a => a.tableCode === tbl.code);

              return (
                <div
                  key={tbl.code}
                  className="glass-panel"
                  onClick={() => setSelectedTable(tbl)}
                  style={{
                    padding: '18px',
                    cursor: 'pointer',
                    borderColor: hasAlert 
                      ? 'rgba(239, 68, 68, 0.5)' 
                      : isSelected ? 'var(--accent-primary)' : 'var(--border-subtle)',
                    background: isSelected ? 'var(--bg-card-hover)' : 'var(--bg-card)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                    <div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 800 }}>{tbl.code}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{tbl.section} • Cap: {tbl.capacity}</div>
                    </div>
                    <span className={`badge ${getStatusBadgeClass(tbl.status)}`}>
                      {tbl.status.replace('_', ' ')}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.82rem', marginTop: '14px', paddingTop: '12px', borderTop: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)' }}>
                      <Users size={14} />
                      <span>{tbl.customerCount} Guests</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-dim)', fontSize: '0.78rem' }}>
                      <Clock size={13} />
                      <span>{tbl.lastStateChangeAt}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Selected Table Inspection Sidebar */}
        <aside>
          <div className="glass-panel" style={{ padding: '22px' }}>
            {selectedTable ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Table {selectedTable.code} Details</h3>
                  <span className={`badge ${getStatusBadgeClass(selectedTable.status)}`}>
                    {selectedTable.status}
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '0.85rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Section</span>
                    <span style={{ fontWeight: 600 }}>{selectedTable.section}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Estimated Guests</span>
                    <span style={{ fontWeight: 600 }}>{selectedTable.customerCount} persons</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Assigned Waiter</span>
                    <span style={{ fontWeight: 600 }}>{selectedTable.assignedWaiter || 'Unassigned'}</span>
                  </div>
                  {selectedTable.timeSinceLastAttendanceSec !== undefined && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Time Since Attendance</span>
                      <span style={{ fontWeight: 600, color: selectedTable.timeSinceLastAttendanceSec > 300 ? '#f87171' : 'inherit' }}>
                        {Math.floor(selectedTable.timeSinceLastAttendanceSec / 60)}m {selectedTable.timeSinceLastAttendanceSec % 60}s
                      </span>
                    </div>
                  )}
                </div>

                {/* Manual Operations Confirmation Gates */}
                <div style={{ marginTop: '24px' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '12px', textTransform: 'uppercase' }}>
                    Staff Operational Actions
                  </div>
                  <button
                    onClick={() => handleConfirmAttendance(selectedTable.code)}
                    style={{
                      width: '100%',
                      padding: '10px 16px',
                      borderRadius: '8px',
                      background: 'var(--accent-primary)',
                      color: '#fff',
                      fontWeight: 600,
                      fontSize: '0.85rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      marginBottom: '10px',
                      boxShadow: '0 4px 14px rgba(99, 102, 241, 0.4)'
                    }}
                  >
                    <CheckCircle2 size={16} />
                    Confirm Waiter Attendance
                  </button>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '8px' }}>
                    <ShieldCheck size={14} color="#34d399" />
                    <span>Logged as verified event with employee audit trail</span>
                  </div>
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--text-dim)', textAlign: 'center', padding: '40px 0' }}>
                Select a table to inspect occupancy timeline and actions
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
};

export default App;
