import { TrackingFootageItem, Table, Alert } from '../types';

const STORAGE_KEY = 'smartserve_tracking_footages';
const ACTIVE_FOOTAGE_KEY = 'smartserve_active_tracking_footage_id';

export const DEFAULT_TABLES: Table[] = [
  {
    id: 'tbl-01',
    code: 'T-01',
    capacity: 4,
    section: 'Main Dining (Floor 1)',
    status: 'OCCUPIED',
    customerCount: 3,
    lastStateChangeAt: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    assignedWaiter: 'Marco Rossi',
    timeSinceLastAttendanceSec: 120,
    timeSinceFoodDeliverySec: 420,
    hasActiveAlert: false,
  },
  {
    id: 'tbl-02',
    code: 'T-02',
    capacity: 2,
    section: 'Main Dining (Floor 1)',
    status: 'FOOD_DELIVERED',
    customerCount: 2,
    lastStateChangeAt: new Date(Date.now() - 35 * 60 * 1000).toISOString(),
    assignedWaiter: 'Sophia Chen',
    timeSinceLastAttendanceSec: 45,
    timeSinceFoodDeliverySec: 60,
    hasActiveAlert: false,
  },
  {
    id: 'tbl-03',
    code: 'T-03',
    capacity: 6,
    section: 'Main Dining (Floor 1)',
    status: 'NEEDS_ATTENTION',
    customerCount: 5,
    lastStateChangeAt: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
    assignedWaiter: 'Marco Rossi',
    timeSinceLastAttendanceSec: 360,
    hasActiveAlert: true,
    alertSeverity: 'WARNING',
  },
  {
    id: 'tbl-04',
    code: 'T-04',
    capacity: 4,
    section: 'Main Dining (Floor 1)',
    status: 'VACANT',
    customerCount: 0,
    lastStateChangeAt: new Date(Date.now() - 50 * 60 * 1000).toISOString(),
  },
];

export const DEFAULT_ALERTS: Alert[] = [
  {
    id: 'alt-01',
    tableCode: 'T-03',
    type: 'ATTENDANCE_OVERDUE',
    severity: 'WARNING',
    message: 'Table T-03 seated for 6 minutes without staff greeting',
    triggeredAt: new Date(Date.now() - 60 * 1000).toISOString(),
    isAcknowledged: false,
  },
];

export const DEFAULT_TRACKING_FOOTAGES: TrackingFootageItem[] = [
  {
    id: 'cam-01',
    name: 'Main Dining Room (Demo CCTV)',
    floor: 'Floor 1',
    section: 'Floor 1: Main Dining',
    description: 'Indoor dining surveillance video (Cctv-Resturant-Demo) with YOLO26 patron tracking and service time monitoring.',
    videoUrl: '/api/v1/cameras/cam-01/stream/processed',
    rawVideoUrl: '/api/v1/cameras/cam-01/stream/raw',
    resolution: '1280x720',
    fps: 30,
    isCustom: false,
    modelName: 'Fine-tuned YOLO26s (Restaurant CCTV)',
    detectionsCount: 8,
    tables: DEFAULT_TABLES,
    alerts: DEFAULT_ALERTS,
    status: 'Monitoring',
    cameraHealth: 'HEALTHY',
    inferenceStatus: 'ACTIVE',
    effectiveFps: 29.8,
    latencyMs: 14.8,
    lastEventTime: 'Just now',
    lastEventDescription: 'Table T-01 Occupied (3 patrons)',
    sourceType: 'video',
    processingJobId: 'job-f1-01',
  },
];

type FootageChangeCallback = (newActive: TrackingFootageItem) => void;
const subscribers: Set<FootageChangeCallback> = new Set();
const CUSTOM_FLOORS_KEY = 'smartserve_custom_floors';

