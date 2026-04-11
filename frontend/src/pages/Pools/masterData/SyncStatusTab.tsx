import { useCallback, useEffect, useMemo, useState } from 'react'
import { App as AntApp, Button, Card, Input, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  listMasterDataSyncConflicts,
  listMasterDataSyncStatus,
  listPoolTargetDatabases,
  reconcileMasterDataSyncConflict,
  resolveMasterDataSyncConflict,
  retryMasterDataSyncConflict,
  type PoolMasterDataSyncDeadlineState,
  type PoolMasterDataRegistryEntry,
  type PoolMasterDataSyncPriority,
  type PoolMasterDataSyncRole,
  type PoolMasterDataSyncConflict,
  type PoolMasterDataSyncStatus,
  type SimpleDatabaseRef,
} from '../../../api/intercompanyPools'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import { findRegistryEntryByEntityType, getSyncEntityOptions } from './registry'

const { Text } = Typography

const CONFLICT_STATUS_OPTIONS: { value: 'pending' | 'retrying' | 'resolved'; label: string }[] = [
  { value: 'pending', label: 'pending' },
  { value: 'retrying', label: 'retrying' },
  { value: 'resolved', label: 'resolved' },
]

const PRIORITY_OPTIONS: { value: PoolMasterDataSyncPriority; label: string }[] = [
  { value: 'p0', label: 'p0' },
  { value: 'p1', label: 'p1' },
  { value: 'p2', label: 'p2' },
  { value: 'p3', label: 'p3' },
]

const ROLE_OPTIONS: { value: PoolMasterDataSyncRole; label: string }[] = [
  { value: 'inbound', label: 'inbound' },
  { value: 'outbound', label: 'outbound' },
  { value: 'reconcile', label: 'reconcile' },
  { value: 'manual_remediation', label: 'manual_remediation' },
]

const DEADLINE_STATE_OPTIONS: { value: PoolMasterDataSyncDeadlineState; label: string }[] = [
  { value: 'none', label: 'none' },
  { value: 'pending', label: 'pending' },
  { value: 'met', label: 'met' },
  { value: 'missed', label: 'missed' },
]

const DEADLINE_STATE_COLORS: Record<PoolMasterDataSyncDeadlineState, string> = {
  none: 'default',
  pending: 'processing',
  met: 'success',
  missed: 'error',
}

const buildDedupeReviewHref = (conflict: PoolMasterDataSyncConflict): string | null => {
  if (conflict.conflict_code !== 'MASTER_DATA_DEDUPE_REVIEW_REQUIRED') {
    return null
  }
  const diagnostics = conflict.diagnostics ?? {}
  const reviewItemId = typeof diagnostics.dedupe_review_item_id === 'string'
    ? diagnostics.dedupe_review_item_id.trim()
    : ''
  const clusterId = typeof diagnostics.dedupe_cluster_id === 'string'
    ? diagnostics.dedupe_cluster_id.trim()
    : ''
  const entityType = typeof diagnostics.entity_type === 'string'
    ? diagnostics.entity_type.trim()
    : conflict.entity_type
  const canonicalId = typeof diagnostics.canonical_id === 'string'
    ? diagnostics.canonical_id.trim()
    : conflict.canonical_id

  if (!reviewItemId && !clusterId) {
    return null
  }
  const params = new URLSearchParams()
  params.set('tab', 'dedupe-review')
  if (reviewItemId) {
    params.set('reviewItemId', reviewItemId)
  }
  if (clusterId) {
    params.set('clusterId', clusterId)
  }
  if (entityType) {
    params.set('entityType', entityType)
  }
  if (canonicalId) {
    params.set('canonicalId', canonicalId)
  }
  if (conflict.database_id) {
    params.set('databaseId', conflict.database_id)
  }
  return `/pools/master-data?${params.toString()}`
}

type SyncStatusTabProps = {
  registryEntries: PoolMasterDataRegistryEntry[]
}

