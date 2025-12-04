/**
 * Workflow API Adapter.
 *
 * Bridges the gap between the old endpoint-based API and the new
 * generated API from OpenAPI specifications.
 *
 * This adapter:
 * 1. Uses customInstance (same as generated code) for API calls
 * 2. Provides the same function signatures as endpoints/workflows.ts
 * 3. Maps parameters to the v2 action-based endpoints
 * 4. Provides type transformations between generated and legacy types
 *
 * Note: Generated types use `from_node`/`to_node` for edges, while
 * legacy types use `from`/`to`. This adapter handles the conversion.
 */

import { customInstance } from '../mutator'
// Import legacy types for UI components (React Flow integration)
import type {
  DAGStructure as LegacyDAGStructure,
  DAGNode as LegacyDAGNode,
  DAGEdge as LegacyDAGEdge,
  WorkflowTemplate as LegacyWorkflowTemplate,
  WorkflowExecution as LegacyWorkflowExecution,
  ValidationResult as LegacyValidationResult,
  NodeStepResult as LegacyNodeStepResult,
} from '../../types/workflow'

// Re-export generated types for direct use when needed
export type {
  WorkflowTemplateList,
  WorkflowExecutionList,
  WorkflowValidateResponse,
  WorkflowCloneRequest,
  WorkflowCloneResponse,
  WorkflowExecuteRequest,
  WorkflowExecuteResponse,
  WorkflowCancelResponse,
  WorkflowStepResult as GeneratedStepResult,
  DAGStructure as GeneratedDAGStructure,
  WorkflowNode as GeneratedWorkflowNode,
  WorkflowEdge as GeneratedWorkflowEdge,
  WorkflowConfig,
  WorkflowTypeEnum,
  Status2a6Enum as ExecutionStatusEnum,
  WorkflowStepResultStatusEnum as StepStatusEnum,
} from '../generated/model'

// Import types for internal use
import type {
  WorkflowTemplateList,
  WorkflowTemplateDetail,
  WorkflowExecutionList,
  WorkflowExecutionDetail,
  WorkflowValidateResponse,
  WorkflowCloneResponse,
  WorkflowExecuteResponse,
  WorkflowCancelResponse,
  WorkflowStepResult,
  DAGStructure as GeneratedDAGStructure,
  WorkflowNode as GeneratedWorkflowNode,
  WorkflowEdge as GeneratedWorkflowEdge,
  WorkflowConfig,
} from '../generated/model'

// ============================================================================
// Type aliases for backward compatibility
// ============================================================================

// Re-export legacy types as primary types for UI components
export type DAGStructure = LegacyDAGStructure
export type DAGNode = LegacyDAGNode
export type DAGEdge = LegacyDAGEdge
export type WorkflowTemplate = LegacyWorkflowTemplate
export type WorkflowExecution = LegacyWorkflowExecution
export type ValidationResult = LegacyValidationResult
export type NodeStepResult = LegacyNodeStepResult

// ============================================================================
// Type Transformations (Generated <-> Legacy)
// ============================================================================

/**
 * Convert generated DAG edge to legacy format.
 * Generated: { from_node, to_node, condition }
 * Legacy: { from, to, condition }
 */
function convertEdgeToLegacy(edge: GeneratedWorkflowEdge): LegacyDAGEdge {
  return {
    from: edge.from_node,
    to: edge.to_node,
    condition: edge.condition ?? undefined,
  }
}

/**
 * Convert legacy DAG edge to generated format for API calls.
 */
function convertEdgeToGenerated(edge: LegacyDAGEdge): GeneratedWorkflowEdge {
  return {
    from_node: edge.from,
    to_node: edge.to,
    condition: edge.condition ?? null,
  }
}

/**
 * Convert wait_for from generated string to legacy union type.
 */
function convertWaitFor(waitFor?: string): 'all' | 'any' | number | undefined {
  if (waitFor === undefined) return undefined
  if (waitFor === 'all' || waitFor === 'any') return waitFor
  const num = parseInt(waitFor, 10)
  return Number.isNaN(num) ? undefined : num
}

/**
 * Convert generated DAG node to legacy format.
 * Merges specialized configs (parallel_config, loop_config, subworkflow_config)
 * into the unified 'config' field for legacy UI components.
 */
