import type { ColumnsType } from 'antd/es/table'

export type PermissionLevelCode = 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
export type RbacPermissionsResourceKey = 'clusters' | 'databases' | 'operation-templates' | 'workflow-templates' | 'artifacts'

export type RbacPermissionsListState = {
  principal_id?: number
  resource_id?: string
  level?: PermissionLevelCode
  search: string
  page: number
  pageSize: number
}

export type PermissionsTableRow = Record<string, unknown>

export type RbacPermissionsTableConfig = {
  columns: ColumnsType<PermissionsTableRow>
  rows: PermissionsTableRow[]
  total: number
  loading: boolean
  fetching: boolean
  error: unknown
  rowKey: (row: PermissionsTableRow) => string
  refetch: () => void
}

export const LEVEL_OPTIONS: Array<{ label: PermissionLevelCode; value: PermissionLevelCode }> = [
  { label: 'VIEW', value: 'VIEW' },
  { label: 'OPERATE', value: 'OPERATE' },
  { label: 'MANAGE', value: 'MANAGE' },
  { label: 'ADMIN', value: 'ADMIN' },
]

