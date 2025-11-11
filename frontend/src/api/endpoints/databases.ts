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
  list: async (params?: Record<string, any>) => {
    const response = await apiClient.get<DatabaseListResponse>('/databases', { params })
    return response.data.results
  },

  get: async (id: string) => {
    const response = await apiClient.get<Database>(`/databases/${id}`)
    return response.data
  },

  create: async (data: Partial<Database>) => {
    const response = await apiClient.post<Database>('/databases', data)
    return response.data
  },

  checkHealth: async (id: string) => {
    const response = await apiClient.get(`/databases/${id}/health`)
    return response.data
  },
}
