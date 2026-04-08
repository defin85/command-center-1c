import { Alert, Button, Descriptions, Input, Space, Typography } from 'antd'
import type { DescriptionsProps } from 'antd'

import { LazyJsonCodeEditorFormField } from '../../components/code/LazyJsonCodeEditor'
import { trackUiAction } from '../../observability/uiActionJournal'
import type { PoolODataMetadataCatalogDocument } from '../../api/generated/model'
import type { DocumentPolicyBuilderChainFormValue } from './documentPolicyBuilder'
import { DocumentPolicyBuilderEditor } from './DocumentPolicyBuilderEditor'

export type DecisionEditorMode = 'create' | 'import' | 'revise' | 'rollover' | 'clone'
export type DecisionEditorTab = 'builder' | 'raw'

export type DecisionEditorSourceSummary = {
  decisionId: string
  decisionTableId: string
  decisionRevision: number
  name: string
  compatibilityStatus?: string
  compatibilityReason?: string
}

export type DecisionEditorTargetSummary = {
  databaseId: string
  databaseLabel: string
  configurationLabel: string
  snapshotId?: string
  resolutionMode?: string
}

export type DecisionEditorState = {
  mode: DecisionEditorMode
  activeTab: DecisionEditorTab
  decisionTableId: string
  name: string
  description: string
  chains: DocumentPolicyBuilderChainFormValue[]
  rawJson: string
  isActive: boolean
  parentVersionId?: string
  targetDatabaseId?: string
  sourceSummary?: DecisionEditorSourceSummary
  targetSummary?: DecisionEditorTargetSummary
}

type DecisionEditorPanelProps = {
  error?: string | null
  saving?: boolean
  value: DecisionEditorState
  metadataDocuments?: readonly PoolODataMetadataCatalogDocument[]
  onCancel: () => void
  onChange: (value: DecisionEditorState) => void
  onSave: () => void | Promise<void>
  onTabChange: (tab: DecisionEditorTab) => void
}

const PANEL_COPY: Record<DecisionEditorMode, { title: string; subtitle: string }> = {
  create: {
    title: 'New document policy',
    subtitle: 'Create a new versioned decision resource for document_policy authoring.',
  },
  import: {
    title: 'Import raw policy JSON',
    subtitle: 'Compatibility path for pasting an already validated document_policy payload.',
  },
  revise: {
    title: 'Edit selected decision',
    subtitle: 'Review the existing decision in builder or raw JSON mode and save it as a new revision.',
  },
  rollover: {
    title: 'Rollover selected revision',
    subtitle: 'Use the selected revision as a source seed and publish a new revision for the target database metadata context.',
  },
  clone: {
    title: 'Clone selected revision',
    subtitle: 'Use the selected revision as a source seed and publish a new independent decision resource for the current target database context.',
  },
}

