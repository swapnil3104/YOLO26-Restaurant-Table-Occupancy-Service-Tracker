export type TableStatus =
  | 'VACANT'
  | 'OCCUPIED'
  | 'ATTENDED'
  | 'FOOD_DELIVERED'
  | 'PAYMENT_PENDING'
  | 'CLEANING_REQUIRED'
  | 'NEEDS_ATTENTION'
  | 'UNKNOWN';

export type UserRole = 'WAITER' | 'MANAGER' | 'ADMIN';

export interface StaffUser {
  user_id: string;
  username: string;
  display_name: string;
  role: UserRole;
  active: boolean;
}

export interface Table {
  id: string;
  code: string;
  capacity: number;
  section: string;
  status: TableStatus;
  customerCount: number;
  currentSessionId?: string;
  sessionStartedAt?: string;
  lastStateChangeAt: string;
  assignedWaiter?: string;
  timeSinceLastAttendanceSec?: number;
  timeSinceFoodDeliverySec?: number;
  hasActiveAlert?: boolean;
  alertSeverity?: 'INFO' | 'WARNING' | 'CRITICAL';
}

export interface TimelineItem {
  id: string;
  eventType: string;
  displayName: string;
  timestamp: string;
  relativeTime?: string;
  badgeText: string;
  badgeVariant: 'confirmed' | 'candidate' | 'override' | 'pos' | 'neutral';
  actor?: string;
  source: string;
  verificationStatus: string;
  isMilestone: boolean;
  course?: string;
  notes?: string;
}

export interface Alert {
  id: string;
  tableCode: string;
  type: 'ATTENDANCE_OVERDUE' | 'FOOD_DELIVERY_OVERDUE' | 'SESSION_OVERTIME' | 'CAMERA_DEGRADED' | string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  message: string;
  triggeredAt: string;
  isAcknowledged: boolean;
  resolvedAt?: string;
  dedupKey?: string;
}

export type CCTVSourceType = 'live_stream' | 'recorded_footage';

export interface CameraFeed {
  camera_id: string;
  name: string;
  floor?: string;
  section: string;
  source_type?: CCTVSourceType;
  status: 'ONLINE' | 'DEGRADED' | 'OFFLINE';
  resolution: string;
  fps: number;
  last_frame_at: string;
  raw_stream_url: string;
  processed_stream_url: string;
  cv_metadata_url: string;
  video_url?: string;
  is_custom?: boolean;
}

export interface DetectionItem {
  class_name: string;
  track_id: number;
  confidence: number;
  bbox: [number, number, number, number];
  bottom_contact?: [number, number];
  assigned_table?: string | null;
  status?: string;
}

export interface CVTelemetry {
  camera_id: string;
  frame_timestamp: string;
  model: string;
  inference_latency_ms: number;
  fps: number;
  detections_count: number;
  patrons_tracked?: number;
  detections: DetectionItem[];
  tables: Array<{
    table_id: string;
    status: string;
    estimated_customers: number;
  }>;
}

export interface DashboardKPIs {
  totalTables: number;
  occupiedTables: number;
  availableTables: number;
  waitingAttendanceCount: number;
  activeAlerts: number;
  avgResponseTimeMin: number;
  avgDeliveryTimeMin: number;
  turnoverRatePerHour: number;
  cameraStatus: 'HEALTHY' | 'DEGRADED' | 'DISCONNECTED';
}

export interface SampleSizeMetrics {
  total_sessions: number;
  attended_sessions: number;
  food_delivered_sessions: number;
  completed_sessions: number;
  invalid_or_review_sessions: number;
}

export interface KPIMetrics {
  median_first_attendance_sec: number | null;
  average_first_attendance_sec: number | null;
  median_food_delivery_sec: number | null;
  average_food_delivery_sec: number | null;
  median_occupancy_duration_sec: number | null;
  average_occupancy_duration_sec: number | null;
  table_turnover_rate: number;
  table_utilization_percent: number;
  delay_rate_percent: number;
  data_completeness_percent: number;
  sample_sizes: SampleSizeMetrics;
}

export interface AlertSummaryStats {
  total_alerts: number;
  active_alerts: number;
  resolved_alerts: number;
  critical_alerts: number;
  warning_alerts: number;
  auto_resolved_alerts: number;
}

export interface AnalyticsSummary {
  total_sessions: number;
  completed_sessions: number;
  active_sessions: number;
  kpis: KPIMetrics;
  alerts: AlertSummaryStats;
  filter_start?: string | null;
  filter_end?: string | null;
  section?: string | null;
  table_id?: string | null;

  // Flattened convenience properties for backward compatibility
  median_response_time_seconds?: number | null;
  median_food_delivery_seconds?: number | null;
  average_occupancy_duration_minutes?: number | null;
  turnover_rate_per_hour?: number | null;
  total_alerts?: number;
  warning_alerts?: number;
  critical_alerts?: number;
}

