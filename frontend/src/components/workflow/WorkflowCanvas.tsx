/**
 * WorkflowCanvas - Main React Flow canvas for workflow visualization.
 *
 * Features:
 * - Render DAG nodes and edges
 * - Drag & drop from NodePalette
 * - Connect nodes via handles
 * - Select nodes for PropertyEditor
 * - Design mode vs Monitor mode
 */

import { useCallback, useRef, useMemo, useEffect } from 'react'
import ReactFlow, {
  ReactFlowProvider,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  Connection,
  Node,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  OnConnect,
  OnNodesChange,
  OnEdgesChange,
  XYPosition
} from 'reactflow'
import 'reactflow/dist/style.css'

import { nodeTypes } from './nodes'
import type {
  DAGStructure,
  WorkflowNode,
  WorkflowEdge,
  NodeType
} from '../../types/workflow'
import './WorkflowCanvas.css'

// Mode types
export type CanvasMode = 'design' | 'monitor'

interface WorkflowCanvasProps {
  // Initial DAG structure (from template)
  dagStructure?: DAGStructure
  // Mode: design (editable) or monitor (read-only with status)
  mode?: CanvasMode
  // Callback when DAG changes (design mode)
  onDagChange?: (dag: DAGStructure) => void
  // Callback when node is selected
  onNodeSelect?: (nodeId: string | null) => void
  // Node statuses for monitor mode
  nodeStatuses?: Record<string, {
    status: string
    output?: Record<string, any>
    error?: string
    durationMs?: number
  }>
  // Current executing node ID (monitor mode)
  currentNodeId?: string
}

