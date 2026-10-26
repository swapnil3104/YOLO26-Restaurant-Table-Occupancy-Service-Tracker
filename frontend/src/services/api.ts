/**
 * SmartServe AI - REST API and Streaming Client
 */

import {
  Alert,
  AnalyticsBreakdown,
  AnalyticsFilterParams,
  AnalyticsSummary,
  CameraFeed,
  CVTelemetry,
  StaffUser,
  Table,
  TableStatus,
  TimelineItem,
  VideoSourceItem,
  VideoAssignments,
  VideoSourcesResponse,
  FloorAnalyticsResponse,
} from '../types';

const API_BASE = (import.meta as any).env?.VITE_API_URL || '';

// Pre-seeded staff users matching backend database
export const DEMO_USERS: StaffUser[] = [
  {
    user_id: 'usr_mgr',
    username: 'manager',
    display_name: 'Morgan Manager',
    role: 'MANAGER',
    active: true,
  },
  {
    user_id: 'usr_waiter1',
    username: 'waiter1',
    display_name: 'Sam Waiter',
    role: 'WAITER',
    active: true,
  },
  {
    user_id: 'usr_admin',
    username: 'admin',
    display_name: 'Alex Administrator',
    role: 'ADMIN',
    active: true,
  },
];

let currentActor: StaffUser = DEMO_USERS[0]; // Default to Manager for full dashboard access

export function setCurrentActor(user: StaffUser) {
  currentActor = user;
}

export function getCurrentActor(): StaffUser {
  return currentActor;
}

function getHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    'X-User-ID': currentActor.user_id,
  };
}

// ---------------------------------------------------------------------------
// Cameras & Streaming
// ---------------------------------------------------------------------------

