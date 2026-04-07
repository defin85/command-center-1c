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
  Alert,
  Button,
  Form,
  Grid,
  Input,
  Space,
  Spin,
  Tooltip,
  Typography,
} from 'antd'
import {
  ArrowLeftOutlined,
  AppstoreOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  SaveOutlined,
} from '@ant-design/icons'

import { WorkflowCanvas, NodePalette, PropertyEditor } from '../../components/workflow'
import { LazyJsonCodeEditor } from '../../components/code/LazyJsonCodeEditor'
import { useAuthoringReferences } from '../../api/queries/authoringReferences'
import {
  DrawerFormShell,
  ModalFormShell,
  PageHeader,
  WorkspacePage,
} from '../../components/platform'

import type {
  DAGStructure,
  OperationTemplateListItem,
  ValidationResult,
  WorkflowNodeData,
  WorkflowTemplate,
} from '../../types/workflow'

import { getV2 } from '../../api/generated/v2/v2'
import {
  listOperationCatalogExposures,
  type OperationCatalogExposureExecutionContract,
} from '../../api/operationCatalog'
import {
  convertDAGToGenerated,
  convertTemplateToLegacy,
  convertValidationToLegacy,
} from '../../utils/workflowTransforms'
import { buildRelativeHref, normalizeInternalReturnTo } from './routeState'

import './WorkflowDesigner.css'

const { Text } = Typography
const { useBreakpoint } = Grid
const DESKTOP_BREAKPOINT_PX = 992

const buildRouteWithWorkflowContext = ({
  basePath,
  databaseId,
  nodeId,
  returnTo,
  surface,
  execute,
}: {
  basePath: string
  databaseId?: string
  nodeId?: string | null
  returnTo?: string | null
  surface?: string
  execute?: boolean
}) => {
  const params = new URLSearchParams()
  if (surface) {
    params.set('surface', surface)
  }
  if (databaseId) {
    params.set('database_id', databaseId)
  }
  if (nodeId) {
    params.set('node', nodeId)
  }
  if (execute) {
    params.set('execute', 'true')
  }
  if (returnTo) {
    params.set('returnTo', returnTo)
  }
  return buildRelativeHref(basePath, params)
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
}

const initialDagStructure: DAGStructure = {
  nodes: [],
  edges: [],
}

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