function convertNodeToLegacy(node: GeneratedWorkflowNode): LegacyDAGNode {
  // Merge specialized configs into unified config for legacy compatibility
  // Handle null -> undefined conversions for legacy type compatibility
  const mergedConfig: LegacyDAGNode['config'] = {
    timeout: node.config?.timeout_seconds,
    retries: node.config?.max_retries,
    expression: node.config?.expression ?? undefined,
    // Parallel config
    ...(node.parallel_config && {
      parallel_nodes: node.parallel_config.parallel_nodes,
      wait_for: convertWaitFor(node.parallel_config.wait_for),
    }),
    // Loop config
    ...(node.loop_config && {
      loop_mode: node.loop_config.mode,
      loop_count: node.loop_config.count ?? undefined,
      loop_condition: node.loop_config.condition ?? undefined,
      loop_items: node.loop_config.items ?? undefined,
      max_iterations: node.loop_config.max_iterations,
    }),
    // Subworkflow config
    ...(node.subworkflow_config && {
      subworkflow_id: node.subworkflow_config.subworkflow_id,
      input_mapping: node.subworkflow_config.input_mapping as Record<string, string> | undefined,
      output_mapping: node.subworkflow_config.output_mapping as Record<string, string> | undefined,
    }),
  }

  return {
    id: node.id,
    name: node.name,
    type: node.type as LegacyDAGNode['type'],
    template_id: node.template_id ?? undefined,
    config: mergedConfig,
    // Note: position is not present in generated type, will be undefined
    position: (node as LegacyDAGNode).position,
  }
}

/**
 * Convert generated DAG structure to legacy format.
 */
function convertDAGToLegacy(dag: GeneratedDAGStructure): LegacyDAGStructure {
  return {
    nodes: dag.nodes.map(convertNodeToLegacy),
    edges: (dag.edges ?? []).map(convertEdgeToLegacy),
  }
}

/**
 * Convert legacy wait_for to generated string format.
 */
function convertWaitForToString(waitFor?: 'all' | 'any' | number): string | undefined {
  if (waitFor === undefined) return undefined
  return String(waitFor)
}

/**
 * Convert legacy DAG structure to generated format for API calls.
 * Extracts specialized configs from unified 'config' field into separate fields.
 */
function convertDAGToGenerated(dag: LegacyDAGStructure): GeneratedDAGStructure {
  return {
    nodes: dag.nodes.map(node => {
      // Build generated node with proper type conversions
      const generatedNode: GeneratedWorkflowNode = {
        id: node.id,
        name: node.name,
        type: node.type as GeneratedWorkflowNode['type'],
        template_id: node.template_id ?? null,
        config: node.config ? {
          timeout_seconds: node.config.timeout,
          max_retries: node.config.retries,
          expression: node.config.expression ?? null,
        } : undefined,
      }

      // Extract specialized configs from legacy unified config
      if (node.config?.parallel_nodes) {
        generatedNode.parallel_config = {
          parallel_nodes: node.config.parallel_nodes,
          wait_for: convertWaitForToString(node.config.wait_for),
        }
      }

      if (node.config?.loop_mode) {
        generatedNode.loop_config = {
          mode: node.config.loop_mode,
          count: node.config.loop_count ?? null,
          condition: node.config.loop_condition ?? null,
          items: node.config.loop_items ?? null,
          loop_node_id: node.id, // Use node's own ID as loop target
          max_iterations: node.config.max_iterations,
        }
      }

      if (node.config?.subworkflow_id) {
        generatedNode.subworkflow_config = {
          subworkflow_id: node.config.subworkflow_id,
          input_mapping: node.config.input_mapping,
          output_mapping: node.config.output_mapping,
        }
      }

      return generatedNode
    }),
    edges: dag.edges.map(convertEdgeToGenerated),
  }
}

/**
 * Convert WorkflowTemplateDetail to legacy WorkflowTemplate format.
 */
function convertTemplateToLegacy(detail: WorkflowTemplateDetail): LegacyWorkflowTemplate {
  return {
    id: detail.id,
    name: detail.name,
    description: detail.description,
    workflow_type: detail.workflow_type as LegacyWorkflowTemplate['workflow_type'],
    dag_structure: convertDAGToLegacy(detail.dag_structure),
    config: detail.config as LegacyWorkflowTemplate['config'],
    is_valid: detail.is_valid,
    is_active: detail.is_active ?? true,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
    created_by: detail.created_by_username ?? undefined,
    version: detail.version_number,
  }
}

/**
 * Convert WorkflowExecutionDetail to legacy WorkflowExecution format.
 */
