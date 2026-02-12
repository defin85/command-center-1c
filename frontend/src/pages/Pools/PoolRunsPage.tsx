import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from 'reactflow'
import 'reactflow/dist/style.css'

import {
  createPoolRun,
  getPoolGraph,
  getPoolRunReport,
  listOrganizationPools,
  listPoolRuns,
  retryPoolRunFailed,
  type OrganizationPool,
  type PoolGraph,
  type PoolRun,
  type PoolRunReport,
} from '../../api/intercompanyPools'

const { Title, Text } = Typography
const { TextArea } = Input

type CreateRunFormValues = {
  period_start: string
  period_end?: string
  direction: 'top_down' | 'bottom_up'
  mode: 'safe' | 'unsafe'
  source_hash: string
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

const formatDate = (value: string | null | undefined) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

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

export function PoolRunsPage() {
  const { message } = AntApp.useApp()
  const [pools, setPools] = useState<OrganizationPool[]>([])
  const [selectedPoolId, setSelectedPoolId] = useState<string | null>(null)
  const [graphDate, setGraphDate] = useState<string>(new Date().toISOString().slice(0, 10))
  const [graph, setGraph] = useState<PoolGraph | null>(null)
  const [runs, setRuns] = useState<PoolRun[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [report, setReport] = useState<PoolRunReport | null>(null)
  const [loadingPools, setLoadingPools] = useState(false)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [loadingRuns, setLoadingRuns] = useState(false)
  const [loadingReport, setLoadingReport] = useState(false)
  const [creatingRun, setCreatingRun] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [createForm] = Form.useForm<CreateRunFormValues>()
  const [retryForm] = Form.useForm<RetryFormValues>()

  const selectedRun = useMemo(
    () => runs.find((item) => item.id === selectedRunId) ?? null,
    [runs, selectedRunId]
  )

  const flow = useMemo(() => buildFlowLayout(graph), [graph])

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
      return
    }
    setLoadingRuns(true)
    try {
      const data = await listPoolRuns({ poolId: selectedPoolId, limit: 100 })
      setRuns(data)
      if (!selectedRunId && data.length > 0) {
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
  }, [loadPools])

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
      direction: 'bottom_up',
      mode: 'safe',
      source_hash: '',
    })
    retryForm.setFieldsValue({
      entity_name: 'Document_IntercompanyPoolDistribution',
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
    try {
      values = await createForm.validateFields()
    } catch {
      return
    }

    setCreatingRun(true)
    setError(null)
    try {
      const payload = await createPoolRun({
        pool_id: selectedPoolId,
        direction: values.direction,
        period_start: values.period_start,
        period_end: values.period_end?.trim() || null,
        source_hash: values.source_hash?.trim() || '',
        mode: values.mode,
      })
      message.success(payload.created ? 'Run created' : 'Run reused by idempotency key')
      await loadRuns()
      setSelectedRunId(payload.run.id)
    } catch {
      setError('Не удалось создать run.')
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
      await retryPoolRunFailed(selectedRunId, {
        entity_name: values.entity_name,
        max_attempts: values.max_attempts,
        retry_interval_seconds: values.retry_interval_seconds,
        documents_by_database: documentsByDatabase,
      })
      message.success('Retry completed')
      await loadRuns()
      await loadReport()
    } catch {
      setError('Retry failed.')
    } finally {
      setRetrying(false)
    }
  }, [loadReport, loadRuns, message, retryForm, selectedRunId])

  const runColumns: ColumnsType<PoolRun> = useMemo(
    () => [
      {
        title: 'Run',
        dataIndex: 'id',
        key: 'id',
        width: 220,
        render: (value: string) => <Text code>{value.slice(0, 8)}</Text>,
      },
      {
        title: 'Status',
        dataIndex: 'status',
        key: 'status',
        width: 140,
        render: (value: string) => {
          let color = 'default'
          if (value === 'published') color = 'success'
          if (value === 'partial_success') color = 'warning'
          if (value === 'failed') color = 'error'
          if (value === 'publishing') color = 'processing'
          return <Tag color={color}>{value}</Tag>
        },
      },
      {
        title: 'Direction',
        dataIndex: 'direction',
        key: 'direction',
        width: 120,
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

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ marginBottom: 0 }}>
          Pool Runs
        </Title>
        <Text type="secondary">
          Граф пула, dry-run report, публикация и экран дозаписи failed-целей.
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

          <Form form={createForm} layout="inline">
            <Form.Item name="period_start" rules={[{ required: true, message: 'period_start required' }]}>
              <Input type="date" style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="period_end">
              <Input type="date" style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="direction" rules={[{ required: true }]}>
              <Select
                style={{ width: 140 }}
                options={[
                  { value: 'bottom_up', label: 'bottom_up' },
                  { value: 'top_down', label: 'top_down' },
                ]}
              />
            </Form.Item>
            <Form.Item name="mode" rules={[{ required: true }]}>
              <Select
                style={{ width: 120 }}
                options={[
                  { value: 'safe', label: 'safe' },
                  { value: 'unsafe', label: 'unsafe' },
                ]}
              />
            </Form.Item>
            <Form.Item name="source_hash">
              <Input placeholder="source hash" style={{ width: 220 }} />
            </Form.Item>
            <Button type="primary" loading={creatingRun} onClick={() => void handleCreateRun()}>
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
                onChange: (keys) => setSelectedRunId(String(keys[0])),
              }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Dry-run / Publication Report" loading={loadingReport}>
        {!selectedRun && (
          <Text type="secondary">Select a run to inspect report.</Text>
        )}
        {selectedRun && report && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Space size="small">
              <Tag color="blue">run: {selectedRun.id.slice(0, 8)}</Tag>
              <Tag color="processing">{selectedRun.status}</Tag>
              <Tag>attempts: {report.publication_attempts.length}</Tag>
            </Space>
            <Text strong>Validation Summary</Text>
            <TextArea readOnly rows={4} value={JSON.stringify(report.validation_summary ?? {}, null, 2)} />
            <Text strong>Publication Summary</Text>
            <TextArea readOnly rows={4} value={JSON.stringify(report.publication_summary ?? {}, null, 2)} />
            <Text strong>Diagnostics</Text>
            <TextArea readOnly rows={5} value={JSON.stringify(report.diagnostics ?? [], null, 2)} />
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
