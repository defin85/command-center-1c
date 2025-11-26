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
import React, { useMemo, useCallback } from 'react'
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeTypes,
  MarkerType,
  ConnectionLineType,
} from 'reactflow'
import 'reactflow/dist/style.css'
import ServiceNode, { type ServiceNodeData } from './ServiceNode'
import type {
  ServiceMetrics,
  ServiceConnection,
  ServiceLayoutConfig,
} from '../../types/serviceMesh'
import { DEFAULT_SERVICE_POSITIONS, STATUS_COLORS } from '../../types/serviceMesh'
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

const ServiceFlowDiagram: React.FC<ServiceFlowDiagramProps> = ({
  services,
  connections,
  selectedService,
  onServiceSelect,
  positions = DEFAULT_SERVICE_POSITIONS,
}) => {
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

  // Create nodes from services
  const nodes: Node<ServiceNodeData>[] = useMemo(() => {
    return services.map((service) => {
      const position = positions[service.name] || { x: 0, y: 0 }

      return {
        id: service.name,
        type: 'serviceNode',
        position,
        data: {
          metrics: service,
          onSelect: handleServiceSelect,
          isSelected: selectedService === service.name,
        },
        draggable: true,
      }
    })
  }, [services, positions, selectedService, handleServiceSelect])

  // Create edges from connections
  const edges: Edge[] = useMemo(() => {
    return connections.map((conn) => {
      const edgeColor = getEdgeColor(conn.avgLatencyMs)
      const edgeWidth = getEdgeWidth(conn.requestsPerMinute)

      return {
        id: `${conn.source}-${conn.target}`,
        source: conn.source,
        target: conn.target,
        type: 'smoothstep',
        animated: conn.requestsPerMinute > 0,
        style: {
          stroke: edgeColor,
          strokeWidth: edgeWidth,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edgeColor,
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
  }, [connections])

  // Handle click on empty canvas to deselect
  const handlePaneClick = useCallback(() => {
    onServiceSelect(null)
  }, [onServiceSelect])

  return (
    <div className="service-flow-diagram">
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