function convertExecutionToLegacy(detail: WorkflowExecutionDetail): LegacyWorkflowExecution {
  // Handle progress_percent correctly: || 0 would convert valid 0 to 0, but parseFloat("0") || 0 works
  // However, if detail.progress_percent is NaN (invalid string), we need proper handling
  const progressPercent = parseFloat(detail.progress_percent)

  return {
    id: detail.id,
    workflow_template: detail.workflow_template,
    workflow_template_name: detail.template_name,
    input_context: detail.input_context as Record<string, unknown>,
    status: detail.status as LegacyWorkflowExecution['status'],
    progress_percent: Number.isNaN(progressPercent) ? 0 : progressPercent,
    current_node_id: detail.current_node_id || undefined,
    completed_nodes: Object.keys(detail.completed_nodes || {}),
    failed_nodes: Object.keys(detail.failed_nodes || {}),
    final_result: detail.final_result as Record<string, unknown> | undefined,
    error_message: detail.error_message || undefined,
    error_node_id: detail.error_node_id || undefined,
    trace_id: detail.trace_id || undefined,
    started_at: detail.started_at ?? undefined,
    completed_at: detail.completed_at ?? undefined,
    created_at: detail.started_at ?? new Date().toISOString(),
    updated_at: detail.completed_at ?? detail.started_at ?? new Date().toISOString(),
    duration_seconds: detail.duration,
  }
}

/**
 * Convert WorkflowValidateResponse to legacy ValidationResult format.
 */
function convertValidationToLegacy(response: WorkflowValidateResponse): LegacyValidationResult {
  const errors = (response.errors ?? []).map(msg => ({
    severity: 'error' as const,
    message: msg,
  }))
  const warnings = (response.warnings ?? []).map(msg => ({
    severity: 'warning' as const,
    message: msg,
  }))

  return {
    is_valid: response.valid,
    issues: [...errors, ...warnings],
    errors,
    warnings,
  }
}

/**
 * Convert WorkflowStepResult to legacy NodeStepResult format.
 */
function convertStepToLegacy(step: WorkflowStepResult): LegacyNodeStepResult {
  return {
    id: step.id,
    node_id: step.node_id,
    status: step.status as LegacyNodeStepResult['status'],
    input_data: step.input_data as Record<string, unknown> | undefined,
    output_data: step.output_data as Record<string, unknown> | undefined,
    error_message: step.error_message || undefined,
    started_at: step.started_at ?? undefined,
    completed_at: step.completed_at ?? undefined,
    duration_seconds: step.duration_seconds,
    trace_id: step.trace_id || undefined,
    span_id: step.span_id || undefined,
  }
}

// ============================================================================
// Request/Response interfaces
// ============================================================================

export interface WorkflowTemplateListParams {
  page?: number
  page_size?: number
  limit?: number
  offset?: number
  workflow_type?: string
  is_active?: boolean
  is_valid?: boolean
  search?: string
  ordering?: string
}

export interface PaginatedResponse<T> {
  count: number
  total?: number
  next: string | null
  previous: string | null
  results: T[]
  workflows?: T[]  // v2 returns 'workflows' instead of 'results'
}

export interface WorkflowTemplateCreate {
  name: string
  description?: string
  workflow_type?: string
  dag_structure: LegacyDAGStructure
  config?: WorkflowConfig
  is_active?: boolean
}

export interface WorkflowTemplateUpdate {
  workflow_id?: string
  name?: string
  description?: string
  workflow_type?: string
  dag_structure?: LegacyDAGStructure
  config?: WorkflowConfig
  is_active?: boolean
}

export interface WorkflowExecutionListParams {
  page?: number
  page_size?: number
  limit?: number
  offset?: number
  status?: string
  workflow_template?: string
  workflow_id?: string
  ordering?: string
}

export interface WorkflowExecutionCreate {
  input_context: Record<string, unknown>
  async?: boolean  // Legacy field name
  mode?: 'sync' | 'async'
}

export interface OperationTemplateListItem {
  id: string
  name: string
  operation_type: string
  description?: string
}

// ============================================================================
// Workflow Template Endpoints
// ============================================================================

/**
 * List workflow templates with optional filters.
 */
export const listWorkflowTemplates = async (
  params?: WorkflowTemplateListParams
): Promise<PaginatedResponse<WorkflowTemplateList>> => {
  // Convert page/page_size to limit/offset for v2 API
  const limit = params?.limit ?? params?.page_size ?? 50
  const offset = params?.offset ?? (params?.page ? (params.page - 1) * limit : 0)

  return customInstance<PaginatedResponse<WorkflowTemplateList>>({
    url: '/api/v2/workflows/list-workflows/',
    method: 'GET',
    params: {
      limit,
      offset,
      workflow_type: params?.workflow_type,
      is_active: params?.is_active,
      is_valid: params?.is_valid,
      search: params?.search,
    },
  })
}