// Helper to generate unique node ID
const generateNodeId = () => `node_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

// Convert DAG structure to React Flow format
const dagToReactFlow = (dag: DAGStructure): { nodes: WorkflowNode[], edges: WorkflowEdge[] } => {
  const nodes: WorkflowNode[] = dag.nodes.map((node, index) => {
    const defaultPosition: XYPosition = {
      x: 250,
      y: 100 + index * 120
    }

    return {
      id: node.id,
      type: `workflow-${node.type}`,
      position: node.position || defaultPosition,
      data: {
        label: node.name,
        nodeType: node.type,
        templateId: node.template_id,
        config: node.config
      }
    }
  })

  const edges: WorkflowEdge[] = dag.edges.map((edge) => ({
    id: `${edge.from}-${edge.to}`,
    source: edge.from,
    target: edge.to,
    label: edge.condition,
    type: edge.condition ? 'step' : 'smoothstep',
    animated: false
  }))

  return { nodes, edges }
}

// Convert React Flow format to DAG structure
const reactFlowToDag = (nodes: WorkflowNode[], edges: WorkflowEdge[]): DAGStructure => {
  return {
    nodes: nodes.map((node) => ({
      id: node.id,
      name: node.data.label,
      type: node.data.nodeType,
      template_id: node.data.templateId,
      config: node.data.config,
      position: node.position
    })),
    edges: edges.map((edge) => ({
      from: edge.source,
      to: edge.target,
      condition: edge.label as string | undefined
    }))
  }
}

// Inner component that uses React Flow hooks
const WorkflowCanvasInner = ({
  dagStructure,
  mode = 'design',
  onDagChange,
  onNodeSelect,
  nodeStatuses,
  currentNodeId
}: WorkflowCanvasProps) => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition } = useReactFlow()

  // Initialize nodes and edges from DAG structure
  const initialData = useMemo(() => {
    if (dagStructure) {
      return dagToReactFlow(dagStructure)
    }
    return { nodes: [], edges: [] }
  }, []) // Empty deps - only for initial render

  const [nodes, setNodes, onNodesChange] = useNodesState(initialData.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialData.edges)

  // Sync external dagStructure changes with internal state
  useEffect(() => {
    if (dagStructure) {
      const { nodes: newNodes, edges: newEdges } = dagToReactFlow(dagStructure)
      setNodes(newNodes)
      setEdges(newEdges)
    }
  }, [dagStructure, setNodes, setEdges])

  // Update node statuses in monitor mode
  const nodesWithStatus = useMemo(() => {
    if (mode !== 'monitor' || !nodeStatuses) {
      return nodes
    }

    return nodes.map((node) => {
      const status = nodeStatuses[node.id]
      if (status) {
        return {
          ...node,
          data: {
            ...node.data,
            status: status.status,
            output: status.output,
            error: status.error,
            durationMs: status.durationMs
          }
        }
      }
      return node
    })
  }, [nodes, nodeStatuses, mode])

  // Animate edges for current node
  const edgesWithAnimation = useMemo(() => {
    if (mode !== 'monitor' || !currentNodeId) {
      return edges
    }

    return edges.map((edge) => ({
      ...edge,
      animated: edge.target === currentNodeId
    }))
  }, [edges, currentNodeId, mode])

  // Handle connection (design mode only)
  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      if (mode !== 'design') return

      setEdges((eds) => addEdge({
        ...connection,
        type: 'smoothstep',
        animated: false
      }, eds))

      // Notify parent of change
      if (onDagChange) {
        const newEdges = addEdge({
          ...connection,
          type: 'smoothstep',
          animated: false
        }, edges)
        onDagChange(reactFlowToDag(nodes, newEdges as WorkflowEdge[]))
      }
    },
    [mode, setEdges, edges, nodes, onDagChange]
  )

  // Handle nodes change
  const handleNodesChange: OnNodesChange = useCallback(
    (changes) => {
      if (mode !== 'design') return

      onNodesChange(changes)

      // Notify parent after position changes
      const hasPositionChange = changes.some((c) => c.type === 'position' && c.dragging === false)
      if (hasPositionChange && onDagChange) {
        // Use setTimeout to get updated nodes state
        setTimeout(() => {
          setNodes((currentNodes) => {
            onDagChange(reactFlowToDag(currentNodes as WorkflowNode[], edges))
            return currentNodes
          })
        }, 0)
      }
    },
    [mode, onNodesChange, onDagChange, edges, setNodes]
  )

  // Handle edges change
  const handleEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      if (mode !== 'design') return

      onEdgesChange(changes)

      // Notify parent after edge deletion
      const hasDeletion = changes.some((c) => c.type === 'remove')
      if (hasDeletion && onDagChange) {
        setTimeout(() => {
          setEdges((currentEdges) => {
            onDagChange(reactFlowToDag(nodes, currentEdges as WorkflowEdge[]))
            return currentEdges
          })
        }, 0)
      }
    },
    [mode, onEdgesChange, onDagChange, nodes, setEdges]
  )

  // Handle node click
  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (onNodeSelect) {
        onNodeSelect(node.id)
      }
    },
    [onNodeSelect]
  )

  // Handle pane click (deselect)
  const onPaneClick = useCallback(() => {
    if (onNodeSelect) {
      onNodeSelect(null)
    }
  }, [onNodeSelect])

  // Handle drop from NodePalette (design mode)
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      if (mode !== 'design') return

      const nodeType = event.dataTransfer.getData('application/workflow-node-type') as NodeType
      const nodeLabel = event.dataTransfer.getData('application/workflow-node-label')

      if (!nodeType || !nodeLabel) return

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY
      })

      const newNode: WorkflowNode = {
        id: generateNodeId(),
        type: `workflow-${nodeType}`,
        position,
        data: {
          label: nodeLabel,
          nodeType: nodeType,
          config: {}
        }
      }

      setNodes((nds) => [...nds, newNode])

      // Notify parent
      if (onDagChange) {
        onDagChange(reactFlowToDag([...nodes, newNode], edges))
      }
    },
    [mode, screenToFlowPosition, setNodes, nodes, edges, onDagChange]
  )

  return (
    <div
      ref={reactFlowWrapper}
      className={`workflow-canvas-wrapper mode-${mode}`}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <ReactFlow
        nodes={mode === 'monitor' ? nodesWithStatus : nodes}
        edges={mode === 'monitor' ? edgesWithAnimation : edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        snapToGrid
        snapGrid={[15, 15]}
        defaultEdgeOptions={{
          type: 'smoothstep',
          animated: false
        }}
        nodesDraggable={mode === 'design'}
        nodesConnectable={mode === 'design'}
        elementsSelectable={true}
        panOnScroll
        selectionOnDrag={mode === 'design'}
        deleteKeyCode={mode === 'design' ? ['Backspace', 'Delete'] : null}
      >
        <Controls />
        <MiniMap
          nodeStrokeWidth={3}
          zoomable
          pannable
        />
        <Background
          variant={BackgroundVariant.Dots}
          gap={12}
          size={1}
        />
      </ReactFlow>
    </div>
  )
}

// Wrapper component with ReactFlowProvider
const WorkflowCanvas = (props: WorkflowCanvasProps) => {
  return (
    <ReactFlowProvider>
      <WorkflowCanvasInner {...props} />
    </ReactFlowProvider>
  )
}

export default WorkflowCanvas
