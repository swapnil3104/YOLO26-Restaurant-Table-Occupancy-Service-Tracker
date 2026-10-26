import React, { useState, useEffect } from 'react';
import { X, Video, Camera, Layers, CheckCircle2, AlertCircle, Upload, Film, Loader2 } from 'lucide-react';
import { TrackingFootageItem, VideoSourceItem } from '../types';
import { 
  addTrackingFootage, 
  getStoredTrackingFootages, 
  getAvailableFloors, 
  addCustomFloor,
  DEFAULT_TABLES,
  DEFAULT_ALERTS
} from '../services/trackingFootages';
import { uploadCCTVVideoFile, fetchVideoSources } from '../services/api';

interface AddTrackingFootageModalProps {
  isOpen: boolean;
  onClose: () => void;
  onFootageAdded: (newFootage: TrackingFootageItem) => void;
}

export const AddTrackingFootageModal: React.FC<AddTrackingFootageModalProps> = ({
  isOpen,
  onClose,
  onFootageAdded,
}) => {
  const [name, setName] = useState('Main Dining Demo Camera');
  const [availableFloors, setAvailableFloors] = useState<string[]>(['Floor 1', 'Floor 2']);
  const [floorSelection, setFloorSelection] = useState('Floor 1');
  const [isCreatingNewFloor, setIsCreatingNewFloor] = useState(false);
  const [newFloorName, setNewFloorName] = useState('');
  const [sectionName, setSectionName] = useState('Main Dining');
  const [sourceType, setSourceType] = useState<'demo' | 'upload' | 'catalog' | 'rtsp'>('demo');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [videoCatalog, setVideoCatalog] = useState<VideoSourceItem[]>([]);
  const [selectedCatalogId, setSelectedCatalogId] = useState<string>('vid_demo_dining');
  const [videoUrl, setVideoUrl] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [keepOpenForNext, setKeepOpenForNext] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const floors = getAvailableFloors();
      setAvailableFloors(floors);
      if (floors.length > 0 && !floors.includes(floorSelection)) {
        setFloorSelection(floors[0]);
      }
      setError(null);
      setUploadProgress(null);

      fetchVideoSources()
        .then((res) => {
          if (res && res.sources && res.sources.length > 0) {
            setVideoCatalog(res.sources);
            const foundDemo = res.sources.find(s => s.id === 'vid_demo_dining' || s.filename.includes('Cctv-Resturant-Demo') || s.filename.includes('3499758135'));
            if (foundDemo) {
              setSelectedCatalogId(foundDemo.id);
            } else {
              setSelectedCatalogId(res.sources[0].id);
            }
          }
        })
        .catch(() => {});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleFloorSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (val === '__NEW_FLOOR__') {
      setIsCreatingNewFloor(true);
      setNewFloorName('');
    } else {
      setIsCreatingNewFloor(false);
      setFloorSelection(val);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.size > 100 * 1024 * 1024) {
        setError('Video file exceeds maximum limit of 100MB.');
        return;
      }
      setSelectedFile(file);
      setError(null);
      if (!name || name === 'Main Dining Demo Camera') {
        setName(file.name.replace(/\.[^/.]+$/, '').replace(/_/g, ' '));
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Please provide a descriptive camera or footage name.');
      return;
    }

    // Determine actual floor
    let finalFloor = floorSelection;
    if (isCreatingNewFloor) {
      const trimmedFloor = newFloorName.trim();
      if (!trimmedFloor) {
        setError('Please enter a name for the new floor.');
        return;
      }
      addCustomFloor(trimmedFloor);
      finalFloor = trimmedFloor;
    }

    const existing = getStoredTrackingFootages();
    const generatedId = `cam-${Date.now().toString(36)}`;

    // Duplicate check
    if (existing.some((f) => f.name.toLowerCase() === trimmedName.toLowerCase())) {
      setError(`A tracking source named "${trimmedName}" already exists. Please choose a distinct name.`);
      return;
    }

    // Validation for live stream URLs
    if (sourceType === 'rtsp' && videoUrl.trim()) {
      const parsedUrl = videoUrl.trim().toLowerCase();
      if (!parsedUrl.startsWith('rtsp://') && !parsedUrl.startsWith('http://') && !parsedUrl.startsWith('https://')) {
        setError('Live stream URL must start with rtsp://, http://, or https://');
        return;
      }
    }

    if (sourceType === 'upload' && !selectedFile) {
      setError('Please select a video file (.mp4, .webm) to upload.');
      return;
    }

    setIsSubmitting(true);
    setUploadProgress(null);

    let finalStreamUrl = '/api/v1/cameras/cam-01/stream/processed';
    let finalRawUrl = '/api/v1/cameras/cam-01/stream/raw';

    try {
      if (sourceType === 'demo') {
        finalStreamUrl = '/api/v1/cameras/cam-01/stream/processed';
        finalRawUrl = '/api/v1/cameras/video-file/Cctv-Resturant-Demo.mp4';
      } else if (sourceType === 'upload' && selectedFile) {
        setUploadProgress('Uploading video file to server...');
        const uploadRes = await uploadCCTVVideoFile(selectedFile);
        finalStreamUrl = uploadRes.url;
        finalRawUrl = uploadRes.url;
      } else if (sourceType === 'catalog') {
        const item = videoCatalog.find((v) => v.id === selectedCatalogId);
        if (item) {
          finalStreamUrl = item.url;
          finalRawUrl = item.url;
        }
      } else if (sourceType === 'rtsp') {
        finalStreamUrl = videoUrl.trim() || '/api/v1/cameras/cam-01/stream/processed';
        finalRawUrl = videoUrl.trim() || '/api/v1/cameras/cam-01/stream/raw';
      }

      const fullSection = `${finalFloor}: ${sectionName.trim() || 'Dining Area'}`;

      const newFootageItem: TrackingFootageItem = {
        id: generatedId,
        name: trimmedName,
        floor: finalFloor,
        section: fullSection,
        description: `Dining table & patron tracking feed on ${finalFloor} powered by fine-tuned YOLO26.`,
        videoUrl: finalStreamUrl,
        rawVideoUrl: finalRawUrl,
        resolution: '1280x720',
        fps: 30,
        isCustom: true,
        modelName: 'Fine-tuned YOLO26s (Restaurant CCTV)',
        detectionsCount: 8,
        tables: DEFAULT_TABLES,
        alerts: DEFAULT_ALERTS,
        status: 'Monitoring',
        cameraHealth: 'HEALTHY',
        inferenceStatus: 'ACTIVE',
        effectiveFps: 30,
        lastEventTime: 'Just now',
        lastEventDescription: 'YOLO26 automated dining table tracking active.',
        sourceType: sourceType === 'rtsp' ? 'rtsp' : 'video',
        processingJobId: `job-${generatedId}`,
        latencyMs: 15.0,
      };

      addTrackingFootage(newFootageItem);
      onFootageAdded(newFootageItem);
      setIsSubmitting(false);
      setUploadProgress(null);

      if (keepOpenForNext) {
        setName('');
        setVideoUrl('');
        setSelectedFile(null);
        setIsCreatingNewFloor(false);
        setNewFloorName('');
      } else {
        setName('');
        setVideoUrl('');
        setSelectedFile(null);
        setIsCreatingNewFloor(false);
        setNewFloorName('');
        onClose();
      }
    } catch (err: unknown) {
      setIsSubmitting(false);
      setUploadProgress(null);
      setError(err instanceof Error ? err.message : 'Failed to register new tracking source.');
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.65)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 100,
      padding: '16px',
    }}>
      <div style={{
        background: '#ffffff',
        borderRadius: 'var(--radius-xl)',
        maxWidth: '560px',
        width: '100%',
        boxShadow: 'var(--shadow-xl)',
        border: '1px solid var(--border-subtle)',
        overflow: 'hidden',
        animation: 'fadeIn 0.2s ease',
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '18px 24px',
          background: 'linear-gradient(to right, #0f172a, #1e293b)',
          color: '#ffffff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '34px',
              height: '34px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(37, 99, 235, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#60a5fa',
            }}>
              <Camera size={18} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, letterSpacing: '-0.01em' }}>
                Add Tracking Footage
              </h3>
              <p style={{ fontSize: '0.74rem', color: '#94a3b8', margin: '2px 0 0 0' }}>
                Register camera feed for multi-floor YOLO26 diner & table monitoring
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSubmit} style={{ padding: '24px' }}>
          {error && (
            <div style={{
              marginBottom: '16px',
              padding: '10px 14px',
              borderRadius: 'var(--radius-md)',
              background: '#fef2f2',
              border: '1px solid #fecaca',
              color: '#b91c1c',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {uploadProgress && (
            <div style={{
              marginBottom: '16px',
              padding: '10px 14px',
              borderRadius: 'var(--radius-md)',
              background: '#eff6ff',
              border: '1px solid #bfdbfe',
              color: '#1d4ed8',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              <Loader2 size={16} className="spin" style={{ flexShrink: 0 }} />
              <span>{uploadProgress}</span>
            </div>
          )}

          {/* Camera / Source Name */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
              Camera / Footage Name *
            </label>
            <input
              type="text"
              placeholder="e.g. Dining Hall West, Mezzanine VIP Cam"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-medium)',
                fontSize: '0.86rem',
                outline: 'none',
              }}
            />
          </div>

          {/* Floor & Section Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
                Restaurant Floor *
              </label>
              {!isCreatingNewFloor ? (
                <select
                  value={floorSelection}
                  onChange={handleFloorSelectChange}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-medium)',
                    fontSize: '0.86rem',
                    background: '#ffffff',
                  }}
                >
                  {availableFloors.map((fl) => (
                    <option key={fl} value={fl}>{fl}</option>
                  ))}
                  <option value="__NEW_FLOOR__">+ Create New Floor...</option>
                </select>
              ) : (
                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <input
                    type="text"
                    placeholder="e.g. Floor 3 (Rooftop)"
                    value={newFloorName}
                    onChange={(e) => setNewFloorName(e.target.value)}
                    required
                    style={{
                      width: '100%',
                      padding: '9px 12px',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--accent-primary)',
                      fontSize: '0.84rem',
                      outline: 'none',
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setIsCreatingNewFloor(false)}
                    style={{
                      background: '#f1f5f9',
                      border: '1px solid var(--border-medium)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '8px',
                      cursor: 'pointer',
                      fontSize: '0.72rem',
                    }}
                    title="Cancel new floor"
                  >
                    ✕
                  </button>
                </div>
              )}
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
                Section / Zone Label
              </label>
              <input
                type="text"
                placeholder="e.g. Patio, Booths, VIP"
                value={sectionName}
                onChange={(e) => setSectionName(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-medium)',
                  fontSize: '0.86rem',
                }}
              />
            </div>
          </div>

          {/* Source Type Selector */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '8px' }}>
              Select Video Source *
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
              <button
                type="button"
                onClick={() => setSourceType('demo')}
                style={{
                  padding: '8px 4px',
                  borderRadius: 'var(--radius-md)',
                  border: sourceType === 'demo' ? '2px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
                  background: sourceType === 'demo' ? 'var(--accent-light)' : '#f8fafc',
                  color: sourceType === 'demo' ? 'var(--accent-primary)' : 'var(--text-main)',
                  fontWeight: 600,
                  fontSize: '0.74rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '5px',
                  cursor: 'pointer',
                  textAlign: 'center',
                }}
              >
                <Film size={16} />
                <span>Project Demo Video</span>
              </button>

              <button
                type="button"
                onClick={() => setSourceType('upload')}
                style={{
                  padding: '8px 4px',
                  borderRadius: 'var(--radius-md)',
                  border: sourceType === 'upload' ? '2px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
                  background: sourceType === 'upload' ? 'var(--accent-light)' : '#f8fafc',
                  color: sourceType === 'upload' ? 'var(--accent-primary)' : 'var(--text-main)',
                  fontWeight: 600,
                  fontSize: '0.74rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '5px',
                  cursor: 'pointer',
                  textAlign: 'center',
                }}
              >
                <Upload size={16} />
                <span>Upload File (.mp4)</span>
              </button>

              <button
                type="button"
                onClick={() => setSourceType('catalog')}
                style={{
                  padding: '8px 4px',
                  borderRadius: 'var(--radius-md)',
                  border: sourceType === 'catalog' ? '2px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
                  background: sourceType === 'catalog' ? 'var(--accent-light)' : '#f8fafc',
                  color: sourceType === 'catalog' ? 'var(--accent-primary)' : 'var(--text-main)',
                  fontWeight: 600,
                  fontSize: '0.74rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '5px',
                  cursor: 'pointer',
                  textAlign: 'center',
                }}
              >
                <Video size={16} />
                <span>Sample Catalog</span>
              </button>

              <button
                type="button"
                onClick={() => setSourceType('rtsp')}
                style={{
                  padding: '8px 4px',
                  borderRadius: 'var(--radius-md)',
                  border: sourceType === 'rtsp' ? '2px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
                  background: sourceType === 'rtsp' ? 'var(--accent-light)' : '#f8fafc',
                  color: sourceType === 'rtsp' ? 'var(--accent-primary)' : 'var(--text-main)',
                  fontWeight: 600,
                  fontSize: '0.74rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '5px',
                  cursor: 'pointer',
                  textAlign: 'center',
                }}
              >
                <Layers size={16} />
                <span>RTSP Stream</span>
              </button>
            </div>
          </div>

          {/* Conditional Input based on Source Type */}
          {sourceType === 'demo' && (
            <div style={{
              marginBottom: '16px',
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              background: '#f0fdf4',
              border: '1px solid #bbf7d0',
            }}>
              <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#15803d', display: 'block', marginBottom: '2px' }}>
                ✓ Project Demo CCTV Video Selected
              </span>
              <span style={{ fontSize: '0.72rem', color: '#166534', display: 'block' }}>
                File: <strong>Cctv-Resturant-Demo.mp4</strong> with live YOLO26 AI inference, table edge polygons, and seated diner detection.
              </span>
            </div>
          )}

          {sourceType === 'upload' && (
            <div style={{
              marginBottom: '16px',
              padding: '14px',
              borderRadius: 'var(--radius-md)',
              background: '#f8fafc',
              border: '1px solid var(--border-medium)',
            }}>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
                Choose Local Video File (.mp4, .webm, max 100MB) *
              </label>
              <input
                type="file"
                accept=".mp4,.webm,.mkv,.mov"
                onChange={handleFileChange}
                style={{ fontSize: '0.8rem', width: '100%' }}
              />
              {selectedFile && (
                <div style={{ marginTop: '6px', fontSize: '0.74rem', color: '#059669', fontWeight: 600 }}>
                  Selected: {selectedFile.name} ({(selectedFile.size / (1024 * 1024)).toFixed(1)} MB)
                </div>
              )}
            </div>
          )}

          {sourceType === 'catalog' && (
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
                Select Video from Server Catalog
              </label>
              <select
                value={selectedCatalogId}
                onChange={(e) => setSelectedCatalogId(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-medium)',
                  fontSize: '0.84rem',
                  background: '#ffffff',
                }}
              >
                {videoCatalog.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} ({v.filename})
                  </option>
                ))}
              </select>
            </div>
          )}

          {sourceType === 'rtsp' && (
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
                Live Stream URL (RTSP / HTTP)
              </label>
              <input
                type="text"
                placeholder="rtsp://user:pass@camera-ip:554/live"
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-medium)',
                  fontSize: '0.84rem',
                  fontFamily: 'var(--font-mono)',
                }}
              />
            </div>
          )}

          {/* Repeated additions option checkbox */}
          <div style={{
            marginBottom: '20px',
            padding: '10px 12px',
            background: '#f8fafc',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}>
            <input
              type="checkbox"
              id="keepOpenForNext"
              checked={keepOpenForNext}
              onChange={(e) => setKeepOpenForNext(e.target.checked)}
              style={{ cursor: 'pointer', width: '16px', height: '16px' }}
            />
            <label htmlFor="keepOpenForNext" style={{ fontSize: '0.78rem', color: 'var(--text-main)', cursor: 'pointer', userSelect: 'none' }}>
              Add another tracking source immediately after this (repeated addition)
            </label>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              style={{
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                background: '#ffffff',
                border: '1px solid var(--border-medium)',
                color: 'var(--text-main)',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                padding: '8px 18px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--accent-primary)',
                border: 'none',
                color: '#ffffff',
                fontSize: '0.82rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: '0 2px 4px rgba(37, 99, 235, 0.25)',
              }}
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={15} className="spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 size={15} />
                  <span>{keepOpenForNext ? 'Add & Continue' : 'Add & Start Monitoring'}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
