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
  ApartmentOutlined,
  CheckCircleOutlined
} from '@ant-design/icons'
import { useWorkflowTranslation } from '../../i18n'
import type { NodeType } from '../../types/workflow'
import { NODE_TYPE_INFO } from '../../types/workflow'
import './NodePalette.css'

const { Title } = Typography

// Icon mapping
const nodeIcons: Record<NodeType, React.ReactNode> = {
  operation: <ToolOutlined />,
  condition: <BranchesOutlined />,
  parallel: <ToolOutlined />,
  loop: <ToolOutlined />,
  subworkflow: <ApartmentOutlined />
}

type PaletteItem = {
  key: string
  type: NodeType
  label: string
  description: string
  color: string
  icon: React.ReactNode
  preset?: 'approval_gate'
}

const buildPaletteItems = (translate: (key: string) => string): PaletteItem[] => [
  {
    key: 'operation_task',
    type: 'operation',
    label: translate('palette.nodes.operation.label'),
    description: translate('palette.nodes.operation.description'),
    color: NODE_TYPE_INFO.operation.color,
    icon: nodeIcons.operation,
  },
  {
    key: 'decision_gate',
    type: 'condition',
    label: translate('palette.nodes.condition.label'),
    description: translate('palette.nodes.condition.description'),
    color: NODE_TYPE_INFO.condition.color,
    icon: nodeIcons.condition,
  },
  {
    key: 'approval_gate',
    type: 'operation',
    label: translate('palette.nodes.approvalGate.label'),
    description: translate('palette.nodes.approvalGate.description'),
    color: '#13c2c2',
    icon: <CheckCircleOutlined />,
    preset: 'approval_gate',
  },
  {
    key: 'subworkflow_call',
    type: 'subworkflow',
    label: translate('palette.nodes.subworkflow.label'),
    description: translate('palette.nodes.subworkflow.description'),
    color: NODE_TYPE_INFO.subworkflow.color,
    icon: nodeIcons.subworkflow,
  },
]

interface NodePaletteItemProps {
  item: PaletteItem
}

const NodePaletteItem = ({ item }: NodePaletteItemProps) => {
  const { t } = useWorkflowTranslation()
  const onDragStart = (event: React.DragEvent) => {
    event.dataTransfer.setData('application/workflow-node-type', item.type)
    event.dataTransfer.setData('application/workflow-node-label', t('palette.drag.newNodeLabel', { label: item.label }))
    if (item.preset) {
      event.dataTransfer.setData('application/workflow-node-preset', item.preset)
    }
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <Tooltip title={item.description} placement="right">
      <div
        className="node-palette-item"
        draggable
        onDragStart={onDragStart}
        style={{ borderLeftColor: item.color }}
      >
        <div className="palette-item-icon" style={{ color: item.color }}>
          {item.icon}
        </div>
        <div className="palette-item-content">
          <span className="palette-item-label">{item.label}</span>
        </div>
      </div>
    </Tooltip>
  )
}

interface NodePaletteProps {
  collapsed?: boolean
}

const NodePalette = ({ collapsed = false }: NodePaletteProps) => {
  const { t } = useWorkflowTranslation()
  const paletteItems = buildPaletteItems(t)

  if (collapsed) {
    return (
      <div className="node-palette collapsed">
        {paletteItems.map((item) => (
          <Tooltip key={item.key} title={item.label} placement="right">
            <div
              className="node-palette-item-collapsed"
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('application/workflow-node-type', item.type)
                e.dataTransfer.setData('application/workflow-node-label', t('palette.drag.newNodeLabel', { label: item.label }))
                if (item.preset) {
                  e.dataTransfer.setData('application/workflow-node-preset', item.preset)
                }
                e.dataTransfer.effectAllowed = 'move'
              }}
              style={{ color: item.color }}
            >
              {item.icon}
            </div>
          </Tooltip>
        ))}
      </div>
    )
  }

  return (
    <Card className="node-palette" size="small">
      <Title level={5} className="palette-title">
        {t('palette.title')}
      </Title>
      <div className="palette-description">
        {t('palette.description')}
      </div>
      <div className="palette-items">
        {paletteItems.map((item) => (
          <NodePaletteItem key={item.key} item={item} />
        ))}
      </div>
    </Card>
  )
}

export default NodePalette
