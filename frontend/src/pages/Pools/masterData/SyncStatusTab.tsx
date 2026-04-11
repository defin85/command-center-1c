import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  App as AntApp,
  Button,
  Card,
  Descriptions,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useSearchParams } from 'react-router-dom'

import {
  createPoolMasterDataSyncLaunch,
  getPoolMasterDataSyncLaunch,
  listMasterDataSyncConflicts,
  listMasterDataSyncStatus,
  listPoolMasterDataSyncLaunches,
  listPoolTargetClusters,
  listPoolTargetDatabases,
  reconcileMasterDataSyncConflict,
  resolveMasterDataSyncConflict,
  retryMasterDataSyncConflict,
  type PoolMasterDataRegistryEntry,
  type PoolMasterDataSyncConflict,
  type PoolMasterDataSyncDeadlineState,
  type PoolMasterDataSyncLaunch,
  type PoolMasterDataSyncLaunchItem,
  type PoolMasterDataSyncLaunchMode,
  type PoolMasterDataSyncPriority,
  type PoolMasterDataSyncRole,
  type PoolMasterDataSyncStatus,
} from '../../../api/intercompanyPools'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import { findRegistryEntryByEntityType, getSyncEntityOptions } from './registry'
import { SyncLaunchDrawer } from './SyncLaunchDrawer'

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

const LAUNCH_STATUS_COLORS: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
}

