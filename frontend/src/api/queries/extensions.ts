import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../client'
import { queryKeys } from '.'

export type ExtensionsOverviewVersionCount = {
  version: string | null
  count: number
}

export type ExtensionsOverviewRow = {
  name: string
  installed_count: number
  active_count: number
  inactive_count: number
  missing_count: number
  unknown_count: number
  versions: ExtensionsOverviewVersionCount[]
  latest_snapshot_at?: string | null
}

export type ExtensionsOverviewResponse = {
  extensions: ExtensionsOverviewRow[]
  count: number
  total: number
  total_databases: number
}

export type ExtensionsOverviewQuery = {
  search?: string
  status?: 'active' | 'inactive' | 'missing' | 'unknown'
  version?: string
  database_id?: string
  cluster_id?: string
  limit?: number
  offset?: number
}

export async function fetchExtensionsOverview(
  query: ExtensionsOverviewQuery,
  signal?: AbortSignal
): Promise<ExtensionsOverviewResponse> {
  const response = await apiClient.get<ExtensionsOverviewResponse>(
    '/api/v2/extensions/overview/',
    { params: query, signal }
  )
  return response.data
}

export function useExtensionsOverview(query: ExtensionsOverviewQuery) {
  return useQuery({
    queryKey: queryKeys.extensions.overview(query),
    queryFn: ({ signal }) => fetchExtensionsOverview(query, signal),
  })
}

export type ExtensionsOverviewDatabaseRow = {
  database_id: string
  database_name: string
  cluster_id?: string | null
  cluster_name?: string
  status: 'active' | 'inactive' | 'missing' | 'unknown'
  version?: string | null
  snapshot_updated_at?: string | null
}

export type ExtensionsOverviewDatabasesResponse = {
  databases: ExtensionsOverviewDatabaseRow[]
  count: number
  total: number
}

export type ExtensionsOverviewDatabasesQuery = {
  name: string
  version?: string
  status?: 'active' | 'inactive' | 'missing' | 'unknown'
  cluster_id?: string
  limit?: number
  offset?: number
}

export async function fetchExtensionsOverviewDatabases(
  query: ExtensionsOverviewDatabasesQuery,
  signal?: AbortSignal
): Promise<ExtensionsOverviewDatabasesResponse> {
  const response = await apiClient.get<ExtensionsOverviewDatabasesResponse>(
    '/api/v2/extensions/overview/databases/',
    { params: query, signal }
  )
  return response.data
}

export function useExtensionsOverviewDatabases(query: ExtensionsOverviewDatabasesQuery, enabled = true) {
  return useQuery({
    queryKey: queryKeys.extensions.overviewDatabases(query),
    queryFn: ({ signal }) => fetchExtensionsOverviewDatabases(query, signal),
    enabled: enabled && Boolean(query.name),
  })
}
