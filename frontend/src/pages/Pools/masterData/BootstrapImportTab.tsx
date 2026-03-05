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
  createPoolMasterDataBootstrapImportJob,
  getPoolMasterDataBootstrapImportJob,
  listPoolMasterDataBootstrapImportJobs,
  listPoolTargetDatabases,
  retryFailedPoolMasterDataBootstrapImportChunks,
  runPoolMasterDataBootstrapImportPreflight,
  type PoolMasterDataBootstrapImportChunk,
  type PoolMasterDataBootstrapImportEntityType,
  type PoolMasterDataBootstrapImportJob,
  type PoolMasterDataBootstrapImportPreflightResult,
  type SimpleDatabaseRef,
} from '../../../api/intercompanyPools'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'

const { Text } = Typography

type BootstrapScopeFormValues = {
  database_id: string
  entity_scope: PoolMasterDataBootstrapImportEntityType[]
}

const ENTITY_SCOPE_OPTIONS: { value: PoolMasterDataBootstrapImportEntityType; label: string }[] = [
  { value: 'party', label: 'party' },
  { value: 'item', label: 'item' },
  { value: 'tax_profile', label: 'tax_profile' },
  { value: 'contract', label: 'contract' },
  { value: 'binding', label: 'binding' },
]

const TERMINAL_JOB_STATUSES = new Set(['finalized', 'failed', 'canceled'])

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

