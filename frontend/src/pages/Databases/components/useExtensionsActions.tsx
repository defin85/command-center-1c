import { useCallback, useState } from 'react'
import { Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { ActionCatalogAction } from '../../../api/types/actionCatalog'
import type { ExecuteIbcmdCliOperationRequest } from '../../../api/generated/model/executeIbcmdCliOperationRequest'
import { getV2 } from '../../../api/generated'
import { apiClient } from '../../../api/client'
import { tryShowIbcmdCliUiError } from '../../../components/ibcmd/ibcmdCliUiErrors'

const api = getV2()

const isRecord = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const ensureIbcmdConnection = (raw: unknown): Record<string, unknown> => {
  const conn = isRecord(raw) ? raw : null
  const hasRemote = typeof conn?.remote === 'string' && conn.remote.trim().length > 0
  const hasPid = typeof conn?.pid === 'number'
  const hasOffline = isRecord(conn?.offline)
  if (conn && (hasRemote || hasPid || hasOffline)) return conn
  return { offline: {} }
}

type MessageApi = {
  success: (content: string) => void
  error: (content: string) => void
  info: (content: string) => void
}

type ModalApi = {
  confirm: (config: Record<string, unknown>) => void
  error: (config: Record<string, unknown>) => void
}

export type UseExtensionsActionsParams = {
  isStaff: boolean
  message: MessageApi
  modal: ModalApi
  navigate: (to: string) => void
}

export const useExtensionsActions = ({ isStaff, message, modal, navigate }: UseExtensionsActionsParams) => {
  const [extensionsActionPendingId, setExtensionsActionPendingId] = useState<string | null>(null)

  const resetExtensionsActionPendingId = useCallback(() => {
    setExtensionsActionPendingId(null)
  }, [])

  const executeExtensionsAction = useCallback(async (action: ActionCatalogAction, databaseIds: string[]) => {
    const executor = action.executor
    const kind = executor.kind

    if (kind === 'ibcmd_cli') {
      const commandId = (executor.command_id ?? '').trim()
      if (!commandId) {
        throw new Error('Action executor missing command_id')
      }

      const timeoutSeconds = executor.fixed?.timeout_seconds
      const connectionOverride = ensureIbcmdConnection(executor.connection)
      const payload: ExecuteIbcmdCliOperationRequest = {
        command_id: commandId,
        mode: executor.mode === 'manual' ? 'manual' : 'guided',
        database_ids: databaseIds,
        connection: connectionOverride as unknown as ExecuteIbcmdCliOperationRequest['connection'],
        params: executor.params ?? {},
        additional_args: executor.additional_args ?? [],
        stdin: executor.stdin ?? '',
        confirm_dangerous: executor.fixed?.confirm_dangerous === true,
        timeout_seconds: typeof timeoutSeconds === 'number' ? timeoutSeconds : undefined,
      }

      const res = await api.postOperationsExecuteIbcmdCli(payload)
      message.success(`Операция поставлена в очередь: ${action.label}`)
      if (res.operation_id) {
        navigate(`/operations?operation=${res.operation_id}`)
      }
      return
    }

    if (kind === 'designer_cli') {
      const command = (executor.command_id ?? '').trim()
      if (!command) {
        throw new Error('Action executor missing command_id')
      }
      const res = await api.postOperationsExecute({
        operation_type: 'designer_cli',
        database_ids: databaseIds,
        config: {
          command,
          args: executor.additional_args ?? [],
        },
      })
      message.success(`Операция поставлена в очередь: ${action.label}`)
      if (res.operation_id) {
        navigate(`/operations?operation=${res.operation_id}`)
      }
      return
    }

    if (kind === 'workflow') {
      const workflowId = (executor.workflow_id ?? '').trim()
      if (!workflowId) {
        throw new Error('Action executor missing workflow_id')
      }
      const baseContext = executor.params && typeof executor.params === 'object' ? executor.params : {}
      const res = await api.postWorkflowsExecuteWorkflow({
        workflow_id: workflowId,
        mode: 'async',
        input_context: {
          ...baseContext,
          database_ids: databaseIds,
        },
      })
      message.success(`Workflow запущен: ${action.label}`)
      if (res.execution_id) {
        navigate(`/workflows/executions/${res.execution_id}`)
      }
      return
    }

    throw new Error(`Unsupported action executor kind: ${kind}`)
  }, [message, navigate])

  const runExtensionsAction = useCallback(async (action: ActionCatalogAction, databaseIds: string[]) => {
    if (extensionsActionPendingId) return

    const loadPreview = async () => {
      const previewExecutor: ActionCatalogAction['executor'] = action.executor.kind === 'ibcmd_cli'
        ? { ...action.executor, connection: ensureIbcmdConnection(action.executor.connection) }
        : action.executor
      const response = await apiClient.post('/api/v2/ui/execution-plan/preview/', {
        executor: previewExecutor,
        database_ids: databaseIds,
      })
      return response.data as unknown
    }

    type UIBinding = {
      target_ref?: string
      source_ref?: string
      resolve_at?: string
      sensitive?: boolean
      status?: string
      reason?: string | null
    }

    const extractBindings = (preview: unknown): UIBinding[] => {
      if (!preview || typeof preview !== 'object') return []
      const p = preview as Record<string, unknown>
      const raw = p.bindings
      if (!Array.isArray(raw)) return []
      return raw.filter((item) => item && typeof item === 'object') as UIBinding[]
    }

    const formatPreview = (preview: unknown): string => {
      if (!preview || typeof preview !== 'object') return ''
      const p = preview as Record<string, unknown>
      const plan = p.execution_plan as Record<string, unknown> | undefined
      if (!plan || typeof plan !== 'object') return ''
      const kind = String(plan.kind ?? '')
      const argv = Array.isArray(plan.argv_masked) ? plan.argv_masked.filter((x) => typeof x === 'string') : []
      const workflowId = typeof plan.workflow_id === 'string' ? plan.workflow_id : null
      const lines: string[] = []
      if (kind) lines.push(`kind: ${kind}`)
      if (workflowId) lines.push(`workflow_id: ${workflowId}`)
      if (argv.length > 0) {
        lines.push('argv_masked:')
        lines.push(...argv.map((x) => `  ${x}`))
      }
      return lines.join('\n')
    }

    const bindingColumns: ColumnsType<UIBinding> = [
      { title: 'Target', dataIndex: 'target_ref', key: 'target_ref' },
      { title: 'Source', dataIndex: 'source_ref', key: 'source_ref' },
      { title: 'Resolve', dataIndex: 'resolve_at', key: 'resolve_at', width: 90 },
      {
        title: 'Sensitive',
        dataIndex: 'sensitive',
        key: 'sensitive',
        width: 90,
        render: (value: boolean | undefined) => (value ? <Tag color="red">yes</Tag> : <Tag>no</Tag>),
      },
      { title: 'Status', dataIndex: 'status', key: 'status', width: 110 },
      { title: 'Reason', dataIndex: 'reason', key: 'reason' },
    ]

    const doRun = async () => {
      setExtensionsActionPendingId(action.id)
      try {
        await executeExtensionsAction(action, databaseIds)
      } catch (e: unknown) {
        if (!tryShowIbcmdCliUiError(e, modal, message)) {
          const errorMessage = e instanceof Error ? e.message : 'unknown error'
          message.error(`Не удалось выполнить действие: ${errorMessage}`)
        }
      } finally {
        setExtensionsActionPendingId(null)
      }
    }

    if (isStaff) {
      const count = databaseIds.length
      let previewText = ''
      let previewError = ''
      let previewBindings: UIBinding[] = []
      try {
        const preview = await loadPreview()
        previewText = formatPreview(preview)
        previewBindings = extractBindings(preview)
      } catch (e: unknown) {
        previewError = e instanceof Error ? e.message : 'preview failed'
      }

      modal.confirm({
        title: action.executor.fixed?.confirm_dangerous === true ? 'Подтвердить опасное действие?' : 'Подтвердить действие?',
        content: (
          <div>
            <div style={{ marginBottom: 8 }}>
              Действие &quot;{action.label}&quot; будет выполнено для {count} баз(ы).
            </div>
            {previewError ? (
              <div style={{ marginBottom: 8, color: '#cf1322' }}>Preview error: {previewError}</div>
            ) : null}
            {previewText ? (
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{previewText}</pre>
            ) : (
              <div style={{ opacity: 0.7 }}>Preview not available</div>
            )}
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Binding Provenance:</div>
              {previewBindings.length > 0 ? (
                <Table
                  size="small"
                  rowKey={(_row, idx) => String(idx)}
                  pagination={false}
                  dataSource={previewBindings}
                  columns={bindingColumns}
                  scroll={{ x: 900 }}
                />
              ) : (
                <div style={{ opacity: 0.7 }}>No bindings</div>
              )}
            </div>
          </div>
        ),
        okText: 'Выполнить',
        cancelText: 'Отмена',
        okButtonProps: { danger: action.executor.fixed?.confirm_dangerous === true },
        onOk: doRun,
      })
      return
    }

    if (action.executor.fixed?.confirm_dangerous === true) {
      const count = databaseIds.length
      modal.confirm({
        title: 'Подтвердить опасное действие?',
        content: `Действие "${action.label}" будет выполнено для ${count} баз(ы).`,
        okText: 'Выполнить',
        cancelText: 'Отмена',
        okButtonProps: { danger: true },
        onOk: doRun,
      })
      return
    }

    await doRun()
  }, [executeExtensionsAction, extensionsActionPendingId, isStaff, message, modal])

  return { runExtensionsAction, extensionsActionPendingId, resetExtensionsActionPendingId }
}
