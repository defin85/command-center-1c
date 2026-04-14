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
import { useWorkflowTranslation } from '../../../i18n'
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

const LoopNode = ({ data, selected }: NodeProps<WorkflowNodeData>) => {
  const { t } = useWorkflowTranslation()
  const status = data.status || 'pending'
  const { color, icon } = statusConfig[status]

  const loopMode = data.config?.loop_mode || 'count'
  const loopCount = data.config?.loop_count || 0
  const maxIterations = data.config?.max_iterations || 100
  const currentIteration = toNumber(data.output?.current_iteration)
  const totalIterations = toNumber(data.output?.total_iterations)
  const loopModeLabel = (
    loopMode === 'count'
      ? t('nodeViews.loop.modeValues.count')
      : loopMode === 'while'
        ? t('nodeViews.loop.modeValues.while')
        : loopMode === 'foreach'
          ? t('nodeViews.loop.modeValues.foreach')
          : loopMode
  )

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
            <span className="field-label">{t('nodeViews.loop.fields.mode')}</span>
            <Tag color="purple">{loopModeLabel}</Tag>
          </div>

          {loopMode === 'count' && (
            <div className="node-field">
              <span className="field-label">{t('nodeViews.loop.fields.count')}</span>
              <span className="field-value">{loopCount}</span>
            </div>
          )}

          {loopMode === 'while' && data.config?.loop_condition && (
            <Tooltip title={data.config.loop_condition}>
              <div className="node-field expression">
                <code>{`${data.config.loop_condition.slice(0, 25)}\u2026`}</code>
              </div>
            </Tooltip>
          )}

          {loopMode === 'foreach' && data.config?.loop_items && (
            <div className="node-field">
              <span className="field-label">{t('nodeViews.loop.fields.items')}</span>
              <span className="field-value">{data.config.loop_items}</span>
            </div>
          )}

          {status === 'running' && currentIteration !== null && (
            <div className="node-progress">
              <span className="iteration-counter">
                {loopMode === 'count'
                  ? t('nodeViews.loop.values.iterationWithCount', {
                      current: currentIteration + 1,
                      total: loopCount,
                    })
                  : t('nodeViews.loop.values.iterationWithMax', {
                      current: currentIteration + 1,
                      max: maxIterations,
                    })}
              </span>
              {loopMode === 'count' && loopCount > 0 && (
                <Progress
                  percent={Math.round(((currentIteration + 1) / loopCount) * 100)}
                  size="small"
                  status="active"
                />
              )}
            </div>
          )}

          {totalIterations !== null && status !== 'running' && (
            <div className="node-field">
              <span className="field-label">{t('nodeViews.loop.fields.iterations')}</span>
              <span className="field-value">{totalIterations}</span>
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
