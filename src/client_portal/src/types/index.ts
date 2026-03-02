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
  | 'technology';

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
 * Task submission form data
 */
export interface TaskFormData {
  title: string;
  description: string;
  domain: TaskDomain;
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