export function DecisionEditorPanel({
  error,
  saving,
  value,
  metadataDocuments = [],
  onCancel,
  onChange,
  onSave,
  onTabChange,
}: DecisionEditorPanelProps) {
  const copy = PANEL_COPY[value.mode]
  const saveButtonLabel = value.mode === 'rollover'
    ? 'Publish rollover revision'
    : value.mode === 'clone'
      ? 'Publish cloned decision'
      : 'Save decision'
  type SummaryItem = NonNullable<DescriptionsProps['items']>[number]
  const summaryItems: SummaryItem[] = []

  if (value.sourceSummary) {
    summaryItems.push({
      key: 'source-revision',
      label: 'Source revision',
      children: `${value.sourceSummary.name} (${value.sourceSummary.decisionTableId} r${value.sourceSummary.decisionRevision})`,
    })
  }

  if (value.sourceSummary?.compatibilityStatus) {
    summaryItems.push({
      key: 'source-compatibility',
      label: 'Source compatibility',
      children: value.sourceSummary.compatibilityReason
        ? `${value.sourceSummary.compatibilityStatus} · ${value.sourceSummary.compatibilityReason}`
        : value.sourceSummary.compatibilityStatus,
    })
  }

  if (value.targetSummary) {
    summaryItems.push(
      {
        key: 'target-database',
        label: 'Target database',
        children: value.targetSummary.databaseLabel,
      },
      {
        key: 'target-configuration',
        label: 'Target metadata snapshot',
        children: value.targetSummary.configurationLabel,
      }
    )
  }

  if (value.targetSummary?.snapshotId) {
    summaryItems.push({
      key: 'target-snapshot-id',
      label: 'Target snapshot ID',
      children: value.targetSummary.snapshotId,
    })
  }

  if (value.targetSummary?.resolutionMode) {
    summaryItems.push({
      key: 'target-resolution-mode',
      label: 'Target resolution mode',
      children: value.targetSummary.resolutionMode,
    })
  }

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      <div>
        <Typography.Title level={4} style={{ marginBottom: 4 }}>
          {copy.title}
        </Typography.Title>
        <Typography.Text type="secondary">
          {copy.subtitle}
        </Typography.Text>
      </div>

      {error ? (
        <Alert type="error" showIcon message={error} />
      ) : null}

      {summaryItems.length > 0 ? (
        <Descriptions
          size="small"
          column={1}
          items={summaryItems}
        />
      ) : null}

      {value.mode === 'rollover' ? (
        <Alert
          type="info"
          showIcon
          message="Publishing a rollover creates a new revision only. Existing workflows, bindings, and runtime projections stay pinned until you update them explicitly."
        />
      ) : null}

      {value.mode === 'clone' ? (
        <Alert
          type="info"
          showIcon
          message="Publishing a clone creates a new independent decision resource. Existing workflows, bindings, and runtime projections stay pinned until you update them explicitly."
        />
      ) : null}

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Typography.Text strong>Decision table ID</Typography.Text>
        <Input
          aria-label="Decision table ID"
          disabled={saving || Boolean(value.parentVersionId)}
          value={value.decisionTableId}
          onChange={(event) => onChange({
            ...value,
            decisionTableId: event.target.value,
          })}
        />
      </Space>

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Typography.Text strong>Decision name</Typography.Text>
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
        <Typography.Text strong>Description</Typography.Text>
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

      <div role="tablist" aria-label="Decision editor mode">
        <Space wrap>
          <Button
            role="tab"
            aria-selected={value.activeTab === 'builder'}
            type={value.activeTab === 'builder' ? 'primary' : 'default'}
            onClick={() => onTabChange('builder')}
            disabled={saving}
          >
            Builder
          </Button>
          <Button
            role="tab"
            aria-selected={value.activeTab === 'raw'}
            type={value.activeTab === 'raw' ? 'primary' : 'default'}
            onClick={() => onTabChange('raw')}
            disabled={saving}
          >
            Raw JSON
          </Button>
        </Space>
      </div>

      {value.activeTab === 'builder' ? (
        <DocumentPolicyBuilderEditor
          disabled={saving}
          metadataDocuments={metadataDocuments}
          value={value.chains}
          onChange={(chains) => onChange({ ...value, chains })}
        />
      ) : (
        <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
          <Typography.Text type="secondary">
            Use raw JSON only for compatibility imports or to paste an already validated
            {' '}
            <code>document_policy.v1</code>
            {' '}
            payload.
          </Typography.Text>
          <LazyJsonCodeEditorFormField
            value={value.rawJson}
            onChange={(nextValue) => onChange({
              ...value,
              rawJson: nextValue,
            })}
            height={320}
            title="Document policy JSON"
            enableFormat
            enableCopy
            readOnly={saving}
          />
        </Space>
      )}

      <Space wrap>
        <Button
          type="primary"
          loading={saving}
          onClick={() => {
            void trackUiAction({
              actionKind: 'drawer.submit',
              actionName: saveButtonLabel,
            }, onSave)
          }}
        >
          {saveButtonLabel}
        </Button>
        <Button disabled={saving} onClick={onCancel}>
          Cancel
        </Button>
      </Space>
    </Space>
  )
}
