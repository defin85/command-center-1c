/**
 * Failed operations alert component for Dashboard.
 *
 * Displays a warning card with list of recent failed operations.
 */

import { Card, Alert, List, Button, Badge, Typography, Space } from 'antd'
import { WarningOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { DashboardOperation } from '../types'
import { getOperationTypeLabel } from '../../Operations/utils'
import { useDashboardTranslation, useLocaleFormatters } from '../../../i18n'

const { Text } = Typography

export interface FailedOperationsAlertProps {
  /** Failed operations to display */
  operations: DashboardOperation[]
  /** Maximum number of operations to display (default: 5) */
  maxDisplay?: number
}

/**
 * Truncate text to specified length with ellipsis
 */
const truncateText = (text: string, maxLength: number): string => {
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength)}\u2026`
}

const getRelativeCreatedAtLabel = (
  value: string,
  formatters: ReturnType<typeof useLocaleFormatters>,
) => {
  const timestamp = Date.parse(value)
  if (Number.isNaN(timestamp)) {
    return formatters.dateTime(value)
  }

  const seconds = Math.round((timestamp - Date.now()) / 1000)
  const absoluteSeconds = Math.abs(seconds)

  if (absoluteSeconds < 60) {
    return formatters.relativeTime(seconds, 'second')
  }

  if (absoluteSeconds < 3600) {
    return formatters.relativeTime(Math.round(seconds / 60), 'minute')
  }

  if (absoluteSeconds < 86400) {
    return formatters.relativeTime(Math.round(seconds / 3600), 'hour')
  }

  return formatters.relativeTime(Math.round(seconds / 86400), 'day')
}

/**
 * FailedOperationsAlert - Warning card for failed operations
 */
export const FailedOperationsAlert = ({
  operations,
  maxDisplay = 5,
}: FailedOperationsAlertProps) => {
  const navigate = useNavigate()
  const { t } = useDashboardTranslation()
  const formatters = useLocaleFormatters()

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
          <span>{t(($) => $.failedOperations.title)}</span>
          <Badge count={operations.length} style={{ backgroundColor: '#ff4d4f' }} />
        </Space>
      }
      size="small"
    >
      <Alert
        type="error"
        showIcon
        icon={<ExclamationCircleOutlined />}
        message={t(($) => $.failedOperations.requiresAttention, {
          count: operations.length,
        })}
        description={
          <>
            <List
              size="small"
              dataSource={displayOperations}
              renderItem={(operation) => (
                <List.Item>
                  <Space direction="vertical" size={0} style={{ width: '100%' }}>
                    <Space>
                      <Text strong>{getOperationTypeLabel(operation.operation_type)}</Text>
                      <Text type="secondary">
                        {getRelativeCreatedAtLabel(operation.created_at, formatters)}
                      </Text>
                    </Space>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {truncateText(operation.name, 50)}
                    </Text>
                  </Space>
                </List.Item>
              )}
            />
            {hasMore && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t(($) => $.failedOperations.andMore, {
                  count: operations.length - maxDisplay,
                })}
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
        {t(($) => $.failedOperations.viewAllFailed)}
      </Button>
    </Card>
  )
}
