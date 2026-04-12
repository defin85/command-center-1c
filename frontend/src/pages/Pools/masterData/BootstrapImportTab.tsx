import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Progress,
  Segmented,
  Select,
  Space,
  Steps,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  cancelPoolMasterDataBootstrapImportJob,
  createPoolMasterDataBootstrapCollection,
  createPoolMasterDataBootstrapImportJob,
  getPoolMasterDataBootstrapCollection,
  getPoolMasterDataBootstrapImportJob,
  listPoolMasterDataBootstrapCollections,
  listPoolMasterDataBootstrapImportJobs,
  listPoolTargetClusters,
  listPoolTargetDatabases,
  retryFailedPoolMasterDataBootstrapImportChunks,
  runPoolMasterDataBootstrapCollectionPreflight,
  runPoolMasterDataBootstrapImportPreflight,
  type PoolMasterDataBootstrapCollection,
  type PoolMasterDataBootstrapCollectionItem,
  type PoolMasterDataBootstrapCollectionPreflightResult,
  type PoolMasterDataBootstrapImportChunk,
  type PoolMasterDataBootstrapImportEntityType,
  type PoolMasterDataBootstrapImportJob,
  type PoolMasterDataBootstrapImportPreflightResult,
  type PoolMasterDataRegistryEntry,
  type SimpleClusterRef,
  type SimpleDatabaseRef,
} from '../../../api/intercompanyPools'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import { getBootstrapEntityOptions, getDefaultBootstrapScope } from './registry'

const { Text } = Typography

type BootstrapLauncherMode = 'single' | 'batch'

type BootstrapScopeFormValues = {
  database_id?: string
  target_mode?: 'cluster_all' | 'database_set'
  cluster_id?: string
  database_ids?: string[]
  entity_scope: PoolMasterDataBootstrapImportEntityType[]
}

type PreflightState =
  | { kind: 'single'; result: PoolMasterDataBootstrapImportPreflightResult }
  | { kind: 'batch'; result: PoolMasterDataBootstrapCollectionPreflightResult }
  | null

type DryRunState =
  | { kind: 'single'; summary: Record<string, unknown> }
  | { kind: 'batch'; summary: Record<string, unknown> }
  | null

const TERMINAL_JOB_STATUSES = new Set(['finalized', 'failed', 'canceled'])
const TERMINAL_COLLECTION_STATUSES = new Set([
  'preflight_completed',
  'dry_run_completed',
  'finalized',
  'failed',
])

const STATUS_COLOR: Record<string, string> = {
  preflight_pending: 'processing',
  preflight_failed: 'error',
  dry_run_pending: 'processing',
  dry_run_failed: 'error',
  execute_pending: 'processing',
  running: 'processing',
  finalized: 'success',
  failed: 'error',
  canceled: 'default',
}

const COLLECTION_STATUS_COLOR: Record<string, string> = {
  preflight_completed: 'processing',
  dry_run_running: 'processing',
  dry_run_completed: 'processing',
  execute_running: 'processing',
  finalized: 'success',
  failed: 'error',
}

const COLLECTION_ITEM_STATUS_COLOR: Record<string, string> = {
  pending: 'processing',
  scheduled: 'processing',
  coalesced: 'default',
  skipped: 'default',
  failed: 'error',
  completed: 'success',
}

const buildBootstrapDedupeReviewHref = (job: PoolMasterDataBootstrapImportJob | null): string | null => {
  const errors = Array.isArray(job?.report?.diagnostics?.errors)
    ? job?.report?.diagnostics?.errors as Array<Record<string, unknown>>
    : []
  const matched = errors.find((item) => {
    const reviewItemId = typeof item.review_item_id === 'string' ? item.review_item_id.trim() : ''
    return reviewItemId.length > 0
  })
  if (!matched) {
    return null
  }
  const reviewItemId = String(matched.review_item_id || '').trim()
  if (!reviewItemId) {
    return null
  }
  const params = new URLSearchParams()
  params.set('tab', 'dedupe-review')
  params.set('reviewItemId', reviewItemId)
  return `/pools/master-data?${params.toString()}`
}

type BootstrapImportTabProps = {
  registryEntries: PoolMasterDataRegistryEntry[]
}