export interface TablePerformanceItem {
  table_id: string;
  table_code: string;
  section: string;
  capacity: number;
  sessions_count: number;
  completed_sessions_count: number;
  median_occupancy_sec: number | null;
  average_occupancy_sec: number | null;
  turnover_rate: number;
  utilization_percent: number;
  delays_count: number;
}

export interface WaiterPerformanceItem {
  waiter_id: string;
  staff_name: string;
  tables_handled: number;
  median_response_sec: number | null;
  average_response_sec: number | null;
  on_time_attendance_rate: number;
  delays_count: number;
  sample_size: number;
}

export interface HourlyDistributionItem {
  hour_of_day: number;
  session_count: number;
  average_occupancy_rate: number;
}

export interface AnalyticsBreakdown {
  tables: TablePerformanceItem[];
  waiters: WaiterPerformanceItem[];
  hourly: HourlyDistributionItem[];
  filter_start?: string | null;
  filter_end?: string | null;
  section?: string | null;
  table_id?: string | null;
}

export interface AnalyticsFilterParams {
  table_id?: string;
  section?: string;
  waiter_id?: string;
  start_time?: string;
  end_time?: string;
  include_estimates?: boolean;
  anonymize?: boolean;
}

export interface VideoSourceItem {
  id: string;
  name: string;
  description: string;
  category: 'tracking' | 'standard_cctv' | 'custom';
  filename: string;
  url: string;
  resolution: string;
  fps: number;
  duration_sec?: number;
  is_annotated: boolean;
  recommended_view: 'tracking' | 'standard' | 'both';
  is_custom?: boolean;
}

export interface VideoAssignments {
  tracking_video_id: string;
  standard_video_id: string;
  camera_assignments: Record<string, string>;
}

export interface VideoSourcesResponse {
  sources: VideoSourceItem[];
  assignments: VideoAssignments;
}

export type TrackingLifecycleState =
  | 'Added'
  | 'Validating'
  | 'Initializing Model'
  | 'Monitoring'
  | 'Paused'
  | 'Error'
  | 'Disconnected'
  | 'Stopping'
  | 'Stopped';

export interface TrackingFootageItem {
  id: string;
  name: string;
  floor: string;
  section: string;
  description: string;
  videoUrl: string;
  rawVideoUrl?: string;
  resolution: string;
  fps: number;
  isCustom?: boolean;
  modelName: string;
  detectionsCount: number;
  tables: Table[];
  alerts: Alert[];
  status?: TrackingLifecycleState;
  cameraHealth?: 'HEALTHY' | 'DEGRADED' | 'DISCONNECTED';
  inferenceStatus?: 'ACTIVE' | 'INITIALIZING' | 'PAUSED' | 'IDLE' | 'ERROR';
  effectiveFps?: number;
  lastEventTime?: string;
  lastEventDescription?: string;
  sourceType?: 'video' | 'rtsp' | 'live_stream' | 'recorded_footage';
  processingJobId?: string;
  latencyMs?: number;
}
export type ReportingScope = 'LIVE_ACTIVE_SOURCES' | 'HISTORICAL_SHIFT' | 'COMBINED';

export interface FloorKPIItem {
  floor_name: string;
  monitored_sources_count: number;
  source_ids: string[];
  coverage_status: 'FULL_COVERAGE' | 'PARTIAL_COVERAGE' | 'OFFLINE' | 'UNKNOWN';
  total_tables: number;
  occupied_tables: number;
  vacant_tables: number;
  occupancy_rate_percent: number | null;
  detected_diners: number | null;
  active_alerts_count: number;
  critical_alerts_count: number;
  warning_alerts_count: number;
  avg_response_time_sec: number | null;
  avg_food_delivery_sec: number | null;
  last_freshness_sec: number | null;
  is_live: boolean;
}

export interface CentralRestaurantKPIs {
  reporting_scope: ReportingScope;
  total_monitored_floors: number;
  total_active_sources: number;
  total_canonical_tables: number;
  total_occupied_tables: number;
  total_vacant_tables: number;
  central_occupancy_rate_percent: number | null;
  total_detected_diners: number | null;
  total_active_alerts: number;
  critical_alerts_count: number;
  warning_alerts_count: number;
  weighted_avg_response_time_sec: number | null;
  weighted_avg_food_delivery_sec: number | null;
  coverage_health: 'ALL_HEALTHY' | 'PARTIAL_COVERAGE' | 'DEGRADED' | 'NO_SOURCES';
  coverage_warning?: string | null;
  timestamp: string;
}

export interface ShiftHistoricalSummary {
  total_sessions_today: number;
  completed_sessions: number;
  turnover_rate: number;
  historical_avg_response_sec: number | null;
  historical_avg_delivery_sec: number | null;
}

export interface FloorAnalyticsResponse {
  central: CentralRestaurantKPIs;
  floors: FloorKPIItem[];
  shift_history: ShiftHistoricalSummary;
}
