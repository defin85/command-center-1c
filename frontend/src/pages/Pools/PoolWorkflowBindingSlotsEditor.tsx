import { Button, Card, Col, Form, Input, Row, Select, Space, Tag, Typography } from 'antd'

import type { AvailableDecisionRevision } from '../../types/workflow'
import { formatAvailableDecisionLabel } from '../../components/workflow/decisionOptions'

const { Text } = Typography

type PoolWorkflowBindingSlotsEditorProps = {
  bindingIndex: number
  availableDecisions: AvailableDecisionRevision[]
  decisionsLoading: boolean
  disabled: boolean
  getFieldValue: (namePath: Array<string | number>) => unknown
  setFieldValue: (namePath: Array<string | number>, value: unknown) => void
}

type DecisionOption = {
  value: string
  label: string
  decisionTableId: string
  decisionKey: string
  decisionRevision: number
}

function buildDecisionOptions({
  availableDecisions,
  decisionTableId,
  decisionKey,
  decisionRevisionRaw,
  selectedDecisionValue,
}: {
  availableDecisions: AvailableDecisionRevision[]
  decisionTableId: string
  decisionKey: string
  decisionRevisionRaw: string
  selectedDecisionValue: string | undefined
}): DecisionOption[] {
  const decisionOptions: DecisionOption[] = availableDecisions.map((decision) => ({
    value: `${decision.decisionTableId}:${decision.decisionRevision}`,
    label: formatAvailableDecisionLabel(decision),
    decisionTableId: decision.decisionTableId,
    decisionKey: decision.decisionKey,
    decisionRevision: decision.decisionRevision,
  }))

  if (
    decisionTableId
    && decisionKey
    && decisionRevisionRaw
    && !decisionOptions.some((option) => option.value === selectedDecisionValue)
  ) {
    decisionOptions.unshift({
      value: selectedDecisionValue ?? '',
      label: `${decisionTableId} (${decisionKey}) · r${decisionRevisionRaw} [inactive]`,
      decisionTableId,
      decisionKey,
      decisionRevision: Number(decisionRevisionRaw),
    })
  }

  return decisionOptions
}

export function PoolWorkflowBindingSlotsEditor({
  bindingIndex,
  availableDecisions,
  decisionsLoading,
  disabled,
  getFieldValue,
  setFieldValue,
}: PoolWorkflowBindingSlotsEditorProps) {
  return (
    <Card size="small" title="Publication slots">
      <Form.List name={[bindingIndex, 'decisions']}>
        {(decisionFields, decisionActions) => (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            {decisionFields.length === 0 ? (
              <Text type="secondary">No publication slots pinned yet.</Text>
            ) : null}
            {decisionFields.map((decisionField) => {
              const decisionTableId = String(
                getFieldValue([
                  'workflow_bindings',
                  bindingIndex,
                  'decisions',
                  decisionField.name,
                  'decision_table_id',
                ]) ?? ''
              ).trim()
              const decisionKey = String(
                getFieldValue([
                  'workflow_bindings',
                  bindingIndex,
                  'decisions',
                  decisionField.name,
                  'decision_key',
                ]) ?? ''
              ).trim()
              const decisionRevisionRaw = String(
                getFieldValue([
                  'workflow_bindings',
                  bindingIndex,
                  'decisions',
                  decisionField.name,
                  'decision_revision',
                ]) ?? ''
              ).trim()
              const selectedDecisionValue = (
                decisionTableId && decisionRevisionRaw
                  ? `${decisionTableId}:${decisionRevisionRaw}`
                  : undefined
              )
              const decisionOptions = buildDecisionOptions({
                availableDecisions,
                decisionTableId,
                decisionKey,
                decisionRevisionRaw,
                selectedDecisionValue,
              })
              return (
                <Row key={decisionField.key} gutter={12} align="middle">
                  <Col span={6}>
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                      <Text type="secondary">Slot name</Text>
                      <Tag
                        color={decisionKey ? 'blue' : 'default'}
                        style={{ width: 'fit-content' }}
                        data-testid={`pool-catalog-workflow-binding-slot-key-${bindingIndex}-${decisionField.name}`}
                      >
                        {decisionKey || 'unassigned'}
                      </Tag>
                      {decisionTableId ? (
                        <Text
                          type="secondary"
                          data-testid={`pool-catalog-workflow-binding-slot-ref-${bindingIndex}-${decisionField.name}`}
                        >
                          {decisionTableId}
                          {decisionRevisionRaw ? ` · r${decisionRevisionRaw}` : ''}
                        </Text>
                      ) : null}
                    </Space>
                  </Col>
                  <Col span={16}>
                    <Form.Item
                      label={decisionField.name === 0 ? 'Pinned revision' : undefined}
                      help={
                        decisionField.name === 0
                          ? 'Select active revision from /decisions. Slot name is derived from decision_key.'
                          : undefined
                      }
                    >
                      <Select
                        showSearch
                        allowClear
                        optionFilterProp="label"
                        disabled={disabled}
                        loading={decisionsLoading}
                        placeholder="Select decision revision from /decisions"
                        value={selectedDecisionValue}
                        data-testid={`pool-catalog-workflow-binding-decision-select-${bindingIndex}-${decisionField.name}`}
                        options={decisionOptions.map((option) => ({
                          value: option.value,
                          label: option.label,
                        }))}
                        onChange={(value) => {
                          const selected = decisionOptions.find((option) => option.value === value)
                          setFieldValue(
                            ['workflow_bindings', bindingIndex, 'decisions', decisionField.name, 'decision_table_id'],
                            selected?.decisionTableId ?? ''
                          )
                          setFieldValue(
                            ['workflow_bindings', bindingIndex, 'decisions', decisionField.name, 'decision_key'],
                            selected?.decisionKey ?? ''
                          )
                          setFieldValue(
                            ['workflow_bindings', bindingIndex, 'decisions', decisionField.name, 'decision_revision'],
                            selected?.decisionRevision ?? null
                          )
                        }}
                      />
                      <Form.Item name={[decisionField.name, 'decision_table_id']} hidden>
                        <Input />
                      </Form.Item>
                      <Form.Item name={[decisionField.name, 'decision_key']} hidden>
                        <Input />
                      </Form.Item>
                      <Form.Item name={[decisionField.name, 'decision_revision']} hidden>
                        <Input />
                      </Form.Item>
                    </Form.Item>
                  </Col>
                  <Col span={2}>
                    <Button
                      danger
                      onClick={() => decisionActions.remove(decisionField.name)}
                      disabled={disabled}
                      data-testid={`pool-catalog-workflow-binding-decision-remove-${bindingIndex}-${decisionField.name}`}
                    >
                      x
                    </Button>
                  </Col>
                </Row>
              )
            })}
            <Button
              onClick={() => decisionActions.add({ decision_table_id: '', decision_key: '', decision_revision: null })}
              disabled={disabled}
              data-testid={`pool-catalog-workflow-binding-add-decision-${bindingIndex}`}
            >
              Add slot
            </Button>
          </Space>
        )}
      </Form.List>
    </Card>
  )
}
