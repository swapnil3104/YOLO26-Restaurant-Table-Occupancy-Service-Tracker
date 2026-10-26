import React, { useState } from 'react';
import { Camera, Plus, Shield } from 'lucide-react';
import { CameraFeed } from '../../types';
import { CameraGrid, GridLayoutMode } from './CameraGrid';
import { CCTVPlayerCard } from '../CCTVPlayerCard';
import { RenameCCTVModal } from '../RenameCCTVModal';
import { ErrorBoundary } from '../common/ErrorBoundary';

export interface StandardCctvViewProps {
  cameras: CameraFeed[];
  layoutMode: GridLayoutMode;
  onLayoutChange: (mode: GridLayoutMode) => void;
  selectedCameraId?: string;
  onSelectCamera: (id: string) => void;
  onRefresh: () => void | Promise<void>;
  onOpenAddModal: () => void;
  onDeleteCamera: (camera: CameraFeed) => void;
}

export const StandardCctvView: React.FC<StandardCctvViewProps> = ({
  cameras,
  layoutMode,
  onLayoutChange,
  selectedCameraId,
  onSelectCamera,
  onRefresh,
  onOpenAddModal,
  onDeleteCamera,
}) => {
  const [editingCamera, setEditingCamera] = useState<CameraFeed | null>(null);

  const selectedIdx = Math.max(
    0,
    cameras.findIndex((c) => c.camera_id === selectedCameraId)
  );

  return (
    <ErrorBoundary fallbackTitle="Standard CCTV View Error">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* View-Only Guarantee Banner */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 16px',
            background: 'rgba(100, 116, 139, 0.08)',
            border: '1px solid rgba(100, 116, 139, 0.2)',
            borderRadius: 'var(--radius-lg, 12px)',
            fontSize: '0.78rem',
            color: '#475569',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Shield size={16} color="#64748b" />
            <span>
              <strong>Zero-Inference Policy:</strong> Standard CCTV view streams raw footage for physical facility security only. No AI inference jobs, patron tracking, or occupancy analytics are created.
            </span>
          </div>
          <span style={{ fontWeight: 700, color: '#64748b', whiteSpace: 'nowrap' }}>
            {cameras.length} Active {cameras.length === 1 ? 'Feed' : 'Feeds'}
          </span>
        </div>

        {/* Empty State */}
        {cameras.length === 0 ? (
          <div
            style={{
              padding: '60px 24px',
              background: '#ffffff',
              borderRadius: 'var(--radius-xl, 16px)',
              border: '2px dashed var(--border-medium, #cbd5e1)',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '50%',
                background: 'rgba(59, 130, 246, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Camera size={28} color="#3b82f6" />
            </div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#0f172a' }}>
              No CCTV Feeds Configured
            </h3>
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#64748b', maxWidth: '420px' }}>
              Add a camera stream or recorded surveillance footage to begin monitoring facility areas without triggering AI tracking.
            </p>
            <button
              onClick={onOpenAddModal}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '9px 18px',
                background: 'var(--accent-primary, #3b82f6)',
                color: '#ffffff',
                border: 'none',
                borderRadius: 'var(--radius-md, 8px)',
                fontSize: '0.82rem',
                fontWeight: 700,
                cursor: 'pointer',
                marginTop: '8px',
              }}
            >
              <Plus size={16} />
              <span>Add First CCTV Feed</span>
            </button>
          </div>
        ) : (
          /* Responsive Multi-Camera Grid */
          <CameraGrid
            layoutMode={layoutMode}
            onLayoutChange={onLayoutChange}
            selectedChildIndex={selectedIdx}
            totalFeeds={cameras.length}
          >
            {cameras.map((camera) => (
              <CCTVPlayerCard
                key={camera.camera_id}
                camera={camera}
                isSelected={camera.camera_id === selectedCameraId}
                onSelect={() => onSelectCamera(camera.camera_id)}
                onFocus={() => {
                  onSelectCamera(camera.camera_id);
                  onLayoutChange('single');
                }}
                onEdit={() => setEditingCamera(camera)}
                onRemove={() => onDeleteCamera(camera)}
                isSingleMode={layoutMode === 'single'}
              />
            ))}
          </CameraGrid>
        )}

        {/* Rename Modal */}
        {editingCamera && (
          <RenameCCTVModal
            isOpen={true}
            camera={editingCamera}
            onClose={() => setEditingCamera(null)}
            onCameraUpdated={async () => {
              await onRefresh();
              setEditingCamera(null);
            }}
          />
        )}
      </div>
    </ErrorBoundary>
  );
};

export default React.memo(StandardCctvView);
