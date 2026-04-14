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
import { useOperationsTranslation } from '../../../../i18n'
import { getOperationTypeDescription, getOperationTypeLabel } from '../../utils'

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
  config: OperationConfig,
  t: ReturnType<typeof useOperationsTranslation>['t'],
): { label: string; value: string }[] => {
  if (!operationType) return []

  const items: { label: string; value: string }[] = []
  const dc = config.driver_command

  switch (operationType) {
    case 'block_sessions':
      if (config.denied_from) {
        items.push({ label: t(($) => $.wizard.reviewFields.blockStart), value: formatDateTime(config.denied_from) })
      }
      if (config.denied_to) {
        items.push({ label: t(($) => $.wizard.reviewFields.blockEnd), value: formatDateTime(config.denied_to) })
      }
      if (config.message) {
        items.push({ label: t(($) => $.wizard.reviewFields.message), value: config.message })
      }
      if (config.permission_code) {
        items.push({ label: t(($) => $.wizard.reviewFields.permissionCode), value: config.permission_code })
      }
      if (config.parameter) {
        items.push({ label: t(($) => $.wizard.reviewFields.blockParameter), value: config.parameter })
      }
      break

    case 'terminate_sessions':
      if (config.filter_by_app) {
        items.push({ label: t(($) => $.wizard.reviewFields.filterByApp), value: config.filter_by_app })
      }
      items.push({
        label: t(($) => $.wizard.reviewFields.excludeAdmins),
        value: config.exclude_admin ? t(($) => $.wizard.reviewFields.yes) : t(($) => $.wizard.reviewFields.no),
      })
      break

    case 'designer_cli':
      if (dc && dc.driver === 'cli') {
        if (dc.command_id) {
          items.push({ label: t(($) => $.wizard.reviewFields.command), value: dc.command_label ? `${dc.command_label} (${dc.command_id})` : dc.command_id })
        }
        items.push({ label: t(($) => $.wizard.reviewFields.mode), value: dc.mode || 'guided' })

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
            items.push({ label: t(($) => $.wizard.reviewFields.preview), value: preview })
          }
        }
        const opt = dc.cli_options ?? {}
        items.push({ label: t(($) => $.wizard.reviewFields.disableStartupMessages), value: opt.disable_startup_messages !== false ? t(($) => $.wizard.reviewFields.yes) : t(($) => $.wizard.reviewFields.no) })
        items.push({ label: t(($) => $.wizard.reviewFields.disableStartupDialogs), value: opt.disable_startup_dialogs !== false ? t(($) => $.wizard.reviewFields.yes) : t(($) => $.wizard.reviewFields.no) })
        items.push({ label: t(($) => $.wizard.reviewFields.captureLog), value: opt.log_capture === true ? t(($) => $.wizard.reviewFields.yes) : t(($) => $.wizard.reviewFields.no) })
        if (opt.log_capture && opt.log_path) {
          items.push({ label: t(($) => $.wizard.reviewFields.logFilePath), value: opt.log_path })
        }
        if (opt.log_capture) {
          items.push({ label: t(($) => $.wizard.reviewFields.appendLog), value: opt.log_no_truncate === true ? t(($) => $.wizard.reviewFields.yes) : t(($) => $.wizard.reviewFields.no) })
        }
        if (dc.command_risk_level) {
          items.push({ label: t(($) => $.wizard.reviewFields.risk), value: dc.command_risk_level })
        }
        if (dc.command_risk_level === 'dangerous') {
          items.push({
            label: t(($) => $.wizard.reviewFields.dangerousConfirmed),
            value: dc.confirm_dangerous === true ? t(($) => $.wizard.reviewFields.yes) : t(($) => $.wizard.reviewFields.no),
          })
        }
        break
      }

      if (config.command) {
        items.push({ label: t(($) => $.wizard.reviewFields.command), value: config.command })
      }
      break

    case 'query':
      if (config.entity) {
        items.push({ label: t(($) => $.wizard.reviewFields.entity), value: config.entity })
      }
      if (config.filter) {
        items.push({ label: t(($) => $.wizard.reviewFields.filter), value: config.filter })
      }
      if (config.select) {
        items.push({ label: t(($) => $.wizard.reviewFields.select), value: config.select })
      }
      if (config.top) {
        items.push({ label: t(($) => $.wizard.reviewFields.limit), value: String(config.top) })
      }
      break

    case 'ibcmd_cli': {
      if (dc && dc.driver === 'ibcmd') {
        if (dc.command_id) {
          items.push({ label: t(($) => $.wizard.reviewFields.command), value: dc.command_label ? `${dc.command_label} (${dc.command_id})` : dc.command_id })
        }
        items.push({ label: t(($) => $.wizard.reviewFields.mode), value: dc.mode || 'guided' })
        if (dc.command_scope) {
          items.push({ label: t(($) => $.wizard.reviewFields.scope), value: dc.command_scope })
        }
        if (dc.command_risk_level) {
          items.push({ label: t(($) => $.wizard.reviewFields.risk), value: dc.command_risk_level })
        }
        if (dc.command_scope === 'global' && dc.auth_database_id) {
          items.push({ label: t(($) => $.wizard.reviewFields.authMappingInfobase), value: dc.auth_database_id })
        }
        if (dc.ib_auth?.strategy) {
          items.push({ label: t(($) => $.wizard.reviewFields.ibAuthStrategy), value: dc.ib_auth.strategy })
        }
        if (typeof dc.timeout_seconds === 'number') {
          items.push({ label: t(($) => $.wizard.reviewFields.timeoutSeconds), value: String(dc.timeout_seconds) })
        }
        const connectionOverride = dc.connection_override === true
        if (dc.command_scope === 'per_database' && !connectionOverride) {
          items.push({ label: t(($) => $.wizard.reviewFields.connection), value: t(($) => $.wizard.reviewFields.connectionDerived) })
        } else {
          const connection = dc.connection
          if (connection?.remote) {
            items.push({ label: t(($) => $.wizard.reviewFields.connectionRemote), value: connection.remote })
          }
          if (typeof connection?.pid === 'number') {
            items.push({ label: t(($) => $.wizard.reviewFields.connectionPid), value: String(connection.pid) })
          }
          const offline = connection?.offline
          if (offline && typeof offline === 'object') {
            const offlineParts = Object.entries(offline)
              .filter(([key, value]) => key !== 'db_pwd' && typeof value === 'string' && value.trim().length > 0)
              .sort((a, b) => a[0].localeCompare(b[0]))
              .map(([key, value]) => `${key}=${value.trim()}`)
            if (offlineParts.length > 0) {
              items.push({ label: t(($) => $.wizard.reviewFields.connectionOffline), value: offlineParts.join('\n') })
            }
          }
        }
        if (dc.args_text) {
          const maskedArgs = maskArgvTextLines(dc.args_text)
          items.push({ label: t(($) => $.wizard.reviewFields.extraArguments), value: maskedArgs || t(($) => $.wizard.reviewFields.masked) })
        }
        if (dc.stdin) {
          items.push({ label: t(($) => $.wizard.reviewFields.stdin), value: t(($) => $.wizard.reviewFields.masked) })
        }
        if (dc.command_risk_level === 'dangerous') {
          items.push({
            label: t(($) => $.wizard.reviewFields.dangerousConfirmed),
            value: dc.confirm_dangerous === true ? t(($) => $.wizard.reviewFields.yes) : t(($) => $.wizard.reviewFields.no),
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
  databaseCount: number,
  t: ReturnType<typeof useOperationsTranslation>['t'],
): string | null => {
  if (!operationType || databaseCount === 0) return null

  const dbText = databaseCount === 1
    ? t(($) => $.wizard.warnings.singleDatabase)
    : t(($) => $.wizard.warnings.multipleDatabases, { count: databaseCount })

  switch (operationType) {
    case 'lock_scheduled_jobs':
      return t(($) => $.wizard.warnings.lockScheduledJobs, { value: dbText })
    case 'unlock_scheduled_jobs':
      return t(($) => $.wizard.warnings.unlockScheduledJobs, { value: dbText })
    case 'block_sessions':
      return t(($) => $.wizard.warnings.blockSessions, { value: dbText })
    case 'unblock_sessions':
      return t(($) => $.wizard.warnings.unblockSessions, { value: dbText })
    case 'terminate_sessions':
      return t(($) => $.wizard.warnings.terminateSessions, { value: dbText })
    case 'designer_cli':
      return t(($) => $.wizard.warnings.designerCli, { value: dbText })
    case 'ibcmd_cli':
      return t(($) => $.wizard.warnings.ibcmdCli, { value: dbText })
    case 'query':
      return t(($) => $.wizard.warnings.query, { value: dbText })
    case 'sync_cluster':
      return t(($) => $.wizard.warnings.syncCluster, { value: dbText })
    case 'health_check':
      return t(($) => $.wizard.warnings.healthCheck, { value: dbText })
    default:
      return t(($) => $.wizard.warnings.default, { value: dbText })
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
  const { t } = useOperationsTranslation()
  // Find operation config
  const operationConfig = OPERATION_TYPES.find((op) => op.type === operationType)
  const categoryConfig = operationConfig
    ? OPERATION_CATEGORIES[operationConfig.category]
    : null

  // Format config items for display
  const configItems = useMemo(
    () => formatConfigForDisplay(operationType, config, t),
    [operationType, config, t]
  )

  // Warning message
  const warningMessage = getWarningMessage(operationType, selectedDatabases.length, t)
  const alertType = getAlertType(operationType)

  return (
    <div style={{ padding: '16px 0' }}>
      <Title level={4} style={{ marginBottom: 24 }}>
        <Space>
          <CheckCircleOutlined style={{ color: '#52c41a' }} />
          {t(($) => $.wizard.review.title)}
        </Space>
      </Title>

      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {/* Operation Type Card */}
        <Card
          size="small"
          title={
            <Space>
              <RocketOutlined />
              {t(($) => $.wizard.review.operationType)}
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
                    {t(($) => $.categories[operationConfig?.category as keyof typeof $.categories])}
                  </Tag>
                )}
                <Text strong style={{ fontSize: 16 }}>
                  {operationType ? getOperationTypeLabel(operationType, t) : operationType}
                </Text>
              </Space>
              {(operationType ? getOperationTypeDescription(operationType, t) : operationConfig?.description) && (
                <Text type="secondary" style={{ display: 'block' }}>
                  {operationType ? getOperationTypeDescription(operationType, t) : operationConfig?.description}
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
              {t(($) => $.wizard.review.targetDatabases, { count: selectedDatabases.length })}
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
              {t(($) => $.wizard.review.selectedDatabasesFallback, { count: selectedDatabases.length })}
            </Text>
          )}
        </Card>

        {/* Configuration Card */}
        <Card
          size="small"
          title={
            <Space>
              <FileOutlined />
              {t(($) => $.wizard.review.configuration)}
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
            <Text type="secondary">{t(($) => $.wizard.review.noAdditionalConfig)}</Text>
          )}
        </Card>

        {/* Warning Alert */}
        {warningMessage && (
          <Alert
            message={
              <Space>
                <WarningOutlined />
                <Text strong>{t(($) => $.wizard.review.reviewBeforeExecuting)}</Text>
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
