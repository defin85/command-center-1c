import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Input,
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
  getOrganization,
  getPoolGraph,
  listOrganizationPools,
  listOrganizations,
  type Organization,
  type OrganizationPool,
  type OrganizationPoolBinding,
  type OrganizationStatus,
  type PoolGraph,
} from '../../api/intercompanyPools'

const { Title, Text } = Typography

const formatDate = (value: string | null | undefined) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
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

  for (let index = 0; index < graph.nodes.length; index += 1) {
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
  for (const depth of Array.from(groupedByDepth.keys()).sort((a, b) => a - b)) {
    const nodesAtDepth = groupedByDepth.get(depth) ?? []
    nodesAtDepth.forEach((node, rowIndex) => {
      flowNodes.push({
        id: node.node_version_id,
        position: { x: depth * 280, y: rowIndex * 112 },
        data: { label: `${node.name}\n${node.inn}` },
        style: {
          border: node.is_root ? '2px solid #1677ff' : '1px solid #d9d9d9',
          borderRadius: 8,
          padding: 8,
          width: 230,
          background: '#ffffff',
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

const statusColor: Record<OrganizationStatus, string> = {
  active: 'success',
  inactive: 'default',
  archived: 'warning',
}

export function PoolCatalogPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null)
  const [organizationDetail, setOrganizationDetail] = useState<{
    organization: Organization
    pool_bindings: OrganizationPoolBinding[]
  } | null>(null)
  const [pools, setPools] = useState<OrganizationPool[]>([])
  const [selectedPoolId, setSelectedPoolId] = useState<string | null>(null)
  const [graphDate, setGraphDate] = useState<string>(new Date().toISOString().slice(0, 10))
  const [graph, setGraph] = useState<PoolGraph | null>(null)
  const [loadingOrganizations, setLoadingOrganizations] = useState(false)
  const [loadingOrganizationDetail, setLoadingOrganizationDetail] = useState(false)
  const [loadingPools, setLoadingPools] = useState(false)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | OrganizationStatus>('all')
  const [databaseLinkFilter, setDatabaseLinkFilter] = useState<'all' | 'linked' | 'unlinked'>('all')
  const [error, setError] = useState<string | null>(null)

  const flow = useMemo(() => buildFlowLayout(graph), [graph])

  const loadOrganizations = useCallback(async () => {
    setLoadingOrganizations(true)
    setError(null)
    try {
      const data = await listOrganizations({
        status: statusFilter === 'all' ? undefined : statusFilter,
        query: query.trim() || undefined,
        databaseLinked: databaseLinkFilter === 'all' ? undefined : databaseLinkFilter === 'linked',
        limit: 300,
      })
      setOrganizations(data)
      setSelectedOrganizationId((previous) => {
        if (previous && data.some((item) => item.id === previous)) {
          return previous
        }
        return data[0]?.id ?? null
      })
    } catch {
      setError('Не удалось загрузить каталог организаций.')
    } finally {
      setLoadingOrganizations(false)
    }
  }, [databaseLinkFilter, query, statusFilter])

  const loadOrganizationDetail = useCallback(async () => {
    if (!selectedOrganizationId) {
      setOrganizationDetail(null)
      return
    }
    setLoadingOrganizationDetail(true)
    try {
      const detail = await getOrganization(selectedOrganizationId)
      setOrganizationDetail(detail)
    } catch {
      setError('Не удалось загрузить детали организации.')
    } finally {
      setLoadingOrganizationDetail(false)
    }
  }, [selectedOrganizationId])

  const loadPools = useCallback(async () => {
    setLoadingPools(true)
    try {
      const data = await listOrganizationPools()
      setPools(data)
      setSelectedPoolId((previous) => {
        if (previous && data.some((item) => item.id === previous)) {
          return previous
        }
        return data[0]?.id ?? null
      })
    } catch {
      setError('Не удалось загрузить каталог пулов.')
    } finally {
      setLoadingPools(false)
    }
  }, [])

  const loadGraph = useCallback(async () => {
    if (!selectedPoolId) {
      setGraph(null)
      return
    }
    setLoadingGraph(true)
    try {
      const payload = await getPoolGraph(selectedPoolId, graphDate || undefined)
      setGraph(payload)
    } catch {
      setError('Не удалось загрузить граф пула.')
    } finally {
      setLoadingGraph(false)
    }
  }, [graphDate, selectedPoolId])

  useEffect(() => {
    void loadOrganizations()
  }, [loadOrganizations])

  useEffect(() => {
    void loadOrganizationDetail()
  }, [loadOrganizationDetail])

  useEffect(() => {
    void loadPools()
  }, [loadPools])

  useEffect(() => {
    void loadGraph()
  }, [loadGraph])

  const organizationColumns: ColumnsType<Organization> = useMemo(
    () => [
      {
        title: 'Name',
        dataIndex: 'name',
        key: 'name',
        render: (value: string, record) => (
          <Space direction="vertical" size={0}>
            <Text strong>{value}</Text>
            <Text type="secondary">INN: {record.inn}</Text>
          </Space>
        ),
      },
      {
        title: 'Status',
        dataIndex: 'status',
        key: 'status',
        width: 120,
        render: (value: OrganizationStatus) => <Tag color={statusColor[value]}>{value}</Tag>,
      },
      {
        title: 'Database',
        key: 'database_id',
        width: 220,
        render: (_value, record) => (
          record.database_id
            ? <Text code>{record.database_id.slice(0, 8)}</Text>
            : <Text type="secondary">not linked</Text>
        ),
      },
      {
        title: 'Updated',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 180,
        render: (value: string) => formatDate(value),
      },
    ],
    []
  )

  const bindingColumns: ColumnsType<OrganizationPoolBinding> = useMemo(
    () => [
      {
        title: 'Pool',
        key: 'pool',
        render: (_value, record) => `${record.pool_code} - ${record.pool_name}`,
      },
      {
        title: 'Root',
        dataIndex: 'is_root',
        key: 'is_root',
        width: 90,
        render: (value: boolean) => (value ? <Tag color="blue">yes</Tag> : <Tag>no</Tag>),
      },
      {
        title: 'From',
        dataIndex: 'effective_from',
        key: 'effective_from',
        width: 120,
      },
      {
        title: 'To',
        dataIndex: 'effective_to',
        key: 'effective_to',
        width: 120,
        render: (value: string | null) => value || 'open',
      },
    ],
    []
  )

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Title level={3} style={{ marginBottom: 0 }}>
          Pool Catalog
        </Title>
        <Text type="secondary">
          Tenant-aware каталог организаций и read-only граф структуры пула по дате.
        </Text>
      </div>

      {error && <Alert type="error" message={error} showIcon />}

      <Card title="Organizations" loading={loadingOrganizations}>
        <Space size="small" wrap style={{ marginBottom: 12 }}>
          <Input
            value={query}
            placeholder="Search by INN/name"
            style={{ width: 280 }}
            onChange={(event) => setQuery(event.target.value)}
            onPressEnter={() => { void loadOrganizations() }}
            allowClear
          />
          <Select
            value={statusFilter}
            style={{ width: 160 }}
            options={[
              { value: 'all', label: 'All statuses' },
              { value: 'active', label: 'Active' },
              { value: 'inactive', label: 'Inactive' },
              { value: 'archived', label: 'Archived' },
            ]}
            onChange={setStatusFilter}
          />
          <Select
            value={databaseLinkFilter}
            style={{ width: 180 }}
            options={[
              { value: 'all', label: 'All databases' },
              { value: 'linked', label: 'Linked only' },
              { value: 'unlinked', label: 'Unlinked only' },
            ]}
            onChange={setDatabaseLinkFilter}
          />
          <Button onClick={() => { void loadOrganizations() }} loading={loadingOrganizations}>
            Refresh
          </Button>
        </Space>

        <Row gutter={16}>
          <Col span={14}>
            <Table
              rowKey="id"
              size="small"
              columns={organizationColumns}
              dataSource={organizations}
              loading={loadingOrganizations}
              pagination={{ pageSize: 10 }}
              rowSelection={{
                type: 'radio',
                selectedRowKeys: selectedOrganizationId ? [selectedOrganizationId] : [],
                onChange: (keys) => setSelectedOrganizationId(String(keys[0])),
              }}
              onRow={(record) => ({
                onClick: () => setSelectedOrganizationId(record.id),
              })}
            />
          </Col>
          <Col span={10}>
            <Card title="Organization details" loading={loadingOrganizationDetail}>
              {!organizationDetail && (
                <Text type="secondary">Выберите организацию из каталога.</Text>
              )}
              {organizationDetail && (
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <Descriptions size="small" column={1}>
                    <Descriptions.Item label="Name">{organizationDetail.organization.name}</Descriptions.Item>
                    <Descriptions.Item label="INN">{organizationDetail.organization.inn}</Descriptions.Item>
                    <Descriptions.Item label="KPP">{organizationDetail.organization.kpp || '-'}</Descriptions.Item>
                    <Descriptions.Item label="Status">
                      <Tag color={statusColor[organizationDetail.organization.status]}>
                        {organizationDetail.organization.status}
                      </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="Database ID">
                      {organizationDetail.organization.database_id
                        ? <Text code>{organizationDetail.organization.database_id}</Text>
                        : <Text type="secondary">not linked</Text>}
                    </Descriptions.Item>
                  </Descriptions>
                  <Text strong>Pool bindings</Text>
                  <Table
                    rowKey={(record) => `${record.pool_id}:${record.effective_from}`}
                    size="small"
                    columns={bindingColumns}
                    dataSource={organizationDetail.pool_bindings}
                    pagination={false}
                    locale={{ emptyText: 'No bindings' }}
                  />
                </Space>
              )}
            </Card>
          </Col>
        </Row>
      </Card>

      <Card title="Pools graph (read-only)" loading={loadingPools || loadingGraph}>
        <Space size="small" wrap style={{ marginBottom: 12 }}>
          <Select
            value={selectedPoolId ?? undefined}
            style={{ width: 320 }}
            placeholder="Select pool"
            options={pools.map((pool) => ({
              value: pool.id,
              label: `${pool.code} - ${pool.name}`,
            }))}
            onChange={(value) => setSelectedPoolId(value)}
          />
          <Input
            type="date"
            value={graphDate}
            style={{ width: 170 }}
            onChange={(event) => setGraphDate(event.target.value)}
          />
          <Button onClick={() => { void loadGraph() }} loading={loadingGraph}>
            Refresh graph
          </Button>
        </Space>
        <div style={{ height: 520 }}>
          <ReactFlow
            nodes={flow.nodes}
            edges={flow.edges}
            fitView
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            zoomOnDoubleClick={false}
            proOptions={{ hideAttribution: true }}
          >
            <MiniMap />
            <Controls />
            <Background />
          </ReactFlow>
        </div>
      </Card>
    </Space>
  )
}