export async function fetchCameras(): Promise<CameraFeed[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/cameras`, { headers: getHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Using fallback camera list:', err);
    return [
      {
        camera_id: 'cam-01',
        name: 'Main Dining Room (Cam 01)',
        section: 'Main Dining',
        status: 'ONLINE',
        resolution: '1280x720',
        fps: 30.0,
        last_frame_at: new Date().toISOString(),
        raw_stream_url: `${API_BASE}/api/v1/cameras/cam-01/stream/raw`,
        processed_stream_url: `${API_BASE}/api/v1/cameras/cam-01/stream/processed`,
        cv_metadata_url: `${API_BASE}/api/v1/cameras/cam-01/cv-metadata`,
      },
      {
        camera_id: 'cam-02',
        name: 'Patio Terrace (Cam 02)',
        section: 'Patio Terrace',
        status: 'ONLINE',
        resolution: '1280x720',
        fps: 25.0,
        last_frame_at: new Date().toISOString(),
        raw_stream_url: `${API_BASE}/api/v1/cameras/cam-02/stream/raw`,
        processed_stream_url: `${API_BASE}/api/v1/cameras/cam-02/stream/processed`,
        cv_metadata_url: `${API_BASE}/api/v1/cameras/cam-02/cv-metadata`,
      },
      {
        camera_id: 'cam-03',
        name: 'Window Booths & Bar (Cam 03)',
        section: 'Window Booth',
        status: 'ONLINE',
        resolution: '1280x720',
        fps: 30.0,
        last_frame_at: new Date().toISOString(),
        raw_stream_url: `${API_BASE}/api/v1/cameras/cam-03/stream/raw`,
        processed_stream_url: `${API_BASE}/api/v1/cameras/cam-03/stream/processed`,
        cv_metadata_url: `${API_BASE}/api/v1/cameras/cam-03/cv-metadata`,
      },
      {
        camera_id: 'cam-04',
        name: 'Private Dining Lounge (Cam 04)',
        section: 'Private Lounge',
        status: 'ONLINE',
        resolution: '1280x720',
        fps: 30.0,
        last_frame_at: new Date().toISOString(),
        raw_stream_url: `${API_BASE}/api/v1/cameras/cam-04/stream/raw`,
        processed_stream_url: `${API_BASE}/api/v1/cameras/cam-04/stream/processed`,
        cv_metadata_url: `${API_BASE}/api/v1/cameras/cam-04/cv-metadata`,
      },
    ];
  }
}

export async function fetchCameraCVMetadata(cameraId: string): Promise<CVTelemetry | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/cameras/${cameraId}/cv-metadata`, { headers: getHeaders() });
    if (!res.ok) {
      const fallbackRes = await fetch(`${API_BASE}/api/v1/cameras/cam-01/cv-metadata`, { headers: getHeaders() });
      if (fallbackRes.ok) return await fallbackRes.json();
      throw new Error(`HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.warn(`Failed fetching CV telemetry for ${cameraId}:`, err);
    return null;
  }
}

export async function createCameraFeed(payload: {
  name: string;
  floor: string;
  section: string;
  source_type: 'live_stream' | 'recorded_footage';
  stream_url?: string;
  video_file_id?: string;
}): Promise<CameraFeed> {
  const res = await fetch(`${API_BASE}/api/v1/cameras`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || `Failed to create camera: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function updateCameraFeed(
  cameraId: string,
  payload: { name?: string; floor?: string; section?: string; status?: string }
): Promise<CameraFeed> {
  const res = await fetch(`${API_BASE}/api/v1/cameras/${cameraId}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || `Failed to update camera: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function deleteCameraFeed(cameraId: string): Promise<{ status: string; message: string; camera_id: string }> {
  const res = await fetch(`${API_BASE}/api/v1/cameras/${cameraId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || `Failed to delete camera: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function uploadCCTVVideoFile(file: File): Promise<{
  status: string;
  video_id: string;
  filename: string;
  url: string;
  size_bytes: number;
  source_label: string;
}> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/api/v1/cameras/upload`, {
    method: 'POST',
    headers: {
      'X-User-ID': currentActor.user_id,
    },
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || `File upload failed: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchVideoSources(): Promise<VideoSourcesResponse> {
  const fallbackSources: VideoSourceItem[] = [
    {
      id: 'vid_yolo_tracked',
      name: 'YOLO26 & ByteTrack Tracking Feed (Main Dining)',
      description: 'Neural computer vision tracking with ByteTrack person IDs, bounding boxes, ground-contact points, and dining table zones.',
      category: 'tracking',
      filename: 'yolo_tracked_camera_01.mp4',
      url: '/videos/yolo_tracked_camera_01.mp4',
      resolution: '1280x720',
      fps: 30.0,
      duration_sec: 30.0,
      is_annotated: true,
      recommended_view: 'tracking',
    },
    {
      id: 'vid_table_edge_tracker',
      name: 'Table Edge Detection & Proximity Tracker',
      description: 'Sub-pixel table border detection, glowing neon active table edges, diner proximity vectors, and occupancy status classification.',
      category: 'tracking',
      filename: 'output_annotated_cctv.mp4',
      url: '/videos/output_annotated_cctv.mp4',
      resolution: '1280x720',
      fps: 25.0,
      duration_sec: 24.0,
      is_annotated: true,
      recommended_view: 'tracking',
    },
    {
      id: 'vid_cctv_dining',
      name: 'CAM-01: Main Dining Room (Raw CCTV)',
      description: 'Unprocessed 1080p surveillance video of the central dining floor, 6 tables, active patrons and waiters.',
      category: 'standard_cctv',
      filename: 'cctv_camera_01_main_dining_raw.mp4',
      url: '/videos/cctv_camera_01_main_dining_raw.mp4',
      resolution: '1280x720',
      fps: 30.0,
      duration_sec: 30.0,
      is_annotated: false,
      recommended_view: 'standard',
    },
    {
      id: 'vid_cctv_patio',
      name: 'CAM-02: Patio Terrace (Raw CCTV)',
      description: 'Outdoor terrace tables and patio perimeter surveillance feed.',
      category: 'standard_cctv',
      filename: 'cctv_camera_02_patio.mp4',
      url: '/videos/cctv_camera_02_patio.mp4',
      resolution: '1280x720',
      fps: 25.0,
      duration_sec: 18.0,
      is_annotated: false,
      recommended_view: 'standard',
    },
    {
      id: 'vid_cctv_booths',
      name: 'CAM-03: Window Booths & Bar Area (Raw CCTV)',
      description: 'Window-side booths, beverage counter, and dining lounge surveillance feed.',
      category: 'standard_cctv',
      filename: 'cctv_camera_03_booths.mp4',
      url: '/videos/cctv_camera_03_booths.mp4',
      resolution: '1280x720',
      fps: 30.0,
      duration_sec: 15.0,
      is_annotated: false,
      recommended_view: 'standard',
    },
  ];

  const fallbackAssignments: VideoAssignments = {
    tracking_video_id: 'vid_yolo_tracked',
    standard_video_id: 'vid_cctv_dining',
    camera_assignments: {
      'cam-01': 'vid_cctv_dining',
      'cam-02': 'vid_cctv_patio',
      'cam-03': 'vid_cctv_booths',
      'cam-04': 'vid_cctv_dining',
    },
  };

  try {
    const res = await fetch(`${API_BASE}/api/v1/cameras/video-sources`, { headers: getHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Using local video catalog fallback:', err);
    return {
      sources: fallbackSources,
      assignments: fallbackAssignments,
    };
  }
}

export async function assignVideoSources(payload: Partial<VideoAssignments>): Promise<VideoSourcesResponse> {
  const res = await fetch(`${API_BASE}/api/v1/cameras/video-sources/assign`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Failed to assign video source: HTTP ${res.status}`);
  }
  return await res.json();
}

// ---------------------------------------------------------------------------
// Tables & Occupancy
// ---------------------------------------------------------------------------

export async function fetchTables(): Promise<Table[]> {
  try {
    // 1. Fetch table layouts
    const [tablesRes, occupancyRes] = await Promise.all([
      fetch(`${API_BASE}/api/v1/tables`, { headers: getHeaders() }),
      fetch(`${API_BASE}/api/v1/occupancy`, { headers: getHeaders() }),
    ]);

    if (!tablesRes.ok) throw new Error(`Tables HTTP ${tablesRes.status}`);
    const tableConfigs = await tablesRes.json();
    const occupancyData = occupancyRes.ok ? await occupancyRes.json() : {};

    const mappedTables = tableConfigs.map((cfg: any, index: number) => {
      const occ = occupancyData[cfg.id] || {};
      const rawState = occ.current_state || occ.state || cfg.status || 'AVAILABLE';
      let status: TableStatus = 'VACANT';
      if (rawState === 'AVAILABLE' || rawState === 'VACANT') {
        status = 'VACANT';
      } else if (rawState === 'OCCUPIED' || rawState === 'POSSIBLY_OCCUPIED') {
        const activeSess = occ.active_session;
        if (activeSess?.service_status === 'ATTENDED') {
          status = 'ATTENDED';
        } else if (activeSess?.service_status === 'SERVED' || activeSess?.service_status === 'PARTIALLY_SERVED') {
          status = 'FOOD_DELIVERED';
        } else {
          status = 'OCCUPIED';
        }
      } else if (rawState === 'CLEANING_REQUIRED') {
        status = 'CLEANING_REQUIRED';
      } else if (rawState === 'ATTENDED') {
        status = 'ATTENDED';
      } else if (rawState === 'FOOD_DELIVERED') {
        status = 'FOOD_DELIVERED';
      } else if (rawState === 'NEEDS_ATTENTION') {
        status = 'NEEDS_ATTENTION';
      } else {
        status = (rawState as TableStatus) || 'VACANT';
      }

      const activeSession = occ.active_session;
      const customerCount = occ.estimated_customer_count ?? occ.customer_count ?? (activeSession?.estimated_customer_count ?? (status === 'VACANT' ? 0 : 2));
      const sessionId = activeSession?.session_id || occ.session_id;
      const sessionStartedAt = activeSession?.start_time || occ.session_started_at;
      const rawChangeTime = occ.last_state_change || occ.state_changed_at;
      const lastStateChangeAt = rawChangeTime ? new Date(rawChangeTime).toLocaleTimeString() : 'Just now';

      return {
        id: cfg.id,
        code: cfg.code || `T0${index + 1}`,
        capacity: cfg.capacity || 4,
        section: cfg.section || 'Main Dining',
        status: status,
        customerCount: customerCount,
        currentSessionId: sessionId,
        sessionStartedAt: sessionStartedAt,
        lastStateChangeAt: lastStateChangeAt,
        assignedWaiter: 'Sam Waiter',
        timeSinceLastAttendanceSec: occ.time_since_last_attendance_sec,
        timeSinceFoodDeliverySec: occ.time_since_food_delivery_sec,
        hasActiveAlert: status === 'NEEDS_ATTENTION' || (status === 'OCCUPIED' && ((occ.time_since_last_attendance_sec || 0) > 180)),
        alertSeverity: status === 'NEEDS_ATTENTION' ? 'WARNING' : undefined,
      };
    });

    // 3. Overlay live vision detections from camera stream if available
    try {
      const cvData = await fetchCameraCVMetadata('cam-01');
      if (cvData?.tables && Array.isArray(cvData.tables)) {
        cvData.tables.forEach((cvT: any) => {
          const cvCode = (cvT.table_id || '').replace('-', '').toLowerCase();
          const matched = mappedTables.find(
            (t: any) => t.code.replace('-', '').toLowerCase() === cvCode || t.id.replace('-', '').toLowerCase() === cvCode
          );
          if (matched && cvT.status && cvT.status !== 'VACANT') {
            matched.status = cvT.status;
            if (cvT.estimated_customers > 0) {
              matched.customerCount = cvT.estimated_customers;
            }
          }
        });
      }
    } catch {
      // non-critical
    }

    return mappedTables;
  } catch (err) {
    console.warn('Using fallback tables state:', err);
    return [
      {
        id: 'table-01',
        code: 'T01',
        capacity: 4,
        section: 'Main Dining',
        status: 'OCCUPIED',
        customerCount: 3,
        currentSessionId: 'sess-01',
        sessionStartedAt: new Date(Date.now() - 25 * 60000).toISOString(),
        lastStateChangeAt: '25m ago',
        assignedWaiter: 'Alex Waiter',
        timeSinceLastAttendanceSec: 320,
        hasActiveAlert: true,
        alertSeverity: 'WARNING',
      },
      {
        id: 'table-02',
        code: 'T02',
        capacity: 2,
        section: 'Main Dining',
        status: 'ATTENDED',
        customerCount: 2,
        currentSessionId: 'sess-02',
        sessionStartedAt: new Date(Date.now() - 15 * 60000).toISOString(),
        lastStateChangeAt: '12m ago',
        assignedWaiter: 'Sarah K.',
        timeSinceLastAttendanceSec: 120,
        timeSinceFoodDeliverySec: 680,
      },
      {
        id: 'table-03',
        code: 'T03',
        capacity: 6,
        section: 'Patio Terrace',
        status: 'FOOD_DELIVERED',
        customerCount: 5,
        currentSessionId: 'sess-03',
        sessionStartedAt: new Date(Date.now() - 40 * 60000).toISOString(),
        lastStateChangeAt: '8m ago',
        assignedWaiter: 'Alex Waiter',
        timeSinceFoodDeliverySec: 240,
      },
      {
        id: 'table-04',
        code: 'T04',
        capacity: 4,
        section: 'Patio Terrace',
        status: 'VACANT',
        customerCount: 0,
        lastStateChangeAt: '45m ago',
      },
      {
        id: 'table-05',
        code: 'T05',
        capacity: 4,
        section: 'Window Booth',
        status: 'CLEANING_REQUIRED',
        customerCount: 0,
        lastStateChangeAt: '3m ago',
        assignedWaiter: 'Sarah K.',
      },
      {
        id: 'table-06',
        code: 'T06',
        capacity: 8,
        section: 'Private Lounge',
        status: 'VACANT',
        customerCount: 0,
        lastStateChangeAt: '1h ago',
      },
    ];
  }
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export async function fetchAlerts(): Promise<Alert[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/alerts?status=ACTIVE`, { headers: getHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.map((a: any) => ({
      id: a.alert_id,
      tableCode: a.table_id || 'T01',
      type: a.alert_type,
      severity: a.severity,
      message: a.metadata_json?.message || a.message || `${a.alert_type} on table ${a.table_id || 'T01'}`,
      triggeredAt: new Date(a.created_at || a.triggered_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      isAcknowledged: a.status === 'ACKNOWLEDGED',
      dedupKey: a.dedup_key,
    }));
  } catch (err) {
    return [
      {
        id: 'alt-1',
        tableCode: 'T01',
        type: 'ATTENDANCE_OVERDUE',
        severity: 'WARNING',
        message: 'Table T01 seated 5m ago with no recorded waiter greeting.',
        triggeredAt: '5m ago',
        isAcknowledged: false,
      },
      {
        id: 'alt-2',
        tableCode: 'T02',
        type: 'FOOD_DELIVERY_OVERDUE',
        severity: 'INFO',
        message: 'Table T02 greeting confirmed; kitchen order pending delivery.',
        triggeredAt: '12m ago',
        isAcknowledged: true,
      },
    ];
  }
}

export async function acknowledgeAlert(alertId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/alerts/${alertId}/acknowledge?user_id=${currentActor.user_id}`, {
      method: 'POST',
      headers: getHeaders(),
    });
    return res.ok;
  } catch (err) {
    console.error('Failed to acknowledge alert:', err);
    return false;
  }
}

export async function resolveAlert(alertId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/alerts/${alertId}/resolve?user_id=${currentActor.user_id}`, {
      method: 'POST',
      headers: getHeaders(),
    });
    return res.ok;
  } catch (err) {
    console.error('Failed to resolve alert:', err);
    return false;
  }
}

// ---------------------------------------------------------------------------
// Service Timeline & Confirmations
// ---------------------------------------------------------------------------

export async function fetchSessionTimeline(sessionId: string): Promise<TimelineItem[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}/timeline`, { headers: getHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.items.map((item: any) => ({
      id: item.event_id,
      eventType: item.event_type,
      displayName: item.display_name,
      timestamp: item.timestamp,
      relativeTime: item.relative_time,
      badgeText: item.badge_text,
      badgeVariant: item.badge_variant,
      actor: item.actor_display_name,
      source: item.source,
      verificationStatus: item.verification_status,
      isMilestone: item.is_milestone,
      course: item.course,
      notes: item.notes,
    }));
  } catch (err) {
    return [
      {
        id: 'ev-1',
        eventType: 'TABLE_OCCUPIED',
        displayName: 'Guests Seated',
        timestamp: new Date(Date.now() - 25 * 60000).toISOString(),
        relativeTime: '25m ago',
        badgeText: 'AI Vision Estimate (Confirmed)',
        badgeVariant: 'candidate',
        source: 'AI_OBSERVATION',
        verificationStatus: 'CONFIRMED',
        isMilestone: true,
      },
      {
        id: 'ev-2',
        eventType: 'FIRST_ATTENDANCE',
        displayName: 'First Attendance Recorded',
        timestamp: new Date(Date.now() - 21 * 60000).toISOString(),
        relativeTime: '21m ago',
        badgeText: 'Confirmed by Waiter (Alex Waiter)',
        badgeVariant: 'confirmed',
        actor: 'Alex Waiter',
        source: 'WAITER_UI',
        verificationStatus: 'CONFIRMED',
        isMilestone: true,
      },
      {
        id: 'ev-3',
        eventType: 'FOOD_DELIVERY',
        displayName: 'Food Delivery (Batch 1)',
        timestamp: new Date(Date.now() - 8 * 60000).toISOString(),
        relativeTime: '8m ago',
        badgeText: 'Confirmed by Waiter (Alex Waiter)',
        badgeVariant: 'confirmed',
        actor: 'Alex Waiter',
        source: 'WAITER_UI',
        verificationStatus: 'CONFIRMED',
        isMilestone: true,
        course: 'Appetizers & Mains',
      },
    ];
  }
}

export async function confirmAttendance(tableId: string, sessionId?: string): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/events/attendance`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        table_id: tableId,
        session_id: sessionId,
      }),
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || `HTTP ${res.status}`);
    }
    return { success: true, message: 'Waiter attendance confirmed successfully.' };
  } catch (err: any) {
    return { success: false, message: err.message || 'Failed to confirm attendance' };
  }
}

export async function confirmFoodDelivery(
  tableId: string,
  sessionId?: string,
  course = 'Mains',
  batchNumber = 1
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/events/food-delivery`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        table_id: tableId,
        session_id: sessionId,
        course,
        batch_number: batchNumber,
      }),
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || `HTTP ${res.status}`);
    }
    return { success: true, message: `Food delivery (${course} - Batch #${batchNumber}) confirmed.` };
  } catch (err: any) {
    return { success: false, message: err.message || 'Failed to confirm food delivery' };
  }
}

export async function overrideTableState(
  tableId: string,
  targetState: string,
  customerCount = 2,
  reason = 'Walk-in party seated'
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/occupancy/${tableId}/override`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        target_state: targetState,
        customer_count: customerCount,
        actor: currentActor.username,
        reason: reason,
      }),
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || `HTTP ${res.status}`);
    }
    return { success: true, message: `Table state updated to ${targetState}.` };
  } catch (err: any) {
    return { success: false, message: err.message || 'Failed to update table state' };
  }
}

export async function cleanTable(tableId: string): Promise<{ success: boolean; message: string }> {
  try {
    // Call /clean or /cleaned endpoint
    const res = await fetch(`${API_BASE}/api/v1/occupancy/${tableId}/clean`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        actor: currentActor.username,
        reason: 'Table sanitized and reset by staff',
      }),
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || `HTTP ${res.status}`);
    }
    return { success: true, message: 'Table sanitized and reset to Available.' };
  } catch (err: any) {
    return { success: false, message: err.message || 'Failed to reset table' };
  }
}

// ---------------------------------------------------------------------------
// Analytics & Export
// ---------------------------------------------------------------------------

function buildQueryString(params?: Record<string, any>): string {
  if (!params) return '';
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== '') {
      searchParams.append(key, String(val));
    }
  });
  const qs = searchParams.toString();
  return qs ? `?${qs}` : '';
}

export async function fetchAnalyticsSummary(filters?: AnalyticsFilterParams): Promise<AnalyticsSummary> {
  const qs = buildQueryString(filters);
  try {
    const res = await fetch(`${API_BASE}/api/v1/analytics/summary${qs}`, { headers: getHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data: AnalyticsSummary = await res.json();
    // Populate convenience fields for backward compatibility
    if (data && data.kpis) {
      data.median_response_time_seconds = data.kpis.median_first_attendance_sec;
      data.median_food_delivery_seconds = data.kpis.median_food_delivery_sec;
      data.average_occupancy_duration_minutes =
        data.kpis.average_occupancy_duration_sec != null
          ? Number((data.kpis.average_occupancy_duration_sec / 60).toFixed(1))
          : null;
      data.turnover_rate_per_hour = data.kpis.table_turnover_rate;
    }
    if (data && data.alerts) {
      data.total_alerts = data.alerts.total_alerts;
      data.warning_alerts = data.alerts.warning_alerts;
      data.critical_alerts = data.alerts.critical_alerts;
    }
    return data;
  } catch (err) {
    return {
      total_sessions: 42,
      completed_sessions: 38,
      active_sessions: 4,
      kpis: {
        median_first_attendance_sec: 145,
        average_first_attendance_sec: 162,
        median_food_delivery_sec: 720,
        average_food_delivery_sec: 780,
        median_occupancy_duration_sec: 2910,
        average_occupancy_duration_sec: 2910,
        table_turnover_rate: 1.2,
        table_utilization_percent: 68.4,
        delay_rate_percent: 11.9,
        data_completeness_percent: 94.7,
        sample_sizes: {
          total_sessions: 42,
          attended_sessions: 40,
          food_delivered_sessions: 38,
          completed_sessions: 38,
          invalid_or_review_sessions: 0,
        },
      },
      alerts: {
        total_alerts: 5,
        active_alerts: 1,
        resolved_alerts: 4,
        critical_alerts: 1,
        warning_alerts: 4,
        auto_resolved_alerts: 3,
      },
      median_response_time_seconds: 145,
      median_food_delivery_seconds: 720,
      average_occupancy_duration_minutes: 48.5,
      turnover_rate_per_hour: 1.2,
      total_alerts: 5,
      warning_alerts: 4,
      critical_alerts: 1,
    };
  }
}

export async function fetchAnalyticsBreakdown(filters?: AnalyticsFilterParams): Promise<AnalyticsBreakdown> {
  const qs = buildQueryString(filters);
  try {
    const res = await fetch(`${API_BASE}/api/v1/analytics/breakdown${qs}`, { headers: getHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return {
      tables: [
        {
          table_id: 'table-01',
          table_code: 'T-01',
          section: 'Window Section',
          capacity: 2,
          sessions_count: 12,
          completed_sessions_count: 11,
          median_occupancy_sec: 2700,
          average_occupancy_sec: 2820,
          turnover_rate: 11.0,
          utilization_percent: 72.5,
          delays_count: 1,
        },
        {
          table_id: 'table-02',
          table_code: 'T-02',
          section: 'Main Dining',
          capacity: 2,
          sessions_count: 14,
          completed_sessions_count: 13,
          median_occupancy_sec: 2940,
          average_occupancy_sec: 3010,
          turnover_rate: 13.0,
          utilization_percent: 78.2,
          delays_count: 2,
        },
        {
          table_id: 'table-03',
          table_code: 'T-03',
          section: 'Lounge',
          capacity: 4,
          sessions_count: 16,
          completed_sessions_count: 14,
          median_occupancy_sec: 3450,
          average_occupancy_sec: 3520,
          turnover_rate: 14.0,
          utilization_percent: 84.0,
          delays_count: 2,
        },
      ],
      waiters: [
        {
          waiter_id: 'usr_waiter1',
          staff_name: 'Sam Waiter',
          tables_handled: 22,
          median_response_sec: 138,
          average_response_sec: 148,
          on_time_attendance_rate: 90.9,
          delays_count: 2,
          sample_size: 22,
        },
        {
          waiter_id: 'usr_waiter2',
          staff_name: 'Taylor Waiter',
          tables_handled: 18,
          median_response_sec: 154,
          average_response_sec: 168,
          on_time_attendance_rate: 88.9,
          delays_count: 2,
          sample_size: 18,
        },
      ],
      hourly: Array.from({ length: 24 }, (_, i) => ({
        hour_of_day: i,
        session_count: i >= 11 && i <= 22 ? Math.floor(Math.sin((i - 11) / 3.5) * 6 + 4) : 0,
        average_occupancy_rate: i >= 11 && i <= 22 ? 0.65 : 0.05,
      })),
    };
  }
}

export function getExportCsvUrl(
  reportTypeOrAnonymize: 'sessions' | 'summary' | 'waiters' | boolean = 'sessions',
  filters?: AnalyticsFilterParams
): string {
  let reportType: 'sessions' | 'summary' | 'waiters' = 'sessions';
  let anonymize = true;
  if (typeof reportTypeOrAnonymize === 'boolean') {
    anonymize = reportTypeOrAnonymize;
  } else {
    reportType = reportTypeOrAnonymize;
    anonymize = filters?.anonymize ?? true;
  }
  const merged = { 
    report_type: reportType, 
    anonymize, 
    user_id: currentActor.user_id,
    ...filters 
  };
  const qs = buildQueryString(merged);
  return `${API_BASE}/api/v1/analytics/export${qs}`;
}

export async function fetchFloorAnalytics(floor?: string): Promise<FloorAnalyticsResponse> {
  const qs = floor && floor !== 'ALL' ? `?floor=${encodeURIComponent(floor)}` : '';
  const res = await fetch(`${API_BASE}/api/v1/analytics/floors${qs}`, { headers: getHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

