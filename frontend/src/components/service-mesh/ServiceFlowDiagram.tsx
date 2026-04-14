/**
 * Service mesh flow diagram using react-flow.
 *
 * Displays:
 * - Service nodes with metrics
 * - Connections between services with traffic indicators
 * - Interactive selection for detail drawer
 *
 * Layout:
 *        [Frontend]
 *            |
 *       [API Gateway]
 *      /     |      \
 * [Orch] [Worker] [RAS]
 */
import React, { useCallback, useRef, useState, useEffect } from 'react'
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeTypes,
  MarkerType,
  ConnectionLineType,
  useNodesState,
  useEdgesState,
} from 'reactflow'
import { Button, Segmented } from 'antd'
import { FullscreenOutlined, FullscreenExitOutlined } from '@ant-design/icons'
import 'reactflow/dist/style.css'
import { useServiceMeshTranslation } from '../../i18n'
import ServiceNode, { type ServiceNodeData } from './ServiceNode'
import type {
  ServiceMetrics,
  ServiceConnection,
  ServiceLayoutConfig,
  OperationFlowEvent,
  OperationFlowStatus,
  ConnectionType,
  LayoutDirection,
  DirectionMode,
} from '../../types/serviceMesh'
import {
  DEFAULT_SERVICE_POSITIONS,
  STATUS_COLORS,
  CONNECTION_TYPE_COLORS,
  CONNECTION_TYPE_DASHARRAY,
  CONNECTION_TYPES,
} from '../../types/serviceMesh'
import { calculateDagreLayout } from '../../utils/graphLayout'
import './ServiceFlowDiagram.css'

const NODES_UPDATE_THROTTLE = 100 // ms - throttle node updates

// Register custom node types
const nodeTypes: NodeTypes = {
  serviceNode: ServiceNode,
}

interface ServiceFlowDiagramProps {
  services: ServiceMetrics[]
  connections: ServiceConnection[]
  selectedService: string | null
  onServiceSelect: (service: string | null) => void
  positions?: ServiceLayoutConfig
  activeOperation?: OperationFlowEvent | null
  /** Current direction mode (TB, LR, or auto) */
  directionMode: DirectionMode
  /** Calculated layout direction */
  direction: LayoutDirection
  /** Callback when user changes direction mode */
  onDirectionModeChange: (mode: DirectionMode) => void
}

/**
 * Get connection type for a source-target pair
 */
function getConnectionType(source: string, target: string): ConnectionType {
  const key = `${source}->${target}`
  return CONNECTION_TYPES[key] || 'http'
}

/**
 * Get edge color based on latency and connection type
 */
function getEdgeColor(source: string, target: string, avgLatencyMs: number): string {
  if (avgLatencyMs > 1000) {
    return STATUS_COLORS.critical
  }
  if (avgLatencyMs > 500) {
    return STATUS_COLORS.degraded
  }
  const connType = getConnectionType(source, target)
  return CONNECTION_TYPE_COLORS[connType]
}

/**
 * Get edge width based on requests per minute
 */
function getEdgeWidth(requestsPerMinute: number): number {
  if (requestsPerMinute > 1000) {
    return 4
  }
  if (requestsPerMinute > 100) {
    return 3
  }
  if (requestsPerMinute > 10) {
    return 2
  }
  return 1
}

function getConnectionBaseWidth(connType: ConnectionType): number {
  // Non-HTTP edges can be hard to see on large graphs, so give them a small baseline.
  switch (connType) {
    case 'database':
    case 'streams':
    case 'queue':
    case 'pubsub':
    case 'tcp':
      return 2
    default:
      return 1
  }
}

/**
 * Get edge style based on active operation flow
 */
function getOperationEdgeStyle(
  source: string,
  target: string,
  activeOperation: OperationFlowEvent | null | undefined
): { stroke: string; strokeWidth: number; animated: boolean } | null {
  if (!activeOperation) return null

  const flowEdge = activeOperation.flow.edges.find(
    (e) => e.from === source && e.to === target
  )

  if (!flowEdge) {
    // Edge not in operation path - dim it
    return {
      stroke: '#d9d9d9',
      strokeWidth: 1,
      animated: false,
    }
  }

  switch (flowEdge.status) {
    case 'active':
      return {
        stroke: '#1890ff',
        strokeWidth: 4,
        animated: true,
      }
    case 'completed':
      return {
        stroke: '#52c41a',
        strokeWidth: 3,
        animated: false,
      }
    case 'failed':
      return {
        stroke: '#ff4d4f',
        strokeWidth: 3,
        animated: true,
      }
    default:
      return {
        stroke: '#d9d9d9',
        strokeWidth: 1,
        animated: false,
      }
  }
}