/**
 * Get a single workflow template by ID.
 * Returns legacy WorkflowTemplate format for UI compatibility.
 */
export const getWorkflowTemplate = async (id: string): Promise<LegacyWorkflowTemplate> => {
  interface GetWorkflowResponse {
    workflow: WorkflowTemplateDetail
    executions?: WorkflowExecutionList[]
    statistics?: {
      total_executions: number
      successful: number
      failed: number
      average_duration: number
    }
  }

  const response = await customInstance<GetWorkflowResponse>({
    url: '/api/v2/workflows/get-workflow/',
    method: 'GET',
    params: { workflow_id: id },
  })

  // Convert to legacy format
  const detail = response.workflow ?? (response as unknown as WorkflowTemplateDetail)
  return convertTemplateToLegacy(detail)
}

/**
 * Create a new workflow template.
 * Returns legacy WorkflowTemplate format for UI compatibility.
 */
export const createWorkflowTemplate = async (
  data: WorkflowTemplateCreate
): Promise<LegacyWorkflowTemplate> => {
  interface CreateWorkflowResponse {
    workflow: WorkflowTemplateDetail
    message: string
  }

  // Convert DAG to generated format for API
  const apiData = {
    ...data,
    dag_structure: convertDAGToGenerated(data.dag_structure),
  }

  const response = await customInstance<CreateWorkflowResponse>({
    url: '/api/v2/workflows/create-workflow/',
    method: 'POST',
    data: apiData,
  })

  const detail = response.workflow ?? (response as unknown as WorkflowTemplateDetail)
  return convertTemplateToLegacy(detail)
}

/**
 * Update an existing workflow template.
 * Returns legacy WorkflowTemplate format for UI compatibility.
 */
export const updateWorkflowTemplate = async (
  id: string,
  data: WorkflowTemplateUpdate
): Promise<LegacyWorkflowTemplate> => {
  interface UpdateWorkflowResponse {
    workflow: WorkflowTemplateDetail
    updated_fields: string[]
    message: string
  }

  // Convert DAG to generated format if present
  const apiData = {
    ...data,
    workflow_id: id,
    dag_structure: data.dag_structure ? convertDAGToGenerated(data.dag_structure) : undefined,
  }

  const response = await customInstance<UpdateWorkflowResponse>({
    url: '/api/v2/workflows/update-workflow/',
    method: 'POST',
    data: apiData,
  })

  const detail = response.workflow ?? (response as unknown as WorkflowTemplateDetail)
  return convertTemplateToLegacy(detail)
}

/**
 * Delete a workflow template.
 */
export const deleteWorkflowTemplate = async (id: string, force = false): Promise<void> => {
  await customInstance<{ workflow_id: string; deleted: boolean; message: string }>({
    url: '/api/v2/workflows/delete-workflow/',
    method: 'POST',
    data: { workflow_id: id, force },
  })
}

/**
 * Validate a workflow template's DAG structure.
 * Returns legacy ValidationResult format for UI compatibility.
 */
export const validateWorkflowTemplate = async (id: string): Promise<LegacyValidationResult> => {
  const response = await customInstance<WorkflowValidateResponse>({
    url: '/api/v2/workflows/validate-workflow/',
    method: 'POST',
    data: { workflow_id: id },
  })

  return convertValidationToLegacy(response)
}

/**
 * Validate a DAG structure without saving.
 * Returns legacy ValidationResult format for UI compatibility.
 */
export const validateDAGStructure = async (dagStructure: LegacyDAGStructure): Promise<LegacyValidationResult> => {
  const response = await customInstance<WorkflowValidateResponse>({
    url: '/api/v2/workflows/validate-workflow/',
    method: 'POST',
    data: { dag_structure: convertDAGToGenerated(dagStructure) },
  })

  return convertValidationToLegacy(response)
}

/**
 * Clone an existing workflow template.
 * Returns legacy WorkflowTemplate format for UI compatibility.
 */
export const cloneWorkflowTemplate = async (
  id: string,
  newName?: string
): Promise<LegacyWorkflowTemplate> => {
  interface CloneResponse extends WorkflowCloneResponse {
    workflow?: WorkflowTemplateDetail
  }

  const response = await customInstance<CloneResponse>({
    url: '/api/v2/workflows/clone-workflow/',
    method: 'POST',
    data: { workflow_id: id, new_name: newName },
  })

  const detail = response.workflow ?? (response as unknown as WorkflowTemplateDetail)
  return convertTemplateToLegacy(detail)
}

/**
 * Execute response with execution_id for navigation.
 */
export interface ExecuteWorkflowResult {
  execution_id: string
  status: string
  mode: string
  message: string
}

