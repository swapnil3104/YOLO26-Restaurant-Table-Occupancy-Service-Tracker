import React, { useState, useEffect } from 'react';
import { X, Camera, Film, CheckCircle2, AlertCircle, Eye } from 'lucide-react';
import { CameraFeed, VideoSourceItem } from '../types';
import { createCameraFeed, fetchVideoSources, uploadCCTVVideoFile } from '../services/api';

interface AddCCTVModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSourceAdded: (newFeed: CameraFeed) => void;
  existingFeeds: CameraFeed[];
}

export const AddCCTVModal: React.FC<AddCCTVModalProps> = ({
  isOpen,
  onClose,
  onSourceAdded,
  existingFeeds,
}) => {
  const [name, setName] = useState('');
  const [floor, setFloor] = useState('Floor 1');
  const [customFloor, setCustomFloor] = useState('');
  const [section, setSection] = useState('Main Dining');
  const [sourceType, setSourceType] = useState<'live_stream' | 'recorded_footage'>('live_stream');
  const [streamUrl, setStreamUrl] = useState('');
  
  // Recorded video options
  const [videoCatalog, setVideoCatalog] = useState<VideoSourceItem[]>([]);
  const [selectedCatalogId, setSelectedCatalogId] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [previewActive, setPreviewActive] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchVideoSources()
        .then((res) => {
          if (res?.sources) {
            setVideoCatalog(res.sources.filter(s => s.category === 'standard_cctv' || s.category === 'custom'));
            if (res.sources.length > 0 && !selectedCatalogId) {
              const defaultCctv = res.sources.find(s => s.category === 'standard_cctv') || res.sources[0];
              setSelectedCatalogId(defaultCctv.id);
            }
          }
        })
        .catch(() => {});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const effectiveFloor = floor === 'CUSTOM' ? customFloor.trim() || 'Floor 1' : floor;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
      if (!['.mp4', '.webm', '.mkv', '.mov'].includes(ext)) {
        setError(`Unsupported file format "${ext}". Supported: .mp4, .webm, .mkv, .mov`);
        return;
      }
      if (file.size > 100 * 1024 * 1024) {
        setError(`File exceeds 100 MB limit (${(file.size / (1024 * 1024)).toFixed(1)} MB).`);
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanName = name.trim();
    if (!cleanName) {
      setError('Please provide a descriptive camera name (e.g. "Main Dining South CCTV").');
      return;
    }

    if (existingFeeds.some(f => f.name.toLowerCase() === cleanName.toLowerCase())) {
      setError(`A camera named "${cleanName}" already exists. Please choose a distinct name.`);
      return;
    }

    setIsSubmitting(true);
    setUploadProgress(null);

    try {
      let finalVideoFileId: string | undefined = undefined;

      // Handle file upload if user provided a local file
      if (sourceType === 'recorded_footage' && selectedFile) {
        setUploadProgress('Uploading video file with validation...');
        const uploadRes = await uploadCCTVVideoFile(selectedFile);
        finalVideoFileId = uploadRes.filename;
      } else if (sourceType === 'recorded_footage' && selectedCatalogId) {
        finalVideoFileId = selectedCatalogId;
      }

      const created = await createCameraFeed({
        name: cleanName,
        floor: effectiveFloor,
        section: section.trim() || 'Main Dining',
        source_type: sourceType,
        stream_url: sourceType === 'live_stream' ? (streamUrl.trim() || undefined) : undefined,
        video_file_id: finalVideoFileId,
      });

      onSourceAdded(created);
      setName('');
      setStreamUrl('');
      setSelectedFile(null);
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to add CCTV camera feed.');
    } finally {
      setIsSubmitting(false);
      setUploadProgress(null);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.7)',
      backdropFilter: 'blur(5px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
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
        maxHeight: '92vh',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '18px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#f8fafc',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--accent-light)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-primary)',
            }}>
              <Camera size={20} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-main)' }}>
                Add CCTV Camera Feed
              </h3>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                Standard CCTV viewing only • Zero AI inference side effects
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Body / Form */}
        <form onSubmit={handleSubmit} style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
          {error && (
            <div style={{
              padding: '10px 14px',
              background: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: 'var(--radius-md)',
              color: '#dc2626',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '16px',
            }}>
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {uploadProgress && (
            <div style={{
              padding: '10px 14px',
              background: 'rgba(59, 130, 246, 0.08)',
              border: '1px solid #bfdbfe',
              borderRadius: 'var(--radius-md)',
              color: 'var(--accent-primary)',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '16px',
            }}>
              <CheckCircle2 size={16} />
              <span>{uploadProgress}</span>
            </div>
          )}

          {/* 1. Camera Name */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
              Camera Name *
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Floor 1 — Cashier Counter CCTV"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-medium)',
                fontSize: '0.84rem',
                outline: 'none',
              }}
            />
          </div>

          {/* 2. Restaurant Floor & Section */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
                Restaurant Floor *
              </label>
              <select
                value={floor}
                onChange={(e) => setFloor(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-medium)',
                  fontSize: '0.84rem',
                  background: '#ffffff',
                }}
              >
                <option value="Floor 1">Floor 1 (Ground)</option>
                <option value="Floor 2">Floor 2 (Mezzanine)</option>
                <option value="Floor 3">Floor 3 (Terrace)</option>
                <option value="Patio">Patio Area</option>
                <option value="Rooftop">Rooftop Lounge</option>
                <option value="CUSTOM">Custom Floor...</option>
              </select>
              {floor === 'CUSTOM' && (
                <input
                  type="text"
                  placeholder="Enter custom floor name"
                  value={customFloor}
                  onChange={(e) => setCustomFloor(e.target.value)}
                  style={{
                    width: '100%',
                    marginTop: '8px',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-medium)',
                    fontSize: '0.82rem',
                  }}
                />
              )}
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
                Section / Zone
              </label>
              <input
                type="text"
                placeholder="e.g. Main Dining, Bar, Kitchen"
                value={section}
                onChange={(e) => setSection(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-medium)',
                  fontSize: '0.84rem',
                }}
              />
            </div>
          </div>

          {/* 3. Ingestion Source Type Selector */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
              Ingestion Source Type *
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setSourceType('live_stream')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md)',
                  border: sourceType === 'live_stream' ? '2px solid var(--accent-primary)' : '1px solid var(--border-medium)',
                  background: sourceType === 'live_stream' ? 'rgba(37, 99, 235, 0.05)' : '#ffffff',
                  color: sourceType === 'live_stream' ? 'var(--accent-primary)' : 'var(--text-main)',
                  fontWeight: 600,
                  fontSize: '0.82rem',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <Camera size={16} />
                <div>
                  <div>Live CCTV Stream</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 400 }}>RTSP / MJPEG Feed</div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setSourceType('recorded_footage')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md)',
                  border: sourceType === 'recorded_footage' ? '2px solid #f59e0b' : '1px solid var(--border-medium)',
                  background: sourceType === 'recorded_footage' ? 'rgba(245, 158, 11, 0.05)' : '#ffffff',
                  color: sourceType === 'recorded_footage' ? '#b45309' : 'var(--text-main)',
                  fontWeight: 600,
                  fontSize: '0.82rem',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <Film size={16} />
                <div>
                  <div>Recorded Footage</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 400 }}>Video File Playback</div>
                </div>
              </button>
            </div>
          </div>

          {/* 4. Type-Specific Ingestion Config */}
          {sourceType === 'live_stream' ? (
            <div style={{
              padding: '14px',
              background: '#f8fafc',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              marginBottom: '16px',
            }}>
              <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '4px' }}>
                Live Stream Endpoint URL (RTSP / HTTP / MJPEG)
              </label>
              <input
                type="text"
                placeholder="Leave blank for simulated live feed, or enter rtsp://... or http://..."
                value={streamUrl}
                onChange={(e) => setStreamUrl(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-medium)',
                  fontSize: '0.8rem',
                  fontFamily: 'var(--font-mono)',
                }}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px', fontSize: '0.7rem', color: '#10b981' }}>
                <CheckCircle2 size={12} />
                <span>Labeled explicitly as <strong>LIVE CCTV STREAM</strong>. No AI tracking load.</span>
              </div>
            </div>
          ) : (
            <div style={{
              padding: '14px',
              background: '#fffbeb',
              border: '1px solid #fde68a',
              borderRadius: 'var(--radius-lg)',
              marginBottom: '16px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
                <span style={{
                  fontSize: '0.7rem',
                  fontWeight: 800,
                  color: '#b45309',
                  background: '#fef3c7',
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-full)',
                }}>
                  RECORDED FOOTAGE • NOT LIVE CCTV
                </span>
              </div>

              {/* Upload local file */}
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '4px' }}>
                  Upload Video File (.mp4, .webm, max 100MB)
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="file"
                    accept=".mp4,.webm,.mkv,.mov"
                    onChange={handleFileChange}
                    style={{ fontSize: '0.78rem' }}
                  />
                  {selectedFile && (
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      ({(selectedFile.size / (1024 * 1024)).toFixed(1)} MB)
                    </span>
                  )}
                </div>
              </div>

              {/* Or select from catalog */}
              <div>
                <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '4px' }}>
                  Or Select Pre-Loaded CCTV Sample Footage
                </label>
                <select
                  value={selectedCatalogId}
                  onChange={(e) => {
                    setSelectedCatalogId(e.target.value);
                    setSelectedFile(null);
                  }}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-medium)',
                    fontSize: '0.8rem',
                    background: '#ffffff',
                  }}
                >
                  {videoCatalog.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name} ({v.resolution} • {v.fps} FPS)
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* 5. Live Preview Option */}
          <div style={{ marginBottom: '16px' }}>
            <button
              type="button"
              onClick={() => setPreviewActive(!previewActive)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                background: 'transparent',
                border: 'none',
                color: 'var(--accent-primary)',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                padding: '4px 0',
              }}
            >
              <Eye size={14} />
              <span>{previewActive ? 'Hide Source Preview' : 'Show Live Source Preview'}</span>
            </button>

            {previewActive && (
              <div style={{
                marginTop: '8px',
                aspectRatio: '16 / 9',
                background: '#040711',
                borderRadius: 'var(--radius-md)',
                overflow: 'hidden',
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <img
                  src={streamUrl.trim() || '/api/v1/cameras/cam-01/stream/raw'}
                  alt="Stream Preview"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
                <div style={{
                  position: 'absolute',
                  top: '6px',
                  left: '6px',
                  background: 'rgba(0,0,0,0.7)',
                  color: '#ffffff',
                  fontSize: '0.66rem',
                  padding: '2px 6px',
                  borderRadius: 'var(--radius-sm)',
                  fontWeight: 700,
                }}>
                  PREVIEW FEED
                </div>
              </div>
            )}
          </div>

          {/* Modal Actions */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '10px',
            marginTop: '20px',
            borderTop: '1px solid var(--border-subtle)',
            paddingTop: '16px',
          }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              style={{
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                background: 'transparent',
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
                padding: '8px 20px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--accent-primary)',
                color: '#ffffff',
                border: 'none',
                fontSize: '0.82rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {isSubmitting ? 'Registering Source...' : 'Add CCTV Feed'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
