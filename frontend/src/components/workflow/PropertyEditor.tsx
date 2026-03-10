/**
 * PropertyEditor - Panel for editing selected node properties.
 *
 * Features:
 * - Dynamic form based on node type
 * - Validation for required fields
 * - Template selection for operations
 * - Expression editor for conditions
 */

import { useEffect, useRef, useState } from 'react'
import {
  Card,
  Form,
  Input,
  InputNumber,
  Select,
  Button,
  Space,
  Typography,
  Divider,
  Alert,
  Collapse
} from 'antd'
import {
  DeleteOutlined,
  CopyOutlined
} from '@ant-design/icons'
import type {
  WorkflowNodeData,
  NodeConfig,
  OperationTemplateListItem,
  OperationTemplateExecutionContract,
  AvailableWorkflowRevision,
  AvailableDecisionRevision,
  OperationRef,
  DecisionRef,
  OperationIO,
  OperationIOMode,
} from '../../types/workflow'
import { NODE_TYPE_INFO } from '../../types/workflow'
import { LazyJsonCodeEditor } from '../code/LazyJsonCodeEditor'
import './PropertyEditor.css'

const { Text } = Typography
const { TextArea } = Input
const { Panel } = Collapse

interface PropertyEditorProps {
  // Selected node data
  nodeId: string | null
  nodeData: WorkflowNodeData | null
  // Callback when properties change
  onNodeUpdate: (nodeId: string, data: Partial<WorkflowNodeData>) => void
  // Callback to delete node
  onNodeDelete: (nodeId: string) => void
  // Callback to duplicate node
  onNodeDuplicate?: (nodeId: string) => void
  // Available operation templates (for operation nodes)
  operationTemplates?: OperationTemplateListItem[]
  // Available workflows (for subworkflow nodes)
  availableWorkflows?: AvailableWorkflowRevision[]
  // Available decisions (for decision-gate nodes)
  availableDecisions?: AvailableDecisionRevision[]
  // Read-only mode (monitor mode)
  readOnly?: boolean
}

const OPERATION_IO_SEGMENT_RE = /^[A-Za-z_][A-Za-z0-9_]*$/
const OPERATION_IO_RESERVED_ROOTS = new Set(['nodes'])
const OPERATION_IO_RESERVED_PREFIXES = ['_', 'node_']

const validateOperationIoPath = ({
  path,
  fieldName,
  checkReservedRoot,
}: {
  path: string
  fieldName: string
  checkReservedRoot: boolean
}) => {
  const normalized = path.trim()
  if (!normalized) {
    throw new Error(`${fieldName} must not be empty`)
  }
  if (normalized.startsWith('.') || normalized.endsWith('.') || normalized.includes('..')) {
    throw new Error(`${fieldName} must use dot-notation without empty segments`)
  }

  const segments = normalized.split('.')
  for (const segment of segments) {
    if (!OPERATION_IO_SEGMENT_RE.test(segment)) {
      throw new Error(
        `${fieldName} segment "${segment}" is invalid; use [A-Za-z_][A-Za-z0-9_]*`
      )
    }
  }

  if (checkReservedRoot) {
    const root = segments[0]
    if (
      OPERATION_IO_RESERVED_ROOTS.has(root) ||
      OPERATION_IO_RESERVED_PREFIXES.some((prefix) => root.startsWith(prefix))
    ) {
      throw new Error(`${fieldName} root "${root}" is reserved`)
    }
  }

  return normalized
}

