import { Alert, Button, Input, Select, Space, Spin, Typography } from 'antd'

import type { OrganizationPool, PoolGraph } from '../../api/intercompanyPools'
import { EmptyState, EntityDetails } from '../../components/platform'

const { Text, Title } = Typography

export type DecisionLegacyImportState = {
  poolId: string
  edgeVersionId: string
  decisionTableId: string
  name: string
  description: string
}

type DecisionLegacyImportPanelProps = {
  error?: string | null
  graph: PoolGraph | null
  graphLoading?: boolean
  onOpenRawImport: () => void
  pools: OrganizationPool[]
  poolsLoading?: boolean
  saving?: boolean
  value: DecisionLegacyImportState
  onCancel: () => void
  onChange: (value: DecisionLegacyImportState) => void
  onImport: () => void
}

const hasLegacyDocumentPolicy = (metadata: Record<string, unknown> | null | undefined): boolean => {
  if (!metadata || typeof metadata !== 'object') {
    return false
  }
  return metadata.document_policy !== undefined && metadata.document_policy !== null
}

const buildLegacyEdgeOptions = (graph: PoolGraph | null) => {
  if (!graph) {
    return []
  }

  const nodesById = new Map(graph.nodes.map((node) => [node.node_version_id, node]))
  return graph.edges
    .filter((edge) => hasLegacyDocumentPolicy(edge.metadata))
    .map((edge) => {
      const parent = nodesById.get(edge.parent_node_version_id)
      const child = nodesById.get(edge.child_node_version_id)
      const parentLabel = parent?.name || edge.parent_node_version_id
      const childLabel = child?.name || edge.child_node_version_id
      return {
        value: edge.edge_version_id,
        label: `${parentLabel} -> ${childLabel} (${edge.edge_version_id})`,
      }
    })
}

export function DecisionLegacyImportPanel({
  error,
  graph,
  graphLoading,
  onOpenRawImport,
  pools,
  poolsLoading,
  saving,
  value,
  onCancel,
  onChange,
  onImport,
}: DecisionLegacyImportPanelProps) {
  const edgeOptions = buildLegacyEdgeOptions(graph)
  const selectedEdgeLabel = edgeOptions.find((option) => option.value === value.edgeVersionId)?.label ?? null

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      <div>
        <Title level={4} style={{ marginBottom: 4 }}>
          Import legacy edge policy
        </Title>
        <Text type="secondary">
          Canonical migration flow: select a pool topology edge with legacy
          {' '}
          <code>document_policy</code>
          {' '}
          metadata and materialize it into the versioned
          {' '}
          <code>/decisions</code>
          {' '}
          lifecycle.
        </Text>
      </div>

      {error ? (
        <Alert type="error" showIcon message={error} />
      ) : null}

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Text strong>Pool</Text>
        <Select
          aria-label="Legacy import pool"
          data-testid="decision-legacy-import-pool-select"
          disabled={saving || poolsLoading}
          loading={poolsLoading}
          placeholder="Select a pool"
          value={value.poolId || undefined}
          options={pools.map((pool) => ({
            value: pool.id,
            label: `${pool.name} (${pool.code})`,
          }))}
          onChange={(poolId) => onChange({
            ...value,
            poolId,
            edgeVersionId: '',
          })}
        />
      </Space>

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Text strong>Legacy edge</Text>
        <Select
          aria-label="Legacy import edge"
          data-testid="decision-legacy-import-edge-select"
          disabled={saving || !value.poolId || graphLoading || poolsLoading || edgeOptions.length === 0}
          loading={graphLoading}
          placeholder="Select a topology edge"
          value={value.edgeVersionId || undefined}
          options={edgeOptions}
          onChange={(edgeVersionId) => onChange({
            ...value,
            edgeVersionId,
          })}
        />
        {graphLoading ? (
          <Space size="small">
            <Spin size="small" />
            <Text type="secondary">Loading topology snapshot…</Text>
          </Space>
        ) : null}
        {!graphLoading && value.poolId && edgeOptions.length === 0 ? (
          <EmptyState description="No legacy document_policy edges found for the selected pool." />
        ) : null}
      </Space>

      {selectedEdgeLabel ? (
        <EntityDetails title="Selected legacy source">
          <Space direction="vertical" size="small" style={{ display: 'flex' }}>
            <Text>{selectedEdgeLabel}</Text>
            <Text type="secondary">Source path: edge.metadata.document_policy</Text>
          </Space>
        </EntityDetails>
      ) : null}

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Text strong>Decision table ID</Text>
        <Input
          aria-label="Decision table ID"
          disabled={saving}
          value={value.decisionTableId}
          onChange={(event) => onChange({
            ...value,
            decisionTableId: event.target.value,
          })}
        />
      </Space>

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Text strong>Decision name</Text>
        <Input
          aria-label="Decision name"
          disabled={saving}
          value={value.name}
          onChange={(event) => onChange({
            ...value,
            name: event.target.value,
          })}
        />
      </Space>

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Text strong>Decision description</Text>
        <Input.TextArea
          aria-label="Decision description"
          autoSize={{ minRows: 2, maxRows: 4 }}
          disabled={saving}
          value={value.description}
          onChange={(event) => onChange({
            ...value,
            description: event.target.value,
          })}
        />
      </Space>

      <Alert
        type="info"
        showIcon
        message="Raw JSON remains compatibility-only"
        description={(
          <Space direction="vertical" size={4}>
            <span>Use this flow for legacy topology edges. Raw JSON stays available only as an explicit compatibility path.</span>
            <Button type="link" style={{ paddingInline: 0 }} disabled={saving} onClick={onOpenRawImport}>
              Open raw JSON compatibility import
            </Button>
          </Space>
        )}
      />

      <Space wrap>
        <Button
          type="primary"
          loading={saving}
          disabled={!value.poolId || !value.edgeVersionId}
          onClick={onImport}
        >
          Import to /decisions
        </Button>
        <Button disabled={saving} onClick={onCancel}>
          Cancel
        </Button>
      </Space>
    </Space>
  )
}
