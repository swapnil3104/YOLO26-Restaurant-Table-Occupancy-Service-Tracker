import React, { useState, useEffect, useMemo } from 'react';
import { 
  Camera, 
  Sparkles, 
  ChevronRight, 
  Eye
} from 'lucide-react';
import { 
  CameraFeed, 
  CVTelemetry, 
  TrackingFootageItem, 
  FloorAnalyticsResponse, 
  ReportingScope 
} from '../types';
import { fetchCameraCVMetadata, deleteCameraFeed, fetchFloorAnalytics } from '../services/api';
import { 
  pauseTrackingFootage, 
  resumeTrackingFootage, 
  removeTrackingFootage 
} from '../services/trackingFootages';
import { computeFloorAndCentralKPIs } from '../services/floorAnalytics';
import { StandardCctvView } from '../components/surveillance/StandardCctvView';
import { TrackingView } from '../components/surveillance/TrackingView';
import { SourceManager } from '../components/surveillance/SourceManager';
import { GridLayoutMode } from '../components/surveillance/CameraGrid';
import { AddCCTVModal } from '../components/AddCCTVModal';
import { RemoveTrackingSourceModal } from '../components/RemoveTrackingSourceModal';

export type SurveillancePrimaryView = 'standard_cctv' | 'tracking_view';

export interface SurveillancePageProps {
  cameras: CameraFeed[];
  onRefresh: () => void | Promise<void>;
  activeFootage?: TrackingFootageItem;
  footages?: TrackingFootageItem[];
  onSelectFootage?: (footageId: string) => void;
  onOpenAddFootage?: () => void;
}

