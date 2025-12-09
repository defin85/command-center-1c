/**
 * Modal component for displaying operation details and task list.
 * Extracted from Operations.tsx.
 */

import { Modal, Space, Table, Tag, Progress, Alert, Typography, Button } from 'antd'
import { MonitorOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { OperationDetailsModalProps, UITask } from '../types'
import { getStatusColor, getOperationTypeLabel } from '../utils'

const { Paragraph } = Typography

/**
 * OperationDetailsModal - Shows detailed operation info with task breakdown
 */
export const OperationDetailsModal = ({
  operation,
  visible,
  onClose,
  onMonitor,
}: OperationDetailsModalProps) => {
  const taskColumns: ColumnsType<UITask> = [
    {
      title: 'Database',
      dataIndex: 'database_name',
      key: 'database_name',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={getStatusColor(status)}>{status}</Tag>,
    },
    {
      title: 'Duration',
      dataIndex: 'duration_seconds',
      key: 'duration',
      render: (seconds: number | null) => (seconds ? `${seconds.toFixed(2)}s` : '-'),
    },
    {
      title: 'Retries',
      dataIndex: 'retry_count',
      key: 'retry_count',
      render: (count: number, record) => `${count}/${record.max_retries}`,
    },
    {
      title: 'Error',
      dataIndex: 'error_message',
      key: 'error',
      render: (error: string) =>
        error ? <span style={{ color: 'red' }}>{error}</span> : '-',
    },
  ]

  return (
    <Modal
      title={`Operation Details: ${operation?.name}`}
      open={visible}
      onCancel={onClose}
      width={1000}
      footer={null}
    >
      {operation && (
        <div>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {/* Operation ID with Monitor Workflow button */}
            <div
              style={{
                padding: '12px',
                background: '#f0f2f5',
                borderRadius: '8px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <strong>Operation ID:</strong>
                <Paragraph
                  copyable={{ text: operation.id }}
                  style={{ marginBottom: 0, marginLeft: 8, display: 'inline' }}
                >
                  <code>{operation.id}</code>
                </Paragraph>
              </div>
              <Button
                type="primary"
                icon={<MonitorOutlined />}
                onClick={() => onMonitor(operation.id)}
              >
                Monitor Workflow
              </Button>
            </div>

            <div>
              <strong>Description:</strong> {operation.description || '-'}
            </div>
            <div>
              <strong>Type:</strong> {getOperationTypeLabel(operation.operation_type)}
            </div>
            <div>
              <strong>Target Entity:</strong> {operation.target_entity || '-'}
            </div>
            <div>
              <strong>Progress:</strong> <Progress percent={operation.progress} />
            </div>
            <div>
              <strong>Statistics:</strong>{' '}
              {`${operation.completed_tasks} completed, ${operation.failed_tasks} failed, ${operation.total_tasks} total`}
            </div>

            {/* Error message from metadata */}
            {operation.status === 'failed' &&
            operation.metadata &&
            (operation.metadata as Record<string, unknown>).error ? (
              <Alert
                type="error"
                showIcon
                message="Operation Failed"
                description={String(
                  (operation.metadata as Record<string, unknown>).error
                )}
              />
            ) : null}

            <h3>Tasks</h3>
            <Table
              columns={taskColumns}
              dataSource={operation.tasks}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Space>
        </div>
      )}
    </Modal>
  )
}
