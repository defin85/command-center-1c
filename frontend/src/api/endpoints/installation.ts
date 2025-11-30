import { apiClient } from '../client'
import {
  BatchInstallRequest,
  BatchInstallResponse,
  InstallationProgress,
  ExtensionInstallation,
  InstallSingleResponse,
} from '../../types/installation'

export const installationApi = {
  // v2 migration: POST /databases/batch-install-extension/ → POST /extensions/batch-install
  batchInstall: async (request: BatchInstallRequest): Promise<BatchInstallResponse> => {
    const response = await apiClient.post<BatchInstallResponse>(
      '/extensions/batch-install',
      request
    )
    return response.data
  },

  // v2 migration: GET /databases/installation-progress/{taskId}/ → GET /extensions/get-install-progress?task_id={taskId}
  getProgress: async (taskId: string): Promise<InstallationProgress> => {
    const response = await apiClient.get<InstallationProgress>(
      '/extensions/get-install-progress',
      { params: { task_id: taskId } }
    )
    return response.data
  },

  // v2 migration: GET /databases/{databaseId}/extension-status/ → GET /extensions/get-install-status?database_id={databaseId}
  getDatabaseStatus: async (databaseId: string): Promise<ExtensionInstallation | null> => {
    try {
      const response = await apiClient.get<ExtensionInstallation>(
        '/extensions/get-install-status',
        { params: { database_id: databaseId } }
      )
      return response.data
    } catch (error: any) {
      // Если установка еще не начата, вернуть null
      if (error.response?.status === 404) {
        return null
      }
      throw error
    }
  },

  // v2 migration: POST /databases/{databaseId}/retry-installation/ → POST /extensions/retry-installation/
  retryInstallation: async (databaseId: string): Promise<{
    database_id: string
    installation_id: string
    status: string
    celery_task_id?: string
    message: string
  }> => {
    const response = await apiClient.post<{
      database_id: string
      installation_id: string
      status: string
      celery_task_id?: string
      message: string
    }>(
      '/extensions/retry-installation/',
      { database_id: databaseId }
    )
    return response.data
  },

  // v2 migration: POST /databases/{databaseId}/install-extension/ → POST /extensions/install-single?database_id={databaseId}
  installSingle: async (
    databaseId: string,
    extensionConfig: { name: string; path: string }
  ): Promise<InstallSingleResponse> => {
    const response = await apiClient.post<InstallSingleResponse>(
      '/extensions/install-single',
      { extension_config: extensionConfig },
      { params: { database_id: databaseId } }
    )
    return response.data
  },

  // v2 migration: GET /databases/extension-installations/ → GET /extensions/list-extensions/
  getAllInstallations: async (): Promise<ExtensionInstallation[]> => {
    const response = await apiClient.get<{
      extensions: ExtensionInstallation[]
      count: number
      total: number
      summary: {
        pending: number
        in_progress: number
        completed: number
        failed: number
      }
    }>('/extensions/list-extensions/')
    return response.data.extensions
  },
}
