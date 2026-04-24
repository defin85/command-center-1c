import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Checkbox,
  Descriptions,
  Empty,
  Form,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  createPoolMasterDataChartJob,
  discoverPoolMasterDataChartCandidates,
  getPoolMasterDataChartJob,
  listPoolMasterDataChartJobs,
  listPoolMasterDataChartSources,
  listPoolTargetDatabases,
  upsertPoolMasterDataChartSource,
  type ListPoolMasterDataChartJobsParams,
  type PoolMasterDataChartDiscoveryCandidate,
  type PoolMasterDataChartFollowerStatus,
  type PoolMasterDataChartJob,
  type PoolMasterDataChartMaterializationMode,
  type PoolMasterDataChartSource,
  type PoolMasterDataRegistryEntry,
  type SimpleDatabaseRef,
} from '../../../api/intercompanyPools'
import { usePoolsTranslation } from '../../../i18n'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import { findRegistryEntryByEntityType } from './registry'

const { Text } = Typography

const JOB_STATUS_COLOR: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  succeeded: 'success',
  failed: 'error',
}

const FOLLOWER_VERDICT_COLOR: Record<string, string> = {
  ok: 'success',
  backfilled: 'processing',
  missing: 'warning',
  ambiguous: 'error',
  stale: 'error',
}

type ChartImportFormValues = {
  database_id?: string
  chart_candidate_key?: string
  chart_identity?: string
  manual_override_reason?: string
}

type ChartImportTabProps = {
  registryEntries: PoolMasterDataRegistryEntry[]
}

function summarizeCounters(counters: Record<string, unknown> | undefined): string {
  if (!counters) {
    return '-'
  }
  const parts: string[] = []
  for (const key of [
    'rows_total',
    'created_count',
    'updated_count',
    'unchanged_count',
    'retired_count',
    'database_count',
    'ok_count',
    'backfilled_count',
    'missing_count',
    'ambiguous_count',
    'stale_count',
  ]) {
    const rawValue = counters[key]
    if (typeof rawValue === 'number') {
      parts.push(`${key}=${rawValue}`)
    }
  }
  return parts.length > 0 ? parts.join(' ') : '-'
}

function getChartCandidateKey(candidate: PoolMasterDataChartDiscoveryCandidate): string {
  return candidate.row_source_evidence_fingerprint || candidate.source_evidence_fingerprint || `${candidate.chart_identity}:${candidate.derivation_method}`
}

function isChartCandidateLoadReady(candidate: PoolMasterDataChartDiscoveryCandidate | null): boolean {
  return Boolean(candidate?.is_complete && candidate.row_source_status === 'ready')
}

function readRowSourceStatusFromSource(source: PoolMasterDataChartSource | null): string {
  const rowSource = source?.metadata?.row_source
  if (rowSource && typeof rowSource === 'object' && 'row_source_status' in rowSource) {
    const status = (rowSource as Record<string, unknown>).row_source_status
    return typeof status === 'string' ? status : ''
  }
  return ''
}

function readRowSourceRecordFromSource(source: PoolMasterDataChartSource | null): Record<string, unknown> {
  const rowSource = source?.metadata?.row_source
  return rowSource && typeof rowSource === 'object'
    ? rowSource as Record<string, unknown>
    : {}
}

function readSourceRevisionToken(job: PoolMasterDataChartJob | null): string {
  const countersToken = typeof job?.counters?.source_revision_token === 'string'
    ? job.counters.source_revision_token
    : ''
  if (countersToken) {
    return countersToken
  }
  const revision = job?.diagnostics?.source_revision
  if (revision && typeof revision === 'object' && 'token' in revision) {
    const value = (revision as Record<string, unknown>).token
    return typeof value === 'string' ? value : ''
  }
  return ''
}

