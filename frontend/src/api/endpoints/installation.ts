import { apiClient } from '../client'
import {
  BatchInstallRequest,
  BatchInstallResponse,
  InstallationProgress,
  ExtensionInstallation,
} from '../../types/installation'

export const installationApi = {
  // Запустить массовую установку
  batchInstall: async (request: BatchInstallRequest): Promise<BatchInstallResponse> => {
    const response = await apiClient.post<BatchInstallResponse>(
      '/databases/batch-install-extension/',
      request
    )
    return response.data
  },

  // Получить прогресс установки
  getProgress: async (taskId: string): Promise<InstallationProgress> => {
    const response = await apiClient.get<InstallationProgress>(
      `/databases/installation-progress/${taskId}/`
    )
    return response.data
  },

  // Получить статус для конкретной базы
  getDatabaseStatus: async (databaseId: number): Promise<ExtensionInstallation> => {
    const response = await apiClient.get<ExtensionInstallation>(
      `/databases/${databaseId}/extension-status/`
    )
    return response.data
  },

  // Повторить неудачную установку
  retryInstallation: async (databaseId: number): Promise<{ task_id: string }> => {
    const response = await apiClient.post<{ task_id: string }>(
      `/databases/${databaseId}/retry-installation/`
    )
    return response.data
  },

  // Получить список всех установок
  getAllInstallations: async (): Promise<ExtensionInstallation[]> => {
    const response = await apiClient.get<ExtensionInstallation[]>(
      '/databases/extension-installations/'
    )
    return response.data
  },
}
