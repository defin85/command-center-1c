import { apiClient } from './client'

export type RuntimeSetting = {
  key: string
  value: unknown
  source?: string
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

export async function getEffectiveRuntimeSettings(): Promise<RuntimeSetting[]> {
  const response = await apiClient.get<{ settings: RuntimeSetting[] }>(
    '/api/v2/settings/runtime-effective/',
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

export async function updateRuntimeSettingOverride(
  key: string,
  value: unknown,
  status: 'draft' | 'published' = 'published'
): Promise<{ key: string; value: unknown; status: string }> {
  const response = await apiClient.patch<{ key: string; value: unknown; status: string }>(
    `/api/v2/settings/runtime-overrides/${key}/`,
    { value, status }
  )
  return response.data
}
