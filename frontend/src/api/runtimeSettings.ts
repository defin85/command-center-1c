import { apiClient } from './client'

export type RuntimeSetting = {
  key: string
  value: unknown
  value_type: string
  description: string
  min_value?: number | null
  max_value?: number | null
  default: unknown
}

export async function getRuntimeSettings(): Promise<RuntimeSetting[]> {
  const response = await apiClient.get<{ settings: RuntimeSetting[] }>(
    '/api/v2/settings/runtime/',
    { skipGlobalError: true }
  )
  return response.data.settings ?? []
}

export async function updateRuntimeSetting(
  key: string,
  value: unknown
): Promise<RuntimeSetting> {
  const response = await apiClient.patch<RuntimeSetting>(
    `/api/v2/settings/runtime/${key}/`,
    { value }
  )
  return response.data
}
