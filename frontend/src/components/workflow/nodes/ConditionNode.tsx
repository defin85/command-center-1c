/**
 * ConditionNode - Custom React Flow node for condition type.
 *
 * Diamond-shaped node for branching logic.
 */

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Card, Tag, Tooltip } from 'antd'
import {
  BranchesOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  MinusCircleOutlined
} from '@ant-design/icons'
import type { WorkflowNodeData, StepStatus } from '../../../types/workflow'
import './nodeStyles.css'

const statusConfig: Record<StepStatus, { color: string; icon: React.ReactNode }> = {
  pending: { color: 'default', icon: <ClockCircleOutlined /> },
  running: { color: 'processing', icon: <LoadingOutlined spin /> },
  completed: { color: 'success', icon: <CheckCircleOutlined /> },
  failed: { color: 'error', icon: <CloseCircleOutlined /> },
  skipped: { color: 'warning', icon: <MinusCircleOutlined /> }
}

const ConditionNode = ({ data, selected }: NodeProps<WorkflowNodeData>) => {
  const status = data.status || 'pending'
  const { color, icon } = statusConfig[status]

  return (
    <div className={`workflow-node condition-node ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Top} className="node-handle" />

      <Card
        size="small"
        className={`node-card status-${status}`}
        styles={{
          header: { padding: '4px 8px', minHeight: 'auto' },
          body: { padding: '8px' }
        }}
        title={
          <div className="node-header">
            <BranchesOutlined className="node-icon" style={{ color: '#faad14' }} />
            <span className="node-title">{data.label}</span>
          </div>
        }
        extra={
          <Tag color={color} className="status-tag">
            {icon}
          </Tag>
        }
      >
        <div className="node-content">
          {data.decisionRef ? (
            <Tooltip title={`${data.decisionRef.decision_key} r${data.decisionRef.decision_revision}`}>
              <div className="node-field expression">
                <code>{`decision:${data.decisionRef.decision_key} r${data.decisionRef.decision_revision}`}</code>
              </div>
            </Tooltip>
          ) : data.config?.expression && (
            <Tooltip title={data.config.expression}>
              <div className="node-field expression">
                <code>{`${data.config.expression.slice(0, 30)}\u2026`}</code>
              </div>
            </Tooltip>
          )}

          {data.output?.result !== undefined && (
            <div className="node-field">
              <span className="field-label">Result:</span>
              <Tag color={data.output.result ? 'green' : 'red'}>
                {data.output.result ? 'TRUE' : 'FALSE'}
              </Tag>
            </div>
          )}
        </div>
      </Card>

      {/* True branch - left side */}
      <Handle
        type="source"
        position={Position.Left}
        id="true"
        className="node-handle handle-true"
        style={{ background: '#52c41a' }}
      />

      {/* False branch - right side */}
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        className="node-handle handle-false"
        style={{ background: '#ff4d4f' }}
      />

      {/* Default/next - bottom */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="default"
        className="node-handle"
      />
    </div>
  )
}

export default memo(ConditionNode)
