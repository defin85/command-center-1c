/**
 * Workflow Types for React Flow integration.
 *
 * These types mirror the Django backend models and Pydantic schemas
 * for workflow templates and executions.
 */

// ============================================================================
// DAG Structure Types (match backend models.py)
// ============================================================================

export type NodeType = 'operation' | 'condition' | 'parallel' | 'loop' | 'subworkflow'
export type WorkflowType = 'sequential' | 'parallel' | 'conditional' | 'complex'

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
  input_mapping?: Record<string, string>
  output_mapping?: Record<string, string>
}

export interface DAGNode {
  id: string
  name: string
  type: NodeType
  template_id?: string          // For operation nodes
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
  dag_structure: DAGStructure
  config?: WorkflowTemplateConfig
  is_valid: boolean
  is_active: boolean
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

export interface OperationTemplateListItem {
  id: string
  name: string
  operation_type: string
  description?: string
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
  input_data?: Record<string, any>
  output_data?: Record<string, any>
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
  input_context: Record<string, any>
  status: ExecutionStatus
  progress_percent: number
  current_node_id?: string
  completed_nodes: string[]
  failed_nodes: string[]
  final_result?: Record<string, any>
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
  input_context: Record<string, any>
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
  details?: Record<string, any>
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
  config?: NodeConfig
  status?: StepStatus          // For monitor mode
  output?: Record<string, any>
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
    label: 'Operation',
    description: 'Execute an operation template',
    icon: 'ToolOutlined',
    color: '#1890ff',
    requiredFields: ['template_id']
  },
  condition: {
    type: 'condition',
    label: 'Condition',
    description: 'Branch based on expression',
    icon: 'BranchesOutlined',
    color: '#faad14',
    requiredFields: ['expression']
  },
  parallel: {
    type: 'parallel',
    label: 'Parallel',
    description: 'Execute nodes in parallel',
    icon: 'ForkOutlined',
    color: '#52c41a',
    requiredFields: ['parallel_nodes']
  },
  loop: {
    type: 'loop',
    label: 'Loop',
    description: 'Repeat nodes multiple times',
    icon: 'SyncOutlined',
    color: '#722ed1',
    requiredFields: ['loop_mode']
  },
  subworkflow: {
    type: 'subworkflow',
    label: 'Sub-Workflow',
    description: 'Execute another workflow',
    icon: 'ApartmentOutlined',
    color: '#eb2f96',
    requiredFields: ['subworkflow_id']
  }
}