export function SyncStatusTab({ registryEntries }: SyncStatusTabProps) {
  const { message } = AntApp.useApp()
  const [databases, setDatabases] = useState<SimpleDatabaseRef[]>([])
  const [databaseId, setDatabaseId] = useState<string | undefined>(undefined)
  const [entityType, setEntityType] = useState<string | undefined>(undefined)
  const [priority, setPriority] = useState<PoolMasterDataSyncPriority | undefined>(undefined)
  const [role, setRole] = useState<PoolMasterDataSyncRole | undefined>(undefined)
  const [serverAffinity, setServerAffinity] = useState<string | undefined>(undefined)
  const [deadlineState, setDeadlineState] = useState<PoolMasterDataSyncDeadlineState | undefined>(undefined)
  const [conflictStatus, setConflictStatus] = useState<'pending' | 'retrying' | 'resolved' | undefined>(undefined)
  const [statusRows, setStatusRows] = useState<PoolMasterDataSyncStatus[]>([])
  const [conflictRows, setConflictRows] = useState<PoolMasterDataSyncConflict[]>([])
  const [loading, setLoading] = useState(false)
  const [actionConflictId, setActionConflictId] = useState<string | null>(null)
  const entityTypeOptions = useMemo(
    () => getSyncEntityOptions(registryEntries),
    [registryEntries]
  )
  const visibleSyncEntityTypes = useMemo(
    () => new Set(entityTypeOptions.map((option) => option.value)),
    [entityTypeOptions]
  )

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
          priority,
          role,
          server_affinity: serverAffinity,
          deadline_state: deadlineState,
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
  }, [conflictStatus, databaseId, deadlineState, entityType, message, priority, role, serverAffinity])

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

  const canRunConflictWorkflowAction = useCallback(
    (conflict: PoolMasterDataSyncConflict): boolean => {
      const entry = findRegistryEntryByEntityType(registryEntries, conflict.entity_type)
      if (!entry) {
        return false
      }
      return String(conflict.origin_system || '').trim().toLowerCase() === 'ib'
        ? entry.capabilities.sync_inbound
        : entry.capabilities.sync_outbound
    },
    [registryEntries]
  )
  const visibleStatusRows = useMemo(
    () => statusRows.filter((row) => visibleSyncEntityTypes.has(row.entity_type)),
    [statusRows, visibleSyncEntityTypes]
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
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      width: 120,
      render: (value: PoolMasterDataSyncStatus['priority']) => (
        value ? <Tag>{value}</Tag> : <Text type="secondary">-</Text>
      ),
    },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      width: 180,
      render: (value: PoolMasterDataSyncStatus['role']) => (
        value ? <Tag color="blue">{value}</Tag> : <Text type="secondary">-</Text>
      ),
    },
    {
      title: 'Server affinity',
      dataIndex: 'server_affinity',
      key: 'server_affinity',
      width: 200,
      render: (value: string) => (value ? <Text code>{value}</Text> : <Text type="secondary">-</Text>),
    },
    {
      title: 'Deadline state',
      dataIndex: 'deadline_state',
      key: 'deadline_state',
      width: 160,
      render: (value: PoolMasterDataSyncStatus['deadline_state']) => (
        <Tag color={DEADLINE_STATE_COLORS[value]}>{value}</Tag>
      ),
    },
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
          {buildDedupeReviewHref(row) ? (
            <Button
              size="small"
              type="link"
              href={buildDedupeReviewHref(row) || undefined}
            >
              Open Review
            </Button>
          ) : null}
          {canRunConflictWorkflowAction(row) && (
            <Button
              size="small"
              onClick={() => void runConflictAction(row, 'retry')}
              loading={actionConflictId === row.id}
              disabled={row.status === 'resolved'}
            >
              Retry
            </Button>
          )}
          {canRunConflictWorkflowAction(row) && (
            <Button
              size="small"
              onClick={() => void runConflictAction(row, 'reconcile')}
              loading={actionConflictId === row.id}
              disabled={row.status === 'resolved'}
            >
              Reconcile
            </Button>
          )}
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
            data-testid="sync-status-filter-entity-type"
            allowClear
            placeholder="Entity type"
            value={entityType}
            options={entityTypeOptions}
            onChange={(value) => setEntityType(value)}
            style={{ width: 180 }}
          />
          <Select
            data-testid="sync-status-filter-priority"
            allowClear
            placeholder="Priority"
            value={priority}
            options={PRIORITY_OPTIONS}
            onChange={(value) => setPriority(value)}
            style={{ width: 160 }}
          />
          <Select
            data-testid="sync-status-filter-role"
            allowClear
            placeholder="Role"
            value={role}
            options={ROLE_OPTIONS}
            onChange={(value) => setRole(value)}
            style={{ width: 220 }}
          />
          <Input
            data-testid="sync-status-filter-server-affinity"
            allowClear
            placeholder="Server affinity"
            value={serverAffinity}
            onChange={(event) => {
              const value = event.target.value.trim()
              setServerAffinity(value ? value : undefined)
            }}
            style={{ width: 220 }}
          />
          <Select
            data-testid="sync-status-filter-deadline-state"
            allowClear
            placeholder="Deadline state"
            value={deadlineState}
            options={DEADLINE_STATE_OPTIONS}
            onChange={(value) => setDeadlineState(value)}
            style={{ width: 200 }}
          />
          <Select
            data-testid="sync-status-filter-conflict-status"
            allowClear
            placeholder="Conflict status"
            value={conflictStatus}
            options={CONFLICT_STATUS_OPTIONS}
            onChange={(value) => setConflictStatus(value)}
            style={{ width: 200 }}
          />
          <Button data-testid="sync-status-refresh" onClick={() => void loadData()} loading={loading}>
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
          dataSource={visibleStatusRows}
          pagination={false}
          scroll={{ x: 2320 }}
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
