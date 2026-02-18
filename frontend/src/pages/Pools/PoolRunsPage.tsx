import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Radio,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { UploadOutlined } from '@ant-design/icons'
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from 'reactflow'
import 'reactflow/dist/style.css'

import {
  abortPoolRunPublication,
  confirmPoolRunPublication,
  createPoolRun,
  getPoolGraph,
  getPoolRunReport,
  listOrganizationPools,
  listPoolRuns,
  listPoolSchemaTemplates,
  retryPoolRunFailed,
  type OrganizationPool,
  type PoolGraph,
  type PoolPublicationAttemptDiagnostics,
  type PoolRun,
  type PoolRunReport,
  type PoolRunRetryChainAttempt,
  type PoolRunSafeCommandConflict,
  type PoolRunSafeCommandType,
  type PoolSchemaTemplate,
} from '../../api/intercompanyPools'

const { Title, Text } = Typography
const { TextArea } = Input

type CreateRunFormValues = {
  period_start: string
  period_end?: string
  direction: 'top_down' | 'bottom_up'
  mode: 'safe' | 'unsafe'
  starting_amount?: number
  schema_template_id?: string
  source_payload_json?: string
  source_artifact_id?: string
}

type RetryFormValues = {
  entity_name: string
  max_attempts: number
  retry_interval_seconds: number
  documents_json: string
}

const DEFAULT_RETRY_DOCUMENTS_JSON = JSON.stringify(
  {
    "<database_id>": [{ Amount: '100.00' }],
  },
  null,
  2
)

const DEFAULT_BOTTOM_UP_SOURCE_PAYLOAD_JSON = JSON.stringify(
  [{ inn: '730000000001', amount: '100.00' }],
  null,
  2
)

const CREATE_RUN_PROBLEM_CODE_MESSAGES: Record<string, string> = {
  VALIDATION_ERROR: 'Проверьте корректность параметров запуска.',
  TENANT_CONTEXT_REQUIRED: 'Для запуска run требуется активный tenant context.',
  POOL_NOT_FOUND: 'Пул не найден в текущем tenant context.',
  SCHEMA_TEMPLATE_NOT_FOUND: 'Выбранный schema template недоступен в текущем tenant context.',
  ODATA_MAPPING_NOT_CONFIGURED: 'Для target databases не настроены OData Infobase Users. Проверьте /rbac → Infobase Users.',
  ODATA_MAPPING_AMBIGUOUS: 'Обнаружены неоднозначные OData Infobase Users mappings. Исправьте дубликаты в /rbac → Infobase Users.',
  ODATA_PUBLICATION_AUTH_CONTEXT_INVALID: 'Некорректный publication auth context. Проверьте запуск run и настройки /rbac → Infobase Users.',
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'default',
  validated: 'processing',
  publishing: 'processing',
  published: 'success',
  partial_success: 'warning',
  failed: 'error',
}

const STATUS_REASON_COLORS: Record<string, string> = {
  preparing: 'gold',
  awaiting_approval: 'orange',
  queued: 'blue',
}

const APPROVAL_STATE_COLORS: Record<string, string> = {
  preparing: 'gold',
  awaiting_approval: 'orange',
  approved: 'green',
  not_required: 'cyan',
}

const PUBLICATION_STEP_COLORS: Record<string, string> = {
  not_enqueued: 'default',
  queued: 'blue',
  started: 'processing',
  completed: 'success',
}

const INPUT_CONTRACT_COLORS: Record<string, string> = {
  run_input_v1: 'green',
  legacy_pre_run_input: 'orange',
}

const PUBLICATION_MAPPING_ERROR_CODES = new Set([
  'ODATA_MAPPING_NOT_CONFIGURED',
  'ODATA_MAPPING_AMBIGUOUS',
  'ODATA_PUBLICATION_AUTH_CONTEXT_INVALID',
])

const formatDate = (value: string | null | undefined) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

const formatShortId = (value: string | null | undefined) => {
  if (!value) return '-'
  return value.slice(0, 8)
}

const getStatusColor = (status: string) => STATUS_COLORS[status] ?? 'default'
const getStatusReasonColor = (statusReason: string) => STATUS_REASON_COLORS[statusReason] ?? 'default'
const getApprovalStateColor = (approvalState: string) => APPROVAL_STATE_COLORS[approvalState] ?? 'default'
const getPublicationStepColor = (stepState: string) => PUBLICATION_STEP_COLORS[stepState] ?? 'default'
const getInputContractColor = (contractVersion: string) => INPUT_CONTRACT_COLORS[contractVersion] ?? 'default'
const getWorkflowAttemptKindColor = (attemptKind: string) => (
  attemptKind === 'initial' ? 'blue' : attemptKind === 'retry' ? 'cyan' : 'default'
)
const getWorkflowExecutionStatusColor = (status: string) => (
  status === 'completed'
    ? 'success'
    : status === 'failed' || status === 'cancelled'
      ? 'error'
      : 'processing'
)

