/**
 * Databases API Adapter.
 *
 * Bridges the gap between the old endpoint-based API and the new
 * generated API from OpenAPI specifications.
 *
 * This adapter:
 * 1. Uses customInstance (same as generated code) for API calls
 * 2. Provides the same function signatures as endpoints/databases.ts
 * 3. Maps parameters to the v2 action-based endpoints
 *
 * Migration: endpoints/databases.ts -> adapters/databases.ts
 */

import { customInstance } from '../mutator'

// ============================================================================
// Types
// ============================================================================

export interface Database {
  id: string
  name: string
  host: string
  port: number
  status: string
  last_check?: string
  created_at: string
}

export interface DatabaseListParams {
  cluster_id?: string
  status?: string
  health_status?: string
  search?: string
  limit?: number
  offset?: number
}

export interface DatabaseListResponse {
  databases: Database[]
  count: number
  total?: number
}

export interface DatabaseDetailResponse {
  database: Database
  cluster?: {
    id: string
    name: string
  }
}

export interface HealthCheckResponse {
  database_id: string
  status: 'ok' | 'degraded' | 'down'
  response_time_ms: number
  checked_at: string
}

export interface BulkHealthCheckParams {
  database_ids: string[]
  cluster_id?: string
}

export interface BulkHealthCheckResponse {
  results: Array<{
    database_id: string
    status: 'ok' | 'degraded' | 'down'
    response_time_ms: number
  }>
  summary: {
    total: number
    healthy: number
    degraded: number
    down: number
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List all databases with optional filtering.
 * GET /api/v2/databases/list-databases/
 */
export const listDatabases = async (params?: DatabaseListParams): Promise<Database[]> => {
  const response = await customInstance<DatabaseListResponse>({
    url: '/api/v2/databases/list-databases/',
    method: 'GET',
    params: {
      cluster_id: params?.cluster_id,
      status: params?.status,
      health_status: params?.health_status,
      search: params?.search,
      limit: params?.limit ?? 100,
      offset: params?.offset ?? 0,
    },
  })
  return response.databases ?? []
}

/**
 * Get a single database by ID.
 * GET /api/v2/databases/get-database/?database_id=X
 */
export const getDatabase = async (id: string): Promise<Database> => {
  const response = await customInstance<DatabaseDetailResponse>({
    url: '/api/v2/databases/get-database/',
    method: 'GET',
    params: { database_id: id },
  })
  return response.database
}

/**
 * Perform health check on a specific database.
 * POST /api/v2/databases/health-check/
 */
export const checkHealth = async (id: string): Promise<HealthCheckResponse> => {
  return customInstance<HealthCheckResponse>({
    url: '/api/v2/databases/health-check/',
    method: 'POST',
    data: { database_id: id },
  })
}

/**
 * Perform health check on multiple databases.
 * POST /api/v2/databases/bulk-health-check/
 */
export const bulkHealthCheck = async (
  params: BulkHealthCheckParams
): Promise<BulkHealthCheckResponse> => {
  return customInstance<BulkHealthCheckResponse>({
    url: '/api/v2/databases/bulk-health-check/',
    method: 'POST',
    data: params,
  })
}

// ============================================================================
// Legacy API object (for backward compatibility)
// ============================================================================

/**
 * @deprecated Use individual functions instead.
 * This object maintains backward compatibility with endpoints/databases.ts
 */
export const databasesApi = {
  list: listDatabases,
  get: getDatabase,
  checkHealth,
  bulkHealthCheck,
}

export default databasesApi
