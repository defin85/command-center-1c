import { Alert, Button, Card, Col, Form, Input, Row, Select, Space, Tag, Typography } from 'antd'
import type { AvailableDecisionRevision } from '../../types/workflow'

import {
  createEmptyWorkflowBindingFormValue,
  getWorkflowBindingCardSummary,
  getWorkflowBindingCardTitle,
  type PoolWorkflowBindingFormValue,
} from './poolWorkflowBindingsForm'
import { PoolWorkflowBindingSlotsEditor } from './PoolWorkflowBindingSlotsEditor'
import {
  buildTopologyCoverageContext,
  summarizeTopologySlotCoverage,
  type TopologyEdgeSelector,
} from './topologySlotCoverage'

const { Text } = Typography
const { TextArea } = Input

type PoolWorkflowBindingsEditorProps = {
  availableDecisions?: AvailableDecisionRevision[]
  decisionsLoading?: boolean
  decisionsLoadError?: string | null
  topologyEdgeSelectors?: TopologyEdgeSelector[]
  disabled?: boolean
}

const STATUS_OPTIONS = [
  { value: 'draft', label: 'draft' },
  { value: 'active', label: 'active' },
  { value: 'inactive', label: 'inactive' },
]

export function PoolWorkflowBindingsEditor({
  availableDecisions = [],
  decisionsLoading = false,
  decisionsLoadError = null,
  topologyEdgeSelectors = [],
  disabled = false,
}: PoolWorkflowBindingsEditorProps) {
  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="Workflow bindings are edited as first-class records"
        description="Каждый binding pin-ит workflow revision, selector, effective period и optional decision/parameter context для default pool path."
      />
      {decisionsLoadError ? (
        <Alert
          type="warning"
          showIcon
          message={decisionsLoadError}
          description="Decision refs selector читает active revisions из /decisions. Existing pinned refs останутся видимыми, но новые значения без этого каталога выбрать нельзя."
        />
      ) : null}
      <Form.List name="workflow_bindings">
        {(fields, { add, remove }) => (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {fields.length === 0 ? (
              <Text type="secondary">No workflow bindings configured for this pool yet.</Text>
            ) : null}
            {fields.map((field) => (
              <Form.Item key={field.key} noStyle shouldUpdate>
                {({ getFieldValue, setFieldValue }) => {
                  const binding = getFieldValue(['workflow_bindings', field.name]) as PoolWorkflowBindingFormValue | undefined
                  const bindingLabel = getWorkflowBindingCardTitle(binding, field.name + 1)
                  const slotRefs = (binding?.decisions ?? [])
                    .map((decision) => {
                      const slotKey = String(decision?.decision_key ?? '').trim()
                      const decisionTableId = String(decision?.decision_table_id ?? '').trim()
                      const decisionRevision = String(decision?.decision_revision ?? '').trim()
                      if (!slotKey || !decisionTableId || !decisionRevision) {
                        return null
                      }
                      return {
                        slotKey,
                        refLabel: `${decisionTableId} r${decisionRevision}`,
                      }
                    })
                    .filter((slotRef): slotRef is { slotKey: string; refLabel: string } => Boolean(slotRef))
                  const coverageSummary = summarizeTopologySlotCoverage(
                    topologyEdgeSelectors,
                    buildTopologyCoverageContext({
                      bindingLabel,
                      detail: `Coverage is evaluated against binding draft ${bindingLabel}.`,
                      slotRefs,
                      source: 'selected',
                    })
                  )
                  const unresolvedCoverageItems = coverageSummary.items.filter((item) => item.coverage.status !== 'resolved')
                  return (
                    <Card
                      size="small"
                      title={getWorkflowBindingCardTitle(binding, field.name + 1)}
                      extra={(
                        <Button
                          danger
                          size="small"
                          onClick={() => remove(field.name)}
                          disabled={disabled}
                          data-testid={`pool-catalog-workflow-binding-remove-${field.name}`}
                        >
                          Remove
                        </Button>
                      )}
                      data-testid={`pool-catalog-workflow-binding-card-${field.name}`}
                    >
                      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                        <Text
                          type="secondary"
                          data-testid={`pool-catalog-workflow-binding-summary-${field.name}`}
                        >
                          {getWorkflowBindingCardSummary(binding)}
                        </Text>
                        <Card
                          size="small"
                          title="Topology coverage"
                          data-testid={`pool-catalog-workflow-binding-coverage-${field.name}`}
                        >
                          {topologyEdgeSelectors.length === 0 ? (
                            <Text type="secondary">No topology edges in the selected snapshot yet.</Text>
                          ) : (
                            <Space direction="vertical" size="small" style={{ width: '100%' }}>
                              <Space size={[4, 4]} wrap>
                                <Tag>edges: {coverageSummary.totalEdges}</Tag>
                                <Tag color="success">resolved: {coverageSummary.counts.resolved}</Tag>
                                <Tag color="error">missing slot: {coverageSummary.counts.missing_slot}</Tag>
                                <Tag color="default">missing selector: {coverageSummary.counts.missing_selector}</Tag>
                                <Tag color="warning">ambiguous: {coverageSummary.counts.ambiguous_slot}</Tag>
                              </Space>
                              {unresolvedCoverageItems.length === 0 ? (
                                <Text type="secondary">All topology edges are covered by pinned slots in this binding.</Text>
                              ) : (
                                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                  {unresolvedCoverageItems.map((item) => (
                                    <Text
                                      key={`${item.edgeId}:${item.coverage.status}`}
                                      type="secondary"
                                      data-testid={`pool-catalog-workflow-binding-coverage-item-${field.name}`}
                                    >
                                      {`${item.edgeLabel} · ${item.slotKey || 'slot not set'} · ${item.coverage.label}`}
                                    </Text>
                                  ))}
                                </Space>
                              )}
                            </Space>
                          )}
                        </Card>
                        <Row gutter={12}>
                          <Col span={12}>
                            <Form.Item name={[field.name, 'binding_id']} label="binding_id">
                              <Input
                                allowClear
                                placeholder="optional existing binding id"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-id-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item name={[field.name, 'status']} label="status">
                              <Select
                                options={STATUS_OPTIONS}
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-status-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Row gutter={12}>
                          <Col span={12}>
                            <Form.Item name={[field.name, 'workflow_definition_key']} label="workflow_definition_key">
                              <Input
                                placeholder="services-publication"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-workflow-key-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item name={[field.name, 'workflow_name']} label="workflow_name">
                              <Input
                                placeholder="services_publication"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-workflow-name-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Row gutter={12}>
                          <Col span={16}>
                            <Form.Item name={[field.name, 'workflow_revision_id']} label="workflow_revision_id">
                              <Input
                                placeholder="uuid"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-workflow-revision-id-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item name={[field.name, 'workflow_revision']} label="workflow_revision">
                              <Input
                                type="number"
                                min={1}
                                placeholder="3"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-workflow-revision-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Row gutter={12}>
                          <Col span={12}>
                            <Form.Item name={[field.name, 'effective_from']} label="effective_from">
                              <Input
                                type="date"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-effective-from-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item name={[field.name, 'effective_to']} label="effective_to">
                              <Input
                                type="date"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-effective-to-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Row gutter={12}>
                          <Col span={8}>
                            <Form.Item name={[field.name, 'selector', 'direction']} label="selector.direction">
                              <Input
                                allowClear
                                placeholder="top_down"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-selector-direction-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item name={[field.name, 'selector', 'mode']} label="selector.mode">
                              <Input
                                allowClear
                                placeholder="safe"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-selector-mode-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item name={[field.name, 'selector', 'tags_csv']} label="selector.tags">
                              <Input
                                allowClear
                                placeholder="baseline, monthly"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-selector-tags-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                        </Row>
                        <PoolWorkflowBindingSlotsEditor
                          bindingIndex={field.name}
                          availableDecisions={availableDecisions}
                          decisionsLoading={decisionsLoading}
                          disabled={disabled}
                          topologyEdgeSelectors={topologyEdgeSelectors}
                          getFieldValue={getFieldValue}
                          setFieldValue={setFieldValue}
                        />

                        <Card size="small" title="Role mapping">
                          <Form.List name={[field.name, 'role_mapping']}>
                            {(roleFields, roleActions) => (
                              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                                {roleFields.length === 0 ? (
                                  <Text type="secondary">No role mapping.</Text>
                                ) : null}
                                {roleFields.map((roleField) => (
                                  <Row key={roleField.key} gutter={8}>
                                    <Col span={10}>
                                      <Form.Item name={[roleField.name, 'source_role']}>
                                        <Input
                                          placeholder="source_role"
                                          disabled={disabled}
                                          data-testid={`pool-catalog-workflow-binding-role-source-${field.name}-${roleField.name}`}
                                        />
                                      </Form.Item>
                                    </Col>
                                    <Col span={12}>
                                      <Form.Item name={[roleField.name, 'target_role']}>
                                        <Input
                                          placeholder="target_role"
                                          disabled={disabled}
                                          data-testid={`pool-catalog-workflow-binding-role-target-${field.name}-${roleField.name}`}
                                        />
                                      </Form.Item>
                                    </Col>
                                    <Col span={2}>
                                      <Button
                                        danger
                                        onClick={() => roleActions.remove(roleField.name)}
                                        disabled={disabled}
                                        data-testid={`pool-catalog-workflow-binding-role-remove-${field.name}-${roleField.name}`}
                                      >
                                        x
                                      </Button>
                                    </Col>
                                  </Row>
                                ))}
                                <Button
                                  onClick={() => roleActions.add({ source_role: '', target_role: '' })}
                                  disabled={disabled}
                                  data-testid={`pool-catalog-workflow-binding-add-role-${field.name}`}
                                >
                                  Add role mapping
                                </Button>
                              </Space>
                            )}
                          </Form.List>
                        </Card>

                        <Card size="small" title="Binding parameters">
                          <Form.List name={[field.name, 'parameters']}>
                            {(parameterFields, parameterActions) => (
                              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                                {parameterFields.length === 0 ? (
                                  <Text type="secondary">No binding parameters.</Text>
                                ) : null}
                                {parameterFields.map((parameterField) => (
                                  <Row key={parameterField.key} gutter={8}>
                                    <Col span={8}>
                                      <Form.Item name={[parameterField.name, 'key']}>
                                        <Input
                                          placeholder="parameter key"
                                          disabled={disabled}
                                          data-testid={(
                                            `pool-catalog-workflow-binding-parameter-key-${field.name}-${parameterField.name}`
                                          )}
                                        />
                                      </Form.Item>
                                    </Col>
                                    <Col span={14}>
                                      <Form.Item name={[parameterField.name, 'value_json']}>
                                        <TextArea
                                          autoSize={{ minRows: 1, maxRows: 4 }}
                                          placeholder='"strict" or {"threshold": 10}'
                                          disabled={disabled}
                                          data-testid={(
                                            `pool-catalog-workflow-binding-parameter-value-${field.name}-${parameterField.name}`
                                          )}
                                        />
                                      </Form.Item>
                                    </Col>
                                    <Col span={2}>
                                      <Button
                                        danger
                                        onClick={() => parameterActions.remove(parameterField.name)}
                                        disabled={disabled}
                                        data-testid={(
                                          `pool-catalog-workflow-binding-parameter-remove-${field.name}-${parameterField.name}`
                                        )}
                                      >
                                        x
                                      </Button>
                                    </Col>
                                  </Row>
                                ))}
                                <Button
                                  onClick={() => parameterActions.add({ key: '', value_json: '' })}
                                  disabled={disabled}
                                  data-testid={`pool-catalog-workflow-binding-add-parameter-${field.name}`}
                                >
                                  Add parameter
                                </Button>
                              </Space>
                            )}
                          </Form.List>
                        </Card>
                      </Space>
                    </Card>
                  )
                }}
              </Form.Item>
            ))}
            <Button
              onClick={() => add(createEmptyWorkflowBindingFormValue())}
              disabled={disabled}
              data-testid="pool-catalog-workflow-binding-add"
            >
              Add workflow binding
            </Button>
          </Space>
        )}
      </Form.List>
    </Space>
  )
}
