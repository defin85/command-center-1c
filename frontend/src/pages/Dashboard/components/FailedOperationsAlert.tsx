/**
 * Failed operations alert component for Dashboard.
 *
 * Displays a warning card with list of recent failed operations.
 */

import { Card, Alert, List, Button, Badge, Typography, Space } from 'antd'
import { WarningOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import type { UIBatchOperation } from '../types'
import { getOperationTypeLabel } from '../../Operations/utils'

// Enable relative time plugin
dayjs.extend(relativeTime)

const { Text } = Typography

export interface FailedOperationsAlertProps {
  /** Failed operations to display */
  operations: UIBatchOperation[]
  /** Maximum number of operations to display (default: 5) */
  maxDisplay?: number
}

/**
 * Truncate text to specified length with ellipsis
 */
const truncateText = (text: string, maxLength: number): string => {
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength)}...`
}

/**
 * FailedOperationsAlert - Warning card for failed operations
 */
export const FailedOperationsAlert = ({
  operations,
  maxDisplay = 5,
}: FailedOperationsAlertProps) => {
  const navigate = useNavigate()

  // Don't render if no failed operations
  if (operations.length === 0) {
    return null
  }

  const displayOperations = operations.slice(0, maxDisplay)
  const hasMore = operations.length > maxDisplay

  return (
    <Card
      title={
        <Space>
          <WarningOutlined style={{ color: '#ff4d4f' }} />
          <span>Failed Operations</span>
          <Badge count={operations.length} style={{ backgroundColor: '#ff4d4f' }} />
        </Space>
      }
      size="small"
    >
      <Alert
        type="error"
        showIcon
        icon={<ExclamationCircleOutlined />}
        message={`${operations.length} operation(s) require attention`}
        description={
          <>
            <List
              size="small"
              dataSource={displayOperations}
              renderItem={(operation) => {
                const errorTask = operation.tasks.find(t => t.error_message)
                return (
                  <List.Item>
                    <Space direction="vertical" size={0} style={{ width: '100%' }}>
                      <Space>
                        <Text strong>{getOperationTypeLabel(operation.operation_type)}</Text>
                        <Text type="secondary">
                          {dayjs(operation.created_at).fromNow()}
                        </Text>
                      </Space>
                      {errorTask?.error_message && (
                        <Text type="danger" style={{ fontSize: 12 }}>
                          {truncateText(errorTask.error_message, 50)}
                        </Text>
                      )}
                    </Space>
                  </List.Item>
                )
              }}
            />
            {hasMore && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                and {operations.length - maxDisplay} more...
              </Text>
            )}
          </>
        }
        style={{ marginBottom: 0 }}
      />
      <Button
        type="link"
        onClick={() => navigate('/operations?status=failed')}
        style={{ padding: 0, marginTop: 8 }}
      >
        View All Failed
      </Button>
    </Card>
  )
}