/**
 * Get operation status for a service node
 */
function getNodeOperationStatus(
  serviceName: string,
  activeOperation: OperationFlowEvent | null | undefined
): OperationFlowStatus | null {
  if (!activeOperation) return null

  const pathNode = activeOperation.flow.path.find((p) => p.service === serviceName)
  return pathNode?.status || null
}

const ServiceFlowDiagram: React.FC<ServiceFlowDiagramProps> = ({
  services,
  connections,
  selectedService,
  onServiceSelect,
  positions = DEFAULT_SERVICE_POSITIONS,
  activeOperation,
  directionMode,
  direction,
  onDirectionModeChange,
}) => {
  const { t } = useServiceMeshTranslation()
  const containerRef = useRef<HTMLDivElement>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const isInitialLoadRef = useRef(true)
  const connectionTypeLabels: Record<ConnectionType, string> = {
    http: t(($) => $.connectionTypes.http),
    queue: t(($) => $.connectionTypes.queue),
    database: t(($) => $.connectionTypes.database),
    pubsub: t(($) => $.connectionTypes.pubsub),
    streams: t(($) => $.connectionTypes.streams),
    tcp: t(($) => $.connectionTypes.tcp),
  }
  const connectionShortLabels: Record<ConnectionType, string> = {
    http: t(($) => $.connectionShort.http),
    queue: t(($) => $.connectionShort.queue),
    database: t(($) => $.connectionShort.database),
    pubsub: t(($) => $.connectionShort.pubsub),
    streams: t(($) => $.connectionShort.streams),
    tcp: t(($) => $.connectionShort.tcp),
  }

  // Throttle refs for node/edge updates
  const lastUpdateRef = useRef<number>(0)
  const pendingUpdateRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // React Flow state management
  const [nodes, setNodes, onNodesChange] = useNodesState<ServiceNodeData>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  // Store current node positions to preserve drag positions
  const nodePositionsRef = useRef<Record<string, { x: number; y: number }>>({})
  // Track previous direction to detect changes
  const prevDirectionRef = useRef<LayoutDirection>(direction)

  // Reset saved positions when direction changes
  useEffect(() => {
    if (prevDirectionRef.current !== direction) {
      nodePositionsRef.current = {}
      prevDirectionRef.current = direction
    }
  }, [direction])

  // Handle fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
    }
  }, [])

  // Toggle fullscreen
  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen()
    } else {
      document.exitFullscreen()
    }
  }, [])

  // Handle service selection
  const handleServiceSelect = useCallback(
    (service: string) => {
      if (selectedService === service) {
        onServiceSelect(null) // Deselect if already selected
      } else {
        onServiceSelect(service)
      }
    },
    [selectedService, onServiceSelect]
  )

  // Hover handlers for nodes
  const handleNodeMouseEnter = useCallback((serviceName: string) => {
    setHoveredNode(serviceName)
  }, [])

  const handleNodeMouseLeave = useCallback(() => {
    setHoveredNode(null)
  }, [])

  // Custom onNodesChange handler to track dragged positions
  const handleNodesChange = useCallback(
    (changes: Parameters<typeof onNodesChange>[0]) => {
      // Update positions ref when nodes are dragged
      changes.forEach((change) => {
        if (change.type === 'position' && change.position && change.id) {
          nodePositionsRef.current[change.id] = change.position
        }
      })
      onNodesChange(changes)
    },
    [onNodesChange]
  )

  // Throttled update for nodes and edges to prevent excessive re-renders
  // @ts-expect-error - throttledUpdate prepared for future use when nodes/edges update is unified
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const throttledUpdate = useCallback((newNodes: Node<ServiceNodeData>[], newEdges: Edge[]) => {
    const now = Date.now()
    const timeSinceLastUpdate = now - lastUpdateRef.current

    // Clear pending update
    if (pendingUpdateRef.current) {
      clearTimeout(pendingUpdateRef.current)
      pendingUpdateRef.current = null
    }

    if (timeSinceLastUpdate >= NODES_UPDATE_THROTTLE) {
      // Enough time passed - update immediately
      lastUpdateRef.current = now
      setNodes(newNodes)
      setEdges(newEdges)
    } else {
      // Schedule update for later
      pendingUpdateRef.current = setTimeout(() => {
        lastUpdateRef.current = Date.now()
        setNodes(newNodes)
        setEdges(newEdges)
      }, NODES_UPDATE_THROTTLE - timeSinceLastUpdate)
    }
  }, [setNodes, setEdges])

  // Update nodes when services, selections, or hover state change
  useEffect(() => {
    if (services.length === 0) return

    const calculatedPositions = calculateDagreLayout(services, connections, {
      direction,
      rankSep: 150,
      nodeSep: 120,
    })

    const newNodes: Node<ServiceNodeData>[] = services.map((service) => {
      // Keep existing positions if nodes were dragged, otherwise use calculated
      const draggedPosition = nodePositionsRef.current[service.name]
      const position = draggedPosition || calculatedPositions[service.name] || positions[service.name] || { x: 0, y: 0 }
      const operationStatus = getNodeOperationStatus(service.name, activeOperation)

      return {
        id: service.name,
        type: 'serviceNode',
        position,
        data: {
          metrics: service,
          onSelect: handleServiceSelect,
          isSelected: selectedService === service.name,
          operationStatus,
          onMouseEnter: () => handleNodeMouseEnter(service.name),
          onMouseLeave: handleNodeMouseLeave,
          direction,
        },
        draggable: true,
      }
    })

    setNodes(newNodes)

    // Mark initial load as complete after first render
    if (isInitialLoadRef.current && services.length > 0) {
      isInitialLoadRef.current = false
    }
  }, [services, connections, selectedService, activeOperation, handleServiceSelect, handleNodeMouseEnter, handleNodeMouseLeave, positions, setNodes, direction])

  // Update edges when connections, hover state, or active operation change
  useEffect(() => {
    const focusNode = hoveredNode || selectedService

    const newEdges: Edge[] = connections.map((conn) => {
      const operationStyle = getOperationEdgeStyle(conn.source, conn.target, activeOperation)
      const connType = getConnectionType(conn.source, conn.target)
      const dasharray = CONNECTION_TYPE_DASHARRAY[connType]

      // Find flow edge for status-based className
      const flowEdge = activeOperation?.flow.edges.find(
        (e) => e.from === conn.source && e.to === conn.target
      )

      // Determine CSS class for operation state
      const getEdgeClassName = (): string | undefined => {
        if (!operationStyle) return undefined
        if (operationStyle.animated) return 'operation-active'
        if (flowEdge?.status === 'completed') return 'operation-completed'
        if (flowEdge?.status === 'failed') return 'operation-failed'
        return 'operation-inactive'
      }

      // If there is an active operation, use its styles
      const stroke = operationStyle?.stroke || getEdgeColor(conn.source, conn.target, conn.avgLatencyMs)
      const strokeWidth =
        operationStyle?.strokeWidth ||
        Math.max(getConnectionBaseWidth(connType), getEdgeWidth(conn.requestsPerMinute))
      const animated = operationStyle?.animated ?? (conn.requestsPerMinute > 0)

      // Calculate opacity based on hovered/selected node (focus)
      const isConnectedToFocus = focusNode
        ? conn.source === focusNode || conn.target === focusNode
        : true
      const opacity = focusNode ? (isConnectedToFocus ? 1 : 0.1) : 1

      // Show connection type label when focusing a node (otherwise keep it minimal).
      const shortType = connectionShortLabels[connType]
      const labelText = focusNode
        ? (conn.requestsPerMinute > 0 ? `${shortType} ${conn.requestsPerMinute.toFixed(0)}/m` : shortType)
        : (conn.requestsPerMinute > 0 ? `${conn.requestsPerMinute.toFixed(0)}/min` : undefined)

      return {
        id: `${conn.source}-${conn.target}`,
        source: conn.source,
        target: conn.target,
        type: 'smoothstep',
        animated,
        className: getEdgeClassName(),
        style: {
          stroke,
          strokeWidth,
          strokeDasharray: dasharray,
          opacity,
          transition: 'opacity 0.2s ease',
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: stroke,
          width: 20,
          height: 20,
        },
        label: labelText,
        labelStyle: {
          fontSize: 10,
          fill: '#8c8c8c',
          opacity,
          transition: 'opacity 0.2s ease',
        },
        labelBgStyle: {
          fill: '#fff',
          opacity,
        },
      }
    })

    setEdges(newEdges)
  }, [activeOperation, connectionShortLabels, connections, hoveredNode, selectedService, setEdges])

  // Handle click on empty canvas to deselect
  const handlePaneClick = useCallback(() => {
    onServiceSelect(null)
  }, [onServiceSelect])

  return (
    <div
      ref={containerRef}
      className={`service-flow-diagram ${isFullscreen ? 'service-flow-diagram--fullscreen' : ''}`}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={handleNodesChange}
        onEdgesChange={onEdgesChange}
        onPaneClick={handlePaneClick}
        connectionLineType={ConnectionLineType.SmoothStep}
        fitView={isInitialLoadRef.current}
        fitViewOptions={{
          padding: 0.2,
          minZoom: 0.5,
          maxZoom: 1.5,
        }}
        minZoom={0.3}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#f0f0f0" gap={20} />
        <Controls
          showInteractive={false}
          position="bottom-right"
        />
      </ReactFlow>

      {/* Controls: direction switcher and fullscreen button */}
      <div className="service-flow-diagram__controls">
        <Segmented
          value={directionMode}
          onChange={(value) => onDirectionModeChange(value as DirectionMode)}
          options={[
            { label: 'TB', value: 'TB', title: t(($) => $.flowDiagram.directionTbTitle) },
            { label: 'LR', value: 'LR', title: t(($) => $.flowDiagram.directionLrTitle) },
            { label: 'Auto', value: 'auto', title: t(($) => $.flowDiagram.directionAutoTitle) },
          ]}
          size="small"
        />
        <Button
          icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          onClick={toggleFullscreen}
          title={isFullscreen ? t(($) => $.flowDiagram.fullscreenExit) : t(($) => $.flowDiagram.fullscreenEnter)}
          size="small"
        />
      </div>

      {/* Status Legend */}
      <div className="service-flow-diagram__legend">
        <div className="service-flow-diagram__legend-title">{t(($) => $.flowDiagram.statusLegend)}</div>
        <div className="service-flow-diagram__legend-item">
          <span
            className="service-flow-diagram__legend-dot"
            style={{ background: STATUS_COLORS.healthy }}
          />
          <span>{t(($) => $.status.healthy)}</span>
        </div>
        <div className="service-flow-diagram__legend-item">
          <span
            className="service-flow-diagram__legend-dot"
            style={{ background: STATUS_COLORS.degraded }}
          />
          <span>{t(($) => $.status.degraded)}</span>
        </div>
        <div className="service-flow-diagram__legend-item">
          <span
            className="service-flow-diagram__legend-dot"
            style={{ background: STATUS_COLORS.critical }}
          />
          <span>{t(($) => $.status.critical)}</span>
        </div>
      </div>

      {/* Connection Types Legend */}
      <div className="service-flow-diagram__connection-legend">
        <div className="service-flow-diagram__legend-title">{t(($) => $.flowDiagram.connectionsLegend)}</div>
        {(Object.entries(CONNECTION_TYPE_COLORS) as [ConnectionType, string][]).map(
          ([type, color]) => (
            <div key={type} className="service-flow-diagram__legend-item">
              <span
                className="service-flow-diagram__legend-line"
                style={{
                  borderTop: `3px ${type === 'database' ? 'dotted' : (type === 'http' || type === 'tcp' ? 'solid' : 'dashed')} ${color}`,
                  background: 'transparent',
                }}
              />
              <span>{connectionTypeLabels[type]}</span>
            </div>
          )
        )}
      </div>
    </div>
  )
}

export default ServiceFlowDiagram
