/**
 * ReviewStep - Step 4 of NewOperationWizard
 * Displays summary of operation before execution.
 */

import { useMemo } from 'react'
import { Typography, Card, Space, Tag, Alert, List, Descriptions } from 'antd'
import {
  LockOutlined,
  UnlockOutlined,
  StopOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CodeOutlined,
  SearchOutlined,
  SyncOutlined,
  HeartOutlined,
  RocketOutlined,
  WarningOutlined,
  FileOutlined,
  DatabaseOutlined,
} from '@ant-design/icons'
import type { ReviewStepProps, OperationConfig, OperationType } from './types'
import { OPERATION_TYPES, OPERATION_CATEGORIES } from './types'
import dayjs from 'dayjs'
import { maskArgv, maskArgvTextLines } from '../../../../lib/masking'

const { Title, Text } = Typography

/**
 * Map icon names to actual Ant Design icon components
 */
const iconMap: Record<string, React.ReactNode> = {
  LockOutlined: <LockOutlined />,
  UnlockOutlined: <UnlockOutlined />,
  StopOutlined: <StopOutlined />,
  CheckCircleOutlined: <CheckCircleOutlined />,
  CloseCircleOutlined: <CloseCircleOutlined />,
  CodeOutlined: <CodeOutlined />,
  SearchOutlined: <SearchOutlined />,
  SyncOutlined: <SyncOutlined />,
  HeartOutlined: <HeartOutlined />,
}

/**
 * Category color mapping
 */
const categoryColors: Record<string, string> = {
  ras: 'blue',
  odata: 'green',
  cli: 'purple',
  system: 'orange',
}

const formatDateTime = (value: string) => {
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('DD.MM.YYYY HH:mm') : value
}

/**
 * Format configuration for display based on operation type
 */