export function BootstrapImportTab() {
  const { message } = AntApp.useApp()
  const [form] = Form.useForm<BootstrapScopeFormValues>()
  const [databases, setDatabases] = useState<SimpleDatabaseRef[]>([])
  const [jobs, setJobs] = useState<PoolMasterDataBootstrapImportJob[]>([])
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [selectedJob, setSelectedJob] = useState<PoolMasterDataBootstrapImportJob | null>(null)
  const [preflightResult, setPreflightResult] = useState<PoolMasterDataBootstrapImportPreflightResult | null>(null)
  const [dryRunSummary, setDryRunSummary] = useState<Record<string, unknown> | null>(null)
  const [loadingDatabases, setLoadingDatabases] = useState(false)
  const [loadingJobs, setLoadingJobs] = useState(false)
  const [loadingJobDetail, setLoadingJobDetail] = useState(false)
  const [runningPreflight, setRunningPreflight] = useState(false)
  const [runningDryRun, setRunningDryRun] = useState(false)
  const [runningExecute, setRunningExecute] = useState(false)
  const [runningJobAction, setRunningJobAction] = useState(false)
  const [jobActionError, setJobActionError] = useState('')

  const loadDatabases = useCallback(async () => {
    setLoadingDatabases(true)
    try {
      const response = await listPoolTargetDatabases()
      setDatabases(response)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить список баз для bootstrap import.')
      message.error(resolved.message)
    } finally {
      setLoadingDatabases(false)
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

  useEffect(() => {
    void loadDatabases()
    void loadJobs()
  }, [loadDatabases, loadJobs])

  useEffect(() => {
    if (!selectedJobId) {
      setSelectedJob(null)
      return
    }
    void loadJobDetail(selectedJobId)
  }, [loadJobDetail, selectedJobId])

  useEffect(() => {
    if (!selectedJobId || !selectedJob || TERMINAL_JOB_STATUSES.has(selectedJob.status)) {
      return
    }
    const timer = window.setInterval(() => {
      void loadJobDetail(selectedJobId, true)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [loadJobDetail, selectedJob, selectedJobId])

  const currentWizardStep = useMemo(() => {
    if (selectedJob?.status === 'finalized') {
      return 3
    }
    if (dryRunSummary) {
      return 2
    }
    if (preflightResult?.ok) {
      return 1
    }
    return 0
  }, [dryRunSummary, preflightResult, selectedJob])

  const executeAllowed = Boolean(preflightResult?.ok && dryRunSummary)

  const setFieldErrorsFromProblem = (
    fieldErrors: Record<string, string[]>
  ) => {
    if (Object.keys(fieldErrors).length === 0) {
      return
    }
    form.setFields(
      Object.entries(fieldErrors).map(([name, errors]) => ({ name, errors })) as never
    )
  }

  const resolveScopePayload = async (): Promise<BootstrapScopeFormValues> => {
    const values = await form.validateFields()
    return {
      database_id: values.database_id,
      entity_scope: values.entity_scope,
    }
  }

  const refreshJobsForCurrentDatabase = async () => {
    const currentDatabaseId = form.getFieldValue('database_id')
    await loadJobs(currentDatabaseId)
  }

  const handleRunPreflight = async () => {
    setJobActionError('')
    setRunningPreflight(true)
    try {
      const payload = await resolveScopePayload()
      const response = await runPoolMasterDataBootstrapImportPreflight(payload)
      setPreflightResult(response.preflight)
      setDryRunSummary(null)
      message.success(response.preflight.ok ? 'Preflight успешно пройден.' : 'Preflight завершён с ошибками.')
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось выполнить preflight.')
      setFieldErrorsFromProblem(resolved.fieldErrors)
      setJobActionError(resolved.message)
      message.error(resolved.message)
    } finally {
      setRunningPreflight(false)
    }
  }

  const handleCreateDryRun = async () => {
    if (!preflightResult?.ok) {
      message.error('Сначала выполните успешный preflight.')
      return
    }

    setJobActionError('')
    setRunningDryRun(true)
    try {
      const payload = await resolveScopePayload()
      const response = await createPoolMasterDataBootstrapImportJob({
        ...payload,
        mode: 'dry_run',
      })
      setDryRunSummary(response.job.dry_run_summary || {})
      setSelectedJobId(response.job.id)
      await refreshJobsForCurrentDatabase()
      message.success('Dry-run завершён.')
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось выполнить dry-run.')
      setFieldErrorsFromProblem(resolved.fieldErrors)
      setJobActionError(resolved.message)
      message.error(resolved.message)
    } finally {
      setRunningDryRun(false)
    }
  }

  const handleCreateExecute = async () => {
    if (!executeAllowed) {
      message.error('Execute доступен только после успешных preflight и dry-run.')
      return
    }

    setJobActionError('')
    setRunningExecute(true)
    try {
      const payload = await resolveScopePayload()
      const response = await createPoolMasterDataBootstrapImportJob({
        ...payload,
        mode: 'execute',
      })
      setSelectedJobId(response.job.id)
      await refreshJobsForCurrentDatabase()
      message.success('Execute запущен.')
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось запустить execute.')
      setFieldErrorsFromProblem(resolved.fieldErrors)
      setJobActionError(resolved.message)
      message.error(resolved.message)
    } finally {
      setRunningExecute(false)
    }
  }

  const runJobAction = async (
    action: 'cancel' | 'retry_failed_chunks'
  ) => {
    if (!selectedJob) {
      return
    }
    setRunningJobAction(true)
    setJobActionError('')
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
      setJobActionError(resolved.message)
      message.error(resolved.message)
    } finally {
      setRunningJobAction(false)
    }
  }

  const rowsTotal =
    Number(dryRunSummary?.rows_total || selectedJob?.dry_run_summary?.rows_total || 0) || 0
  const completionPercent = Math.min(
    100,
    Math.max(0, Math.round(Number(selectedJob?.progress?.completion_ratio || 0) * 100))
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
      width: 300,
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

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Steps
          current={currentWizardStep}
          items={[
            { title: 'Scope' },
            { title: 'Preflight' },
            { title: 'Dry-run' },
            { title: 'Execute' },
          ]}
          style={{ marginBottom: 16 }}
        />

        <Form
          form={form}
          layout="vertical"
          initialValues={{ entity_scope: ['party', 'item'] }}
        >
          <Space wrap align="start">
            <Form.Item
              name="database_id"
              label="Database"
              rules={[{ required: true, message: 'Выберите базу.' }]}
              style={{ minWidth: 320, marginBottom: 8 }}
            >
              <Select
                data-testid="bootstrap-import-database-select"
                loading={loadingDatabases}
                placeholder="Select database"
                options={databases.map((database) => ({ value: database.id, label: database.name }))}
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
                options={ENTITY_SCOPE_OPTIONS}
              />
            </Form.Item>
          </Space>
        </Form>

        <Space wrap style={{ marginBottom: 12 }}>
          <Button
            data-testid="bootstrap-import-run-preflight"
            onClick={() => void handleRunPreflight()}
            loading={runningPreflight}
          >
            Run Preflight
          </Button>
          <Button
            data-testid="bootstrap-import-run-dry-run"
            onClick={() => void handleCreateDryRun()}
            loading={runningDryRun}
            disabled={!preflightResult?.ok}
          >
            Run Dry-run
          </Button>
          <Button
            data-testid="bootstrap-import-run-execute"
            type="primary"
            onClick={() => void handleCreateExecute()}
            loading={runningExecute}
            disabled={!executeAllowed}
          >
            Execute
          </Button>
          <Button
            data-testid="bootstrap-import-refresh"
            onClick={() => void refreshJobsForCurrentDatabase()}
            loading={loadingJobs}
          >
            Refresh Jobs
          </Button>
        </Space>

        {!!jobActionError && (
          <Alert
            type="error"
            showIcon
            message={jobActionError}
            style={{ marginBottom: 12 }}
          />
        )}

        {preflightResult && (
          <Alert
            type={preflightResult.ok ? 'success' : 'warning'}
            showIcon
            message={preflightResult.ok ? 'Preflight passed.' : 'Preflight failed.'}
            description={
              preflightResult.errors.length > 0
                ? preflightResult.errors.map((item) => item.detail || item.code).join('; ')
                : 'Source and coverage checks are valid.'
            }
          />
        )}
      </Card>

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
              disabled={!selectedJob || (selectedJob.report.failed_count + selectedJob.report.deferred_count) === 0}
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
            <Space>
              <Tag color={STATUS_COLOR[selectedJob.status] || 'default'}>{selectedJob.status}</Tag>
              <Text type="secondary">Started: {formatDateTime(selectedJob.started_at)}</Text>
              <Text type="secondary">Finished: {formatDateTime(selectedJob.finished_at)}</Text>
            </Space>

            <Progress
              data-testid="bootstrap-import-progress"
              percent={completionPercent}
              status={selectedJob.status === 'failed' ? 'exception' : 'active'}
            />

            <Descriptions size="small" bordered column={3}>
              <Descriptions.Item label="Rows (dry-run)">{rowsTotal}</Descriptions.Item>
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
    </Space>
  )
}
