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
import { usePoolsTranslation } from '../../../i18n'
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
  const { t } = usePoolsTranslation()
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
      const resolved = resolveApiError(error, t('masterData.bootstrapImportTab.messages.failedToLoadTargets'))
      message.error(resolved.message)
    } finally {
      setLoadingTargets(false)
    }
  }, [message, t])

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
        const resolved = resolveApiError(error, t('masterData.bootstrapImportTab.messages.failedToLoadJobs'))
        message.error(resolved.message)
      } finally {
        setLoadingJobs(false)
      }
    },
    [message, selectedJobId, t]
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
      const resolved = resolveApiError(error, t('masterData.bootstrapImportTab.messages.failedToLoadCollections'))
      message.error(resolved.message)
    } finally {
      setLoadingCollections(false)
    }
  }, [message, selectedCollectionId, t])

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
          const resolved = resolveApiError(error, t('masterData.bootstrapImportTab.messages.failedToLoadJobDetail'))
          message.error(resolved.message)
        }
      } finally {
        if (!silent) {
          setLoadingJobDetail(false)
        }
      }
    },
    [message, t]
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
          const resolved = resolveApiError(error, t('masterData.bootstrapImportTab.messages.failedToLoadCollectionDetail'))
          message.error(resolved.message)
        }
      } finally {
        if (!silent) {
          setLoadingCollectionDetail(false)
        }
      }
    },
    [message, t]
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
        form.setFields([{ name: 'cluster_id', errors: [t('masterData.bootstrapImportTab.validation.selectCluster')] }] as never)
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
      form.setFields([{ name: 'database_ids', errors: [t('masterData.bootstrapImportTab.validation.selectAtLeastOneDatabase')] }] as never)
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
        message.success(
          response.preflight.ok
            ? t('masterData.bootstrapImportTab.messages.preflightPassed')
            : t('masterData.bootstrapImportTab.messages.preflightFailed')
        )
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
          ? t('masterData.bootstrapImportTab.messages.aggregatePreflightPassed', { count: response.preflight.database_count })
          : t('masterData.bootstrapImportTab.messages.aggregatePreflightFailed')
      )
    } catch (error) {
      if (error instanceof Error && error.message === 'VALIDATION_ERROR') {
        return
      }
      const resolved = resolveApiError(error, t('masterData.bootstrapImportTab.messages.failedToRunPreflight'))
      setFieldErrorsFromProblem(resolved.fieldErrors)
      setActionError(resolved.message)
      message.error(resolved.message)
    } finally {
      setRunningPreflight(false)
    }
  }

  const handleCreateDryRun = async () => {
    if (launcherMode === 'single' && !singlePreflightResult?.ok) {
      message.error(t('masterData.bootstrapImportTab.messages.runSinglePreflightFirst'))
      return
    }
    if (launcherMode === 'batch' && !effectiveBatchPreflightResult?.ok) {
      message.error(t('masterData.bootstrapImportTab.messages.runAggregatePreflightFirst'))
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
        message.success(t('masterData.bootstrapImportTab.messages.dryRunCompleted'))
        return
      }

      const payload = await resolveBatchScopePayload()
      if (!selectedCollection?.id) {
        message.error(t('masterData.bootstrapImportTab.messages.runAggregatePreflightFirst'))
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
      message.success(t('masterData.bootstrapImportTab.messages.batchDryRunCompleted'))
    } catch (error) {
      if (error instanceof Error && error.message === 'VALIDATION_ERROR') {
        return
      }
      const resolved = resolveApiError(error, t('masterData.bootstrapImportTab.messages.failedToRunDryRun'))
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
          ? t('masterData.bootstrapImportTab.messages.singleExecuteRequiresPreflightAndDryRun')
          : t('masterData.bootstrapImportTab.messages.batchExecuteRequiresPreflightAndDryRun')
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
        message.success(t('masterData.bootstrapImportTab.messages.executeStarted'))
        return
      }

      const payload = await resolveBatchScopePayload()
      if (!selectedCollection?.id) {
        message.error(t('masterData.bootstrapImportTab.messages.runBatchDryRunFirst'))
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
      message.success(t('masterData.bootstrapImportTab.messages.batchExecuteStarted'))
    } catch (error) {
      if (error instanceof Error && error.message === 'VALIDATION_ERROR') {
        return
      }
      const resolved = resolveApiError(error, t('masterData.bootstrapImportTab.messages.failedToStartExecute'))
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
      message.success(
        action === 'cancel'
          ? t('masterData.bootstrapImportTab.messages.jobCanceled')
          : t('masterData.bootstrapImportTab.messages.retryFailedChunksCompleted')
      )
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.bootstrapImportTab.messages.failedToRunJobAction'))
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
      title: t('masterData.bootstrapImportTab.columns.created'),
      dataIndex: 'created_at',
      key: 'created_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: t('masterData.bootstrapImportTab.columns.status'),
      dataIndex: 'status',
      key: 'status',
      width: 170,
      render: (value: string) => <Tag color={STATUS_COLOR[value] || 'default'}>{value}</Tag>,
    },
    {
      title: t('masterData.bootstrapImportTab.columns.scope'),
      key: 'scope',
      width: 280,
      render: (_, row) => row.entity_scope.join(', '),
    },
    {
      title: t('masterData.bootstrapImportTab.columns.rows'),
      key: 'rows',
      width: 100,
      render: (_, row) => Number(row.dry_run_summary?.rows_total || 0),
    },
    {
      title: t('masterData.bootstrapImportTab.columns.failed'),
      key: 'failed',
      width: 110,
      render: (_, row) => row.report.failed_count + row.report.deferred_count,
    },
  ]

  const chunkColumns: ColumnsType<PoolMasterDataBootstrapImportChunk> = [
    { title: t('masterData.bootstrapImportTab.columns.entity'), dataIndex: 'entity_type', key: 'entity_type', width: 120 },
    { title: t('masterData.bootstrapImportTab.columns.chunk'), dataIndex: 'chunk_index', key: 'chunk_index', width: 90 },
    {
      title: t('masterData.bootstrapImportTab.columns.status'),
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (value: string) => <Tag color={STATUS_COLOR[value] || 'default'}>{value}</Tag>,
    },
    { title: t('masterData.bootstrapImportTab.columns.attempt'), dataIndex: 'attempt_count', key: 'attempt_count', width: 90 },
    { title: t('masterData.bootstrapImportTab.columns.created'), dataIndex: 'records_created', key: 'records_created', width: 90 },
    { title: t('masterData.bootstrapImportTab.columns.updated'), dataIndex: 'records_updated', key: 'records_updated', width: 90 },
    { title: t('masterData.bootstrapImportTab.columns.skipped'), dataIndex: 'records_skipped', key: 'records_skipped', width: 90 },
    { title: t('masterData.bootstrapImportTab.columns.failed'), dataIndex: 'records_failed', key: 'records_failed', width: 90 },
    {
      title: t('masterData.bootstrapImportTab.columns.error'),
      dataIndex: 'last_error_code',
      key: 'last_error_code',
      width: 240,
      render: (value: string) => (value ? <Tag color="error">{value}</Tag> : <Text type="secondary">{t('common.noValue')}</Text>),
    },
  ]

  const collectionColumns: ColumnsType<PoolMasterDataBootstrapCollection> = [
    {
      title: t('masterData.bootstrapImportTab.columns.created'),
      dataIndex: 'created_at',
      key: 'created_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: t('masterData.bootstrapImportTab.columns.status'),
      dataIndex: 'status',
      key: 'status',
      width: 170,
      render: (value: string) => <Tag color={COLLECTION_STATUS_COLOR[value] || 'default'}>{value}</Tag>,
    },
    {
      title: t('masterData.bootstrapImportTab.columns.mode'),
      dataIndex: 'target_mode',
      key: 'target_mode',
      width: 150,
      render: (value: 'cluster_all' | 'database_set') => (
        value === 'cluster_all'
          ? t('masterData.bootstrapImportTab.targetMode.clusterAll')
          : t('masterData.bootstrapImportTab.targetMode.databaseSet')
      ),
    },
    {
      title: t('masterData.bootstrapImportTab.columns.targets'),
      key: 'targets',
      width: 280,
      render: (_, row) =>
        formatCollectionSnapshot(row) ||
        (row.target_mode === 'cluster_all'
          ? clusterNameById.get(row.cluster_id || '') || t('masterData.bootstrapImportTab.columns.clusterFallback', { clusterId: row.cluster_id || t('common.noValue') })
          : t('masterData.bootstrapImportTab.columns.databaseCount', { count: row.database_ids.length })),
    },
    {
      title: t('masterData.bootstrapImportTab.columns.scope'),
      key: 'scope',
      width: 260,
      render: (_, row) => row.entity_scope.join(', '),
    },
    {
      title: t('masterData.bootstrapImportTab.columns.outcomes'),
      key: 'outcomes',
      width: 220,
      render: (_, row) =>
        `${row.aggregate_counters.completed || 0}/${row.aggregate_counters.coalesced || 0}/${row.aggregate_counters.failed || 0}`,
    },
  ]

  const collectionItemColumns: ColumnsType<PoolMasterDataBootstrapCollectionItem> = [
    {
      title: t('masterData.bootstrapImportTab.columns.database'),
      dataIndex: 'database_name',
      key: 'database_name',
      width: 260,
      render: (_value: string, row) => {
        const clusterName = row.cluster_id ? clusterNameById.get(row.cluster_id) : ''
        return clusterName ? `${row.database_name} · ${clusterName}` : row.database_name
      },
    },
    {
      title: t('masterData.bootstrapImportTab.columns.status'),
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (value: string) => (
        <Tag color={COLLECTION_ITEM_STATUS_COLOR[value] || 'default'}>{value}</Tag>
      ),
    },
    {
      title: t('masterData.bootstrapImportTab.columns.rows'),
      key: 'rows',
      width: 90,
      render: (_, row) => Number(row.dry_run_summary?.rows_total || 0),
    },
    {
      title: t('masterData.bootstrapImportTab.columns.childJob'),
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
            {t('masterData.bootstrapImportTab.actions.openJob')}
          </Button>
        ) : (
          <Text type="secondary">{t('common.noValue')}</Text>
        ),
    },
    {
      title: t('masterData.bootstrapImportTab.columns.reason'),
      key: 'reason_code',
      width: 280,
      render: (_, row) =>
        row.reason_code ? <Tag color="error">{row.reason_code}</Tag> : <Text type="secondary">{t('common.noValue')}</Text>,
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
  const launcherModeOptions = useMemo(
    () => [
      { label: t('masterData.bootstrapImportTab.modes.single'), value: 'single' as const },
      { label: t('masterData.bootstrapImportTab.modes.batch'), value: 'batch' as const },
    ],
    [t]
  )
  const stepItems = useMemo(
    () => [
      { title: t('masterData.bootstrapImportTab.steps.scope') },
      { title: t('masterData.bootstrapImportTab.steps.preflight') },
      { title: t('masterData.bootstrapImportTab.steps.dryRun') },
      { title: t('masterData.bootstrapImportTab.steps.execute') },
    ],
    [t]
  )

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Segmented<BootstrapLauncherMode>
            value={launcherMode}
            options={launcherModeOptions}
            onChange={(value) => setLauncherMode(value)}
          />

          <Steps
            current={currentWizardStep}
            items={stepItems}
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
                  label={t('masterData.bootstrapImportTab.fields.database')}
                  rules={[{ required: true, message: t('masterData.bootstrapImportTab.validation.selectDatabase') }]}
                  style={{ minWidth: 320, marginBottom: 8 }}
                >
                  <Select
                    data-testid="bootstrap-import-database-select"
                    loading={loadingTargets}
                    placeholder={t('masterData.bootstrapImportTab.placeholders.selectDatabase')}
                    options={singleDatabaseOptions}
                  />
                </Form.Item>
                <Form.Item
                  name="entity_scope"
                  label={t('masterData.bootstrapImportTab.fields.entityScope')}
                  rules={[{ required: true, type: 'array', min: 1, message: t('masterData.bootstrapImportTab.validation.selectAtLeastOneEntity') }]}
                  style={{ minWidth: 360, marginBottom: 8 }}
                >
                  <Select
                    data-testid="bootstrap-import-entity-scope-select"
                    mode="multiple"
                    allowClear
                    placeholder={t('masterData.bootstrapImportTab.placeholders.selectEntities')}
                    options={entityScopeOptions}
                  />
                </Form.Item>
              </Space>
            ) : (
              <Space wrap align="start">
                <Form.Item
                  name="target_mode"
                  label={t('masterData.bootstrapImportTab.fields.targetMode')}
                  rules={[{ required: true, message: t('masterData.bootstrapImportTab.validation.selectTargetMode') }]}
                  style={{ minWidth: 220, marginBottom: 8 }}
                >
                  <Select
                    data-testid="bootstrap-collection-target-mode-select"
                    options={[
                      { value: 'cluster_all', label: t('masterData.bootstrapImportTab.targetMode.clusterAll') },
                      { value: 'database_set', label: t('masterData.bootstrapImportTab.targetMode.databaseSet') },
                    ]}
                  />
                </Form.Item>
                {currentTargetMode === 'cluster_all' ? (
                  <Form.Item
                    name="cluster_id"
                    label={t('masterData.bootstrapImportTab.fields.cluster')}
                    rules={[{ required: true, message: t('masterData.bootstrapImportTab.validation.selectCluster') }]}
                    style={{ minWidth: 320, marginBottom: 8 }}
                  >
                    <Select
                      data-testid="bootstrap-collection-cluster-select"
                      loading={loadingTargets}
                      placeholder={t('masterData.bootstrapImportTab.placeholders.selectCluster')}
                      options={clusterOptions}
                    />
                  </Form.Item>
                ) : (
                  <Form.Item
                    name="database_ids"
                    label={t('masterData.bootstrapImportTab.fields.databases')}
                    rules={[{ required: true, type: 'array', min: 1, message: t('masterData.bootstrapImportTab.validation.selectAtLeastOneDatabase') }]}
                    style={{ minWidth: 420, marginBottom: 8 }}
                  >
                    <Select
                      data-testid="bootstrap-collection-databases-select"
                      mode="multiple"
                      allowClear
                      loading={loadingTargets}
                      placeholder={t('masterData.bootstrapImportTab.placeholders.selectDatabases')}
                      options={batchDatabaseOptions}
                    />
                  </Form.Item>
                )}
                <Form.Item
                  name="entity_scope"
                  label={t('masterData.bootstrapImportTab.fields.entityScope')}
                  rules={[{ required: true, type: 'array', min: 1, message: t('masterData.bootstrapImportTab.validation.selectAtLeastOneEntity') }]}
                  style={{ minWidth: 360, marginBottom: 8 }}
                >
                  <Select
                    data-testid="bootstrap-collection-entity-scope-select"
                    mode="multiple"
                    allowClear
                    placeholder={t('masterData.bootstrapImportTab.placeholders.selectEntities')}
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
              {t('masterData.bootstrapImportTab.actions.runPreflight')}
            </Button>
            <Button
              data-testid={launcherMode === 'single' ? 'bootstrap-import-run-dry-run' : 'bootstrap-collection-run-dry-run'}
              onClick={() => void handleCreateDryRun()}
              loading={runningDryRun}
              disabled={launcherMode === 'single' ? !singlePreflightResult?.ok : !effectiveBatchPreflightResult?.ok}
            >
              {t('masterData.bootstrapImportTab.actions.runDryRun')}
            </Button>
            <Button
              data-testid={launcherMode === 'single' ? 'bootstrap-import-run-execute' : 'bootstrap-collection-run-execute'}
              type="primary"
              onClick={() => void handleCreateExecute()}
              loading={runningExecute}
              disabled={!executeAllowed}
            >
              {t('masterData.bootstrapImportTab.actions.execute')}
            </Button>
            <Button
              data-testid={launcherMode === 'single' ? 'bootstrap-import-refresh' : 'bootstrap-collection-refresh'}
              onClick={() =>
                void (launcherMode === 'single' ? refreshJobsForCurrentDatabase() : loadCollections())
              }
              loading={launcherMode === 'single' ? loadingJobs : loadingCollections}
            >
              {t('catalog.actions.refresh')}
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
              message={singlePreflightResult.ok ? t('masterData.bootstrapImportTab.alerts.preflightPassed') : t('masterData.bootstrapImportTab.alerts.preflightFailed')}
              description={
                singlePreflightResult.errors.length > 0
                  ? singlePreflightResult.errors.map((item) => item.detail || item.code).join('; ')
                  : t('masterData.bootstrapImportTab.alerts.preflightValidDescription')
              }
            />
          )}

          {launcherMode === 'batch' && effectiveBatchPreflightResult && (
            <Alert
              type={effectiveBatchPreflightResult.ok ? 'success' : 'warning'}
              showIcon
              message={effectiveBatchPreflightResult.ok ? t('masterData.bootstrapImportTab.alerts.aggregatePreflightPassed') : t('masterData.bootstrapImportTab.alerts.aggregatePreflightFailed')}
              description={
                effectiveBatchPreflightResult.ok
                  ? t('masterData.bootstrapImportTab.alerts.aggregateReadyDescription', { count: effectiveBatchPreflightResult.database_count })
                  : effectiveBatchPreflightResult.errors
                      .map((item) => String(item.detail || item.code || t('masterData.bootstrapImportTab.alerts.preflightFailed')))
                      .join('; ')
              }
            />
          )}
        </Space>
      </Card>

      {launcherMode === 'single' ? (
        <>
          <Card
            title={t('masterData.bootstrapImportTab.page.currentJobTitle')}
            extra={
              <Space>
                <Button
                  data-testid="bootstrap-import-cancel-job"
                  onClick={() => void runJobAction('cancel')}
                  loading={runningJobAction}
                  disabled={!selectedJob || TERMINAL_JOB_STATUSES.has(selectedJob.status)}
                >
                  {t('masterData.bootstrapImportTab.actions.cancel')}
                </Button>
                <Button
                  data-testid="bootstrap-import-retry-failed"
                  onClick={() => void runJobAction('retry_failed_chunks')}
                  loading={runningJobAction}
                  disabled={
                    !selectedJob || (selectedJob.report.failed_count + selectedJob.report.deferred_count) === 0
                  }
                >
                  {t('masterData.bootstrapImportTab.actions.retryFailedChunks')}
                </Button>
              </Space>
            }
          >
            {!selectedJob ? (
              <Empty description={t('masterData.bootstrapImportTab.page.noBootstrapJob')} />
            ) : (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {buildBootstrapDedupeReviewHref(selectedJob) ? (
                  <Alert
                    type="warning"
                    showIcon
                    message={t('masterData.bootstrapImportTab.alerts.unresolvedDedupe')}
                    action={(
                      <Button type="link" href={buildBootstrapDedupeReviewHref(selectedJob) || undefined}>
                        {t('masterData.syncStatusTab.actions.openReview')}
                      </Button>
                    )}
                  />
                ) : null}

                <Space>
                  <Tag color={STATUS_COLOR[selectedJob.status] || 'default'}>{selectedJob.status}</Tag>
                  <Text type="secondary">{t('masterData.bootstrapImportTab.page.startedAt', { value: formatDateTime(selectedJob.started_at) })}</Text>
                  <Text type="secondary">{t('masterData.bootstrapImportTab.page.finishedAt', { value: formatDateTime(selectedJob.finished_at) })}</Text>
                </Space>

                <Progress
                  data-testid="bootstrap-import-progress"
                  percent={currentSingleCompletionPercent}
                  status={selectedJob.status === 'failed' ? 'exception' : 'active'}
                />

                <Descriptions size="small" bordered column={3}>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.rowsDryRun')}>{currentSingleRowsTotal}</Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.created')}>{selectedJob.report.created_count}</Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.updated')}>{selectedJob.report.updated_count}</Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.skipped')}>{selectedJob.report.skipped_count}</Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.failed')}>{selectedJob.report.failed_count}</Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.deferred')}>{selectedJob.report.deferred_count}</Descriptions.Item>
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

          <Card title={t('masterData.bootstrapImportTab.page.recentJobsTitle')}>
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
          <Card title={t('masterData.bootstrapImportTab.page.currentCollectionTitle')}>
            {!selectedCollection ? (
              <Empty description={t('masterData.bootstrapImportTab.page.noBatchCollection')} />
            ) : (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {selectedCollection.mode === 'preflight' && selectedCollection.status === 'failed' ? (
                  <Alert
                    type="warning"
                    showIcon
                    message={t('masterData.bootstrapImportTab.alerts.aggregatePreflightContainsFailed')}
                    description={t('masterData.bootstrapImportTab.alerts.aggregatePreflightBlockedDescription')}
                  />
                ) : null}
                {selectedCollection.mode === 'dry_run' &&
                Number(selectedCollection.aggregate_counters.failed || 0) > 0 ? (
                  <Alert
                    type="warning"
                    showIcon
                    message={t('masterData.bootstrapImportTab.alerts.batchDryRunContainsFailed')}
                    description={t('masterData.bootstrapImportTab.alerts.batchDryRunBlockedDescription')}
                  />
                ) : null}
                {selectedCollection.mode === 'dry_run' &&
                selectedCollection.status === 'dry_run_running' ? (
                  <Alert
                    type="info"
                    showIcon
                    message={t('masterData.bootstrapImportTab.alerts.batchDryRunRunning')}
                    description={t('masterData.bootstrapImportTab.alerts.batchDryRunRunningDescription')}
                  />
                ) : null}

                <Space>
                  <Tag color={COLLECTION_STATUS_COLOR[selectedCollection.status] || 'default'}>
                    {selectedCollection.status}
                  </Tag>
                  <Text type="secondary">
                    {t('masterData.bootstrapImportTab.page.requestedBy', {
                      value: selectedCollection.requested_by_username || selectedCollection.requested_by_id || t('common.noValue'),
                    })}
                  </Text>
                  <Text type="secondary">{t('masterData.bootstrapImportTab.page.createdAt', { value: formatDateTime(selectedCollection.created_at) })}</Text>
                </Space>

                <Progress
                  data-testid="bootstrap-collection-progress"
                  percent={currentCollectionCompletionPercent}
                  status={selectedCollection.status === 'failed' ? 'exception' : 'active'}
                />

                <Descriptions size="small" bordered column={3}>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.targetMode')}>
                    {selectedCollection.target_mode === 'cluster_all'
                      ? t('masterData.bootstrapImportTab.targetMode.clusterAll')
                      : t('masterData.bootstrapImportTab.targetMode.databaseSet')}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.cluster')}>
                    {selectedCollection.cluster_id
                      ? clusterNameById.get(selectedCollection.cluster_id) || selectedCollection.cluster_id
                      : t('common.noValue')}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.targetSnapshot')}>
                    {formatCollectionSnapshot(selectedCollection) || t('common.noValue')}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.rowsDryRun')}>{currentCollectionRowsTotal}</Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.scheduled')}>
                    {selectedCollection.aggregate_counters.scheduled || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.coalesced')}>
                    {selectedCollection.aggregate_counters.coalesced || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.completed')}>
                    {selectedCollection.aggregate_counters.completed || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.failed')}>
                    {selectedCollection.aggregate_counters.failed || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('masterData.bootstrapImportTab.details.skipped')}>
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

          <Card title={t('masterData.bootstrapImportTab.page.recentCollectionsTitle')}>
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