const formatConfigForDisplay = (
  operationType: OperationType | null,
  config: OperationConfig
): { label: string; value: string }[] => {
  if (!operationType) return []

  const items: { label: string; value: string }[] = []
  const dc = config.driver_command

  switch (operationType) {
    case 'block_sessions':
      if (config.denied_from) {
        items.push({ label: 'Block Start', value: formatDateTime(config.denied_from) })
      }
      if (config.denied_to) {
        items.push({ label: 'Block End', value: formatDateTime(config.denied_to) })
      }
      if (config.message) {
        items.push({ label: 'Message', value: config.message })
      }
      if (config.permission_code) {
        items.push({ label: 'Permission Code', value: config.permission_code })
      }
      if (config.parameter) {
        items.push({ label: 'Block Parameter', value: config.parameter })
      }
      break

    case 'terminate_sessions':
      if (config.filter_by_app) {
        items.push({ label: 'Filter by App', value: config.filter_by_app })
      }
      items.push({
        label: 'Exclude Admins',
        value: config.exclude_admin ? 'Yes' : 'No',
      })
      break

    case 'designer_cli':
      if (dc && dc.driver === 'cli') {
        if (dc.command_id) {
          items.push({ label: 'Command', value: dc.command_label ? `${dc.command_label} (${dc.command_id})` : dc.command_id })
        }
        items.push({ label: 'Mode', value: dc.mode || 'guided' })

        const commandId = typeof dc.command_id === 'string' ? dc.command_id.trim() : ''
        const args = Array.isArray(dc.resolved_args) && dc.resolved_args.every((item) => typeof item === 'string')
          ? dc.resolved_args
          : typeof dc.args_text === 'string'
            ? dc.args_text
              .split('\n')
              .map((item) => item.trim())
              .filter((item) => item.length > 0)
            : []

        if (commandId) {
          const preview = maskArgv([commandId, ...args]).join('\n')
          if (preview) {
            items.push({ label: 'Preview', value: preview })
          }
        }
        const opt = dc.cli_options ?? {}
        items.push({
          label: 'Disable Messages',
          value: opt.disable_startup_messages === false ? 'No' : 'Yes',
        })
        items.push({
          label: 'Disable Dialogs',
          value: opt.disable_startup_dialogs === false ? 'No' : 'Yes',
        })
        items.push({
          label: 'Capture Log',
          value: opt.log_capture ? 'Yes' : 'No',
        })
        if (opt.log_capture && opt.log_path) {
          items.push({ label: 'Log Path', value: opt.log_path })
        }
        if (opt.log_capture) {
          items.push({
            label: 'Append Log',
            value: opt.log_no_truncate ? 'Yes' : 'No',
          })
        }
        if (dc.command_risk_level === 'dangerous') {
          items.push({
            label: 'Dangerous Confirmed',
            value: dc.confirm_dangerous === true ? 'Yes' : 'No',
          })
        }
        break
      }

      if (config.command) {
        items.push({ label: 'Command', value: config.command })
      }
      break

    case 'query':
      if (config.entity) {
        items.push({ label: 'Entity', value: config.entity })
      }
      if (config.filter) {
        items.push({ label: 'Filter', value: config.filter })
      }
      if (config.select) {
        items.push({ label: 'Select', value: config.select })
      }
      if (config.top) {
        items.push({ label: 'Limit', value: String(config.top) })
      }
      break

    case 'ibcmd_cli': {
      if (dc && dc.driver === 'ibcmd') {
        if (dc.command_id) {
          items.push({ label: 'Command', value: dc.command_label ? `${dc.command_label} (${dc.command_id})` : dc.command_id })
        }
        items.push({ label: 'Mode', value: dc.mode || 'guided' })
        if (dc.command_scope) {
          items.push({ label: 'Scope', value: dc.command_scope })
        }
        if (dc.command_risk_level) {
          items.push({ label: 'Risk', value: dc.command_risk_level })
        }
        if (dc.command_scope === 'global' && dc.auth_database_id) {
          items.push({ label: 'Auth database', value: dc.auth_database_id })
        }
        if (typeof dc.timeout_seconds === 'number') {
          items.push({ label: 'Timeout', value: `${dc.timeout_seconds}s` })
        }
        const connection = dc.connection
        if (connection?.remote) {
          items.push({ label: 'Remote', value: connection.remote })
        }
        if (typeof connection?.pid === 'number') {
          items.push({ label: 'PID', value: String(connection.pid) })
        }
        const offline = connection?.offline
        if (offline && typeof offline === 'object') {
          const offlineParts: string[] = []
          if (offline.config) offlineParts.push(`config=${offline.config}`)
          if (offline.data) offlineParts.push(`data=${offline.data}`)
          if (offline.dbms) offlineParts.push(`dbms=${offline.dbms}`)
          if (offline.db_server) offlineParts.push(`db_server=${offline.db_server}`)
          if (offline.db_name) offlineParts.push(`db_name=${offline.db_name}`)
          if (offline.db_user) offlineParts.push(`db_user=${offline.db_user}`)
        if (offlineParts.length > 0) {
          items.push({ label: 'Offline', value: offlineParts.join('\n') })
        }
      }
        if (dc.args_text) {
          const maskedArgs = maskArgvTextLines(dc.args_text)
          items.push({ label: 'Additional args', value: maskedArgs || '***' })
        }
        if (dc.stdin) {
          items.push({ label: 'Stdin', value: '***' })
        }
        if (dc.command_risk_level === 'dangerous') {
          items.push({
            label: 'Dangerous Confirmed',
            value: dc.confirm_dangerous === true ? 'Yes' : 'No',
          })
        }
      }
      break
    }

    default:
      // No config items for other operation types
      break
  }

  return items
}

/**
 * Get warning message based on operation type and database count
 */
const getWarningMessage = (
  operationType: OperationType | null,
  databaseCount: number
): string | null => {
  if (!operationType || databaseCount === 0) return null

  const dbText = databaseCount === 1 ? '1 database' : `${databaseCount} databases`

  switch (operationType) {
    case 'lock_scheduled_jobs':
      return `This operation will lock scheduled jobs on ${dbText}. Scheduled tasks will not run until unlocked.`
    case 'unlock_scheduled_jobs':
      return `This operation will unlock scheduled jobs on ${dbText}. Make sure maintenance is complete.`
    case 'block_sessions':
      return `This operation will block new user sessions on ${dbText}. Users will not be able to connect.`
    case 'unblock_sessions':
      return `This operation will unblock sessions on ${dbText}. Users will be able to connect again.`
    case 'terminate_sessions':
      return `This operation will terminate active sessions on ${dbText}. Users may lose unsaved work!`
    case 'designer_cli':
      return `This operation will execute DESIGNER CLI on ${dbText}.`
    case 'ibcmd_cli':
      return `This operation will execute IBCMD CLI command. Selected databases: ${dbText}.`
    case 'query':
      return `This operation will execute OData query on ${dbText}.`
    case 'sync_cluster':
      return `This operation will synchronize cluster data for ${dbText}.`
    case 'health_check':
      return `This operation will check connectivity for ${dbText}.`
    default:
      return `This operation will affect ${dbText}. Make sure you have verified the target databases.`
  }
}

