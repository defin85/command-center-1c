import { Alert, Button, Descriptions, Input, Space, Typography } from 'antd'
import type { DescriptionsProps } from 'antd'

import { LazyJsonCodeEditorFormField } from '../../components/code/LazyJsonCodeEditor'
import { useDecisionsTranslation } from '../../i18n'
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
  const { t } = useDecisionsTranslation()
  const copy = value.mode === 'create'
    ? {
      title: t(($) => $.editor.modes.create.title),
      subtitle: t(($) => $.editor.modes.create.subtitle),
    }
    : value.mode === 'import'
      ? {
        title: t(($) => $.editor.modes.import.title),
        subtitle: t(($) => $.editor.modes.import.subtitle),
      }
      : value.mode === 'revise'
        ? {
          title: t(($) => $.editor.modes.revise.title),
          subtitle: t(($) => $.editor.modes.revise.subtitle),
        }
        : value.mode === 'rollover'
          ? {
            title: t(($) => $.editor.modes.rollover.title),
            subtitle: t(($) => $.editor.modes.rollover.subtitle),
          }
          : {
            title: t(($) => $.editor.modes.clone.title),
            subtitle: t(($) => $.editor.modes.clone.subtitle),
          }
  const saveButtonLabel = value.mode === 'rollover'
    ? t(($) => $.editor.saveButtons.rollover)
    : value.mode === 'clone'
      ? t(($) => $.editor.saveButtons.clone)
      : t(($) => $.editor.saveButtons.default)
  type SummaryItem = NonNullable<DescriptionsProps['items']>[number]
  const summaryItems: SummaryItem[] = []

  if (value.sourceSummary) {
    summaryItems.push({
      key: 'source-revision',
      label: t(($) => $.editor.summary.sourceRevision),
      children: `${value.sourceSummary.name} (${value.sourceSummary.decisionTableId} r${value.sourceSummary.decisionRevision})`,
    })
  }

  if (value.sourceSummary?.compatibilityStatus) {
    summaryItems.push({
      key: 'source-compatibility',
      label: t(($) => $.editor.summary.sourceCompatibility),
      children: value.sourceSummary.compatibilityReason
        ? `${value.sourceSummary.compatibilityStatus} · ${value.sourceSummary.compatibilityReason}`
        : value.sourceSummary.compatibilityStatus,
    })
  }

  if (value.targetSummary) {
    summaryItems.push(
      {
        key: 'target-database',
        label: t(($) => $.editor.summary.targetDatabase),
        children: value.targetSummary.databaseLabel,
      },
      {
        key: 'target-configuration',
        label: t(($) => $.editor.summary.targetMetadataSnapshot),
        children: value.targetSummary.configurationLabel,
      }
    )
  }

  if (value.targetSummary?.snapshotId) {
    summaryItems.push({
      key: 'target-snapshot-id',
      label: t(($) => $.editor.summary.targetSnapshotId),
      children: value.targetSummary.snapshotId,
    })
  }

  if (value.targetSummary?.resolutionMode) {
    summaryItems.push({
      key: 'target-resolution-mode',
      label: t(($) => $.editor.summary.targetResolutionMode),
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
          message={t(($) => $.editor.alerts.rollover)}
        />
      ) : null}

      {value.mode === 'clone' ? (
        <Alert
          type="info"
          showIcon
          message={t(($) => $.editor.alerts.clone)}
        />
      ) : null}

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Typography.Text strong>{t(($) => $.editor.fields.decisionTableId)}</Typography.Text>
        <Input
          aria-label={t(($) => $.editor.fields.decisionTableId)}
          disabled={saving || Boolean(value.parentVersionId)}
          value={value.decisionTableId}
          onChange={(event) => onChange({
            ...value,
            decisionTableId: event.target.value,
          })}
        />
      </Space>

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Typography.Text strong>{t(($) => $.editor.fields.decisionName)}</Typography.Text>
        <Input
          aria-label={t(($) => $.editor.fields.decisionName)}
          disabled={saving}
          value={value.name}
          onChange={(event) => onChange({
            ...value,
            name: event.target.value,
          })}
        />
      </Space>

      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
        <Typography.Text strong>{t(($) => $.editor.fields.description)}</Typography.Text>
        <Input.TextArea
          aria-label={t(($) => $.editor.fields.description)}
          autoSize={{ minRows: 2, maxRows: 4 }}
          disabled={saving}
          value={value.description}
          onChange={(event) => onChange({
            ...value,
            description: event.target.value,
          })}
        />
      </Space>

      <div role="tablist" aria-label={t(($) => $.editor.tabsAriaLabel)}>
        <Space wrap>
          <Button
            role="tab"
            aria-selected={value.activeTab === 'builder'}
            type={value.activeTab === 'builder' ? 'primary' : 'default'}
            onClick={() => onTabChange('builder')}
            disabled={saving}
          >
            {t(($) => $.editor.tabs.builder)}
          </Button>
          <Button
            role="tab"
            aria-selected={value.activeTab === 'raw'}
            type={value.activeTab === 'raw' ? 'primary' : 'default'}
            onClick={() => onTabChange('raw')}
            disabled={saving}
          >
            {t(($) => $.editor.tabs.rawJson)}
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
            {t(($) => $.editor.rawJsonDescription)}
          </Typography.Text>
          <LazyJsonCodeEditorFormField
            value={value.rawJson}
            onChange={(nextValue) => onChange({
              ...value,
              rawJson: nextValue,
            })}
            height={320}
            title={t(($) => $.editor.rawJsonTitle)}
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
          {t(($) => $.editor.cancel)}
        </Button>
      </Space>
    </Space>
  )
}