export function getStoredTrackingFootages(): TrackingFootageItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === null) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_TRACKING_FOOTAGES));
      return DEFAULT_TRACKING_FOOTAGES;
    }
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      // Auto-migrate legacy 3-source mock setup to the single requested project demo video
      if (parsed.some((f) => f.name === 'Main Dining Room (Cam 01)' || f.name === 'Patio Terrace (Cam 02)')) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_TRACKING_FOOTAGES));
        localStorage.setItem(ACTIVE_FOOTAGE_KEY, DEFAULT_TRACKING_FOOTAGES[0].id);
        return DEFAULT_TRACKING_FOOTAGES;
      }
      if (parsed.length === 0) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_TRACKING_FOOTAGES));
        return DEFAULT_TRACKING_FOOTAGES;
      }
      return parsed.map((item) => ({
        ...item,
        floor: item.floor || (item.name?.includes('Floor 2') ? 'Floor 2' : 'Floor 1'),
        status: item.status || 'Monitoring',
        cameraHealth: item.cameraHealth || 'HEALTHY',
        inferenceStatus: item.inferenceStatus || 'ACTIVE',
        effectiveFps: item.effectiveFps || item.fps || 30,
        lastEventTime: item.lastEventTime || 'Just now',
        tables: Array.isArray(item.tables) && item.tables.length > 0 ? item.tables : DEFAULT_TABLES,
        alerts: Array.isArray(item.alerts) ? item.alerts : DEFAULT_ALERTS,
      }));
    }
    return DEFAULT_TRACKING_FOOTAGES;
  } catch {
    return DEFAULT_TRACKING_FOOTAGES;
  }
}

export function saveTrackingFootages(footages: TrackingFootageItem[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(footages));
  } catch (err) {
    console.error('Failed to save tracking footages to localStorage', err);
  }
}

export function getActiveTrackingFootage(): TrackingFootageItem {
  const footages = getStoredTrackingFootages();
  try {
    const activeId = localStorage.getItem(ACTIVE_FOOTAGE_KEY);
    const found = footages.find((f) => f.id === activeId);
    if (found) return found;
  } catch {
    // fallback
  }
  return footages[0] || DEFAULT_TRACKING_FOOTAGES[0];
}

export function setActiveTrackingFootage(footageId: string): TrackingFootageItem {
  const footages = getStoredTrackingFootages();
  const selected = footages.find((f) => f.id === footageId) || footages[0] || DEFAULT_TRACKING_FOOTAGES[0];
  try {
    localStorage.setItem(ACTIVE_FOOTAGE_KEY, selected.id);
  } catch {
    // ignore
  }

  notifySubscribers(selected);
  return selected;
}

function notifySubscribers(selectedItem: TrackingFootageItem): void {
  subscribers.forEach((cb) => {
    try {
      cb(selectedItem);
    } catch (e) {
      console.error('Error notifying tracking footage subscriber', e);
    }
  });
}

/**
 * Automates the Phase 4 registration pipeline lifecycle:
 * Added -> Validating -> Initializing Model -> Monitoring
 * Does NOT interrupt other running tracking feeds!
 */
export function startTrackingPipeline(footageId: string): void {
  // Step 1: Initial state is 'Added'
  updateFootageState(footageId, {
    status: 'Added',
    cameraHealth: 'HEALTHY',
    inferenceStatus: 'INITIALIZING',
    lastEventTime: 'Source Registered',
    lastEventDescription: 'Validating stream format and network latency...',
  });

  // Step 2: Transition to 'Validating' at +600ms
  setTimeout(() => {
    updateFootageState(footageId, {
      status: 'Validating',
      inferenceStatus: 'INITIALIZING',
      lastEventTime: 'Validating',
      lastEventDescription: 'Inspecting RTSP stream & camera resolution...',
    });
  }, 600);

  // Step 3: Transition to 'Initializing Model' at +1300ms
  setTimeout(() => {
    updateFootageState(footageId, {
      status: 'Initializing Model',
      inferenceStatus: 'INITIALIZING',
      lastEventTime: 'Loading YOLO26',
      lastEventDescription: 'Loading fine-tuned YOLO26s weights & ByteTrack config...',
    });
  }, 1300);

  // Step 4: Transition to 'Monitoring' at +2200ms
  setTimeout(() => {
    updateFootageState(footageId, {
      status: 'Monitoring',
      cameraHealth: 'HEALTHY',
      inferenceStatus: 'ACTIVE',
      effectiveFps: 29.6,
      latencyMs: 15.2,
      lastEventTime: 'Just now',
      lastEventDescription: 'YOLO26 inference active — tracking patrons and table occupancy',
    });
  }, 2200);
}

function updateFootageState(footageId: string, patch: Partial<TrackingFootageItem>): void {
  const current = getStoredTrackingFootages();
  const target = current.find((f) => f.id === footageId);
  if (!target) return;

  const updated = current.map((f) => {
    if (f.id === footageId) {
      return { ...f, ...patch };
    }
    return f;
  });

  saveTrackingFootages(updated);
  const active = getActiveTrackingFootage();
  if (active.id === footageId) {
    notifySubscribers({ ...active, ...patch });
  } else {
    notifySubscribers(active);
  }
}