const parseDocumentsPayload = (raw: string): Record<string, Array<Record<string, unknown>>> => {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error('documents_by_database: invalid JSON')
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('documents_by_database: object expected')
  }

  const asObject = parsed as Record<string, unknown>
  const result: Record<string, Array<Record<string, unknown>>> = {}
  for (const [databaseId, rows] of Object.entries(asObject)) {
    if (!Array.isArray(rows)) {
      throw new Error(`documents_by_database.${databaseId}: array expected`)
    }
    result[databaseId] = rows.map((item) => {
      if (!item || typeof item !== 'object' || Array.isArray(item)) {
        throw new Error(`documents_by_database.${databaseId}: object rows expected`)
      }
      return item as Record<string, unknown>
    })
  }
  return result
}

const parseBottomUpSourcePayload = (raw: string): Record<string, unknown> | Array<Record<string, unknown>> => {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error('source_payload: invalid JSON')
  }
  if (!parsed || (typeof parsed !== 'object' && !Array.isArray(parsed))) {
    throw new Error('source_payload: object or array expected')
  }
  if (!Array.isArray(parsed)) {
    return parsed as Record<string, unknown>
  }
  return parsed.map((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      throw new Error('source_payload: array items must be objects')
    }
    return item as Record<string, unknown>
  })
}

type ProblemDetailsPayload = {
  code: string | null
  detail: string | null
  title: string | null
  status: number | null
}

const parseProblemDetails = (error: unknown): ProblemDetailsPayload | null => {
  if (!error || typeof error !== 'object') return null
  const response = (error as { response?: { data?: unknown } }).response
  const payload = response?.data
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return null
  }
  const candidate = payload as {
    code?: unknown
    detail?: unknown
    title?: unknown
    status?: unknown
  }
  const hasKnownShape = (
    typeof candidate.code === 'string'
    || typeof candidate.detail === 'string'
    || typeof candidate.title === 'string'
    || typeof candidate.status === 'number'
  )
  if (!hasKnownShape) {
    return null
  }
  return {
    code: typeof candidate.code === 'string' ? candidate.code.trim() : null,
    detail: typeof candidate.detail === 'string' ? candidate.detail.trim() : null,
    title: typeof candidate.title === 'string' ? candidate.title.trim() : null,
    status: typeof candidate.status === 'number' ? candidate.status : null,
  }
}

const resolveCreateRunProblemMessage = (
  problem: ProblemDetailsPayload,
  fallbackMessage: string
): string => {
  const codeMessage = problem.code ? CREATE_RUN_PROBLEM_CODE_MESSAGES[problem.code] : undefined
  if (codeMessage) {
    return codeMessage
  }
  if (problem.detail && problem.detail.length > 0) {
    return problem.detail
  }
  if (problem.title && problem.title.length > 0) {
    return problem.title
  }
  return fallbackMessage
}

const resolveInputContractVersion = (run: PoolRun): string => {
  if (run.input_contract_version) {
    return run.input_contract_version
  }
  return run.run_input ? 'run_input_v1' : 'legacy_pre_run_input'
}

const summarizeRunInput = (run: PoolRun): string => {
  if (!run.run_input || typeof run.run_input !== 'object') {
    return 'null'
  }
  const keys = Object.keys(run.run_input)
  if (keys.length === 0) {
    return '{}'
  }
  const preview = keys.slice(0, 2).join(', ')
  return keys.length > 2 ? `${preview}, +${keys.length - 2}` : preview
}

const buildFlowLayout = (graph: PoolGraph | null): { nodes: Node[]; edges: Edge[] } => {
  if (!graph) {
    return { nodes: [], edges: [] }
  }
  const depthByNodeId = new Map<string, number>()
  for (const node of graph.nodes) {
    if (node.is_root) {
      depthByNodeId.set(node.node_version_id, 0)
    }
  }
  for (let i = 0; i < graph.nodes.length; i += 1) {
    let changed = false
    for (const edge of graph.edges) {
      const parentDepth = depthByNodeId.get(edge.parent_node_version_id)
      if (parentDepth === undefined) continue
      const nextDepth = parentDepth + 1
      const currentDepth = depthByNodeId.get(edge.child_node_version_id)
      if (currentDepth === undefined || nextDepth > currentDepth) {
        depthByNodeId.set(edge.child_node_version_id, nextDepth)
        changed = true
      }
    }
    if (!changed) break
  }

  const groupedByDepth = new Map<number, typeof graph.nodes>()
  for (const node of graph.nodes) {
    const depth = depthByNodeId.get(node.node_version_id) ?? 0
    const current = groupedByDepth.get(depth) ?? []
    current.push(node)
    groupedByDepth.set(depth, current)
  }

  const flowNodes: Node[] = []
  for (const [depth, nodesInDepth] of groupedByDepth.entries()) {
    nodesInDepth.forEach((node, index) => {
      flowNodes.push({
        id: node.node_version_id,
        position: { x: depth * 260, y: index * 110 },
        data: { label: `${node.name}\n${node.inn}` },
        style: {
          border: node.is_root ? '2px solid #1890ff' : '1px solid #d9d9d9',
          borderRadius: 8,
          padding: 8,
          width: 220,
          background: '#fff',
          fontSize: 12,
          whiteSpace: 'pre-line',
        },
      })
    })
  }

  const flowEdges: Edge[] = graph.edges.map((edge) => ({
    id: edge.edge_version_id,
    source: edge.parent_node_version_id,
    target: edge.child_node_version_id,
    label: `w=${edge.weight}`,
    animated: false,
  }))

  return { nodes: flowNodes, edges: flowEdges }
}

