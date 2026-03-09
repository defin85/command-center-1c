/**
 * Workflow Types - Frontend-specific types for React Flow workflow designer.
 *
 * This file contains TWO categories of types:
 *
 * 1. API Mirror Types (lines 12-175):
 *    - DAGNode, DAGEdge, DAGStructure
 *    - WorkflowTemplate, WorkflowExecution, etc.
 *    - These DUPLICATE generated types but are kept for React Flow compatibility
 *    - TODO: Migrate to generated types when React Flow adapter is ready
 *
 * 2. Frontend-only Types (lines 177-301):
 *    - WorkflowNodeData, WorkflowNode, WorkflowEdge (React Flow specific)
 *    - Conversion functions (dagNodeToReactFlow, reactFlowToDagNode, etc.)
 *    - NODE_TYPE_INFO constants for palette
 *    - These will NEVER be generated as they are UI-specific
 *
 * Related:
 * - frontend/src/api/generated/model/workflow*.ts (generated API types)
 * - frontend/src/components/workflow/ (React Flow components)
 *
 * @module types/workflow
 */

// ============================================================================
// DAG Structure Types (match backend models.py)
// ============================================================================

export type NodeType = 'operation' | 'condition' | 'parallel' | 'loop' | 'subworkflow'
export type WorkflowType = 'sequential' | 'parallel' | 'conditional' | 'complex'
export type OperationBindingMode = 'alias_latest' | 'pinned_exposure'
export type OperationIOMode = 'implicit_legacy' | 'explicit_strict'
export type SubWorkflowBindingMode = 'direct_runtime_id' | 'pinned_revision'

export interface OperationRef {
  alias: string
  binding_mode: OperationBindingMode
  template_exposure_id?: string
  template_exposure_revision?: number
}

export interface DecisionRef {
  decision_table_id: string
  decision_key: string
  decision_revision: number
}

export interface SubWorkflowRef {
  binding_mode?: SubWorkflowBindingMode
  workflow_definition_key?: string | null
  workflow_revision_id?: string | null
  workflow_revision?: number | null
}

export interface OperationIO {
  mode: OperationIOMode
  input_mapping: Record<string, string>
  output_mapping: Record<string, string>
}

export interface NodeConfig {
  timeout?: number
  retries?: number
  retry_delay?: number
  expression?: string           // For condition nodes
  parallel_nodes?: string[]     // For parallel nodes
  wait_for?: 'all' | 'any' | number
  loop_mode?: 'count' | 'while' | 'foreach'
  loop_count?: number
  loop_condition?: string
  loop_items?: string
  max_iterations?: number
  subworkflow_id?: string       // For subworkflow nodes
  subworkflow_ref?: SubWorkflowRef
  input_mapping?: Record<string, string>
  output_mapping?: Record<string, string>
}

export interface DAGNode {
  id: string
  name: string
  type: NodeType
  template_id?: string          // For operation nodes
  operation_ref?: OperationRef  // OperationExposure binding for operation nodes
  decision_ref?: DecisionRef
  io?: OperationIO              // Explicit data-flow contract for operation nodes
  config?: NodeConfig
  position?: { x: number; y: number }  // For React Flow
}

export interface DAGEdge {
  from: string
  to: string
  condition?: string            // For conditional branches
}

export interface DAGStructure {
  nodes: DAGNode[]
  edges: DAGEdge[]
}

// ============================================================================
// Workflow Template Types
// ============================================================================

export interface WorkflowTemplateConfig {
  timeout_seconds?: number
  max_retries?: number
  retry_delay_seconds?: number
  allow_parallel?: boolean
  require_confirmation?: boolean
  notification_channels?: string[]
}

export interface WorkflowTemplate {
  id: string
  name: string
  description?: string
  workflow_type: WorkflowType
  category?: string
  dag_structure: DAGStructure
  config?: WorkflowTemplateConfig
  is_valid: boolean
  is_active: boolean
  is_system_managed?: boolean
  management_mode?: string
  visibility_surface?: string
  read_only_reason?: string | null
  created_at: string
  updated_at: string
  created_by?: string
  version?: number
}

export interface WorkflowTemplateCreate {
  name: string
  description?: string
  workflow_type?: WorkflowType
  dag_structure: DAGStructure
  config?: WorkflowTemplateConfig
  is_active?: boolean
}

export interface WorkflowTemplateUpdate {
  name?: string
  description?: string
  workflow_type?: WorkflowType
  dag_structure?: DAGStructure
  config?: WorkflowTemplateConfig
  is_active?: boolean
}

// ============================================================================
// Operation Template Types (for node configuration)
// ============================================================================

export interface OperationTemplateExecutionCapability {
  id: string
  label: string
  operationType: string
  targetEntity: string
  executorKind: string
}

export interface OperationTemplateExecutionInput {
  mode: string
  requiredParameters: string[]
  optionalParameters: string[]
  parameterSchemas: Record<string, Record<string, unknown>>
}

export interface OperationTemplateExecutionOutput {
  resultPath: string
  supportsStructuredMapping: boolean
}

export interface OperationTemplateExecutionSideEffect {
  executionMode: string
  effectKind: string
  summary?: string
  timeoutSeconds?: number
  maxRetries?: number
}

export interface OperationTemplateExecutionProvenance {
  surface: string
  alias: string
  exposureId: string
  exposureRevision?: number
  definitionId: string
  executorCommandId?: string
}

export interface OperationTemplateExecutionContract {
  contractVersion: string
  capability: OperationTemplateExecutionCapability
  input: OperationTemplateExecutionInput
  output: OperationTemplateExecutionOutput
  sideEffect: OperationTemplateExecutionSideEffect
  provenance: OperationTemplateExecutionProvenance
}

