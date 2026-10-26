import React from 'react';
import { Table } from '../types';
import { Users, Clock, AlertTriangle } from 'lucide-react';

interface FloorPlanMapProps {
  tables: Table[];
  selectedTableId: string | null;
  onSelectTable: (table: Table) => void;
}

export const FloorPlanMap: React.FC<FloorPlanMapProps> = ({
  tables,
  selectedTableId,
  onSelectTable,
}) => {
  // Group tables by section
  const sections = [
    { id: 'Window Section', name: 'Window Section', icon: '🪟' },
    { id: 'Main Dining', name: 'Main Dining Room', icon: '🍽️' },
    { id: 'Lounge', name: 'Lounge & Sofa Area', icon: '🛋️' },
    { id: 'Patio Terrace', name: 'Patio Terrace', icon: '🌿' },
  ];

  // Helper to determine status styling
  const getStatusColor = (status: string, hasAlert: boolean) => {
    if (hasAlert) return { bg: '#fef2f2', border: '#ef4444', text: '#b91c1c', fill: '#fee2e2' };
    switch (status) {
      case 'VACANT':
        return { bg: '#ecfdf5', border: '#10b981', text: '#047857', fill: '#d1fae5' };
      case 'OCCUPIED':
        return { bg: '#eff6ff', border: '#3b82f6', text: '#1d4ed8', fill: '#dbeafe' };
      case 'ATTENDED':
        return { bg: '#f0fdfa', border: '#0d9488', text: '#0f766e', fill: '#ccfbf1' };
      case 'FOOD_DELIVERED':
        return { bg: '#f5f3ff', border: '#8b5cf6', text: '#6d28d9', fill: '#ede9fe' };
      case 'CLEANING_REQUIRED':
        return { bg: '#fdf2f8', border: '#ec4899', text: '#be123c', fill: '#fce7f3' };
      default:
        return { bg: '#f8fafc', border: '#94a3b8', text: '#475569', fill: '#f1f5f9' };
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'VACANT': return 'Ready';
      case 'OCCUPIED': return 'Seated';
      case 'ATTENDED': return 'Ordered';
      case 'FOOD_DELIVERED': return 'Served';
      case 'CLEANING_REQUIRED': return 'Bussing';
      default: return status;
    }
  };

  return (
    <div style={{
      background: '#ffffff',
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--radius-lg)',
      padding: '24px',
      boxShadow: 'var(--shadow-sm)',
    }}>
      {/* Floor Plan Header & Legend */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '20px',
        paddingBottom: '16px',
        borderBottom: '1px solid var(--border-subtle)',
      }}>
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>
            Dining Room Visual Floor Layout
          </h3>
          <p style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
            Click any table to open service controls, seat parties, or page waitstaff.
          </p>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap', fontSize: '0.74rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#10b981' }} />
            <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>Vacant / Ready</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#3b82f6' }} />
            <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>Seated</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#0d9488' }} />
            <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>Attended</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#8b5cf6' }} />
            <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>Served</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ec4899' }} />
            <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>Needs Bussing</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444' }} />
            <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>Alert / Overdue</span>
          </div>
        </div>
      </div>

      {/* Restaurant Zones Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '20px',
      }}>
        {sections.map((sec) => {
          const sectionTables = tables.filter(t => 
            t.section?.toLowerCase().includes(sec.id.toLowerCase()) || 
            (sec.id === 'Main Dining' && (!t.section || t.section === 'Main'))
          );

          return (
            <div
              key={sec.id}
              style={{
                background: '#f8fafc',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '16px',
                position: 'relative',
              }}
            >
              {/* Zone Title */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '14px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '0.84rem', color: 'var(--text-main)' }}>
                  <span>{sec.icon}</span>
                  <span>{sec.name}</span>
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 600 }}>
                  {sectionTables.length} Tables
                </span>
              </div>

              {/* Table Placements Inside Zone */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
                gap: '14px',
                minHeight: '120px',
                alignItems: 'center',
              }}>
                {sectionTables.map((tbl) => {
                  const isSelected = selectedTableId === tbl.id;
                  const colors = getStatusColor(tbl.status, !!tbl.hasActiveAlert);
                  const isRound = tbl.capacity <= 2 || tbl.code.includes('01') || tbl.code.includes('02');

                  return (
                    <button
                      key={tbl.id}
                      onClick={() => onSelectTable(tbl)}
                      style={{
                        position: 'relative',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '14px 10px',
                        background: colors.bg,
                        border: `2px solid ${isSelected ? 'var(--accent-primary)' : colors.border}`,
                        borderRadius: isRound ? '50%' : '14px',
                        width: '100%',
                        aspectRatio: isRound ? '1 / 1' : '1.2 / 1',
                        maxWidth: '140px',
                        margin: '0 auto',
                        boxShadow: isSelected ? '0 0 0 3px rgba(37, 99, 235, 0.25), var(--shadow-md)' : 'var(--shadow-sm)',
                        transform: isSelected ? 'scale(1.04)' : 'none',
                        transition: 'all 0.15s ease',
                        cursor: 'pointer',
                      }}
                      onMouseEnter={(e) => {
                        if (!isSelected) e.currentTarget.style.transform = 'translateY(-2px)';
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) e.currentTarget.style.transform = 'none';
                      }}
                    >
                      {/* Active Alert Dot */}
                      {tbl.hasActiveAlert && (
                        <div style={{
                          position: 'absolute',
                          top: '4px',
                          right: '6px',
                          color: '#dc2626',
                          animation: 'pulseDot 1.5s infinite',
                        }}>
                          <AlertTriangle size={14} />
                        </div>
                      )}

                      {/* Table Code */}
                      <div style={{
                        fontSize: '1rem',
                        fontWeight: 800,
                        fontFamily: 'var(--font-sans)',
                        color: colors.text,
                        lineHeight: 1.1,
                      }}>
                        {tbl.code}
                      </div>

                      {/* Capacity & Seated count */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.68rem',
                        color: colors.text,
                        fontWeight: 600,
                        marginTop: '3px',
                      }}>
                        <Users size={11} />
                        <span>{tbl.customerCount > 0 ? `${tbl.customerCount}/${tbl.capacity}` : `0/${tbl.capacity}`}</span>
                      </div>

                      {/* Status label badge */}
                      <div style={{
                        marginTop: '4px',
                        padding: '1px 6px',
                        borderRadius: '9999px',
                        background: colors.fill,
                        color: colors.text,
                        fontSize: '0.62rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        letterSpacing: '0.02em',
                      }}>
                        {tbl.hasActiveAlert ? 'OVERDUE' : getStatusLabel(tbl.status)}
                      </div>

                      {/* Elapsed Timer if active */}
                      {tbl.status !== 'VACANT' && (
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px',
                          fontSize: '0.62rem',
                          color: 'var(--text-dim)',
                          marginTop: '2px',
                        }}>
                          <Clock size={9} />
                          <span>{tbl.lastStateChangeAt.includes('ago') ? tbl.lastStateChangeAt : 'Active'}</span>
                        </div>
                      )}
                    </button>
                  );
                })}

                {sectionTables.length === 0 && (
                  <div style={{
                    gridColumn: '1 / -1',
                    textAlign: 'center',
                    padding: '20px',
                    fontSize: '0.74rem',
                    color: 'var(--text-dim)',
                  }}>
                    No tables assigned to this zone
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
