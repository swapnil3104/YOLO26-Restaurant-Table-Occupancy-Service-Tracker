import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { Sidebar, ActivePage } from './components/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
import { SurveillanceVisionPage } from './pages/SurveillanceVisionPage';
import { AnalyticsReportsPage } from './pages/AnalyticsReportsPage';
import { AddTrackingFootageModal } from './components/AddTrackingFootageModal';
import { CameraFeed, Table, Alert, StaffUser, TrackingFootageItem } from './types';
import { 
  fetchCameras, 
  fetchAlerts, 
  fetchTables,
  getCurrentActor, 
  setCurrentActor 
} from './services/api';
import { 
  getActiveTrackingFootage, 
  getStoredTrackingFootages, 
  setActiveTrackingFootage, 
  subscribeToFootageChanges 
} from './services/trackingFootages';
import { useRealtime } from './hooks/useRealtime';
import { soundService } from './services/sound';

export const App: React.FC = () => {
  const getInitialPage = (): ActivePage => {
    const hash = window.location.hash.toLowerCase();
    if (hash.includes('tracking') || hash.includes('camera') || hash.includes('surveillance')) {
      return 'cameras';
    }
    if (hash.includes('analytics') || hash.includes('report')) {
      return 'analytics';
    }
    return 'dashboard';
  };

  // Navigation state (supports hash routes #tracking, #cameras, #analytics)
  const [activePage, setActivePage] = useState<ActivePage>(getInitialPage);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [soundAlertsEnabled, setSoundAlertsEnabled] = useState(true);

  useEffect(() => {
    const handleHash = () => {
      setActivePage(getInitialPage());
    };
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  // Tracking Footage Library & Active Footage State
  const [footages, setFootages] = useState<TrackingFootageItem[]>(getStoredTrackingFootages());
  const [activeFootage, setActiveFootage] = useState<TrackingFootageItem>(getActiveTrackingFootage());
  const [isAddFootageModalOpen, setIsAddFootageModalOpen] = useState<boolean>(false);

  // Application Data States (driven by active tracking footage)
  const [cameras, setCameras] = useState<CameraFeed[]>([]);
  const [tables, setTables] = useState<Table[]>(activeFootage.tables);
  const [alerts, setAlerts] = useState<Alert[]>(activeFootage.alerts);
  const [currentActor, setActor] = useState<StaffUser>(getCurrentActor());

  // Real-time Data Freshness timestamp
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  // Subscribe to tracking footage changes across the entire app
  useEffect(() => {
    const unsubscribe = subscribeToFootageChanges((newActive) => {
      const stored = getStoredTrackingFootages();
      setFootages(stored);
      if (newActive && newActive.id !== 'none') {
        setActiveFootage(newActive);
        setTables(newActive.tables || []);
        setAlerts(newActive.alerts || []);
      } else if (stored.length > 0) {
        setActiveFootage(stored[0]);
        setTables(stored[0].tables || []);
        setAlerts(stored[0].alerts || []);
      } else {
        setTables([]);
        setAlerts([]);
      }
      setLastUpdated(new Date());
    });
    return unsubscribe;
  }, []);

  // Master Cameras & Sync Refresh Callback
  const loadData = useCallback(async () => {
    try {
      const stored = getStoredTrackingFootages();
      setFootages(stored);
      const [camsData, alertsData, tablesData] = await Promise.all([
        fetchCameras(),
        fetchAlerts(),
        fetchTables(),
      ]);
      setCameras(camsData);
      if (tablesData && tablesData.length > 0) {
        setTables(tablesData);
      }
      // Merge active alerts with active footage alerts
      if (alertsData.length > 0) {
        setAlerts((prev) => {
          const combined = [...prev];
          alertsData.forEach((a) => {
            if (!combined.some((c) => c.id === a.id)) {
              combined.push(a);
            }
          });
          return combined;
        });
      }
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Error fetching operational state:', err);
    }
  }, []);

  // Initial Load & Polling Fallback (every 8s)
  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 8000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Real-time WebSocket listener
  const { connectionStatus } = useRealtime({
    onMessage: (msg) => {
      if (msg.type === 'alert' && soundAlertsEnabled) {
        soundService.playAlertPing();
      }
      if (msg.type === 'event' || msg.type === 'alert' || msg.type === 'occupancy') {
        loadData();
      }
    },
  });

  const handleActorChange = (user: StaffUser) => {
    setActor(user);
    setCurrentActor(user);
    loadData();
  };

  const handleToggleSound = () => {
    const next = !soundAlertsEnabled;
    setSoundAlertsEnabled(next);
    soundService.setEnabled(next);
    if (next) {
      soundService.playChime();
    }
  };

  const handleSelectFootage = (footageId: string) => {
    setActiveTrackingFootage(footageId);
  };

  return (
    <div className="app-container">
      {/* Persistent Left Sidebar */}
      <Sidebar
        activePage={activePage}
        onPageChange={setActivePage}
        activeAlertsCount={alerts.filter(a => !a.isAcknowledged).length}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main App Content Area */}
      <div className="main-content">
        {/* Top Header with Global Active Tracking Channel Switcher */}
        <Header
          connectionStatus={connectionStatus}
          lastUpdated={lastUpdated}
          onRefresh={loadData}
          onActorChange={handleActorChange}
          soundAlertsEnabled={soundAlertsEnabled}
          onToggleSoundAlerts={handleToggleSound}
          activeFootage={activeFootage}
          footages={footages}
          onSelectFootage={handleSelectFootage}
          onOpenAddFootage={() => setIsAddFootageModalOpen(true)}
        />

        {/* Dynamic Page Routing */}
        <main style={{ flex: 1, minHeight: 0 }}>
          {activePage === 'dashboard' && (
            <DashboardPage
              tables={tables}
              alerts={alerts}
              currentActor={currentActor}
              onRefresh={loadData}
            />
          )}

          {activePage === 'cameras' && (
            <SurveillanceVisionPage
              cameras={cameras}
              onRefresh={loadData}
              activeFootage={activeFootage}
              footages={footages}
              onSelectFootage={handleSelectFootage}
              onOpenAddFootage={() => setIsAddFootageModalOpen(true)}
            />
          )}

          {activePage === 'analytics' && (
            <AnalyticsReportsPage
              tables={tables}
              currentActor={currentActor}
              onRefresh={loadData}
            />
          )}
        </main>
      </div>

      {/* Global Add Tracking Footage Modal */}
      <AddTrackingFootageModal
        isOpen={isAddFootageModalOpen}
        onClose={() => setIsAddFootageModalOpen(false)}
        onFootageAdded={(newFootage) => {
          setActiveTrackingFootage(newFootage.id);
        }}
      />
    </div>
  );
};

export default App;

