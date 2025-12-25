/**
 * SubWorkflowNode - Custom React Flow node for sub-workflow execution.
 *
 * Container node that executes another workflow.
 */

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Card, Tag, Tooltip, Button } from 'antd'
import {
  ApartmentOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  MinusCircleOutlined,
  ExportOutlined
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

const toStringValue = (value: unknown): string | null => {
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number') {
    return `${value}`
  }
  return null
}

const SubWorkflowNode = ({ data, selected }: NodeProps<WorkflowNodeData>) => {
  const status = data.status || 'pending'
  const { color, icon } = statusConfig[status]

  const subworkflowId = data.config?.subworkflow_id
  const inputMapping = data.config?.input_mapping || {}
  const outputMapping = data.config?.output_mapping || {}
  const subExecutionId = toStringValue(data.output?.sub_execution_id)

  const handleOpenSubWorkflow = () => {
    if (subworkflowId) {
      // Open sub-workflow in new tab/modal
      window.open(`/workflows/${subworkflowId}`, '_blank')
    }
  }

  return (
    <div className={`workflow-node subworkflow-node ${selected ? 'selected' : ''}`}>
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
            <ApartmentOutlined className="node-icon" style={{ color: '#eb2f96' }} />
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
          {subworkflowId && (
            <div className="node-field">
              <span className="field-label">Workflow:</span>
              <Tooltip title="Open sub-workflow">
                <Button
                  type="link"
                  size="small"
                  onClick={handleOpenSubWorkflow}
                  className="subworkflow-link"
                >
                  {subworkflowId.slice(0, 8)}...
                  <ExportOutlined />
                </Button>
              </Tooltip>
            </div>
          )}

          {Object.keys(inputMapping).length > 0 && (
            <Tooltip title={JSON.stringify(inputMapping, null, 2)}>
              <div className="node-field">
                <span className="field-label">Inputs:</span>
                <span className="field-value">{Object.keys(inputMapping).length} mapped</span>
              </div>
            </Tooltip>
          )}

          {Object.keys(outputMapping).length > 0 && (
            <Tooltip title={JSON.stringify(outputMapping, null, 2)}>
              <div className="node-field">
                <span className="field-label">Outputs:</span>
                <span className="field-value">{Object.keys(outputMapping).length} mapped</span>
              </div>
            </Tooltip>
          )}

          {status === 'running' && subExecutionId && (
            <div className="node-field">
              <span className="field-label">Execution:</span>
              <span className="field-value mono">{subExecutionId.slice(0, 8)}...</span>
            </div>
          )}

          {data.durationMs !== undefined && status !== 'pending' && status !== 'running' && (
            <div className="node-field">
              <span className="field-label">Duration:</span>
              <span className="field-value">{(data.durationMs / 1000).toFixed(2)}s</span>
            </div>
          )}
        </div>
      </Card>

      <Handle type="source" position={Position.Bottom} className="node-handle" />
    </div>
  )
}

export default memo(SubWorkflowNode)
