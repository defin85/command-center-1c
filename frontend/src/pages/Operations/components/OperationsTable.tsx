/**
 * Reusable table component for displaying batch operations.
 * Extracted from Operations.tsx for reusability.
 */

import { Button, Space, Tag, Progress, Typography, Tooltip } from 'antd'
import { EyeOutlined, StopOutlined, LinkOutlined } from '@ant-design/icons'
import type { OperationsTableProps, UIBatchOperation } from '../types'
import { getStatusColor, getOperationTypeLabel } from '../utils'
import { TableToolkit } from '../../../components/table/TableToolkit'

const { Paragraph } = Typography

/**
 * OperationsTable - Reusable table for batch operations
 */
export const buildOperationsColumns = ({
  onViewDetails,
  onCancel,
  onFilterWorkflow,
  onFilterNode,
}: Pick<
  OperationsTableProps,
  'onViewDetails' | 'onCancel' | 'onFilterWorkflow' | 'onFilterNode'
>): import('antd/es/table').ColumnsType<UIBatchOperation> => ([
  {
    title: 'Name',
    dataIndex: 'name',
    key: 'name',
    width: 250,
  },
  {
    title: 'Operation ID',
    dataIndex: 'id',
    key: 'id',
    width: 200,
    render: (id: string) => (
      <Paragraph
        copyable={{ text: id, tooltips: ['Copy ID', 'Copied!'] }}
        style={{ marginBottom: 0, fontSize: '12px' }}
      >
        <code>{id.substring(0, 8)}...</code>
      </Paragraph>
    ),
  },
  {
    title: 'Workflow',
    dataIndex: 'workflow_execution_id',
    key: 'workflow_execution_id',
    width: 160,
    render: (_, record) => (
      record.workflow_execution_id ? (
        <Space size={4}>
          <Tag>{record.workflow_execution_id.substring(0, 8)}...</Tag>
          {onFilterWorkflow && (
            <Tooltip title="Filter by workflow">
              <Button
                size="small"
                type="text"
                icon={<LinkOutlined />}
                onClick={() => onFilterWorkflow(record.workflow_execution_id as string)}
              />
            </Tooltip>
          )}
          {record.node_id && onFilterNode && (
            <Tooltip title="Filter by node">
              <Button
                size="small"
                type="text"
                icon={<LinkOutlined rotate={90} />}
                onClick={() => onFilterNode(record.node_id as string)}
              />
            </Tooltip>
          )}
        </Space>
      ) : '-'
    ),
  },
  {
    title: 'Type',
    dataIndex: 'operation_type',
    key: 'operation_type',
    width: 150,
    render: (type: string) => <Tag color="blue">{getOperationTypeLabel(type)}</Tag>,
  },
  {
    title: 'Status',
    dataIndex: 'status',
    key: 'status',
    width: 120,
    render: (status: string) => (
      <Tag color={getStatusColor(status)}>{status.toUpperCase()}</Tag>
    ),
  },
  {
    title: 'Progress',
    key: 'progress',
    width: 200,
    render: (_, record) => (
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Progress percent={record.progress} size="small" />
        <span style={{ fontSize: '12px' }}>
          {record.completed_tasks}/{record.total_tasks} tasks
          {record.failed_tasks > 0 && ` (${record.failed_tasks} failed)`}
        </span>
      </Space>
    ),
  },
  {
    title: 'Databases',
    dataIndex: 'database_names',
    key: 'databases',
    width: 150,
    render: (names: string[]) => `${names.length} db(s)`,
  },
  {
    title: 'Created',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 180,
    render: (date: string) => new Date(date).toLocaleString(),
  },
  {
    title: 'Duration',
    dataIndex: 'duration_seconds',
    key: 'duration_seconds',
    width: 100,
    render: (seconds: number | null) => {
      if (!seconds) return '-'
      return `${Math.round(seconds)}s`
    },
  },
  {
    title: 'Actions',
    key: 'actions',
    width: 150,
    render: (_, record) => (
      <Space>
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => onViewDetails(record)}
        >
          Details
        </Button>
        {record.status === 'processing' && (
          <Button
            type="link"
            danger
            icon={<StopOutlined />}
            onClick={() => onCancel(record.id)}
          >
            Cancel
          </Button>
        )}
      </Space>
    ),
  },
])

export const OperationsTable = ({
  table,
  operations,
  total,
  loading,
  toolbarActions,
  columns,
}: OperationsTableProps) => {
  return (
    <TableToolkit
      table={table}
      data={operations}
      total={total}
      loading={loading}
      rowKey="id"
      columns={columns}
      tableLayout="fixed"
      scroll={{ x: table.totalColumnsWidth }}
      toolbarActions={toolbarActions}
      searchPlaceholder="Search operations"
    />
  )
}
