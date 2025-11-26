/**
 * LoopNode - Custom React Flow node for loop execution.
 *
 * Circular node that repeats nodes multiple times.
 */

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Card, Tag, Tooltip, Progress } from 'antd'
import {
  SyncOutlined,
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

const loopModeLabels: Record<string, string> = {
  count: 'Count',
  while: 'While',
  foreach: 'For Each'
}

const LoopNode = ({ data, selected }: NodeProps<WorkflowNodeData>) => {
  const status = data.status || 'pending'
  const { color, icon } = statusConfig[status]

  const loopMode = data.config?.loop_mode || 'count'
  const loopCount = data.config?.loop_count || 0
  const maxIterations = data.config?.max_iterations || 100

  return (
    <div className={`workflow-node loop-node ${selected ? 'selected' : ''}`}>
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
            <SyncOutlined className="node-icon" style={{ color: '#722ed1' }} spin={status === 'running'} />
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
            <span className="field-label">Mode:</span>
            <Tag color="purple">{loopModeLabels[loopMode] || loopMode}</Tag>
          </div>

          {loopMode === 'count' && (
            <div className="node-field">
              <span className="field-label">Count:</span>
              <span className="field-value">{loopCount}</span>
            </div>
          )}

          {loopMode === 'while' && data.config?.loop_condition && (
            <Tooltip title={data.config.loop_condition}>
              <div className="node-field expression">
                <code>{data.config.loop_condition.slice(0, 25)}...</code>
              </div>
            </Tooltip>
          )}

          {loopMode === 'foreach' && data.config?.loop_items && (
            <div className="node-field">
              <span className="field-label">Items:</span>
              <span className="field-value">{data.config.loop_items}</span>
            </div>
          )}

          {status === 'running' && data.output?.current_iteration !== undefined && (
            <div className="node-progress">
              <span className="iteration-counter">
                Iteration {data.output.current_iteration + 1}
                {loopMode === 'count' ? ` / ${loopCount}` : ` (max ${maxIterations})`}
              </span>
              {loopMode === 'count' && (
                <Progress
                  percent={Math.round(((data.output.current_iteration + 1) / loopCount) * 100)}
                  size="small"
                  status="active"
                />
              )}
            </div>
          )}

          {data.output?.total_iterations !== undefined && status !== 'running' && (
            <div className="node-field">
              <span className="field-label">Iterations:</span>
              <span className="field-value">{data.output.total_iterations}</span>
            </div>
          )}
        </div>
      </Card>

      {/* Loop body output */}
      <Handle
        type="source"
        position={Position.Right}
        id="body"
        className="node-handle handle-loop-body"
        style={{ background: '#722ed1' }}
      />

      {/* Loop exit */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="exit"
        className="node-handle"
      />
    </div>
  )
}

export default memo(LoopNode)
