import type { AxiosRequestConfig } from 'axios'

import { apiClient } from './client'

export type DriverName = 'cli' | 'ibcmd'
export type DriverCommandScope = 'per_database' | 'global'
export type DriverCommandRiskLevel = 'safe' | 'dangerous'
export type DriverCommandParamKind = 'flag' | 'positional'
export type DriverCommandValueType = 'string' | 'int' | 'float' | 'bool'

export interface DriverCommandParamV2 {
  kind: DriverCommandParamKind
  flag?: string
  position?: number | null
  required: boolean
  expects_value: boolean
  label?: string
  description?: string
  value_type?: DriverCommandValueType | null
  enum?: string[]
  default?: unknown
  repeatable?: boolean
  sensitive?: boolean
  artifact?: unknown
  ui?: unknown
  disabled?: boolean
}

export interface DriverCommandV2 {
  label: string
  description?: string
  argv: string[]
  scope: DriverCommandScope
  risk_level: DriverCommandRiskLevel
  params_by_name?: Record<string, DriverCommandParamV2>
  ui?: unknown
  source_section?: string
  disabled?: boolean
  permissions?: unknown
}

export interface DriverCatalogV2 {
  catalog_version: number
  driver: string
  platform_version?: string
  source?: {
    type?: string
    doc_id?: string
    section_prefix?: string
    doc_url?: string
    hint?: string
  }
  generated_at?: string
  commands_by_id: Record<string, DriverCommandV2>
}

export interface DriverCommandsResponseV2 {
  driver: DriverName
  base_version: string
  overrides_version: string | null
  generated_at: string
  catalog: DriverCatalogV2
}

type DriverCommandsCacheEntry = {
  etag?: string
  data: DriverCommandsResponseV2
}

const driverCommandsCache = new Map<DriverName, DriverCommandsCacheEntry>()

export async function fetchDriverCommands(
  driver: DriverName,
  signal?: AbortSignal
): Promise<DriverCommandsResponseV2> {
  const cached = driverCommandsCache.get(driver)
  const headers: Record<string, string> = {}
  if (cached?.etag) {
    headers['If-None-Match'] = cached.etag
  }

  const requestConfig: AxiosRequestConfig = {
    params: { driver },
    headers,
    signal,
    validateStatus: (status) => status === 200 || status === 304,
  }

  const response = await apiClient.get<DriverCommandsResponseV2>(
    '/api/v2/operations/driver-commands/',
    requestConfig
  )

  if (response.status === 304) {
    if (cached?.data) {
      return cached.data
    }
    // Unexpected 304 without a cache entry (retry without If-None-Match)
    return fetchDriverCommandsUncached(driver, signal)
  }

  const etag = typeof response.headers?.etag === 'string' ? response.headers.etag : undefined
  driverCommandsCache.set(driver, { etag, data: response.data })
  return response.data
}

async function fetchDriverCommandsUncached(
  driver: DriverName,
  signal?: AbortSignal
): Promise<DriverCommandsResponseV2> {
  const response = await apiClient.get<DriverCommandsResponseV2>(
    '/api/v2/operations/driver-commands/',
    {
      params: { driver },
      signal,
    }
  )
  const etag = typeof response.headers?.etag === 'string' ? response.headers.etag : undefined
  driverCommandsCache.set(driver, { etag, data: response.data })
  return response.data
}

