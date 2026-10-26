import React from 'react';
import { AlertTriangle, RefreshCw, Cpu, FileX, ShieldAlert, ArrowRight } from 'lucide-react';

export type ActionableFailureType =
  | 'UNAVAILABLE_STREAM'
  | 'MISSING_WEIGHTS'
  | 'INVALID_FILE'
  | 'PROCESSING_LIMIT'
  | 'GENERIC_ERROR';

interface ActionableFailureCardProps {
  type: ActionableFailureType;
  title?: string;
  message?: string;
  details?: string;
  onRetry?: () => void;
  onAction?: () => void;
  actionLabel?: string;
  isRetrying?: boolean;
}

export const ActionableFailureCard: React.FC<ActionableFailureCardProps> = ({
  type,
  title,
  message,
  details,
  onRetry,
  onAction,
  actionLabel,
  isRetrying = false,
}) => {
  const getConfig = () => {
    switch (type) {
      case 'UNAVAILABLE_STREAM':
        return {
          icon: <AlertTriangle size={22} color="#f59e0b" />,
          defaultTitle: 'Camera Stream Offline or Unavailable',
          defaultMessage: 'Unable to establish video stream connection to this camera endpoint.',
          defaultDetails: 'Check camera network connectivity, verify RTSP/MJPEG stream URL, or ensure the server streaming worker is active.',
          bg: 'rgba(245, 158, 11, 0.08)',
          border: '1px solid rgba(245, 158, 11, 0.25)',
          badgeColor: '#b45309',
          retryText: 'Retry Connection',
        };
      case 'MISSING_WEIGHTS':
        return {
          icon: <Cpu size={22} color="#ef4444" />,
          defaultTitle: 'Fine-Tuned YOLO26 Model Checkpoint Missing',
          defaultMessage: 'The designated restaurant CCTV model weights file was not found.',
          defaultDetails: 'Ensure models/yolo26_restaurant_cctv.pt is present and accessible by the inference worker before starting tracking.',
          bg: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.25)',
          badgeColor: '#b91c1c',
          retryText: 'Reload Model',
        };
      case 'INVALID_FILE':
        return {
          icon: <FileX size={22} color="#ef4444" />,
          defaultTitle: 'Invalid Footage File or Format',
          defaultMessage: 'The uploaded file is corrupt, exceeds the size limit, or is an unsupported container.',
          defaultDetails: 'Upload standard MP4, WebM, or AVI footage up to 500MB with supported H.264/H.265/VP9 video encoding.',
          bg: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.25)',
          badgeColor: '#b91c1c',
          retryText: 'Choose Another File',
        };
      case 'PROCESSING_LIMIT':
        return {
          icon: <ShieldAlert size={22} color="#8b5cf6" />,
          defaultTitle: 'Inference Concurrency Limit Reached',
          defaultMessage: 'Maximum active YOLO26 tracking workers are currently allocated for this server.',
          defaultDetails: 'Pause or remove an idle tracking source before allocating an additional inference worker.',
          bg: 'rgba(139, 92, 246, 0.08)',
          border: '1px solid rgba(139, 92, 246, 0.25)',
          badgeColor: '#6d28d9',
          retryText: 'Refresh Workers',
        };
      default:
        return {
          icon: <AlertTriangle size={22} color="#ef4444" />,
          defaultTitle: 'Operational Service Disruption',
          defaultMessage: 'An unexpected processing failure occurred for this feed.',
          defaultDetails: 'Inspect server logs or retry the operation.',
          bg: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.25)',
          badgeColor: '#b91c1c',
          retryText: 'Retry',
        };
    }
  };

  const config = getConfig();

  return (
    <div
      style={{
        background: config.bg,
        border: config.border,
        borderRadius: 'var(--radius-lg, 12px)',
        padding: '16px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        textAlign: 'left',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <div style={{ marginTop: '2px', flexShrink: 0 }}>{config.icon}</div>
        <div style={{ flex: 1 }}>
          <h4
            style={{
              margin: '0 0 4px 0',
              fontSize: '0.92rem',
              fontWeight: 700,
              color: config.badgeColor,
            }}
          >
            {title || config.defaultTitle}
          </h4>
          <p
            style={{
              margin: '0 0 6px 0',
              fontSize: '0.82rem',
              color: 'var(--text-main, #1e293b)',
              lineHeight: 1.45,
            }}
          >
            {message || config.defaultMessage}
          </p>
          {(details || config.defaultDetails) && (
            <p
              style={{
                margin: 0,
                fontSize: '0.74rem',
                color: 'var(--text-muted, #64748b)',
                lineHeight: 1.4,
                fontFamily: 'monospace',
                background: 'rgba(255, 255, 255, 0.7)',
                padding: '4px 8px',
                borderRadius: '4px',
                display: 'inline-block',
              }}
            >
              {details || config.defaultDetails}
            </p>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
        {onRetry && (
          <button
            onClick={onRetry}
            disabled={isRetrying}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              background: '#ffffff',
              border: `1px solid ${config.badgeColor}`,
              borderRadius: 'var(--radius-md, 8px)',
              color: config.badgeColor,
              fontSize: '0.78rem',
              fontWeight: 700,
              cursor: isRetrying ? 'not-allowed' : 'pointer',
              boxShadow: 'var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05))',
            }}
          >
            <RefreshCw size={13} className={isRetrying ? 'spin' : ''} />
            <span>{isRetrying ? 'Retrying...' : config.retryText}</span>
          </button>
        )}

        {onAction && actionLabel && (
          <button
            onClick={onAction}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              background: config.badgeColor,
              border: 'none',
              borderRadius: 'var(--radius-md, 8px)',
              color: '#ffffff',
              fontSize: '0.78rem',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            <span>{actionLabel}</span>
            <ArrowRight size={13} />
          </button>
        )}
      </div>
    </div>
  );
};

export default ActionableFailureCard;
