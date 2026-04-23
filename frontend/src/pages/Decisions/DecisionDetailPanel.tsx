import { Alert, Collapse, Descriptions, Space, Typography } from 'antd'

import type { DecisionTableRead as DecisionTable } from '../../api/generated/model/decisionTableRead'
import { LazyJsonCodeEditor } from '../../components/code/LazyJsonCodeEditor'
import { EntityDetails } from '../../components/platform'
import { useDecisionsTranslation } from '../../i18n'
import type { DocumentPolicyOutput } from './documentPolicyBuilder'
import { DocumentPolicyViewer } from './DocumentPolicyViewer'
import { normalizeMetadataItems, renderCompatibilityTag, formatJson, type MetadataContextLike } from './decisionPageUtils'

const { Text: AntText } = Typography

type DecisionDetailPanelProps = {
  selectedDecision: DecisionTable | null
  detailLoading: boolean
  detailError: string | null
  detailContext: MetadataContextLike
  selectedPolicy: DocumentPolicyOutput | null
  selectedDecisionSupportsDocumentPolicyAuthoring: boolean
  selectedDecisionPinnedInBinding: boolean
  selectedDecisionRequiresRollover: boolean
}

export function DecisionDetailPanel({
  selectedDecision,
  detailLoading,
  detailError,
  detailContext,
  selectedPolicy,
  selectedDecisionSupportsDocumentPolicyAuthoring,
  selectedDecisionPinnedInBinding,
  selectedDecisionRequiresRollover,
}: DecisionDetailPanelProps) {
  const { t } = useDecisionsTranslation()
  const metadataItems = normalizeMetadataItems(selectedDecision?.metadata_context ?? detailContext, {
    unavailableLabel: t(($) => $.metadata.unavailable),
    driftYesLabel: t(($) => $.metadata.driftYes),
    driftNoLabel: t(($) => $.metadata.driftNo),
  })
  const metadataLabels = {
    config: t(($) => $.metadata.config),
    version: t(($) => $.metadata.version),
    generation: t(($) => $.metadata.generation),
    snapshot: t(($) => $.metadata.snapshot),
    mode: t(($) => $.metadata.mode),
    hash: t(($) => $.metadata.hash),
    observed_hash: t(($) => $.metadata.observedHash),
    drift: t(($) => $.metadata.drift),
    provenance: t(($) => $.metadata.provenance),
  } as const

  return (
    <EntityDetails
      title={selectedDecision?.name || t(($) => $.detail.defaultTitle)}
      error={detailError}
      loading={detailLoading}
      empty={!selectedDecision}
      emptyDescription={t(($) => $.detail.empty)}
    >
      {selectedDecision ? (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Descriptions
            size="small"
            column={{ xs: 1, md: 2 }}
            items={[
              {
                key: 'decision-table-id',
                label: t(($) => $.detail.decisionTableId),
                children: selectedDecision.decision_table_id,
              },
              {
                key: 'decision-key',
                label: t(($) => $.detail.canonicalKey),
                children: selectedDecision.decision_key,
              },
              {
                key: 'revision',
                label: t(($) => $.detail.revision),
                children: selectedDecision.decision_revision,
              },
              {
                key: 'parent-version',
                label: t(($) => $.detail.parentVersion),
                children: selectedDecision.parent_version || t(($) => $.metadata.unavailable),
              },
              {
                key: 'status',
                label: t(($) => $.detail.compatibility),
                children: renderCompatibilityTag(selectedDecision.metadata_compatibility),
              },
            ]}
          />

          {selectedDecision.metadata_compatibility?.reason ? (
            <Alert
              type="warning"
              showIcon
              message={selectedDecision.metadata_compatibility.reason}
            />
          ) : null}

          {!selectedDecisionSupportsDocumentPolicyAuthoring ? (
            <Alert
              type={selectedDecisionPinnedInBinding ? 'warning' : 'info'}
              showIcon
              message={
                selectedDecisionPinnedInBinding
                  ? t(($) => $.messages.legacyBoundReadOnly)
                  : t(($) => $.messages.unsupportedEdit, { decisionKey: selectedDecision.decision_key })
              }
            />
          ) : null}

          {selectedDecisionRequiresRollover ? (
            <Alert
              type="info"
              showIcon
              message={t(($) => $.detail.requiresRollover)}
            />
          ) : null}

          {selectedDecisionSupportsDocumentPolicyAuthoring ? (
            <div>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <AntText strong>{t(($) => $.detail.structuredTitle)}</AntText>
                <AntText type="secondary">
                  {t(($) => $.detail.structuredDescription)}
                </AntText>
              </Space>
              <div style={{ marginTop: 12 }}>
                <DocumentPolicyViewer policy={selectedPolicy} />
              </div>
            </div>
          ) : null}

          <Collapse
            size="small"
            items={[
              {
                key: 'metadata',
                label: t(($) => $.detail.metadataSection),
                children: (
                  <Descriptions
                    size="small"
                    column={{ xs: 1, md: 2 }}
                    items={metadataItems.map((item) => ({
                      key: `detail-${item.key}`,
                      label: metadataLabels[item.key as keyof typeof metadataLabels],
                      children: item.value,
                    }))}
                  />
                ),
              },
              {
                key: 'json',
                label: selectedDecisionSupportsDocumentPolicyAuthoring
                  ? t(($) => $.detail.compiledDocumentPolicyJson)
                  : t(($) => $.detail.decisionRulesJson),
                children: (
                  <LazyJsonCodeEditor
                    value={selectedDecisionSupportsDocumentPolicyAuthoring
                      ? (selectedPolicy ? formatJson(selectedPolicy) : '{}')
                      : formatJson(selectedDecision.rules ?? [])}
                    onChange={() => {}}
                    readOnly
                    height={320}
                    title={selectedDecisionSupportsDocumentPolicyAuthoring
                      ? t(($) => $.detail.documentPolicyOutput)
                      : t(($) => $.detail.decisionRulesOutput)}
                    enableCopy
                  />
                ),
              },
            ]}
          />
        </Space>
      ) : null}
    </EntityDetails>
  )
}