export interface OperationTemplateListItem {
  id: string
  name: string
  operation_type: string
  description?: string
  exposure_id?: string
  exposure_revision?: number
  executionContract?: OperationTemplateExecutionContract
}

export interface AvailableWorkflowRevision {
  id: string
  name: string
  workflowDefinitionKey: string
  workflowRevisionId: string
  workflowRevision: number
}

export interface AvailableDecisionRevision {
  id: string
  name: string
  decisionTableId: string
  decisionKey: string
  decisionRevision: number
}

// ============================================================================
// Workflow Execution Types
// ============================================================================

export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

export interface NodeStepResult {
  id: string
  node_id: string
  status: StepStatus
  input_data?: Record<string, unknown>
  output_data?: Record<string, unknown>
  error_message?: string
  started_at?: string
  completed_at?: string
  duration_seconds?: number
  trace_id?: string
  span_id?: string
}

export interface WorkflowExecution {
  id: string
  workflow_template: string
  workflow_template_name?: string
  input_context: Record<string, unknown>
  status: ExecutionStatus
  progress_percent: number
  current_node_id?: string
  completed_nodes: string[]
  failed_nodes: string[]
  final_result?: Record<string, unknown>
  error_message?: string
  error_node_id?: string
  trace_id?: string
  started_at?: string
  completed_at?: string
  created_at: string
  updated_at: string
  duration_seconds?: number
}

export interface WorkflowExecutionCreate {
  input_context: Record<string, unknown>
  async?: boolean
}

// ============================================================================
// Validation Types
// ============================================================================

export type ValidationSeverity = 'error' | 'warning' | 'info'

export interface ValidationIssue {
  severity: ValidationSeverity
  message: string
  node_ids?: string[]
  details?: Record<string, unknown>
}

export interface ValidationResult {
  is_valid: boolean
  issues: ValidationIssue[]
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
}

// ============================================================================
// React Flow Conversion Types
// ============================================================================

import { Node, Edge, XYPosition } from 'reactflow'

export interface WorkflowNodeData {
  label: string
  nodeType: NodeType
  templateId?: string
  operationRef?: OperationRef
  decisionRef?: DecisionRef
  io?: OperationIO
  config?: NodeConfig
  status?: StepStatus          // For monitor mode
  output?: Record<string, unknown>
  error?: string
  durationMs?: number
}

export type WorkflowNode = Node<WorkflowNodeData>
export type WorkflowEdge = Edge

// Conversion helpers
export const dagNodeToReactFlow = (node: DAGNode, index: number): WorkflowNode => {
  const defaultPosition: XYPosition = {
    x: 250,
    y: 100 + index * 120
  }

  return {
    id: node.id,
    type: `workflow-${node.type}`,  // Custom node type
    position: node.position || defaultPosition,
    data: {
      label: node.name,
      nodeType: node.type,
      templateId: node.template_id,
      operationRef: node.operation_ref,
      decisionRef: node.decision_ref,
      io: node.io,
      config: node.config
    }
  }
}

export const dagEdgeToReactFlow = (edge: DAGEdge): WorkflowEdge => {
  return {
    id: `${edge.from}-${edge.to}`,
    source: edge.from,
    target: edge.to,
    label: edge.condition,
    type: edge.condition ? 'step' : 'smoothstep',
    animated: false
  }
}

export const reactFlowToDagNode = (node: WorkflowNode): DAGNode => {
  return {
    id: node.id,
    name: node.data.label,
    type: node.data.nodeType,
    template_id: node.data.templateId,
    operation_ref: node.data.operationRef,
    decision_ref: node.data.decisionRef,
    io: node.data.io,
    config: node.data.config,
    position: node.position
  }
}

export const reactFlowToDagEdge = (edge: WorkflowEdge): DAGEdge => {
  return {
    from: edge.source,
    to: edge.target,
    condition: edge.label as string | undefined
  }
}

// ============================================================================
// Node Type Metadata (for palette)
// ============================================================================

export interface NodeTypeInfo {
  type: NodeType
  label: string
  description: string
  icon: string
  color: string
  requiredFields: string[]
}

export const NODE_TYPE_INFO: Record<NodeType, NodeTypeInfo> = {
  operation: {
    type: 'operation',
    label: 'Operation Task',
    description: 'Run a reusable atomic operation from the templates catalog',
    icon: 'ToolOutlined',
    color: '#1890ff',
    requiredFields: ['template_id']
  },
  condition: {
    type: 'condition',
    label: 'Decision Gate',
    description: 'Route the scheme through an explicit branch or decision point',
    icon: 'BranchesOutlined',
    color: '#faad14',
    requiredFields: ['expression']
  },
  parallel: {
    type: 'parallel',
    label: 'Parallel Stage',
    description: 'Run several scheme steps at the same time and join them later',
    icon: 'ForkOutlined',
    color: '#52c41a',
    requiredFields: ['parallel_nodes']
  },
  loop: {
    type: 'loop',
    label: 'Repeat Stage',
    description: 'Repeat a scheme fragment with explicit iteration rules',
    icon: 'SyncOutlined',
    color: '#722ed1',
    requiredFields: ['loop_mode']
  },
  subworkflow: {
    type: 'subworkflow',
    label: 'Subworkflow Call',
    description: 'Reuse another workflow definition as a pinned scheme fragment',
    icon: 'ApartmentOutlined',
    color: '#eb2f96',
    requiredFields: ['subworkflow_id']
  }
}
