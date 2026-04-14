/**
 * OperationNode - Custom React Flow node for operation type.
 *
 * Displays operation node with template info and execution status.
 * Enhanced with improved error tooltips and trace link indicators.
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
  MinusCircleOutlined,
  LinkOutlined
} from '@ant-design/icons'
import { useWorkflowTranslation } from '../../../i18n'
import type { WorkflowNodeData, StepStatus } from '../../../types/workflow'
import './nodeStyles.css'

// Extended WorkflowNodeData type with spanId for tracing
interface OperationNodeData extends WorkflowNodeData {
  spanId?: string
  isCurrent?: boolean
}

const statusConfig: Record<StepStatus, { color: string; icon: React.ReactNode }> = {
  pending: { color: 'default', icon: <ClockCircleOutlined /> },
  running: { color: 'processing', icon: <LoadingOutlined spin /> },
  completed: { color: 'success', icon: <CheckCircleOutlined /> },
  failed: { color: 'error', icon: <CloseCircleOutlined /> },
  skipped: { color: 'warning', icon: <MinusCircleOutlined /> }
}

const OperationNode = ({ data, selected }: NodeProps<OperationNodeData>) => {
  const { t } = useWorkflowTranslation()
  const status = data.status || 'pending'
  const { color, icon } = statusConfig[status]

  // Build CSS classes
  const nodeClasses = [
    'workflow-node',
    'operation-node',
    selected ? 'selected' : '',
    data.isCurrent ? 'current-node' : ''
  ].filter(Boolean).join(' ')

  // Format error message for tooltip
  const formatErrorTooltip = (error: string) => {
    // Truncate very long errors
    const maxLength = 500
    const truncated = error.length > maxLength
      ? `${error.slice(0, maxLength)}…`
      : error
    return (
      <div className="node-error-tooltip">
        <strong>{t('nodeViews.operation.errorLabel')}</strong>
        <br />
        {truncated}
      </div>
    )
  }

  return (
    <div className={nodeClasses}>
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
            <Tooltip title={t('nodeViews.operation.tooltips.template')}>
              <div className="node-field">
                <span className="field-label">{t('nodeViews.operation.fields.template')}</span>
                <span className="field-value">{data.templateId}</span>
              </div>
            </Tooltip>
          )}

          {data.config?.timeout && (
            <div className="node-field">
              <span className="field-label">{t('nodeViews.operation.fields.timeout')}</span>
              <span className="field-value">{data.config.timeout}s</span>
            </div>
          )}

          {data.io?.mode === 'explicit_strict' && (
            <div className="node-field">
              <span className="field-label">{t('nodeViews.operation.fields.dataFlow')}</span>
              <span className="field-value">{t('nodeViews.operation.values.explicitStrict')}</span>
            </div>
          )}

          {status === 'running' && (
            <div className="node-running">
              <Spin size="small" /> {t('nodeViews.operation.values.executing')}
            </div>
          )}

          {data.durationMs !== undefined && status !== 'pending' && status !== 'running' && (
            <div className="node-field">
              <span className="field-label">{t('nodeViews.operation.fields.duration')}</span>
              <span className="field-value">{(data.durationMs / 1000).toFixed(2)}s</span>
            </div>
          )}

          {data.error && (
            <Tooltip
              title={formatErrorTooltip(data.error)}
              overlayStyle={{ maxWidth: 350 }}
              placement="bottom"
            >
              <div className="node-error">
                <CloseCircleOutlined /> {t('nodeViews.operation.values.error')}
              </div>
            </Tooltip>
          )}

          {data.spanId && (
            <Tooltip title={t('nodeViews.operation.tooltips.trace')}>
              <div className="trace-link-indicator">
                <LinkOutlined />
                <span>{t('nodeViews.operation.values.trace')}</span>
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
