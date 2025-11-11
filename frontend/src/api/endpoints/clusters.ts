import { apiClient } from '../client'

export interface Cluster {
    id: string
    name: string
    description: string
    ras_server: string
    cluster_service_url: string
    cluster_user?: string
    status: 'active' | 'inactive' | 'error' | 'maintenance'
    status_display: string
    last_sync?: string
    metadata?: Record<string, any>
    databases_count?: number
    created_at: string
    updated_at: string
}

export interface ClusterCreateRequest {
    name: string
    description?: string
    ras_server: string
    cluster_service_url: string
    cluster_user?: string
    cluster_pwd?: string
    status?: string
}

export interface ClusterListResponse {
    count: number
    next: string | null
    previous: string | null
    results: Cluster[]
}

export const clustersApi = {
    // Получить список кластеров
    list: async (params?: Record<string, any>) => {
        const response = await apiClient.get<ClusterListResponse>('/databases/clusters', { params })
        return response.data.results
    },

    // Получить один кластер
    get: async (id: string) => {
        const response = await apiClient.get<Cluster>(`/databases/clusters/${id}`)
        return response.data
    },

    // Создать кластер
    create: async (data: ClusterCreateRequest) => {
        const response = await apiClient.post<Cluster>('/databases/clusters', data)
        return response.data
    },

    // Обновить кластер
    update: async (id: string, data: Partial<ClusterCreateRequest>) => {
        const response = await apiClient.put<Cluster>(`/databases/clusters/${id}`, data)
        return response.data
    },

    // Частичное обновление кластера
    patch: async (id: string, data: Partial<ClusterCreateRequest>) => {
        const response = await apiClient.patch<Cluster>(`/databases/clusters/${id}`, data)
        return response.data
    },

    // Удалить кластер
    delete: async (id: string) => {
        await apiClient.delete(`/databases/clusters/${id}`)
    },

    // Синхронизировать с RAS
    sync: async (id: string) => {
        const response = await apiClient.post<{
            status: string
            message: string
            databases_found: number
        }>(`/databases/clusters/${id}/sync`)
        return response.data
    },

    // Получить базы кластера
    getDatabases: async (id: string) => {
        const response = await apiClient.get(`/databases/clusters/${id}/databases`)
        return response.data
    },
}
