/**
 * Custom workflow node types for React Flow.
 *
 * Export all node components and the nodeTypes configuration.
 */

import OperationNode from './OperationNode'
import ConditionNode from './ConditionNode'
import ParallelNode from './ParallelNode'
import LoopNode from './LoopNode'
import SubWorkflowNode from './SubWorkflowNode'

// Node type mapping for React Flow
export const nodeTypes = {
  'workflow-operation': OperationNode,
  'workflow-condition': ConditionNode,
  'workflow-parallel': ParallelNode,
  'workflow-loop': LoopNode,
  'workflow-subworkflow': SubWorkflowNode
}

// Export individual components
export {
  OperationNode,
  ConditionNode,
  ParallelNode,
  LoopNode,
  SubWorkflowNode
}
