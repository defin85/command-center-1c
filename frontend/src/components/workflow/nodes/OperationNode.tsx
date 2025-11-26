/**
 * OperationNode - Custom React Flow node for operation type.
 *
 * Displays operation node with template info and execution status.
 */

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Card, Tag, Tooltip, Spin } from 'antd'
import {
  ToolOutlined,
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

const OperationNode = ({ data, selected }: NodeProps<WorkflowNodeData>) => {
  const status = data.status || 'pending'
  const { color, icon } = statusConfig[status]

  return (
    <div className={`workflow-node operation-node ${selected ? 'selected' : ''}`}>
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
            <ToolOutlined className="node-icon" style={{ color: '#1890ff' }} />
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
          {data.templateId && (
            <Tooltip title="Operation Template">
              <div className="node-field">
                <span className="field-label">Template:</span>
                <span className="field-value">{data.templateId}</span>
              </div>
            </Tooltip>
          )}

          {data.config?.timeout && (
            <div className="node-field">
              <span className="field-label">Timeout:</span>
              <span className="field-value">{data.config.timeout}s</span>
            </div>
          )}

          {status === 'running' && (
            <div className="node-running">
              <Spin size="small" /> Executing...
            </div>
          )}

          {data.durationMs !== undefined && status !== 'pending' && status !== 'running' && (
            <div className="node-field">
              <span className="field-label">Duration:</span>
              <span className="field-value">{(data.durationMs / 1000).toFixed(2)}s</span>
            </div>
          )}

          {data.error && (
            <Tooltip title={data.error}>
              <div className="node-error">
                <CloseCircleOutlined /> Error
              </div>
            </Tooltip>
          )}
        </div>
      </Card>

      <Handle type="source" position={Position.Bottom} className="node-handle" />
    </div>
  )
}

export default memo(OperationNode)
