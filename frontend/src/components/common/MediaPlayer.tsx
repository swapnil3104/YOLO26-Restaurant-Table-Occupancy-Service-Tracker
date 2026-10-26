import React, { useState, useRef, useEffect } from 'react';
import { 
  Play, 
  Pause, 
  Volume2, 
  VolumeX, 
  Maximize2, 
  Minimize2, 
  RefreshCw, 
  RotateCcw
} from 'lucide-react';
import { ActionableFailureCard } from './ActionableFailureCard';

export interface MediaPlayerProps {
  streamUrl: string;
  sourceType?: 'live_stream' | 'recorded_footage';
  posterUrl?: string;
  autoPlay?: boolean;
  loop?: boolean;
  isMuted?: boolean;
  onFullscreenChange?: (isFullscreen: boolean) => void;
  aspectRatio?: string;
  onError?: (err: Error | null) => void;
  showControls?: boolean;
  overlayBadge?: React.ReactNode;
  fallbackRawUrl?: string;
}

export const MediaPlayer: React.FC<MediaPlayerProps> = ({
  streamUrl,
  sourceType = 'live_stream',
  posterUrl,
  autoPlay = true,
  loop = true,
  isMuted: initialMuted = true,
  onFullscreenChange,
  aspectRatio = '16/9',
  onError,
  showControls = true,
  overlayBadge,
  fallbackRawUrl,
}) => {
  const isVideo = sourceType === 'recorded_footage' || streamUrl.endsWith('.mp4') || streamUrl.endsWith('.webm');
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const [isMuted, setIsMuted] = useState(initialMuted);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Connection & Stream state
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [cacheBuster, setCacheBuster] = useState(Date.now());

  // Clean unmount
  useEffect(() => {
    return () => {
      if (videoRef.current) {
        try {
          videoRef.current.pause();
          videoRef.current.src = '';
          videoRef.current.load();
        } catch {
          // ignore cleanup
        }
      }
    };
  }, []);

  // Sync fullscreen state
  useEffect(() => {
    const handleFsChange = () => {
      const fs = document.fullscreenElement === containerRef.current;
      setIsFullscreen(fs);
      if (onFullscreenChange) onFullscreenChange(fs);
    };
    document.addEventListener('fullscreenchange', handleFsChange);
    return () => document.removeEventListener('fullscreenchange', handleFsChange);
  }, [onFullscreenChange]);

  const handleToggleFullscreen = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!containerRef.current) return;
    try {
      if (!document.fullscreenElement) {
        await containerRef.current.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch (err) {
      console.warn('Fullscreen toggle failed:', err);
    }
  };

  const handleTogglePlay = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    }
  };

  const handleToggleMute = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!videoRef.current) return;
    const next = !isMuted;
    videoRef.current.muted = next;
    setIsMuted(next);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    const target = parseFloat(e.target.value);
    setCurrentTime(target);
    if (videoRef.current) {
      videoRef.current.currentTime = target;
    }
  };

  const handleCycleSpeed = (e: React.MouseEvent) => {
    e.stopPropagation();
    const rates = [1, 1.5, 2, 0.5];
    const nextIdx = (rates.indexOf(playbackRate) + 1) % rates.length;
    const nextRate = rates[nextIdx];
    setPlaybackRate(nextRate);
    if (videoRef.current) {
      videoRef.current.playbackRate = nextRate;
    }
  };

  const handleRetry = () => {
    setHasError(false);
    setIsLoading(true);
    setRetryCount(prev => prev + 1);
    setCacheBuster(Date.now());
    if (onError) onError(null);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const resolvedStreamUrl = `${streamUrl}${streamUrl.includes('?') ? '&' : '?'}cb=${cacheBuster}`;

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        aspectRatio,
        background: '#090d16',
        borderRadius: 'var(--radius-md, 8px)',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {/* Live / Video Rendering Area */}
      {!hasError && (
        <>
          {isVideo ? (
            <video
              ref={videoRef}
              src={streamUrl}
              poster={posterUrl}
              autoPlay={autoPlay}
              loop={loop}
              muted={isMuted}
              playsInline
              onLoadedData={() => setIsLoading(false)}
              onTimeUpdate={() => {
                if (videoRef.current) setCurrentTime(videoRef.current.currentTime);
              }}
              onLoadedMetadata={() => {
                if (videoRef.current) setDuration(videoRef.current.duration);
              }}
              onError={() => {
                setIsLoading(false);
                setHasError(true);
                if (onError) onError(new Error('Video loading failed'));
              }}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                display: 'block',
              }}
            />
          ) : (
            <img
              src={resolvedStreamUrl}
              alt="Live Camera Feed"
              onLoad={() => setIsLoading(false)}
              onError={() => {
                setIsLoading(false);
                setHasError(true);
                if (onError) onError(new Error('Stream disconnected or offline'));
              }}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                display: 'block',
              }}
            />
          )}
        </>
      )}

      {/* Actionable Failure State when Stream Errors */}
      {hasError && (
        <div style={{ padding: '20px', width: '90%', maxWidth: '420px', zIndex: 10 }}>
          <ActionableFailureCard
            type="UNAVAILABLE_STREAM"
            message={`Stream failed after attempt #${retryCount + 1}. Connection timed out or camera offline.`}
            details={fallbackRawUrl ? `Fallback stream: ${fallbackRawUrl}` : undefined}
            onRetry={handleRetry}
          />
        </div>
      )}

      {/* Loading Spinner */}
      {isLoading && !hasError && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(9, 13, 22, 0.7)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            color: '#94a3b8',
            fontSize: '0.78rem',
            zIndex: 5,
          }}
        >
          <RefreshCw size={24} className="spin" color="#38bdf8" />
          <span>Connecting Feed...</span>
        </div>
      )}

      {/* Custom Overlay Badge (e.g. YOLO26 Detection HUD, floor label, etc.) */}
      {overlayBadge && (
        <div style={{ position: 'absolute', top: '10px', left: '10px', zIndex: 6 }}>
          {overlayBadge}
        </div>
      )}

      {/* On-screen Controls Overlay */}
      {showControls && !hasError && (
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            padding: '8px 12px',
            background: 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.4) 60%, transparent 100%)',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
            zIndex: 8,
          }}
        >
          {isVideo && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="range"
                min={0}
                max={duration || 100}
                value={currentTime}
                onChange={handleSeek}
                style={{
                  flex: 1,
                  height: '4px',
                  accentColor: '#38bdf8',
                  cursor: 'pointer',
                }}
              />
              <span style={{ fontSize: '0.7rem', color: '#cbd5e1', fontFamily: 'monospace' }}>
                {formatTime(currentTime)} / {formatTime(duration)}
              </span>
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {isVideo && (
                <>
                  <button
                    onClick={handleTogglePlay}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#ffffff',
                      cursor: 'pointer',
                      padding: '4px',
                    }}
                    title={isPlaying ? 'Pause' : 'Play'}
                  >
                    {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                  </button>

                  <button
                    onClick={() => {
                      if (videoRef.current) videoRef.current.currentTime = 0;
                    }}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#94a3b8',
                      cursor: 'pointer',
                      padding: '4px',
                    }}
                    title="Rewind"
                  >
                    <RotateCcw size={14} />
                  </button>

                  <button
                    onClick={handleToggleMute}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#ffffff',
                      cursor: 'pointer',
                      padding: '4px',
                    }}
                    title={isMuted ? 'Unmute' : 'Mute'}
                  >
                    {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
                  </button>

                  <button
                    onClick={handleCycleSpeed}
                    style={{
                      background: 'rgba(255, 255, 255, 0.15)',
                      border: 'none',
                      borderRadius: '4px',
                      color: '#ffffff',
                      cursor: 'pointer',
                      padding: '2px 6px',
                      fontSize: '0.68rem',
                      fontWeight: 700,
                    }}
                    title="Playback Rate"
                  >
                    {playbackRate}x
                  </button>
                </>
              )}

              {!isVideo && (
                <button
                  onClick={handleRetry}
                  style={{
                    background: 'rgba(255,255,255,0.15)',
                    border: 'none',
                    borderRadius: '4px',
                    color: '#ffffff',
                    cursor: 'pointer',
                    padding: '3px 8px',
                    fontSize: '0.72rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                  title="Reconnect Live Stream"
                >
                  <RefreshCw size={12} />
                  <span>Reconnect</span>
                </button>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                onClick={handleToggleFullscreen}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#ffffff',
                  cursor: 'pointer',
                  padding: '4px',
                }}
                title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
              >
                {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default React.memo(MediaPlayer);