export function BootstrapImportTab({ registryEntries }: BootstrapImportTabProps) {
  const { message } = AntApp.useApp()
  const [form] = Form.useForm<BootstrapScopeFormValues>()
  const [launcherMode, setLauncherMode] = useState<BootstrapLauncherMode>('single')
  const [clusters, setClusters] = useState<SimpleClusterRef[]>([])
  const [databases, setDatabases] = useState<SimpleDatabaseRef[]>([])
  const [jobs, setJobs] = useState<PoolMasterDataBootstrapImportJob[]>([])
  const [collections, setCollections] = useState<PoolMasterDataBootstrapCollection[]>([])
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null)
  const [selectedJob, setSelectedJob] = useState<PoolMasterDataBootstrapImportJob | null>(null)
  const [selectedCollection, setSelectedCollection] = useState<PoolMasterDataBootstrapCollection | null>(null)
  const [preflightState, setPreflightState] = useState<PreflightState>(null)
  const [dryRunState, setDryRunState] = useState<DryRunState>(null)
  const [loadingTargets, setLoadingTargets] = useState(false)
  const [loadingJobs, setLoadingJobs] = useState(false)
  const [loadingCollections, setLoadingCollections] = useState(false)
  const [loadingJobDetail, setLoadingJobDetail] = useState(false)
  const [loadingCollectionDetail, setLoadingCollectionDetail] = useState(false)
  const [runningPreflight, setRunningPreflight] = useState(false)
  const [runningDryRun, setRunningDryRun] = useState(false)
  const [runningExecute, setRunningExecute] = useState(false)
  const [runningJobAction, setRunningJobAction] = useState(false)
  const [actionError, setActionError] = useState('')

  const entityScopeOptions = useMemo(
    () => getBootstrapEntityOptions(registryEntries),
    [registryEntries]
  )
  const defaultScope = useMemo(
    () => getDefaultBootstrapScope(registryEntries),
    [registryEntries]
  )
  const clusterNameById = useMemo(
    () =>
      new Map(
        clusters.map((cluster) => [cluster.id, cluster.name])
      ),
    [clusters]
  )
  const databaseById = useMemo(
    () =>
      new Map(
        databases.map((database) => [database.id, database])
      ),
    [databases]
  )

  const singlePreflightResult = preflightState?.kind === 'single' ? preflightState.result : null
  const batchPreflightResult = preflightState?.kind === 'batch' ? preflightState.result : null
  const singleDryRunSummary = dryRunState?.kind === 'single' ? dryRunState.summary : null
  const batchDryRunSummary = dryRunState?.kind === 'batch' ? dryRunState.summary : null
  const effectiveBatchPreflightResult = useMemo(() => {
    if (batchPreflightResult) {
      return batchPreflightResult
    }
    const candidate = selectedCollection?.aggregate_preflight_result
    if (!candidate || Object.keys(candidate).length === 0) {
      return null
    }
    return candidate as PoolMasterDataBootstrapCollectionPreflightResult
  }, [batchPreflightResult, selectedCollection])
  const effectiveBatchDryRunSummary = useMemo(() => {
    if (batchDryRunSummary && Object.keys(batchDryRunSummary).length > 0) {
      return batchDryRunSummary
    }
    const candidate = selectedCollection?.aggregate_dry_run_summary
    if (!candidate || Object.keys(candidate).length === 0) {
      return null
    }
    return candidate
  }, [batchDryRunSummary, selectedCollection])
  const watchedTargetMode = Form.useWatch('target_mode', form) as
    | 'cluster_all'
    | 'database_set'
    | undefined

  const formatDatabaseLabel = useCallback(
    (database: SimpleDatabaseRef) => {
      const clusterName = database.cluster_id ? clusterNameById.get(database.cluster_id) : ''
      return clusterName ? `${database.name} · ${clusterName}` : database.name
    },
    [clusterNameById]
  )

  const loadTargets = useCallback(async () => {
    setLoadingTargets(true)
    try {
      const [clustersResponse, databasesResponse] = await Promise.all([
        listPoolTargetClusters(),
        listPoolTargetDatabases(),
      ])
      setClusters(clustersResponse)
      setDatabases(databasesResponse)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить кластеры и базы для bootstrap import.')
      message.error(resolved.message)
    } finally {
      setLoadingTargets(false)
    }
  }, [message])

  const loadJobs = useCallback(
    async (databaseId?: string) => {
      setLoadingJobs(true)
      try {
        const response = await listPoolMasterDataBootstrapImportJobs({
          database_id: databaseId || undefined,
          limit: 20,
          offset: 0,
        })
        setJobs(response.jobs)
        if (!selectedJobId && response.jobs.length > 0) {
          setSelectedJobId(response.jobs[0].id)
        }
      } catch (error) {
        const resolved = resolveApiError(error, 'Не удалось загрузить bootstrap jobs.')
        message.error(resolved.message)
      } finally {
        setLoadingJobs(false)
      }
    },
    [message, selectedJobId]
  )

  const loadCollections = useCallback(async () => {
    setLoadingCollections(true)
    try {
      const response = await listPoolMasterDataBootstrapCollections({
        limit: 20,
        offset: 0,
      })
      setCollections(response.collections)
      if (!selectedCollectionId && response.collections.length > 0) {
        setSelectedCollectionId(response.collections[0].id)
      }
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить batch collection requests.')
      message.error(resolved.message)
    } finally {
      setLoadingCollections(false)
    }
  }, [message, selectedCollectionId])

  const loadJobDetail = useCallback(
    async (jobId: string, silent = false) => {
      if (!silent) {
        setLoadingJobDetail(true)
      }
      try {
        const response = await getPoolMasterDataBootstrapImportJob(jobId)
        setSelectedJob(response.job)
      } catch (error) {
        if (!silent) {
          const resolved = resolveApiError(error, 'Не удалось загрузить детали bootstrap job.')
          message.error(resolved.message)
        }
      } finally {
        if (!silent) {
          setLoadingJobDetail(false)
        }
      }
    },
    [message]
  )

  const loadCollectionDetail = useCallback(
    async (collectionId: string, silent = false) => {
      if (!silent) {
        setLoadingCollectionDetail(true)
      }
      try {
        const response = await getPoolMasterDataBootstrapCollection(collectionId)
        setSelectedCollection(response.collection)
      } catch (error) {
        if (!silent) {
          const resolved = resolveApiError(error, 'Не удалось загрузить детали batch collection.')
          message.error(resolved.message)
        }
      } finally {
        if (!silent) {
          setLoadingCollectionDetail(false)
        }
      }
    },
    [message]
  )

  useEffect(() => {
    void loadTargets()
    void loadJobs()
    void loadCollections()
  }, [loadCollections, loadJobs, loadTargets])

  useEffect(() => {
    const currentScope = form.getFieldValue('entity_scope') as PoolMasterDataBootstrapImportEntityType[] | undefined
    if ((currentScope?.length ?? 0) > 0 || defaultScope.length === 0) {
      return
    }
    form.setFieldsValue({
      entity_scope: defaultScope,
      target_mode: 'database_set',
    })
  }, [defaultScope, form])

  useEffect(() => {
    if (!selectedJobId) {
      setSelectedJob(null)
      return
    }
    void loadJobDetail(selectedJobId)
  }, [loadJobDetail, selectedJobId])

  useEffect(() => {
    if (!selectedCollectionId) {
      setSelectedCollection(null)
      return
    }
    void loadCollectionDetail(selectedCollectionId)
  }, [loadCollectionDetail, selectedCollectionId])

  useEffect(() => {
    if (!selectedJobId || !selectedJob || TERMINAL_JOB_STATUSES.has(selectedJob.status)) {
      return
    }
    const timer = window.setInterval(() => {
      void loadJobDetail(selectedJobId, true)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [loadJobDetail, selectedJob, selectedJobId])

  useEffect(() => {
    if (
      !selectedCollectionId ||
      !selectedCollection ||
      TERMINAL_COLLECTION_STATUSES.has(selectedCollection.status)
    ) {
      return
    }
    const timer = window.setInterval(() => {
      void loadCollectionDetail(selectedCollectionId, true)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [loadCollectionDetail, selectedCollection, selectedCollectionId])

  const currentWizardStep = useMemo(() => {
    if (launcherMode === 'single') {
      if (selectedJob?.status === 'finalized') {
        return 3
      }
      if (singleDryRunSummary) {
        return 2
      }
      if (singlePreflightResult?.ok) {
        return 1
      }
      return 0
    }
    if (selectedCollection && selectedCollection.mode === 'execute') {
      return 3
    }
    if (effectiveBatchDryRunSummary || selectedCollection?.mode === 'dry_run') {
      return 2
    }
    if (effectiveBatchPreflightResult?.ok) {
      return 1
    }
    return 0
  }, [
    effectiveBatchDryRunSummary,
    effectiveBatchPreflightResult,
    launcherMode,
    selectedCollection,
    selectedJob,
    singleDryRunSummary,
    singlePreflightResult,
  ])

  const batchExecuteBlockedByDryRunFailure =
    launcherMode === 'batch' &&
    selectedCollection?.mode === 'dry_run' &&
    (selectedCollection.status === 'failed' || Number(selectedCollection.aggregate_counters.failed || 0) > 0)

  const executeAllowed =
    launcherMode === 'single'
      ? Boolean(singlePreflightResult?.ok && singleDryRunSummary)
      : Boolean(
          effectiveBatchPreflightResult?.ok &&
          selectedCollection?.id &&
          selectedCollection.mode === 'dry_run' &&
          selectedCollection.status === 'dry_run_completed' &&
          !batchExecuteBlockedByDryRunFailure
        )

  const setFieldErrorsFromProblem = (fieldErrors: Record<string, string[]>) => {
    if (Object.keys(fieldErrors).length === 0) {
      return
    }
    form.setFields(
      Object.entries(fieldErrors).map(([name, errors]) => ({ name, errors })) as never
    )
  }

  const resolveSingleScopePayload = async () => {
    const values = await form.validateFields(['database_id', 'entity_scope'])
    return {
      database_id: values.database_id as string,
      entity_scope: values.entity_scope as PoolMasterDataBootstrapImportEntityType[],
    }
  }

  const resolveBatchScopePayload = async () => {
    const values = await form.validateFields(['target_mode', 'cluster_id', 'database_ids', 'entity_scope'])
    const targetMode = values.target_mode as 'cluster_all' | 'database_set'
    if (targetMode === 'cluster_all') {
      if (!values.cluster_id) {
        form.setFields([{ name: 'cluster_id', errors: ['Выберите cluster.'] }] as never)
        throw new Error('VALIDATION_ERROR')
      }
      return {
        target_mode: targetMode,
        cluster_id: values.cluster_id as string,
        entity_scope: values.entity_scope as PoolMasterDataBootstrapImportEntityType[],
      }
    }
    const databaseIds = (values.database_ids as string[] | undefined) ?? []
    if (databaseIds.length === 0) {
      form.setFields([{ name: 'database_ids', errors: ['Выберите минимум одну базу.'] }] as never)
      throw new Error('VALIDATION_ERROR')
    }
    return {
      target_mode: targetMode,
      database_ids: databaseIds,
      entity_scope: values.entity_scope as PoolMasterDataBootstrapImportEntityType[],
    }
  }

  const refreshJobsForCurrentDatabase = async () => {
    const currentDatabaseId = form.getFieldValue('database_id')
    await loadJobs(currentDatabaseId)
  }

  const handleRunPreflight = async () => {
    setActionError('')
    setRunningPreflight(true)
    try {
      if (launcherMode === 'single') {
        const payload = await resolveSingleScopePayload()
        const response = await runPoolMasterDataBootstrapImportPreflight(payload)
        setPreflightState({ kind: 'single', result: response.preflight })
        setDryRunState(null)
        message.success(response.preflight.ok ? 'Preflight успешно пройден.' : 'Preflight завершён с ошибками.')
        return
      }

      const payload = await resolveBatchScopePayload()
      const response = await runPoolMasterDataBootstrapCollectionPreflight(payload)
      setPreflightState({ kind: 'batch', result: response.preflight })
      setDryRunState(null)
      setSelectedCollectionId(response.collection.id)
      setSelectedCollection(response.collection)
      await loadCollections()
      message.success(
        response.preflight.ok
          ? `Aggregate preflight успешно пройден для ${response.preflight.database_count} ИБ.`
          : 'Aggregate preflight завершён с ошибками.'
      )
    } catch (error) {
      if (error instanceof Error && error.message === 'VALIDATION_ERROR') {
        return
      }
      const resolved = resolveApiError(error, 'Не удалось выполнить preflight.')
      setFieldErrorsFromProblem(resolved.fieldErrors)
      setActionError(resolved.message)
      message.error(resolved.message)
    } finally {
      setRunningPreflight(false)
    }
  }

  const handleCreateDryRun = async () => {
    if (launcherMode === 'single' && !singlePreflightResult?.ok) {
      message.error('Сначала выполните успешный preflight.')
      return
    }
    if (launcherMode === 'batch' && !effectiveBatchPreflightResult?.ok) {
      message.error('Сначала выполните успешный aggregate preflight.')
      return
    }

    setActionError('')
    setRunningDryRun(true)
    try {
      if (launcherMode === 'single') {
        const payload = await resolveSingleScopePayload()
        const response = await createPoolMasterDataBootstrapImportJob({
          ...payload,
          mode: 'dry_run',
        })
        setDryRunState({ kind: 'single', summary: response.job.dry_run_summary || {} })
        setSelectedJobId(response.job.id)
        await refreshJobsForCurrentDatabase()
        message.success('Dry-run завершён.')
        return
      }

      const payload = await resolveBatchScopePayload()
      if (!selectedCollection?.id) {
        message.error('Сначала выполните aggregate preflight.')
        return
      }
      const response = await createPoolMasterDataBootstrapCollection({
        collection_id: selectedCollection.id,
        ...payload,
        mode: 'dry_run',
      })
      setDryRunState({
        kind: 'batch',
        summary: response.collection.aggregate_dry_run_summary || {},
      })
      setSelectedCollectionId(response.collection.id)
      setSelectedCollection(response.collection)
      await loadCollections()
      message.success('Batch dry-run завершён.')
    } catch (error) {
      if (error instanceof Error && error.message === 'VALIDATION_ERROR') {
        return
      }
      const resolved = resolveApiError(error, 'Не удалось выполнить dry-run.')
      setFieldErrorsFromProblem(resolved.fieldErrors)
      setActionError(resolved.message)
      message.error(resolved.message)
    } finally {
      setRunningDryRun(false)
    }
  }

  const handleCreateExecute = async () => {
    if (!executeAllowed) {
      message.error(
        launcherMode === 'single'
          ? 'Execute доступен только после успешных preflight и dry-run.'
          : 'Batch execute доступен только после успешных preflight и dry-run.'
      )
      return
    }

    setActionError('')
    setRunningExecute(true)
    try {
      if (launcherMode === 'single') {
        const payload = await resolveSingleScopePayload()
        const response = await createPoolMasterDataBootstrapImportJob({
          ...payload,
          mode: 'execute',
        })
        setSelectedJobId(response.job.id)
        await refreshJobsForCurrentDatabase()
        message.success('Execute запущен.')
        return
      }

      const payload = await resolveBatchScopePayload()
      if (!selectedCollection?.id) {
        message.error('Сначала выполните успешный batch dry-run.')
        return
      }
      const response = await createPoolMasterDataBootstrapCollection({
        collection_id: selectedCollection.id,
        ...payload,
        mode: 'execute',
      })
      setSelectedCollectionId(response.collection.id)
      setSelectedCollection(response.collection)
      await loadCollections()
      message.success('Batch execute запущен.')
    } catch (error) {
      if (error instanceof Error && error.message === 'VALIDATION_ERROR') {
        return
      }
      const resolved = resolveApiError(error, 'Не удалось запустить execute.')
      setFieldErrorsFromProblem(resolved.fieldErrors)
      setActionError(resolved.message)
      message.error(resolved.message)
    } finally {
      setRunningExecute(false)
    }
  }

  const runJobAction = async (action: 'cancel' | 'retry_failed_chunks') => {
    if (!selectedJob) {
      return
    }
    setRunningJobAction(true)
    setActionError('')
    try {
      const response =
        action === 'cancel'
          ? await cancelPoolMasterDataBootstrapImportJob(selectedJob.id)
          : await retryFailedPoolMasterDataBootstrapImportChunks(selectedJob.id)
      setSelectedJob(response.job)
      await refreshJobsForCurrentDatabase()
      message.success(action === 'cancel' ? 'Job отменён.' : 'Retry failed chunks выполнен.')
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось выполнить действие над bootstrap job.')
      setActionError(resolved.message)
      message.error(resolved.message)
    } finally {
      setRunningJobAction(false)
    }
  }

  const openChildJob = (jobId: string) => {
    setLauncherMode('single')
    setSelectedJobId(jobId)
    void loadJobDetail(jobId)
  }

  const currentTargetMode = watchedTargetMode ?? 'database_set'

  const currentSingleRowsTotal =
    Number(singleDryRunSummary?.rows_total || selectedJob?.dry_run_summary?.rows_total || 0) || 0
  const currentSingleCompletionPercent = Math.min(
    100,
    Math.max(0, Math.round(Number(selectedJob?.progress?.completion_ratio || 0) * 100))
  )
  const currentCollectionRowsTotal =
    Number(effectiveBatchDryRunSummary?.rows_total || selectedCollection?.aggregate_dry_run_summary?.rows_total || 0) || 0
  const currentCollectionCompletionPercent = Math.min(
    100,
    Math.max(0, Math.round(Number(selectedCollection?.progress?.completion_ratio || 0) * 100))
  )

  const formatCollectionSnapshot = useCallback(
    (collection: PoolMasterDataBootstrapCollection) =>
      collection.database_ids
        .map((databaseId) => {
          const database = databaseById.get(databaseId)
          if (!database) {
            return databaseId
          }
          return formatDatabaseLabel(database)
        })
        .join(', '),
    [databaseById, formatDatabaseLabel]
  )

  const jobColumns: ColumnsType<PoolMasterDataBootstrapImportJob> = [
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
      width: 170,
      render: (value: string) => <Tag color={STATUS_COLOR[value] || 'default'}>{value}</Tag>,
    },
    {
      title: 'Scope',
      key: 'scope',
      width: 280,
      render: (_, row) => row.entity_scope.join(', '),
    },
    {
      title: 'Rows',
      key: 'rows',
      width: 100,
      render: (_, row) => Number(row.dry_run_summary?.rows_total || 0),
    },
    {
      title: 'Failed',
      key: 'failed',
      width: 110,
      render: (_, row) => row.report.failed_count + row.report.deferred_count,
    },
  ]

  const chunkColumns: ColumnsType<PoolMasterDataBootstrapImportChunk> = [
    { title: 'Entity', dataIndex: 'entity_type', key: 'entity_type', width: 120 },
    { title: 'Chunk', dataIndex: 'chunk_index', key: 'chunk_index', width: 90 },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (value: string) => <Tag color={STATUS_COLOR[value] || 'default'}>{value}</Tag>,
    },
    { title: 'Attempt', dataIndex: 'attempt_count', key: 'attempt_count', width: 90 },
    { title: 'Created', dataIndex: 'records_created', key: 'records_created', width: 90 },
    { title: 'Updated', dataIndex: 'records_updated', key: 'records_updated', width: 90 },
    { title: 'Skipped', dataIndex: 'records_skipped', key: 'records_skipped', width: 90 },
    { title: 'Failed', dataIndex: 'records_failed', key: 'records_failed', width: 90 },
    {
      title: 'Error',
      dataIndex: 'last_error_code',
      key: 'last_error_code',
      width: 240,
      render: (value: string) => (value ? <Tag color="error">{value}</Tag> : <Text type="secondary">-</Text>),
    },
  ]

  const collectionColumns: ColumnsType<PoolMasterDataBootstrapCollection> = [
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
      width: 170,
      render: (value: string) => <Tag color={COLLECTION_STATUS_COLOR[value] || 'default'}>{value}</Tag>,
    },
    {
      title: 'Mode',
      dataIndex: 'target_mode',
      key: 'target_mode',
      width: 150,
    },
    {
      title: 'Targets',
      key: 'targets',
      width: 280,
      render: (_, row) =>
        formatCollectionSnapshot(row) ||
        (row.target_mode === 'cluster_all'
          ? clusterNameById.get(row.cluster_id || '') || `Cluster ${row.cluster_id || '-'}`
          : `${row.database_ids.length} databases`),
    },
    {
      title: 'Scope',
      key: 'scope',
      width: 260,
      render: (_, row) => row.entity_scope.join(', '),
    },
    {
      title: 'Outcomes',
      key: 'outcomes',
      width: 220,
      render: (_, row) =>
        `${row.aggregate_counters.completed || 0}/${row.aggregate_counters.coalesced || 0}/${row.aggregate_counters.failed || 0}`,
    },
  ]

  const collectionItemColumns: ColumnsType<PoolMasterDataBootstrapCollectionItem> = [
    {
      title: 'Database',
      dataIndex: 'database_name',
      key: 'database_name',
      width: 260,
      render: (_value: string, row) => {
        const clusterName = row.cluster_id ? clusterNameById.get(row.cluster_id) : ''
        return clusterName ? `${row.database_name} · ${clusterName}` : row.database_name
      },
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (value: string) => (
        <Tag color={COLLECTION_ITEM_STATUS_COLOR[value] || 'default'}>{value}</Tag>
      ),
    },
    {
      title: 'Rows',
      key: 'rows',
      width: 90,
      render: (_, row) => Number(row.dry_run_summary?.rows_total || 0),
    },
    {
      title: 'Child Job',
      key: 'child_job_id',
      width: 180,
      render: (_, row) =>
        row.child_job_id ? (
          <Button
            type="link"
            size="small"
            onClick={(event) => {
              event.stopPropagation()
              openChildJob(row.child_job_id as string)
            }}
          >
            Open Job
          </Button>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
    {
      title: 'Reason',
      key: 'reason_code',
      width: 280,
      render: (_, row) =>
        row.reason_code ? <Tag color="error">{row.reason_code}</Tag> : <Text type="secondary">-</Text>,
    },
  ]

  const batchDatabaseOptions = useMemo(
    () =>
      databases.map((database) => ({
        value: database.id,
        label: formatDatabaseLabel(database),
      })),
    [databases, formatDatabaseLabel]
  )
  const singleDatabaseOptions = useMemo(
    () =>
      databases.map((database) => ({
        value: database.id,
        label: database.name,
      })),
    [databases]
  )

  const clusterOptions = useMemo(
    () =>
      clusters.map((cluster) => ({
        value: cluster.id,
        label: cluster.name,
      })),
    [clusters]
  )

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Segmented<BootstrapLauncherMode>
            value={launcherMode}
            options={[
              { label: 'Single Database', value: 'single' },
              { label: 'Batch Collection', value: 'batch' },
            ]}
            onChange={(value) => setLauncherMode(value)}
          />

          <Steps
            current={currentWizardStep}
            items={[
              { title: 'Scope' },
              { title: 'Preflight' },
              { title: 'Dry-run' },
              { title: 'Execute' },
            ]}
          />

          <Form
            form={form}
            layout="vertical"
            initialValues={{ entity_scope: defaultScope, target_mode: 'database_set' }}
          >
            {launcherMode === 'single' ? (
              <Space wrap align="start">
                <Form.Item
                  name="database_id"
                  label="Database"
                  rules={[{ required: true, message: 'Выберите базу.' }]}
                  style={{ minWidth: 320, marginBottom: 8 }}
                >
                  <Select
                    data-testid="bootstrap-import-database-select"
                    loading={loadingTargets}
                    placeholder="Select database"
                    options={singleDatabaseOptions}
                  />
                </Form.Item>
                <Form.Item
                  name="entity_scope"
                  label="Entity scope"
                  rules={[{ required: true, type: 'array', min: 1, message: 'Выберите минимум одну сущность.' }]}
                  style={{ minWidth: 360, marginBottom: 8 }}
                >
                  <Select
                    data-testid="bootstrap-import-entity-scope-select"
                    mode="multiple"
                    allowClear
                    placeholder="Select entities"
                    options={entityScopeOptions}
                  />
                </Form.Item>
              </Space>
            ) : (
              <Space wrap align="start">
                <Form.Item
                  name="target_mode"
                  label="Target mode"
                  rules={[{ required: true, message: 'Выберите target mode.' }]}
                  style={{ minWidth: 220, marginBottom: 8 }}
                >
                  <Select
                    data-testid="bootstrap-collection-target-mode-select"
                    options={[
                      { value: 'cluster_all', label: 'All databases in cluster' },
                      { value: 'database_set', label: 'Selected databases' },
                    ]}
                  />
                </Form.Item>
                {currentTargetMode === 'cluster_all' ? (
                  <Form.Item
                    name="cluster_id"
                    label="Cluster"
                    rules={[{ required: true, message: 'Выберите cluster.' }]}
                    style={{ minWidth: 320, marginBottom: 8 }}
                  >
                    <Select
                      data-testid="bootstrap-collection-cluster-select"
                      loading={loadingTargets}
                      placeholder="Select cluster"
                      options={clusterOptions}
                    />
                  </Form.Item>
                ) : (
                  <Form.Item
                    name="database_ids"
                    label="Databases"
                    rules={[{ required: true, type: 'array', min: 1, message: 'Выберите минимум одну базу.' }]}
                    style={{ minWidth: 420, marginBottom: 8 }}
                  >
                    <Select
                      data-testid="bootstrap-collection-databases-select"
                      mode="multiple"
                      allowClear
                      loading={loadingTargets}
                      placeholder="Select databases"
                      options={batchDatabaseOptions}
                    />
                  </Form.Item>
                )}
                <Form.Item
                  name="entity_scope"
                  label="Entity scope"
                  rules={[{ required: true, type: 'array', min: 1, message: 'Выберите минимум одну сущность.' }]}
                  style={{ minWidth: 360, marginBottom: 8 }}
                >
                  <Select
                    data-testid="bootstrap-collection-entity-scope-select"
                    mode="multiple"
                    allowClear
                    placeholder="Select entities"
                    options={entityScopeOptions}
                  />
                </Form.Item>
              </Space>
            )}
          </Form>

          <Space wrap>
            <Button
              data-testid={launcherMode === 'single' ? 'bootstrap-import-run-preflight' : 'bootstrap-collection-run-preflight'}
              onClick={() => void handleRunPreflight()}
              loading={runningPreflight}
            >
              Run Preflight
            </Button>
            <Button
              data-testid={launcherMode === 'single' ? 'bootstrap-import-run-dry-run' : 'bootstrap-collection-run-dry-run'}
              onClick={() => void handleCreateDryRun()}
              loading={runningDryRun}
              disabled={launcherMode === 'single' ? !singlePreflightResult?.ok : !effectiveBatchPreflightResult?.ok}
            >
              Run Dry-run
            </Button>
            <Button
              data-testid={launcherMode === 'single' ? 'bootstrap-import-run-execute' : 'bootstrap-collection-run-execute'}
              type="primary"
              onClick={() => void handleCreateExecute()}
              loading={runningExecute}
              disabled={!executeAllowed}
            >
              Execute
            </Button>
            <Button
              data-testid={launcherMode === 'single' ? 'bootstrap-import-refresh' : 'bootstrap-collection-refresh'}
              onClick={() =>
                void (launcherMode === 'single' ? refreshJobsForCurrentDatabase() : loadCollections())
              }
              loading={launcherMode === 'single' ? loadingJobs : loadingCollections}
            >
              Refresh
            </Button>
          </Space>

          {!!actionError && (
            <Alert
              type="error"
              showIcon
              message={actionError}
            />
          )}

          {launcherMode === 'single' && singlePreflightResult && (
            <Alert
              type={singlePreflightResult.ok ? 'success' : 'warning'}
              showIcon
              message={singlePreflightResult.ok ? 'Preflight passed.' : 'Preflight failed.'}
              description={
                singlePreflightResult.errors.length > 0
                  ? singlePreflightResult.errors.map((item) => item.detail || item.code).join('; ')
                  : 'Source and coverage checks are valid.'
              }
            />
          )}

          {launcherMode === 'batch' && effectiveBatchPreflightResult && (
            <Alert
              type={effectiveBatchPreflightResult.ok ? 'success' : 'warning'}
              showIcon
              message={effectiveBatchPreflightResult.ok ? 'Aggregate preflight passed.' : 'Aggregate preflight failed.'}
              description={
                effectiveBatchPreflightResult.ok
                  ? `${effectiveBatchPreflightResult.database_count} databases are ready for bootstrap collection.`
                  : effectiveBatchPreflightResult.errors
                      .map((item) => String(item.detail || item.code || 'Preflight failed'))
                      .join('; ')
              }
            />
          )}
        </Space>
      </Card>

      {launcherMode === 'single' ? (
        <>
          <Card
            title="Current Job"
            extra={
              <Space>
                <Button
                  data-testid="bootstrap-import-cancel-job"
                  onClick={() => void runJobAction('cancel')}
                  loading={runningJobAction}
                  disabled={!selectedJob || TERMINAL_JOB_STATUSES.has(selectedJob.status)}
                >
                  Cancel
                </Button>
                <Button
                  data-testid="bootstrap-import-retry-failed"
                  onClick={() => void runJobAction('retry_failed_chunks')}
                  loading={runningJobAction}
                  disabled={
                    !selectedJob || (selectedJob.report.failed_count + selectedJob.report.deferred_count) === 0
                  }
                >
                  Retry Failed Chunks
                </Button>
              </Space>
            }
          >
            {!selectedJob ? (
              <Empty description="No bootstrap job selected." />
            ) : (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {buildBootstrapDedupeReviewHref(selectedJob) ? (
                  <Alert
                    type="warning"
                    showIcon
                    message="Bootstrap import encountered unresolved cross-infobase dedupe."
                    action={(
                      <Button type="link" href={buildBootstrapDedupeReviewHref(selectedJob) || undefined}>
                        Open Review
                      </Button>
                    )}
                  />
                ) : null}

                <Space>
                  <Tag color={STATUS_COLOR[selectedJob.status] || 'default'}>{selectedJob.status}</Tag>
                  <Text type="secondary">Started: {formatDateTime(selectedJob.started_at)}</Text>
                  <Text type="secondary">Finished: {formatDateTime(selectedJob.finished_at)}</Text>
                </Space>

                <Progress
                  data-testid="bootstrap-import-progress"
                  percent={currentSingleCompletionPercent}
                  status={selectedJob.status === 'failed' ? 'exception' : 'active'}
                />

                <Descriptions size="small" bordered column={3}>
                  <Descriptions.Item label="Rows (dry-run)">{currentSingleRowsTotal}</Descriptions.Item>
                  <Descriptions.Item label="Created">{selectedJob.report.created_count}</Descriptions.Item>
                  <Descriptions.Item label="Updated">{selectedJob.report.updated_count}</Descriptions.Item>
                  <Descriptions.Item label="Skipped">{selectedJob.report.skipped_count}</Descriptions.Item>
                  <Descriptions.Item label="Failed">{selectedJob.report.failed_count}</Descriptions.Item>
                  <Descriptions.Item label="Deferred">{selectedJob.report.deferred_count}</Descriptions.Item>
                </Descriptions>

                <Table
                  rowKey="id"
                  loading={loadingJobDetail}
                  columns={chunkColumns}
                  dataSource={selectedJob.chunks || []}
                  pagination={false}
                  size="small"
                  scroll={{ x: 1200 }}
                />
              </Space>
            )}
          </Card>

          <Card title="Recent Jobs">
            <Table
              rowKey="id"
              loading={loadingJobs}
              columns={jobColumns}
              dataSource={jobs}
              pagination={false}
              size="small"
              scroll={{ x: 1100 }}
              onRow={(record) => ({
                onClick: () => setSelectedJobId(record.id),
              })}
            />
          </Card>
        </>
      ) : (
        <>
          <Card title="Current Collection">
            {!selectedCollection ? (
              <Empty description="No batch collection selected." />
            ) : (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {selectedCollection.mode === 'preflight' && selectedCollection.status === 'failed' ? (
                  <Alert
                    type="warning"
                    showIcon
                    message="Aggregate preflight contains failed databases."
                    description="Dry-run remains blocked until the selected target snapshot completes preflight without failed items."
                  />
                ) : null}
                {selectedCollection.mode === 'dry_run' &&
                Number(selectedCollection.aggregate_counters.failed || 0) > 0 ? (
                  <Alert
                    type="warning"
                    showIcon
                    message="Batch dry-run contains failed databases."
                    description="Execute remains blocked until the selected target snapshot completes dry-run without failed items."
                  />
                ) : null}
                {selectedCollection.mode === 'dry_run' &&
                selectedCollection.status === 'dry_run_running' ? (
                  <Alert
                    type="info"
                    showIcon
                    message="Batch dry-run is running."
                    description="The aggregate preview is processed asynchronously. Refresh or wait for the collection detail to update."
                  />
                ) : null}

                <Space>
                  <Tag color={COLLECTION_STATUS_COLOR[selectedCollection.status] || 'default'}>
                    {selectedCollection.status}
                  </Tag>
                  <Text type="secondary">
                    Requested by: {selectedCollection.requested_by_username || selectedCollection.requested_by_id || '-'}
                  </Text>
                  <Text type="secondary">Created: {formatDateTime(selectedCollection.created_at)}</Text>
                </Space>

                <Progress
                  data-testid="bootstrap-collection-progress"
                  percent={currentCollectionCompletionPercent}
                  status={selectedCollection.status === 'failed' ? 'exception' : 'active'}
                />

                <Descriptions size="small" bordered column={3}>
                  <Descriptions.Item label="Target Mode">{selectedCollection.target_mode}</Descriptions.Item>
                  <Descriptions.Item label="Cluster">
                    {selectedCollection.cluster_id
                      ? clusterNameById.get(selectedCollection.cluster_id) || selectedCollection.cluster_id
                      : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Target Snapshot">
                    {formatCollectionSnapshot(selectedCollection) || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Rows (dry-run)">{currentCollectionRowsTotal}</Descriptions.Item>
                  <Descriptions.Item label="Scheduled">
                    {selectedCollection.aggregate_counters.scheduled || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="Coalesced">
                    {selectedCollection.aggregate_counters.coalesced || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="Completed">
                    {selectedCollection.aggregate_counters.completed || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="Failed">
                    {selectedCollection.aggregate_counters.failed || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="Skipped">
                    {selectedCollection.aggregate_counters.skipped || 0}
                  </Descriptions.Item>
                </Descriptions>

                <Table
                  rowKey="id"
                  loading={loadingCollectionDetail}
                  columns={collectionItemColumns}
                  dataSource={selectedCollection.items || []}
                  pagination={false}
                  size="small"
                  scroll={{ x: 1100 }}
                />
              </Space>
            )}
          </Card>

          <Card title="Recent Collections">
            <Table
              rowKey="id"
              loading={loadingCollections}
              columns={collectionColumns}
              dataSource={collections}
              pagination={false}
              size="small"
              scroll={{ x: 1200 }}
              onRow={(record) => ({
                onClick: () => setSelectedCollectionId(record.id),
              })}
            />
          </Card>
        </>
      )}
    </Space>
  )
}