export function pauseTrackingFootage(footageId: string): void {
  updateFootageState(footageId, {
    status: 'Paused',
    inferenceStatus: 'PAUSED',
    lastEventDescription: 'Monitoring paused by manager',
  });
}

export function resumeTrackingFootage(footageId: string): void {
  updateFootageState(footageId, {
    status: 'Monitoring',
    inferenceStatus: 'ACTIVE',
    lastEventDescription: 'YOLO26 inference resumed',
  });
}

export function removeTrackingFootage(footageId: string): TrackingFootageItem[] {
  const current = getStoredTrackingFootages();
  const currentActiveId = localStorage.getItem(ACTIVE_FOOTAGE_KEY) || (current[0]?.id ?? '');
  const remaining = current.filter((f) => f.id !== footageId);
  saveTrackingFootages(remaining);

  if (currentActiveId === footageId) {
    if (remaining.length > 0) {
      setActiveTrackingFootage(remaining[0].id);
    } else {
      localStorage.removeItem(ACTIVE_FOOTAGE_KEY);
      const emptyStateItem: TrackingFootageItem = {
        id: 'none',
        name: 'No Active Sources',
        floor: 'None',
        section: 'None',
        description: 'No tracking sources currently registered',
        videoUrl: '',
        rawVideoUrl: '',
        resolution: '1280x720',
        fps: 0,
        isCustom: false,
        modelName: 'Fine-tuned YOLO26s',
        detectionsCount: 0,
        tables: [],
        alerts: [],
        status: 'Stopped',
        cameraHealth: 'HEALTHY',
        inferenceStatus: 'IDLE',
      };
      notifySubscribers(emptyStateItem);
    }
  } else {
    const active = remaining.find((f) => f.id === currentActiveId) || remaining[0];
    if (active) {
      notifySubscribers(active);
    }
  }

  return remaining;
}

export function resetToDemoFootage(): TrackingFootageItem[] {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_TRACKING_FOOTAGES));
  localStorage.setItem(ACTIVE_FOOTAGE_KEY, DEFAULT_TRACKING_FOOTAGES[0].id);
  notifySubscribers(DEFAULT_TRACKING_FOOTAGES[0]);
  return DEFAULT_TRACKING_FOOTAGES;
}

export function addTrackingFootage(newFootage: TrackingFootageItem): TrackingFootageItem[] {
  const current = getStoredTrackingFootages();
  const formattedItem: TrackingFootageItem = {
    ...newFootage,
    status: 'Added',
    cameraHealth: 'HEALTHY',
    inferenceStatus: 'INITIALIZING',
    lastEventTime: 'Just now',
    lastEventDescription: 'Source added. Initiating YOLO26 pipeline...',
  };

  const updated = [...current.filter((f) => f.id !== formattedItem.id), formattedItem];
  saveTrackingFootages(updated);
  setActiveTrackingFootage(formattedItem.id);

  // Trigger automated pipeline without interrupting other sources
  startTrackingPipeline(formattedItem.id);

  return updated;
}

export function getAvailableFloors(): string[] {
  const footages = getStoredTrackingFootages();
  const set = new Set<string>();
  // Defaults
  set.add('Floor 1');
  set.add('Floor 2');

  footages.forEach((f) => {
    if (f.floor) set.add(f.floor);
  });

  try {
    const custom = localStorage.getItem(CUSTOM_FLOORS_KEY);
    if (custom) {
      const arr = JSON.parse(custom);
      if (Array.isArray(arr)) {
        arr.forEach((item) => set.add(item));
      }
    }
  } catch {
    // ignore
  }

  return Array.from(set).sort();
}

export function addCustomFloor(floorName: string): string[] {
  const clean = floorName.trim();
  if (!clean) return getAvailableFloors();

  const current = getAvailableFloors();
  if (!current.includes(clean)) {
    current.push(clean);
    try {
      localStorage.setItem(CUSTOM_FLOORS_KEY, JSON.stringify(current));
    } catch {
      // ignore
    }
  }
  return current;
}

export function subscribeToFootageChanges(callback: FootageChangeCallback): () => void {
  subscribers.add(callback);
  return () => {
    subscribers.delete(callback);
  };
}