/**
 * Execute a workflow template (create execution).
 * Returns execution_id for navigation to monitor page.
 */
export const executeWorkflowTemplate = async (
  id: string,
  data: WorkflowExecutionCreate
): Promise<ExecuteWorkflowResult> => {
  // Handle both legacy 'async' and new 'mode' fields
  const mode = data.mode ?? (data.async ? 'async' : 'sync')

  const response = await customInstance<WorkflowExecuteResponse>({
    url: '/api/v2/workflows/execute-workflow/',
    method: 'POST',
    data: {
      workflow_id: id,
      input_context: data.input_context,
      mode,
    },
  })

  return {
    execution_id: response.execution_id,
    status: response.status ?? 'pending',
    mode: response.mode ?? mode,
    message: response.message ?? 'Workflow execution started',
  }
}

// ============================================================================
// Workflow Execution Endpoints
// ============================================================================

/**
 * List workflow executions with optional filters.
 */
export const listWorkflowExecutions = async (
  params?: WorkflowExecutionListParams
): Promise<PaginatedResponse<WorkflowExecutionList>> => {
  // Convert page/page_size to limit/offset for v2 API
  const limit = params?.limit ?? params?.page_size ?? 50
  const offset = params?.offset ?? (params?.page ? (params.page - 1) * limit : 0)

  return customInstance<PaginatedResponse<WorkflowExecutionList>>({
    url: '/api/v2/workflows/list-executions/',
    method: 'GET',
    params: {
      limit,
      offset,
      status: params?.status,
      workflow_id: params?.workflow_id ?? params?.workflow_template,
    },
  })
}

/**
 * Get a single workflow execution by ID.
 * Returns legacy WorkflowExecution format for UI compatibility.
 */
export const getWorkflowExecution = async (id: string): Promise<LegacyWorkflowExecution> => {
  interface GetExecutionResponse {
    execution: WorkflowExecutionDetail
    steps?: WorkflowStepResult[]
  }

  const response = await customInstance<GetExecutionResponse>({
    url: '/api/v2/workflows/get-execution/',
    method: 'GET',
    params: { execution_id: id },
  })

  // Convert to legacy format
  const detail = response.execution ?? (response as unknown as WorkflowExecutionDetail)
  return convertExecutionToLegacy(detail)
}

/**
 * Get execution status (lightweight).
 */
export const getWorkflowExecutionStatus = async (id: string): Promise<{
  execution_id: string
  status: string
  progress_percent: number
  current_node_id?: string
  error_message?: string
}> => {
  // Use getWorkflowExecution and extract status
  const execution = await getWorkflowExecution(id)
  return {
    execution_id: execution.id,
    status: execution.status,
    progress_percent: execution.progress_percent,
    current_node_id: execution.current_node_id,
    error_message: execution.error_message,
  }
}

/**
 * Cancel response interface.
 */
export interface CancelExecutionResult {
  status: string
  message: string
}

/**
 * Cancel a running workflow execution.
 */
export const cancelWorkflowExecution = async (id: string): Promise<CancelExecutionResult> => {
  const response = await customInstance<WorkflowCancelResponse>({
    url: '/api/v2/workflows/cancel-execution/',
    method: 'POST',
    data: { execution_id: id },
  })

  return {
    status: response.status ?? 'cancelled',
    message: response.message ?? 'Execution cancelled successfully',
  }
}

/**
 * Get step results for a workflow execution.
 * Returns legacy NodeStepResult format for UI compatibility.
 */
export const getWorkflowExecutionSteps = async (id: string): Promise<LegacyNodeStepResult[]> => {
  interface GetStepsResponse {
    steps: WorkflowStepResult[]
    count: number
  }

  const response = await customInstance<GetStepsResponse>({
    url: '/api/v2/workflows/get-execution-steps/',
    method: 'GET',
    params: { execution_id: id },
  })

  const steps = response.steps ?? (response as unknown as WorkflowStepResult[])
  return steps.map(convertStepToLegacy)
}

// ============================================================================
// Operation Templates (for operation node configuration)
// ============================================================================

/**
 * List available operation templates for workflow operations.
 */
export const listOperationTemplates = async (): Promise<OperationTemplateListItem[]> => {
  interface ListTemplatesResponse {
    templates: OperationTemplateListItem[]
    count: number
  }

  const response = await customInstance<ListTemplatesResponse>({
    url: '/api/v2/templates/list-templates/',
    method: 'GET',
    params: { limit: 1000 }, // Get all for dropdown
  })

  return response.templates ?? (response as unknown as OperationTemplateListItem[])
}
