import { Alert, Button, Space, Typography } from 'antd'

import type { DecisionTable } from '../../api/generated/model/decisionTable'
import { EntityList, StatusBadge } from '../../components/platform'
import { useDecisionsTranslation } from '../../i18n'
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
  const { t } = useDecisionsTranslation()

  return (
    <EntityList
      title={title}
      loading={loading}
      emptyDescription={canFilterBySnapshot
        ? t(($) => $.catalog.emptyMatching)
        : t(($) => $.catalog.emptyDefault)}
      dataSource={decisions}
      toolbar={snapshotFilterMessage ? (
        <Alert
          type={snapshotFilterMode === 'all' ? 'info' : hiddenDecisionCount > 0 ? 'info' : 'success'}
          showIcon
          message={snapshotFilterMessage}
          description={(
            <Space wrap size={[8, 8]}>
              <Text type="secondary">{t(($) => $.catalog.selectedConfiguration)}</Text>
              <Text code>{selectedConfigurationLabel || t(($) => $.metadata.unavailable)}</Text>
              {(hiddenDecisionCount > 0 || snapshotFilterMode === 'all') ? (
                <Button type="link" onClick={onToggleSnapshotMode}>
                  {snapshotFilterMode === 'all'
                    ? t(($) => $.catalog.showMatchingOnly)
                    : t(($) => $.catalog.showAll)}
                </Button>
              ) : null}
            </Space>
          )}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      renderItem={(decision) => (
        <Button
          type="text"
          block
          aria-label={t(($) => $.catalog.openDecision, { name: decision.name })}
          aria-pressed={selectedDecisionId === decision.id}
          style={{
            justifyContent: 'flex-start',
            height: 'auto',
            paddingBlock: 12,
            paddingInline: 12,
            borderRadius: 8,
            border: selectedDecisionId === decision.id ? '1px solid #91caff' : '1px solid #f0f0f0',
            borderInlineStart: selectedDecisionId === decision.id ? '4px solid #1677ff' : '4px solid transparent',
            background: selectedDecisionId === decision.id ? '#e6f4ff' : '#fff',
            boxShadow: selectedDecisionId === decision.id ? '0 1px 2px rgba(22, 119, 255, 0.12)' : 'none',
          }}
          onClick={() => onSelectDecision(decision.id)}
        >
          <Space direction="vertical" size={2} style={{ width: '100%' }}>
            <Space wrap>
              <Text strong>{decision.name}</Text>
              <StatusBadge status={decision.is_active ? 'active' : 'inactive'} />
              {isDecisionPinnedInBinding(decision, pinnedDecisionRefs) ? (
                <StatusBadge status="pinned" label={t(($) => $.catalog.pinnedInBinding)} />
              ) : null}
              {renderCompatibilityTag(decision.metadata_compatibility)}
            </Space>
            <Text type="secondary">{decision.decision_table_id}</Text>
            <Text type="secondary">
              {t(($) => $.catalog.revision, { revision: String(decision.decision_revision) })}
            </Text>
          </Space>
        </Button>
      )}
    />
  )
}
