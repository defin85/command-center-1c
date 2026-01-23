/**
 * WorkflowDesigner - Page for creating and editing workflow templates.
 *
 * Features:
 * - Visual workflow canvas with React Flow
 * - Node palette for drag & drop
 * - Property editor for selected node
 * - Save/Load workflow templates via API
 * - Validation before save
 *
 * Migration: Uses generated API directly with transform utilities.
 * Legacy adapter (api/adapters/workflows) is no longer used here.
 */

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  App,
  Layout,
  Typography,
  Button,
  Space,
  Modal,
  Input,
  Form,
  Spin,
  Alert,
  Tooltip
} from 'antd'
import {
  SaveOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  ArrowLeftOutlined
} from '@ant-design/icons'
import { WorkflowCanvas, NodePalette, PropertyEditor } from '../../components/workflow'
import { LazyJsonCodeEditor } from '../../components/code/LazyJsonCodeEditor'

// Types from types/workflow (legacy format for UI components)
import type {
  WorkflowNodeData,
  DAGStructure,
  WorkflowTemplate,
  ValidationResult
} from '../../types/workflow'

// Generated API
import { getV2 } from '../../api/generated/v2/v2'

// Transform utilities for API <-> UI type conversion
import {
  convertTemplateToLegacy,
  convertValidationToLegacy,
  convertDAGToGenerated,
} from '../../utils/workflowTransforms'

import './WorkflowDesigner.css'

// Initialize generated API
const api = getV2()

const { Header, Sider, Content } = Layout
const { Title } = Typography

interface WorkflowDesignerState {
  template: WorkflowTemplate | null
  dagStructure: DAGStructure
  selectedNodeId: string | null
  isModified: boolean
  isLoading: boolean
  isSaving: boolean
  isValidating: boolean
  validationResult: ValidationResult | null
  operationTemplates: { id: string; name: string; operation_type: string }[]
}

const initialDagStructure: DAGStructure = {
  nodes: [],
  edges: []
}

