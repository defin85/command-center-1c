import { useCallback, useEffect, useMemo, useState } from 'react'
import { App as AntApp, Button, Card, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  listMasterDataSyncConflicts,
  listMasterDataSyncStatus,
  listPoolTargetDatabases,
  reconcileMasterDataSyncConflict,
  resolveMasterDataSyncConflict,
  retryMasterDataSyncConflict,
  type PoolMasterDataEntityType,
  type PoolMasterDataSyncConflict,
  type PoolMasterDataSyncStatus,
  type SimpleDatabaseRef,
} from '../../../api/intercompanyPools'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'

const { Text } = Typography

const ENTITY_TYPE_OPTIONS: { value: PoolMasterDataEntityType; label: string }[] = [
  { value: 'party', label: 'party' },
  { value: 'item', label: 'item' },
  { value: 'contract', label: 'contract' },
  { value: 'tax_profile', label: 'tax_profile' },
]

const CONFLICT_STATUS_OPTIONS = [
  { value: 'pending', label: 'pending' },
  { value: 'retrying', label: 'retrying' },
  { value: 'resolved', label: 'resolved' },
] as const

export function SyncStatusTab() {
  const { message } = AntApp.useApp()
  const [databases, setDatabases] = useState<SimpleDatabaseRef[]>([])
  const [databaseId, setDatabaseId] = useState<string | undefined>(undefined)
  const [entityType, setEntityType] = useState<PoolMasterDataEntityType | undefined>(undefined)
  const [conflictStatus, setConflictStatus] = useState<'pending' | 'retrying' | 'resolved' | undefined>(undefined)
  const [statusRows, setStatusRows] = useState<PoolMasterDataSyncStatus[]>([])
  const [conflictRows, setConflictRows] = useState<PoolMasterDataSyncConflict[]>([])
  const [loading, setLoading] = useState(false)
  const [actionConflictId, setActionConflictId] = useState<string | null>(null)

  const databaseNameById = useMemo(() => {
    const lookup = new Map<string, string>()
    for (const database of databases) {
      lookup.set(database.id, database.name)
    }
    return lookup
  }, [databases])

  const loadDatabases = useCallback(async () => {
    try {
      const rows = await listPoolTargetDatabases()
      setDatabases(rows)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить список баз для Sync.')
      message.error(resolved.message)
    }
  }, [message])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [statusResponse, conflictsResponse] = await Promise.all([
        listMasterDataSyncStatus({
          database_id: databaseId,
          entity_type: entityType,
        }),
        listMasterDataSyncConflicts({
          database_id: databaseId,
          entity_type: entityType,
          status: conflictStatus,
          limit: 200,
        }),
      ])
      setStatusRows(statusResponse.statuses)
      setConflictRows(conflictsResponse.conflicts)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить sync status/conflicts.')
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [conflictStatus, databaseId, entityType, message])

  useEffect(() => {
    void loadDatabases()
  }, [loadDatabases])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const runConflictAction = useCallback(
    async (conflict: PoolMasterDataSyncConflict, action: 'retry' | 'reconcile' | 'resolve') => {
      setActionConflictId(conflict.id)
      try {
        if (action === 'retry') {
          await retryMasterDataSyncConflict(conflict.id, {
            note: 'Manual retry from Pool Master Data Sync UI',
          })
          message.success('Conflict переведён в retrying.')
        } else if (action === 'reconcile') {
          await reconcileMasterDataSyncConflict(conflict.id, {
            note: 'Manual reconcile from Pool Master Data Sync UI',
            reconcile_payload: { strategy: 'manual_reconcile' },
          })
          message.success('Conflict отправлен в reconcile.')
        } else {
          await resolveMasterDataSyncConflict(conflict.id, {
            resolution_code: 'MANUAL_RECONCILE',
            note: 'Manual resolve from Pool Master Data Sync UI',
            metadata: { source: 'ui' },
          })
          message.success('Conflict помечен как resolved.')
        }
        await loadData()
      } catch (error) {
        const resolved = resolveApiError(error, 'Не удалось выполнить conflict action.')
        message.error(resolved.message)
      } finally {
        setActionConflictId(null)
      }
    },
    [loadData, message]
  )

  const statusColumns: ColumnsType<PoolMasterDataSyncStatus> = [
    {
      title: 'Database',
      dataIndex: 'database_id',
      key: 'database_id',
      width: 260,
      render: (value: string) => databaseNameById.get(value) || value,
    },
    { title: 'Entity', dataIndex: 'entity_type', key: 'entity_type', width: 120 },
    { title: 'Checkpoint', dataIndex: 'checkpoint_token', key: 'checkpoint_token', width: 220 },
    { title: 'Pending', dataIndex: 'pending_count', key: 'pending_count', width: 100 },
    { title: 'Retry', dataIndex: 'retry_count', key: 'retry_count', width: 100 },
    { title: 'Conflicts', dataIndex: 'conflict_pending_count', key: 'conflict_pending_count', width: 120 },
    { title: 'Lag (s)', dataIndex: 'lag_seconds', key: 'lag_seconds', width: 100 },
    {
      title: 'Last Success',
      dataIndex: 'last_success_at',
      key: 'last_success_at',
      width: 220,
      render: (value: string | null) => formatDateTime(value),
    },
    {
      title: 'Error',
      dataIndex: 'last_error_code',
      key: 'last_error_code',
      width: 220,
      render: (value: string) => (value ? <Tag color="red">{value}</Tag> : <Text type="secondary">-</Text>),
    },
  ]

  const conflictColumns: ColumnsType<PoolMasterDataSyncConflict> = [
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (value: string) => (
        <Tag color={value === 'resolved' ? 'green' : value === 'retrying' ? 'gold' : 'red'}>
          {value}
        </Tag>
      ),
    },
    { title: 'Entity', dataIndex: 'entity_type', key: 'entity_type', width: 120 },
    {
      title: 'Database',
      dataIndex: 'database_id',
      key: 'database_id',
      width: 240,
      render: (value: string) => databaseNameById.get(value) || value,
    },
    { title: 'Canonical ID', dataIndex: 'canonical_id', key: 'canonical_id', width: 200 },
    { title: 'Conflict Code', dataIndex: 'conflict_code', key: 'conflict_code', width: 220 },
    {
      title: 'Origin',
      key: 'origin',
      width: 220,
      render: (_, row) => `${row.origin_system || '-'}:${row.origin_event_id || '-'}`,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 300,
      render: (_, row) => (
        <Space>
          <Button
            size="small"
            onClick={() => void runConflictAction(row, 'retry')}
            loading={actionConflictId === row.id}
            disabled={row.status === 'resolved'}
          >
            Retry
          </Button>
          <Button
            size="small"
            onClick={() => void runConflictAction(row, 'reconcile')}
            loading={actionConflictId === row.id}
            disabled={row.status === 'resolved'}
          >
            Reconcile
          </Button>
          <Button
            size="small"
            type="primary"
            onClick={() => void runConflictAction(row, 'resolve')}
            loading={actionConflictId === row.id}
            disabled={row.status === 'resolved'}
          >
            Resolve
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Space wrap style={{ marginBottom: 16 }}>
          <Select
            allowClear
            placeholder="Database"
            value={databaseId}
            options={databases.map((database) => ({ value: database.id, label: database.name }))}
            onChange={(value) => setDatabaseId(value)}
            style={{ width: 280 }}
          />
          <Select
            allowClear
            placeholder="Entity type"
            value={entityType}
            options={ENTITY_TYPE_OPTIONS}
            onChange={(value) => setEntityType(value)}
            style={{ width: 180 }}
          />
          <Select
            allowClear
            placeholder="Conflict status"
            value={conflictStatus}
            options={CONFLICT_STATUS_OPTIONS}
            onChange={(value) => setConflictStatus(value)}
            style={{ width: 200 }}
          />
          <Button onClick={() => void loadData()} loading={loading}>
            Refresh
          </Button>
        </Space>
        <Text type="secondary">
          Monitor lag/retries/checkpoints and manage conflict queue actions in one place.
        </Text>
      </Card>

      <Card title="Sync Status">
        <Table
          rowKey={(row) => `${row.database_id}:${row.entity_type}`}
          loading={loading}
          columns={statusColumns}
          dataSource={statusRows}
          pagination={false}
          scroll={{ x: 1560 }}
        />
      </Card>

      <Card title="Conflict Queue">
        <Table
          rowKey="id"
          loading={loading}
          columns={conflictColumns}
          dataSource={conflictRows}
          pagination={false}
          scroll={{ x: 1840 }}
        />
      </Card>
    </Space>
  )
}
