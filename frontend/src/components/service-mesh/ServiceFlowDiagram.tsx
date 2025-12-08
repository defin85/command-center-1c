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
import React, { useMemo, useCallback, useRef, useState, useEffect } from 'react'
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeTypes,
  MarkerType,
  ConnectionLineType,
} from 'reactflow'
import { Button } from 'antd'
import { FullscreenOutlined, FullscreenExitOutlined } from '@ant-design/icons'
import 'reactflow/dist/style.css'
import ServiceNode, { type ServiceNodeData } from './ServiceNode'
import type {
  ServiceMetrics,
  ServiceConnection,
  ServiceLayoutConfig,
  OperationFlowEvent,
  OperationFlowStatus,
} from '../../types/serviceMesh'
import { DEFAULT_SERVICE_POSITIONS, STATUS_COLORS } from '../../types/serviceMesh'
import { calculateDagreLayout } from '../../utils/graphLayout'
import './ServiceFlowDiagram.css'

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
}

/**
 * Get edge color based on latency
 */
function getEdgeColor(avgLatencyMs: number): string {
  if (avgLatencyMs > 1000) {
    return STATUS_COLORS.critical
  }
  if (avgLatencyMs > 500) {
    return STATUS_COLORS.degraded
  }
  return '#1890ff'
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
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)

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

  // Calculate positions using dagre (memoized)
  const calculatedPositions = useMemo(() => {
    if (services.length === 0) {
      return positions // fallback to default
    }
    return calculateDagreLayout(services, connections, {
      direction: 'TB',
      rankSep: 120,
      nodeSep: 100,
    })
  }, [services, connections])  // positions is fallback only, doesn't affect calculation

  // Create nodes from services
  const nodes: Node<ServiceNodeData>[] = useMemo(() => {
    return services.map((service) => {
      const position = calculatedPositions[service.name] || positions[service.name] || { x: 0, y: 0 }
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
        },
        draggable: true,
      }
    })
  }, [services, calculatedPositions, positions, selectedService, handleServiceSelect, activeOperation])

  // Create edges from connections
  const edges: Edge[] = useMemo(() => {
    return connections.map((conn) => {
      const operationStyle = getOperationEdgeStyle(conn.source, conn.target, activeOperation)

      // If there is an active operation, use its styles
      const stroke = operationStyle?.stroke || getEdgeColor(conn.avgLatencyMs)
      const strokeWidth = operationStyle?.strokeWidth || getEdgeWidth(conn.requestsPerMinute)
      const animated = operationStyle?.animated ?? (conn.requestsPerMinute > 0)

      return {
        id: `${conn.source}-${conn.target}`,
        source: conn.source,
        target: conn.target,
        type: 'smoothstep',
        animated,
        style: {
          stroke,
          strokeWidth,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: stroke,
          width: 20,
          height: 20,
        },
        label: conn.requestsPerMinute > 0 ? `${conn.requestsPerMinute.toFixed(0)}/min` : undefined,
        labelStyle: {
          fontSize: 10,
          fill: '#8c8c8c',
        },
        labelBgStyle: {
          fill: '#fff',
        },
      }
    })
  }, [connections, activeOperation])

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
        onPaneClick={handlePaneClick}
        connectionLineType={ConnectionLineType.SmoothStep}
        fitView
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

      {/* Fullscreen button */}
      <div className="service-flow-diagram__fullscreen-button">
        <Button
          icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          onClick={toggleFullscreen}
          title={isFullscreen ? 'Выйти из полноэкранного режима' : 'Полноэкранный режим'}
          size="large"
        />
      </div>

      {/* Legend */}
      <div className="service-flow-diagram__legend">
        <div className="service-flow-diagram__legend-title">Legend</div>
        <div className="service-flow-diagram__legend-item">
          <span
            className="service-flow-diagram__legend-dot"
            style={{ background: STATUS_COLORS.healthy }}
          />
          <span>Healthy</span>
        </div>
        <div className="service-flow-diagram__legend-item">
          <span
            className="service-flow-diagram__legend-dot"
            style={{ background: STATUS_COLORS.degraded }}
          />
          <span>Degraded</span>
        </div>
        <div className="service-flow-diagram__legend-item">
          <span
            className="service-flow-diagram__legend-dot"
            style={{ background: STATUS_COLORS.critical }}
          />
          <span>Critical</span>
        </div>
      </div>
    </div>
  )
}

export default ServiceFlowDiagram
