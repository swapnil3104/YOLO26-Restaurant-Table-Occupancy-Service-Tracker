import React from 'react';
import { AlertTriangle, Trash2, ShieldCheck, X } from 'lucide-react';
import { TrackingFootageItem } from '../types';

interface RemoveTrackingSourceModalProps {
  source: TrackingFootageItem | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isRemoving?: boolean;
}

export const RemoveTrackingSourceModal: React.FC<RemoveTrackingSourceModalProps> = ({
  source,
  isOpen,
  onClose,
  onConfirm,
  isRemoving = false,
}) => {
  if (!isOpen || !source) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000,
        padding: '16px',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
        background: '#ffffff',
        borderRadius: 'var(--radius-xl)',
        maxWidth: '480px',
        width: '100%',
        boxShadow: 'var(--shadow-xl)',
        border: '1px solid var(--border-subtle)',
        overflow: 'hidden',
        animation: 'fadeIn 0.2s ease',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          background: '#fff1f2',
          borderBottom: '1px solid #fecdd3',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: 'var(--radius-md)',
              background: '#ffe4e6',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#e11d48',
            }}>
              <AlertTriangle size={18} />
            </div>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: '#9f1239' }}>
                Remove Tracking Source
              </h3>
              <p style={{ fontSize: '0.74rem', color: '#be123c', margin: '2px 0 0 0' }}>
                Confirm release of inference worker and stream resources
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isRemoving}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#9f1239',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div style={{ padding: '20px' }}>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-main)', margin: '0 0 14px 0', lineHeight: 1.5 }}>
            Are you sure you want to stop monitoring and remove <strong>{source.name}</strong> ({source.floor || 'Floor 1'})?
          </p>

          <div style={{
            padding: '12px 14px',
            background: '#f8fafc',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            marginBottom: '16px',
            fontSize: '0.78rem',
            color: 'var(--text-muted)',
            lineHeight: 1.45,
          }}>
            <ul style={{ margin: 0, paddingLeft: '18px' }}>
              <li>YOLO26 inference and ByteTrack processing for this feed will be safely stopped.</li>
              <li>Camera stream handles, socket connections, and worker memory will be released.</li>
              <li>Other active floor tracking sources will continue without interruption.</li>
            </ul>
          </div>

          {/* Historical Data Protection Notice */}
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            padding: '10px 14px',
            background: '#f0fdf4',
            borderRadius: 'var(--radius-md)',
            border: '1px solid #bbf7d0',
            color: '#15803d',
            fontSize: '0.76rem',
            lineHeight: 1.4,
          }}>
            <ShieldCheck size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong>Historical Data Preserved:</strong> Prior dining sessions, table occupancy history, service timestamps, and generated shift KPIs for this floor are permanently saved and will not be erased.
            </div>
          </div>
        </div>

        {/* Actions Footer */}
        <div style={{
          padding: '14px 20px',
          background: '#f8fafc',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: '10px',
        }}>
          <button
            type="button"
            onClick={onClose}
            disabled={isRemoving}
            style={{
              padding: '8px 16px',
              borderRadius: 'var(--radius-md)',
              background: '#ffffff',
              border: '1px solid var(--border-medium)',
              color: 'var(--text-main)',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: isRemoving ? 'not-allowed' : 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            data-testid="confirm-remove-source-btn"
            type="button"
            onClick={onConfirm}
            disabled={isRemoving}
            style={{
              padding: '8px 18px',
              borderRadius: 'var(--radius-md)',
              background: '#e11d48',
              border: 'none',
              color: '#ffffff',
              fontSize: '0.82rem',
              fontWeight: 700,
              cursor: isRemoving ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: '0 2px 4px rgba(225, 29, 72, 0.25)',
            }}
          >
            <Trash2 size={14} />
            <span>{isRemoving ? 'Releasing Resources...' : 'Confirm & Remove Source'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
