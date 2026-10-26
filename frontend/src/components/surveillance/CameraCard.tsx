import React, { useState } from 'react';
import { 
  Maximize2, 
  Edit2, 
  Trash2, 
  Radio, 
  Film, 
  Sparkles, 
  Pause, 
  Play, 
  Layers
} from 'lucide-react';
import { CameraFeed } from '../../types';
import { MediaPlayer } from '../common/MediaPlayer';

export interface CameraCardProps {
  camera: CameraFeed;
  mode?: 'view_only' | 'tracking';
  isSelected?: boolean;
  onSelect?: () => void;
  onFocus?: () => void;
  onEdit?: () => void;
  onRemove?: () => void;
  onPauseToggle?: () => void;
  isPaused?: boolean;
  isSingleMode?: boolean;
}

export const CameraCard: React.FC<CameraCardProps> = ({
  camera,
  mode = 'view_only',
  isSelected = false,
  onSelect,
  onFocus,
  onEdit,
  onRemove,
  onPauseToggle,
  isPaused = false,
  isSingleMode = false,
}) => {
  const [streamError, setStreamError] = useState<Error | null>(null);

  const isRecorded = camera.source_type === 'recorded_footage' || !!camera.video_url;
  const isTracking = mode === 'tracking';

  const streamUrl = isTracking
    ? camera.processed_stream_url || `/api/v1/cameras/${camera.camera_id}/stream/processed`
    : camera.video_url || camera.raw_stream_url || `/api/v1/cameras/${camera.camera_id}/stream/raw`;

  return (
    <div
      onClick={onSelect}
      style={{
        background: '#ffffff',
        borderRadius: 'var(--radius-lg, 12px)',
        border: isSelected
          ? '2px solid var(--accent-primary, #3b82f6)'
          : '1px solid var(--border-subtle, #e2e8f0)',
        boxShadow: isSelected
          ? '0 0 0 3px rgba(59, 130, 246, 0.15), var(--shadow-md, 0 4px 6px -1px rgba(0,0,0,0.1))'
          : 'var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05))',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 0.15s ease',
        cursor: onSelect ? 'pointer' : 'default',
      }}
    >
      {/* Top Header */}
      <div
        style={{
          padding: '10px 14px',
          background: isSelected ? 'rgba(59, 130, 246, 0.03)' : '#ffffff',
          borderBottom: '1px solid var(--border-subtle, #f1f5f9)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
          {/* Status Dot */}
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: isPaused
                ? '#f59e0b'
                : streamError
                ? '#ef4444'
                : camera.status === 'ONLINE'
                ? '#10b981'
                : '#f59e0b',
              flexShrink: 0,
            }}
            title={isPaused ? 'Paused' : streamError ? 'Error' : camera.status}
          />

          <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            <h4
              style={{
                margin: 0,
                fontSize: '0.86rem',
                fontWeight: 700,
                color: 'var(--text-main, #0f172a)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {camera.name}
            </h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.7rem', color: 'var(--text-muted, #64748b)' }}>
              {camera.floor && (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                  <Layers size={10} />
                  <span>{camera.floor}</span>
                </span>
              )}
              <span>•</span>
              <span>{camera.section}</span>
            </div>
          </div>
        </div>

        {/* Right Badges & Quick Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {isTracking ? (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '2px 8px',
                borderRadius: '999px',
                background: isPaused ? 'rgba(245, 158, 11, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                color: isPaused ? '#b45309' : '#059669',
                fontSize: '0.68rem',
                fontWeight: 700,
              }}
            >
              <Sparkles size={11} />
              <span>{isPaused ? 'PAUSED' : 'YOLO26'}</span>
            </span>
          ) : (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '2px 8px',
                borderRadius: '999px',
                background: isRecorded ? 'rgba(99, 102, 241, 0.1)' : 'rgba(100, 116, 139, 0.1)',
                color: isRecorded ? '#4f46e5' : '#475569',
                fontSize: '0.68rem',
                fontWeight: 700,
              }}
            >
              {isRecorded ? <Film size={11} /> : <Radio size={11} />}
              <span>{isRecorded ? 'RECORDED' : 'LIVE'}</span>
            </span>
          )}

          {/* Action buttons */}
          {onFocus && !isSingleMode && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onFocus();
              }}
              title="Focus this camera"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted, #64748b)',
                cursor: 'pointer',
                padding: '4px',
                borderRadius: '4px',
              }}
            >
              <Maximize2 size={13} />
            </button>
          )}

          {onPauseToggle && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onPauseToggle();
              }}
              title={isPaused ? 'Resume tracking' : 'Pause tracking'}
              style={{
                background: 'transparent',
                border: 'none',
                color: isPaused ? '#10b981' : '#f59e0b',
                cursor: 'pointer',
                padding: '4px',
                borderRadius: '4px',
              }}
            >
              {isPaused ? <Play size={13} /> : <Pause size={13} />}
            </button>
          )}

          {onEdit && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onEdit();
              }}
              title="Rename Camera"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted, #64748b)',
                cursor: 'pointer',
                padding: '4px',
                borderRadius: '4px',
              }}
            >
              <Edit2 size={13} />
            </button>
          )}

          {onRemove && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRemove();
              }}
              title="Remove camera source"
              style={{
                background: 'transparent',
                border: 'none',
                color: '#ef4444',
                cursor: 'pointer',
                padding: '4px',
                borderRadius: '4px',
              }}
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Media Player Container */}
      <div style={{ position: 'relative', width: '100%', background: '#090d16' }}>
        <MediaPlayer
          streamUrl={streamUrl}
          sourceType={isRecorded ? 'recorded_footage' : 'live_stream'}
          autoPlay={!isPaused}
          loop={true}
          onError={(err) => setStreamError(err)}
          fallbackRawUrl={camera.raw_stream_url}
        />
      </div>

      {/* Footer Info Bar */}
      <div
        style={{
          padding: '8px 14px',
          background: '#f8fafc',
          borderTop: '1px solid var(--border-subtle, #f1f5f9)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.72rem',
          color: 'var(--text-dim, #64748b)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>{camera.resolution || '1080p'}</span>
          <span>•</span>
          <span>{camera.fps || 30} FPS</span>
        </div>

        <div>
          {isTracking ? (
            <span style={{ color: '#059669', fontWeight: 600 }}>Active Inference Feed</span>
          ) : (
            <span style={{ color: '#64748b' }}>Zero Inference</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default React.memo(CameraCard);
