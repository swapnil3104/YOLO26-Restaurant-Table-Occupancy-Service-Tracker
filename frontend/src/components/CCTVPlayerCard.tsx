import React, { useState, useRef, useEffect } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Volume2, 
  VolumeX, 
  Maximize2, 
  Minimize2, 
  RefreshCw, 
  AlertTriangle, 
  Edit2, 
  Trash2, 
  Radio, 
  Film,
  Repeat
} from 'lucide-react';
import { CameraFeed } from '../types';

interface CCTVPlayerCardProps {
  camera: CameraFeed;
  isSelected?: boolean;
  onSelect?: () => void;
  onFocus?: () => void;
  onEdit?: () => void;
  onRemove?: () => void;
  isSingleMode?: boolean;
}

export const CCTVPlayerCard: React.FC<CCTVPlayerCardProps> = ({
  camera,
  isSelected = false,
  onSelect,
  onFocus,
  onEdit,
  onRemove,
  isSingleMode = false,
}) => {
  const isRecorded = camera.source_type === 'recorded_footage' || !!camera.video_url;
  const cardContainerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Playback state for recorded footage
  const [isPlaying, setIsPlaying] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(true);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isLooping, setIsLooping] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Live feed state
  const [hasStreamError, setHasStreamError] = useState(false);
  const [retryAttempts, setRetryAttempts] = useState(0);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [streamCacheBust, setStreamCacheBust] = useState(Date.now());

  // Clean unmount & resource release
  useEffect(() => {
    return () => {
      if (videoRef.current) {
        try {
          videoRef.current.pause();
          videoRef.current.src = '';
          videoRef.current.load();
        } catch {
          // Ignore cleanup errors
        }
      }
    };
  }, []);

  // Listen to fullscreenchange
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === cardContainerRef.current);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const toggleFullscreen = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!cardContainerRef.current) return;
    try {
      if (!document.fullscreenElement) {
        await cardContainerRef.current.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch (err) {
      console.warn('Fullscreen request failed:', err);
    }
  };

  // Video playback controls
  const handleTogglePlay = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration || 0);
      if (isPlaying) {
        videoRef.current.play().catch(() => {});
      }
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(e.target.value);
    setCurrentTime(newTime);
    if (videoRef.current) {
      videoRef.current.currentTime = newTime;
    }
  };

  const handleRestart = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  const handleRateChange = (rate: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setPlaybackRate(rate);
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
    }
  };

  const handleToggleMute = (e: React.MouseEvent) => {
    e.stopPropagation();
    const next = !isMuted;
    setIsMuted(next);
    if (videoRef.current) {
      videoRef.current.muted = next;
    }
  };

  // Live stream retry logic
  const handleRetryStream = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsReconnecting(true);
    setHasStreamError(false);
    setRetryAttempts(prev => prev + 1);
    setStreamCacheBust(Date.now());
    setTimeout(() => setIsReconnecting(false), 800);
  };

  const formatTime = (seconds: number) => {
    if (isNaN(seconds)) return '00:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const rawStreamUrlWithBust = `${camera.raw_stream_url}${camera.raw_stream_url.includes('?') ? '&' : '?'}t=${streamCacheBust}`;
  const videoFileUrl = camera.video_url || `/api/v1/cameras/video-file/Cctv-Resturant-Demo.mp4`;

  return (
    <div
      ref={cardContainerRef}
      onClick={onSelect}
      style={{
        background: '#ffffff',
        borderRadius: isFullscreen ? '0px' : 'var(--radius-lg)',
        border: isSelected && !isFullscreen ? '2px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
        overflow: 'hidden',
        boxShadow: isFullscreen ? 'none' : 'var(--shadow-md)',
        display: 'flex',
        flexDirection: 'column',
        position: isFullscreen ? 'fixed' : 'relative',
        inset: isFullscreen ? 0 : 'auto',
        zIndex: isFullscreen ? 9999 : 1,
        transition: 'border 0.15s ease',
      }}
    >
      {/* 1. Feed Header */}
      <div style={{
        padding: '10px 16px',
        background: '#0d131f',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '8px',
      }}>
        {/* Left: Camera Name, Floor & Source Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
          <div className={camera.status === 'ONLINE' && !hasStreamError ? 'live-indicator' : 'live-indicator-offline'} />
          <span style={{
            fontSize: isSingleMode ? '0.98rem' : '0.86rem',
            fontWeight: 700,
            color: '#ffffff',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>
            {camera.name}
          </span>
          <span style={{
            fontSize: '0.72rem',
            color: '#94a3b8',
            background: 'rgba(255, 255, 255, 0.08)',
            padding: '2px 8px',
            borderRadius: 'var(--radius-sm)',
            whiteSpace: 'nowrap',
          }}>
            {camera.floor || 'Floor 1'}
          </span>
        </div>

        {/* Right: Source Type Label & Header Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isRecorded ? (
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              background: 'rgba(245, 158, 11, 0.18)',
              border: '1px solid rgba(245, 158, 11, 0.4)',
              color: '#f59e0b',
              fontSize: '0.68rem',
              fontWeight: 700,
              letterSpacing: '0.03em',
            }}>
              <Film size={11} />
              RECORDED FOOTAGE
            </span>
          ) : (
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              background: 'rgba(16, 185, 129, 0.18)',
              border: '1px solid rgba(16, 185, 129, 0.4)',
              color: '#10b981',
              fontSize: '0.68rem',
              fontWeight: 700,
              letterSpacing: '0.03em',
            }}>
              <Radio size={11} />
              LIVE CCTV STREAM
            </span>
          )}

          <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>
            {camera.resolution} • {camera.fps} FPS
          </span>
        </div>
      </div>

      {/* 2. Media Player Viewport Container */}
      <div style={{
        position: 'relative',
        width: '100%',
        aspectRatio: isFullscreen ? 'auto' : (isSingleMode ? '21 / 9' : '16 / 9'),
        flex: isFullscreen ? 1 : 'none',
        background: '#040711',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        {isRecorded ? (
          /* A. HTML5 Video Player for Recorded Footage */
          <>
            <video
              ref={videoRef}
              src={videoFileUrl}
              loop={isLooping}
              muted={isMuted}
              playsInline
              autoPlay
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onEnded={() => {
                if (!isLooping) setIsPlaying(false);
              }}
              onError={() => setHasStreamError(true)}
              style={{
                width: '100%',
                height: '100%',
                objectFit: isSingleMode ? 'contain' : 'cover',
                display: 'block',
              }}
            />

            {/* Video overlay badge */}
            <div style={{
              position: 'absolute',
              top: '10px',
              left: '10px',
              background: 'rgba(0, 0, 0, 0.75)',
              backdropFilter: 'blur(6px)',
              padding: '3px 8px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.68rem',
              fontFamily: 'var(--font-mono)',
              color: '#f59e0b',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}>
              <Film size={12} />
              <span>RECORDED FOOTAGE • {formatTime(currentTime)} / {formatTime(duration)}</span>
            </div>
          </>
        ) : (
          /* B. Live CCTV MJPEG / RTSP Stream */
          hasStreamError ? (
            <div style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#94a3b8',
              padding: '24px',
              textAlign: 'center',
            }}>
              <AlertTriangle size={32} color="#f59e0b" style={{ marginBottom: '8px' }} />
              <div style={{ fontSize: '0.84rem', fontWeight: 700, color: '#e2e8f0' }}>Live Stream Offline</div>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>
                Camera is unreachable or RTSP connection timed out
              </div>
              <button
                onClick={handleRetryStream}
                disabled={isReconnecting}
                style={{
                  marginTop: '12px',
                  padding: '6px 14px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--accent-primary)',
                  color: '#ffffff',
                  border: 'none',
                  fontSize: '0.76rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <RefreshCw size={13} className={isReconnecting ? 'spin' : ''} />
                <span>{isReconnecting ? 'Reconnecting...' : `Retry Connection ${retryAttempts > 0 ? `(${retryAttempts})` : ''}`}</span>
              </button>
            </div>
          ) : (
            <>
              <img
                src={rawStreamUrlWithBust}
                alt={`${camera.name} Live CCTV`}
                onError={() => setHasStreamError(true)}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: isSingleMode ? 'contain' : 'cover',
                  display: 'block',
                }}
              />
              {/* Live overlay tag */}
              <div style={{
                position: 'absolute',
                top: '10px',
                left: '10px',
                background: 'rgba(0, 0, 0, 0.75)',
                backdropFilter: 'blur(6px)',
                padding: '3px 8px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.68rem',
                fontFamily: 'var(--font-mono)',
                color: '#10b981',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}>
                <Radio size={12} />
                <span>LIVE FEED • NO AI LOAD</span>
              </div>
            </>
          )
        )}
      </div>

      {/* 3. Recorded Footage Playback Bar (Visible for Recorded Media) */}
      {isRecorded && (
        <div style={{
          padding: '8px 14px',
          background: '#0d131f',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
        }}>
          {/* Progress seek bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#cbd5e1' }}>
              {formatTime(currentTime)}
            </span>
            <input
              type="range"
              min="0"
              max={duration || 100}
              step="0.1"
              value={currentTime}
              onChange={handleSeek}
              style={{
                flex: 1,
                cursor: 'pointer',
                accentColor: '#f59e0b',
                height: '4px',
              }}
            />
            <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>
              {formatTime(duration)}
            </span>
          </div>

          {/* Media control icons */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <button
                onClick={handleTogglePlay}
                title={isPlaying ? 'Pause' : 'Play'}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#ffffff',
                  cursor: 'pointer',
                  padding: '4px',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                {isPlaying ? <Pause size={15} /> : <Play size={15} />}
              </button>

              <button
                onClick={handleRestart}
                title="Restart footage"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: '4px',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <RotateCcw size={14} />
              </button>

              <button
                onClick={handleToggleMute}
                title={isMuted ? 'Unmute' : 'Mute'}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: '4px',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                {isMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
              </button>

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setIsLooping(!isLooping);
                }}
                title={isLooping ? 'Looping enabled' : 'Looping disabled'}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: isLooping ? '#f59e0b' : '#64748b',
                  cursor: 'pointer',
                  padding: '4px',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <Repeat size={14} />
              </button>
            </div>

            {/* Playback speed buttons */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              {[0.5, 1, 1.5, 2].map((rate) => (
                <button
                  key={rate}
                  onClick={(e) => handleRateChange(rate, e)}
                  style={{
                    background: playbackRate === rate ? 'rgba(245, 158, 11, 0.25)' : 'transparent',
                    border: playbackRate === rate ? '1px solid #f59e0b' : 'none',
                    color: playbackRate === rate ? '#f59e0b' : '#94a3b8',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.64rem',
                    fontWeight: 700,
                    padding: '2px 5px',
                    cursor: 'pointer',
                  }}
                >
                  {rate}x
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 4. Card Bottom Action Toolbar */}
      <div style={{
        padding: '10px 16px',
        background: '#f8fafc',
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.74rem',
        color: 'var(--text-muted)',
      }}>
        <div>
          <span>Section: <strong>{camera.section}</strong></span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Focus button (in grid mode) */}
          {!isSingleMode && onFocus && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onFocus();
              }}
              title="Focus single camera view"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--accent-primary)',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 6px',
              }}
            >
              <Maximize2 size={13} />
              <span>Focus</span>
            </button>
          )}

          {/* Fullscreen button */}
          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-main)',
              cursor: 'pointer',
              padding: '4px 6px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            <span>{isFullscreen ? 'Exit' : 'Fullscreen'}</span>
          </button>

          {/* Rename / Edit */}
          {onEdit && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onEdit();
              }}
              title="Rename camera or update location"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '4px',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <Edit2 size={14} />
            </button>
          )}

          {/* Remove */}
          {onRemove && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRemove();
              }}
              title="Remove camera feed"
              style={{
                background: 'transparent',
                border: 'none',
                color: '#ef4444',
                cursor: 'pointer',
                padding: '4px',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
