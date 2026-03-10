import { Alert, Button, Card, Input, Space, Typography } from 'antd'

import { LazyJsonCodeEditorFormField } from '../../components/code/LazyJsonCodeEditor'
import type { DocumentPolicyBuilderChainFormValue } from './documentPolicyBuilder'
import { DocumentPolicyBuilderEditor } from './DocumentPolicyBuilderEditor'

export type DecisionEditorMode = 'create' | 'import' | 'revise'
export type DecisionEditorTab = 'builder' | 'raw'

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
}

type DecisionEditorPanelProps = {
  error?: string | null
  saving?: boolean
  value: DecisionEditorState
  onCancel: () => void
  onChange: (value: DecisionEditorState) => void
  onSave: () => void
  onTabChange: (tab: DecisionEditorTab) => void
}

const PANEL_COPY: Record<DecisionEditorMode, { title: string; subtitle: string }> = {
  create: {
    title: 'New document policy',
    subtitle: 'Create a new versioned decision resource for document_policy authoring.',
  },
  import: {
    title: 'Import legacy policy',
    subtitle: 'Materialize a legacy document_policy payload into the decision-resource lifecycle.',
  },
  revise: {
    title: 'Revise selected decision',
    subtitle: 'Publish a new revision while preserving pinned lineage for the selected decision.',
  },
}

export function DecisionEditorPanel({
  error,
  saving,
  value,
  onCancel,
  onChange,
  onSave,
  onTabChange,
}: DecisionEditorPanelProps) {
  const copy = PANEL_COPY[value.mode]

  return (
    <Card>
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
          <Button type="primary" loading={saving} onClick={onSave}>
            Save decision
          </Button>
          <Button disabled={saving} onClick={onCancel}>
            Cancel
          </Button>
        </Space>
      </Space>
    </Card>
  )
}
