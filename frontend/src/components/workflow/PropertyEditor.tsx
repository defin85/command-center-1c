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
import { useWorkflowTranslation } from '../../i18n'
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
import { trackUiAction } from '../../observability/uiActionJournal'
import { LazyJsonCodeEditor } from '../code/LazyJsonCodeEditor'
import { DecisionRevisionSelect } from './DecisionRevisionSelect'
import { WorkflowRevisionSelect } from './WorkflowRevisionSelect'
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
  t,
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
  t: (key: string, options?: Record<string, unknown>) => string
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
      <Form.Item label={t('propertyEditor.operation.fields.template')} htmlFor={`${idPrefix}-operation-template`} required>
        <Select
          id={`${idPrefix}-operation-template`}
          value={templateId}
          placeholder={t('propertyEditor.operation.placeholders.selectTemplate')}
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
        <Card size="small" title={t('propertyEditor.operation.executionContract.title')} style={{ marginBottom: 12 }}>
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            <Text strong>{executionContract.capability.id}</Text>
            <Text type="secondary">
              {`${executionContract.capability.executorKind} -> ${executionContract.capability.targetEntity}`}
            </Text>
            <Text>
              {`Input (${executionContract.input.mode}): required ${formatExecutionContractList(executionContract.input.requiredParameters)}`}
            </Text>
            <Text>
              {t('propertyEditor.operation.executionContract.optionalInputs', {
                value: formatExecutionContractList(executionContract.input.optionalParameters),
              })}
            </Text>
            <Text>
              {t('propertyEditor.operation.executionContract.outputPath', {
                value: executionContract.output.resultPath,
              })}
            </Text>
            <Text>
              {t('propertyEditor.operation.executionContract.sideEffects', {
                effectKind: executionContract.sideEffect.effectKind,
                executionMode: executionContract.sideEffect.executionMode,
              })}
            </Text>
            {executionContract.sideEffect.summary && (
              <Text>{executionContract.sideEffect.summary}</Text>
            )}
            <Text type="secondary">
              {t('propertyEditor.operation.executionContract.bindingProvenance', {
                alias: executionContract.provenance.alias,
                revision: executionContract.provenance.exposureRevision ?? '?',
              })}
            </Text>
          </Space>
        </Card>
      )}

      <Form.Item label={t('propertyEditor.operation.fields.timeoutSeconds')} htmlFor={`${idPrefix}-operation-timeout`}>
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

      <Form.Item label={t('propertyEditor.operation.fields.retries')} htmlFor={`${idPrefix}-operation-retries`}>
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

      <Form.Item label={t('propertyEditor.operation.fields.retryDelaySeconds')} htmlFor={`${idPrefix}-operation-retry-delay`}>
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
        label={t('propertyEditor.operation.fields.dataFlowMode')}
        htmlFor={`${idPrefix}-operation-io-mode`}
        help={t('propertyEditor.operation.fields.dataFlowModeHelp')}
      >
        <Select
          id={`${idPrefix}-operation-io-mode`}
          value={normalizedIo.mode}
          disabled={readOnly}
          onChange={(value) => handleIoModeChange(value as OperationIOMode)}
          options={[
            { value: 'implicit_legacy', label: t('propertyEditor.operation.ioModes.implicitLegacy') },
            { value: 'explicit_strict', label: t('propertyEditor.operation.ioModes.explicitStrict') },
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
              message={t('propertyEditor.operation.missingRequiredMappings', { value: missingRequiredMappings.join(', ') })}
              description={t('propertyEditor.operation.missingRequiredMappingsDescription')}
            />
          )}
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message={t('propertyEditor.operation.mappingRules.title')}
            description={t('propertyEditor.operation.mappingRules.description')}
          />
          <Collapse ghost>
            <Panel header={t('propertyEditor.operation.mappingPanels.input.title')} key="operation-io-input">
              <Form.Item
                help={inputMappingError ? inputMappingError : t('propertyEditor.operation.mappingPanels.input.help')}
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
            <Panel header={t('propertyEditor.operation.mappingPanels.output.title')} key="operation-io-output">
              <Form.Item
                help={outputMappingError ? outputMappingError : t('propertyEditor.operation.mappingPanels.output.help')}
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
  t,
}: {
  config: NodeConfig
  decisionRef?: DecisionRef
  onChange: (config: NodeConfig) => void
  onDecisionChange: (decisionRef?: DecisionRef) => void
  availableDecisions: AvailableDecisionRevision[]
  readOnly: boolean
  idPrefix: string
  t: (key: string, options?: Record<string, unknown>) => string
}) => {
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
  const compiledExpression = decisionRef
    ? `{{ decisions.${decisionRef.decision_key} }}`
    : ''

  return (
    <>
      <Form.Item
        label={t('propertyEditor.condition.fields.decisionTable')}
        htmlFor={`${idPrefix}-condition-decision`}
        help={t('propertyEditor.condition.fields.decisionTableHelp')}
      >
        <DecisionRevisionSelect
          id={`${idPrefix}-condition-decision`}
          testId={`${idPrefix}-condition-decision`}
          currentDecision={decisionRef}
          availableDecisions={availableDecisions}
          placeholder={t('propertyEditor.condition.placeholders.selectDecisionTable')}
          disabled={readOnly}
          allowClear
          onChange={onDecisionChange}
        />
      </Form.Item>

      {decisionRef ? (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message={t('propertyEditor.condition.messages.managedByDecisionTable')}
            description={
              selectedDecision
                ? t('propertyEditor.condition.messages.managedByDecisionTableSelected', {
                    name: selectedDecision.name,
                    key: selectedDecision.decisionKey,
                  })
                : t('propertyEditor.condition.messages.managedByDecisionTableFallback')
            }
          />
          <Form.Item
            label={t('propertyEditor.condition.fields.compiledExpression')}
            htmlFor={`${idPrefix}-condition-expression`}
            help={t('propertyEditor.condition.fields.compiledExpressionHelp')}
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
            label={t('propertyEditor.condition.fields.legacyExpression')}
            htmlFor={`${idPrefix}-condition-expression`}
            required
            help={t('propertyEditor.condition.fields.legacyExpressionHelp')}
          >
            <TextArea
              id={`${idPrefix}-condition-expression`}
              data-testid={`${idPrefix}-condition-expression`}
              value={config.expression}
              placeholder={t('propertyEditor.condition.placeholders.legacyExpression')}
              disabled={readOnly}
              rows={3}
              onChange={(e) => onChange({ ...config, expression: e.target.value })}
            />
          </Form.Item>

          <Alert
            type="warning"
            message={t('propertyEditor.condition.messages.legacyMode')}
            description={t('propertyEditor.condition.messages.legacyModeDescription')}
            showIcon
            style={{ marginTop: 8 }}
          />
        </>
      ) : (
        <Alert
          type="info"
          showIcon
          message={t('propertyEditor.condition.messages.selectPinnedDecision')}
          description={t('propertyEditor.condition.messages.selectPinnedDecisionDescription')}
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
  t,
}: {
  config: NodeConfig
  onChange: (config: NodeConfig) => void
  readOnly: boolean
  idPrefix: string
  t: (key: string, options?: Record<string, unknown>) => string
}) => (
  <>
    <Alert
      type="warning"
      showIcon
      style={{ marginBottom: 12 }}
      message={t('propertyEditor.runtimeOnly.message')}
      description={t('propertyEditor.runtimeOnly.description')}
    />
    <Form.Item label={t('propertyEditor.parallel.fields.parallelNodes')} htmlFor={`${idPrefix}-parallel-nodes`} help={t('propertyEditor.parallel.fields.parallelNodesHelp')}>
      <Select
        id={`${idPrefix}-parallel-nodes`}
        mode="tags"
        value={config.parallel_nodes || []}
        placeholder={t('propertyEditor.parallel.placeholders.parallelNodes')}
        disabled={readOnly}
        onChange={(value) => onChange({ ...config, parallel_nodes: value })}
      />
    </Form.Item>

    <Form.Item label={t('propertyEditor.parallel.fields.waitFor')} htmlFor={`${idPrefix}-parallel-wait-for`}>
      <Select
        id={`${idPrefix}-parallel-wait-for`}
        value={config.wait_for || 'all'}
        disabled={readOnly}
        onChange={(value) => onChange({ ...config, wait_for: value })}
        options={[
          { value: 'all', label: t('propertyEditor.parallel.waitOptions.all') },
          { value: 'any', label: t('propertyEditor.parallel.waitOptions.any') },
          { value: 1, label: t('propertyEditor.parallel.waitOptions.one') },
          { value: 2, label: t('propertyEditor.parallel.waitOptions.two') },
          { value: 3, label: t('propertyEditor.parallel.waitOptions.three') }
        ]}
      />
    </Form.Item>

    <Form.Item label={t('propertyEditor.parallel.fields.timeoutSeconds')} htmlFor={`${idPrefix}-parallel-timeout`}>
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
  t,
}: {
  config: NodeConfig
  onChange: (config: NodeConfig) => void
  readOnly: boolean
  idPrefix: string
  t: (key: string, options?: Record<string, unknown>) => string
}) => (
  <>
    <Alert
      type="warning"
      showIcon
      style={{ marginBottom: 12 }}
      message={t('propertyEditor.runtimeOnly.message')}
      description={t('propertyEditor.runtimeOnly.description')}
    />
    <Form.Item label={t('propertyEditor.loop.fields.loopMode')} htmlFor={`${idPrefix}-loop-mode`} required>
      <Select
        id={`${idPrefix}-loop-mode`}
        value={config.loop_mode || 'count'}
        disabled={readOnly}
        onChange={(value) => onChange({ ...config, loop_mode: value })}
        options={[
          { value: 'count', label: t('propertyEditor.loop.modeOptions.count') },
          { value: 'while', label: t('propertyEditor.loop.modeOptions.while') },
          { value: 'foreach', label: t('propertyEditor.loop.modeOptions.foreach') }
        ]}
      />
    </Form.Item>

    {config.loop_mode === 'count' && (
      <Form.Item label={t('propertyEditor.loop.fields.loopCount')} htmlFor={`${idPrefix}-loop-count`}>
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
        label={t('propertyEditor.loop.fields.loopCondition')}
        htmlFor={`${idPrefix}-loop-condition`}
        help={t('propertyEditor.loop.fields.loopConditionHelp')}
      >
        <TextArea
          id={`${idPrefix}-loop-condition`}
          value={config.loop_condition}
          placeholder={t('propertyEditor.loop.placeholders.loopCondition')}
          disabled={readOnly}
          rows={2}
          onChange={(e) => onChange({ ...config, loop_condition: e.target.value })}
        />
      </Form.Item>
    )}

    {config.loop_mode === 'foreach' && (
      <Form.Item
        label={t('propertyEditor.loop.fields.itemsExpression')}
        htmlFor={`${idPrefix}-loop-items`}
        help={t('propertyEditor.loop.fields.itemsExpressionHelp')}
      >
        <TextArea
          id={`${idPrefix}-loop-items`}
          value={config.loop_items}
          placeholder={t('propertyEditor.loop.placeholders.itemsExpression')}
          disabled={readOnly}
          rows={2}
          onChange={(e) => onChange({ ...config, loop_items: e.target.value })}
        />
      </Form.Item>
    )}

    <Form.Item label={t('propertyEditor.loop.fields.maxIterations')} htmlFor={`${idPrefix}-loop-max-iterations`} help={t('propertyEditor.loop.fields.maxIterationsHelp')}>
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
  t,
}: {
  config: NodeConfig
  onChange: (config: NodeConfig) => void
  workflows: AvailableWorkflowRevision[]
  readOnly: boolean
  idPrefix: string
  t: (key: string, options?: Record<string, unknown>) => string
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
        label={t('propertyEditor.subworkflow.fields.subWorkflow')}
        htmlFor={`${idPrefix}-subworkflow`}
        required
        help={t('propertyEditor.subworkflow.fields.subWorkflowHelp')}
      >
        <WorkflowRevisionSelect
          id={`${idPrefix}-subworkflow`}
          testId={`${idPrefix}-subworkflow`}
          currentWorkflow={{
            workflowDefinitionKey: config.subworkflow_ref?.workflow_definition_key,
            workflowRevisionId: config.subworkflow_ref?.workflow_revision_id ?? config.subworkflow_id,
            workflowRevision: config.subworkflow_ref?.workflow_revision,
          }}
          workflows={workflows}
          placeholder={t('propertyEditor.subworkflow.placeholders.selectWorkflow')}
          disabled={readOnly}
          onChange={(selectedWorkflow) => {
            if (!selectedWorkflow) {
              onChange({
                ...config,
                subworkflow_id: undefined,
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
        />
      </Form.Item>

      <Collapse ghost>
        <Panel header={t('propertyEditor.subworkflow.mappingPanels.input.title')} key="input">
            <Form.Item
              help={inputMappingError ? inputMappingError : t('propertyEditor.subworkflow.mappingPanels.input.help')}
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
        <Panel header={t('propertyEditor.subworkflow.mappingPanels.output.title')} key="output">
          <Form.Item
            help={outputMappingError ? outputMappingError : t('propertyEditor.subworkflow.mappingPanels.output.help')}
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
  const { t } = useWorkflowTranslation()
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
          <Text type="secondary">{t('propertyEditor.emptyState')}</Text>
        </div>
      </Card>
    )
  }

  const nodeInfo = NODE_TYPE_INFO[localData.nodeType]
  const compatibilityReadOnlyReason = resolveCompatibilityReadOnlyReason(localData)
  const effectiveReadOnly = readOnly || compatibilityReadOnlyReason !== null
  const trackNodeAction = <T,>(actionName: string, handler: () => T) => (
    trackUiAction({
      actionKind: 'operator.action',
      actionName,
      context: {
        node_id: nodeId,
        node_type: localData.nodeType,
      },
    }, handler)
  )

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
    void trackNodeAction('Delete workflow node', () => onNodeDelete(nodeId))
  }

  const handleDuplicate = () => {
    if (onNodeDuplicate) {
      void trackNodeAction('Duplicate workflow node', () => onNodeDuplicate(nodeId))
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
            t={t}
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
            t={t}
          />
        )
      case 'parallel':
        return (
          <ParallelForm
            config={config}
            onChange={handleConfigChange}
            readOnly={effectiveReadOnly}
            idPrefix={idPrefix}
            t={t}
          />
        )
      case 'loop':
        return (
          <LoopForm
            config={config}
            onChange={handleConfigChange}
            readOnly={effectiveReadOnly}
            idPrefix={idPrefix}
            t={t}
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
            t={t}
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
          {t(`palette.nodes.${localData.nodeType}.label`)}
        </div>
        <Text type="secondary" className="node-id">
          {t('propertyEditor.labels.nodeId', { value: nodeId })}
        </Text>
      </div>

      <Form layout="vertical" size="small">
        <Form.Item label={t('propertyEditor.fields.stepName')} required htmlFor={`${idPrefix}-node-name`}>
          <Input
            id={`${idPrefix}-node-name`}
            value={localData.label}
            placeholder={t('propertyEditor.placeholders.stepName')}
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
                {t('propertyEditor.actions.duplicate')}
              </Button>
            )}
            <Button
              danger
              icon={<DeleteOutlined />}
              size="small"
              onClick={handleDelete}
            >
              {t('propertyEditor.actions.delete')}
            </Button>
          </Space>
        </>
      )}
    </Card>
  )
}

export default PropertyEditor
