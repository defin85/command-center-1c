import { apiClient } from './client'

export interface DriverCatalogListItem {
  driver: string
  version: string
  command_count: number
  source?: string
}

export interface DriverCatalogListResponse {
  items: DriverCatalogListItem[]
  count: number
}

export interface DriverCatalogGetResponse {
  driver: string
  catalog: Record<string, unknown>
}

export interface DriverCatalogUpdateRequest {
  driver: string
  catalog: Record<string, unknown>
}

export interface DriverCatalogImportRequest {
  driver: string
  its_payload: Record<string, unknown>
  save?: boolean
}

export async function listDriverCatalogs(): Promise<DriverCatalogListResponse> {
  const response = await apiClient.get<DriverCatalogListResponse>(
    '/api/v2/settings/driver-catalogs/'
  )
  return response.data
}

export async function getDriverCatalog(driver: string): Promise<DriverCatalogGetResponse> {
  const response = await apiClient.get<DriverCatalogGetResponse>(
    '/api/v2/settings/driver-catalogs/get/',
    { params: { driver } }
  )
  return response.data
}

export async function updateDriverCatalog(
  payload: DriverCatalogUpdateRequest
): Promise<DriverCatalogGetResponse> {
  const response = await apiClient.post<DriverCatalogGetResponse>(
    '/api/v2/settings/driver-catalogs/update/',
    payload
  )
  return response.data
}

export async function importItsCatalog(
  payload: DriverCatalogImportRequest
): Promise<DriverCatalogGetResponse> {
  const response = await apiClient.post<DriverCatalogGetResponse>(
    '/api/v2/settings/driver-catalogs/import-its/',
    payload
  )
  return response.data
}
