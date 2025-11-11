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
  getDatabaseStatus: async (databaseId: string): Promise<ExtensionInstallation | null> => {
    try {
      const response = await apiClient.get<ExtensionInstallation>(
        `/databases/${databaseId}/extension-status/`
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

  // Повторить неудачную установку
  retryInstallation: async (databaseId: number): Promise<{ task_id: string }> => {
    const response = await apiClient.post<{ task_id: string }>(
      `/databases/${databaseId}/retry-installation/`
    )
    return response.data
  },

  // Установить расширение на одну базу
  installSingle: async (
    databaseId: string,
    extensionConfig: { name: string; path: string }
  ): Promise<{ task_id: string; message: string }> => {
    const response = await apiClient.post<{ task_id: string; message: string }>(
      `/databases/${databaseId}/install-extension/`,
      { extension_config: extensionConfig }
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
