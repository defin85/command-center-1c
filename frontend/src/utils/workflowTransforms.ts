/**
 * Workflow Transformation Utilities.
 *
 * This module provides bidirectional transformation functions between
 * Generated API types and Legacy frontend types for workflow-related entities.
 *
 * The transformations handle:
 * - Edge: from/to (generated) <-> from/to (legacy)
 * - Node config: split configs (generated) <-> unified config (legacy)
 * - progress_percent: string (generated) -> number (legacy)
 * - completed_nodes: Record (generated) -> string[] (legacy)
 *
 * @module utils/workflowTransforms
 */

// Legacy types for UI components (React Flow integration)
import type {
  DAGStructure as LegacyDAGStructure,
  DAGNode as LegacyDAGNode,
  DAGEdge as LegacyDAGEdge,
  WorkflowTemplate as LegacyWorkflowTemplate,
  WorkflowExecution as LegacyWorkflowExecution,
  ValidationResult as LegacyValidationResult,
  NodeStepResult as LegacyNodeStepResult,
} from '../types/workflow'

// Generated types from OpenAPI
import type {
  DAGStructure as GeneratedDAGStructure,
  WorkflowNode as GeneratedWorkflowNode,
  WorkflowEdge as GeneratedWorkflowEdge,
  WorkflowTemplateDetail,
  WorkflowExecutionDetail,
  WorkflowValidateResponse,
  WorkflowStepResult,
} from '../api/generated/model'

type RawOperationRef = {
  alias?: unknown
  binding_mode?: unknown
  template_exposure_id?: unknown
  template_exposure_revision?: unknown
}

type RawOperationIO = {
  mode?: unknown
  input_mapping?: unknown
  output_mapping?: unknown
}

function normalizeOperationRef(raw: unknown): LegacyDAGNode['operation_ref'] {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return undefined
  }
  const candidate = raw as RawOperationRef
  const alias = typeof candidate.alias === 'string' ? candidate.alias.trim() : ''
  if (!alias) {
    return undefined
  }
  const mode = candidate.binding_mode === 'pinned_exposure' ? 'pinned_exposure' : 'alias_latest'
  const exposureId = typeof candidate.template_exposure_id === 'string'
    ? candidate.template_exposure_id.trim()
    : ''
  const revisionParsed = Number.parseInt(String(candidate.template_exposure_revision ?? ''), 10)
  const revision = Number.isNaN(revisionParsed) ? undefined : revisionParsed
  return {
    alias,
    binding_mode: mode,
    ...(exposureId ? { template_exposure_id: exposureId } : {}),
    ...(revision !== undefined ? { template_exposure_revision: revision } : {}),
  }
}

function normalizeOperationIO(raw: unknown): LegacyDAGNode['io'] {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return undefined
  }
  const candidate = raw as RawOperationIO
  const mode = candidate.mode === 'explicit_strict' ? 'explicit_strict' : 'implicit_legacy'

  const normalizeMapping = (value: unknown): Record<string, string> => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return {}
    }
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([key, rawPath]) => typeof key === 'string' && typeof rawPath === 'string')
      .map(([key, rawPath]) => [key, String(rawPath)] as const)
    return Object.fromEntries(entries)
  }

  return {
    mode,
    input_mapping: normalizeMapping(candidate.input_mapping),
    output_mapping: normalizeMapping(candidate.output_mapping),
  }
}

// ============================================================================
// Edge Transformations
// ============================================================================

/**
 * Convert generated DAG edge to legacy format.
 * Generated: { from, to, condition }
 * Legacy: { from, to, condition }
 */
export function convertEdgeToLegacy(edge: GeneratedWorkflowEdge): LegacyDAGEdge {
  return {
    from: edge.from,
    to: edge.to,
    condition: edge.condition ?? undefined,
  }
}

/**
 * Convert legacy DAG edge to generated format for API calls.
 * Legacy: { from, to, condition }
 * Generated: { from, to, condition }
 */
export function convertEdgeToGenerated(edge: LegacyDAGEdge): GeneratedWorkflowEdge {
  return {
    from: edge.from,
    to: edge.to,
    condition: edge.condition ?? null,
  }
}

// ============================================================================
// Wait For Transformations
// ============================================================================

/**
 * Convert wait_for from generated string to legacy union type.
 * Generated: string ("all" | "any" | "3")
 * Legacy: 'all' | 'any' | number
 */
export function convertWaitFor(waitFor?: string): 'all' | 'any' | number | undefined {
  if (waitFor === undefined) return undefined
  if (waitFor === 'all' || waitFor === 'any') return waitFor
  const num = parseInt(waitFor, 10)
  return Number.isNaN(num) ? undefined : num
}

/**
 * Convert legacy wait_for to generated string format.
 * Legacy: 'all' | 'any' | number
 * Generated: string
 */
export function convertWaitForToString(waitFor?: 'all' | 'any' | number): string | undefined {
  if (waitFor === undefined) return undefined
  return String(waitFor)
}

// ============================================================================
// Node Transformations
// ============================================================================

/**
 * Convert generated DAG node to legacy format.
 * Merges specialized configs (parallel_config, loop_config, subworkflow_config)
 * into the unified 'config' field for legacy UI components.
 */
