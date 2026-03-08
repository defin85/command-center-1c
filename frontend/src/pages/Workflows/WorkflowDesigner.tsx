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
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
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
  ValidationResult,
  OperationTemplateListItem,
} from '../../types/workflow'

// Generated API
import { getV2 } from '../../api/generated/v2/v2'
import { listOperationCatalogExposures } from '../../api/operationCatalog'

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
  operationTemplates: OperationTemplateListItem[]
}

const initialDagStructure: DAGStructure = {
  nodes: [],
  edges: []
}

const WorkflowDesigner = () => {
  const { id: templateId } = useParams<{ id?: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
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
  const isSystemManagedProjection = state.template?.is_system_managed === true
  const isRuntimeDiagnosticsSurface =
    searchParams.get('surface') === 'runtime_diagnostics' || isSystemManagedProjection
  const backTarget = isRuntimeDiagnosticsSurface
    ? '/workflows?surface=runtime_diagnostics'
    : '/workflows'
  const runtimeProjectionReadOnlyReason = state.template?.read_only_reason
    || 'System-managed runtime workflow projections are available for diagnostics only.'

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
        const response = await listOperationCatalogExposures({
          surface: 'template',
          limit: 1000,
          offset: 0,
        })
        const templates = response.exposures
          .filter((row) => row.surface === 'template')
          .map((row) => {
            const operationType = typeof row.operation_type === 'string' && row.operation_type
              ? row.operation_type
              : 'designer_cli'
            const rawRevision = (
              row as {
                exposure_revision?: number | string | null
                template_exposure_revision?: number | string | null
              }
            )
            const revisionValue = rawRevision.template_exposure_revision ?? rawRevision.exposure_revision
            const parsedRevision = Number.parseInt(String(revisionValue ?? ''), 10)
            return {
              id: String(row.alias ?? ''),
              name: String(row.name ?? ''),
              operation_type: operationType,
              exposure_id: String(row.id ?? '') || undefined,
              exposure_revision: Number.isNaN(parsedRevision) ? undefined : parsedRevision,
            }
          })
          .filter((row) => row.id && row.name)
          .sort((left, right) => left.name.localeCompare(right.name))
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
          const hasTemplateId = Object.prototype.hasOwnProperty.call(data, 'templateId')
          const hasOperationRef = Object.prototype.hasOwnProperty.call(data, 'operationRef')
          const hasIo = Object.prototype.hasOwnProperty.call(data, 'io')
          return {
            ...node,
            name: data.label ?? node.name,
            template_id: hasTemplateId ? data.templateId : node.template_id,
            operation_ref: hasOperationRef ? data.operationRef : node.operation_ref,
            io: hasIo ? data.io : node.io,
            config: data.config ?? node.config
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
          operationRef: node.operation_ref,
          io: node.io,
          config: node.config
        } as WorkflowNodeData
      })()
    : null

  // Validate workflow
  const handleValidate = async () => {
    if (isSystemManagedProjection) {
      message.info(runtimeProjectionReadOnlyReason)
      return
    }
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
    if (isSystemManagedProjection) {
      message.info(runtimeProjectionReadOnlyReason)
      return
    }
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
    if (isSystemManagedProjection) {
      message.info(runtimeProjectionReadOnlyReason)
      return
    }
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
    if (isSystemManagedProjection) {
      message.info(runtimeProjectionReadOnlyReason)
      return
    }
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
            onClick={() => navigate(backTarget)}
          >
            Back
          </Button>
          <Title level={4} className="header-title">
            {state.template ? state.template.name : 'New Workflow Scheme'}
            {state.isModified && <span className="modified-indicator">*</span>}
          </Title>
        </div>
        <Space className="header-actions">
          <Tooltip title="Validate DAG structure">
            <Button
              icon={<CheckCircleOutlined />}
              onClick={handleValidate}
              loading={state.isValidating}
              disabled={isSystemManagedProjection || !state.template?.id || state.isModified}
            >
              Validate
            </Button>
          </Tooltip>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveClick}
            loading={state.isSaving}
            disabled={isSystemManagedProjection}
          >
            Save
          </Button>
          <Button
            icon={<PlayCircleOutlined />}
            onClick={() => setExecuteModalVisible(true)}
            disabled={isSystemManagedProjection || !state.template?.is_valid}
          >
            Execute
          </Button>
        </Space>
      </Header>

      {isSystemManagedProjection ? (
        <Alert
          showIcon
          type="warning"
          message="Runtime diagnostics surface"
          description={runtimeProjectionReadOnlyReason}
          style={{ margin: '16px 16px 0' }}
        />
      ) : (
        <Alert
          showIcon
          type="info"
          message="Workflow scheme library"
          description="This editor authors reusable workflow definitions for pools. Templates stay atomic, pool bindings decide where the scheme is active, and runtime projections are compiled into diagnostics-only artifacts."
          style={{ margin: '16px 16px 0' }}
        />
      )}

      <Layout className="designer-body">
        {/* Left Sider - Node Palette */}
        <Sider width={220} className="designer-sider-left">
          {isSystemManagedProjection ? (
            <Alert
              showIcon
              type="info"
              message="Read-only runtime projection"
              description="Generated runtime projections can be inspected, but not changed from the analyst workflow surface."
              style={{ margin: 16 }}
            />
          ) : (
            <NodePalette />
          )}
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
            mode={isSystemManagedProjection ? 'monitor' : 'design'}
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
            readOnly={isSystemManagedProjection}
          />
        </Sider>
      </Layout>

      {/* Save Modal (for new workflows) */}
      <Modal
        title="Save Workflow Scheme"
        open={saveModalVisible}
        onOk={handleSave}
        onCancel={() => setSaveModalVisible(false)}
        confirmLoading={state.isSaving}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="Scheme Name"
            rules={[{ required: true, message: 'Please enter a name' }]}
            htmlFor="workflow-name"
          >
            <Input id="workflow-name" placeholder="Services Publication" />
          </Form.Item>
          <Form.Item name="description" label="Description" htmlFor="workflow-description">
            <Input.TextArea
              id="workflow-description"
              rows={3}
              placeholder="Reusable analyst-facing distribution or publication scheme"
            />
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
