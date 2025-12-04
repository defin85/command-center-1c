/**
 * Workflow API endpoints.
 *
 * Provides methods for workflow template CRUD operations,
 * workflow execution, and validation.
 */

// v2 migration: using apiClient through API Gateway instead of direct orchestratorClient
import { apiClient } from '../client'
import type {
  WorkflowTemplate,
  WorkflowTemplateCreate,
  WorkflowTemplateUpdate,
  WorkflowExecution,
  WorkflowExecutionCreate,
  ValidationResult,
  NodeStepResult
} from '../../types/workflow'

// ============================================================================
// Workflow Template Endpoints
// ============================================================================

export interface WorkflowTemplateListParams {
  page?: number
  page_size?: number
  workflow_type?: string
  is_active?: boolean
  is_valid?: boolean
  search?: string
  ordering?: string
}

export interface PaginatedResponse<T> {
  count: number
  total?: number  // API v2 alternative
  next: string | null
  previous: string | null
  results: T[]
  workflows?: T[]  // API v2 returns 'workflows' instead of 'results'
}

/**
 * List workflow templates with optional filters.
 */
export const listWorkflowTemplates = async (
  params?: WorkflowTemplateListParams
): Promise<PaginatedResponse<WorkflowTemplate>> => {
  // v2 migration: GET /workflows/templates/ → GET /workflows/list-workflows
  const response = await apiClient.get('/workflows/list-workflows', { params })
  return response.data
}

/**
 * Get a single workflow template by ID.
 */
export const getWorkflowTemplate = async (id: string): Promise<WorkflowTemplate> => {
  // v2 migration: GET /workflows/templates/{id}/ → GET /workflows/get-workflow?workflow_id={id}
  const response = await apiClient.get('/workflows/get-workflow', { params: { workflow_id: id } })
  // API v2 wraps response in { workflow: {...}, statistics: {...}, executions: [...] }
  return response.data.workflow || response.data
}

/**
 * Create a new workflow template.
 */
export const createWorkflowTemplate = async (
  data: WorkflowTemplateCreate
): Promise<WorkflowTemplate> => {
  // v2 migration: POST /workflows/templates/ → POST /workflows/create-workflow
  const response = await apiClient.post('/workflows/create-workflow', data)
  return response.data
}

/**
 * Update an existing workflow template.
 */
export const updateWorkflowTemplate = async (
  id: string,
  data: WorkflowTemplateUpdate
): Promise<WorkflowTemplate> => {
  // v2 migration: PATCH /workflows/templates/{id}/ → POST /workflows/update-workflow?workflow_id={id}
  const response = await apiClient.post('/workflows/update-workflow', data, { params: { workflow_id: id } })
  return response.data
}

/**
 * Delete a workflow template.
 */
export const deleteWorkflowTemplate = async (id: string): Promise<void> => {
  // v2 migration: DELETE /workflows/templates/{id}/ → POST /workflows/delete-workflow?workflow_id={id}
  await apiClient.post('/workflows/delete-workflow', null, { params: { workflow_id: id } })
}

/**
 * Validate a workflow template's DAG structure.
 */
export const validateWorkflowTemplate = async (id: string): Promise<ValidationResult> => {
  // v2 migration: POST /workflows/templates/{id}/validate/ → POST /workflows/validate-workflow?workflow_id={id}
  const response = await apiClient.post('/workflows/validate-workflow', null, { params: { workflow_id: id } })
  return response.data
}

/**
 * Clone an existing workflow template.
 */
export const cloneWorkflowTemplate = async (
  id: string,
  newName?: string
): Promise<WorkflowTemplate> => {
  // v2 migration: POST /workflows/templates/{id}/clone/ → POST /workflows/clone-workflow?workflow_id={id}
  const response = await apiClient.post('/workflows/clone-workflow', {
    name: newName
  }, { params: { workflow_id: id } })
  return response.data
}

/**
 * Execute a workflow template (create execution).
 */
export const executeWorkflowTemplate = async (
  id: string,
  data: WorkflowExecutionCreate
): Promise<WorkflowExecution> => {
  // v2 migration: POST /workflows/templates/{id}/execute/ → POST /workflows/execute-workflow?workflow_id={id}
  const response = await apiClient.post('/workflows/execute-workflow', data, { params: { workflow_id: id } })
  return response.data
}

// ============================================================================
// Workflow Execution Endpoints
// ============================================================================

export interface WorkflowExecutionListParams {
  page?: number
  page_size?: number
  status?: string
  workflow_template?: string
  ordering?: string
}

/**
 * List workflow executions with optional filters.
 */
export const listWorkflowExecutions = async (
  params?: WorkflowExecutionListParams
): Promise<PaginatedResponse<WorkflowExecution>> => {
  // v2 migration: GET /workflows/executions/ → GET /workflows/list-executions
  const response = await apiClient.get('/workflows/list-executions', { params })
  return response.data
}

/**
 * Get a single workflow execution by ID.
 */
export const getWorkflowExecution = async (id: string): Promise<WorkflowExecution> => {
  // v2 migration: GET /workflows/executions/{id}/ → GET /workflows/get-execution?execution_id={id}
  const response = await apiClient.get('/workflows/get-execution', { params: { execution_id: id } })
  return response.data
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
  // v2 migration: GET /workflows/executions/{id}/status/ → GET /workflows/get-execution-status?execution_id={id}
  const response = await apiClient.get('/workflows/get-execution-status', { params: { execution_id: id } })
  return response.data
}

/**
 * Cancel a running workflow execution.
 */
export const cancelWorkflowExecution = async (id: string): Promise<{
  status: string
  message: string
}> => {
  // v2 migration: POST /workflows/executions/{id}/cancel/ → POST /workflows/cancel-execution?execution_id={id}
  const response = await apiClient.post('/workflows/cancel-execution', null, { params: { execution_id: id } })
  return response.data
}

/**
 * Get step results for a workflow execution.
 */
export const getWorkflowExecutionSteps = async (id: string): Promise<NodeStepResult[]> => {
  // v2 migration: GET /workflows/executions/{id}/steps/ → GET /workflows/get-execution-steps?execution_id={id}
  const response = await apiClient.get('/workflows/get-execution-steps', { params: { execution_id: id } })
  return response.data
}

// ============================================================================
// Operation Templates (for operation node configuration)
// ============================================================================

export interface OperationTemplateListItem {
  id: string
  name: string
  operation_type: string
  description?: string
}

/**
 * List available operation templates for workflow operations.
 */
export const listOperationTemplates = async (): Promise<OperationTemplateListItem[]> => {
  // v2 migration: GET /templates/ → GET /templates/list-templates/
  const response = await apiClient.get('/templates/list-templates/', {
    params: { limit: 1000 }  // Get all for dropdown
  })
  return response.data.templates || response.data
}
