import type { ReactNode } from 'react'
import { Space, Tag, Typography } from 'antd'

const { Text } = Typography

type ApiErrorShape = {
  success?: boolean
  error?: {
    code?: string
    message?: string
    details?: {
      missing?: Array<{
        database_id?: string
        database_name?: string
        missing_keys?: string[]
      }>
      missing_total?: number
      omitted?: number
    }
  }
}

type AxiosErrorLike = {
  response?: { data?: unknown }
  message?: string
}

export type IbcmdCliUiError = {
  code: string
  title: string
  content: ReactNode
}

export const parseIbcmdCliUiError = (error: unknown): IbcmdCliUiError | null => {
  const maybe = error as AxiosErrorLike | null
  const data = maybe?.response?.data as ApiErrorShape | undefined
  const apiError = data?.error
  const errorCode = typeof apiError?.code === 'string' ? apiError.code : ''

  if (errorCode === 'IBCMD_CONNECTION_PROFILE_INVALID') {
    const details = apiError?.details
    const missing = Array.isArray(details?.missing) ? details?.missing : []
    const missingTotal = typeof details?.missing_total === 'number' ? details.missing_total : missing.length
    const omitted = typeof details?.omitted === 'number' ? details.omitted : 0

    return {
      code: errorCode,
      title: 'IBCMD connection profile не настроен',
      content: (
        <Space direction="vertical" size="small">
          <Text>
            Для <Text code>scope=per_database</Text> без override требуется непустой профиль подключения для каждой базы.
          </Text>
          <Text type="secondary">
            Настройте IBCMD connection profile на странице <Text code>/databases</Text> или включите per-run override connection.
          </Text>
          {missing.length > 0 && (
            <div>
              {missing.slice(0, 10).map((item) => {
                const label = item.database_name || item.database_id || 'unknown'
                const keys = Array.isArray(item.missing_keys) ? item.missing_keys.join(', ') : ''
                return (
                  <div key={item.database_id || label}>
                    <Tag>{label}</Tag>
                    {keys ? <Text type="secondary">missing: {keys}</Text> : null}
                  </div>
                )
              })}
              {(missingTotal > 10 || omitted > 0) ? (
                <Text type="secondary">... and more (total: {missingTotal})</Text>
              ) : null}
            </div>
          )}
        </Space>
      ),
    }
  }

  if (errorCode === 'MISSING_CONNECTION') {
    return {
      code: errorCode,
      title: 'Не задан connection',
      content: (
        <Space direction="vertical" size="small">
          <Text>
            Вы передали пустой <Text code>connection</Text>. Либо удалите поле connection, чтобы использовать профили баз, либо задайте
            хотя бы один параметр (<Text code>remote</Text>/<Text code>pid</Text>/<Text code>offline.*</Text>).
          </Text>
          <Text type="secondary">
            Задайте параметры в настройках соединения (например в editor `ui.action_catalog`) или в Configure при создании операции.
          </Text>
        </Space>
      ),
    }
  }

  return null
}

export type ModalErrorApiLike = {
  error: (config: { title?: ReactNode; content?: ReactNode }) => void
}

export type MessageApiLike = {
  error: (content: string) => void
}

export const tryShowIbcmdCliUiError = (error: unknown, modal: ModalErrorApiLike, _message: MessageApiLike): boolean => {
  const parsed = parseIbcmdCliUiError(error)
  if (!parsed) return false
  modal.error({ title: parsed.title, content: parsed.content })
  return true
}
