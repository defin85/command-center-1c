import { Alert, Button, Input, Select, Space, Spin, Typography } from 'antd'

import type { OrganizationPool, PoolGraph } from '../../api/intercompanyPools'
import { EmptyState, EntityDetails } from '../../components/platform'
import { useDecisionsTranslation } from '../../i18n'
import { trackUiAction } from '../../observability/uiActionJournal'

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
  onImport: () => void | Promise<void>
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
  const { t } = useDecisionsTranslation()
  const edgeOptions = buildLegacyEdgeOptions(graph)
  const selectedEdgeLabel = edgeOptions.find((option) => option.value === value.edgeVersionId)?.label ?? null

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      <div>
        <Title level={4} style={{ marginBottom: 4 }}>
          {t(($) => $.legacyImport.title)}
        </Title>
        <Text type="secondary">
          {t(($) => $.legacyImport.subtitle)}
        </Text>
      </div>

      {error ? (
        <Alert type="error" showIcon message={error} />
      ) : null}

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Text strong>{t(($) => $.legacyImport.pool)}</Text>
        <Select
          aria-label={t(($) => $.legacyImport.pool)}
          data-testid="decision-legacy-import-pool-select"
          disabled={saving || poolsLoading}
          loading={poolsLoading}
          placeholder={t(($) => $.legacyImport.poolPlaceholder)}
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
        <Text strong>{t(($) => $.legacyImport.edge)}</Text>
        <Select
          aria-label={t(($) => $.legacyImport.edge)}
          data-testid="decision-legacy-import-edge-select"
          disabled={saving || !value.poolId || graphLoading || poolsLoading || edgeOptions.length === 0}
          loading={graphLoading}
          placeholder={t(($) => $.legacyImport.edgePlaceholder)}
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
            <Text type="secondary">{t(($) => $.legacyImport.topologyLoading)}</Text>
          </Space>
        ) : null}
        {!graphLoading && value.poolId && edgeOptions.length === 0 ? (
          <EmptyState description={t(($) => $.legacyImport.noLegacyEdges)} />
        ) : null}
      </Space>

      {selectedEdgeLabel ? (
        <EntityDetails title={t(($) => $.legacyImport.selectedSource)}>
          <Space direction="vertical" size="small" style={{ display: 'flex' }}>
            <Text>{selectedEdgeLabel}</Text>
            <Text type="secondary">{t(($) => $.legacyImport.sourcePath)}</Text>
          </Space>
        </EntityDetails>
      ) : null}

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Text strong>{t(($) => $.legacyImport.decisionTableId)}</Text>
        <Input
          aria-label={t(($) => $.legacyImport.decisionTableId)}
          disabled={saving}
          value={value.decisionTableId}
          onChange={(event) => onChange({
            ...value,
            decisionTableId: event.target.value,
          })}
        />
      </Space>

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Text strong>{t(($) => $.legacyImport.decisionName)}</Text>
        <Input
          aria-label={t(($) => $.legacyImport.decisionName)}
          disabled={saving}
          value={value.name}
          onChange={(event) => onChange({
            ...value,
            name: event.target.value,
          })}
        />
      </Space>

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Text strong>{t(($) => $.legacyImport.decisionDescription)}</Text>
        <Input.TextArea
          aria-label={t(($) => $.legacyImport.decisionDescription)}
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
        message={t(($) => $.legacyImport.rawJsonCompatibilityTitle)}
        description={(
          <Space direction="vertical" size={4}>
            <span>{t(($) => $.legacyImport.rawJsonCompatibilityDescription)}</span>
            <Button type="link" style={{ paddingInline: 0 }} disabled={saving} onClick={onOpenRawImport}>
              {t(($) => $.legacyImport.openRawJsonCompatibilityImport)}
            </Button>
          </Space>
        )}
      />

      <Space wrap>
        <Button
          type="primary"
          loading={saving}
          disabled={!value.poolId || !value.edgeVersionId}
          onClick={() => {
            void trackUiAction({
              actionKind: 'drawer.submit',
              actionName: t(($) => $.legacyImport.importAction),
            }, onImport)
          }}
        >
          {t(($) => $.legacyImport.importAction)}
        </Button>
        <Button disabled={saving} onClick={onCancel}>
          {t(($) => $.legacyImport.cancel)}
        </Button>
      </Space>
    </Space>
  )
}
