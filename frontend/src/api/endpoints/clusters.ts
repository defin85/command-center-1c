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
    next?: string | null
    previous?: string | null
    results?: Cluster[]
    clusters?: Cluster[]  // API v2 returns 'clusters' instead of 'results'
}

export const clustersApi = {
    // v2 migration: GET /databases/clusters → GET /clusters/list-clusters
    list: async (params?: Record<string, any>): Promise<Cluster[]> => {
        const response = await apiClient.get<ClusterListResponse>('/clusters/list-clusters', { params })
        // Defensive: handle both 'clusters' (API v2) and 'results' (DRF standard)
        return response.data?.clusters ?? response.data?.results ?? []
    },

    // v2 migration: GET /databases/clusters/{id} → GET /clusters/get-cluster?cluster_id={id}
    get: async (id: string) => {
        const response = await apiClient.get<Cluster>('/clusters/get-cluster', {
            params: { cluster_id: id }
        })
        return response.data
    },

    // v2 migration: POST /databases/clusters → POST /clusters/create-cluster
    create: async (data: ClusterCreateRequest) => {
        const response = await apiClient.post<Cluster>('/clusters/create-cluster', data)
        return response.data
    },

    // v2 migration: PUT /databases/clusters/{id} → PUT /clusters/update-cluster?cluster_id={id}
    update: async (id: string, data: Partial<ClusterCreateRequest>) => {
        const response = await apiClient.put<Cluster>('/clusters/update-cluster', data, {
            params: { cluster_id: id }
        })
        return response.data
    },

    // v2 migration: PATCH /databases/clusters/{id} → PATCH /clusters/update-cluster?cluster_id={id}
    patch: async (id: string, data: Partial<ClusterCreateRequest>) => {
        const response = await apiClient.patch<Cluster>('/clusters/update-cluster', data, {
            params: { cluster_id: id }
        })
        return response.data
    },

    // v2 migration: DELETE /databases/clusters/{id} → DELETE /clusters/delete-cluster?cluster_id={id}
    delete: async (id: string) => {
        await apiClient.delete('/clusters/delete-cluster', {
            params: { cluster_id: id }
        })
    },

    // v2 migration: POST /databases/clusters/{id}/sync → POST /clusters/sync-cluster?cluster_id={id}
    sync: async (id: string) => {
        const response = await apiClient.post<{
            status: string
            message: string
            databases_found: number
        }>('/clusters/sync-cluster', null, {
            params: { cluster_id: id }
        })
        return response.data
    },

    // v2 migration: GET /databases/clusters/{id}/databases → GET /clusters/get-cluster-databases?cluster_id={id}
    getDatabases: async (id: string) => {
        const response = await apiClient.get<{ databases?: any[]; results?: any[] }>('/clusters/get-cluster-databases', {
            params: { cluster_id: id }
        })
        // Defensive: handle both 'databases' (API v2) and 'results' (DRF standard)
        return response.data?.databases ?? response.data?.results ?? []
    },
}
