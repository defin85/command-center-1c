import { Grid, Space, Spin, Table, Tag, Typography } from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'

import type {
  ExtensionsOverviewDatabaseRow,
  ExtensionsOverviewRow,
} from '../../api/queries/extensions'

const { useBreakpoint } = Grid
const { Text } = Typography

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
              <Text type="secondary">{row.cluster_name || row.cluster_id || '—'}</Text>
              <Space wrap>
                <Tag>{row.status}</Tag>
                <Tag>version: {row.version || '—'}</Tag>
              </Space>
              <Text>Active: {String(row.flags?.active ?? '—')}</Text>
              <Text>Safe mode: {String(row.flags?.safe_mode ?? '—')}</Text>
              <Text>Unsafe action protection: {String(row.flags?.unsafe_action_protection ?? '—')}</Text>
              <Text type="secondary">
                Snapshot: {row.snapshot_updated_at ? new Date(row.snapshot_updated_at).toLocaleString() : '—'}
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
  return (
    <Table
      size="small"
      rowKey={(row) => row.database_id}
      pagination={false}
      dataSource={data}
      columns={[
        { title: 'Database', dataIndex: 'database_id', key: 'database_id' },
        { title: 'Base at', dataIndex: 'base_at', key: 'base_at', width: 220 },
        { title: 'Current at', dataIndex: 'current_at', key: 'current_at', width: 220 },
      ]}
      scroll={{ x: 700 }}
    />
  )
}
