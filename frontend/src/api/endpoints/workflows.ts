/**
 * Workflow API endpoints.
 *
 * Provides methods for workflow template CRUD operations,
 * workflow execution, and validation.
 */

import axios from 'axios'
import type {
  WorkflowTemplate,
  WorkflowTemplateCreate,
  WorkflowTemplateUpdate,
  WorkflowExecution,
  WorkflowExecutionCreate,
  ValidationResult,
  NodeStepResult
} from '../../types/workflow'

// Orchestrator API client (direct connection for workflows)
// Note: In production, this would go through API Gateway
const ORCHESTRATOR_URL = import.meta.env.VITE_ORCHESTRATOR_URL || 'http://localhost:8000'

const orchestratorClient = axios.create({
  baseURL: `${ORCHESTRATOR_URL}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
orchestratorClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Handle 401 responses
orchestratorClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

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
  next: string | null
  previous: string | null
  results: T[]
}

/**
 * List workflow templates with optional filters.
 */
export const listWorkflowTemplates = async (
  params?: WorkflowTemplateListParams
): Promise<PaginatedResponse<WorkflowTemplate>> => {
  const response = await orchestratorClient.get('/workflows/templates/', { params })
  return response.data
}

/**
 * Get a single workflow template by ID.
 */
export const getWorkflowTemplate = async (id: string): Promise<WorkflowTemplate> => {
  const response = await orchestratorClient.get(`/workflows/templates/${id}/`)
  return response.data
}

/**
 * Create a new workflow template.
 */
export const createWorkflowTemplate = async (
  data: WorkflowTemplateCreate
): Promise<WorkflowTemplate> => {
  const response = await orchestratorClient.post('/workflows/templates/', data)
  return response.data
}

/**
 * Update an existing workflow template.
 */
export const updateWorkflowTemplate = async (
  id: string,
  data: WorkflowTemplateUpdate
): Promise<WorkflowTemplate> => {
  const response = await orchestratorClient.patch(`/workflows/templates/${id}/`, data)
  return response.data
}

/**
 * Delete a workflow template.
 */
export const deleteWorkflowTemplate = async (id: string): Promise<void> => {
  await orchestratorClient.delete(`/workflows/templates/${id}/`)
}

/**
 * Validate a workflow template's DAG structure.
 */
export const validateWorkflowTemplate = async (id: string): Promise<ValidationResult> => {
  const response = await orchestratorClient.post(`/workflows/templates/${id}/validate/`)
  return response.data
}

/**
 * Clone an existing workflow template.
 */
export const cloneWorkflowTemplate = async (
  id: string,
  newName?: string
): Promise<WorkflowTemplate> => {
  const response = await orchestratorClient.post(`/workflows/templates/${id}/clone/`, {
    name: newName
  })
  return response.data
}

/**
 * Execute a workflow template (create execution).
 */
export const executeWorkflowTemplate = async (
  id: string,
  data: WorkflowExecutionCreate
): Promise<WorkflowExecution> => {
  const response = await orchestratorClient.post(`/workflows/templates/${id}/execute/`, data)
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
  const response = await orchestratorClient.get('/workflows/executions/', { params })
  return response.data
}

/**
 * Get a single workflow execution by ID.
 */
export const getWorkflowExecution = async (id: string): Promise<WorkflowExecution> => {
  const response = await orchestratorClient.get(`/workflows/executions/${id}/`)
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
  const response = await orchestratorClient.get(`/workflows/executions/${id}/status/`)
  return response.data
}

/**
 * Cancel a running workflow execution.
 */
export const cancelWorkflowExecution = async (id: string): Promise<{
  status: string
  message: string
}> => {
  const response = await orchestratorClient.post(`/workflows/executions/${id}/cancel/`)
  return response.data
}

/**
 * Get step results for a workflow execution.
 */
export const getWorkflowExecutionSteps = async (id: string): Promise<NodeStepResult[]> => {
  const response = await orchestratorClient.get(`/workflows/executions/${id}/steps/`)
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
  const response = await orchestratorClient.get('/templates/', {
    params: { page_size: 1000 }  // Get all for dropdown
  })
  return response.data.results || response.data
}

// ============================================================================
// Export client for custom requests
// ============================================================================

export { orchestratorClient }
