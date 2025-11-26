/**
 * NodePalette - Draggable node templates panel.
 *
 * Features:
 * - Display available node types
 * - Drag & drop to canvas
 * - Visual indicators for node types
 */

import { Card, Typography, Tooltip } from 'antd'
import {
  ToolOutlined,
  BranchesOutlined,
  ForkOutlined,
  SyncOutlined,
  ApartmentOutlined
} from '@ant-design/icons'
import type { NodeType } from '../../types/workflow'
import { NODE_TYPE_INFO } from '../../types/workflow'
import './NodePalette.css'

const { Title } = Typography

// Icon mapping
const nodeIcons: Record<NodeType, React.ReactNode> = {
  operation: <ToolOutlined />,
  condition: <BranchesOutlined />,
  parallel: <ForkOutlined />,
  loop: <SyncOutlined />,
  subworkflow: <ApartmentOutlined />
}

interface NodePaletteItemProps {
  type: NodeType
}

const NodePaletteItem = ({ type }: NodePaletteItemProps) => {
  const info = NODE_TYPE_INFO[type]

  const onDragStart = (event: React.DragEvent) => {
    event.dataTransfer.setData('application/workflow-node-type', type)
    event.dataTransfer.setData('application/workflow-node-label', `New ${info.label}`)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <Tooltip title={info.description} placement="right">
      <div
        className="node-palette-item"
        draggable
        onDragStart={onDragStart}
        style={{ borderLeftColor: info.color }}
      >
        <div className="palette-item-icon" style={{ color: info.color }}>
          {nodeIcons[type]}
        </div>
        <div className="palette-item-content">
          <span className="palette-item-label">{info.label}</span>
        </div>
      </div>
    </Tooltip>
  )
}

interface NodePaletteProps {
  collapsed?: boolean
}

const NodePalette = ({ collapsed = false }: NodePaletteProps) => {
  if (collapsed) {
    return (
      <div className="node-palette collapsed">
        {(Object.keys(NODE_TYPE_INFO) as NodeType[]).map((type) => (
          <Tooltip key={type} title={NODE_TYPE_INFO[type].label} placement="right">
            <div
              className="node-palette-item-collapsed"
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('application/workflow-node-type', type)
                e.dataTransfer.setData('application/workflow-node-label', `New ${NODE_TYPE_INFO[type].label}`)
                e.dataTransfer.effectAllowed = 'move'
              }}
              style={{ color: NODE_TYPE_INFO[type].color }}
            >
              {nodeIcons[type]}
            </div>
          </Tooltip>
        ))}
      </div>
    )
  }

  return (
    <Card className="node-palette" size="small">
      <Title level={5} className="palette-title">
        Node Types
      </Title>
      <div className="palette-description">
        Drag nodes to the canvas
      </div>
      <div className="palette-items">
        {(Object.keys(NODE_TYPE_INFO) as NodeType[]).map((type) => (
          <NodePaletteItem key={type} type={type} />
        ))}
      </div>
    </Card>
  )
}

export default NodePalette