const WorkflowDesigner = () => {
  const { id: templateId } = useParams<{ id?: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [form] = Form.useForm()

  const [state, setState] = useState<WorkflowDesignerState>({
    template: null,
    dagStructure: initialDagStructure,
    selectedNodeId: null,
    isModified: false,
    isLoading: !!templateId,
    isSaving: false,
    isValidating: false,
    validationResult: null,
    operationTemplates: []
  })

  const [saveModalVisible, setSaveModalVisible] = useState(false)
  const [executeModalVisible, setExecuteModalVisible] = useState(false)
  const [executeInput, setExecuteInput] = useState('{}')

  // Load template if editing
  useEffect(() => {
    const loadTemplate = async () => {
      if (!templateId) return

      try {
        // Use generated API directly with transform
        const response = await api.getWorkflowsGetWorkflow({ workflow_id: templateId })
        const template = convertTemplateToLegacy(response.workflow)
        setState((prev) => ({
          ...prev,
          template,
          dagStructure: template.dag_structure,
          isLoading: false
        }))
        form.setFieldsValue({
          name: template.name,
          description: template.description
        })
      } catch (_error) {
        message.error('Failed to load workflow template')
        setState((prev) => ({ ...prev, isLoading: false }))
      }
    }

    loadTemplate()
  }, [templateId, form, message])

  // Load operation templates
  useEffect(() => {
    const loadOperationTemplates = async () => {
      try {
        const response = await api.getTemplatesListTemplates({ limit: 1000 })
        const templates = response.templates.map((t) => ({
          id: t.id,
          name: t.name,
          operation_type: t.operation_type,
        }))
        setState((prev) => ({
          ...prev,
          operationTemplates: templates,
        }))
      } catch (error) {
        console.error('Failed to load operation templates:', error)
      }
    }

    loadOperationTemplates()
  }, [])

  // Handle DAG change
  const handleDagChange = useCallback((dag: DAGStructure) => {
    setState((prev) => ({
      ...prev,
      dagStructure: dag,
      isModified: true,
      validationResult: null
    }))
  }, [])

  // Handle node selection
  const handleNodeSelect = useCallback((nodeId: string | null) => {
    setState((prev) => ({ ...prev, selectedNodeId: nodeId }))
  }, [])

  // Handle node update from PropertyEditor
  const handleNodeUpdate = useCallback((nodeId: string, data: Partial<WorkflowNodeData>) => {
    setState((prev) => {
      const updatedNodes = prev.dagStructure.nodes.map((node) => {
        if (node.id === nodeId) {
          return {
            ...node,
            name: data.label || node.name,
            template_id: data.templateId || node.template_id,
            config: data.config || node.config
          }
        }
        return node
      })

      return {
        ...prev,
        dagStructure: {
          ...prev.dagStructure,
          nodes: updatedNodes
        },
        isModified: true,
        validationResult: null
      }
    })
  }, [])

  // Handle node delete from PropertyEditor
  const handleNodeDelete = useCallback((nodeId: string) => {
    setState((prev) => {
      const updatedNodes = prev.dagStructure.nodes.filter((n) => n.id !== nodeId)
      const updatedEdges = prev.dagStructure.edges.filter(
        (e) => e.from !== nodeId && e.to !== nodeId
      )

      return {
        ...prev,
        dagStructure: {
          nodes: updatedNodes,
          edges: updatedEdges
        },
        selectedNodeId: null,
        isModified: true,
        validationResult: null
      }
    })
  }, [])

  // Get selected node data
  const selectedNodeData = state.selectedNodeId
    ? (() => {
        const node = state.dagStructure.nodes.find((n) => n.id === state.selectedNodeId)
        if (!node) return null
        return {
          label: node.name,
          nodeType: node.type,
          templateId: node.template_id,
          config: node.config
        } as WorkflowNodeData
      })()
    : null

  // Validate workflow
  const handleValidate = async () => {
    if (!state.template?.id) {
      message.warning('Save the workflow first to validate')
      return
    }
    if (state.isModified) {
      message.warning('Save the workflow first to validate')
      return
    }

    setState((prev) => ({ ...prev, isValidating: true }))

    try {
      // Use generated API directly with transform
      const response = await api.postWorkflowsValidateWorkflow({ workflow_id: state.template.id })
      const result = convertValidationToLegacy(response)
      setState((prev) => ({
        ...prev,
        validationResult: result,
        isValidating: false
      }))

      if (result.is_valid) {
        message.success('Workflow is valid!')
      } else {
        message.error(`Validation failed: ${result.errors.length} error(s)`)
      }
    } catch (_error) {
      message.error('Validation failed')
      setState((prev) => ({ ...prev, isValidating: false }))
    }
  }

  // Save workflow
  const handleSave = async () => {
    try {
      const values = await form.validateFields()

      setState((prev) => ({ ...prev, isSaving: true }))

      // Convert DAG to generated format for API
      // Use type assertion because generated type uses { [key: string]: unknown }
      const dagStructureForApi = convertDAGToGenerated(state.dagStructure) as unknown as { [key: string]: unknown }

      let savedTemplate: WorkflowTemplate

      if (state.template?.id) {
        // Update existing - use generated API directly
        const response = await api.postWorkflowsUpdateWorkflow({
          workflow_id: state.template.id,
          name: values.name,
          description: values.description,
          dag_structure: dagStructureForApi,
          workflow_type: 'complex',
        })
        savedTemplate = convertTemplateToLegacy(response.workflow)
        message.success('Workflow saved successfully')
      } else {
        // Create new - use generated API directly
        const response = await api.postWorkflowsCreateWorkflow({
          name: values.name,
          description: values.description,
          dag_structure: dagStructureForApi,
          workflow_type: 'complex',
        })
        savedTemplate = convertTemplateToLegacy(response.workflow)
        message.success('Workflow created successfully')
        // Navigate to edit URL
        navigate(`/workflows/${savedTemplate.id}`, { replace: true })
      }

      setState((prev) => ({
        ...prev,
        template: savedTemplate,
        isModified: false,
        isSaving: false
      }))

      setSaveModalVisible(false)
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } }
      message.error(axiosError.response?.data?.detail || 'Failed to save workflow')
      setState((prev) => ({ ...prev, isSaving: false }))
    }
  }

  // Execute workflow
  const handleExecute = async () => {
    if (!state.template?.id) {
      message.warning('Save the workflow first')
      return
    }

    if (!state.template.is_valid) {
      message.warning('Validate the workflow first')
      return
    }

    try {
      const inputContext = JSON.parse(executeInput)
      // Use generated API directly
      const response = await api.postWorkflowsExecuteWorkflow({
        workflow_id: state.template.id,
        input_context: inputContext,
        mode: 'async',
      })

      message.success('Workflow execution started')
      setExecuteModalVisible(false)

      // Navigate to monitor page
      navigate(`/workflows/executions/${response.execution_id}`)
    } catch (error: unknown) {
      if (error instanceof SyntaxError) {
        message.error('Invalid JSON input')
      } else {
        const axiosError = error as { response?: { data?: { detail?: string } } }
        message.error(axiosError.response?.data?.detail || 'Failed to execute workflow')
      }
    }
  }

  // Handle save button click
  const handleSaveClick = () => {
    if (!state.template) {
      // New workflow - show modal for name
      setSaveModalVisible(true)
    } else {
      // Existing workflow - save directly
      handleSave()
    }
  }

  if (state.isLoading) {
    return (
      <div className="workflow-designer-loading">
        <Spin size="large" tip="Loading workflow\u2026">
          <div style={{ minHeight: 200 }} />
        </Spin>
      </div>
    )
  }

  return (
    <Layout className="workflow-designer">
      {/* Header */}
      <Header className="designer-header">
        <div className="header-left">
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/workflows')}
          >
            Back
          </Button>
          <Title level={4} className="header-title">
            {state.template ? state.template.name : 'New Workflow'}
            {state.isModified && <span className="modified-indicator">*</span>}
          </Title>
        </div>
        <Space className="header-actions">
          <Tooltip title="Validate DAG structure">
            <Button
              icon={<CheckCircleOutlined />}
              onClick={handleValidate}
              loading={state.isValidating}
              disabled={!state.template?.id || state.isModified}
            >
              Validate
            </Button>
          </Tooltip>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveClick}
            loading={state.isSaving}
          >
            Save
          </Button>
          <Button
            icon={<PlayCircleOutlined />}
            onClick={() => setExecuteModalVisible(true)}
            disabled={!state.template?.is_valid}
          >
            Execute
          </Button>
        </Space>
      </Header>

      <Layout className="designer-body">
        {/* Left Sider - Node Palette */}
        <Sider width={220} className="designer-sider-left">
          <NodePalette />
        </Sider>

        {/* Main Content - Canvas */}
        <Content className="designer-content">
          {state.validationResult && !state.validationResult.is_valid && (
            <Alert
              type="error"
              message="Validation Errors"
              description={
                <ul>
                  {state.validationResult.errors.map((e, i) => (
                    <li key={i}>{e.message}</li>
                  ))}
                </ul>
              }
              closable
              onClose={() => setState((prev) => ({ ...prev, validationResult: null }))}
              className="validation-alert"
            />
          )}
          <WorkflowCanvas
            dagStructure={state.dagStructure}
            mode="design"
            onDagChange={handleDagChange}
            onNodeSelect={handleNodeSelect}
          />
        </Content>

        {/* Right Sider - Property Editor */}
        <Sider width={300} className="designer-sider-right">
          <PropertyEditor
            nodeId={state.selectedNodeId}
            nodeData={selectedNodeData}
            onNodeUpdate={handleNodeUpdate}
            onNodeDelete={handleNodeDelete}
            operationTemplates={state.operationTemplates}
          />
        </Sider>
      </Layout>

      {/* Save Modal (for new workflows) */}
      <Modal
        title="Save Workflow"
        open={saveModalVisible}
        onOk={handleSave}
        onCancel={() => setSaveModalVisible(false)}
        confirmLoading={state.isSaving}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="Workflow Name"
            rules={[{ required: true, message: 'Please enter a name' }]}
            htmlFor="workflow-name"
          >
            <Input id="workflow-name" placeholder="My Workflow" />
          </Form.Item>
          <Form.Item name="description" label="Description" htmlFor="workflow-description">
            <Input.TextArea id="workflow-description" rows={3} placeholder="Optional description" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Execute Modal - uses controlled input without Form to avoid useForm warning */}
      <Modal
        title="Execute Workflow"
        open={executeModalVisible}
        onOk={handleExecute}
        onCancel={() => setExecuteModalVisible(false)}
        okText="Execute"
        destroyOnHidden
      >
        {executeModalVisible && (
          <LazyJsonCodeEditor
            id="workflow-execute-input"
            title="Input Context (JSON)"
            value={executeInput}
            onChange={setExecuteInput}
            height={220}
            path="workflow-execute-input.json"
          />
        )}
        <div style={{ marginTop: 4, color: 'rgba(0, 0, 0, 0.45)', fontSize: 12 }}>
          Provide input variables for the workflow
        </div>
      </Modal>
    </Layout>
  )
}

export default WorkflowDesigner