const parseOperationIoMappingObject = (raw: string, mappingName: string): Record<string, string> => {
  const trimmed = raw.trim()
  if (!trimmed) {
    return {}
  }
  const parsed: unknown = JSON.parse(trimmed)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${mappingName} must be a JSON object`)
  }

  const record: Record<string, string> = {}
  for (const [rawTargetPath, rawSourcePath] of Object.entries(parsed as Record<string, unknown>)) {
    if (typeof rawSourcePath !== 'string') {
      throw new Error(`${mappingName} value for "${rawTargetPath}" must be a string`)
    }

    const targetPath = validateOperationIoPath({
      path: rawTargetPath,
      fieldName: `${mappingName} target path`,
      checkReservedRoot: true,
    })
    const sourcePath = validateOperationIoPath({
      path: rawSourcePath,
      fieldName: `${mappingName} source path`,
      checkReservedRoot: false,
    })
    record[targetPath] = sourcePath
  }
  return record
}

const formatExecutionContractList = (items: string[]): string => (
  items.length > 0 ? items.join(', ') : 'none'
)

const resolveCompatibilityReadOnlyReason = (nodeData: WorkflowNodeData): string | null => {
  if (nodeData.nodeType === 'parallel' || nodeData.nodeType === 'loop') {
    return 'Parallel and loop nodes remain inspectable for compatibility, but default analyst authoring no longer edits them.'
  }
  if (
    nodeData.nodeType === 'condition'
    && !nodeData.decisionRef
    && typeof nodeData.config?.expression === 'string'
    && nodeData.config.expression.trim()
  ) {
    return 'This construct remains visible for compatibility, but the default analyst surface no longer allows editing raw expressions.'
  }
  return null
}

const resolveRequiredInputTargets = (contract: OperationTemplateExecutionContract | undefined): string[] => {
  if (!contract) {
    return []
  }
  return contract.input.requiredParameters.map((parameter) => `${contract.input.mode}.${parameter}`)
}

// Form for Operation node
const OperationForm = ({
  config,
  io,
  templateId,
  onTemplateChange,
  onChange,
  onIoChange,
  templates,
  readOnly,
  idPrefix,
}: {
  config: NodeConfig
  io?: OperationIO
  templateId?: string
  onTemplateChange: (templateId?: string) => void
  onChange: (config: NodeConfig) => void
  onIoChange: (io: OperationIO) => void
  templates: OperationTemplateListItem[]
  readOnly: boolean
  idPrefix: string
}) => {
  const normalizedIo: OperationIO = io ?? {
    mode: 'implicit_legacy',
    input_mapping: {},
    output_mapping: {},
  }
  const [inputMappingRaw, setInputMappingRaw] = useState<string>(() =>
    JSON.stringify(normalizedIo.input_mapping || {}, null, 2)
  )
  const [outputMappingRaw, setOutputMappingRaw] = useState<string>(() =>
    JSON.stringify(normalizedIo.output_mapping || {}, null, 2)
  )
  const [inputMappingError, setInputMappingError] = useState<string | null>(null)
  const [outputMappingError, setOutputMappingError] = useState<string | null>(null)
  const lastIdPrefixRef = useRef<string>(idPrefix)
  const selectedTemplate = templateId
    ? templates.find((template) => template.id === templateId)
    : undefined
  const executionContract = selectedTemplate?.executionContract
  const requiredInputTargets = resolveRequiredInputTargets(executionContract)
  const configuredInputTargets = new Set(Object.keys(normalizedIo.input_mapping || {}))
  const missingRequiredMappings = normalizedIo.mode === 'explicit_strict'
    ? requiredInputTargets.filter((targetPath) => !configuredInputTargets.has(targetPath))
    : []

  useEffect(() => {
    if (lastIdPrefixRef.current === idPrefix) {
      return
    }
    lastIdPrefixRef.current = idPrefix
    setInputMappingRaw(JSON.stringify(normalizedIo.input_mapping || {}, null, 2))
    setOutputMappingRaw(JSON.stringify(normalizedIo.output_mapping || {}, null, 2))
    setInputMappingError(null)
    setOutputMappingError(null)
  }, [idPrefix, normalizedIo.input_mapping, normalizedIo.output_mapping])

  const handleIoModeChange = (mode: OperationIOMode) => {
    onIoChange({
      mode,
      input_mapping: normalizedIo.input_mapping || {},
      output_mapping: normalizedIo.output_mapping || {},
    })
  }

  const handleInputMappingChange = (raw: string) => {
    setInputMappingRaw(raw)
    try {
      const mapping = parseOperationIoMappingObject(raw, 'input_mapping')
      setInputMappingError(null)
      onIoChange({
        mode: normalizedIo.mode,
        input_mapping: mapping,
        output_mapping: normalizedIo.output_mapping || {},
      })
    } catch (err) {
      setInputMappingError(err instanceof Error ? err.message : 'Invalid JSON')
    }
  }

  const handleOutputMappingChange = (raw: string) => {
    setOutputMappingRaw(raw)
    try {
      const mapping = parseOperationIoMappingObject(raw, 'output_mapping')
      setOutputMappingError(null)
      onIoChange({
        mode: normalizedIo.mode,
        input_mapping: normalizedIo.input_mapping || {},
        output_mapping: mapping,
      })
    } catch (err) {
      setOutputMappingError(err instanceof Error ? err.message : 'Invalid JSON')
    }
  }

  return (
    <>
      <Form.Item label="Template" htmlFor={`${idPrefix}-operation-template`} required>
        <Select
          id={`${idPrefix}-operation-template`}
          value={templateId}
          placeholder="Select operation template"
          disabled={readOnly}
          showSearch
          optionFilterProp="children"
          onChange={(value) => onTemplateChange(value || undefined)}
          options={templates.map((t) => ({
            value: t.id,
            label: `${t.name} (${t.operation_type})`
          }))}
          allowClear
        />
      </Form.Item>

      {executionContract && (
        <Card size="small" title="Execution contract" style={{ marginBottom: 12 }}>
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            <Text strong>{executionContract.capability.id}</Text>
            <Text type="secondary">
              {`${executionContract.capability.executorKind} -> ${executionContract.capability.targetEntity}`}
            </Text>
            <Text>
              {`Input (${executionContract.input.mode}): required ${formatExecutionContractList(executionContract.input.requiredParameters)}`}
            </Text>
            <Text>
              {`Optional inputs: ${formatExecutionContractList(executionContract.input.optionalParameters)}`}
            </Text>
            <Text>
              {`Output path: ${executionContract.output.resultPath}`}
            </Text>
            <Text>
              {`Side effects: ${executionContract.sideEffect.effectKind} / ${executionContract.sideEffect.executionMode}`}
            </Text>
            {executionContract.sideEffect.summary && (
              <Text>{executionContract.sideEffect.summary}</Text>
            )}
            <Text type="secondary">
              {`Binding provenance: ${executionContract.provenance.alias} · r${executionContract.provenance.exposureRevision ?? '?'}`}
            </Text>
          </Space>
        </Card>
      )}

      <Form.Item label="Timeout (seconds)" htmlFor={`${idPrefix}-operation-timeout`}>
        <InputNumber
          id={`${idPrefix}-operation-timeout`}
          value={config.timeout}
          min={1}
          max={3600}
          disabled={readOnly}
          style={{ width: '100%' }}
          onChange={(value) => onChange({ ...config, timeout: value || undefined })}
        />
      </Form.Item>

      <Form.Item label="Retries" htmlFor={`${idPrefix}-operation-retries`}>
        <InputNumber
          id={`${idPrefix}-operation-retries`}
          value={config.retries}
          min={0}
          max={10}
          disabled={readOnly}
          style={{ width: '100%' }}
          onChange={(value) => onChange({ ...config, retries: value || undefined })}
        />
      </Form.Item>

      <Form.Item label="Retry Delay (seconds)" htmlFor={`${idPrefix}-operation-retry-delay`}>
        <InputNumber
          id={`${idPrefix}-operation-retry-delay`}
          value={config.retry_delay}
          min={1}
          max={300}
          disabled={readOnly}
          style={{ width: '100%' }}
          onChange={(value) => onChange({ ...config, retry_delay: value || undefined })}
        />
      </Form.Item>

      <Divider style={{ margin: '12px 0' }} />

      <Form.Item
        label="Data Flow Mode"
        htmlFor={`${idPrefix}-operation-io-mode`}
        help="implicit_legacy keeps old behavior; explicit_strict uses only declared input/output mappings."
      >
        <Select
          id={`${idPrefix}-operation-io-mode`}
          value={normalizedIo.mode}
          disabled={readOnly}
          onChange={(value) => handleIoModeChange(value as OperationIOMode)}
          options={[
            { value: 'implicit_legacy', label: 'implicit_legacy (backward-compatible)' },
            { value: 'explicit_strict', label: 'explicit_strict (mapped only)' },
          ]}
        />
      </Form.Item>

      {normalizedIo.mode === 'explicit_strict' && (
        <>
          {missingRequiredMappings.length > 0 && (
            <Alert
              type="error"
              showIcon
              style={{ marginBottom: 12 }}
              message={`Missing required mappings: ${missingRequiredMappings.join(', ')}`}
              description="Selected template declares mandatory inputs that must be mapped explicitly on the workflow step."
            />
          )}
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="Mapping rules"
            description={
              'Use JSON object format {"target.path": "source.path"}. Target roots "nodes", "_*", and "node_*" are reserved.'
            }
          />
          <Collapse ghost>
            <Panel header="Input Mapping (before render)" key="operation-io-input">
              <Form.Item
                help={inputMappingError ? inputMappingError : 'Map workflow context -> template render context'}
                validateStatus={inputMappingError ? 'error' : undefined}
              >
                <LazyJsonCodeEditor
                  id={`${idPrefix}-operation-input-mapping`}
                  value={inputMappingRaw}
                  onChange={handleInputMappingChange}
                  readOnly={readOnly}
                  height={180}
                  path={`${idPrefix}-operation-input-mapping.json`}
                />
              </Form.Item>
            </Panel>
            <Panel header="Output Mapping (after success)" key="operation-io-output">
              <Form.Item
                help={outputMappingError ? outputMappingError : 'Map operation output -> workflow context'}
                validateStatus={outputMappingError ? 'error' : undefined}
              >
                <LazyJsonCodeEditor
                  id={`${idPrefix}-operation-output-mapping`}
                  value={outputMappingRaw}
                  onChange={handleOutputMappingChange}
                  readOnly={readOnly}
                  height={180}
                  path={`${idPrefix}-operation-output-mapping.json`}
                />
              </Form.Item>
            </Panel>
          </Collapse>
        </>
      )}
    </>
  )
}

// Form for Condition node
const ConditionForm = ({
  config,
  decisionRef,
  onChange,
  onDecisionChange,
  availableDecisions,
  readOnly,
  idPrefix,
}: {
  config: NodeConfig
  decisionRef?: DecisionRef
  onChange: (config: NodeConfig) => void
  onDecisionChange: (decisionRef?: DecisionRef) => void
  availableDecisions: AvailableDecisionRevision[]
  readOnly: boolean
  idPrefix: string
}) => {
  const selectedDecisionValue = decisionRef
    ? `${decisionRef.decision_table_id}:${decisionRef.decision_revision}`
    : undefined
  const legacyExpression = typeof config.expression === 'string'
    ? config.expression.trim()
    : ''
  const hasLegacyExpression = !decisionRef && legacyExpression.length > 0
  const selectedDecision = decisionRef
    ? availableDecisions.find(
        (decision) => (
          decision.decisionTableId === decisionRef.decision_table_id
          && decision.decisionRevision === decisionRef.decision_revision
        )
      )
    : undefined
  const decisionOptions = availableDecisions.map((decision) => ({
    value: `${decision.decisionTableId}:${decision.decisionRevision}`,
    label: `${decision.name} (${decision.decisionKey}) · r${decision.decisionRevision}`,
  }))
  if (decisionRef && !selectedDecision) {
    decisionOptions.unshift({
      value: `${decisionRef.decision_table_id}:${decisionRef.decision_revision}`,
      label: `${decisionRef.decision_table_id} (${decisionRef.decision_key}) · r${decisionRef.decision_revision} [inactive]`,
    })
  }
  const compiledExpression = decisionRef
    ? `{{ decisions.${decisionRef.decision_key} }}`
    : ''

  return (
    <>
      <Form.Item
        label="Decision Table"
        htmlFor={`${idPrefix}-condition-decision`}
        help="Pin a fail-closed decision table for analyst-facing routing. Leave empty only for legacy expression mode."
      >
        <Select
          id={`${idPrefix}-condition-decision`}
          data-testid={`${idPrefix}-condition-decision`}
          value={selectedDecisionValue}
          placeholder="Select decision table"
          disabled={readOnly}
          showSearch
          allowClear
          optionFilterProp="label"
          onChange={(value) => {
            if (!value) {
              onDecisionChange(undefined)
              return
            }
            const selected = availableDecisions.find(
              (decision) => `${decision.decisionTableId}:${decision.decisionRevision}` === value
            )
            onDecisionChange(selected
              ? {
                  decision_table_id: selected.decisionTableId,
                  decision_key: selected.decisionKey,
                  decision_revision: selected.decisionRevision,
                }
              : undefined)
          }}
          options={decisionOptions}
        />
      </Form.Item>

      {decisionRef ? (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="Decision-gate expression is managed by the pinned decision table"
            description={
              selectedDecision
                ? `${selectedDecision.name} evaluates into decisions.${selectedDecision.decisionKey} and is compiled fail-closed.`
                : 'Pinned decision ref is preserved in the workflow definition and compiled into decisions.<key>.'
            }
          />
          <Form.Item
            label="Compiled Expression"
            htmlFor={`${idPrefix}-condition-expression`}
            help="Read-only compatibility expression synthesized from decision_ref."
          >
            <TextArea
              id={`${idPrefix}-condition-expression`}
              data-testid={`${idPrefix}-condition-expression`}
              value={compiledExpression}
              disabled
              rows={2}
            />
          </Form.Item>
        </>
      ) : hasLegacyExpression ? (
        <>
          <Form.Item
            label="Legacy Expression"
            htmlFor={`${idPrefix}-condition-expression`}
            required
            help="Jinja2 expression that evaluates to true/false. Example: {{ amount > 100 }}"
          >
            <TextArea
              id={`${idPrefix}-condition-expression`}
              data-testid={`${idPrefix}-condition-expression`}
              value={config.expression}
              placeholder="{{ variable > value }}"
              disabled={readOnly}
              rows={3}
              onChange={(e) => onChange({ ...config, expression: e.target.value })}
            />
          </Form.Item>

          <Alert
            type="warning"
            message="Legacy condition mode"
            description="This construct remains visible for compatibility, but the default analyst surface no longer allows editing raw expressions."
            showIcon
            style={{ marginTop: 8 }}
          />
        </>
      ) : (
        <Alert
          type="info"
          showIcon
          message="Select a pinned decision table to configure this gate."
          description="Default analyst authoring uses fail-closed decision tables. Raw expressions are shown only for existing compatibility workflows."
        />
      )}
    </>
  )
}

// Form for Parallel node
const ParallelForm = ({
  config,
  onChange,
  readOnly,
  idPrefix,
}: {
  config: NodeConfig
  onChange: (config: NodeConfig) => void
  readOnly: boolean
  idPrefix: string
}) => (
  <>
    <Alert
      type="warning"
      showIcon
      style={{ marginBottom: 12 }}
      message="Runtime-only workflow construct"
      description="Parallel and loop nodes remain inspectable for compatibility, but default analyst authoring no longer edits them."
    />
    <Form.Item label="Parallel Nodes" htmlFor={`${idPrefix}-parallel-nodes`} help="Node IDs to execute in parallel">
      <Select
        id={`${idPrefix}-parallel-nodes`}
        mode="tags"
        value={config.parallel_nodes || []}
        placeholder="Enter node IDs"
        disabled={readOnly}
        onChange={(value) => onChange({ ...config, parallel_nodes: value })}
      />
    </Form.Item>

    <Form.Item label="Wait For" htmlFor={`${idPrefix}-parallel-wait-for`}>
      <Select
        id={`${idPrefix}-parallel-wait-for`}
        value={config.wait_for || 'all'}
        disabled={readOnly}
        onChange={(value) => onChange({ ...config, wait_for: value })}
        options={[
          { value: 'all', label: 'All nodes complete' },
          { value: 'any', label: 'Any node completes' },
          { value: 1, label: '1 node completes' },
          { value: 2, label: '2 nodes complete' },
          { value: 3, label: '3 nodes complete' }
        ]}
      />
    </Form.Item>

    <Form.Item label="Timeout (seconds)" htmlFor={`${idPrefix}-parallel-timeout`}>
      <InputNumber
        id={`${idPrefix}-parallel-timeout`}
        value={config.timeout}
        min={1}
        max={3600}
        disabled={readOnly}
        style={{ width: '100%' }}
        onChange={(value) => onChange({ ...config, timeout: value || undefined })}
      />
    </Form.Item>
  </>
)

// Form for Loop node
const LoopForm = ({
  config,
  onChange,
  readOnly,
  idPrefix,
}: {
  config: NodeConfig
  onChange: (config: NodeConfig) => void
  readOnly: boolean
  idPrefix: string
}) => (
  <>
    <Alert
      type="warning"
      showIcon
      style={{ marginBottom: 12 }}
      message="Runtime-only workflow construct"
      description="Parallel and loop nodes remain inspectable for compatibility, but default analyst authoring no longer edits them."
    />
    <Form.Item label="Loop Mode" htmlFor={`${idPrefix}-loop-mode`} required>
      <Select
        id={`${idPrefix}-loop-mode`}
        value={config.loop_mode || 'count'}
        disabled={readOnly}
        onChange={(value) => onChange({ ...config, loop_mode: value })}
        options={[
          { value: 'count', label: 'Count (repeat N times)' },
          { value: 'while', label: 'While (condition-based)' },
          { value: 'foreach', label: 'For Each (iterate items)' }
        ]}
      />
    </Form.Item>

    {config.loop_mode === 'count' && (
      <Form.Item label="Loop Count" htmlFor={`${idPrefix}-loop-count`}>
        <InputNumber
          id={`${idPrefix}-loop-count`}
          value={config.loop_count}
          min={1}
          max={1000}
          disabled={readOnly}
          style={{ width: '100%' }}
          onChange={(value) => onChange({ ...config, loop_count: value || undefined })}
        />
      </Form.Item>
    )}

    {config.loop_mode === 'while' && (
      <Form.Item
        label="Loop Condition"
        htmlFor={`${idPrefix}-loop-condition`}
        help="Jinja2 expression. Loop continues while true."
      >
        <TextArea
          id={`${idPrefix}-loop-condition`}
          value={config.loop_condition}
          placeholder="{{ counter < 10 }}"
          disabled={readOnly}
          rows={2}
          onChange={(e) => onChange({ ...config, loop_condition: e.target.value })}
        />
      </Form.Item>
    )}

    {config.loop_mode === 'foreach' && (
      <Form.Item
        label="Items Expression"
        htmlFor={`${idPrefix}-loop-items`}
        help="Jinja2 expression that returns a list."
      >
        <TextArea
          id={`${idPrefix}-loop-items`}
          value={config.loop_items}
          placeholder="{{ databases }}"
          disabled={readOnly}
          rows={2}
          onChange={(e) => onChange({ ...config, loop_items: e.target.value })}
        />
      </Form.Item>
    )}

    <Form.Item label="Max Iterations" htmlFor={`${idPrefix}-loop-max-iterations`} help="Safety limit">
      <InputNumber
        id={`${idPrefix}-loop-max-iterations`}
        value={config.max_iterations || 100}
        min={1}
        max={10000}
        disabled={readOnly}
        style={{ width: '100%' }}
        onChange={(value) => onChange({ ...config, max_iterations: value || undefined })}
      />
    </Form.Item>
  </>
)

// Form for SubWorkflow node
const SubWorkflowForm = ({
  config,
  onChange,
  workflows,
  readOnly,
  idPrefix,
}: {
  config: NodeConfig
  onChange: (config: NodeConfig) => void
  workflows: AvailableWorkflowRevision[]
  readOnly: boolean
  idPrefix: string
}) => {
  const [inputMappingRaw, setInputMappingRaw] = useState<string>(() => JSON.stringify(config.input_mapping || {}, null, 2))
  const [outputMappingRaw, setOutputMappingRaw] = useState<string>(() => JSON.stringify(config.output_mapping || {}, null, 2))
  const [inputMappingError, setInputMappingError] = useState<string | null>(null)
  const [outputMappingError, setOutputMappingError] = useState<string | null>(null)
  const lastIdPrefixRef = useRef<string>(idPrefix)

  useEffect(() => {
    if (lastIdPrefixRef.current === idPrefix) {
      return
    }
    lastIdPrefixRef.current = idPrefix
    setInputMappingRaw(JSON.stringify(config.input_mapping || {}, null, 2))
    setOutputMappingRaw(JSON.stringify(config.output_mapping || {}, null, 2))
    setInputMappingError(null)
    setOutputMappingError(null)
  }, [idPrefix, config.input_mapping, config.output_mapping])

  const parseMappingObject = (raw: string): Record<string, string> => {
    const trimmed = raw.trim()
    if (!trimmed) {
      return {}
    }
    const parsed: unknown = JSON.parse(trimmed)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('Mapping must be a JSON object')
    }

    const record: Record<string, string> = {}
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof value !== 'string') {
        throw new Error(`Mapping value for "${key}" must be a string`)
      }
      record[key] = value
    }
    return record
  }

  const handleInputMappingChange = (raw: string) => {
    setInputMappingRaw(raw)
    try {
      const mapping = parseMappingObject(raw)
      setInputMappingError(null)
      onChange({ ...config, input_mapping: mapping })
    } catch (err) {
      setInputMappingError(err instanceof Error ? err.message : 'Invalid JSON')
    }
  }

  const handleOutputMappingChange = (raw: string) => {
    setOutputMappingRaw(raw)
    try {
      const mapping = parseMappingObject(raw)
      setOutputMappingError(null)
      onChange({ ...config, output_mapping: mapping })
    } catch (err) {
      setOutputMappingError(err instanceof Error ? err.message : 'Invalid JSON')
    }
  }

  return (
    <>
      <Form.Item
        label="Sub-Workflow"
        htmlFor={`${idPrefix}-subworkflow`}
        required
        help="Analyst-facing subworkflow calls pin an explicit workflow revision by default."
      >
        <Select
          id={`${idPrefix}-subworkflow`}
          data-testid={`${idPrefix}-subworkflow`}
          value={config.subworkflow_ref?.workflow_revision_id ?? config.subworkflow_id}
          placeholder="Select workflow"
          disabled={readOnly}
          showSearch
          optionFilterProp="label"
          onChange={(value) => {
            const selectedWorkflow = workflows.find(
              (workflow) => workflow.workflowRevisionId === value
            )
            if (!selectedWorkflow) {
              onChange({
                ...config,
                subworkflow_id: value,
                subworkflow_ref: undefined,
              })
              return
            }
            onChange({
              ...config,
              subworkflow_id: selectedWorkflow.workflowRevisionId,
              subworkflow_ref: {
                binding_mode: 'pinned_revision',
                workflow_definition_key: selectedWorkflow.workflowDefinitionKey,
                workflow_revision_id: selectedWorkflow.workflowRevisionId,
                workflow_revision: selectedWorkflow.workflowRevision,
              },
            })
          }}
          options={workflows.map((w) => ({
            value: w.workflowRevisionId,
            label: `${w.name} · r${w.workflowRevision}`
          }))}
        />
      </Form.Item>

      <Collapse ghost>
        <Panel header="Input Mapping" key="input">
            <Form.Item
              help={inputMappingError ? inputMappingError : 'Map parent context to sub-workflow input'}
              validateStatus={inputMappingError ? 'error' : undefined}
            >
            <LazyJsonCodeEditor
              id={`${idPrefix}-subworkflow-input-mapping`}
              value={inputMappingRaw}
              onChange={handleInputMappingChange}
              readOnly={readOnly}
              height={180}
              path={`${idPrefix}-subworkflow-input-mapping.json`}
            />
          </Form.Item>
        </Panel>
        <Panel header="Output Mapping" key="output">
          <Form.Item
            help={outputMappingError ? outputMappingError : 'Map sub-workflow output to parent context'}
            validateStatus={outputMappingError ? 'error' : undefined}
          >
            <LazyJsonCodeEditor
              id={`${idPrefix}-subworkflow-output-mapping`}
              value={outputMappingRaw}
              onChange={handleOutputMappingChange}
              readOnly={readOnly}
              height={180}
              path={`${idPrefix}-subworkflow-output-mapping.json`}
            />
          </Form.Item>
        </Panel>
      </Collapse>
    </>
  )
}

const PropertyEditor = ({
  nodeId,
  nodeData,
  onNodeUpdate,
  onNodeDelete,
  onNodeDuplicate,
  operationTemplates = [],
  availableWorkflows = [],
  availableDecisions = [],
  readOnly = false
}: PropertyEditorProps) => {
  const [localData, setLocalData] = useState<WorkflowNodeData | null>(null)
  const idPrefix = nodeId ? `workflow-${nodeId}` : 'workflow-node'

  // Sync local state with props
  useEffect(() => {
    setLocalData(nodeData)
  }, [nodeData])

  if (!nodeId || !localData) {
    return (
      <Card className="property-editor empty">
        <div className="empty-state">
          <Text type="secondary">Select a scheme step to edit its contract</Text>
        </div>
      </Card>
    )
  }

  const nodeInfo = NODE_TYPE_INFO[localData.nodeType]
  const compatibilityReadOnlyReason = resolveCompatibilityReadOnlyReason(localData)
  const effectiveReadOnly = readOnly || compatibilityReadOnlyReason !== null

  const handleLabelChange = (label: string) => {
    setLocalData({ ...localData, label })
    onNodeUpdate(nodeId, { label })
  }

  const handleConfigChange = (config: NodeConfig) => {
    setLocalData({ ...localData, config })
    onNodeUpdate(nodeId, { config })
  }

  const handleIoChange = (io: OperationIO) => {
    setLocalData({ ...localData, io })
    onNodeUpdate(nodeId, { io })
  }

  const handleDecisionChange = (decisionRef?: DecisionRef) => {
    const currentConfig = { ...(localData.config || {}) }
    const currentCompiledExpression = localData.decisionRef
      ? `{{ decisions.${localData.decisionRef.decision_key} }}`
      : undefined
    let nextConfig: NodeConfig

    if (decisionRef) {
      nextConfig = {
        ...currentConfig,
        expression: `{{ decisions.${decisionRef.decision_key} }}`,
      }
    } else if (
      currentCompiledExpression
      && currentConfig.expression === currentCompiledExpression
    ) {
      const { expression: _expression, ...restConfig } = currentConfig
      nextConfig = restConfig
    } else {
      nextConfig = currentConfig
    }

    setLocalData({ ...localData, decisionRef, config: nextConfig })
    onNodeUpdate(nodeId, { decisionRef, config: nextConfig })
  }

  const handleTemplateChange = (templateId?: string) => {
    const normalizedTemplateId = typeof templateId === 'string' && templateId.trim()
      ? templateId.trim()
      : undefined
    const selectedTemplate = normalizedTemplateId
      ? operationTemplates.find((template) => template.id === normalizedTemplateId)
      : undefined
    const operationRef: OperationRef | undefined = normalizedTemplateId
      ? (() => {
          const exposureId = typeof selectedTemplate?.exposure_id === 'string' && selectedTemplate.exposure_id.trim()
            ? selectedTemplate.exposure_id.trim()
            : undefined
          const revision = typeof selectedTemplate?.exposure_revision === 'number' && selectedTemplate.exposure_revision > 0
            ? selectedTemplate.exposure_revision
            : undefined
          if (exposureId && revision !== undefined) {
            return {
              alias: normalizedTemplateId,
              binding_mode: 'pinned_exposure',
              template_exposure_id: exposureId,
              template_exposure_revision: revision,
            }
          }
          return {
            alias: normalizedTemplateId,
            binding_mode: 'alias_latest',
            ...(exposureId ? { template_exposure_id: exposureId } : {}),
            ...(revision !== undefined ? { template_exposure_revision: revision } : {}),
          }
        })()
      : undefined

    setLocalData({ ...localData, templateId: normalizedTemplateId, operationRef })
    onNodeUpdate(nodeId, { templateId: normalizedTemplateId, operationRef })
  }

  const handleDelete = () => {
    onNodeDelete(nodeId)
  }

  const handleDuplicate = () => {
    if (onNodeDuplicate) {
      onNodeDuplicate(nodeId)
    }
  }

  // Render type-specific form
  const renderTypeForm = () => {
    const config = localData.config || {}

    switch (localData.nodeType) {
      case 'operation':
        return (
          <OperationForm
            config={config}
            io={localData.io}
            templateId={localData.templateId}
            onTemplateChange={handleTemplateChange}
            onChange={handleConfigChange}
            onIoChange={handleIoChange}
            templates={operationTemplates}
            readOnly={effectiveReadOnly}
            idPrefix={idPrefix}
          />
        )
      case 'condition':
        return (
          <ConditionForm
            config={config}
            decisionRef={localData.decisionRef}
            onChange={handleConfigChange}
            onDecisionChange={handleDecisionChange}
            availableDecisions={availableDecisions}
            readOnly={effectiveReadOnly}
            idPrefix={idPrefix}
          />
        )
      case 'parallel':
        return (
          <ParallelForm
            config={config}
            onChange={handleConfigChange}
            readOnly={effectiveReadOnly}
            idPrefix={idPrefix}
          />
        )
      case 'loop':
        return (
          <LoopForm
            config={config}
            onChange={handleConfigChange}
            readOnly={effectiveReadOnly}
            idPrefix={idPrefix}
          />
        )
      case 'subworkflow':
        return (
          <SubWorkflowForm
            config={config}
            onChange={handleConfigChange}
            workflows={availableWorkflows}
            readOnly={effectiveReadOnly}
            idPrefix={idPrefix}
          />
        )
      default:
        return null
    }
  }

  return (
    <Card className="property-editor" size="small">
      <div className="editor-header">
        <div className="node-type-badge" style={{ backgroundColor: nodeInfo.color }}>
          {nodeInfo.label}
        </div>
        <Text type="secondary" className="node-id">
          ID: {nodeId}
        </Text>
      </div>

      <Form layout="vertical" size="small">
        <Form.Item label="Step Name" required htmlFor={`${idPrefix}-node-name`}>
          <Input
            id={`${idPrefix}-node-name`}
            value={localData.label}
            placeholder="Step name"
            disabled={effectiveReadOnly}
            onChange={(e) => handleLabelChange(e.target.value)}
          />
        </Form.Item>

        <Divider style={{ margin: '12px 0' }} />

        {renderTypeForm()}
      </Form>

      {!effectiveReadOnly && (
        <>
          <Divider style={{ margin: '12px 0' }} />
          <Space>
            {onNodeDuplicate && (
              <Button
                icon={<CopyOutlined />}
                size="small"
                onClick={handleDuplicate}
              >
                Duplicate
              </Button>
            )}
            <Button
              danger
              icon={<DeleteOutlined />}
              size="small"
              onClick={handleDelete}
            >
              Delete
            </Button>
          </Space>
        </>
      )}
    </Card>
  )
}

export default PropertyEditor
