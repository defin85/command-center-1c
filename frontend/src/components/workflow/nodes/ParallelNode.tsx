/**
 * ParallelNode - Custom React Flow node for parallel execution.
 *
 * Fork-like node that executes multiple nodes concurrently.
 */

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Card, Tag, Progress } from 'antd'
import {
  ForkOutlined,
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

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value)
    return Number.isNaN(parsed) ? null : parsed
  }
  return null
}

const ParallelNode = ({ data, selected }: NodeProps<WorkflowNodeData>) => {
  const status = data.status || 'pending'
  const { color, icon } = statusConfig[status]

  const parallelNodes = data.config?.parallel_nodes || []
  const waitFor = data.config?.wait_for || 'all'
  const completedCount = toNumber(data.output?.completed_count)

  return (
    <div className={`workflow-node parallel-node ${selected ? 'selected' : ''}`}>
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
            <ForkOutlined className="node-icon" style={{ color: '#52c41a' }} />
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
          <div className="node-field">
            <span className="field-label">Parallel:</span>
            <span className="field-value">{parallelNodes.length} nodes</span>
          </div>

          <div className="node-field">
            <span className="field-label">Wait for:</span>
            <Tag color="blue">{waitFor}</Tag>
          </div>

          {status === 'running' && completedCount !== null && parallelNodes.length > 0 && (
            <div className="node-progress">
              <Progress
                percent={Math.round(
                  (completedCount / parallelNodes.length) * 100
                )}
                size="small"
                status="active"
              />
            </div>
          )}
        </div>
      </Card>

      <Handle type="source" position={Position.Bottom} className="node-handle" />
    </div>
  )
}

export default memo(ParallelNode)