const LAUNCH_ITEM_STATUS_COLORS: Record<string, string> = {
  pending: 'default',
  scheduled: 'processing',
  coalesced: 'blue',
  skipped: 'default',
  failed: 'error',
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

const buildLaunchSummary = (launch: PoolMasterDataSyncLaunch): string => (
  launch.target_mode === 'cluster_all'
    ? `cluster_all · ${launch.database_ids.length} db`
    : `database_set · ${launch.database_ids.length} db`
)

export function SyncStatusTab({ registryEntries }: SyncStatusTabProps) {
  const { message } = AntApp.useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const [clusters, setClusters] = useState<Array<{ id: string; name: string }>>([])
  const [databases, setDatabases] = useState<Array<{ id: string; name: string; cluster_id: string | null }>>([])
  const [databaseId, setDatabaseId] = useState<string | undefined>(searchParams.get('databaseId')?.trim() || undefined)
  const [entityType, setEntityType] = useState<string | undefined>(searchParams.get('entityType')?.trim() || undefined)
  const [priority, setPriority] = useState<PoolMasterDataSyncPriority | undefined>(undefined)
  const [role, setRole] = useState<PoolMasterDataSyncRole | undefined>(undefined)
  const [serverAffinity, setServerAffinity] = useState<string | undefined>(undefined)
  const [deadlineState, setDeadlineState] = useState<PoolMasterDataSyncDeadlineState | undefined>(undefined)
  const [conflictStatus, setConflictStatus] = useState<'pending' | 'retrying' | 'resolved' | undefined>(undefined)
  const [statusRows, setStatusRows] = useState<PoolMasterDataSyncStatus[]>([])
  const [conflictRows, setConflictRows] = useState<PoolMasterDataSyncConflict[]>([])
  const [launches, setLaunches] = useState<PoolMasterDataSyncLaunch[]>([])
  const [selectedLaunchId, setSelectedLaunchId] = useState<string | null>(searchParams.get('launchId')?.trim() || null)
  const [selectedLaunch, setSelectedLaunch] = useState<PoolMasterDataSyncLaunch | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingTargets, setLoadingTargets] = useState(false)
  const [loadingLaunches, setLoadingLaunches] = useState(false)
  const [loadingLaunchDetail, setLoadingLaunchDetail] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [actionConflictId, setActionConflictId] = useState<string | null>(null)

  const filterEntityTypeOptions = useMemo(
    () => getSyncEntityOptions(registryEntries),
    [registryEntries]
  )
  const visibleSyncEntityTypes = useMemo(
    () => new Set(filterEntityTypeOptions.map((option) => option.value)),
    [filterEntityTypeOptions]
  )

  const databaseNameById = useMemo(() => {
    const lookup = new Map<string, string>()
    for (const database of databases) {
      lookup.set(database.id, database.name)
    }
    return lookup
  }, [databases])

  const clusterNameById = useMemo(() => {
    const lookup = new Map<string, string>()
    for (const cluster of clusters) {
      lookup.set(cluster.id, cluster.name)
    }
    return lookup
  }, [clusters])

  const updateRouteParams = useCallback((updates: Record<string, string | null | undefined>) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      Object.entries(updates).forEach(([key, value]) => {
        const normalized = typeof value === 'string' ? value.trim() : ''
        if (normalized) {
          next.set(key, normalized)
        } else {
          next.delete(key)
        }
      })
      return next
    }, { replace: true })
  }, [setSearchParams])

  const loadTargets = useCallback(async () => {
    setLoadingTargets(true)
    try {
      const [clusterRows, databaseRows] = await Promise.all([
        listPoolTargetClusters(),
        listPoolTargetDatabases(),
      ])
      setClusters(clusterRows)
      setDatabases(databaseRows)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить кластеры и базы для Sync.')
      message.error(resolved.message)
    } finally {
      setLoadingTargets(false)
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

  const loadLaunches = useCallback(async () => {
    setLoadingLaunches(true)
    try {
      const response = await listPoolMasterDataSyncLaunches({
        limit: 20,
        offset: 0,
      })
      setLaunches(response.launches)
      if (!selectedLaunchId && response.launches.length > 0) {
        const nextId = response.launches[0].id
        setSelectedLaunchId(nextId)
        updateRouteParams({ launchId: nextId })
      }
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить launch history.')
      message.error(resolved.message)
    } finally {
      setLoadingLaunches(false)
    }
  }, [message, selectedLaunchId, updateRouteParams])

  const loadLaunchDetail = useCallback(async (launchId: string, silent = false) => {
    if (!silent) {
      setLoadingLaunchDetail(true)
    }
    try {
      const response = await getPoolMasterDataSyncLaunch(launchId)
      setSelectedLaunch(response.launch)
    } catch (error) {
      if (!silent) {
        const resolved = resolveApiError(error, 'Не удалось загрузить детали manual sync launch.')
        message.error(resolved.message)
      }
    } finally {
      if (!silent) {
        setLoadingLaunchDetail(false)
      }
    }
  }, [message])

  useEffect(() => {
    void loadTargets()
    void loadData()
    void loadLaunches()
  }, [loadData, loadLaunches, loadTargets])

  useEffect(() => {
    const nextDatabaseId = searchParams.get('databaseId')?.trim() || undefined
    const nextEntityType = searchParams.get('entityType')?.trim() || undefined
    const nextLaunchId = searchParams.get('launchId')?.trim() || null
    setDatabaseId((current) => (current === nextDatabaseId ? current : nextDatabaseId))
    setEntityType((current) => (current === nextEntityType ? current : nextEntityType))
    setSelectedLaunchId((current) => (current === nextLaunchId ? current : nextLaunchId))
  }, [searchParams])

  useEffect(() => {
    if (!selectedLaunchId) {
      setSelectedLaunch(null)
      return
    }
    void loadLaunchDetail(selectedLaunchId)
  }, [loadLaunchDetail, selectedLaunchId])

  useEffect(() => {
    if (!selectedLaunchId || !selectedLaunch) {
      return
    }
    if (selectedLaunch.status !== 'pending' && selectedLaunch.status !== 'running') {
      return
    }
    const timer = window.setInterval(() => {
      void loadLaunchDetail(selectedLaunchId, true)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [loadLaunchDetail, selectedLaunch, selectedLaunchId])

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

  const handleSelectLaunch = useCallback((launchId: string) => {
    setSelectedLaunchId(launchId)
    updateRouteParams({ launchId })
  }, [updateRouteParams])

  const handoffToScope = useCallback((item: PoolMasterDataSyncLaunchItem, target: 'status' | 'conflicts') => {
    setDatabaseId(item.database_id)
    setEntityType(item.entity_type)
    if (target === 'conflicts') {
      setConflictStatus('pending')
    }
    updateRouteParams({
      databaseId: item.database_id,
      entityType: item.entity_type,
      launchId: selectedLaunchId,
    })
  }, [selectedLaunchId, updateRouteParams])

  const submitLaunch = useCallback(async (payload: {
    mode: PoolMasterDataSyncLaunchMode
    target_mode: 'cluster_all' | 'database_set'
    cluster_id?: string
    database_ids?: string[]
    entity_scope: string[]
  }) => {
    const response = await createPoolMasterDataSyncLaunch(payload)
    setDrawerOpen(false)
    setSelectedLaunchId(response.launch.id)
    updateRouteParams({ launchId: response.launch.id })
    message.success('Manual sync launch создан.')
    await Promise.all([
      loadLaunches(),
      loadLaunchDetail(response.launch.id),
    ])
  }, [loadLaunchDetail, loadLaunches, message, updateRouteParams])

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

  const launchColumns: ColumnsType<PoolMasterDataSyncLaunch> = [
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: 'Mode',
      dataIndex: 'mode',
      key: 'mode',
      width: 120,
      render: (value: string) => <Tag color="blue">{value}</Tag>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (value: string) => <Tag color={LAUNCH_STATUS_COLORS[value] || 'default'}>{value}</Tag>,
    },
    {
      title: 'Targets',
      key: 'targets',
      width: 220,
      render: (_, row) => buildLaunchSummary(row),
    },
    {
      title: 'Entities',
      dataIndex: 'entity_scope',
      key: 'entity_scope',
      width: 220,
      render: (value: string[]) => value.join(', '),
    },
    {
      title: 'Requested By',
      dataIndex: 'requested_by_username',
      key: 'requested_by_username',
      width: 180,
      render: (value: string) => value || <Text type="secondary">service</Text>,
    },
    {
      title: 'Counters',
      key: 'counters',
      width: 260,
      render: (_, row) => {
        const counters = row.aggregate_counters ?? {}
        return (
          <Space size={4} wrap>
            <Tag>scheduled {counters.scheduled ?? 0}</Tag>
            <Tag color="blue">coalesced {counters.coalesced ?? 0}</Tag>
            <Tag>skipped {counters.skipped ?? 0}</Tag>
            <Tag color="red">failed {counters.failed ?? 0}</Tag>
            <Tag color="green">completed {counters.completed ?? 0}</Tag>
          </Space>
        )
      },
    },
  ]

  const launchItemColumns: ColumnsType<PoolMasterDataSyncLaunchItem> = [
    {
      title: 'Database',
      dataIndex: 'database_name',
      key: 'database_name',
      width: 220,
    },
    {
      title: 'Entity',
      dataIndex: 'entity_type',
      key: 'entity_type',
      width: 120,
    },
    {
      title: 'Outcome',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (value: string) => (
        <Tag color={LAUNCH_ITEM_STATUS_COLORS[value] || 'default'}>{value}</Tag>
      ),
    },
    {
      title: 'Child Job',
      key: 'child_job',
      width: 280,
      render: (_, row) => (
        row.child_job_id
          ? (
            <Space direction="vertical" size={0}>
              <Text code>{row.child_job_id}</Text>
              {row.child_job_status ? <Text type="secondary">{row.child_job_status}</Text> : null}
            </Space>
          )
          : <Text type="secondary">-</Text>
      ),
    },
    {
      title: 'Reason',
      key: 'reason',
      width: 260,
      render: (_, row) => (
        row.reason_code
          ? (
            <Space direction="vertical" size={0}>
              <Tag color="red">{row.reason_code}</Tag>
              {row.reason_detail ? <Text type="secondary">{row.reason_detail}</Text> : null}
            </Space>
          )
          : <Text type="secondary">-</Text>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 220,
      render: (_, row) => (
        <Space>
          <Button size="small" onClick={() => handoffToScope(row, 'status')}>
            Filter Status
          </Button>
          <Button size="small" onClick={() => handoffToScope(row, 'conflicts')}>
            Filter Conflicts
          </Button>
        </Space>
      ),
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
            <Button size="small" type="link" href={buildDedupeReviewHref(row) || undefined}>
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
            onChange={(value) => {
              setDatabaseId(value)
              updateRouteParams({ databaseId: value, entityType })
            }}
            style={{ width: 280 }}
          />
          <Select
            data-testid="sync-status-filter-entity-type"
            allowClear
            placeholder="Entity type"
            value={entityType}
            options={filterEntityTypeOptions}
            onChange={(value) => {
              setEntityType(value)
              updateRouteParams({ databaseId, entityType: value })
            }}
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
          <Button
            data-testid="sync-launch-open-drawer"
            type="primary"
            onClick={() => setDrawerOpen(true)}
            loading={loadingTargets}
          >
            Launch Sync
          </Button>
          <Button data-testid="sync-status-refresh" onClick={() => {
            void loadData()
            void loadLaunches()
            if (selectedLaunchId) {
              void loadLaunchDetail(selectedLaunchId)
            }
          }} loading={loading || loadingLaunches}>
            Refresh
          </Button>
        </Space>
        <Text type="secondary">
          Monitor lag/retries/checkpoints, launch cluster-wide sync waves, and manage conflict queue actions in one place.
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

      <Card title="Launch History">
        <Table
          rowKey="id"
          loading={loadingLaunches}
          columns={launchColumns}
          dataSource={launches}
          pagination={false}
          scroll={{ x: 1640 }}
          onRow={(record) => ({
            onClick: () => handleSelectLaunch(record.id),
          })}
        />
      </Card>

      {selectedLaunch ? (
        <Card
          title="Launch Detail"
          loading={loadingLaunchDetail}
          extra={selectedLaunch.status ? <Tag color={LAUNCH_STATUS_COLORS[selectedLaunch.status] || 'default'}>{selectedLaunch.status}</Tag> : null}
        >
          <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="Launch ID">{selectedLaunch.id}</Descriptions.Item>
            <Descriptions.Item label="Mode">{selectedLaunch.mode}</Descriptions.Item>
            <Descriptions.Item label="Requested By">
              {selectedLaunch.requested_by_username || 'service'}
            </Descriptions.Item>
            <Descriptions.Item label="Created">{formatDateTime(selectedLaunch.created_at)}</Descriptions.Item>
            <Descriptions.Item label="Targets">
              {selectedLaunch.target_mode === 'cluster_all'
                ? `${clusterNameById.get(selectedLaunch.cluster_id ?? '') || selectedLaunch.cluster_id || 'cluster_all'} · ${selectedLaunch.database_ids.length} db`
                : `${selectedLaunch.database_ids.length} db`}
            </Descriptions.Item>
            <Descriptions.Item label="Entities">{selectedLaunch.entity_scope.join(', ')}</Descriptions.Item>
            <Descriptions.Item label="Workflow Execution">
              {selectedLaunch.workflow_execution_id ? <Text code>{selectedLaunch.workflow_execution_id}</Text> : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="Operation">
              {selectedLaunch.operation_id ? <Text code>{selectedLaunch.operation_id}</Text> : '-'}
            </Descriptions.Item>
          </Descriptions>

          <Space wrap style={{ marginBottom: 12 }}>
            <Tag>scheduled {selectedLaunch.aggregate_counters?.scheduled ?? 0}</Tag>
            <Tag color="blue">coalesced {selectedLaunch.aggregate_counters?.coalesced ?? 0}</Tag>
            <Tag>skipped {selectedLaunch.aggregate_counters?.skipped ?? 0}</Tag>
            <Tag color="red">failed {selectedLaunch.aggregate_counters?.failed ?? 0}</Tag>
            <Tag color="green">completed {selectedLaunch.aggregate_counters?.completed ?? 0}</Tag>
            <Tag>terminal {selectedLaunch.progress?.terminal_items ?? 0}</Tag>
          </Space>

          {selectedLaunch.last_error_code || selectedLaunch.last_error ? (
            <Card size="small" style={{ marginBottom: 16 }}>
              <Space direction="vertical" size={4}>
                {selectedLaunch.last_error_code ? <Tag color="red">{selectedLaunch.last_error_code}</Tag> : null}
                {selectedLaunch.last_error ? <Text type="secondary">{selectedLaunch.last_error}</Text> : null}
              </Space>
            </Card>
          ) : null}

          <Table
            rowKey="id"
            columns={launchItemColumns}
            dataSource={selectedLaunch.items ?? []}
            pagination={false}
            scroll={{ x: 1320 }}
          />
        </Card>
      ) : null}

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

      <SyncLaunchDrawer
        open={drawerOpen}
        clusters={clusters}
        databases={databases}
        clusterNameById={clusterNameById}
        registryEntries={registryEntries}
        loadingTargets={loadingTargets}
        onClose={() => setDrawerOpen(false)}
        onSubmit={submitLaunch}
      />
    </Space>
  )
}
