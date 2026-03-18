import { Alert, Descriptions, Space, Typography } from 'antd'

import type { DecisionTable } from '../../api/generated/model'
import { LazyJsonCodeEditor } from '../../components/code/LazyJsonCodeEditor'
import { EntityDetails } from '../../components/platform'
import type { DocumentPolicyOutput } from './documentPolicyBuilder'
import { DocumentPolicyViewer } from './DocumentPolicyViewer'
import { normalizeMetadataItems, renderCompatibilityTag, formatJson, LEGACY_BOUND_DECISION_READ_ONLY_MESSAGE, type MetadataContextLike } from './decisionPageUtils'

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
  return (
    <EntityDetails
      title={selectedDecision?.name || 'Decision detail'}
      error={detailError}
      loading={detailLoading}
      empty={!selectedDecision}
      emptyDescription="Select a decision revision to inspect metadata and output"
    >
      {selectedDecision ? (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Descriptions
            size="small"
            column={{ xs: 1, md: 2 }}
            items={[
              {
                key: 'decision-table-id',
                label: 'Decision table ID',
                children: selectedDecision.decision_table_id,
              },
              {
                key: 'decision-key',
                label: 'Canonical key',
                children: selectedDecision.decision_key,
              },
              {
                key: 'revision',
                label: 'Revision',
                children: selectedDecision.decision_revision,
              },
              {
                key: 'parent-version',
                label: 'Parent version',
                children: selectedDecision.parent_version || '—',
              },
              {
                key: 'status',
                label: 'Compatibility',
                children: renderCompatibilityTag(selectedDecision.metadata_compatibility),
              },
            ]}
          />

          <Descriptions
            size="small"
            column={{ xs: 1, md: 2 }}
            items={normalizeMetadataItems(selectedDecision.metadata_context ?? detailContext).map((item) => ({
              key: `detail-${item.key}`,
              label: item.label,
              children: item.value,
            }))}
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
                  ? LEGACY_BOUND_DECISION_READ_ONLY_MESSAGE
                  : `This revision uses decision_key "${selectedDecision.decision_key}". /decisions editing supports only document_policy.`
              }
            />
          ) : null}

          {selectedDecisionRequiresRollover ? (
            <Alert
              type="info"
              showIcon
              message="This revision is outside the default compatible set for the selected database. Use Rollover selected revision to create a new revision for the current target metadata context."
            />
          ) : null}

          {selectedDecisionSupportsDocumentPolicyAuthoring ? (
            <div>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <AntText strong>Structured policy view</AntText>
                <AntText type="secondary">
                  Browse the selected decision as chains, documents, field mappings, and table-part mappings.
                  Use Edit selected decision to save any changes as a new revision.
                </AntText>
              </Space>
              <div style={{ marginTop: 12 }}>
                <DocumentPolicyViewer policy={selectedPolicy} />
              </div>
            </div>
          ) : null}

          <div>
            <AntText strong>{selectedDecisionSupportsDocumentPolicyAuthoring ? 'Compiled document_policy JSON' : 'Decision rules JSON'}</AntText>
            <div style={{ marginTop: 12 }}>
              <LazyJsonCodeEditor
                value={selectedDecisionSupportsDocumentPolicyAuthoring
                  ? (selectedPolicy ? formatJson(selectedPolicy) : '{}')
                  : formatJson(selectedDecision.rules ?? [])}
                onChange={() => {}}
                readOnly
                height={320}
                title={selectedDecisionSupportsDocumentPolicyAuthoring ? 'Document policy output' : 'Decision rules output'}
                enableCopy
              />
            </div>
          </div>
        </Space>
      ) : null}
    </EntityDetails>
  )
}
