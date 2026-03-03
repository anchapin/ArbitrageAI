/**
 * Type definitions for the ArbitrageAI Client Portal
 * 
 * This file contains shared types used across the application.
 * During TypeScript migration, these types will be expanded.
 */

/**
 * Task status enumeration
 */
export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed';

/**
 * Task domain categories
 */
export type TaskDomain =
  | 'general'
  | 'legal'
  | 'accounting'
  | 'healthcare'
  | 'finance'
  | 'retail'
  | 'manufacturing'
  | 'technology'
  | 'data_analysis';

/**
 * Task representation
 */
export interface Task {
  /** Unique task identifier */
  id: string;
  
  /** Task title */
  title: string;
  
  /** Task description */
  description: string;
  
  /** Current task status */
  status: TaskStatus;
  
  /** Task domain/category */
  domain: TaskDomain;
  
  /** Task result (if completed) */
  result?: string;
  
  /** Error message (if failed) */
  error?: string;
  
  /** Progress percentage (0-100) */
  progress?: number;
  
  /** ISO 8601 timestamp */
  createdAt: string;
  
  /** ISO 8601 timestamp */
  updatedAt: string;
  
  /** ISO 8601 timestamp (optional) */
  completedAt?: string;
}

/**
 * Task creation request
 */
export interface CreateTaskRequest {
  title: string;
  description: string;
  domain: TaskDomain;
  fileContent?: string;
  filename?: string;
  fileType?: string;
}

/**
 * Task complexity levels
 */
export type TaskComplexity = 'simple' | 'medium' | 'complex';

/**
 * Task urgency levels
 */
export type TaskUrgency = 'standard' | 'rush' | 'urgent';

/**
 * Task submission form data
 */
export interface TaskFormData {
  title: string;
  description: string;
  domain: TaskDomain;
  complexity?: TaskComplexity;
  urgency?: TaskUrgency;
  clientEmail: string;
  file: File | null;
}

/**
 * API response wrapper
 */
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

/**
 * Pagination parameters
 */
export interface PaginationParams {
  page?: number;
  limit?: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

/**
 * Paginated response
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

/**
 * Analytics data
 */
export interface AnalyticsData {
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  pendingTasks: number;
  averageCompletionTime?: number;
  successRate?: number;
  tasksByDomain?: Record<TaskDomain, number>;
  tasksByStatus?: Record<TaskStatus, number>;
}

/**
 * User session
 */
export interface UserSession {
  userId: string;
  email: string;
  name?: string;
  role: 'client' | 'admin';
  expiresAt: string;
}

/**
 * Error types
 */
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, string>;
}

/**
 * Form validation errors
 */
export interface FormErrors {
  [field: string]: string;
}

/**
 * Analytics Dashboard Types
 */

/**
 * KPI (Key Performance Indicator) data
 */
export interface KPIData {
  total_revenue: number;
  revenue_growth_rate: number;
  total_tasks: number;
  tasks_per_hour: number;
  success_rate: number;
  active_users: number;
  avg_completion_time: number;
}

/**
 * Prediction data for analytics forecasting
 */
export interface PredictionData {
  prediction: number;
  trend: 'up' | 'down' | 'stable';
  confidence: number;
  lower_bound: number;
  upper_bound: number;
  horizon_hours?: number;
  timestamp?: string;
}

/**
 * Predictions object containing multiple prediction types
 */
export interface Predictions {
  revenue?: PredictionData;
  tasks?: PredictionData;
}

/**
 * Anomaly severity levels
 */
export type AnomalySeverity = 'critical' | 'high' | 'medium' | 'low';

/**
 * Detected anomaly in analytics data
 */
export interface Anomaly {
  metric: string;
  severity: AnomalySeverity;
  value: number;
  expected_range: [number, number];
  description: string;
  timestamp: string;
}

/**
 * Performance metric measurement
 */
export interface PerformanceMetric {
  name: string;
  value: number;
  unit: string;
  target?: number;
  timestamp?: string;
}

/**
 * Time range options for analytics queries
 */
export type TimeRange = '24h' | '7d' | '30d' | 'all';

/**
 * Metric selection options
 */
export type MetricType = 'revenue' | 'tasks' | 'success_rate' | 'users' | 'completion_time';

/**
 * Analytics dashboard component props
 */
export interface AnalyticsDashboardProps {
  /** Initial time range selection */
  initialTimeRange?: TimeRange;
  /** Callback when time range changes */
  onTimeRangeChange?: (timeRange: TimeRange) => void;
  /** Custom API base URL (optional) */
  apiBaseUrl?: string;
}

/**
 * Chart configuration options
 */
export interface ChartOptions {
  responsive: boolean;
  plugins: {
    legend: {
      position: string;
    };
    title: {
      display: boolean;
      text: string;
    };
  };
  scales?: {
    y?: {
      beginAtZero: boolean;
    };
    r?: {
      beginAtZero: boolean;
    };
  };
}

/**
 * Chart dataset for visualization
 */
export interface ChartDataset {
  label: string;
  data: number[];
  borderColor?: string;
  backgroundColor?: string | string[];
  tension?: number;
  pointBackgroundColor?: string;
}

/**
 * Chart data structure
 */
export interface ChartData {
  labels: string[];
  datasets: ChartDataset[];
}

/**
 * Recommendation item
 */
export interface Recommendation {
  id?: string | number;
  text: string;
  priority?: 'high' | 'medium' | 'low';
  category?: string;
}

/**
 * Complete analytics state
 */
export interface AnalyticsState {
  kpis: KPIData | null;
  predictions: Predictions;
  anomalies: Anomaly[];
  performanceMetrics: PerformanceMetric[];
  recommendations: Recommendation[];
  loading: boolean;
  timeRange: TimeRange;
  selectedMetric: MetricType;
}

/**
 * Trend direction indicators
 */
export type TrendDirection = 'up' | 'down' | 'stable';

/**
 * Formatter function types
 */
export type CurrencyFormatter = (value: number) => string;
export type NumberFormatter = (value: number) => string;
export type SeverityColorGetter = (severity: AnomalySeverity) => string;
export type TrendIconGetter = (trend: TrendDirection) => string;
