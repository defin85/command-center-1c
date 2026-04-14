import { useCallback, useMemo, useState } from 'react'
import { Alert, App, Button, Input, Space, Spin, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ReloadOutlined, RetweetOutlined, RightCircleOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'

import type { DLQMessage } from '../../api/generated/model/dLQMessage'
import { useDlqMessage, useDlqMessages, useRetryDlqMessage } from '../../api/queries/dlq'
import { useAuthz } from '../../authz/useAuthz'
import { DrawerSurfaceShell, PageHeader, RouteButton, WorkspacePage } from '../../components/platform'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { useAdminSupportTranslation, useCommonTranslation, useLocaleFormatters } from '../../i18n'
import { confirmWithTracking } from '../../observability/confirmWithTracking'
import { trackUiAction } from '../../observability/uiActionJournal'

const { Text } = Typography

export function DLQPage() {
  const { message, modal } = App.useApp()
  const { isStaff } = useAuthz()
  const { t } = useAdminSupportTranslation()
  const { t: tCommon } = useCommonTranslation()
  const formatters = useLocaleFormatters()
  const [searchParams, setSearchParams] = useSearchParams()

  const [retryReason, setRetryReason] = useState<string>('')
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const fallbackColumnConfigs = useMemo(() => [
    {
      key: 'failed_at',
      label: t(($) => $.dlq.table.failedAt),
      sortable: true,
      groupKey: 'core',
      groupLabel: t(($) => $.dlq.table.operation),
    },
    {
      key: 'operation_id',
      label: t(($) => $.dlq.table.operation),
      sortable: true,
      groupKey: 'core',
      groupLabel: t(($) => $.dlq.table.operation),
    },
    {
      key: 'error_code',
      label: t(($) => $.dlq.table.error),
      sortable: true,
      groupKey: 'details',
      groupLabel: t(($) => $.dlq.table.message),
    },
    {
      key: 'error_message',
      label: t(($) => $.dlq.table.message),
      groupKey: 'details',
      groupLabel: t(($) => $.dlq.table.message),
    },
    {
      key: 'worker_id',
      label: t(($) => $.dlq.table.worker),
      sortable: true,
      groupKey: 'details',
      groupLabel: t(($) => $.dlq.table.message),
    },
    {
      key: 'actions',
      label: t(($) => $.dlq.table.actions),
      groupKey: 'actions',
      groupLabel: t(($) => $.dlq.table.actions),
    },
  ], [t])
  const retryMutation = useRetryDlqMessage()
  const unavailableShort = tCommon(($) => $.values.unavailableShort)

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(updates).forEach(([key, value]) => {
        if (!value) {
          next.delete(key)
        } else {
          next.set(key, value)
        }
      })
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )

  const retryEntry = useCallback(async (entry: DLQMessage): Promise<{ ok: boolean; id: string }> => {
    const operationId = (entry.operation_id || '').trim()
    const originalMessageId = (entry.original_message_id || '').trim()
    const id = operationId || originalMessageId

    if (!operationId && !originalMessageId) {
      return { ok: false, id: entry.dlq_message_id }
    }

    try {
      await retryMutation.mutateAsync({
        operation_id: operationId || undefined,
        original_message_id: operationId ? undefined : originalMessageId || undefined,
        reason: retryReason.trim() || undefined,
      })
      return { ok: true, id }
    } catch (_err) {
      return { ok: false, id }
    }
  }, [retryMutation, retryReason])

  const onRetry = useCallback(async (entry: DLQMessage) => {
    const result = await trackUiAction({
      actionKind: 'operator.action',
      actionName: 'Retry DLQ message',
      context: {
        dlq_message_id: entry.dlq_message_id,
        operation_id: entry.operation_id || undefined,
        original_message_id: entry.original_message_id || undefined,
        manual_operation: 'dlq.retry_single',
      },
    }, () => retryEntry(entry))
    if (!result) {
      message.error(t(($) => $.dlq.messages.retryFailed, { id: entry.dlq_message_id }))
      return
    }
    if (result.ok) {
      message.success(t(($) => $.dlq.messages.retrySuccess, { id: result.id }))
    } else {
      message.error(t(($) => $.dlq.messages.retryFailed, { id: result.id }))
    }
  }, [message, retryEntry, t])

  const onBulkRetry = () => {
    const entries = (dlqQuery.data?.messages ?? []).filter((m) => selectedRowKeys.includes(m.dlq_message_id))
    if (entries.length === 0) return

    confirmWithTracking(modal, {
      title: t(($) => $.dlq.confirm.retrySelectedTitle),
      content: t(($) => $.dlq.confirm.retrySelectedContent, { count: entries.length }),
      okText: t(($) => $.dlq.confirm.retry),
      cancelText: t(($) => $.dlq.confirm.cancel),
      onOk: async () => {
        const key = 'bulk-dlq-retry'
        let success = 0
        let failed = 0

        message.loading({ content: t(($) => $.dlq.messages.bulkLoading, { count: entries.length }), key })
        for (let i = 0; i < entries.length; i++) {
          const result = await retryEntry(entries[i])
          if (result.ok) {
            success++
          } else {
            failed++
          }
          message.loading({
            content: t(($) => $.dlq.messages.bulkProgress, {
              current: String(i + 1),
              total: String(entries.length),
            }),
            key,
          })
        }

        setSelectedRowKeys([])

        if (failed === 0) {
          message.success({
            content: t(($) => $.dlq.messages.bulkSuccess, {
              success: String(success),
              total: String(entries.length),
            }),
            key,
          })
        } else {
          message.warning({
            content: t(($) => $.dlq.messages.bulkPartial, {
              success: String(success),
              failed: String(failed),
            }),
            key,
          })
        }
      },
    })
  }

  const columns: ColumnsType<DLQMessage> = useMemo(() => ([
    {
      title: t(($) => $.dlq.table.failedAt),
      dataIndex: 'failed_at',
      key: 'failed_at',
      width: 190,
      render: (value: string) => formatters.dateTime(value, { fallback: unavailableShort }),
    },
    {
      title: t(($) => $.dlq.table.operation),
      dataIndex: 'operation_id',
      key: 'operation_id',
      width: 320,
      render: (_value: unknown, record) => {
        const operationId = (record.operation_id || '').trim()
        const originalId = (record.original_message_id || '').trim()
        return (
          <div>
            <Space size={6}>
              <Button
                type="link"
                style={{ padding: 0 }}
                onClick={() => updateSearchParams({ message: record.dlq_message_id })}
              >
                {operationId || '-'}
              </Button>
              {operationId && (
                <RouteButton
                  size="small"
                  icon={<RightCircleOutlined />}
                  to={`/operations?tab=monitor&operation=${encodeURIComponent(operationId)}`}
                  title={t(($) => $.dlq.table.openInOperations)}
                  aria-label={t(($) => $.dlq.table.openInOperations)}
                />
              )}
            </Space>
            <div style={{ marginTop: 4 }}>
              <Text type="secondary">dlq: {record.dlq_message_id}</Text>
            </div>
            {originalId && (
              <div>
                <Text type="secondary">orig: {originalId}</Text>
              </div>
            )}
          </div>
        )
      },
    },
    {
      title: t(($) => $.dlq.table.error),
      dataIndex: 'error_code',
      key: 'error_code',
      width: 180,
      render: (_value: unknown, record) => {
        const code = (record.error_code || '').trim()
        return code ? <Tag color="red">{code}</Tag> : ''
      },
    },
    {
      title: t(($) => $.dlq.table.message),
      dataIndex: 'error_message',
      key: 'error_message',
      render: (v: string) => (
        <Text ellipsis={{ tooltip: v }} style={{ maxWidth: 520, display: 'inline-block' }}>
          {v || ''}
        </Text>
      ),
    },
    {
      title: t(($) => $.dlq.table.worker),
      dataIndex: 'worker_id',
      key: 'worker_id',
      width: 160,
      render: (v: string) => v || '',
    },
    {
      title: t(($) => $.dlq.table.actions),
      key: 'actions',
      width: 140,
      render: (_value: unknown, record) => (
        <Button
          size="small"
          icon={<RetweetOutlined />}
          loading={retryMutation.isPending}
          onClick={() => void onRetry(record)}
        >
          {t(($) => $.dlq.detail.retry)}
        </Button>
      ),
    },
  ]), [formatters, onRetry, retryMutation.isPending, t, unavailableShort, updateSearchParams])

  const table = useTableToolkit({
    tableId: 'dlq',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const dlqQuery = useDlqMessages({
    search: table.search,
    filters: table.filtersPayload,
    sort: table.sortPayload,
    limit: table.pagination.pageSize,
    offset: pageStart,
  }, { enabled: isStaff })
  type AxiosErrorLike = { response?: { status?: number } }
  const status = (dlqQuery.error as AxiosErrorLike | null)?.response?.status
  const showStaffWarning = status === 403

  const messages = dlqQuery.data?.messages ?? []
  const totalMessages = typeof dlqQuery.data?.total === 'number'
    ? dlqQuery.data.total
    : messages.length
  const selectedMessageId = (searchParams.get('message') || '').trim() || null
  const selectedMessageFromCatalog = selectedMessageId
    ? messages.find((entry) => entry.dlq_message_id === selectedMessageId) ?? null
    : null
  const selectedMessageQuery = useDlqMessage(selectedMessageId, {
    enabled: isStaff && Boolean(selectedMessageId) && selectedMessageFromCatalog === null,
  })
  const selectedMessage = selectedMessageFromCatalog ?? selectedMessageQuery.data ?? null
  const selectedMessageLoading = Boolean(selectedMessageId)
    && selectedMessage === null
    && selectedMessageQuery.isLoading
  const selectedMessageError = Boolean(selectedMessageId)
    && selectedMessage === null
    && !selectedMessageLoading
    ? t(($) => $.dlq.detail.missing)
    : null

  if (!isStaff) {
    return (
      <WorkspacePage
        header={(
          <PageHeader
            title={t(($) => $.dlq.page.title)}
            subtitle={t(($) => $.dlq.page.staffOnlySubtitle)}
          />
        )}
      >
        <Alert
          type="warning"
          message={t(($) => $.dlq.page.staffOnlyMessage)}
        />
      </WorkspacePage>
    )
  }

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t(($) => $.dlq.page.title)}
          subtitle={t(($) => $.dlq.page.subtitle)}
          actions={(
            <Space wrap>
              <Button icon={<ReloadOutlined />} onClick={() => dlqQuery.refetch()} loading={dlqQuery.isFetching}>
                {t(($) => $.dlq.page.refresh)}
              </Button>
              <Button
                type="primary"
                icon={<RetweetOutlined />}
                onClick={onBulkRetry}
                disabled={selectedRowKeys.length === 0 || retryMutation.isPending}
              >
                {t(($) => $.dlq.page.retrySelected, { count: selectedRowKeys.length })}
              </Button>
            </Space>
          )}
        />
      )}
    >
      {showStaffWarning && (
        <Alert
          type="warning"
          message={t(($) => $.dlq.page.accessDeniedTitle)}
          description={t(($) => $.dlq.page.accessDeniedDescription)}
          showIcon
        />
      )}

      <TableToolkit
        table={table}
        data={messages}
        total={totalMessages}
        loading={dlqQuery.isLoading}
        rowKey="dlq_message_id"
        columns={columns}
        rowSelection={{
          selectedRowKeys,
          onChange: setSelectedRowKeys,
        }}
        searchPlaceholder={t(($) => $.dlq.page.searchPlaceholder)}
        toolbarActions={(
          <Input
            placeholder={t(($) => $.dlq.page.retryReasonPlaceholder)}
            value={retryReason}
            onChange={(event) => setRetryReason(event.target.value)}
            style={{ width: 260 }}
          />
        )}
        onRow={(record) => ({
          onClick: () => updateSearchParams({ message: record.dlq_message_id }),
          style: { cursor: 'pointer' },
        })}
      />

      <DrawerSurfaceShell
        open={Boolean(selectedMessageId)}
        onClose={() => updateSearchParams({ message: null })}
        title={selectedMessage
          ? t(($) => $.dlq.detail.title, { id: selectedMessage.dlq_message_id })
          : t(($) => $.dlq.detail.titleFallback)}
        subtitle={selectedMessage?.operation_id
          ? t(($) => $.dlq.detail.subtitle, { operationId: selectedMessage.operation_id })
          : undefined}
        drawerTestId="dlq-message-detail-drawer"
        extra={selectedMessage ? (
          <Space wrap>
            {selectedMessage.operation_id ? (
              <RouteButton
                to={`/operations?tab=monitor&operation=${encodeURIComponent(selectedMessage.operation_id)}`}
                icon={<RightCircleOutlined />}
              >
                {t(($) => $.dlq.detail.openInOperations)}
              </RouteButton>
            ) : null}
            <Button
              type="primary"
              icon={<RetweetOutlined />}
              loading={retryMutation.isPending}
              onClick={() => { void onRetry(selectedMessage) }}
            >
              {t(($) => $.dlq.detail.retry)}
            </Button>
          </Space>
        ) : null}
      >
        {selectedMessageLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
            <Spin />
          </div>
        ) : selectedMessageError ? (
          <Alert
            type="error"
            message={t(($) => $.dlq.detail.failedRestoreTitle)}
            description={selectedMessageError}
            showIcon
          />
        ) : selectedMessage ? (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Text><strong>{t(($) => $.dlq.detail.fields.dlqId)}:</strong> {selectedMessage.dlq_message_id}</Text>
            <Text><strong>{t(($) => $.dlq.detail.fields.operation)}:</strong> {selectedMessage.operation_id || unavailableShort}</Text>
            <Text><strong>{t(($) => $.dlq.detail.fields.originalMessage)}:</strong> {selectedMessage.original_message_id || unavailableShort}</Text>
            <Text><strong>{t(($) => $.dlq.detail.fields.worker)}:</strong> {selectedMessage.worker_id || unavailableShort}</Text>
            <Text><strong>{t(($) => $.dlq.detail.fields.failedAt)}:</strong> {formatters.dateTime(selectedMessage.failed_at, { fallback: unavailableShort })}</Text>
            <Text><strong>{t(($) => $.dlq.detail.fields.errorCode)}:</strong> {selectedMessage.error_code || unavailableShort}</Text>
            <Text><strong>{t(($) => $.dlq.detail.fields.errorMessage)}:</strong> {selectedMessage.error_message || unavailableShort}</Text>
            <Text><strong>{t(($) => $.dlq.detail.fields.retryReason)}:</strong> {retryReason || unavailableShort}</Text>
          </Space>
        ) : (
          <Text type="secondary">{t(($) => $.dlq.detail.empty)}</Text>
        )}
      </DrawerSurfaceShell>
    </WorkspacePage>
  )
}