export function ChartImportTab({ registryEntries }: ChartImportTabProps) {
  const { message } = AntApp.useApp()
  const { t } = usePoolsTranslation()
  const [form] = Form.useForm<ChartImportFormValues>()
  const [databases, setDatabases] = useState<SimpleDatabaseRef[]>([])
  const [sources, setSources] = useState<PoolMasterDataChartSource[]>([])
  const [jobs, setJobs] = useState<PoolMasterDataChartJob[]>([])
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null)
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [selectedJob, setSelectedJob] = useState<PoolMasterDataChartJob | null>(null)
  const [targetDatabaseIds, setTargetDatabaseIds] = useState<string[]>([])
  const [chartCandidates, setChartCandidates] = useState<PoolMasterDataChartDiscoveryCandidate[]>([])
  const [discoveryDiagnostics, setDiscoveryDiagnostics] = useState<Array<Record<string, unknown>>>([])
  const [manualOverride, setManualOverride] = useState(false)
  const [reviewedDryRunJobId, setReviewedDryRunJobId] = useState<string | null>(null)
  const [loadingTargets, setLoadingTargets] = useState(false)
  const [loadingDiscovery, setLoadingDiscovery] = useState(false)
  const [loadingSources, setLoadingSources] = useState(false)
  const [loadingJobs, setLoadingJobs] = useState(false)
  const [loadingJobDetail, setLoadingJobDetail] = useState(false)
  const [savingSource, setSavingSource] = useState(false)
  const [preparingInitialLoad, setPreparingInitialLoad] = useState(false)
  const [runningMode, setRunningMode] = useState<PoolMasterDataChartMaterializationMode | null>(null)

  const glAccountRegistryEntry = useMemo(
    () => findRegistryEntryByEntityType(registryEntries, 'gl_account'),
    [registryEntries]
  )
  const selectedSource = useMemo(
    () => sources.find((source) => source.id === selectedSourceId) ?? null,
    [selectedSourceId, sources]
  )
  const selectedCandidateKey = Form.useWatch('chart_candidate_key', form)
  const selectedCandidate = useMemo(
    () => chartCandidates.find((candidate) => getChartCandidateKey(candidate) === selectedCandidateKey) ?? null,
    [chartCandidates, selectedCandidateKey]
  )
  const selectedCandidateLoadReady = isChartCandidateLoadReady(selectedCandidate)
  const selectedSourceRowSourceStatus = readRowSourceStatusFromSource(selectedSource)
  const selectedSourceLoadReady = !selectedSource || !selectedSourceRowSourceStatus || selectedSourceRowSourceStatus === 'ready'
  const selectedSourceRowSource = readRowSourceRecordFromSource(selectedSource)
  const candidateDatabases = selectedSource?.candidate_databases ?? []
  const latestSuccessfulDryRun = useMemo(
    () => jobs.find((job) => job.mode === 'dry_run' && job.status === 'succeeded') ?? null,
    [jobs]
  )
  const successfulModes = useMemo(
    () => new Set(
      jobs
        .filter((job) => job.status === 'succeeded')
        .map((job) => job.mode)
    ),
    [jobs]
  )
  const hasSuccessfulPreflight = successfulModes.has('preflight')
  const hasSuccessfulDryRun = successfulModes.has('dry_run')
  const hasSuccessfulMaterialization = successfulModes.has('materialize')
  const hasSnapshot = Boolean(selectedSource?.latest_snapshot)
  const hasFollowerTargets = targetDatabaseIds.length > 0 || candidateDatabases.length > 0
  const hasReviewedDryRun = Boolean(latestSuccessfulDryRun && reviewedDryRunJobId === latestSuccessfulDryRun.id)

  const getModeLabel = useCallback((mode: string) => {
    if (mode === 'preflight') return t('masterData.chartImportTab.mode.preflight')
    if (mode === 'dry_run') return t('masterData.chartImportTab.mode.dryRun')
    if (mode === 'materialize') return t('masterData.chartImportTab.mode.materialize')
    if (mode === 'verify_followers') return t('masterData.chartImportTab.mode.verifyFollowers')
    if (mode === 'backfill_bindings') return t('masterData.chartImportTab.mode.backfillBindings')
    return mode
  }, [t])

  const loadTargets = useCallback(async () => {
    setLoadingTargets(true)
    try {
      const response = await listPoolTargetDatabases()
      setDatabases(response)
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.chartImportTab.messages.failedToLoadTargets'))
      message.error(resolved.message)
    } finally {
      setLoadingTargets(false)
    }
  }, [message, t])

  const loadDiscovery = useCallback(async (databaseId: string) => {
    const normalizedDatabaseId = String(databaseId || '').trim()
    if (!normalizedDatabaseId) {
      setChartCandidates([])
      setDiscoveryDiagnostics([])
      form.setFieldsValue({ chart_candidate_key: undefined, chart_identity: undefined })
      return
    }
    setLoadingDiscovery(true)
    try {
      const response = await discoverPoolMasterDataChartCandidates(normalizedDatabaseId)
      setChartCandidates(response.candidates)
      setDiscoveryDiagnostics(response.diagnostics)
      const currentIdentity = String(form.getFieldValue('chart_identity') || '').trim()
      const selectedByIdentity = response.candidates.find((candidate) => (
        candidate.is_complete && candidate.chart_identity === currentIdentity
      ))
      const firstComplete = response.candidates.find((candidate) => candidate.is_complete)
      const firstLoadReady = response.candidates.find((candidate) => isChartCandidateLoadReady(candidate))
      const candidate = selectedByIdentity ?? firstLoadReady ?? firstComplete ?? null
      form.setFieldsValue({
        chart_candidate_key: candidate ? getChartCandidateKey(candidate) : undefined,
        chart_identity: candidate?.chart_identity ?? (manualOverride ? currentIdentity : undefined),
      })
    } catch (error) {
      setChartCandidates([])
      setDiscoveryDiagnostics([])
      const resolved = resolveApiError(error, t('masterData.chartImportTab.messages.failedToDiscoverCharts'))
      message.error(resolved.message)
    } finally {
      setLoadingDiscovery(false)
    }
  }, [form, manualOverride, message, t])

  const loadSources = useCallback(async () => {
    setLoadingSources(true)
    try {
      const response = await listPoolMasterDataChartSources({ limit: 20, offset: 0 })
      setSources(response.sources)
      setSelectedSourceId((current) => {
        if (current && response.sources.some((source) => source.id === current)) {
          return current
        }
        return response.sources[0]?.id ?? null
      })
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.chartImportTab.messages.failedToLoadSources'))
      message.error(resolved.message)
    } finally {
      setLoadingSources(false)
    }
  }, [message, t])

  const loadJobs = useCallback(async (params: ListPoolMasterDataChartJobsParams = {}) => {
    setLoadingJobs(true)
    try {
      const response = await listPoolMasterDataChartJobs({
        limit: 20,
        offset: 0,
        ...params,
      })
      setJobs(response.jobs)
      setSelectedJobId((current) => {
        if (current && response.jobs.some((job) => job.id === current)) {
          return current
        }
        return response.jobs[0]?.id ?? null
      })
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.chartImportTab.messages.failedToLoadJobs'))
      message.error(resolved.message)
    } finally {
      setLoadingJobs(false)
    }
  }, [message, t])

  const loadJobDetail = useCallback(async (jobId: string, silent = false) => {
    if (!silent) {
      setLoadingJobDetail(true)
    }
    try {
      const response = await getPoolMasterDataChartJob(jobId)
      setSelectedJob(response.job)
    } catch (error) {
      if (!silent) {
        const resolved = resolveApiError(error, t('masterData.chartImportTab.messages.failedToLoadJobDetail'))
        message.error(resolved.message)
      }
    } finally {
      if (!silent) {
        setLoadingJobDetail(false)
      }
    }
  }, [message, t])

  useEffect(() => {
    void loadTargets()
    void loadSources()
  }, [loadSources, loadTargets])

  useEffect(() => {
    if (!selectedSourceId) {
      setJobs([])
      setSelectedJobId(null)
      setSelectedJob(null)
      return
    }
    void loadJobs({ chart_source_id: selectedSourceId })
  }, [loadJobs, selectedSourceId])

  useEffect(() => {
    if (!selectedJobId) {
      setSelectedJob(null)
      return
    }
    void loadJobDetail(selectedJobId, true)
  }, [loadJobDetail, selectedJobId])

  useEffect(() => {
    if (!latestSuccessfulDryRun || reviewedDryRunJobId === latestSuccessfulDryRun.id) {
      return
    }
    setReviewedDryRunJobId(null)
  }, [latestSuccessfulDryRun, reviewedDryRunJobId])

  useEffect(() => {
    if (!selectedSource) {
      form.resetFields()
      setTargetDatabaseIds([])
      setChartCandidates([])
      setDiscoveryDiagnostics([])
      setReviewedDryRunJobId(null)
      return
    }
    form.setFieldsValue({
      database_id: selectedSource.database_id,
      chart_identity: selectedSource.chart_identity,
    })
    setTargetDatabaseIds(selectedSource.candidate_databases.map((item) => item.database_id))
    void loadDiscovery(selectedSource.database_id)
  }, [form, loadDiscovery, selectedSource])

  const saveSourceFromForm = useCallback(async (): Promise<PoolMasterDataChartSource | null> => {
    let values: ChartImportFormValues
    try {
      values = await form.validateFields()
    } catch {
      return null
    }
    const candidate = selectedCandidate
    if (!manualOverride && !candidate) {
      message.warning(t('masterData.chartImportTab.messages.selectChartCandidate'))
      return null
    }
    if (!manualOverride && candidate && !candidate.is_complete) {
      message.warning(t('masterData.chartImportTab.messages.discoveryCandidateIncomplete'))
      return null
    }
    setSavingSource(true)
    try {
      const response = await upsertPoolMasterDataChartSource({
        database_id: String(values.database_id || '').trim(),
        chart_identity: manualOverride
          ? String(values.chart_identity || '').trim()
          : String(candidate?.chart_identity || '').trim(),
        discovery_provenance: !manualOverride && candidate
          ? candidate as unknown as Record<string, unknown>
          : undefined,
        manual_override_reason: manualOverride
          ? String(values.manual_override_reason || '').trim()
          : undefined,
        discovery_diagnostics: manualOverride
          ? discoveryDiagnostics
          : undefined,
      })
      message.success(t('masterData.chartImportTab.messages.sourceSaved'))
      setSelectedSourceId(response.source.id)
      await loadSources()
      return response.source
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.chartImportTab.messages.failedToSaveSource'))
      message.error(resolved.message)
      return null
    } finally {
      setSavingSource(false)
    }
  }, [
    discoveryDiagnostics,
    form,
    loadSources,
    manualOverride,
    message,
    selectedCandidate,
    t,
  ])

  const handleUpsertSource = async () => {
    await saveSourceFromForm()
  }

  const handlePrepareInitialLoad = useCallback(async () => {
    if (manualOverride || !selectedCandidateLoadReady) {
      message.warning(t('masterData.chartImportTab.messages.rowSourceNotReady'))
      return
    }
    const source = await saveSourceFromForm()
    if (!source) {
      return
    }
    setPreparingInitialLoad(true)
    try {
      const preflight = await createPoolMasterDataChartJob({
        chart_source_id: source.id,
        mode: 'preflight',
      })
      const dryRun = await createPoolMasterDataChartJob({
        chart_source_id: source.id,
        mode: 'dry_run',
      })
      setReviewedDryRunJobId(null)
      setSelectedJobId(dryRun.job.id)
      setSelectedJob(dryRun.job)
      await Promise.all([
        loadSources(),
        loadJobs({ chart_source_id: source.id }),
      ])
      message.success(t('masterData.chartImportTab.messages.initialLoadReady', {
        preflight: getModeLabel(preflight.job.mode),
        dryRun: getModeLabel(dryRun.job.mode),
      }))
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.chartImportTab.messages.failedToPrepareInitialLoad'))
      message.error(resolved.message)
    } finally {
      setPreparingInitialLoad(false)
    }
  }, [
    getModeLabel,
    loadJobs,
    loadSources,
    manualOverride,
    message,
    saveSourceFromForm,
    selectedCandidateLoadReady,
    t,
  ])

  const runJob = useCallback(async (mode: PoolMasterDataChartMaterializationMode) => {
    if (!selectedSource) {
      message.error(t('masterData.chartImportTab.messages.selectSourceFirst'))
      return
    }
    if (!selectedSourceLoadReady && (mode === 'preflight' || mode === 'dry_run' || mode === 'materialize')) {
      message.warning(t('masterData.chartImportTab.messages.rowSourceNotReady'))
      return
    }
    if (mode === 'dry_run' && !hasSuccessfulPreflight) {
      message.warning(t('masterData.chartImportTab.messages.runPreflightFirst'))
      return
    }
    if (mode === 'materialize' && !hasSuccessfulDryRun) {
      message.warning(t('masterData.chartImportTab.messages.runDryRunFirst'))
      return
    }
    if (mode === 'materialize' && !hasReviewedDryRun) {
      message.warning(t('masterData.chartImportTab.messages.reviewDryRunFirst'))
      return
    }
    if ((mode === 'verify_followers' || mode === 'backfill_bindings') && !hasSnapshot) {
      message.warning(t('masterData.chartImportTab.messages.materializeFirst'))
      return
    }
    if ((mode === 'verify_followers' || mode === 'backfill_bindings') && !hasFollowerTargets) {
      message.warning(t('masterData.chartImportTab.messages.noFollowerTargets'))
      return
    }

    setRunningMode(mode)
    try {
      const jobPayload: Parameters<typeof createPoolMasterDataChartJob>[0] = {
        chart_source_id: selectedSource.id,
        mode,
        database_ids: mode === 'verify_followers' || mode === 'backfill_bindings'
          ? targetDatabaseIds
          : undefined,
      }
      if (mode === 'materialize' && latestSuccessfulDryRun) {
        jobPayload.materialize_review = {
          dry_run_job_id: latestSuccessfulDryRun.id,
          source_revision_token: readSourceRevisionToken(latestSuccessfulDryRun),
          reviewed_counters: latestSuccessfulDryRun.counters,
        }
      }
      const response = await createPoolMasterDataChartJob(jobPayload)
      if (mode === 'dry_run') {
        setReviewedDryRunJobId(null)
      }
      setSelectedJobId(response.job.id)
      setSelectedJob(response.job)
      await Promise.all([
        loadSources(),
        loadJobs({ chart_source_id: selectedSource.id }),
      ])
      message.success(t('masterData.chartImportTab.messages.jobCompleted', { mode: getModeLabel(mode) }))
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.chartImportTab.messages.failedToRunJob'))
      message.error(resolved.message)
    } finally {
      setRunningMode(null)
    }
  }, [
    getModeLabel,
    hasFollowerTargets,
    hasSnapshot,
    hasReviewedDryRun,
    hasSuccessfulDryRun,
    hasSuccessfulPreflight,
    latestSuccessfulDryRun,
    loadJobs,
    loadSources,
    message,
    selectedSource,
    selectedSourceLoadReady,
    t,
    targetDatabaseIds,
  ])

  const sourceColumns: ColumnsType<PoolMasterDataChartSource> = useMemo(() => [
    {
      title: t('masterData.chartImportTab.columns.database'),
      dataIndex: 'database_name',
      key: 'database_name',
      render: (_value, row) => (
        <Space direction="vertical" size={0}>
          <Text>{row.database_name}</Text>
          <Text type="secondary">{row.chart_identity}</Text>
        </Space>
      ),
    },
    {
      title: t('masterData.chartImportTab.columns.compatibilityClass'),
      dataIndex: 'config_name',
      key: 'config_name',
      render: (_value, row) => `${row.config_name} / ${row.config_version}`,
    },
    {
      title: t('masterData.chartImportTab.columns.status'),
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => <Tag color={JOB_STATUS_COLOR[value] ?? 'default'}>{value}</Tag>,
    },
    {
      title: t('masterData.chartImportTab.columns.snapshot'),
      dataIndex: 'latest_snapshot',
      key: 'latest_snapshot',
      render: (value: PoolMasterDataChartSource['latest_snapshot']) => (
        value
          ? `${value.row_count} / ${value.fingerprint.slice(0, 12)}`
          : '-'
      ),
    },
    {
      title: t('masterData.chartImportTab.columns.updated'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (value: string) => formatDateTime(value),
    },
  ], [t])

  const jobColumns: ColumnsType<PoolMasterDataChartJob> = useMemo(() => [
    {
      title: t('masterData.chartImportTab.columns.mode'),
      dataIndex: 'mode',
      key: 'mode',
      render: (value: string) => getModeLabel(value),
    },
    {
      title: t('masterData.chartImportTab.columns.status'),
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => <Tag color={JOB_STATUS_COLOR[value] ?? 'default'}>{value}</Tag>,
    },
    {
      title: t('masterData.chartImportTab.columns.outcomes'),
      dataIndex: 'counters',
      key: 'counters',
      render: (value: Record<string, unknown>) => summarizeCounters(value),
    },
    {
      title: t('masterData.chartImportTab.columns.updated'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (value: string) => formatDateTime(value),
    },
  ], [getModeLabel, t])

  const followerColumns: ColumnsType<PoolMasterDataChartFollowerStatus> = useMemo(() => [
    {
      title: t('masterData.chartImportTab.columns.database'),
      dataIndex: 'database_name',
      key: 'database_name',
      render: (_value: string, row: PoolMasterDataChartFollowerStatus) => (
        <Space direction="vertical" size={0}>
          <Text>{row.database_name}</Text>
          {row.detail ? <Text type="secondary">{row.detail}</Text> : null}
        </Space>
      ),
    },
    {
      title: t('masterData.chartImportTab.columns.verdict'),
      dataIndex: 'verdict',
      key: 'verdict',
      render: (value: string) => <Tag color={FOLLOWER_VERDICT_COLOR[value] ?? 'default'}>{value}</Tag>,
    },
    {
      title: t('masterData.chartImportTab.columns.outcomes'),
      dataIndex: 'diagnostics',
      key: 'diagnostics',
      render: (_value: unknown, row: PoolMasterDataChartFollowerStatus) => summarizeCounters({
        matched_accounts: row.matched_accounts,
        missing_accounts: row.missing_accounts,
        ambiguous_accounts: row.ambiguous_accounts,
        stale_bindings: row.stale_bindings,
        backfilled_accounts: row.backfilled_accounts,
      }),
    },
    {
      title: t('masterData.chartImportTab.columns.remediation'),
      dataIndex: 'bindings_remediation_href',
      key: 'bindings_remediation_href',
      render: (value: string | null | undefined) => (
        value
          ? (
            <Button type="link" href={value}>
              {t('masterData.chartImportTab.actions.openBindings')}
            </Button>
          )
          : '-'
      ),
    },
  ], [t])

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message={t('masterData.chartImportTab.alerts.contractTitle')}
        description={t('masterData.chartImportTab.alerts.contractDescription')}
      />

      {glAccountRegistryEntry ? (
        <Alert
          type="info"
          showIcon
          message={t('masterData.chartImportTab.alerts.registryTitle')}
          description={(
            <Space size={8} wrap>
              <Tag color={glAccountRegistryEntry.capabilities.bootstrap_import ? 'success' : 'default'}>
                {t('masterData.chartImportTab.alerts.bootstrapCapable')}
              </Tag>
              <Tag color={!glAccountRegistryEntry.capabilities.sync_outbound ? 'blue' : 'error'}>
                {t('masterData.chartImportTab.alerts.noGenericSync')}
              </Tag>
              <Tag color={!glAccountRegistryEntry.capabilities.outbox_fanout ? 'blue' : 'error'}>
                {t('masterData.chartImportTab.alerts.noOutboxFanout')}
              </Tag>
            </Space>
          )}
        />
      ) : null}

      {selectedSource?.last_error ? (
        <Alert
          type="error"
          showIcon
          message={selectedSource.last_error_code || t('masterData.chartImportTab.alerts.sourceError')}
          description={selectedSource.last_error}
        />
      ) : null}

      {selectedJob?.status === 'failed' ? (
        <Alert
          type="error"
          showIcon
          message={selectedJob.last_error_code || t('masterData.chartImportTab.alerts.jobFailed')}
          description={selectedJob.last_error}
        />
      ) : null}

      {!hasSuccessfulPreflight && selectedSource ? (
        <Alert
          type="warning"
          showIcon
          message={t('masterData.chartImportTab.alerts.preflightRequired')}
          description={t('masterData.chartImportTab.alerts.preflightRequiredDescription')}
        />
      ) : null}

      {selectedSource && !selectedSourceLoadReady ? (
        <Alert
          type="warning"
          showIcon
          message={t('masterData.chartImportTab.alerts.rowSourceNotReady')}
          description={t('masterData.chartImportTab.alerts.rowSourceNotReadyDescription')}
        />
      ) : null}

      {!hasFollowerTargets && hasSnapshot ? (
        <Alert
          type="warning"
          showIcon
          message={t('masterData.chartImportTab.alerts.noFollowerTargets')}
          description={t('masterData.chartImportTab.alerts.noFollowerTargetsDescription')}
        />
      ) : null}

      <Card title={t('masterData.chartImportTab.page.sourceTitle')}>
        <Form form={form} layout="vertical">
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Form.Item
              label={t('masterData.chartImportTab.fields.database')}
              name="database_id"
              rules={[{ required: true, message: t('masterData.chartImportTab.validation.selectDatabase') }]}
            >
              <Select
                showSearch
                loading={loadingTargets}
                options={databases.map((database) => ({
                  value: database.id,
                  label: database.name,
                }))}
                placeholder={t('masterData.chartImportTab.placeholders.selectDatabase')}
                data-testid="chart-import-source-database-select"
                optionFilterProp="label"
                onChange={(value) => {
                  form.setFieldsValue({
                    chart_candidate_key: undefined,
                    chart_identity: undefined,
                    manual_override_reason: undefined,
                  })
                  setReviewedDryRunJobId(null)
                  void loadDiscovery(value)
                }}
              />
            </Form.Item>
            <Form.Item
              label={t('masterData.chartImportTab.fields.chartCandidate')}
              name="chart_candidate_key"
              rules={manualOverride ? [] : [{ required: true, message: t('masterData.chartImportTab.validation.selectChartCandidate') }]}
            >
              <Select
                loading={loadingDiscovery}
                disabled={manualOverride}
                options={chartCandidates.map((candidate) => ({
                  value: getChartCandidateKey(candidate),
                  label: `${candidate.name || candidate.chart_identity} · ${candidate.derivation_method}`,
                  disabled: !candidate.is_complete,
                }))}
                placeholder={t('masterData.chartImportTab.placeholders.selectChartCandidate')}
                data-testid="chart-import-chart-candidate-select"
                onChange={(value) => {
                  const candidate = chartCandidates.find((item) => getChartCandidateKey(item) === value)
                  form.setFieldsValue({ chart_identity: candidate?.chart_identity })
                }}
              />
            </Form.Item>
            {selectedCandidate ? (
              <Space direction="vertical" size={8} style={{ width: '100%' }} data-testid="chart-import-selected-candidate-evidence">
                <Space size={8} wrap>
                  <Tag color={selectedCandidate.confidence === 'high' ? 'success' : 'processing'}>
                    {selectedCandidate.confidence}
                  </Tag>
                  <Tag>{selectedCandidate.source_kind}</Tag>
                  <Tag color={selectedCandidateLoadReady ? 'success' : 'warning'}>
                    {selectedCandidate.row_source_status || 'identity_only'}
                  </Tag>
                  <Text code>{selectedCandidate.chart_identity}</Text>
                  <Text type="secondary">{selectedCandidate.source_evidence_fingerprint.slice(0, 12)}</Text>
                </Space>
                {selectedCandidateLoadReady ? (
                  <Descriptions size="small" column={1} data-testid="chart-import-row-source-preview">
                    <Descriptions.Item label={t('masterData.chartImportTab.details.rowSourceEntity')}>
                      <Text code>{selectedCandidate.row_source_entity_name || '-'}</Text>
                    </Descriptions.Item>
                    <Descriptions.Item label={t('masterData.chartImportTab.details.rowSourceMapping')}>
                      {Object.entries(selectedCandidate.row_source_field_mapping ?? {})
                        .map(([target, source]) => `${target} <- ${source}`)
                        .join(', ') || '-'}
                    </Descriptions.Item>
                    <Descriptions.Item label={t('masterData.chartImportTab.details.rowSourceEvidence')}>
                      {selectedCandidate.row_source_evidence_fingerprint?.slice(0, 12) || '-'}
                    </Descriptions.Item>
                  </Descriptions>
                ) : (
                  <Alert
                    type="warning"
                    showIcon
                    message={t('masterData.chartImportTab.alerts.rowSourceNotReady')}
                    description={t('masterData.chartImportTab.alerts.rowSourceNotReadyDescription')}
                  />
                )}
              </Space>
            ) : null}
            {discoveryDiagnostics.length > 0 ? (
              <Alert
                type={chartCandidates.some((candidate) => candidate.is_complete) ? 'info' : 'warning'}
                showIcon
                message={t('masterData.chartImportTab.alerts.discoveryDiagnostics')}
                description={discoveryDiagnostics.map((item) => String(item.detail ?? item.code ?? '')).filter(Boolean).join(' ')}
              />
            ) : null}
            <Checkbox
              checked={manualOverride}
              onChange={(event) => {
                setManualOverride(event.target.checked)
                form.setFieldsValue({
                  chart_identity: event.target.checked ? form.getFieldValue('chart_identity') : selectedCandidate?.chart_identity,
                  manual_override_reason: undefined,
                })
              }}
              data-testid="chart-import-manual-override"
            >
              {t('masterData.chartImportTab.fields.manualOverride')}
            </Checkbox>
            {manualOverride ? (
              <>
                <Form.Item
                  label={t('masterData.chartImportTab.fields.chartIdentity')}
                  name="chart_identity"
                  rules={[{ required: true, message: t('masterData.chartImportTab.validation.enterChartIdentity') }]}
                >
                  <Input
                    placeholder={t('masterData.chartImportTab.placeholders.chartIdentity')}
                    data-testid="chart-import-source-chart-identity-input"
                  />
                </Form.Item>
                <Form.Item
                  label={t('masterData.chartImportTab.fields.manualOverrideReason')}
                  name="manual_override_reason"
                  rules={[{ required: true, message: t('masterData.chartImportTab.validation.enterManualOverrideReason') }]}
                >
                  <Input.TextArea
                    rows={3}
                    placeholder={t('masterData.chartImportTab.placeholders.manualOverrideReason')}
                    data-testid="chart-import-manual-override-reason"
                  />
                </Form.Item>
              </>
            ) : null}
            <Space size={8} wrap>
              <Button
                type="primary"
                loading={savingSource}
                onClick={() => { void handleUpsertSource() }}
                data-testid="chart-import-upsert-source"
              >
                {t('masterData.chartImportTab.actions.saveSource')}
              </Button>
              <Button
                loading={loadingDiscovery}
                onClick={() => { void loadDiscovery(String(form.getFieldValue('database_id') || '')) }}
                data-testid="chart-import-discover-candidates"
              >
                {t('masterData.chartImportTab.actions.discoverCharts')}
              </Button>
              <Button
                loading={preparingInitialLoad}
                disabled={manualOverride || !selectedCandidateLoadReady}
                onClick={() => { void handlePrepareInitialLoad() }}
                data-testid="chart-import-prepare-initial-load"
              >
                {t('masterData.chartImportTab.actions.prepareInitialLoad')}
              </Button>
              <Button
                onClick={() => { void loadSources() }}
                loading={loadingSources}
              >
                {t('masterData.chartImportTab.actions.refreshSources')}
              </Button>
            </Space>
          </Space>
        </Form>
      </Card>

      <Card title={t('masterData.chartImportTab.page.lifecycleTitle')}>
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Select
            mode="multiple"
            value={targetDatabaseIds}
            onChange={(value) => setTargetDatabaseIds(value)}
            options={candidateDatabases.map((database) => ({
              value: database.database_id,
              label: database.database_name,
            }))}
            placeholder={t('masterData.chartImportTab.placeholders.selectFollowerDatabases')}
            data-testid="chart-import-target-databases-select"
          />
          <Checkbox
            disabled={!latestSuccessfulDryRun}
            checked={hasReviewedDryRun}
            onChange={(event) => {
              setReviewedDryRunJobId(event.target.checked && latestSuccessfulDryRun ? latestSuccessfulDryRun.id : null)
            }}
            data-testid="chart-import-review-dry-run"
          >
            {t('masterData.chartImportTab.fields.reviewDryRun')}
          </Checkbox>
          <Space size={8} wrap>
            <Button
              type="primary"
              disabled={!selectedSource || !selectedSourceLoadReady}
              loading={runningMode === 'preflight'}
              onClick={() => { void runJob('preflight') }}
              data-testid="chart-import-run-preflight"
            >
              {t('masterData.chartImportTab.actions.runPreflight')}
            </Button>
            <Button
              disabled={!selectedSource || !selectedSourceLoadReady || !hasSuccessfulPreflight}
              loading={runningMode === 'dry_run'}
              onClick={() => { void runJob('dry_run') }}
              data-testid="chart-import-run-dry-run"
            >
              {t('masterData.chartImportTab.actions.runDryRun')}
            </Button>
            <Button
              disabled={!selectedSource || !selectedSourceLoadReady || !hasSuccessfulDryRun || !hasReviewedDryRun}
              loading={runningMode === 'materialize'}
              onClick={() => { void runJob('materialize') }}
              data-testid="chart-import-run-materialize"
            >
              {t('masterData.chartImportTab.actions.runMaterialize')}
            </Button>
            <Button
              disabled={!selectedSource || !hasSnapshot || !hasFollowerTargets}
              loading={runningMode === 'verify_followers'}
              onClick={() => { void runJob('verify_followers') }}
              data-testid="chart-import-run-verify"
            >
              {t('masterData.chartImportTab.actions.runVerifyFollowers')}
            </Button>
            <Button
              disabled={!selectedSource || !hasSnapshot || !hasFollowerTargets}
              loading={runningMode === 'backfill_bindings'}
              onClick={() => { void runJob('backfill_bindings') }}
              data-testid="chart-import-run-backfill"
            >
              {t('masterData.chartImportTab.actions.runBackfill')}
            </Button>
          </Space>
        </Space>
      </Card>

      <Card title={t('masterData.chartImportTab.page.currentSourceTitle')}>
        {selectedSource ? (
          <Descriptions column={1} size="small">
            <Descriptions.Item label={t('masterData.chartImportTab.details.database')}>
              {selectedSource.database_name}
            </Descriptions.Item>
            <Descriptions.Item label={t('masterData.chartImportTab.details.chartIdentity')}>
              {selectedSource.chart_identity}
            </Descriptions.Item>
            <Descriptions.Item label={t('masterData.chartImportTab.details.compatibilityClass')}>
              {selectedSource.config_name} / {selectedSource.config_version}
            </Descriptions.Item>
            <Descriptions.Item label={t('masterData.chartImportTab.details.rowSourceStatus')}>
              <Tag color={selectedSourceLoadReady ? 'success' : 'warning'}>
                {selectedSourceRowSourceStatus || 'legacy'}
              </Tag>
            </Descriptions.Item>
            {selectedSourceRowSource.row_source_entity_name ? (
              <Descriptions.Item label={t('masterData.chartImportTab.details.rowSourceEntity')}>
                <Text code>{String(selectedSourceRowSource.row_source_entity_name)}</Text>
              </Descriptions.Item>
            ) : null}
            <Descriptions.Item label={t('masterData.chartImportTab.details.selectedSourceId')}>
              <Text code data-testid="pool-master-data-chart-import-selected-source-id">
                {selectedSource.id}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label={t('masterData.chartImportTab.details.latestSnapshot')}>
              {selectedSource.latest_snapshot
                ? `${selectedSource.latest_snapshot.row_count} · ${selectedSource.latest_snapshot.fingerprint.slice(0, 12)}`
                : '-'}
            </Descriptions.Item>
            <Descriptions.Item label={t('masterData.chartImportTab.details.candidateDatabases')}>
              {candidateDatabases.length > 0
                ? candidateDatabases.map((item) => item.database_name).join(', ')
                : t('masterData.chartImportTab.details.noCandidateDatabases')}
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={t('masterData.chartImportTab.page.noSource')}
          />
        )}
      </Card>

      <Card title={t('masterData.chartImportTab.page.currentJobTitle')}>
        {selectedJob ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label={t('masterData.chartImportTab.details.mode')}>
                {getModeLabel(selectedJob.mode)}
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.chartImportTab.details.status')}>
                <Tag color={JOB_STATUS_COLOR[selectedJob.status] ?? 'default'}>{selectedJob.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.chartImportTab.details.selectedJobId')}>
                <Text code data-testid="pool-master-data-chart-import-selected-job-id">
                  {selectedJob.id}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.chartImportTab.details.counters')}>
                {summarizeCounters(selectedJob.counters)}
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.chartImportTab.details.requestedBy')}>
                {selectedJob.requested_by_username || '-'}
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.chartImportTab.details.updated')}>
                {formatDateTime(selectedJob.updated_at)}
              </Descriptions.Item>
            </Descriptions>
            {selectedJob.snapshot ? (
              <Alert
                type="info"
                showIcon
                message={t('masterData.chartImportTab.alerts.snapshotReady')}
                description={`${selectedJob.snapshot.row_count} · ${selectedJob.snapshot.fingerprint}`}
              />
            ) : null}
            {Array.isArray(selectedJob.follower_statuses) && selectedJob.follower_statuses.length > 0 ? (
              <Table
                rowKey="id"
                size="small"
                pagination={false}
                loading={loadingJobDetail}
                columns={followerColumns}
                dataSource={selectedJob.follower_statuses}
              />
            ) : (
              <Text type="secondary">
                {hasSuccessfulMaterialization
                  ? t('masterData.chartImportTab.page.noFollowerStatusesYet')
                  : t('masterData.chartImportTab.page.noFollowerStatuses')}
              </Text>
            )}
          </Space>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={t('masterData.chartImportTab.page.noJob')}
          />
        )}
      </Card>

      <Card title={t('masterData.chartImportTab.page.recentSourcesTitle')}>
        <Table
          rowKey="id"
          size="small"
          pagination={false}
          loading={loadingSources}
          columns={sourceColumns}
          dataSource={sources}
          rowClassName={(row) => (row.id === selectedSourceId ? 'ant-table-row-selected' : '')}
          onRow={(row) => ({
            onClick: () => setSelectedSourceId(row.id),
          })}
        />
      </Card>

      <Card title={t('masterData.chartImportTab.page.recentJobsTitle')}>
        <Table
          rowKey="id"
          size="small"
          pagination={false}
          loading={loadingJobs}
          columns={jobColumns}
          dataSource={jobs}
          rowClassName={(row) => (row.id === selectedJobId ? 'ant-table-row-selected' : '')}
          onRow={(row) => ({
            onClick: () => setSelectedJobId(row.id),
          })}
        />
      </Card>
    </Space>
  )
}
