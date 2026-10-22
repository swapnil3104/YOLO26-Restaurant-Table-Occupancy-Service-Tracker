export type TableStatus =
  | 'VACANT'
  | 'OCCUPIED'
  | 'ATTENDED'
  | 'FOOD_DELIVERED'
  | 'PAYMENT_PENDING'
  | 'CLEANING_REQUIRED'
  | 'UNKNOWN';

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
}

export interface ServiceEvent {
  id: string;
  tableCode: string;
  eventType: string;
  source: 'AI_OBSERVATION' | 'STAFF_CONFIRMATION' | 'POS_INTEGRATION' | 'MANAGER_OVERRIDE';
  isVerified: boolean;
  timestamp: string;
  actor?: string;
  notes?: string;
}

export interface Alert {
  id: string;
  tableCode: string;
  type: 'ATTENDANCE_OVERDUE' | 'FOOD_DELIVERY_OVERDUE' | 'SESSION_OVERTIME' | 'CAMERA_DEGRADED';
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  message: string;
  triggeredAt: string;
  isAcknowledged: boolean;
}

export interface CameraHealth {
  cameraId: string;
  status: 'ONLINE' | 'DEGRADED' | 'OFFLINE';
  currentFps: number;
  droppedFrames: number;
  lastFrameAt: string;
}

export interface DashboardKPIs {
  totalTables: number;
  occupiedTables: number;
  activeAlerts: number;
  avgResponseTimeMin: number;
  avgDeliveryTimeMin: number;
  cameraStatus: 'HEALTHY' | 'DEGRADED' | 'DISCONNECTED';
}
