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

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
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
import { isDecisionAvailableByDefault } from '../../components/workflow/decisionOptions'

// Types from types/workflow (legacy format for UI components)
import type {
  WorkflowNodeData,
  DAGStructure,
  WorkflowTemplate,
  ValidationResult,
  OperationTemplateListItem,
  AvailableWorkflowRevision,
  AvailableDecisionRevision,
} from '../../types/workflow'

// Generated API
import { getV2 } from '../../api/generated/v2/v2'
import {
  listOperationCatalogExposures,
  type OperationCatalogExposureExecutionContract,
} from '../../api/operationCatalog'

// Transform utilities for API <-> UI type conversion
import {
  convertTemplateToLegacy,
  convertValidationToLegacy,
  convertDAGToGenerated,
} from '../../utils/workflowTransforms'

import './WorkflowDesigner.css'

const { Header, Sider, Content } = Layout
const { Title } = Typography

const buildRouteWithWorkflowContext = ({
  basePath,
  databaseId,
  surface,
}: {
  basePath: string
  databaseId?: string
  surface?: string
}) => {
  const params = new URLSearchParams()
  if (surface) {
    params.set('surface', surface)
  }
  if (databaseId) {
    params.set('database_id', databaseId)
  }
  const query = params.toString()
  return query ? `${basePath}?${query}` : basePath
}

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
  availableWorkflows: AvailableWorkflowRevision[]
  availableDecisions: AvailableDecisionRevision[]
}

const initialDagStructure: DAGStructure = {
  nodes: [],
  edges: []
}

const isRecord = (value: unknown): value is Record<string, unknown> => (
  value !== null && typeof value === 'object' && !Array.isArray(value)
)

const normalizeStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean)
}

const normalizeOptionalNumber = (value: unknown): number | undefined => {
  const parsed = Number.parseInt(String(value ?? ''), 10)
  return Number.isNaN(parsed) ? undefined : parsed
}

const resolveApiErrorMessage = (error: unknown, fallback: string): string => {
  if (!error || typeof error !== 'object') {
    return fallback
  }
  const payload = (error as { response?: { data?: unknown } }).response?.data
  if (!payload || typeof payload !== 'object') {
    return fallback
  }
  const detail = (payload as { detail?: unknown }).detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  const message = (payload as { error?: { message?: unknown } }).error?.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }
  return fallback
}

const mapExecutionContract = (
  contract: OperationCatalogExposureExecutionContract | undefined
): OperationTemplateListItem['executionContract'] => {
  if (!contract) {
    return undefined
  }

  const parameterSchemas = isRecord(contract.input_contract?.parameter_schemas)
    ? contract.input_contract.parameter_schemas as Record<string, Record<string, unknown>>
    : {}

  return {
    contractVersion: typeof contract.contract_version === 'string'
      ? contract.contract_version
      : '',
    capability: {
      id: typeof contract.capability?.id === 'string' ? contract.capability.id : '',
      label: typeof contract.capability?.label === 'string' ? contract.capability.label : '',
      operationType: typeof contract.capability?.operation_type === 'string'
        ? contract.capability.operation_type
        : '',
      targetEntity: typeof contract.capability?.target_entity === 'string'
        ? contract.capability.target_entity
        : '',
      executorKind: typeof contract.capability?.executor_kind === 'string'
        ? contract.capability.executor_kind
        : '',
    },
    input: {
      mode: typeof contract.input_contract?.mode === 'string'
        ? contract.input_contract.mode
        : 'params',
      requiredParameters: normalizeStringList(contract.input_contract?.required_parameters),
      optionalParameters: normalizeStringList(contract.input_contract?.optional_parameters),
      parameterSchemas,
    },
    output: {
      resultPath: typeof contract.output_contract?.result_path === 'string'
        ? contract.output_contract.result_path
        : 'result',
      supportsStructuredMapping: contract.output_contract?.supports_structured_mapping !== false,
    },
    sideEffect: {
      executionMode: typeof contract.side_effect_profile?.execution_mode === 'string'
        ? contract.side_effect_profile.execution_mode
        : 'sync',
      effectKind: typeof contract.side_effect_profile?.effect_kind === 'string'
        ? contract.side_effect_profile.effect_kind
        : 'opaque',
      ...(typeof contract.side_effect_profile?.summary === 'string'
        && contract.side_effect_profile.summary.trim()
        ? { summary: contract.side_effect_profile.summary.trim() }
        : {}),
      ...(normalizeOptionalNumber(contract.side_effect_profile?.timeout_seconds) !== undefined
        ? { timeoutSeconds: normalizeOptionalNumber(contract.side_effect_profile?.timeout_seconds) }
        : {}),
      ...(normalizeOptionalNumber(contract.side_effect_profile?.max_retries) !== undefined
        ? { maxRetries: normalizeOptionalNumber(contract.side_effect_profile?.max_retries) }
        : {}),
    },
    provenance: {
      surface: typeof contract.binding_provenance?.surface === 'string'
        ? contract.binding_provenance.surface
        : '',
      alias: typeof contract.binding_provenance?.alias === 'string'
        ? contract.binding_provenance.alias
        : '',
      exposureId: typeof contract.binding_provenance?.exposure_id === 'string'
        ? contract.binding_provenance.exposure_id
        : '',
      ...(normalizeOptionalNumber(contract.binding_provenance?.exposure_revision) !== undefined
        ? { exposureRevision: normalizeOptionalNumber(contract.binding_provenance?.exposure_revision) }
        : {}),
      definitionId: typeof contract.binding_provenance?.definition_id === 'string'
        ? contract.binding_provenance.definition_id
        : '',
      ...(typeof contract.binding_provenance?.executor_command_id === 'string'
        && contract.binding_provenance.executor_command_id.trim()
        ? { executorCommandId: contract.binding_provenance.executor_command_id.trim() }
        : {}),
    },
  }
}

