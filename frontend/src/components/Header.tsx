import React, { useState } from 'react';
import { 
  RefreshCw, 
  Clock, 
  ChevronDown, 
  Bell, 
  BellOff, 
  UserCheck, 
  Building,
  Sparkles,
  Plus
} from 'lucide-react';
import { StaffUser, TrackingFootageItem } from '../types';
import { DEMO_USERS, getCurrentActor, setCurrentActor } from '../services/api';
import { ConnectionState } from '../hooks/useRealtime';

interface HeaderProps {
  connectionStatus: ConnectionState;
  lastUpdated: Date;
  onRefresh: () => void;
  onActorChange: (actor: StaffUser) => void;
  soundAlertsEnabled?: boolean;
  onToggleSoundAlerts?: () => void;
  activeFootage?: TrackingFootageItem;
  footages?: TrackingFootageItem[];
  onSelectFootage?: (footageId: string) => void;
  onOpenAddFootage?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  connectionStatus,
  lastUpdated,
  onRefresh,
  onActorChange,
  soundAlertsEnabled = true,
  onToggleSoundAlerts,
  activeFootage,
  footages = [],
  onSelectFootage,
  onOpenAddFootage,
}) => {
  const [currentActor, setActor] = useState<StaffUser>(getCurrentActor());
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isFootageDropdownOpen, setIsFootageDropdownOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleSelectActor = (user: StaffUser) => {
    setCurrentActor(user);
    setActor(user);
    setIsDropdownOpen(false);
    onActorChange(user);
  };

  const handleRefreshClick = () => {
    setIsRefreshing(true);
    onRefresh();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const getSecondsAgo = () => {
    const sec = Math.floor((Date.now() - lastUpdated.getTime()) / 1000);
    if (sec < 5) return 'Just now';
    if (sec < 60) return `${sec}s ago`;
    return `${Math.floor(sec / 60)}m ago`;
  };

  return (
    <header style={{
      height: '64px',
      background: '#ffffff',
      borderBottom: '1px solid var(--border-subtle)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 28px',
      position: 'sticky',
      top: 0,
      zIndex: 40,
      boxShadow: 'var(--shadow-sm)',
    }}>
      {/* Location, Shift & Active Tracking Footage Selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 12px',
          background: '#f8fafc',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          fontSize: '0.84rem',
          fontWeight: 600,
          color: 'var(--text-main)',
        }}>
          <Building size={15} color="var(--accent-primary)" />
          <span>Downtown Bistro & Bar</span>
        </div>

        {/* Global Active Tracking Footage Channel Switcher */}
        {activeFootage && (
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setIsFootageDropdownOpen(!isFootageDropdownOpen)}
              title="Switch active tracking footage driving all restaurant floor dashboards"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 14px',
                background: '#eff6ff',
                border: '1px solid #bfdbfe',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.8rem',
                fontWeight: 700,
                color: 'var(--accent-primary)',
                cursor: 'pointer',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <Sparkles size={14} />
              <span>Tracking: <strong>{activeFootage.name.split('(')[0].trim()}</strong></span>
              <span className="badge badge-occupied" style={{ fontSize: '0.66rem', padding: '1px 6px' }}>
                {activeFootage.tables.length} Tables
              </span>
              <ChevronDown size={13} />
            </button>

            {isFootageDropdownOpen && (
              <div style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                marginTop: '6px',
                width: '320px',
                background: '#ffffff',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-md)',
                boxShadow: 'var(--shadow-xl)',
                zIndex: 60,
                overflow: 'hidden',
              }}>
                <div style={{
                  padding: '10px 14px',
                  background: '#f8fafc',
                  borderBottom: '1px solid var(--border-subtle)',
                  fontSize: '0.74rem',
                  fontWeight: 700,
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}>
                  <span>Active Tracking Footages</span>
                  <span>{footages.length} Available</span>
                </div>

                <div style={{ maxHeight: '260px', overflowY: 'auto' }}>
                  {footages.map((f) => {
                    const isSelected = f.id === activeFootage.id;
                    return (
                      <div
                        key={f.id}
                        onClick={() => {
                          onSelectFootage?.(f.id);
                          setIsFootageDropdownOpen(false);
                        }}
                        style={{
                          padding: '10px 14px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          background: isSelected ? 'var(--accent-light)' : '#ffffff',
                          borderBottom: '1px solid var(--border-subtle)',
                          cursor: 'pointer',
                        }}
                      >
                        <div>
                          <div style={{ fontSize: '0.82rem', fontWeight: isSelected ? 800 : 600, color: isSelected ? 'var(--accent-primary)' : 'var(--text-main)' }}>
                            {f.name}
                          </div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                            {f.section} • {f.tables.length} tables • {f.detectionsCount} guests
                          </div>
                        </div>

                        {isSelected && (
                          <span className="badge badge-occupied" style={{ fontSize: '0.66rem' }}>
                            ACTIVE
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>

                {onOpenAddFootage && (
                  <button
                    onClick={() => {
                      setIsFootageDropdownOpen(false);
                      onOpenAddFootage();
                    }}
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      background: '#f8fafc',
                      border: 'none',
                      borderTop: '1px solid var(--border-subtle)',
                      color: 'var(--accent-primary)',
                      fontSize: '0.8rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    <Plus size={14} />
                    <span>+ Add New Tracking Footage</span>
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '0.78rem',
          color: 'var(--text-muted)',
          padding: '4px 10px',
          background: '#f1f5f9',
          borderRadius: 'var(--radius-sm)',
        }}>
          <Clock size={13} />
          <span>Dinner Shift (17:30 – 23:00)</span>
        </div>
      </div>

      {/* Sync Status, Audio Notification, & Staff Role Selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {/* Sound alerts toggle */}
        {onToggleSoundAlerts && (
          <button
            onClick={onToggleSoundAlerts}
            title={soundAlertsEnabled ? 'Alert chimes: ON (click to mute)' : 'Alert chimes: MUTED (click to enable)'}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 10px',
              borderRadius: 'var(--radius-md)',
              background: soundAlertsEnabled ? 'var(--status-vacant-bg)' : '#f1f5f9',
              border: `1px solid ${soundAlertsEnabled ? 'var(--status-vacant-border)' : 'var(--border-subtle)'}`,
              color: soundAlertsEnabled ? 'var(--status-vacant)' : 'var(--text-muted)',
              fontSize: '0.78rem',
              fontWeight: 600,
            }}
          >
            {soundAlertsEnabled ? <Bell size={14} /> : <BellOff size={14} />}
            <span>{soundAlertsEnabled ? 'Chime On' : 'Muted'}</span>
          </button>
        )}

        {/* Live Sync Status Pill */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: '#f8fafc',
          padding: '5px 12px',
          borderRadius: '9999px',
          border: '1px solid var(--border-subtle)',
          fontSize: '0.78rem',
        }}>
          {connectionStatus === 'CONNECTED' ? (
            <>
              <div className="live-indicator" />
              <span style={{ color: 'var(--status-vacant)', fontWeight: 600 }}>Live Sync</span>
            </>
          ) : connectionStatus === 'CONNECTING' ? (
            <>
              <div className="live-indicator-warning" />
              <span style={{ color: 'var(--status-warning)', fontWeight: 500 }}>Connecting...</span>
            </>
          ) : (
            <>
              <div className="live-indicator-offline" />
              <span style={{ color: 'var(--status-critical)', fontWeight: 500 }}>Polling Fallback</span>
            </>
          )}

          <span style={{ color: 'var(--border-medium)', margin: '0 2px' }}>|</span>

          <span style={{ color: 'var(--text-dim)', fontSize: '0.74rem' }}>
            {getSecondsAgo()}
          </span>

          <button 
            onClick={handleRefreshClick}
            title="Refresh now"
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              color: 'var(--text-muted)',
              transform: isRefreshing ? 'rotate(180deg)' : 'none',
              transition: 'transform 0.4s ease',
              marginLeft: '2px',
            }}
          >
            <RefreshCw size={13} />
          </button>
        </div>

        {/* Current Active Staff User & Role Selector */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '5px 12px',
              background: '#ffffff',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-medium)',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <div style={{
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              background: currentActor.role === 'ADMIN' ? '#4f46e5' : currentActor.role === 'MANAGER' ? '#2563eb' : '#059669',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '0.76rem',
              color: '#ffffff',
            }}>
              {currentActor.display_name.charAt(0)}
            </div>

            <div style={{ textAlign: 'left', lineHeight: 1.25 }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-main)' }}>
                {currentActor.display_name}
              </div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 500 }}>
                {currentActor.role}
              </div>
            </div>

            <ChevronDown size={14} color="var(--text-muted)" />
          </button>

          {isDropdownOpen && (
            <div style={{
              position: 'absolute',
              right: 0,
              top: '115%',
              width: '220px',
              background: '#ffffff',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-xl)',
              padding: '6px',
              zIndex: 50,
            }}>
              <div style={{ padding: '6px 10px', fontSize: '0.68rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Select Active Staff Profile
              </div>
              {DEMO_USERS.map((user) => (
                <button
                  key={user.user_id}
                  onClick={() => handleSelectActor(user)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-sm)',
                    background: user.user_id === currentActor.user_id ? 'var(--accent-light)' : 'transparent',
                    color: user.user_id === currentActor.user_id ? 'var(--accent-primary)' : 'var(--text-main)',
                    fontSize: '0.82rem',
                    textAlign: 'left',
                  }}
                  onMouseEnter={(e) => {
                    if (user.user_id !== currentActor.user_id) e.currentTarget.style.background = '#f8fafc';
                  }}
                  onMouseLeave={(e) => {
                    if (user.user_id !== currentActor.user_id) e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{user.display_name}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{user.role}</div>
                  </div>
                  {user.user_id === currentActor.user_id && <UserCheck size={14} color="var(--accent-primary)" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