/**
 * Get alert type based on operation
 */
const getAlertType = (operationType: OperationType | null): 'warning' | 'info' => {
  const destructiveOperations: OperationType[] = [
    'terminate_sessions',
    'block_sessions',
    'lock_scheduled_jobs',
  ]

  if (operationType && destructiveOperations.includes(operationType)) {
    return 'warning'
  }
  return 'info'
}

/**
 * ReviewStep component
 * Displays full summary of operation before execution
 */
export const ReviewStep = ({
  operationType,
  selectedDatabases,
  config,
  databases,
}: ReviewStepProps) => {
  // Find operation config
  const operationConfig = OPERATION_TYPES.find((op) => op.type === operationType)
  const categoryConfig = operationConfig
    ? OPERATION_CATEGORIES[operationConfig.category]
    : null

  // Format config items for display
  const configItems = useMemo(
    () => formatConfigForDisplay(operationType, config),
    [operationType, config]
  )

  // Warning message
  const warningMessage = getWarningMessage(operationType, selectedDatabases.length)
  const alertType = getAlertType(operationType)

  return (
    <div style={{ padding: '16px 0' }}>
      <Title level={4} style={{ marginBottom: 24 }}>
        <Space>
          <CheckCircleOutlined style={{ color: '#52c41a' }} />
          Review & Execute
        </Space>
      </Title>

      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {/* Operation Type Card */}
        <Card
          size="small"
          title={
            <Space>
              <RocketOutlined />
              Operation Type
            </Space>
          }
        >
          <Space align="start">
            {operationConfig && (
              <div
                style={{
                  fontSize: 32,
                  color: '#1890ff',
                  lineHeight: 1,
                }}
              >
                {iconMap[operationConfig.icon]}
              </div>
            )}
            <div>
              <Space style={{ marginBottom: 4 }}>
                {categoryConfig && (
                  <Tag color={categoryColors[operationConfig?.category || '']}>
                    {categoryConfig.label}
                  </Tag>
                )}
                <Text strong style={{ fontSize: 16 }}>
                  {operationConfig?.label || operationType}
                </Text>
              </Space>
              {operationConfig?.description && (
                <Text type="secondary" style={{ display: 'block' }}>
                  {operationConfig.description}
                </Text>
              )}
            </div>
          </Space>
        </Card>

        {/* Target Databases Card */}
        <Card
          size="small"
          title={
            <Space>
              <DatabaseOutlined />
              Target Databases ({selectedDatabases.length})
            </Space>
          }
        >
          {databases.length > 0 ? (
            <List
              size="small"
              dataSource={databases}
              renderItem={(db) => (
                <List.Item style={{ padding: '8px 0' }}>
                  <Space>
                    <DatabaseOutlined style={{ color: '#1890ff' }} />
                    <Text strong>{db.name}</Text>
                    {db.host && (
                      <Text type="secondary">({db.host})</Text>
                    )}
                  </Space>
                </List.Item>
              )}
              style={{
                maxHeight: 200,
                overflow: 'auto',
              }}
            />
          ) : (
            <Text type="secondary">
              {selectedDatabases.length} database{selectedDatabases.length !== 1 ? 's' : ''} selected
            </Text>
          )}
        </Card>

        {/* Configuration Card */}
        <Card
          size="small"
          title={
            <Space>
              <FileOutlined />
              Configuration
            </Space>
          }
        >
          {configItems.length > 0 ? (
            <Descriptions
              column={1}
              size="small"
              labelStyle={{ fontWeight: 500 }}
            >
              {configItems.map((item, index) => (
                <Descriptions.Item key={index} label={item.label}>
                  {item.value.length > 100 ? (
                    <Text
                      style={{
                        display: 'block',
                        maxHeight: 60,
                        overflow: 'auto',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {item.value}
                    </Text>
                  ) : (
                    item.value
                  )}
                </Descriptions.Item>
              ))}
            </Descriptions>
          ) : (
            <Text type="secondary">No additional configuration required</Text>
          )}
        </Card>

        {/* Warning Alert */}
        {warningMessage && (
          <Alert
            message={
              <Space>
                <WarningOutlined />
                <Text strong>Please Review Before Executing</Text>
              </Space>
            }
            description={warningMessage}
            type={alertType}
            showIcon={false}
          />
        )}
      </Space>
    </div>
  )
}
