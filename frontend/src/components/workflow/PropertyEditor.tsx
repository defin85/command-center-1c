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
  OperationTemplateListItem
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
  availableWorkflows?: { id: string; name: string }[]
  // Read-only mode (monitor mode)
  readOnly?: boolean
}

// Form for Operation node
const OperationForm = ({
  config,
  templateId,
  onTemplateChange,
  onChange,
  templates,
  readOnly,
  idPrefix,
}: {
  config: NodeConfig
  templateId?: string
  onTemplateChange: (templateId?: string) => void
  onChange: (config: NodeConfig) => void
  templates: OperationTemplateListItem[]
  readOnly: boolean
  idPrefix: string
}) => (
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
  </>
)

// Form for Condition node
const ConditionForm = ({
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
    <Form.Item
      label="Expression"
      htmlFor={`${idPrefix}-condition-expression`}
      required
      help="Jinja2 expression that evaluates to true/false. Example: {{ amount > 100 }}"
    >
      <TextArea
        id={`${idPrefix}-condition-expression`}
        value={config.expression}
        placeholder="{{ variable > value }}"
        disabled={readOnly}
        rows={3}
        onChange={(e) => onChange({ ...config, expression: e.target.value })}
      />
    </Form.Item>

    <Alert
      type="info"
      message="Available variables"
      description="Use {{ variable_name }} to access context variables. Results from previous nodes are available as {{ node_id.output.field }}."
      showIcon
      style={{ marginTop: 8 }}
    />
  </>
)

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
  workflows: { id: string; name: string }[]
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
      <Form.Item label="Sub-Workflow" htmlFor={`${idPrefix}-subworkflow`} required>
        <Select
          id={`${idPrefix}-subworkflow`}
          value={config.subworkflow_id}
          placeholder="Select workflow"
          disabled={readOnly}
          showSearch
          optionFilterProp="children"
          onChange={(value) => onChange({ ...config, subworkflow_id: value })}
          options={workflows.map((w) => ({
            value: w.id,
            label: w.name
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
          <Text type="secondary">Select a node to edit its properties</Text>
        </div>
      </Card>
    )
  }

  const nodeInfo = NODE_TYPE_INFO[localData.nodeType]

  const handleLabelChange = (label: string) => {
    setLocalData({ ...localData, label })
    onNodeUpdate(nodeId, { label })
  }

  const handleConfigChange = (config: NodeConfig) => {
    setLocalData({ ...localData, config })
    onNodeUpdate(nodeId, { config })
  }

  const handleTemplateChange = (templateId?: string) => {
    setLocalData({ ...localData, templateId })
    onNodeUpdate(nodeId, { templateId })
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
            templateId={localData.templateId}
            onTemplateChange={handleTemplateChange}
            onChange={handleConfigChange}
            templates={operationTemplates}
            readOnly={readOnly}
            idPrefix={idPrefix}
          />
        )
      case 'condition':
        return (
          <ConditionForm
            config={config}
            onChange={handleConfigChange}
            readOnly={readOnly}
            idPrefix={idPrefix}
          />
        )
      case 'parallel':
        return (
          <ParallelForm
            config={config}
            onChange={handleConfigChange}
            readOnly={readOnly}
            idPrefix={idPrefix}
          />
        )
      case 'loop':
        return (
          <LoopForm
            config={config}
            onChange={handleConfigChange}
            readOnly={readOnly}
            idPrefix={idPrefix}
          />
        )
      case 'subworkflow':
        return (
          <SubWorkflowForm
            config={config}
            onChange={handleConfigChange}
            workflows={availableWorkflows}
            readOnly={readOnly}
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
        <Form.Item label="Name" required htmlFor={`${idPrefix}-node-name`}>
          <Input
            id={`${idPrefix}-node-name`}
            value={localData.label}
            placeholder="Node name"
            disabled={readOnly}
            onChange={(e) => handleLabelChange(e.target.value)}
          />
        </Form.Item>

        <Divider style={{ margin: '12px 0' }} />

        {renderTypeForm()}
      </Form>

      {!readOnly && (
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