export function convertNodeToLegacy(node: GeneratedWorkflowNode): LegacyDAGNode {
  const operationRef = normalizeOperationRef(
    (node as GeneratedWorkflowNode & { operation_ref?: unknown }).operation_ref
  )
  const operationIo = normalizeOperationIO(
    (node as GeneratedWorkflowNode & { io?: unknown }).io
  )

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
    template_id: node.template_id ?? operationRef?.alias ?? undefined,
    operation_ref: operationRef,
    io: operationIo,
    config: mergedConfig,
    // Note: position is not present in generated type, will be undefined
    position: (node as unknown as LegacyDAGNode).position,
  }
}

/**
 * Convert legacy DAG node to generated format for API calls.
 * Extracts specialized configs from unified 'config' field into separate fields.
 */
export function convertNodeToGenerated(node: LegacyDAGNode): GeneratedWorkflowNode {
  // Build generated node with proper type conversions
  const generatedNode: GeneratedWorkflowNode = {
    id: node.id,
    name: node.name,
    type: node.type as GeneratedWorkflowNode['type'],
    template_id: node.template_id ?? null,
    config: node.config
      ? {
          timeout_seconds: node.config.timeout,
          max_retries: node.config.retries,
          expression: node.config.expression ?? null,
        }
      : undefined,
  }

  const operationRef = normalizeOperationRef(node.operation_ref)
  if (operationRef) {
    ;(generatedNode as GeneratedWorkflowNode & { operation_ref?: unknown }).operation_ref = operationRef
  }
  const operationIo = normalizeOperationIO(node.io)
  if (operationIo) {
    ;(generatedNode as GeneratedWorkflowNode & { io?: unknown }).io = operationIo
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
}

// ============================================================================
// DAG Structure Transformations
// ============================================================================

/**
 * Convert generated DAG structure to legacy format.
 */
export function convertDAGToLegacy(dag: GeneratedDAGStructure): LegacyDAGStructure {
  return {
    nodes: dag.nodes.map(convertNodeToLegacy),
    edges: (dag.edges ?? []).map(convertEdgeToLegacy),
  }
}

/**
 * Convert legacy DAG structure to generated format for API calls.
 */
export function convertDAGToGenerated(dag: LegacyDAGStructure): GeneratedDAGStructure {
  return {
    nodes: dag.nodes.map(convertNodeToGenerated),
    edges: dag.edges.map(convertEdgeToGenerated),
  }
}

// ============================================================================
// Workflow Template Transformations
// ============================================================================

/**
 * Convert WorkflowTemplateDetail to legacy WorkflowTemplate format.
 */
export function convertTemplateToLegacy(detail: WorkflowTemplateDetail): LegacyWorkflowTemplate {
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

// ============================================================================
// Workflow Execution Transformations
// ============================================================================

/**
 * Convert WorkflowExecutionDetail to legacy WorkflowExecution format.
 */
export function convertExecutionToLegacy(detail: WorkflowExecutionDetail): LegacyWorkflowExecution {
  // Handle progress_percent correctly: parseFloat for string to number
  // If detail.progress_percent is NaN (invalid string), we fallback to 0
  const progressPercent = parseFloat(detail.progress_percent)

  return {
    id: detail.id,
    workflow_template: detail.workflow_template,
    workflow_template_name: detail.template_name,
    input_context: detail.input_context as Record<string, unknown>,
    status: detail.status as LegacyWorkflowExecution['status'],
    progress_percent: Number.isNaN(progressPercent) ? 0 : progressPercent,
    current_node_id: detail.current_node_id || undefined,
    // Convert Record<string, any> to string[] by taking keys
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

// ============================================================================
// Validation Response Transformations
// ============================================================================

/**
 * Convert WorkflowValidateResponse to legacy ValidationResult format.
 */
export function convertValidationToLegacy(response: WorkflowValidateResponse): LegacyValidationResult {
  const toNodeIds = (msg: unknown): string[] | undefined => {
    if (!msg || typeof msg !== 'object') return undefined
    const maybe = msg as { node_ids?: string[]; node_id?: string | null }
    if (Array.isArray(maybe.node_ids) && maybe.node_ids.length > 0) return maybe.node_ids
    if (maybe.node_id) return [maybe.node_id]
    return undefined
  }

  const errors: LegacyValidationResult['errors'] = (response.errors ?? []).map(msg => ({
    severity: 'error' as const,
    message: typeof msg === 'string' ? msg : msg.message,
    node_ids: toNodeIds(msg),
  }))
  const warnings: LegacyValidationResult['warnings'] = (response.warnings ?? []).map(msg => ({
    severity: 'warning' as const,
    message: typeof msg === 'string' ? msg : msg.message,
    node_ids: toNodeIds(msg),
  }))

  return {
    is_valid: response.valid,
    issues: [...errors, ...warnings],
    errors,
    warnings,
  }
}

// ============================================================================
// Step Result Transformations
// ============================================================================

/**
 * Convert WorkflowStepResult to legacy NodeStepResult format.
 */
export function convertStepToLegacy(step: WorkflowStepResult): LegacyNodeStepResult {
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
