import { Button, Card, Col, Form, Input, Row, Space, Tag, Typography } from 'antd'

import type { AvailableDecisionRevision } from '../../types/workflow'
import { DecisionRevisionSelect } from '../../components/workflow/DecisionRevisionSelect'
import type { TopologyEdgeSelector } from './topologySlotCoverage'

const { Text } = Typography

type PoolWorkflowBindingSlotsEditorProps = {
  bindingIndex: number
  availableDecisions: AvailableDecisionRevision[]
  decisionsLoading: boolean
  disabled: boolean
  topologyEdgeSelectors?: TopologyEdgeSelector[]
  getFieldValue: (namePath: Array<string | number>) => unknown
  setFieldValue: (namePath: Array<string | number>, value: unknown) => void
}

export function PoolWorkflowBindingSlotsEditor({
  bindingIndex,
  availableDecisions,
  decisionsLoading,
  disabled,
  topologyEdgeSelectors = [],
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
              const slotKey = String(
                getFieldValue([
                  'workflow_bindings',
                  bindingIndex,
                  'decisions',
                  decisionField.name,
                  'slot_key',
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
              const matchedEdges = topologyEdgeSelectors.filter((edge) => edge.slotKey === slotKey)
              return (
                <Row key={decisionField.key} gutter={12} align="middle">
                  <Col span={6}>
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                      <Form.Item
                        name={[decisionField.name, 'slot_key']}
                        label={decisionField.name === 0 ? 'Slot key' : undefined}
                        style={{ marginBottom: 0 }}
                      >
                        <Input
                          disabled={disabled}
                          placeholder="sale, purchase, return"
                          data-testid={`pool-catalog-workflow-binding-slot-key-input-${bindingIndex}-${decisionField.name}`}
                        />
                      </Form.Item>
                      <Tag
                        color={matchedEdges.length > 0 ? 'green' : 'default'}
                        style={{ width: 'fit-content' }}
                        data-testid={`pool-catalog-workflow-binding-slot-coverage-${bindingIndex}-${decisionField.name}`}
                      >
                        {matchedEdges.length > 0 ? `edges: ${matchedEdges.length}` : 'unused by topology'}
                      </Tag>
                      {decisionTableId ? (
                        <Text
                          type="secondary"
                          data-testid={`pool-catalog-workflow-binding-slot-ref-${bindingIndex}-${decisionField.name}`}
                        >
                          {decisionTableId} ({decisionKey})
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
                          ? 'Select active revision from /decisions. Slot key is managed separately from the reusable decision key.'
                          : undefined
                      }
                    >
                      <DecisionRevisionSelect
                        allowClear
                        disabled={disabled}
                        loading={decisionsLoading}
                        placeholder="Select decision revision from /decisions"
                        testId={`pool-catalog-workflow-binding-decision-select-${bindingIndex}-${decisionField.name}`}
                        availableDecisions={availableDecisions}
                        currentDecision={(
                          decisionTableId && decisionKey && decisionRevisionRaw
                            ? {
                                decision_table_id: decisionTableId,
                                decision_key: decisionKey,
                                decision_revision: Number(decisionRevisionRaw),
                              }
                            : undefined
                        )}
                        onChange={(selected) => {
                          setFieldValue(
                            ['workflow_bindings', bindingIndex, 'decisions', decisionField.name, 'decision_table_id'],
                            selected?.decision_table_id ?? ''
                          )
                          setFieldValue(
                            ['workflow_bindings', bindingIndex, 'decisions', decisionField.name, 'decision_key'],
                            selected?.decision_key ?? ''
                          )
                          setFieldValue(
                            ['workflow_bindings', bindingIndex, 'decisions', decisionField.name, 'decision_revision'],
                            selected?.decision_revision ?? null
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
              onClick={() => decisionActions.add({ decision_table_id: '', decision_key: '', slot_key: '', decision_revision: null })}
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
