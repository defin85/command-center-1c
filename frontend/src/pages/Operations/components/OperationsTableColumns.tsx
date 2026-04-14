import { Button, Space, Tag, Progress, Typography, Tooltip } from 'antd'
import { EyeOutlined, StopOutlined, LinkOutlined } from '@ant-design/icons'
import type { OperationsTableProps, UIBatchOperation } from '../types'
import type { useOperationsTranslation } from '../../../i18n'
import { getStatusColor, getOperationStatusLabel, getOperationTypeLabel } from '../utils'

const { Paragraph } = Typography
type OperationsT = ReturnType<typeof useOperationsTranslation>['t']

type BuildOperationsColumnsParams = Pick<
  OperationsTableProps,
  'onViewDetails' | 'onCancel' | 'onFilterWorkflow' | 'onFilterNode'
> & {
  canCancel?: boolean
  formatDateTime: (value: string) => string
  t: OperationsT
}

export const buildOperationsColumns = ({
  onViewDetails,
  onCancel,
  onFilterWorkflow,
  onFilterNode,
  canCancel = true,
  formatDateTime,
  t,
}: BuildOperationsColumnsParams): import('antd/es/table').ColumnsType<UIBatchOperation> => ([
  {
    title: t(($) => $.table.name),
    dataIndex: 'name',
    key: 'name',
    width: 250,
  },
  {
    title: t(($) => $.table.operationId),
    dataIndex: 'id',
    key: 'id',
    width: 200,
    render: (id: string) => (
      <Paragraph
        copyable={{ text: id, tooltips: [t(($) => $.table.copyId), t(($) => $.table.copied)] }}
        style={{ marginBottom: 0, fontSize: '12px' }}
      >
        <code>{id.substring(0, 8)}{'\u2026'}</code>
      </Paragraph>
    ),
  },
  {
    title: t(($) => $.table.workflow),
    dataIndex: 'workflow_execution_id',
    key: 'workflow_execution_id',
    width: 160,
    render: (_, record) => (
      record.workflow_execution_id ? (
        <Space size={4}>
          <Tag>{record.workflow_execution_id.substring(0, 8)}{'\u2026'}</Tag>
          {onFilterWorkflow && (
            <Tooltip title={t(($) => $.table.filterByWorkflow)}>
              <Button
                size="small"
                type="text"
                icon={<LinkOutlined />}
                onClick={() => onFilterWorkflow(record.workflow_execution_id as string)}
                aria-label={t(($) => $.table.filterByWorkflow)}
              />
            </Tooltip>
          )}
          {record.node_id && onFilterNode && (
            <Tooltip title={t(($) => $.table.filterByNode)}>
              <Button
                size="small"
                type="text"
                icon={<LinkOutlined rotate={90} />}
                onClick={() => onFilterNode(record.node_id as string)}
                aria-label={t(($) => $.table.filterByNode)}
              />
            </Tooltip>
          )}
        </Space>
      ) : t(($) => $.table.noWorkflow)
    ),
  },
  {
    title: t(($) => $.table.type),
    dataIndex: 'operation_type',
    key: 'operation_type',
    width: 150,
    render: (type: string) => <Tag color="blue">{getOperationTypeLabel(type, t)}</Tag>,
  },
  {
    title: t(($) => $.table.status),
    dataIndex: 'status',
    key: 'status',
    width: 120,
    render: (status: string) => (
      <Tag color={getStatusColor(status)}>{getOperationStatusLabel(status, t)}</Tag>
    ),
  },
  {
    title: t(($) => $.table.progress),
    key: 'progress',
    width: 200,
    render: (_, record) => (
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Progress percent={record.progress} size="small" />
        <span style={{ fontSize: '12px' }}>
          {record.failed_tasks > 0
            ? t(($) => $.table.tasksWithFailed, {
              completed: String(record.completed_tasks),
              total: String(record.total_tasks),
              failed: String(record.failed_tasks),
            })
            : t(($) => $.table.tasks, {
              completed: String(record.completed_tasks),
              total: String(record.total_tasks),
            })}
        </span>
      </Space>
    ),
  },
  {
    title: t(($) => $.table.databases),
    dataIndex: 'database_names',
    key: 'databases',
    width: 150,
    render: (names: string[]) => t(($) => $.table.databaseCount, { value: String(names.length) }),
  },
  {
    title: t(($) => $.table.created),
    dataIndex: 'created_at',
    key: 'created_at',
    width: 180,
    render: (date: string) => formatDateTime(date),
  },
  {
    title: t(($) => $.table.duration),
    dataIndex: 'duration_seconds',
    key: 'duration_seconds',
    width: 100,
    render: (seconds: number | null) => {
      if (!seconds) return t(($) => $.inspect.noValue)
      return t(($) => $.table.durationSeconds, { value: String(Math.round(seconds)) })
    },
  },
  {
    title: t(($) => $.table.actions),
    key: 'actions',
    width: 150,
    render: (_, record) => (
      <Space>
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => onViewDetails(record)}
        >
          {t(($) => $.table.details)}
        </Button>
        {record.status === 'processing' && canCancel && (
          <Button
            type="link"
            danger
            icon={<StopOutlined />}
            onClick={() => onCancel(record.id)}
          >
            {t(($) => $.table.cancel)}
          </Button>
        )}
      </Space>
    ),
  },
])
