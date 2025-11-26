/**
 * PropertyEditor - Panel for editing selected node properties.
 *
 * Features:
 * - Dynamic form based on node type
 * - Validation for required fields
 * - Template selection for operations
 * - Expression editor for conditions
 */

import { useEffect, useState } from 'react'
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
  onChange,
  templates,
  readOnly
}: {
  config: NodeConfig
  onChange: (config: NodeConfig) => void
  templates: OperationTemplateListItem[]
  readOnly: boolean
}) => (
  <>
    <Form.Item label="Template" required>
      <Select
        value={config.timeout ? undefined : undefined}
        placeholder="Select operation template"
        disabled={readOnly}
        showSearch
        optionFilterProp="children"
        onChange={(_value) => onChange({ ...config })}
        options={templates.map((t) => ({
          value: t.id,
          label: `${t.name} (${t.operation_type})`
        }))}
      />
    </Form.Item>

    <Form.Item label="Timeout (seconds)">
      <InputNumber
        value={config.timeout}
        min={1}
        max={3600}
        disabled={readOnly}
        style={{ width: '100%' }}
        onChange={(value) => onChange({ ...config, timeout: value || undefined })}
      />
    </Form.Item>

    <Form.Item label="Retries">
      <InputNumber
        value={config.retries}
        min={0}
        max={10}
        disabled={readOnly}
        style={{ width: '100%' }}
        onChange={(value) => onChange({ ...config, retries: value || undefined })}
      />
    </Form.Item>

    <Form.Item label="Retry Delay (seconds)">
      <InputNumber
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
  readOnly
}: {
  config: NodeConfig
  onChange: (config: NodeConfig) => void
  readOnly: boolean
}) => (
  <>
    <Form.Item
      label="Expression"
      required
      help="Jinja2 expression that evaluates to true/false. Example: {{ amount > 100 }}"
    >
      <TextArea
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
  readOnly
}: {
  config: NodeConfig
  onChange: (config: NodeConfig) => void
  readOnly: boolean
}) => (
  <>
    <Form.Item label="Parallel Nodes" help="Node IDs to execute in parallel">
      <Select
        mode="tags"
        value={config.parallel_nodes || []}
        placeholder="Enter node IDs"
        disabled={readOnly}
        onChange={(value) => onChange({ ...config, parallel_nodes: value })}
      />
    </Form.Item>

    <Form.Item label="Wait For">
      <Select
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

    <Form.Item label="Timeout (seconds)">
      <InputNumber
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
  readOnly
}: {
  config: NodeConfig
  onChange: (config: NodeConfig) => void
  readOnly: boolean
}) => (
  <>
    <Form.Item label="Loop Mode" required>
      <Select
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
      <Form.Item label="Loop Count">
        <InputNumber
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
        help="Jinja2 expression. Loop continues while true."
      >
        <TextArea
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
        help="Jinja2 expression that returns a list."
      >
        <TextArea
          value={config.loop_items}
          placeholder="{{ databases }}"
          disabled={readOnly}
          rows={2}
          onChange={(e) => onChange({ ...config, loop_items: e.target.value })}
        />
      </Form.Item>
    )}

    <Form.Item label="Max Iterations" help="Safety limit">
      <InputNumber
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
  readOnly
}: {
  config: NodeConfig
  onChange: (config: NodeConfig) => void
  workflows: { id: string; name: string }[]
  readOnly: boolean
}) => (
  <>
    <Form.Item label="Sub-Workflow" required>
      <Select
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
        <Form.Item help="Map parent context to sub-workflow input">
          <TextArea
            value={JSON.stringify(config.input_mapping || {}, null, 2)}
            placeholder='{"sub_var": "{{ parent_var }}"}'
            disabled={readOnly}
            rows={4}
            onChange={(e) => {
              try {
                const mapping = JSON.parse(e.target.value)
                onChange({ ...config, input_mapping: mapping })
              } catch {
                // Invalid JSON, ignore
              }
            }}
          />
        </Form.Item>
      </Panel>
      <Panel header="Output Mapping" key="output">
        <Form.Item help="Map sub-workflow output to parent context">
          <TextArea
            value={JSON.stringify(config.output_mapping || {}, null, 2)}
            placeholder='{"parent_var": "{{ sub_result }}"}'
            disabled={readOnly}
            rows={4}
            onChange={(e) => {
              try {
                const mapping = JSON.parse(e.target.value)
                onChange({ ...config, output_mapping: mapping })
              } catch {
                // Invalid JSON, ignore
              }
            }}
          />
        </Form.Item>
      </Panel>
    </Collapse>
  </>
)

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
            onChange={handleConfigChange}
            templates={operationTemplates}
            readOnly={readOnly}
          />
        )
      case 'condition':
        return (
          <ConditionForm
            config={config}
            onChange={handleConfigChange}
            readOnly={readOnly}
          />
        )
      case 'parallel':
        return (
          <ParallelForm
            config={config}
            onChange={handleConfigChange}
            readOnly={readOnly}
          />
        )
      case 'loop':
        return (
          <LoopForm
            config={config}
            onChange={handleConfigChange}
            readOnly={readOnly}
          />
        )
      case 'subworkflow':
        return (
          <SubWorkflowForm
            config={config}
            onChange={handleConfigChange}
            workflows={availableWorkflows}
            readOnly={readOnly}
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
        <Form.Item label="Name" required>
          <Input
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
