import { Alert, Button, Card, Empty, List, Space, Spin, Tag, Typography } from 'antd'

import type { DecisionTable } from '../../api/generated/model'
import { isDecisionPinnedInBinding, type DecisionSnapshotFilterMode, type PinnedDecisionRefs } from './decisionSnapshotFilter'
import { renderCompatibilityTag } from './decisionPageUtils'

const { Text } = Typography

type DecisionCatalogPanelProps = {
  title: string
  decisions: DecisionTable[]
  loading: boolean
  selectedDecisionId: string | null
  pinnedDecisionRefs: PinnedDecisionRefs
  hiddenDecisionCount: number
  snapshotFilterMode: DecisionSnapshotFilterMode
  snapshotFilterMessage: string | null
  selectedConfigurationLabel?: string
  canFilterBySnapshot: boolean
  onToggleSnapshotMode: () => void
  onSelectDecision: (decisionId: string) => void
}

export function DecisionCatalogPanel({
  title,
  decisions,
  loading,
  selectedDecisionId,
  pinnedDecisionRefs,
  hiddenDecisionCount,
  snapshotFilterMode,
  snapshotFilterMessage,
  selectedConfigurationLabel,
  canFilterBySnapshot,
  onToggleSnapshotMode,
  onSelectDecision,
}: DecisionCatalogPanelProps) {
  return (
    <Card title={title}>
      {snapshotFilterMessage ? (
        <Alert
          type={snapshotFilterMode === 'all' ? 'info' : hiddenDecisionCount > 0 ? 'info' : 'success'}
          showIcon
          message={snapshotFilterMessage}
          description={(
            <Space wrap size={[8, 8]}>
              <Text type="secondary">Selected configuration</Text>
              <Tag>{selectedConfigurationLabel}</Tag>
              {(hiddenDecisionCount > 0 || snapshotFilterMode === 'all') ? (
                <Button type="link" onClick={onToggleSnapshotMode}>
                  {snapshotFilterMode === 'all' ? 'Show matching configuration only' : 'Show all revisions'}
                </Button>
              ) : null}
            </Space>
          )}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
          <Spin />
        </div>
      ) : decisions.length === 0 ? (
        <Empty
          description={canFilterBySnapshot
            ? 'No decision revisions match the selected configuration'
            : 'No decision revisions yet'}
        />
      ) : (
        <List
          dataSource={decisions}
          renderItem={(decision) => (
            <List.Item
              style={{
                cursor: 'pointer',
                paddingInline: 0,
                borderLeft: selectedDecisionId === decision.id ? '3px solid #1677ff' : '3px solid transparent',
                paddingLeft: 12,
              }}
              onClick={() => onSelectDecision(decision.id)}
            >
              <Space direction="vertical" size={2} style={{ width: '100%' }}>
                <Space wrap>
                  <Text strong>{decision.name}</Text>
                  <Tag color={decision.is_active ? 'green' : 'default'}>
                    {decision.is_active ? 'active' : 'inactive'}
                  </Tag>
                  {isDecisionPinnedInBinding(decision, pinnedDecisionRefs) ? (
                    <Tag color="gold">Pinned in binding</Tag>
                  ) : null}
                  {renderCompatibilityTag(decision.metadata_compatibility)}
                </Space>
                <Text type="secondary">{decision.decision_table_id}</Text>
                <Text type="secondary">Revision {decision.decision_revision}</Text>
              </Space>
            </List.Item>
          )}
        />
      )}
    </Card>
  )
}
