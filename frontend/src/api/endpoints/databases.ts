/**
 * @deprecated This file is deprecated. Use '../adapters/databases' instead.
 * Migration: endpoints/databases.ts -> adapters/databases.ts
 *
 * This file will be removed in a future release.
 * Sunset date: 2026-03-01
 */
import { apiClient } from '../client'

/**
 * @deprecated Use Database from '../adapters/databases' instead
 */
export interface Database {
  id: string
  name: string
  host: string
  port: number
  status: string
  last_check?: string
  created_at: string
}

/**
 * @deprecated Use DatabaseListResponse from '../adapters/databases' instead
 */
export interface DatabaseListResponse {
  count: number
  total?: number
  next?: string | null
  previous?: string | null
  results?: Database[]
  databases?: Database[]  // API v2 returns 'databases' instead of 'results'
}

/**
 * @deprecated Use databasesApi from '../adapters/databases' instead
 */
export const databasesApi = {
  // v2 migration: GET /databases → GET /databases/list-databases
  list: async (params?: Record<string, any>): Promise<Database[]> => {
    const response = await apiClient.get<DatabaseListResponse>('/databases/list-databases', { params })
    // Defensive: handle both 'databases' (API v2) and 'results' (DRF standard)
    return response.data?.databases ?? response.data?.results ?? []
  },

  // v2 migration: GET /databases/{id} → GET /databases/get-database?database_id={id}
  get: async (id: string) => {
    const response = await apiClient.get<Database>('/databases/get-database', {
      params: { database_id: id }
    })
    return response.data
  },

  // v2 migration: GET /databases/{id}/health → POST /databases/health-check?database_id={id}
  checkHealth: async (id: string) => {
    const response = await apiClient.post(`/databases/health-check`, null, {
      params: { database_id: id }
    })
    return response.data
  },
}