const resolveInternalNavigationTarget = (value: string) => {
  if (typeof window === 'undefined') {
    return value
  }
  try {
    const resolved = new URL(value, window.location.origin)
    return {
      pathname: resolved.pathname,
      search: resolved.search,
      hash: resolved.hash,
    }
  } catch {
    return value
  }
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
  const [searchParams, setSearchParams] = useSearchParams()
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const api = useMemo(() => getV2(), [])
  const screens = useBreakpoint()
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.lg
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < DESKTOP_BREAKPOINT_PX
        : false
    )
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')

  const [state, setState] = useState<WorkflowDesignerState>({
    template: null,
    dagStructure: initialDagStructure,
    selectedNodeId: normalizeRouteParam(searchParams.get('node')),
    isModified: false,
    isLoading: !!templateId,
    isSaving: false,
    isValidating: false,
    validationResult: null,
    operationTemplates: [],
  })

  const [saveModalVisible, setSaveModalVisible] = useState(false)
  const [executeInput, setExecuteInput] = useState('{}')
  const [paletteDrawerOpen, setPaletteDrawerOpen] = useState(false)
  const dagStructureRef = useRef<DAGStructure>(initialDagStructure)
  const selectedNodeFromUrl = normalizeRouteParam(searchParams.get('node'))
  const executeModalFromUrl = searchParams.get('execute') === 'true'
  const returnToFromUrl = normalizeInternalReturnTo(searchParams.get('returnTo'))
  const isSystemManagedProjection = state.template?.is_system_managed === true
  const decisionDatabaseId = String(searchParams.get('database_id') || '').trim()
  const isRuntimeDiagnosticsSurface =
    searchParams.get('surface') === 'runtime_diagnostics' || isSystemManagedProjection
  const designerSurface = isRuntimeDiagnosticsSurface ? 'runtime_diagnostics' : undefined
  const [executeModalVisible, setExecuteModalVisible] = useState(executeModalFromUrl)
  const authoringReferencesQuery = useAuthoringReferences({
    databaseId: decisionDatabaseId || undefined,
  })
  const availableWorkflows = authoringReferencesQuery.data?.availableWorkflows ?? []
  const availableDecisions = authoringReferencesQuery.data?.availableDecisions ?? []
  const backTarget = returnToFromUrl ?? buildRouteWithWorkflowContext({
    basePath: '/workflows',
    databaseId: decisionDatabaseId,
    surface: designerSurface,
  })
  const resolvedBackTarget = useMemo(() => (
    returnToFromUrl ? resolveInternalNavigationTarget(returnToFromUrl) : backTarget
  ), [backTarget, returnToFromUrl])
  const runtimeProjectionReadOnlyReason = state.template?.read_only_reason
    || 'System-managed runtime workflow projections are available for diagnostics only.'
  const designerReturnTarget = useMemo(() => {
    const basePath = state.template?.id
      ? `/workflows/${state.template.id}`
      : templateId
        ? `/workflows/${templateId}`
        : '/workflows/new'
    return buildRouteWithWorkflowContext({
      basePath,
      databaseId: decisionDatabaseId,
      nodeId: state.selectedNodeId,
      returnTo: returnToFromUrl,
      surface: designerSurface,
    })
  }, [decisionDatabaseId, designerSurface, returnToFromUrl, state.selectedNodeId, state.template?.id, templateId])

  useEffect(() => {
    setState((prev) => (
      prev.selectedNodeId === selectedNodeFromUrl
        ? prev
        : { ...prev, selectedNodeId: selectedNodeFromUrl }
    ))
  }, [selectedNodeFromUrl])

  useEffect(() => {
    setExecuteModalVisible((current) => (
      current === executeModalFromUrl
        ? current
        : executeModalFromUrl
    ))
  }, [executeModalFromUrl])

  useEffect(() => {
    if (state.isLoading || !state.selectedNodeId) {
      return
    }
    if (state.dagStructure.nodes.some((node) => node.id === state.selectedNodeId)) {
      return
    }
    routeUpdateModeRef.current = 'replace'
    setState((prev) => ({ ...prev, selectedNodeId: null }))
  }, [state.dagStructure.nodes, state.isLoading, state.selectedNodeId])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    if (state.selectedNodeId) {
      next.set('node', state.selectedNodeId)
    } else {
      next.delete('node')
    }
    if (executeModalVisible) {
      next.set('execute', 'true')
    } else {
      next.delete('execute')
    }
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(
        next,
        routeUpdateModeRef.current === 'replace'
          ? { replace: true }
          : undefined
      )
    }
    routeUpdateModeRef.current = 'replace'
  }, [executeModalVisible, searchParams, setSearchParams, state.selectedNodeId])

  // Load template if editing
  useEffect(() => {
    const loadTemplate = async () => {
      if (!templateId) {
        setState((prev) => ({ ...prev, isLoading: false }))
        return
      }

      try {
        setState((prev) => ({ ...prev, isLoading: true }))
        const response = await api.getWorkflowsGetWorkflow({ workflow_id: templateId })
        const template = convertTemplateToLegacy(response.workflow)
        dagStructureRef.current = template.dag_structure
        setState((prev) => ({
          ...prev,
          template,
          dagStructure: template.dag_structure,
          isLoading: false,
        }))
        form.setFieldsValue({
          name: template.name,
          description: template.description,
        })
      } catch (_error) {
        message.error('Failed to load workflow template')
        setState((prev) => ({ ...prev, isLoading: false }))
      }
    }

    void loadTemplate()
  }, [api, form, message, templateId])

  useEffect(() => {
    if (authoringReferencesQuery.isError) {
      console.error('Failed to load workflow authoring references:', authoringReferencesQuery.error)
    }
  }, [authoringReferencesQuery.error, authoringReferencesQuery.isError])

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

    void loadOperationTemplates()
  }, [])

  const handleDagChange = useCallback((dag: DAGStructure) => {
    dagStructureRef.current = dag
    setState((prev) => ({
      ...prev,
      dagStructure: dag,
      isModified: true,
      validationResult: null,
    }))
  }, [])

  const handleNodeSelect = useCallback((nodeId: string | null) => {
    routeUpdateModeRef.current = 'push'
    setState((prev) => (
      prev.selectedNodeId === nodeId
        ? prev
        : { ...prev, selectedNodeId: nodeId }
    ))
  }, [])

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
            config: data.config ?? node.config,
          }
        }
        return node
      })
      const nextDagStructure = {
        ...prev.dagStructure,
        nodes: updatedNodes,
      }
      dagStructureRef.current = nextDagStructure

      return {
        ...prev,
        dagStructure: nextDagStructure,
        isModified: true,
        validationResult: null,
      }
    })
  }, [])

  const handleNodeDelete = useCallback((nodeId: string) => {
    routeUpdateModeRef.current = 'push'
    setState((prev) => {
      const updatedNodes = prev.dagStructure.nodes.filter((node) => node.id !== nodeId)
      const updatedEdges = prev.dagStructure.edges.filter(
        (edge) => edge.from !== nodeId && edge.to !== nodeId
      )
      const nextDagStructure = {
        nodes: updatedNodes,
        edges: updatedEdges,
      }
      dagStructureRef.current = nextDagStructure

      return {
        ...prev,
        dagStructure: nextDagStructure,
        selectedNodeId: null,
        isModified: true,
        validationResult: null,
      }
    })
  }, [])

  const selectedNodeData = useMemo(() => {
    if (!state.selectedNodeId) {
      return null
    }
    const node = state.dagStructure.nodes.find((entry) => entry.id === state.selectedNodeId)
    if (!node) {
      return null
    }
    return {
      label: node.name,
      nodeType: node.type,
      templateId: node.template_id,
      operationRef: node.operation_ref,
      decisionRef: node.decision_ref,
      io: node.io,
      config: node.config,
    } as WorkflowNodeData
  }, [state.dagStructure.nodes, state.selectedNodeId])

  const selectedNodeLabel = selectedNodeData?.label ?? null

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
      const response = await api.postWorkflowsValidateWorkflow({ workflow_id: state.template.id })
      const result = convertValidationToLegacy(response)
      setState((prev) => ({
        ...prev,
        validationResult: result,
        isValidating: false,
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

  const handleSave = async () => {
    if (isSystemManagedProjection) {
      message.info(runtimeProjectionReadOnlyReason)
      return
    }
    try {
      const values = await form.validateFields()

      setState((prev) => ({ ...prev, isSaving: true }))

      const dagStructureForApi = convertDAGToGenerated(dagStructureRef.current) as unknown as { [key: string]: unknown }

      let savedTemplate: WorkflowTemplate

      if (state.template?.id) {
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
        const response = await api.postWorkflowsCreateWorkflow({
          name: values.name,
          description: values.description,
          dag_structure: dagStructureForApi,
          workflow_type: 'complex',
        })
        savedTemplate = convertTemplateToLegacy(response.workflow)
        message.success('Workflow created successfully')
        navigate(
          buildRouteWithWorkflowContext({
            basePath: `/workflows/${savedTemplate.id}`,
            databaseId: decisionDatabaseId,
            nodeId: state.selectedNodeId,
            returnTo: returnToFromUrl,
            surface: designerSurface,
          }),
          { replace: true }
        )
      }

      setState((prev) => ({
        ...prev,
        template: savedTemplate,
        isModified: false,
        isSaving: false,
      }))

      setSaveModalVisible(false)
    } catch (error: unknown) {
      message.error(resolveApiErrorMessage(error, 'Failed to save workflow'))
      setState((prev) => ({ ...prev, isSaving: false }))
    }
  }

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
      const response = await api.postWorkflowsExecuteWorkflow({
        workflow_id: state.template.id,
        input_context: inputContext,
        mode: 'async',
      })

      message.success('Workflow execution started')
      setExecuteModalVisible(false)
      const params = new URLSearchParams()
      params.set('returnTo', designerReturnTarget)
      navigate(buildRelativeHref(`/workflows/executions/${response.execution_id}`, params))
    } catch (error: unknown) {
      if (error instanceof SyntaxError) {
        message.error('Invalid JSON input')
      } else {
        message.error(resolveApiErrorMessage(error, 'Failed to execute workflow'))
      }
    }
  }

  const handleSaveClick = () => {
    if (isSystemManagedProjection) {
      message.info(runtimeProjectionReadOnlyReason)
      return
    }
    if (!state.template) {
      setSaveModalVisible(true)
      return
    }
    void handleSave()
  }

  if (state.isLoading) {
    return (
      <div className="workflow-designer-loading">
        <Spin size="large" tip="Loading workflow…">
          <div style={{ minHeight: 200 }} />
        </Spin>
      </div>
    )
  }

  return (
    <div className="workflow-designer">
      <WorkspacePage
        header={(
          <PageHeader
            title={(
              <span className="workflow-designer-title">
                {state.template ? state.template.name : 'New Workflow Scheme'}
                {state.isModified ? <span className="modified-indicator">*</span> : null}
              </span>
            )}
            subtitle={isRuntimeDiagnosticsSurface
              ? 'Inspect system-managed runtime projections without mutating the analyst authoring surface.'
              : 'Compose analyst-facing workflow definitions with reusable templates and versioned decisions.'}
            actions={(
              <Space className="designer-header" wrap size={[8, 8]}>
                <Button
                  icon={<ArrowLeftOutlined />}
                  onClick={() => navigate(resolvedBackTarget)}
                >
                  Back
                </Button>
                {isNarrow ? (
                  <Button
                    icon={<AppstoreOutlined />}
                    onClick={() => setPaletteDrawerOpen(true)}
                  >
                    Node palette
                  </Button>
                ) : null}
                <Tooltip title="Validate DAG structure">
                  <Button
                    icon={<CheckCircleOutlined />}
                    onClick={() => void handleValidate()}
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
                  onClick={() => {
                    routeUpdateModeRef.current = 'push'
                    setExecuteModalVisible(true)
                  }}
                  disabled={isSystemManagedProjection || !state.template?.is_valid}
                >
                  Execute
                </Button>
              </Space>
            )}
          />
        )}
      >
        {isSystemManagedProjection ? (
          <Alert
            showIcon
            type="warning"
            message="Runtime diagnostics surface"
            description={runtimeProjectionReadOnlyReason}
          />
        ) : (
          <Alert
            showIcon
            type="info"
            message="Workflow scheme library"
            description="Author analyst-facing workflow composition in /workflows. Use /templates for atomic operations, /decisions for versioned decision resources, and treat runtime projections as diagnostics-only artifacts."
          />
        )}

        <div className="workflow-designer-shell">
          {!isNarrow ? (
            <aside className="designer-panel designer-panel--palette">
              <Text strong className="designer-panel-title">Node palette</Text>
              {isSystemManagedProjection ? (
                <Alert
                  showIcon
                  type="info"
                  message="Read-only runtime projection"
                  description="Generated runtime projections can be inspected, but not changed from the analyst workflow surface."
                />
              ) : (
                <NodePalette />
              )}
            </aside>
          ) : null}

          <section className="designer-content">
            {selectedNodeLabel ? (
              <Text
                data-testid="workflow-designer-selected-node"
                type="secondary"
                className="workflow-designer-selected-node"
              >
                {`Selected node: ${selectedNodeLabel}`}
              </Text>
            ) : null}

            {state.validationResult && !state.validationResult.is_valid ? (
              <Alert
                type="error"
                message="Validation Errors"
                description={(
                  <ul>
                    {state.validationResult.errors.map((error, index) => (
                      <li key={index}>{error.message}</li>
                    ))}
                  </ul>
                )}
                closable
                onClose={() => setState((prev) => ({ ...prev, validationResult: null }))}
                className="validation-alert"
              />
            ) : null}

            <WorkflowCanvas
              dagStructure={state.dagStructure}
              mode={isSystemManagedProjection ? 'monitor' : 'design'}
              onDagChange={handleDagChange}
              onNodeSelect={handleNodeSelect}
            />
          </section>

          {!isNarrow ? (
            <aside className="designer-panel designer-panel--inspector">
              <Text strong className="designer-panel-title">
                {selectedNodeLabel ? `Node details: ${selectedNodeLabel}` : 'Node details'}
              </Text>
              <PropertyEditor
                nodeId={state.selectedNodeId}
                nodeData={selectedNodeData}
                onNodeUpdate={handleNodeUpdate}
                onNodeDelete={handleNodeDelete}
                operationTemplates={state.operationTemplates}
                availableWorkflows={availableWorkflows}
                availableDecisions={availableDecisions}
                readOnly={isSystemManagedProjection}
              />
            </aside>
          ) : null}
        </div>

        {isNarrow ? (
          <DrawerFormShell
            open={paletteDrawerOpen}
            onClose={() => setPaletteDrawerOpen(false)}
            title="Node palette"
            subtitle="Add workflow nodes without leaving the current authoring context."
            drawerTestId="workflow-designer-palette-drawer"
          >
            {isSystemManagedProjection ? (
              <Alert
                showIcon
                type="info"
                message="Read-only runtime projection"
                description="Generated runtime projections can be inspected, but not changed from the analyst workflow surface."
              />
            ) : (
              <NodePalette />
            )}
          </DrawerFormShell>
        ) : null}

        {isNarrow ? (
          <DrawerFormShell
            open={Boolean(state.selectedNodeId && selectedNodeData)}
            onClose={() => handleNodeSelect(null)}
            title="Node details"
            subtitle={selectedNodeLabel ?? 'Select a workflow node to inspect or edit it.'}
            drawerTestId="workflow-designer-node-drawer"
          >
            {selectedNodeData ? (
              <div className="designer-drawer-panel">
                <PropertyEditor
                  nodeId={state.selectedNodeId}
                  nodeData={selectedNodeData}
                  onNodeUpdate={handleNodeUpdate}
                  onNodeDelete={handleNodeDelete}
                  operationTemplates={state.operationTemplates}
                  availableWorkflows={availableWorkflows}
                  availableDecisions={availableDecisions}
                  readOnly={isSystemManagedProjection}
                />
              </div>
            ) : null}
          </DrawerFormShell>
        ) : null}

        <ModalFormShell
          open={saveModalVisible}
          onClose={() => setSaveModalVisible(false)}
          onSubmit={() => {
            void handleSave()
          }}
          title="Save Workflow Scheme"
          subtitle="Capture the current workflow definition as a reusable analyst-facing scheme."
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
        </ModalFormShell>

        <ModalFormShell
          open={executeModalVisible}
          onClose={() => {
            routeUpdateModeRef.current = 'push'
            setExecuteModalVisible(false)
          }}
          onSubmit={() => {
            void handleExecute()
          }}
          title="Execute Workflow"
          subtitle="Provide input context and hand off to runtime diagnostics without leaving the authoring route."
          submitText="Execute"
          width={960}
        >
          {executeModalVisible ? (
            <LazyJsonCodeEditor
              id="workflow-execute-input"
              title="Input Context (JSON)"
              value={executeInput}
              onChange={setExecuteInput}
              height={220}
              path="workflow-execute-input.json"
            />
          ) : null}
          <div className="workflow-designer-execute-help">
            Provide input variables for the workflow
          </div>
        </ModalFormShell>
      </WorkspacePage>
    </div>
  )
}

export default WorkflowDesigner
