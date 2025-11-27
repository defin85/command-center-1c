import { apiClient } from '../client'

export interface Database {
  id: string
  name: string
  host: string
  port: number
  status: string
  last_check?: string
  created_at: string
}

export interface DatabaseListResponse {
  count: number
  next: string | null
  previous: string | null
  results: Database[]
}

export const databasesApi = {
  // v2 migration: GET /databases → GET /databases/list-databases
  list: async (params?: Record<string, any>) => {
    const response = await apiClient.get<DatabaseListResponse>('/databases/list-databases', { params })
    return response.data.results
  },

  // v2 migration: GET /databases/{id} → GET /databases/get-database?database_id={id}
  get: async (id: string) => {
    const response = await apiClient.get<Database>('/databases/get-database', {
      params: { database_id: id }
    })
    return response.data
  },

  // v2 migration: POST /databases → POST /databases/create-database
  create: async (data: Partial<Database>) => {
    const response = await apiClient.post<Database>('/databases/create-database', data)
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
