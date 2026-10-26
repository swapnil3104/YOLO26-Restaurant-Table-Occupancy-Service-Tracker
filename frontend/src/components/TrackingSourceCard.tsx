import React, { useState } from 'react';
import { 
  Play, 
  Pause, 
  Trash2, 
  Maximize2, 
  AlertTriangle, 
  Loader2,
  Cpu
} from 'lucide-react';
import { TrackingFootageItem, TrackingLifecycleState } from '../types';

interface TrackingSourceCardProps {
  source: TrackingFootageItem;
  isSelected: boolean;
  onSelect: () => void;
  onFocus: () => void;
  onPauseToggle: (sourceId: string) => void;
  onRemoveRequest: (source: TrackingFootageItem) => void;
}

export const TrackingSourceCard: React.FC<TrackingSourceCardProps> = ({
  source,
  isSelected,
  onSelect,
  onFocus,
  onPauseToggle,
  onRemoveRequest,
}) => {
  const [streamError, setStreamError] = useState(false);

  const status: TrackingLifecycleState = source.status || 'Monitoring';
  const isInitializing = status === 'Added' || status === 'Validating' || status === 'Initializing Model';
  const isPaused = status === 'Paused';
  const isMonitoring = status === 'Monitoring';
  const isStopping = status === 'Stopping';

  // Badge configuration based on Phase 4 lifecycle states
  const getStatusBadge = () => {
    switch (status) {
      case 'Added':
        return {
          label: 'ADDED',
          bg: 'rgba(59, 130, 246, 0.15)',
          color: '#3b82f6',
          border: 'rgba(59, 130, 246, 0.3)',
          icon: <Loader2 size={12} className="spin" />,
        };
      case 'Validating':
        return {
          label: 'VALIDATING STREAM',
          bg: 'rgba(168, 85, 247, 0.15)',
          color: '#a855f7',
          border: 'rgba(168, 85, 247, 0.3)',
          icon: <Loader2 size={12} className="spin" />,
        };
      case 'Initializing Model':
        return {
          label: 'LOADING YOLO26 WEIGHTS',
          bg: 'rgba(6, 182, 212, 0.15)',
          color: '#06b6d4',
          border: 'rgba(6, 182, 212, 0.3)',
          icon: <Cpu size={12} className="spin" />,
        };
      case 'Monitoring':
        return {
          label: 'YOLO26 MONITORING ACTIVE',
          bg: 'rgba(16, 185, 129, 0.15)',
          color: '#10b981',
          border: 'rgba(16, 185, 129, 0.3)',
          icon: <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />,
        };
      case 'Paused':
        return {
          label: 'MONITORING PAUSED',
          bg: 'rgba(245, 158, 11, 0.15)',
          color: '#f59e0b',
          border: 'rgba(245, 158, 11, 0.3)',
          icon: <Pause size={10} />,
        };
      case 'Stopping':
        return {
          label: 'RELEASING WORKER...',
          bg: 'rgba(239, 68, 68, 0.15)',
          color: '#ef4444',
          border: 'rgba(239, 68, 68, 0.3)',
          icon: <Loader2 size={12} className="spin" />,
        };
      case 'Stopped':
        return {
          label: 'STOPPED',
          bg: 'rgba(100, 116, 139, 0.15)',
          color: '#94a3b8',
          border: 'rgba(100, 116, 139, 0.3)',
          icon: null,
        };
      case 'Error':
        return {
          label: 'ERROR',
          bg: 'rgba(239, 68, 68, 0.15)',
          color: '#ef4444',
          border: 'rgba(239, 68, 68, 0.3)',
          icon: <AlertTriangle size={12} />,
        };
      default:
        return {
          label: status.toUpperCase(),
          bg: '#e2e8f0',
          color: '#475569',
          border: '#cbd5e1',
          icon: null,
        };
    }
  };

  const badge = getStatusBadge();

  return (
    <div
      onClick={onSelect}
      style={{
        background: '#ffffff',
        borderRadius: 'var(--radius-lg)',
        border: isSelected ? '2px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
        overflow: 'hidden',
        boxShadow: isSelected ? 'var(--shadow-md)' : 'var(--shadow-sm)',
        transition: 'all 0.15s ease',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* 1. Card Top Bar */}
      <div style={{
        padding: '10px 14px',
        background: '#0d131f',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
          {/* Floor Tag */}
          <span style={{
            fontSize: '0.68rem',
            fontWeight: 800,
            padding: '2px 8px',
            borderRadius: 'var(--radius-sm)',
            background: 'rgba(37, 99, 235, 0.25)',
            color: '#60a5fa',
            border: '1px solid rgba(96, 165, 250, 0.3)',
            whiteSpace: 'nowrap',
          }}>
            {source.floor || 'Floor 1'}
          </span>

          <span style={{
            fontSize: '0.84rem',
            fontWeight: 700,
            color: '#ffffff',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {source.name}
          </span>
        </div>

        {/* State Badge */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '5px',
          padding: '2px 8px',
          borderRadius: 'var(--radius-full)',
          background: badge.bg,
          color: badge.color,
          border: `1px solid ${badge.border}`,
          fontSize: '0.66rem',
          fontWeight: 700,
          whiteSpace: 'nowrap',
        }}>
          {badge.icon}
          <span>{badge.label}</span>
        </div>
      </div>

      {/* 2. Video Preview Container with Overlays */}
      <div style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '16 / 9',
        background: '#040711',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        {streamError ? (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            textAlign: 'center',
            color: '#94a3b8',
          }}>
            <AlertTriangle size={28} color="#f59e0b" style={{ marginBottom: '6px' }} />
            <span style={{ fontSize: '0.78rem', color: '#e2e8f0', fontWeight: 600 }}>Feed Unavailable</span>
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setStreamError(false);
                }}
                style={{
                  padding: '4px 10px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--accent-primary)',
                  color: '#ffffff',
                  border: 'none',
                  fontSize: '0.7rem',
                  cursor: 'pointer',
                }}
              >
                Retry
              </button>
            </div>
          </div>
        ) : (
          (() => {
            const streamTarget = source.videoUrl || '/api/v1/cameras/cam-01/stream/processed';
            const isVideoFile = Boolean(
              streamTarget.endsWith('.mp4') ||
              streamTarget.endsWith('.webm') ||
              streamTarget.includes('/video-file/') ||
              streamTarget.includes('/videos/')
            );

            return isVideoFile ? (
              <video
                src={streamTarget}
                autoPlay
                loop
                muted
                playsInline
                onError={() => setStreamError(true)}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  display: 'block',
                  filter: isPaused ? 'grayscale(0.6) brightness(0.7)' : 'none',
                }}
              />
            ) : (
              <img
                src={streamTarget}
                alt={`${source.name} live tracking stream`}
                onError={() => setStreamError(true)}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  display: 'block',
                  filter: isPaused ? 'grayscale(0.6) brightness(0.7)' : 'none',
                }}
              />
            );
          })()
        )}

        {/* Initializing / Loading Overlay */}
        {isInitializing && (
          <div style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.85)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
            textAlign: 'center',
            color: '#ffffff',
          }}>
            <Loader2 size={28} className="spin" color="#38bdf8" style={{ marginBottom: '10px' }} />
            <div style={{ fontSize: '0.84rem', fontWeight: 700, color: '#f8fafc' }}>
              {status === 'Added' && 'Registering Tracking Job...'}
              {status === 'Validating' && 'Validating Camera Feed & Resolution...'}
              {status === 'Initializing Model' && 'Initializing YOLO26s Detector...'}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '4px', maxWidth: '300px' }}>
              {source.lastEventDescription || 'Preparing real-time diner and table tracking pipeline'}
            </div>
          </div>
        )}

        {/* Paused Overlay */}
        {isPaused && (
          <div style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.6)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
          }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              background: 'rgba(0,0,0,0.7)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#f59e0b',
            }}>
              <Pause size={20} />
            </div>
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#f8fafc' }}>
              Monitoring Paused
            </span>
          </div>
        )}

        {/* Bottom Left HUD (Active Monitoring) */}
        {isMonitoring && (
          <div style={{
            position: 'absolute',
            bottom: '8px',
            left: '8px',
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(6px)',
            padding: '4px 10px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.68rem',
            fontFamily: 'var(--font-mono)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            color: '#ffffff',
            border: '1px solid rgba(255, 255, 255, 0.1)',
          }}>
            <span style={{ color: '#10b981', fontWeight: 700 }}>● YOLO26</span>
            <span>{source.effectiveFps || source.fps || 30} FPS</span>
            <span>{source.latencyMs || 15.2}ms</span>
            <span style={{ color: '#60a5fa' }}>{source.detectionsCount || 8} Diners</span>
          </div>
        )}
      </div>

      {/* 3. Diagnostics & Telemetry Info Row */}
      <div style={{
        padding: '10px 14px',
        background: '#f8fafc',
        borderTop: '1px solid var(--border-subtle)',
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '8px',
        fontSize: '0.74rem',
      }}>
        <div>
          <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.68rem' }}>CAMERA HEALTH</span>
          <span style={{
            fontWeight: 700,
            color: source.cameraHealth === 'HEALTHY' ? '#16a34a' : '#d97706',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            marginTop: '1px',
          }}>
            <span style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: source.cameraHealth === 'HEALTHY' ? '#16a34a' : '#d97706',
              display: 'inline-block',
            }} />
            {source.cameraHealth || 'HEALTHY'}
          </span>
        </div>

        <div>
          <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.68rem' }}>INFERENCE STATE</span>
          <span style={{
            fontWeight: 700,
            color: isMonitoring ? '#2563eb' : (isPaused ? '#d97706' : '#64748b'),
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            marginTop: '1px',
          }}>
            {source.inferenceStatus || (isMonitoring ? 'ACTIVE' : 'IDLE')}
          </span>
        </div>

        <div style={{ gridColumn: 'span 2' }}>
          <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.68rem' }}>LATEST EVENT</span>
          <span style={{
            color: 'var(--text-main)',
            fontWeight: 600,
            fontSize: '0.72rem',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            display: 'block',
            marginTop: '1px',
          }}>
            {source.lastEventDescription || 'Normal dining room activity'}
          </span>
        </div>
      </div>

      {/* 4. Action Buttons Footer */}
      <div style={{
        padding: '8px 14px',
        background: '#ffffff',
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '8px',
      }}>
        {/* Pause / Resume Button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPauseToggle(source.id);
          }}
          disabled={isInitializing || isStopping}
          title={isPaused ? 'Resume YOLO26 monitoring' : 'Pause monitoring for this source'}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            padding: '5px 10px',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-medium)',
            background: isPaused ? '#fef3c7' : '#f8fafc',
            color: isPaused ? '#b45309' : 'var(--text-main)',
            fontSize: '0.72rem',
            fontWeight: 600,
            cursor: isInitializing || isStopping ? 'not-allowed' : 'pointer',
          }}
        >
          {isPaused ? <Play size={12} /> : <Pause size={12} />}
          <span>{isPaused ? 'Resume' : 'Pause'}</span>
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {/* Focus Button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onFocus();
            }}
            title="Focus this stream in single view"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '5px 10px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-medium)',
              background: '#ffffff',
              color: 'var(--accent-primary)',
              fontSize: '0.72rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <Maximize2 size={12} />
            <span>Focus</span>
          </button>

          {/* Remove Source Button */}
          <button
            data-testid={`remove-source-${source.id}`}
            onClick={(e) => {
              e.stopPropagation();
              onRemoveRequest(source);
            }}
            disabled={isStopping}
            title="Remove tracking source safely"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '5px 8px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid #fecaca',
              background: '#fef2f2',
              color: '#b91c1c',
              fontSize: '0.72rem',
              cursor: isStopping ? 'not-allowed' : 'pointer',
            }}
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  );
};
