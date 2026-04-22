import { useCallback, useEffect, useMemo, useState } from 'react'
import { App as AntApp, Alert, Button, Card, Descriptions, Input, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { createPoolMasterDataSyncLaunch, getPoolMasterDataSyncLaunch, listMasterDataSyncConflicts, listMasterDataSyncStatus, listPoolMasterDataSyncLaunches, listPoolTargetClusters, listPoolTargetDatabases, reconcileMasterDataSyncConflict, resolveMasterDataSyncConflict, retryMasterDataSyncConflict, type PoolMasterDataRegistryEntry, type PoolMasterDataSyncConflict, type PoolMasterDataSyncDeadlineState, type PoolMasterDataSyncLaunch, type PoolMasterDataSyncLaunchItem, type PoolMasterDataSyncLaunchMode, type PoolMasterDataSyncPriority, type PoolMasterDataSyncRole, type PoolMasterDataSyncStatus } from '../../../api/intercompanyPools'
import { usePoolsTranslation } from '../../../i18n'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import { findRegistryEntryByEntityType, getSyncEntityOptions } from './registry'
import { SyncLaunchDrawer } from './SyncLaunchDrawer'

const { Text } = Typography

const CONFLICT_STATUS_OPTIONS: {
  value: 'pending' | 'retrying' | 'resolved'
  label: string
}[] = [
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

const DEADLINE_STATE_OPTIONS: {
  value: PoolMasterDataSyncDeadlineState
  label: string
}[] = [
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
  const reviewItemId = typeof diagnostics.dedupe_review_item_id === 'string' ? diagnostics.dedupe_review_item_id.trim() : ''
  const clusterId = typeof diagnostics.dedupe_cluster_id === 'string' ? diagnostics.dedupe_cluster_id.trim() : ''
  const entityType = typeof diagnostics.entity_type === 'string' ? diagnostics.entity_type.trim() : conflict.entity_type
  const canonicalId = typeof diagnostics.canonical_id === 'string' ? diagnostics.canonical_id.trim() : conflict.canonical_id

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

type SyncLoadScope = 'targets' | 'status' | 'launches' | 'launch_detail'

type SyncLoadDiagnostic = {
  scope: SyncLoadScope
  message: string
  rateLimitClass?: string
  retryAfterSeconds?: number
  budgetScope?: string
  requestId?: string
}

export function SyncStatusTab({ registryEntries }: SyncStatusTabProps) {
  const { message } = AntApp.useApp()
  const { t } = usePoolsTranslation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [clusters, setClusters] = useState<Array<{ id: string; name: string }>>([])
  const [databases, setDatabases] = useState<
    Array<{
      id: string
      name: string
      cluster_id: string | null
      cluster_all_eligibility_state: 'eligible' | 'excluded' | 'unconfigured'
    }>
  >([])
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
  const [loadDiagnostic, setLoadDiagnostic] = useState<SyncLoadDiagnostic | null>(null)

  const filterEntityTypeOptions = useMemo(() => getSyncEntityOptions(registryEntries), [registryEntries])
  const conflictStatusOptions = useMemo(
    () =>
      CONFLICT_STATUS_OPTIONS.map((option) => ({
        ...option,
        label: t(`masterData.syncStatusTab.status.${option.value}`),
      })),
    [t],
  )
  const priorityOptions = useMemo(
    () =>
      PRIORITY_OPTIONS.map((option) => ({
        ...option,
        label: t(`masterData.syncStatusTab.priority.${option.value}`),
      })),
    [t],
  )
  const roleOptions = useMemo(
    () =>
      ROLE_OPTIONS.map((option) => ({
        ...option,
        label: t(`masterData.syncStatusTab.role.${option.value}`),
      })),
    [t],
  )
  const deadlineStateOptions = useMemo(
    () =>
      DEADLINE_STATE_OPTIONS.map((option) => ({
        ...option,
        label: t(`masterData.syncStatusTab.deadline.${option.value}`),
      })),
    [t],
  )
  const visibleSyncEntityTypes = useMemo(() => new Set(filterEntityTypeOptions.map((option) => option.value)), [filterEntityTypeOptions])

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

  const updateRouteParams = useCallback(
    (updates: Record<string, string | null | undefined>) => {
      setSearchParams(
        (current) => {
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
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const clearLoadDiagnostic = useCallback((scope?: SyncLoadScope) => {
    setLoadDiagnostic((current) => {
      if (!current) {
        return current
      }
      if (scope && current.scope !== scope) {
        return current
      }
      return null
    })
  }, [])

  const captureRateLimitDiagnostic = useCallback((scope: SyncLoadScope, error: unknown): boolean => {
    const resolved = resolveApiError(error, '')
    if (resolved.status !== 429) {
      return false
    }

    setLoadDiagnostic({
      scope,
      message: resolved.message,
      rateLimitClass: resolved.rateLimitClass,
      retryAfterSeconds: resolved.retryAfterSeconds,
      budgetScope: resolved.budgetScope,
      requestId: resolved.requestId,
    })
    return true
  }, [])

  const loadTargets = useCallback(async () => {
    setLoadingTargets(true)
    try {
      const [clusterRows, databaseRows] = await Promise.all([listPoolTargetClusters(), listPoolTargetDatabases()])
      setClusters(clusterRows)
      setDatabases(databaseRows)
      clearLoadDiagnostic('targets')
    } catch (error) {
      if (captureRateLimitDiagnostic('targets', error)) {
        return
      }
      const resolved = resolveApiError(error, t('masterData.syncStatusTab.messages.failedToLoadTargets'))
      message.error(resolved.message)
    } finally {
      setLoadingTargets(false)
    }
  }, [captureRateLimitDiagnostic, clearLoadDiagnostic, message, t])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const statusResponse = await listMasterDataSyncStatus({
        database_id: databaseId,
        entity_type: entityType,
        priority,
        role,
        server_affinity: serverAffinity,
        deadline_state: deadlineState,
      })
      setStatusRows(statusResponse.statuses)

      const conflictsResponse = await listMasterDataSyncConflicts({
        database_id: databaseId,
        entity_type: entityType,
        status: conflictStatus,
        limit: 200,
      })
      setConflictRows(conflictsResponse.conflicts)
      clearLoadDiagnostic('status')
    } catch (error) {
      if (captureRateLimitDiagnostic('status', error)) {
        return
      }
      const resolved = resolveApiError(error, t('masterData.syncStatusTab.messages.failedToLoadStatus'))
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [captureRateLimitDiagnostic, clearLoadDiagnostic, conflictStatus, databaseId, deadlineState, entityType, message, priority, role, serverAffinity, t])

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
      clearLoadDiagnostic('launches')
    } catch (error) {
      if (captureRateLimitDiagnostic('launches', error)) {
        return
      }
      const resolved = resolveApiError(error, t('masterData.syncStatusTab.messages.failedToLoadLaunchHistory'))
      message.error(resolved.message)
    } finally {
      setLoadingLaunches(false)
    }
  }, [captureRateLimitDiagnostic, clearLoadDiagnostic, message, selectedLaunchId, t, updateRouteParams])

  const loadLaunchDetail = useCallback(
    async (launchId: string, silent = false) => {
      if (!silent) {
        setLoadingLaunchDetail(true)
      }
      try {
        const response = await getPoolMasterDataSyncLaunch(launchId)
        setSelectedLaunch(response.launch)
        clearLoadDiagnostic('launch_detail')
      } catch (error) {
        if (captureRateLimitDiagnostic('launch_detail', error)) {
          return
        }
        if (!silent) {
          const resolved = resolveApiError(error, t('masterData.syncStatusTab.messages.failedToLoadLaunchDetail'))
          message.error(resolved.message)
        }
      } finally {
        if (!silent) {
          setLoadingLaunchDetail(false)
        }
      }
    },
    [captureRateLimitDiagnostic, clearLoadDiagnostic, message, t],
  )

  const hydrateWorkspace = useCallback(async () => {
    clearLoadDiagnostic()
    await Promise.all([loadTargets(), loadLaunches()])
    await loadData()
  }, [clearLoadDiagnostic, loadData, loadLaunches, loadTargets])

  useEffect(() => {
    void hydrateWorkspace()
  }, [hydrateWorkspace])

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
            note: t('masterData.syncStatusTab.messages.manualRetryNote'),
          })
          message.success(t('masterData.syncStatusTab.messages.retrying'))
        } else if (action === 'reconcile') {
          await reconcileMasterDataSyncConflict(conflict.id, {
            note: t('masterData.syncStatusTab.messages.manualReconcileNote'),
            reconcile_payload: { strategy: 'manual_reconcile' },
          })
          message.success(t('masterData.syncStatusTab.messages.reconcileQueued'))
        } else {
          await resolveMasterDataSyncConflict(conflict.id, {
            resolution_code: 'MANUAL_RECONCILE',
            note: t('masterData.syncStatusTab.messages.manualResolveNote'),
            metadata: { source: 'ui' },
          })
          message.success(t('masterData.syncStatusTab.messages.resolved'))
        }
        await loadData()
      } catch (error) {
        const resolved = resolveApiError(error, t('masterData.syncStatusTab.messages.failedToRunConflictAction'))
        message.error(resolved.message)
      } finally {
        setActionConflictId(null)
      }
    },
    [loadData, message, t],
  )

  const canRunConflictWorkflowAction = useCallback(
    (conflict: PoolMasterDataSyncConflict): boolean => {
      const entry = findRegistryEntryByEntityType(registryEntries, conflict.entity_type)
      if (!entry) {
        return false
      }
      return String(conflict.origin_system || '')
        .trim()
        .toLowerCase() === 'ib'
        ? entry.capabilities.sync_inbound
        : entry.capabilities.sync_outbound
    },
    [registryEntries],
  )

  const handleSelectLaunch = useCallback(
    (launchId: string) => {
      setSelectedLaunchId(launchId)
      updateRouteParams({ launchId })
    },
    [updateRouteParams],
  )

  const handoffToScope = useCallback(
    (item: PoolMasterDataSyncLaunchItem, target: 'status' | 'conflicts') => {
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
    },
    [selectedLaunchId, updateRouteParams],
  )

  const submitLaunch = useCallback(
    async (payload: { mode: PoolMasterDataSyncLaunchMode; target_mode: 'cluster_all' | 'database_set'; cluster_id?: string; database_ids?: string[]; entity_scope: string[] }) => {
      const response = await createPoolMasterDataSyncLaunch(payload)
      setDrawerOpen(false)
      setSelectedLaunchId(response.launch.id)
      updateRouteParams({ launchId: response.launch.id })
      message.success(t('masterData.syncStatusTab.messages.launchCreated'))
      await Promise.all([loadLaunches(), loadLaunchDetail(response.launch.id)])
    },
    [loadLaunchDetail, loadLaunches, message, t, updateRouteParams],
  )

  const openEligibilityContext = useCallback(
    (context: { clusterId: string; databaseId?: string }) => {
      const next = new URLSearchParams()
      next.set('cluster', context.clusterId)
      next.set('context', 'metadata')
      if (context.databaseId) {
        next.set('database', context.databaseId)
      }
      navigate(`/databases?${next.toString()}`)
    },
    [navigate],
  )

  const visibleStatusRows = useMemo(() => statusRows.filter((row) => visibleSyncEntityTypes.has(row.entity_type)), [statusRows, visibleSyncEntityTypes])
  const loadDiagnosticDescription = useMemo(() => {
    if (!loadDiagnostic) {
      return null
    }

    const descriptionParts: string[] = []
    if (loadDiagnostic.retryAfterSeconds) {
      descriptionParts.push(
        t('masterData.syncStatusTab.diagnostics.retryAfter', {
          seconds: loadDiagnostic.retryAfterSeconds,
        }),
      )
    }
    if (loadDiagnostic.rateLimitClass) {
      descriptionParts.push(
        t('masterData.syncStatusTab.diagnostics.rateLimitClass', {
          value: loadDiagnostic.rateLimitClass,
        }),
      )
    }
    if (loadDiagnostic.budgetScope) {
      descriptionParts.push(
        t('masterData.syncStatusTab.diagnostics.budgetScope', {
          value: loadDiagnostic.budgetScope,
        }),
      )
    }
    if (loadDiagnostic.requestId) {
      descriptionParts.push(
        t('masterData.syncStatusTab.diagnostics.requestId', {
          value: loadDiagnostic.requestId,
        }),
      )
    }

    return descriptionParts.join(' ')
  }, [loadDiagnostic, t])

  const buildLaunchSummary = useCallback(
    (launch: PoolMasterDataSyncLaunch): string =>
      launch.target_mode === 'cluster_all'
        ? t('masterData.syncStatusTab.launchSummary.clusterAll', {
            count: launch.database_ids.length,
          })
        : t('masterData.syncStatusTab.launchSummary.databaseSet', {
            count: launch.database_ids.length,
          }),
    [t],
  )

  const statusColumns: ColumnsType<PoolMasterDataSyncStatus> = [
    {
      title: t('masterData.syncStatusTab.columns.database'),
      dataIndex: 'database_id',
      key: 'database_id',
      width: 260,
      render: (value: string) => databaseNameById.get(value) || value,
    },
    {
      title: t('masterData.syncStatusTab.columns.entity'),
      dataIndex: 'entity_type',
      key: 'entity_type',
      width: 120,
    },
    {
      title: t('masterData.syncStatusTab.columns.checkpoint'),
      dataIndex: 'checkpoint_token',
      key: 'checkpoint_token',
      width: 220,
    },
    {
      title: t('masterData.syncStatusTab.columns.pending'),
      dataIndex: 'pending_count',
      key: 'pending_count',
      width: 100,
    },
    {
      title: t('masterData.syncStatusTab.columns.retry'),
      dataIndex: 'retry_count',
      key: 'retry_count',
      width: 100,
    },
    {
      title: t('masterData.syncStatusTab.columns.conflicts'),
      dataIndex: 'conflict_pending_count',
      key: 'conflict_pending_count',
      width: 120,
    },
    {
      title: t('masterData.syncStatusTab.columns.lagSeconds'),
      dataIndex: 'lag_seconds',
      key: 'lag_seconds',
      width: 100,
    },
    {
      title: t('masterData.syncStatusTab.columns.priority'),
      dataIndex: 'priority',
      key: 'priority',
      width: 120,
      render: (value: PoolMasterDataSyncStatus['priority']) => (value ? <Tag>{t(`masterData.syncStatusTab.priority.${value}`)}</Tag> : <Text type="secondary">{t('common.noValue')}</Text>),
    },
    {
      title: t('masterData.syncStatusTab.columns.role'),
      dataIndex: 'role',
      key: 'role',
      width: 180,
      render: (value: PoolMasterDataSyncStatus['role']) => (value ? <Tag color="blue">{t(`masterData.syncStatusTab.role.${value}`)}</Tag> : <Text type="secondary">{t('common.noValue')}</Text>),
    },
    {
      title: t('masterData.syncStatusTab.columns.serverAffinity'),
      dataIndex: 'server_affinity',
      key: 'server_affinity',
      width: 200,
      render: (value: string) => (value ? <Text code>{value}</Text> : <Text type="secondary">{t('common.noValue')}</Text>),
    },
    {
      title: t('masterData.syncStatusTab.columns.deadlineState'),
      dataIndex: 'deadline_state',
      key: 'deadline_state',
      width: 160,
      render: (value: PoolMasterDataSyncStatus['deadline_state']) => <Tag color={DEADLINE_STATE_COLORS[value]}>{t(`masterData.syncStatusTab.deadline.${value}`)}</Tag>,
    },
    {
      title: t('masterData.syncStatusTab.columns.lastSuccess'),
      dataIndex: 'last_success_at',
      key: 'last_success_at',
      width: 220,
      render: (value: string | null) => formatDateTime(value),
    },
    {
      title: t('masterData.syncStatusTab.columns.error'),
      dataIndex: 'last_error_code',
      key: 'last_error_code',
      width: 220,
      render: (value: string) => (value ? <Tag color="red">{value}</Tag> : <Text type="secondary">{t('common.noValue')}</Text>),
    },
  ]

  const launchColumns: ColumnsType<PoolMasterDataSyncLaunch> = [
    {
      title: t('masterData.syncStatusTab.columns.created'),
      dataIndex: 'created_at',
      key: 'created_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: t('masterData.syncStatusTab.columns.mode'),
      dataIndex: 'mode',
      key: 'mode',
      width: 120,
      render: (value: string) => <Tag color="blue">{t(`masterData.syncLaunchDrawer.mode.${value}`)}</Tag>,
    },
    {
      title: t('masterData.syncStatusTab.columns.status'),
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (value: string) => <Tag color={LAUNCH_STATUS_COLORS[value] || 'default'}>{value}</Tag>,
    },
    {
      title: t('masterData.syncStatusTab.columns.targets'),
      key: 'targets',
      width: 220,
      render: (_, row) => buildLaunchSummary(row),
    },
    {
      title: t('masterData.syncStatusTab.columns.entities'),
      dataIndex: 'entity_scope',
      key: 'entity_scope',
      width: 220,
      render: (value: string[]) => value.join(', '),
    },
    {
      title: t('masterData.syncStatusTab.columns.requestedBy'),
      dataIndex: 'requested_by_username',
      key: 'requested_by_username',
      width: 180,
      render: (value: string) => value || <Text type="secondary">{t('masterData.syncStatusTab.serviceUser')}</Text>,
    },
    {
      title: t('masterData.syncStatusTab.columns.counters'),
      key: 'counters',
      width: 260,
      render: (_, row) => {
        const counters = row.aggregate_counters ?? {}
        return (
          <Space size={4} wrap>
            <Tag>
              {t('masterData.syncStatusTab.counterSummary.scheduled', {
                count: counters.scheduled ?? 0,
              })}
            </Tag>
            <Tag color="blue">
              {t('masterData.syncStatusTab.counterSummary.coalesced', {
                count: counters.coalesced ?? 0,
              })}
            </Tag>
            <Tag>
              {t('masterData.syncStatusTab.counterSummary.skipped', {
                count: counters.skipped ?? 0,
              })}
            </Tag>
            <Tag color="red">
              {t('masterData.syncStatusTab.counterSummary.failed', {
                count: counters.failed ?? 0,
              })}
            </Tag>
            <Tag color="green">
              {t('masterData.syncStatusTab.counterSummary.completed', {
                count: counters.completed ?? 0,
              })}
            </Tag>
          </Space>
        )
      },
    },
  ]

  const launchItemColumns: ColumnsType<PoolMasterDataSyncLaunchItem> = [
    {
      title: t('masterData.syncStatusTab.columns.database'),
      dataIndex: 'database_name',
      key: 'database_name',
      width: 220,
    },
    {
      title: t('masterData.syncStatusTab.columns.entity'),
      dataIndex: 'entity_type',
      key: 'entity_type',
      width: 120,
    },
    {
      title: t('masterData.syncStatusTab.columns.outcome'),
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (value: string) => <Tag color={LAUNCH_ITEM_STATUS_COLORS[value] || 'default'}>{value}</Tag>,
    },
    {
      title: t('masterData.syncStatusTab.columns.childJob'),
      key: 'child_job',
      width: 280,
      render: (_, row) =>
        row.child_job_id ? (
          <Space direction="vertical" size={0}>
            <Text code>{row.child_job_id}</Text>
            {row.child_job_status ? <Text type="secondary">{row.child_job_status}</Text> : null}
          </Space>
        ) : (
          <Text type="secondary">{t('common.noValue')}</Text>
        ),
    },
    {
      title: t('masterData.syncStatusTab.columns.reason'),
      key: 'reason',
      width: 260,
      render: (_, row) =>
        row.reason_code ? (
          <Space direction="vertical" size={0}>
            <Tag color="red">{row.reason_code}</Tag>
            {row.reason_detail ? <Text type="secondary">{row.reason_detail}</Text> : null}
          </Space>
        ) : (
          <Text type="secondary">{t('common.noValue')}</Text>
        ),
    },
    {
      title: t('masterData.syncStatusTab.columns.actions'),
      key: 'actions',
      width: 220,
      render: (_, row) => (
        <Space>
          <Button size="small" onClick={() => handoffToScope(row, 'status')}>
            {t('masterData.syncStatusTab.actions.filterStatus')}
          </Button>
          <Button size="small" onClick={() => handoffToScope(row, 'conflicts')}>
            {t('masterData.syncStatusTab.actions.filterConflicts')}
          </Button>
        </Space>
      ),
    },
  ]

  const conflictColumns: ColumnsType<PoolMasterDataSyncConflict> = [
    {
      title: t('masterData.syncStatusTab.columns.created'),
      dataIndex: 'created_at',
      key: 'created_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: t('masterData.syncStatusTab.columns.status'),
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (value: string) => <Tag color={value === 'resolved' ? 'green' : value === 'retrying' ? 'gold' : 'red'}>{value}</Tag>,
    },
    {
      title: t('masterData.syncStatusTab.columns.entity'),
      dataIndex: 'entity_type',
      key: 'entity_type',
      width: 120,
    },
    {
      title: t('masterData.syncStatusTab.columns.database'),
      dataIndex: 'database_id',
      key: 'database_id',
      width: 240,
      render: (value: string) => databaseNameById.get(value) || value,
    },
    {
      title: t('masterData.syncStatusTab.columns.canonicalId'),
      dataIndex: 'canonical_id',
      key: 'canonical_id',
      width: 200,
    },
    {
      title: t('masterData.syncStatusTab.columns.conflictCode'),
      dataIndex: 'conflict_code',
      key: 'conflict_code',
      width: 220,
    },
    {
      title: t('masterData.syncStatusTab.columns.origin'),
      key: 'origin',
      width: 220,
      render: (_, row) => `${row.origin_system || t('common.noValue')}:${row.origin_event_id || t('common.noValue')}`,
    },
    {
      title: t('masterData.syncStatusTab.columns.actions'),
      key: 'actions',
      width: 300,
      render: (_, row) => (
        <Space>
          {buildDedupeReviewHref(row) ? (
            <Button size="small" type="link" href={buildDedupeReviewHref(row) || undefined}>
              {t('masterData.syncStatusTab.actions.openReview')}
            </Button>
          ) : null}
          {canRunConflictWorkflowAction(row) && (
            <Button size="small" onClick={() => void runConflictAction(row, 'retry')} loading={actionConflictId === row.id} disabled={row.status === 'resolved'}>
              {t('masterData.syncStatusTab.actions.retry')}
            </Button>
          )}
          {canRunConflictWorkflowAction(row) && (
            <Button size="small" onClick={() => void runConflictAction(row, 'reconcile')} loading={actionConflictId === row.id} disabled={row.status === 'resolved'}>
              {t('masterData.syncStatusTab.actions.reconcile')}
            </Button>
          )}
          <Button size="small" type="primary" onClick={() => void runConflictAction(row, 'resolve')} loading={actionConflictId === row.id} disabled={row.status === 'resolved'}>
            {t('masterData.syncStatusTab.actions.resolve')}
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {loadDiagnostic ? (
        <Alert
          type="warning"
          showIcon
          data-testid="sync-rate-limit-alert"
          message={t('masterData.syncStatusTab.diagnostics.rateLimited', {
            scope: t(`masterData.syncStatusTab.diagnostics.scope.${loadDiagnostic.scope}`),
          })}
          description={loadDiagnosticDescription || loadDiagnostic.message}
        />
      ) : null}
      <Card>
        <Space wrap style={{ marginBottom: 16 }}>
          <Select
            allowClear
            placeholder={t('masterData.syncStatusTab.filters.databasePlaceholder')}
            value={databaseId}
            options={databases.map((database) => ({
              value: database.id,
              label: database.name,
            }))}
            onChange={(value) => {
              setDatabaseId(value)
              updateRouteParams({ databaseId: value, entityType })
            }}
            style={{ width: 280 }}
          />
          <Select
            data-testid="sync-status-filter-entity-type"
            allowClear
            placeholder={t('masterData.syncStatusTab.filters.entityTypePlaceholder')}
            value={entityType}
            options={filterEntityTypeOptions}
            onChange={(value) => {
              setEntityType(value)
              updateRouteParams({ databaseId, entityType: value })
            }}
            style={{ width: 180 }}
          />
          <Select data-testid="sync-status-filter-priority" allowClear placeholder={t('masterData.syncStatusTab.filters.priorityPlaceholder')} value={priority} options={priorityOptions} onChange={(value) => setPriority(value)} style={{ width: 160 }} />
          <Select data-testid="sync-status-filter-role" allowClear placeholder={t('masterData.syncStatusTab.filters.rolePlaceholder')} value={role} options={roleOptions} onChange={(value) => setRole(value)} style={{ width: 220 }} />
          <Input
            data-testid="sync-status-filter-server-affinity"
            allowClear
            placeholder={t('masterData.syncStatusTab.filters.serverAffinityPlaceholder')}
            value={serverAffinity}
            onChange={(event) => {
              const value = event.target.value.trim()
              setServerAffinity(value ? value : undefined)
            }}
            style={{ width: 220 }}
          />
          <Select data-testid="sync-status-filter-deadline-state" allowClear placeholder={t('masterData.syncStatusTab.filters.deadlineStatePlaceholder')} value={deadlineState} options={deadlineStateOptions} onChange={(value) => setDeadlineState(value)} style={{ width: 200 }} />
          <Select data-testid="sync-status-filter-conflict-status" allowClear placeholder={t('masterData.syncStatusTab.filters.conflictStatusPlaceholder')} value={conflictStatus} options={conflictStatusOptions} onChange={(value) => setConflictStatus(value)} style={{ width: 200 }} />
          <Button data-testid="sync-launch-open-drawer" type="primary" onClick={() => setDrawerOpen(true)} loading={loadingTargets}>
            {t('masterData.syncStatusTab.actions.launchSync')}
          </Button>
          <Button
            data-testid="sync-status-refresh"
            onClick={() => {
              void loadData()
              void loadLaunches()
              if (selectedLaunchId) {
                void loadLaunchDetail(selectedLaunchId)
              }
            }}
            loading={loading || loadingLaunches}
          >
            {t('catalog.actions.refresh')}
          </Button>
        </Space>
        <Text type="secondary">{t('masterData.syncStatusTab.page.subtitle')}</Text>
      </Card>

      <Card title={t('masterData.syncStatusTab.page.syncStatusTitle')}>
        <Table rowKey={(row) => `${row.database_id}:${row.entity_type}`} loading={loading} columns={statusColumns} dataSource={visibleStatusRows} pagination={false} scroll={{ x: 2320 }} />
      </Card>

      <Card title={t('masterData.syncStatusTab.page.launchHistoryTitle')}>
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
        <Card title={t('masterData.syncStatusTab.page.launchDetailTitle')} loading={loadingLaunchDetail} extra={selectedLaunch.status ? <Tag color={LAUNCH_STATUS_COLORS[selectedLaunch.status] || 'default'}>{selectedLaunch.status}</Tag> : null}>
          <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label={t('masterData.syncStatusTab.details.launchId')}>{selectedLaunch.id}</Descriptions.Item>
            <Descriptions.Item label={t('masterData.syncStatusTab.details.mode')}>{t(`masterData.syncLaunchDrawer.mode.${selectedLaunch.mode}`)}</Descriptions.Item>
            <Descriptions.Item label={t('masterData.syncStatusTab.details.requestedBy')}>{selectedLaunch.requested_by_username || t('masterData.syncStatusTab.serviceUser')}</Descriptions.Item>
            <Descriptions.Item label={t('masterData.syncStatusTab.details.created')}>{formatDateTime(selectedLaunch.created_at)}</Descriptions.Item>
            <Descriptions.Item label={t('masterData.syncStatusTab.details.targets')}>
              {selectedLaunch.target_mode === 'cluster_all'
                ? t('masterData.syncStatusTab.details.clusterTargets', {
                    cluster: clusterNameById.get(selectedLaunch.cluster_id ?? '') || selectedLaunch.cluster_id || 'cluster_all',
                    count: selectedLaunch.database_ids.length,
                  })
                : t('masterData.syncStatusTab.details.databaseTargets', {
                    count: selectedLaunch.database_ids.length,
                  })}
            </Descriptions.Item>
            <Descriptions.Item label={t('masterData.syncStatusTab.details.entities')}>{selectedLaunch.entity_scope.join(', ')}</Descriptions.Item>
            <Descriptions.Item label={t('masterData.syncStatusTab.details.workflowExecution')}>{selectedLaunch.workflow_execution_id ? <Text code>{selectedLaunch.workflow_execution_id}</Text> : t('common.noValue')}</Descriptions.Item>
            <Descriptions.Item label={t('masterData.syncStatusTab.details.operation')}>{selectedLaunch.operation_id ? <Text code>{selectedLaunch.operation_id}</Text> : t('common.noValue')}</Descriptions.Item>
          </Descriptions>

          <Space wrap style={{ marginBottom: 12 }}>
            <Tag>
              {t('masterData.syncStatusTab.counterSummary.scheduled', {
                count: selectedLaunch.aggregate_counters?.scheduled ?? 0,
              })}
            </Tag>
            <Tag color="blue">
              {t('masterData.syncStatusTab.counterSummary.coalesced', {
                count: selectedLaunch.aggregate_counters?.coalesced ?? 0,
              })}
            </Tag>
            <Tag>
              {t('masterData.syncStatusTab.counterSummary.skipped', {
                count: selectedLaunch.aggregate_counters?.skipped ?? 0,
              })}
            </Tag>
            <Tag color="red">
              {t('masterData.syncStatusTab.counterSummary.failed', {
                count: selectedLaunch.aggregate_counters?.failed ?? 0,
              })}
            </Tag>
            <Tag color="green">
              {t('masterData.syncStatusTab.counterSummary.completed', {
                count: selectedLaunch.aggregate_counters?.completed ?? 0,
              })}
            </Tag>
            <Tag>
              {t('masterData.syncStatusTab.counterSummary.terminal', {
                count: selectedLaunch.progress?.terminal_items ?? 0,
              })}
            </Tag>
          </Space>

          {selectedLaunch.target_mode === 'cluster_all' && selectedLaunch.target_resolution ? (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message={t('masterData.syncStatusTab.clusterResolution.summary', {
                eligibleCount: selectedLaunch.target_resolution.eligible_count,
                excludedCount: selectedLaunch.target_resolution.excluded_count,
                unconfiguredCount: selectedLaunch.target_resolution.unconfigured_count,
              })}
              description={
                <Space direction="vertical" size={4}>
                  {selectedLaunch.target_resolution.excluded_databases && selectedLaunch.target_resolution.excluded_databases.length > 0 ? (
                    <Text>
                      {t('masterData.syncStatusTab.clusterResolution.excluded', {
                        databases: selectedLaunch.target_resolution.excluded_databases.map((database) => database.database_name).join(', '),
                      })}
                    </Text>
                  ) : null}
                  {selectedLaunch.target_resolution.excluded_count > 0 ? <Text type="secondary">{t('masterData.syncStatusTab.clusterResolution.useDatabaseSet')}</Text> : null}
                </Space>
              }
            />
          ) : null}

          {selectedLaunch.last_error_code || selectedLaunch.last_error ? (
            <Card size="small" style={{ marginBottom: 16 }}>
              <Space direction="vertical" size={4}>
                {selectedLaunch.last_error_code ? <Tag color="red">{selectedLaunch.last_error_code}</Tag> : null}
                {selectedLaunch.last_error ? <Text type="secondary">{selectedLaunch.last_error}</Text> : null}
              </Space>
            </Card>
          ) : null}

          <Table rowKey="id" columns={launchItemColumns} dataSource={selectedLaunch.items ?? []} pagination={false} scroll={{ x: 1320 }} />
        </Card>
      ) : null}

      <Card title={t('masterData.syncStatusTab.page.conflictQueueTitle')}>
        <Table rowKey="id" loading={loading} columns={conflictColumns} dataSource={conflictRows} pagination={false} scroll={{ x: 1840 }} />
      </Card>

      <SyncLaunchDrawer open={drawerOpen} clusters={clusters} databases={databases} clusterNameById={clusterNameById} registryEntries={registryEntries} loadingTargets={loadingTargets} onClose={() => setDrawerOpen(false)} onOpenEligibilityContext={openEligibilityContext} onSubmit={submitLaunch} />
    </Space>
  )
}