const WorkflowDesigner = () => {
  const { id: templateId } = useParams<{ id?: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const api = useMemo(() => getV2(), [])

  const [state, setState] = useState<WorkflowDesignerState>({
    template: null,
    dagStructure: initialDagStructure,
    selectedNodeId: null,
    isModified: false,
    isLoading: !!templateId,
    isSaving: false,
    isValidating: false,
    validationResult: null,
    operationTemplates: [],
    availableWorkflows: [],
    availableDecisions: [],
  })

  const [saveModalVisible, setSaveModalVisible] = useState(false)
  const [executeModalVisible, setExecuteModalVisible] = useState(false)
  const [executeInput, setExecuteInput] = useState('{}')
  const dagStructureRef = useRef<DAGStructure>(initialDagStructure)
  const isSystemManagedProjection = state.template?.is_system_managed === true
  const decisionDatabaseId = String(searchParams.get('database_id') || '').trim()
  const isRuntimeDiagnosticsSurface =
    searchParams.get('surface') === 'runtime_diagnostics' || isSystemManagedProjection
  const backTarget = buildRouteWithWorkflowContext({
    basePath: '/workflows',
    databaseId: decisionDatabaseId,
    surface: isRuntimeDiagnosticsSurface ? 'runtime_diagnostics' : undefined,
  })
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
        dagStructureRef.current = template.dag_structure
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
  }, [api, templateId, form, message])

  useEffect(() => {
    const loadAuthoringReferences = async () => {
      try {
        const [workflowResponse, decisionResponse] = await Promise.all([
          api.getWorkflowsListWorkflows({ surface: 'workflow_library', limit: 1000 }),
          api.getDecisionsCollection(
            decisionDatabaseId
              ? { database_id: decisionDatabaseId }
              : undefined
          ),
        ])

        const workflowsById = new Map(
          (workflowResponse.workflows ?? []).map((workflow) => [workflow.id, workflow])
        )
        const workflowDefinitionKeyCache = new Map<string, string>()
        const resolveWorkflowDefinitionKey = (workflowId: string): string => {
          const cached = workflowDefinitionKeyCache.get(workflowId)
          if (cached) {
            return cached
          }
          const workflow = workflowsById.get(workflowId)
          if (!workflow?.parent_version) {
            workflowDefinitionKeyCache.set(workflowId, workflowId)
            return workflowId
          }
          if (!workflowsById.has(workflow.parent_version)) {
            workflowDefinitionKeyCache.set(workflowId, workflow.parent_version)
            return workflow.parent_version
          }
          const resolved = resolveWorkflowDefinitionKey(workflow.parent_version)
          workflowDefinitionKeyCache.set(workflowId, resolved)
          return resolved
        }

        const availableWorkflows = (workflowResponse.workflows ?? [])
          .filter((workflow) => workflow.is_system_managed !== true)
          .map((workflow) => ({
            id: workflow.id,
            name: workflow.name,
            workflowDefinitionKey: resolveWorkflowDefinitionKey(workflow.id),
            workflowRevisionId: workflow.id,
            workflowRevision: workflow.version_number,
          }))
          .sort((left, right) => (
            left.name.localeCompare(right.name) || left.workflowRevision - right.workflowRevision
          ))

        const availableDecisions = (decisionResponse.decisions ?? [])
          .filter((decision) => decision.is_active !== false)
          .filter((decision) => isDecisionAvailableByDefault({
            id: decision.id,
            name: decision.name,
            decisionTableId: decision.decision_table_id,
            decisionKey: decision.decision_key,
            decisionRevision: decision.decision_revision,
            metadataContext: decision.metadata_context,
            metadataCompatibility: decision.metadata_compatibility,
          }))
          .map((decision) => ({
            id: decision.id,
            name: decision.name,
            decisionTableId: decision.decision_table_id,
            decisionKey: decision.decision_key,
            decisionRevision: decision.decision_revision,
            metadataContext: decision.metadata_context,
            metadataCompatibility: decision.metadata_compatibility,
          }))
          .sort((left, right) => (
            left.name.localeCompare(right.name) || left.decisionRevision - right.decisionRevision
          ))

        setState((prev) => ({
          ...prev,
          availableWorkflows,
          availableDecisions,
        }))
      } catch (error) {
        console.error('Failed to load workflow authoring references:', error)
      }
    }

    void loadAuthoringReferences()
  }, [api, decisionDatabaseId])

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
              executionContract: mapExecutionContract(row.execution_contract),
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
    dagStructureRef.current = dag
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
          const hasDecisionRef = Object.prototype.hasOwnProperty.call(data, 'decisionRef')
          const hasIo = Object.prototype.hasOwnProperty.call(data, 'io')
          return {
            ...node,
            name: data.label ?? node.name,
            template_id: hasTemplateId ? data.templateId : node.template_id,
            operation_ref: hasOperationRef ? data.operationRef : node.operation_ref,
            decision_ref: hasDecisionRef ? data.decisionRef : node.decision_ref,
            io: hasIo ? data.io : node.io,
            config: data.config ?? node.config
          }
        }
        return node
      })
      const nextDagStructure = {
        ...prev.dagStructure,
        nodes: updatedNodes
      }
      dagStructureRef.current = nextDagStructure

      return {
        ...prev,
        dagStructure: nextDagStructure,
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
      const nextDagStructure = {
        nodes: updatedNodes,
        edges: updatedEdges
      }
      dagStructureRef.current = nextDagStructure

      return {
        ...prev,
        dagStructure: nextDagStructure,
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
          decisionRef: node.decision_ref,
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
      const dagStructureForApi = convertDAGToGenerated(dagStructureRef.current) as unknown as { [key: string]: unknown }

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
        navigate(
          buildRouteWithWorkflowContext({
            basePath: `/workflows/${savedTemplate.id}`,
            databaseId: decisionDatabaseId,
          }),
          { replace: true }
        )
      }

      setState((prev) => ({
        ...prev,
        template: savedTemplate,
        isModified: false,
        isSaving: false
      }))

      setSaveModalVisible(false)
    } catch (error: unknown) {
      message.error(resolveApiErrorMessage(error, 'Failed to save workflow'))
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
      navigate(
        buildRouteWithWorkflowContext({
          basePath: `/workflows/executions/${response.execution_id}`,
          databaseId: decisionDatabaseId,
        })
      )
    } catch (error: unknown) {
      if (error instanceof SyntaxError) {
        message.error('Invalid JSON input')
      } else {
        message.error(resolveApiErrorMessage(error, 'Failed to execute workflow'))
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
          description="Author analyst-facing workflow composition in /workflows. Use /templates for atomic operations, /decisions for versioned decision resources, and treat runtime projections as diagnostics-only artifacts."
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
            availableWorkflows={state.availableWorkflows}
            availableDecisions={state.availableDecisions}
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