const generateIdempotencyKey = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `pool-safe-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const parseSafeCommandConflict = (error: unknown): PoolRunSafeCommandConflict | null => {
  if (!error || typeof error !== 'object') return null
  const response = (error as { response?: { data?: unknown } }).response
  const payload = response?.data
  if (!payload || typeof payload !== 'object') return null

  const candidate = payload as Partial<PoolRunSafeCommandConflict>
  if (
    typeof candidate.error_code === 'string'
    && typeof candidate.error_message === 'string'
    && typeof candidate.conflict_reason === 'string'
  ) {
    return {
      success: Boolean(candidate.success),
      error_code: candidate.error_code,
      error_message: candidate.error_message,
      conflict_reason: candidate.conflict_reason,
      retryable: Boolean(candidate.retryable),
      run_id: String(candidate.run_id ?? ''),
    }
  }
  return null
}

export function PoolRunsPage() {
  const { message } = AntApp.useApp()
  const [pools, setPools] = useState<OrganizationPool[]>([])
  const [schemaTemplates, setSchemaTemplates] = useState<PoolSchemaTemplate[]>([])
  const [selectedPoolId, setSelectedPoolId] = useState<string | null>(null)
  const [graphDate, setGraphDate] = useState<string>(new Date().toISOString().slice(0, 10))
  const [graph, setGraph] = useState<PoolGraph | null>(null)
  const [runs, setRuns] = useState<PoolRun[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [report, setReport] = useState<PoolRunReport | null>(null)
  const [loadingPools, setLoadingPools] = useState(false)
  const [loadingSchemaTemplates, setLoadingSchemaTemplates] = useState(false)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [loadingRuns, setLoadingRuns] = useState(false)
  const [loadingReport, setLoadingReport] = useState(false)
  const [creatingRun, setCreatingRun] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [safeActionLoading, setSafeActionLoading] = useState<PoolRunSafeCommandType | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [createForm] = Form.useForm<CreateRunFormValues>()
  const [retryForm] = Form.useForm<RetryFormValues>()

  const selectedRun = useMemo(
    () => runs.find((item) => item.id === selectedRunId) ?? null,
    [runs, selectedRunId]
  )

  const runDetails = useMemo(() => {
    if (report?.run && report.run.id === selectedRunId) {
      return report.run
    }
    return selectedRun
  }, [report, selectedRun, selectedRunId])

  const flow = useMemo(() => buildFlowLayout(graph), [graph])
  const createDirection = Form.useWatch('direction', createForm) ?? 'top_down'

  const loadPools = useCallback(async () => {
    setLoadingPools(true)
    setError(null)
    try {
      const data = await listOrganizationPools()
      setPools(data)
      if (!selectedPoolId && data.length > 0) {
        setSelectedPoolId(data[0].id)
      }
    } catch {
      setError('Не удалось загрузить список пулов.')
    } finally {
      setLoadingPools(false)
    }
  }, [selectedPoolId])

  const loadSchemaTemplates = useCallback(async () => {
    setLoadingSchemaTemplates(true)
    try {
      const data = await listPoolSchemaTemplates({ isPublic: true, isActive: true })
      setSchemaTemplates(data)
    } catch {
      setError('Не удалось загрузить шаблоны импорта.')
    } finally {
      setLoadingSchemaTemplates(false)
    }
  }, [])

  const loadGraph = useCallback(async () => {
    if (!selectedPoolId) {
      setGraph(null)
      return
    }
    setLoadingGraph(true)
    try {
      const data = await getPoolGraph(selectedPoolId, graphDate || undefined)
      setGraph(data)
    } catch {
      setError('Не удалось загрузить граф пула.')
    } finally {
      setLoadingGraph(false)
    }
  }, [graphDate, selectedPoolId])

  const loadRuns = useCallback(async () => {
    if (!selectedPoolId) {
      setRuns([])
      setSelectedRunId(null)
      return
    }
    setLoadingRuns(true)
    try {
      const data = await listPoolRuns({ poolId: selectedPoolId, limit: 100 })
      setRuns(data)
      if (data.length === 0) {
        setSelectedRunId(null)
        return
      }
      if (!selectedRunId || !data.some((item) => item.id === selectedRunId)) {
        setSelectedRunId(data[0].id)
      }
    } catch {
      setError('Не удалось загрузить список run.')
    } finally {
      setLoadingRuns(false)
    }
  }, [selectedPoolId, selectedRunId])

  const loadReport = useCallback(async () => {
    if (!selectedRunId) {
      setReport(null)
      return
    }
    setLoadingReport(true)
    try {
      const data = await getPoolRunReport(selectedRunId)
      setReport(data)
    } catch {
      setError('Не удалось загрузить run report.')
    } finally {
      setLoadingReport(false)
    }
  }, [selectedRunId])

  useEffect(() => {
    void loadPools()
    void loadSchemaTemplates()
  }, [loadPools, loadSchemaTemplates])

  useEffect(() => {
    void loadGraph()
    void loadRuns()
  }, [loadGraph, loadRuns])

  useEffect(() => {
    void loadReport()
  }, [loadReport])

  useEffect(() => {
    createForm.setFieldsValue({
      period_start: new Date().toISOString().slice(0, 10),
      period_end: '',
      direction: 'top_down',
      mode: 'safe',
      starting_amount: 100,
      schema_template_id: undefined,
      source_payload_json: DEFAULT_BOTTOM_UP_SOURCE_PAYLOAD_JSON,
      source_artifact_id: '',
    })
    retryForm.setFieldsValue({
      entity_name: 'Document_РеализацияТоваровУслуг',
      max_attempts: 5,
      retry_interval_seconds: 0,
      documents_json: DEFAULT_RETRY_DOCUMENTS_JSON,
    })
  }, [createForm, retryForm])

  const handleCreateRun = useCallback(async () => {
    if (!selectedPoolId) {
      setError('Выберите пул перед созданием run.')
      return
    }
    let values: CreateRunFormValues
    let direction: CreateRunFormValues['direction'] = 'top_down'
    try {
      values = await createForm.validateFields()
      direction = values.direction
    } catch {
      return
    }

    setCreatingRun(true)
    setError(null)
    try {
      const runInput: Record<string, unknown> = {}
      let schemaTemplateId: string | null | undefined = undefined

      if (direction === 'top_down') {
        const startingAmount = Number(values.starting_amount)
        if (!Number.isFinite(startingAmount) || startingAmount <= 0) {
          setError('top_down: starting amount должен быть положительным числом.')
          return
        }
        runInput.starting_amount = startingAmount.toFixed(2)
      } else {
        const artifactId = values.source_artifact_id?.trim()
        const sourcePayloadRaw = values.source_payload_json?.trim() || ''
        if (sourcePayloadRaw.length > 0) {
          runInput.source_payload = parseBottomUpSourcePayload(sourcePayloadRaw)
        }
        if (artifactId) {
          runInput.source_artifact_id = artifactId
        }
        if (!Object.prototype.hasOwnProperty.call(runInput, 'source_payload') && !artifactId) {
          setError('bottom_up: укажите source payload JSON или source artifact ID.')
          return
        }
        schemaTemplateId = values.schema_template_id?.trim() || null
      }

      const payload = await createPoolRun({
        pool_id: selectedPoolId,
        direction,
        period_start: values.period_start,
        period_end: values.period_end?.trim() || null,
        run_input: runInput,
        mode: values.mode,
        schema_template_id: schemaTemplateId,
      })
      message.success(payload.created ? 'Run создан' : 'Run переиспользован по idempotency key')
      await loadRuns()
      setSelectedRunId(payload.run.id)
    } catch (err) {
      const problem = parseProblemDetails(err)
      if (problem) {
        if (problem.code === 'VALIDATION_ERROR' && problem.detail) {
          const normalizedDetail = problem.detail.toLowerCase()
          const fieldErrors: Array<{ name: keyof CreateRunFormValues; errors: string[] }> = []

          if (direction === 'top_down' && normalizedDetail.includes('starting_amount')) {
            fieldErrors.push({ name: 'starting_amount', errors: [problem.detail] })
          }
          if (
            direction === 'bottom_up'
            && (
              normalizedDetail.includes('source_payload')
              || normalizedDetail.includes('source_artifact_id')
              || normalizedDetail.includes('bottom_up run_input')
            )
          ) {
            fieldErrors.push({ name: 'source_payload_json', errors: [problem.detail] })
            fieldErrors.push({ name: 'source_artifact_id', errors: [problem.detail] })
          }
          if (normalizedDetail.includes('schema_template')) {
            fieldErrors.push({ name: 'schema_template_id', errors: [problem.detail] })
          }

          if (fieldErrors.length > 0) {
            createForm.setFields(fieldErrors)
          }
        }
        setError(resolveCreateRunProblemMessage(problem, 'Не удалось создать run.'))
      } else if (err instanceof Error && err.message) {
        setError(err.message)
      } else {
        setError('Не удалось создать run.')
      }
    } finally {
      setCreatingRun(false)
    }
  }, [createForm, loadRuns, message, selectedPoolId])

  const handleRetryFailed = useCallback(async () => {
    if (!selectedRunId) {
      setError('Выберите run для retry.')
      return
    }
    let values: RetryFormValues
    try {
      values = await retryForm.validateFields()
    } catch {
      return
    }
    let documentsByDatabase: Record<string, Array<Record<string, unknown>>>
    try {
      documentsByDatabase = parseDocumentsPayload(values.documents_json)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Некорректный payload для retry.')
      return
    }

    setRetrying(true)
    setError(null)
    try {
      const idempotencyKey = generateIdempotencyKey()
      const response = await retryPoolRunFailed(selectedRunId, {
        entity_name: values.entity_name,
        max_attempts: values.max_attempts,
        retry_interval_seconds: values.retry_interval_seconds,
        documents_by_database: documentsByDatabase,
      }, idempotencyKey)
      const summary = response.retry_target_summary
      const enqueuedTargets = summary?.enqueued_targets ?? 0
      const failedTargets = summary?.failed_targets ?? 0
      if (response.accepted) {
        message.success(`Retry accepted: ${enqueuedTargets}/${failedTargets} failed targets enqueued`)
      } else {
        message.warning('Retry request was not accepted by workflow runtime.')
      }
      await loadRuns()
      await loadReport()
    } catch (err) {
      const conflict = parseSafeCommandConflict(err)
      if (conflict) {
        setError(`${conflict.error_message} (${conflict.conflict_reason})`)
      } else {
        setError('Retry завершился ошибкой.')
      }
    } finally {
      setRetrying(false)
    }
  }, [loadReport, loadRuns, message, retryForm, selectedRunId])

  const handleSafeCommand = useCallback(async (commandType: PoolRunSafeCommandType) => {
    if (!selectedRunId || !runDetails) {
      setError('Выберите safe run для команды публикации.')
      return
    }
    if (runDetails.mode !== 'safe') {
      setError('Команды confirm/abort доступны только для safe run.')
      return
    }

    const idempotencyKey = generateIdempotencyKey()
    setSafeActionLoading(commandType)
    setError(null)
    try {
      const response = commandType === 'confirm-publication'
        ? await confirmPoolRunPublication(selectedRunId, idempotencyKey)
        : await abortPoolRunPublication(selectedRunId, idempotencyKey)
      const commandLabel = commandType === 'confirm-publication' ? 'Confirm publication' : 'Abort publication'
      if (response.result === 'accepted') {
        message.success(`${commandLabel}: accepted`)
      } else {
        message.info(`${commandLabel}: idempotent replay`)
      }
      await loadRuns()
      await loadReport()
      setSelectedRunId(response.run.id)
    } catch (err) {
      const conflict = parseSafeCommandConflict(err)
      if (conflict) {
        setError(`${conflict.error_message} (${conflict.conflict_reason})`)
      } else {
        setError(
          commandType === 'confirm-publication'
            ? 'Не удалось выполнить confirm-publication.'
            : 'Не удалось выполнить abort-publication.'
        )
      }
    } finally {
      setSafeActionLoading(null)
    }
  }, [loadReport, loadRuns, message, runDetails, selectedRunId])

  const runColumns: ColumnsType<PoolRun> = useMemo(
    () => [
      {
        title: 'Run',
        dataIndex: 'id',
        key: 'id',
        width: 220,
        render: (value: string, record) => (
          <Space size={4} wrap>
            <Text code>{formatShortId(value)}</Text>
            <Tag color={record.mode === 'safe' ? 'geekblue' : 'default'}>{record.mode}</Tag>
          </Space>
        ),
      },
      {
        title: 'Status',
        dataIndex: 'status',
        key: 'status',
        width: 220,
        render: (_value, record) => (
          <Space size={4} wrap>
            <Tag color={getStatusColor(record.status)}>{record.status}</Tag>
            {record.status_reason && (
              <Tag color={getStatusReasonColor(record.status_reason)}>{record.status_reason}</Tag>
            )}
          </Space>
        ),
      },
      {
        title: 'Approval',
        key: 'approval',
        width: 220,
        render: (_value, record) => (
          <Space size={4} wrap>
            {record.approval_state ? (
              <Tag color={getApprovalStateColor(record.approval_state)}>{record.approval_state}</Tag>
            ) : (
              <Tag>n/a</Tag>
            )}
            {record.publication_step_state ? (
              <Tag color={getPublicationStepColor(record.publication_step_state)}>{record.publication_step_state}</Tag>
            ) : null}
          </Space>
        ),
      },
      {
        title: 'Workflow',
        key: 'workflow',
        width: 240,
        render: (_value, record) => {
          const workflowRunId = record.provenance?.workflow_run_id ?? record.workflow_execution_id
          const workflowStatus = record.provenance?.workflow_status ?? record.workflow_status
          const executionBackend = record.provenance?.execution_backend ?? record.execution_backend
          return (
            <Space direction="vertical" size={2}>
              <Text code>{formatShortId(workflowRunId)}</Text>
              <Space size={4} wrap>
                {workflowStatus ? <Tag color="processing">{workflowStatus}</Tag> : <Tag>legacy</Tag>}
                {executionBackend ? <Tag>{executionBackend}</Tag> : null}
              </Space>
            </Space>
          )
        },
      },
      {
        title: 'Input',
        key: 'input',
        width: 220,
        render: (_value, record) => {
          const contractVersion = resolveInputContractVersion(record)
          return (
            <Space direction="vertical" size={2}>
              <Tag color={getInputContractColor(contractVersion)}>{contractVersion}</Tag>
              <Text type="secondary">{summarizeRunInput(record)}</Text>
            </Space>
          )
        },
      },
      {
        title: 'Period',
        key: 'period',
        render: (_value, record) => `${record.period_start}${record.period_end ? `..${record.period_end}` : ''}`,
      },
      {
        title: 'Updated',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 190,
        render: (value: string) => formatDate(value),
      },
    ],
    []
  )

  const publicationAttemptColumns: ColumnsType<PoolPublicationAttemptDiagnostics> = useMemo(
    () => [
      {
        title: 'Target DB',
        dataIndex: 'target_database_id',
        key: 'target_database_id',
        width: 180,
        render: (value: string) => <Text code>{formatShortId(value)}</Text>,
      },
      {
        title: 'Status',
        dataIndex: 'status',
        key: 'status',
        width: 130,
        render: (value: string) => (
          <Tag color={value === 'success' ? 'success' : value === 'failed' ? 'error' : 'processing'}>
            {value}
          </Tag>
        ),
      },
      {
        title: 'Attempt',
        dataIndex: 'attempt_number',
        key: 'attempt_number',
        width: 90,
      },
      {
        title: 'Timestamp',
        dataIndex: 'attempt_timestamp',
        key: 'attempt_timestamp',
        width: 180,
        render: (value?: string) => formatDate(value ?? null),
      },
      {
        title: 'Identity',
        key: 'identity',
        width: 220,
        render: (_value, record) => (
          <Space direction="vertical" size={0}>
            <Text>{record.publication_identity_strategy || record.identity_strategy || '-'}</Text>
            <Text type="secondary">{record.external_document_identity || '-'}</Text>
          </Space>
        ),
      },
      {
        title: 'Error',
        key: 'error',
        render: (_value, record) => {
          const code = record.domain_error_code || record.error_code || '-'
          const messageText = record.domain_error_message || record.error_message || '-'
          const httpStatusValue = record.http_error?.status ?? record.http_status
          const transportMessage = record.transport_error?.message ?? null
          return (
            <Space direction="vertical" size={0}>
              <Text>{code}</Text>
              <Text type="secondary">{messageText}</Text>
              {PUBLICATION_MAPPING_ERROR_CODES.has(code) ? (
                <Text type="secondary">Remediation: /rbac - Infobase Users</Text>
              ) : null}
              {httpStatusValue ? <Text type="secondary">HTTP {httpStatusValue}</Text> : null}
              {transportMessage ? <Text type="secondary">{transportMessage}</Text> : null}
            </Space>
          )
        },
      },
    ],
    []
  )

  const workflowRunId = runDetails?.provenance?.workflow_run_id ?? runDetails?.workflow_execution_id ?? null
  const workflowStatus = runDetails?.provenance?.workflow_status ?? runDetails?.workflow_status ?? null
  const executionBackend = runDetails?.provenance?.execution_backend ?? runDetails?.execution_backend ?? null
  const retryChain = runDetails?.provenance?.retry_chain ?? []

  const isSafeRun = runDetails?.mode === 'safe'
  const isPublishedOrPartial = runDetails?.status === 'published' || runDetails?.status === 'partial_success'
  const isTerminalNonAbortFailed = runDetails?.status === 'failed' && runDetails?.terminal_reason !== 'aborted_by_operator'
  const isSafePrePublishPreparing = isSafeRun && runDetails?.approval_state === 'preparing'
  const canConfirm = Boolean(
    isSafeRun
    && runDetails
    && runDetails.approval_state === 'awaiting_approval'
    && !isPublishedOrPartial
    && runDetails.status !== 'failed'
  )
  const canAbort = Boolean(
    isSafeRun
    && runDetails
    && runDetails.approval_state !== 'not_required'
    && !isPublishedOrPartial
    && !isTerminalNonAbortFailed
  )

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ marginBottom: 0 }}>
          Pool Runs
        </Title>
        <Text type="secondary">
          Единая модель статусов/provenance для run, прозрачная диагностика workflow и safe-команды.
        </Text>
      </div>

      {error && <Alert type="error" message={error} />}

      <Card title="Create / Refresh Run" loading={loadingPools}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space wrap>
            <Select
              style={{ width: 320 }}
              placeholder="Select pool"
              value={selectedPoolId ?? undefined}
              options={pools.map((pool) => ({
                value: pool.id,
                label: `${pool.code} - ${pool.name}`,
              }))}
              onChange={(value) => setSelectedPoolId(value)}
            />
            <Input
              type="date"
              value={graphDate}
              onChange={(event) => setGraphDate(event.target.value)}
              style={{ width: 180 }}
            />
            <Button onClick={() => { void loadGraph(); void loadRuns() }} loading={loadingGraph || loadingRuns}>
              Refresh Data
            </Button>
          </Space>

          <Form form={createForm} layout="vertical">
            <Alert
              type="info"
              showIcon
              message="Pool publication OData credentials source: /rbac"
              description="`odata_url` берётся из Databases, а OData user/password для публикации — из /rbac → Infobase Users (actor/service mapping)."
              style={{ marginBottom: 12 }}
            />
            <Row gutter={12}>
              <Col span={5}>
                <Form.Item name="period_start" label="Period start" rules={[{ required: true }]}>
                  <Input type="date" />
                </Form.Item>
              </Col>
              <Col span={5}>
                <Form.Item name="period_end" label="Period end">
                  <Input type="date" />
                </Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name="direction" label="Direction" rules={[{ required: true }]}>
                  <Radio.Group data-testid="pool-runs-create-direction" optionType="button" buttonStyle="solid">
                    <Radio.Button value="top_down">top_down</Radio.Button>
                    <Radio.Button value="bottom_up">bottom_up</Radio.Button>
                  </Radio.Group>
                </Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name="mode" label="Mode" rules={[{ required: true }]}>
                  <Select
                    options={[
                      { value: 'safe', label: 'safe' },
                      { value: 'unsafe', label: 'unsafe' },
                    ]}
                  />
                </Form.Item>
              </Col>
              <Col span={6}>
                {createDirection === 'top_down' ? (
                  <Form.Item
                    name="starting_amount"
                    label="Starting amount"
                    rules={[
                      { required: true, message: 'starting_amount required' },
                      {
                        validator: async (_rule, value) => {
                          if (value == null || Number(value) <= 0) {
                            throw new Error('starting_amount must be > 0')
                          }
                        },
                      },
                    ]}
                  >
                    <InputNumber data-testid="pool-runs-create-starting-amount" min={0.01} step={0.01} style={{ width: '100%' }} />
                  </Form.Item>
                ) : (
                  <Form.Item name="schema_template_id" label="Schema template">
                    <Select
                      data-testid="pool-runs-create-schema-template"
                      allowClear
                      loading={loadingSchemaTemplates}
                      placeholder="Optional template"
                      options={schemaTemplates.map((item) => ({
                        value: item.id,
                        label: `${item.code} - ${item.name}`,
                      }))}
                    />
                  </Form.Item>
                )}
              </Col>
            </Row>

            {createDirection === 'bottom_up' && (
              <Row gutter={12}>
                <Col span={16}>
                  <Form.Item name="source_payload_json" label="Source payload JSON">
                    <Input.TextArea data-testid="pool-runs-create-source-payload" rows={6} placeholder='[{"inn":"730000000001","amount":"100.00"}]' />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="source_artifact_id" label="Source artifact ID">
                    <Input data-testid="pool-runs-create-source-artifact" placeholder="artifact://..." />
                  </Form.Item>
                  <Upload
                    accept=".json,application/json,text/plain"
                    maxCount={1}
                    showUploadList={false}
                    beforeUpload={async (file) => {
                      try {
                        const text = await file.text()
                        createForm.setFieldValue('source_payload_json', text)
                        message.success('Source payload loaded from file.')
                      } catch {
                        message.error('Не удалось прочитать выбранный файл.')
                      }
                      return false
                    }}
                  >
                    <Button icon={<UploadOutlined />}>Load payload file</Button>
                  </Upload>
                </Col>
              </Row>
            )}

            <Button type="primary" loading={creatingRun} onClick={() => void handleCreateRun()} data-testid="pool-runs-create-submit">
              Create / Upsert Run
            </Button>
          </Form>
        </Space>
      </Card>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="Pool Graph" loading={loadingGraph}>
            <div style={{ height: 460 }}>
              <ReactFlow nodes={flow.nodes} edges={flow.edges} fitView>
                <MiniMap />
                <Controls />
                <Background />
              </ReactFlow>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Runs" loading={loadingRuns}>
            <Table
              rowKey="id"
              size="small"
              columns={runColumns}
              dataSource={runs}
              pagination={{ pageSize: 8 }}
              rowSelection={{
                type: 'radio',
                selectedRowKeys: selectedRunId ? [selectedRunId] : [],
                onChange: (keys) => setSelectedRunId(keys[0] ? String(keys[0]) : null),
              }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Execution Provenance / Report" loading={loadingReport}>
        {!runDetails && (
          <Text type="secondary">Select a run to inspect report.</Text>
        )}
        {runDetails && report && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Space size="small" wrap>
              <Tag color="blue">run: {formatShortId(runDetails.id)}</Tag>
              <Tag color={getStatusColor(runDetails.status)}>{runDetails.status}</Tag>
              {runDetails.status_reason && <Tag color={getStatusReasonColor(runDetails.status_reason)}>{runDetails.status_reason}</Tag>}
              <Tag>attempts: {report.publication_attempts.length}</Tag>
              {Object.entries(report.attempts_by_status ?? {}).map(([status, count]) => (
                <Tag key={status}>{status}: {count}</Tag>
              ))}
            </Space>

            <Descriptions bordered size="small" column={2}>
              <Descriptions.Item label="Workflow Run" span={1}>
                <Text code data-testid="pool-runs-provenance-workflow-id">{workflowRunId ?? '-'}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Workflow Status" span={1}>
                {workflowStatus ? <Tag color="processing">{workflowStatus}</Tag> : <Text type="secondary">legacy</Text>}
              </Descriptions.Item>
              <Descriptions.Item label="Execution Backend" span={1}>
                <Text>{executionBackend ?? '-'}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Workflow Template" span={1}>
                <Text>{runDetails.workflow_template_name ?? '-'}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Input Contract" span={1}>
                <Tag color={getInputContractColor(resolveInputContractVersion(runDetails))}>
                  {resolveInputContractVersion(runDetails)}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Run Input" span={1}>
                <Text>{summarizeRunInput(runDetails)}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Approval State" span={1}>
                {runDetails.approval_state ? (
                  <Tag color={getApprovalStateColor(runDetails.approval_state)}>{runDetails.approval_state}</Tag>
                ) : (
                  <Text type="secondary">n/a</Text>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="Publication Step" span={1}>
                {runDetails.publication_step_state ? (
                  <Tag color={getPublicationStepColor(runDetails.publication_step_state)}>{runDetails.publication_step_state}</Tag>
                ) : (
                  <Text type="secondary">n/a</Text>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="Terminal Reason" span={2}>
                <Text>{runDetails.terminal_reason ?? '-'}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Retry Chain" span={2}>
                {retryChain.length > 0 ? (
                  <Space direction="vertical" size={4}>
                    {retryChain.map((item: PoolRunRetryChainAttempt) => (
                      <Space key={item.workflow_run_id} size={4} wrap>
                        <Tag color={getWorkflowAttemptKindColor(item.attempt_kind)}>
                          #{item.attempt_number} {item.attempt_kind}
                        </Tag>
                        <Tag color={getWorkflowExecutionStatusColor(item.status)}>{item.status}</Tag>
                        <Text code>{formatShortId(item.workflow_run_id)}</Text>
                        {item.parent_workflow_run_id ? (
                          <Text type="secondary">parent: {formatShortId(item.parent_workflow_run_id)}</Text>
                        ) : (
                          <Text type="secondary">root</Text>
                        )}
                      </Space>
                    ))}
                  </Space>
                ) : (
                  <Text type="secondary">empty</Text>
                )}
              </Descriptions.Item>
            </Descriptions>

            <Text strong>Run Input</Text>
            <TextArea
              data-testid="pool-runs-run-input"
              readOnly
              rows={6}
              value={JSON.stringify(runDetails.run_input ?? null, null, 2)}
            />

            <Text strong>Publication Attempts</Text>
            <Table
              rowKey="id"
              size="small"
              columns={publicationAttemptColumns}
              dataSource={report.publication_attempts}
              pagination={{ pageSize: 5 }}
            />

            <Text strong>Validation Summary</Text>
            <TextArea readOnly rows={4} value={JSON.stringify(report.validation_summary ?? {}, null, 2)} />
            <Text strong>Publication Summary</Text>
            <TextArea readOnly rows={4} value={JSON.stringify(report.publication_summary ?? {}, null, 2)} />
            <Text strong>Step Diagnostics</Text>
            <TextArea readOnly rows={6} value={JSON.stringify(report.diagnostics ?? [], null, 2)} />
          </Space>
        )}
      </Card>

      <Card
        title="Safe Mode Actions"
        extra={<Text type="secondary">`Idempotency-Key` генерируется автоматически на каждый action.</Text>}
      >
        {!runDetails && <Text type="secondary">Выберите run для управления safe-публикацией.</Text>}
        {runDetails && runDetails.mode !== 'safe' && (
          <Alert type="info" showIcon message="Этот run создан в unsafe режиме: confirm/abort недоступны." />
        )}
        {runDetails && runDetails.mode === 'safe' && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Space wrap>
              <Tag color="geekblue">safe</Tag>
              {runDetails.status_reason ? <Tag color={getStatusReasonColor(runDetails.status_reason)}>{runDetails.status_reason}</Tag> : null}
              {runDetails.approval_state ? <Tag color={getApprovalStateColor(runDetails.approval_state)}>{runDetails.approval_state}</Tag> : null}
              {runDetails.publication_step_state ? <Tag color={getPublicationStepColor(runDetails.publication_step_state)}>{runDetails.publication_step_state}</Tag> : null}
            </Space>
            {isSafePrePublishPreparing && (
              <Alert
                type="info"
                showIcon
                message="Pre-publish ещё выполняется"
                description="Safe run находится на этапе предпросмотра. Дождитесь состояния awaiting_approval, затем станет доступен Confirm publication."
              />
            )}
            <Text type="secondary">
              `preparing` — выполняется pre-publish (prepare/distribution/reconciliation/approval_gate).
              `awaiting_approval` — pre-publish завершён и run ждёт ручного подтверждения.
              Результаты предпросмотра смотрите выше: Validation Summary / Publication Summary / Step Diagnostics.
            </Text>
            <Space>
              <Button
                type="primary"
                data-testid="pool-runs-safe-confirm"
                loading={safeActionLoading === 'confirm-publication'}
                title={isSafePrePublishPreparing ? 'Доступно после завершения pre-publish (awaiting_approval)' : undefined}
                disabled={!canConfirm}
                onClick={() => void handleSafeCommand('confirm-publication')}
              >
                Confirm publication
              </Button>
              <Button
                danger
                data-testid="pool-runs-safe-abort"
                loading={safeActionLoading === 'abort-publication'}
                disabled={!canAbort}
                onClick={() => void handleSafeCommand('abort-publication')}
              >
                Abort publication
              </Button>
            </Space>
          </Space>
        )}
      </Card>

      <Card title="Retry Failed Targets">
        <Form form={retryForm} layout="vertical">
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="entity_name" label="Entity Name" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="max_attempts" label="Max Attempts" rules={[{ required: true }]}>
                <InputNumber min={1} max={5} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="retry_interval_seconds" label="Retry Interval (sec)" rules={[{ required: true }]}>
                <InputNumber min={0} max={120} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="documents_json" label="documents_by_database JSON" rules={[{ required: true }]}>
            <TextArea rows={8} />
          </Form.Item>
          <Button type="primary" loading={retrying} onClick={() => void handleRetryFailed()} disabled={!selectedRunId}>
            Retry Failed
          </Button>
        </Form>
      </Card>
    </Space>
  )
}
