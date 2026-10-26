import React from 'react';
import { 
  LayoutDashboard, 
  Camera, 
  BarChart3, 
  ChevronLeft, 
  ChevronRight,
  UtensilsCrossed
} from 'lucide-react';

export type ActivePage = 'dashboard' | 'cameras' | 'analytics';

interface SidebarProps {
  activePage: ActivePage;
  onPageChange: (page: ActivePage) => void;
  activeAlertsCount: number;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activePage,
  onPageChange,
  activeAlertsCount,
  collapsed,
  onToggleCollapse,
}) => {
  const navItems = [
    {
      id: 'dashboard' as ActivePage,
      label: 'Floor Operations',
      icon: LayoutDashboard,
      subtitle: 'Tables, Floor Plan & Service',
      badge: activeAlertsCount > 0 ? activeAlertsCount : undefined,
    },
    {
      id: 'cameras' as ActivePage,
      label: 'Surveillance & Vision',
      icon: Camera,
      subtitle: 'Live CCTV & YOLO Tracking',
    },
    {
      id: 'analytics' as ActivePage,
      label: 'Performance & Reports',
      icon: BarChart3,
      subtitle: 'Turnover, Times & Exports',
    },
  ];

  return (
    <aside style={{
      width: collapsed ? '72px' : '256px',
      background: 'var(--bg-sidebar)',
      borderRight: '1px solid var(--border-subtle)',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      transition: 'width 0.2s ease',
      zIndex: 30,
      flexShrink: 0,
      boxShadow: 'var(--shadow-sm)',
    }}>
      {/* Brand & Navigation */}
      <div>
        {/* Restaurant Brand Header */}
        <div style={{
          padding: '20px 18px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          borderBottom: '1px solid var(--border-subtle)',
        }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '10px',
            background: 'var(--accent-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
            flexShrink: 0,
            boxShadow: '0 2px 4px rgba(37, 99, 235, 0.2)',
          }}>
            <UtensilsCrossed size={19} />
          </div>

          {!collapsed && (
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontSize: '0.98rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
                SmartServe
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 500 }}>
                Restaurant Operations
              </div>
            </div>
          )}
        </div>

        {/* Navigation Links */}
        <div style={{ padding: '16px 12px' }}>
          <div style={{
            padding: '0 8px 10px 8px',
            fontSize: '0.68rem',
            fontWeight: 700,
            color: 'var(--text-dim)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            display: collapsed ? 'none' : 'block',
          }}>
            Main Menu
          </div>

          <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activePage === item.id;

              return (
                <button
                  key={item.id}
                  onClick={() => onPageChange(item.id)}
                  title={collapsed ? item.label : undefined}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: collapsed ? '12px' : '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    background: isActive ? 'var(--accent-light)' : 'transparent',
                    border: isActive ? '1px solid #bfdbfe' : '1px solid transparent',
                    color: isActive ? 'var(--accent-primary)' : 'var(--text-muted)',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    position: 'relative',
                    fontWeight: isActive ? 600 : 500,
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.background = '#f1f5f9';
                      e.currentTarget.style.color = 'var(--text-main)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.background = 'transparent';
                      e.currentTarget.style.color = 'var(--text-muted)';
                    }
                  }}
                >
                  <div style={{
                    color: isActive ? 'var(--accent-primary)' : 'var(--text-muted)',
                    display: 'flex',
                    alignItems: 'center',
                  }}>
                    <Icon size={19} />
                  </div>

                  {!collapsed && (
                    <div style={{ textAlign: 'left', flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.86rem', color: isActive ? 'var(--accent-primary)' : 'var(--text-main)', lineHeight: 1.25 }}>
                        {item.label}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {item.subtitle}
                      </div>
                    </div>
                  )}

                  {item.badge !== undefined && (
                    <span style={{
                      position: collapsed ? 'absolute' : 'static',
                      top: collapsed ? '4px' : 'auto',
                      right: collapsed ? '4px' : 'auto',
                      background: 'var(--status-critical)',
                      color: '#ffffff',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      padding: '2px 7px',
                      borderRadius: '9999px',
                      minWidth: '18px',
                      textAlign: 'center',
                      boxShadow: '0 1px 2px rgba(220, 38, 38, 0.25)',
                    }}>
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Footer controls & collapse */}
      <div style={{
        padding: '14px 16px',
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: collapsed ? 'center' : 'space-between',
        background: '#fafafa',
      }}>
        {!collapsed && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 500 }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#059669' }} />
            <span>Shift in Progress</span>
          </div>
        )}

        <button
          onClick={onToggleCollapse}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            padding: '6px',
            borderRadius: 'var(--radius-sm)',
            background: '#ffffff',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
        </button>
      </div>
    </aside>
  );
};
