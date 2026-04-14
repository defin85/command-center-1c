import { Grid, Space, Spin, Table, Tag, Typography } from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import { useAdminSupportTranslation, useCommonTranslation, useLocaleFormatters } from '@/i18n'

import type {
  ExtensionsOverviewDatabaseRow,
  ExtensionsOverviewRow,
} from '../../api/queries/extensions'

const { useBreakpoint } = Grid
const { Text } = Typography

const resolveStatusLabel = (
  status: string | null | undefined,
  t: ReturnType<typeof useAdminSupportTranslation>['t'],
) => {
  switch (status) {
    case 'active':
      return t(($) => $.extensions.status.active)
    case 'inactive':
      return t(($) => $.extensions.status.inactive)
    case 'missing':
      return t(($) => $.extensions.status.missing)
    case 'unknown':
      return t(($) => $.extensions.status.unknown)
    default:
      return status || '—'
  }
}

type ExtensionsOverviewTableProps = {
  columns: ColumnsType<ExtensionsOverviewRow>
  data: ExtensionsOverviewRow[]
  loading: boolean
  pagination: TablePaginationConfig
}

export function ExtensionsOverviewTable({
  columns,
  data,
  loading,
  pagination,
}: ExtensionsOverviewTableProps) {
  return (
    <Table
      rowKey="name"
      columns={columns}
      dataSource={data}
      loading={loading}
      pagination={pagination}
      size="middle"
    />
  )
}

type ExtensionsDrilldownTableProps = {
  columns: ColumnsType<ExtensionsOverviewDatabaseRow>
  data: ExtensionsOverviewDatabaseRow[]
  loading: boolean
  pagination: TablePaginationConfig | false
}

export function ExtensionsDrilldownTable({
  columns,
  data,
  loading,
  pagination,
}: ExtensionsDrilldownTableProps) {
  const { t } = useAdminSupportTranslation()
  const { t: tCommon } = useCommonTranslation()
  const formatters = useLocaleFormatters()
  const screens = useBreakpoint()
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.lg
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < 992
        : false
    )

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
        <Spin />
      </div>
    )
  }

  const unavailable = tCommon(($) => $.values.unavailableShort)

  if (isNarrow) {
    return (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {data.map((row) => (
          <div
            key={row.database_id}
            style={{
              border: '1px solid #f0f0f0',
              borderRadius: 12,
              padding: 12,
            }}
          >
            <Space direction="vertical" size={6} style={{ width: '100%' }}>
              <Text strong>{row.database_name}</Text>
              <Text type="secondary">{row.cluster_name || row.cluster_id || unavailable}</Text>
              <Space wrap>
                <Tag>{resolveStatusLabel(row.status, t)}</Tag>
                <Tag>{t(($) => $.extensions.table.mobileVersion, { value: row.version || unavailable })}</Tag>
              </Space>
              <Text>{t(($) => $.extensions.table.mobileActive, { value: String(row.flags?.active ?? unavailable) })}</Text>
              <Text>{t(($) => $.extensions.table.mobileSafeMode, { value: String(row.flags?.safe_mode ?? unavailable) })}</Text>
              <Text>{t(($) => $.extensions.table.mobileUnsafeActionProtection, { value: String(row.flags?.unsafe_action_protection ?? unavailable) })}</Text>
              <Text type="secondary">
                {t(($) => $.extensions.table.mobileSnapshot, {
                  value: formatters.dateTime(row.snapshot_updated_at, { fallback: unavailable }),
                })}
              </Text>
            </Space>
          </div>
        ))}
      </Space>
    )
  }

  return (
    <Table
      rowKey="database_id"
      columns={columns}
      dataSource={data}
      loading={loading}
      pagination={pagination}
      size="small"
    />
  )
}

type ExtensionsBindingRow = {
  target_ref?: string
  source_ref?: string
  resolve_at?: string
  sensitive?: boolean
  status?: string
  reason?: string | null
}

type ExtensionsBindingsTableProps = {
  columns: ColumnsType<ExtensionsBindingRow>
  data: ExtensionsBindingRow[]
}

export function ExtensionsBindingsTable({
  columns,
  data,
}: ExtensionsBindingsTableProps) {
  return (
    <Table
      size="small"
      rowKey={(_row, idx) => String(idx)}
      pagination={false}
      dataSource={data}
      columns={columns}
      scroll={{ x: 900 }}
    />
  )
}

type ExtensionsDriftRow = {
  database_id: string
  base_at: string
  current_at: string
  base_hash: string
  current_hash: string
}

type ExtensionsDriftTableProps = {
  data: ExtensionsDriftRow[]
}

export function ExtensionsDriftTable({ data }: ExtensionsDriftTableProps) {
  const { t } = useAdminSupportTranslation()

  return (
    <Table
      size="small"
      rowKey={(row) => row.database_id}
      pagination={false}
      dataSource={data}
      columns={[
        { title: t(($) => $.extensions.drift.database), dataIndex: 'database_id', key: 'database_id' },
        { title: t(($) => $.extensions.drift.baseAt), dataIndex: 'base_at', key: 'base_at', width: 220 },
        { title: t(($) => $.extensions.drift.currentAt), dataIndex: 'current_at', key: 'current_at', width: 220 },
      ]}
      scroll={{ x: 700 }}
    />
  )
}