export const SurveillancePage: React.FC<SurveillancePageProps> = ({
  cameras,
  onRefresh,
  activeFootage,
  footages = [],
  onSelectFootage,
  onOpenAddFootage,
}) => {
  // Navigation: Standard CCTV is 1st, Tracking View is 2nd
  const [activeView, setActiveView] = useState<SurveillancePrimaryView>(() => {
    const hash = window.location.hash.toLowerCase();
    const params = new URLSearchParams(window.location.search);
    const viewParam = params.get('view') || params.get('mode');

    if (
      hash === '#tracking' || 
      hash === '#vision' || 
      viewParam === 'tracking' || 
      viewParam === 'single_vision' || 
      viewParam === 'quad_grid'
    ) {
      return 'tracking_view';
    }
    return 'standard_cctv';
  });

  // Layout mode: 'single' vs 'grid' per view
  const [cctvLayout, setCctvLayout] = useState<GridLayoutMode>('grid');
  const [trackingLayout, setTrackingLayout] = useState<GridLayoutMode>('grid');

  // Selected camera / footage tracking
  const [selectedCamId, setSelectedCamId] = useState<string>(cameras[0]?.camera_id || 'cam-01');
  const [telemetry, setTelemetry] = useState<CVTelemetry | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [redirectNotice, setRedirectNotice] = useState<string | null>(null);

  // Standard CCTV source modals & state
  const [isAddCCTVModalOpen, setIsAddCCTVModalOpen] = useState(false);
  const [cameraToRemove, setCameraToRemove] = useState<CameraFeed | null>(null);
  const [isRemovingCamera, setIsRemovingCamera] = useState(false);

  // Tracking View multi-floor state
  const [activeFloorFilter, setActiveFloorFilter] = useState<string>('ALL');
  const [trackingSourceToRemove, setTrackingSourceToRemove] = useState<TrackingFootageItem | null>(null);
  const [isRemovingTrackingSource, setIsRemovingTrackingSource] = useState(false);

  // Central & Floor KPIs state
  const [reportingScope, setReportingScope] = useState<ReportingScope>('LIVE_ACTIVE_SOURCES');
  const [floorAnalytics, setFloorAnalytics] = useState<FloorAnalyticsResponse>(() =>
    computeFloorAndCentralKPIs(footages, 'LIVE_ACTIVE_SOURCES')
  );
  const [freshnessSec, setFreshnessSec] = useState<number>(0);

  // Compute unique floors across active sources
  const uniqueFloors = useMemo(() => {
    const set = new Set<string>();
    if (activeView === 'standard_cctv') {
      cameras.forEach((c) => {
        if (c.floor) set.add(c.floor);
      });
    } else {
      footages.forEach((f) => {
        if (f.floor) set.add(f.floor);
      });
    }
    return Array.from(set).sort();
  }, [cameras, footages, activeView]);

  // Filter sources by active floor
  const filteredCameras = useMemo(() => {
    if (activeFloorFilter === 'ALL') return cameras;
    return cameras.filter((c) => c.floor === activeFloorFilter);
  }, [cameras, activeFloorFilter]);

  const filteredFootages = useMemo(() => {
    if (activeFloorFilter === 'ALL') return footages;
    return footages.filter((f) => f.floor === activeFloorFilter);
  }, [footages, activeFloorFilter]);

  // Recalculate floor analytics
  useEffect(() => {
    const localCalculated = computeFloorAndCentralKPIs(footages, reportingScope);
    setFloorAnalytics(localCalculated);
    setFreshnessSec(0);

    let isMounted = true;
    const fetchRemoteAnalytics = async () => {
      try {
        const remote = await fetchFloorAnalytics(activeFloorFilter);
        if (isMounted && remote && remote.central) {
          setFloorAnalytics(remote);
        }
      } catch {
        // tolerate offline
      }
    };
    fetchRemoteAnalytics();

    const freshnessTimer = setInterval(() => {
      setFreshnessSec((prev) => prev + 1);
    }, 1000);

    return () => {
      isMounted = false;
      clearInterval(freshnessTimer);
    };
  }, [footages, reportingScope, activeFloorFilter]);

  // Legacy bookmark redirect handler
  useEffect(() => {
    const handleUrlCheck = () => {
      const hash = window.location.hash.toLowerCase();
      const params = new URLSearchParams(window.location.search);
      const modeParam = params.get('mode') || params.get('view');

      if (hash === '#dual-split' || modeParam === 'split_dual') {
        setActiveView('tracking_view');
        setRedirectNotice('Legacy "Dual Split" view has been consolidated into the unified Tracking View.');
        window.history.replaceState(null, '', window.location.pathname + '#tracking');
      } else if (hash === '#multi-tracking' || modeParam === 'quad_grid') {
        setActiveView('tracking_view');
        setTrackingLayout('grid');
        setRedirectNotice('Legacy "Multi-Tracking" view has been merged into Tracking View Grid mode.');
        window.history.replaceState(null, '', window.location.pathname + '#tracking');
      } else if (hash === '#cctv' || modeParam === 'single_cctv' || modeParam === 'cctv') {
        setActiveView('standard_cctv');
      }
    };

    handleUrlCheck();
    window.addEventListener('hashchange', handleUrlCheck);
    return () => window.removeEventListener('hashchange', handleUrlCheck);
  }, []);

  // Poll CV Telemetry only in Tracking View (Zero inference polling in Standard CCTV)
  useEffect(() => {
    if (activeView !== 'tracking_view') {
      setTelemetry(null);
      return;
    }

    let isMounted = true;
    const loadTelemetry = async () => {
      const targetCamId = activeFootage?.id || selectedCamId;
      if (!targetCamId) return;
      try {
        const data = await fetchCameraCVMetadata(targetCamId);
        if (isMounted && data) {
          setTelemetry(data);
        }
      } catch {
        // tolerate transient error
      }
    };

    loadTelemetry();
    const interval = setInterval(loadTelemetry, 3000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [activeFootage?.id, selectedCamId, activeView]);

  // Switch between Standard CCTV and Tracking View
  const switchView = (newView: SurveillancePrimaryView) => {
    setActiveView(newView);
    setRedirectNotice(null);
    const hash = newView === 'standard_cctv' ? '#cctv' : '#tracking';
    window.history.replaceState(null, '', window.location.pathname + hash);
  };

  const handleRefreshClick = async () => {
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setTimeout(() => setIsRefreshing(false), 500);
    }
  };

  const handleTrackingPauseToggle = (sourceId: string) => {
    const target = footages.find((f) => f.id === sourceId);
    if (!target) return;
    if (target.status === 'Paused') {
      resumeTrackingFootage(sourceId);
    } else {
      pauseTrackingFootage(sourceId);
    }
    onRefresh();
  };

  const handleConfirmRemoveTrackingSource = async () => {
    if (!trackingSourceToRemove) return;
    setIsRemovingTrackingSource(true);
    try {
      removeTrackingFootage(trackingSourceToRemove.id);
      try {
        await deleteCameraFeed(trackingSourceToRemove.id);
      } catch {
        // tolerate local or non-persisted camera IDs
      }
      await onRefresh();
      setTrackingSourceToRemove(null);
    } catch (err) {
      console.error('Failed to remove tracking source:', err);
    } finally {
      setIsRemovingTrackingSource(false);
    }
  };

  const handleConfirmDeleteCamera = async () => {
    if (!cameraToRemove) return;
    setIsRemovingCamera(true);
    try {
      await deleteCameraFeed(cameraToRemove.camera_id);
      await onRefresh();
      if (selectedCamId === cameraToRemove.camera_id) {
        const remaining = cameras.filter((c) => c.camera_id !== cameraToRemove.camera_id);
        if (remaining.length > 0) {
          setSelectedCamId(remaining[0].camera_id);
        }
      }
      setCameraToRemove(null);
    } catch (err) {
      console.error('Failed to remove camera feed:', err);
    } finally {
      setIsRemovingCamera(false);
    }
  };

  return (
    <div className="page-wrapper" style={{ padding: '24px 32px' }}>
      {/* 1. Legacy Redirect Banner */}
      {redirectNotice && (
        <div
          style={{
            marginBottom: '16px',
            padding: '10px 16px',
            background: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid #bfdbfe',
            borderRadius: 'var(--radius-md, 8px)',
            color: 'var(--accent-primary, #3b82f6)',
            fontSize: '0.82rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={16} />
            <span>{redirectNotice}</span>
          </div>
          <button
            onClick={() => setRedirectNotice(null)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted, #64748b)',
              cursor: 'pointer',
              fontSize: '0.8rem',
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 2. Top Header & Title */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
          marginBottom: '20px',
        }}
      >
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.74rem',
              color: 'var(--text-muted, #64748b)',
              marginBottom: '4px',
            }}
          >
            <span>SmartServe</span>
            <ChevronRight size={12} />
            <span>Surveillance & Vision</span>
            <ChevronRight size={12} />
            <strong style={{ color: 'var(--text-main, #0f172a)' }}>
              {activeView === 'standard_cctv' ? 'Standard CCTV' : 'Tracking View'}
            </strong>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <h1
              style={{
                fontSize: '1.45rem',
                fontWeight: 800,
                letterSpacing: '-0.02em',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                margin: 0,
              }}
            >
              {activeView === 'standard_cctv' ? (
                <>
                  <Camera size={24} color="var(--accent-primary, #3b82f6)" />
                  Standard CCTV
                </>
              ) : (
                <>
                  <Sparkles size={24} color="#3b82f6" />
                  Tracking View
                </>
              )}
            </h1>

            {activeView === 'standard_cctv' ? (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '3px 10px',
                  borderRadius: '999px',
                  background: 'rgba(100, 116, 139, 0.12)',
                  border: '1px solid rgba(100, 116, 139, 0.25)',
                  fontSize: '0.72rem',
                  color: '#475569',
                  fontWeight: 700,
                }}
              >
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: '#64748b',
                    display: 'inline-block',
                  }}
                />
                VIEW ONLY • ZERO INFERENCE
              </span>
            ) : (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '3px 10px',
                  borderRadius: '999px',
                  background: 'rgba(16, 185, 129, 0.1)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  fontSize: '0.72rem',
                  color: '#10b981',
                  fontWeight: 700,
                }}
              >
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: '#10b981',
                    display: 'inline-block',
                  }}
                />
                YOLO26 AI INFERENCE ACTIVE
              </span>
            )}
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted, #64748b)', marginTop: '4px', marginBottom: 0 }}>
            {activeView === 'standard_cctv'
              ? 'Multi-camera surveillance video feeds. Viewing only, with zero AI inference load or analytics side-effects.'
              : 'Real-time dining table occupancy tracking, ByteTrack patron associations, and service time monitoring.'}
          </p>
        </div>
      </div>

      {/* 3. Primary Navigation Tabs: 1. Standard CCTV | 2. Tracking View */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          padding: '6px 8px',
          background: '#ffffff',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: 'var(--radius-lg, 12px)',
          boxShadow: 'var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05))',
          marginBottom: '20px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            id="tab-standard-cctv"
            onClick={() => switchView('standard_cctv')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '9px 18px',
              borderRadius: 'var(--radius-md, 8px)',
              fontSize: '0.84rem',
              fontWeight: activeView === 'standard_cctv' ? 700 : 500,
              background: activeView === 'standard_cctv' ? 'var(--accent-primary, #3b82f6)' : 'transparent',
              color: activeView === 'standard_cctv' ? '#ffffff' : 'var(--text-muted, #64748b)',
              border: 'none',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              boxShadow: activeView === 'standard_cctv' ? '0 2px 4px rgba(37, 99, 235, 0.2)' : 'none',
            }}
          >
            <Eye size={16} />
            <span>1. Standard CCTV</span>
            <span
              style={{
                fontSize: '0.68rem',
                padding: '1px 6px',
                borderRadius: '999px',
                background: activeView === 'standard_cctv' ? 'rgba(255, 255, 255, 0.25)' : '#e2e8f0',
                color: activeView === 'standard_cctv' ? '#ffffff' : '#64748b',
                fontWeight: 700,
              }}
            >
              View Only
            </span>
          </button>

          <button
            id="tab-tracking-view"
            onClick={() => switchView('tracking_view')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '9px 18px',
              borderRadius: 'var(--radius-md, 8px)',
              fontSize: '0.84rem',
              fontWeight: activeView === 'tracking_view' ? 700 : 500,
              background: activeView === 'tracking_view' ? 'var(--accent-primary, #3b82f6)' : 'transparent',
              color: activeView === 'tracking_view' ? '#ffffff' : 'var(--text-muted, #64748b)',
              border: 'none',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              boxShadow: activeView === 'tracking_view' ? '0 2px 4px rgba(37, 99, 235, 0.2)' : 'none',
            }}
          >
            <Sparkles size={16} />
            <span>2. Tracking View</span>
            <span
              style={{
                fontSize: '0.68rem',
                padding: '1px 6px',
                borderRadius: '999px',
                background: activeView === 'tracking_view' ? 'rgba(255, 255, 255, 0.25)' : 'rgba(16, 185, 129, 0.15)',
                color: activeView === 'tracking_view' ? '#ffffff' : '#10b981',
                fontWeight: 700,
              }}
            >
              YOLO26
            </span>
          </button>
        </div>
      </div>

      {/* 4. Unified SourceManager Toolbar (Floor filters, Layout switch, Add action) */}
      <SourceManager
        activeView={activeView}
        floors={uniqueFloors}
        activeFloorFilter={activeFloorFilter}
        onFloorFilterChange={setActiveFloorFilter}
        layoutMode={activeView === 'standard_cctv' ? cctvLayout : trackingLayout}
        onLayoutModeChange={(mode) => {
          if (activeView === 'standard_cctv') setCctvLayout(mode);
          else setTrackingLayout(mode);
        }}
        totalSources={activeView === 'standard_cctv' ? filteredCameras.length : filteredFootages.length}
        onlineSources={
          activeView === 'standard_cctv'
            ? filteredCameras.filter((c) => c.status === 'ONLINE').length
            : filteredFootages.filter((f) => f.status === 'Monitoring').length
        }
        isRefreshing={isRefreshing}
        onRefresh={handleRefreshClick}
        onOpenAddModal={() => {
          if (activeView === 'standard_cctv') {
            setIsAddCCTVModalOpen(true);
          } else if (onOpenAddFootage) {
            onOpenAddFootage();
          }
        }}
      />

      {/* 5. Main Body: Standard CCTV vs Tracking View */}
      {activeView === 'standard_cctv' ? (
        <StandardCctvView
          cameras={filteredCameras}
          layoutMode={cctvLayout}
          onLayoutChange={setCctvLayout}
          selectedCameraId={selectedCamId}
          onSelectCamera={setSelectedCamId}
          onRefresh={onRefresh}
          onOpenAddModal={() => setIsAddCCTVModalOpen(true)}
          onDeleteCamera={(cam) => setCameraToRemove(cam)}
        />
      ) : (
        <TrackingView
          footages={filteredFootages}
          activeFootage={activeFootage}
          onSelectFootage={onSelectFootage}
          layoutMode={trackingLayout}
          onLayoutChange={setTrackingLayout}
          telemetry={telemetry}
          floorAnalytics={floorAnalytics}
          reportingScope={reportingScope}
          onReportingScopeChange={setReportingScope}
          freshnessSeconds={freshnessSec}
          activeFloorFilter={activeFloorFilter}
          onSelectFloor={setActiveFloorFilter}
          onPauseToggle={handleTrackingPauseToggle}
          onRemoveRequest={(footage) => setTrackingSourceToRemove(footage)}
          onOpenAddModal={() => onOpenAddFootage && onOpenAddFootage()}
        />
      )}

      {/* 6. Modals */}
      {/* Add CCTV Modal */}
      <AddCCTVModal
        isOpen={isAddCCTVModalOpen}
        onClose={() => setIsAddCCTVModalOpen(false)}
        existingFeeds={cameras}
        onSourceAdded={async (newFeed) => {
          await onRefresh();
          setSelectedCamId(newFeed.camera_id);
          setIsAddCCTVModalOpen(false);
        }}
      />

      {/* Remove Tracking Source Modal */}
      {trackingSourceToRemove && (
        <RemoveTrackingSourceModal
          isOpen={true}
          source={trackingSourceToRemove}
          onClose={() => setTrackingSourceToRemove(null)}
          onConfirm={handleConfirmRemoveTrackingSource}
          isRemoving={isRemovingTrackingSource}
        />
      )}

      {/* Remove CCTV Camera Feed Confirmation Dialog */}
      {cameraToRemove && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px',
          }}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: 'var(--radius-xl, 16px)',
              padding: '24px',
              maxWidth: '440px',
              width: '100%',
              boxShadow: 'var(--shadow-xl, 0 20px 25px -5px rgba(0,0,0,0.1))',
            }}
          >
            <h3 style={{ margin: '0 0 8px 0', fontSize: '1.05rem', fontWeight: 800, color: '#0f172a' }}>
              Remove CCTV Camera Feed
            </h3>
            <p style={{ margin: '0 0 20px 0', fontSize: '0.84rem', color: '#64748b', lineHeight: 1.5 }}>
              Are you sure you want to remove <strong>{cameraToRemove.name}</strong> ({cameraToRemove.camera_id})? The video stream will be disconnected.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setCameraToRemove(null)}
                disabled={isRemovingCamera}
                style={{
                  padding: '8px 16px',
                  background: '#f1f5f9',
                  border: 'none',
                  borderRadius: 'var(--radius-md, 8px)',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  color: '#475569',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDeleteCamera}
                disabled={isRemovingCamera}
                style={{
                  padding: '8px 16px',
                  background: '#ef4444',
                  border: 'none',
                  borderRadius: 'var(--radius-md, 8px)',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  color: '#ffffff',
                  cursor: isRemovingCamera ? 'not-allowed' : 'pointer',
                }}
              >
                {isRemovingCamera ? 'Removing...' : 'Confirm Remove'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SurveillancePage;
