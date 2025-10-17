import { apiClient } from '../client'

export interface Operation {
  id: string
  type: string
  status: string
  database: string
  payload: Record<string, any>
  result?: Record<string, any>
  error?: string
  created_at: string
  updated_at: string
}

export const operationsApi = {
  list: async (params?: Record<string, any>) => {
    const response = await apiClient.get<Operation[]>('/operations', { params })
    return response.data
  },

  get: async (id: string) => {
    const response = await apiClient.get<Operation>(`/operations/${id}`)
    return response.data
  },

  create: async (data: Partial<Operation>) => {
    const response = await apiClient.post<Operation>('/operations', data)
    return response.data
  },

  cancel: async (id: string) => {
    const response = await apiClient.delete(`/operations/${id}`)
    return response.data
  },
}
