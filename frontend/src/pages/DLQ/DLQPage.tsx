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
import { confirmWithTracking } from '../../observability/confirmWithTracking'
import { trackUiAction } from '../../observability/uiActionJournal'

const { Text } = Typography

export function DLQPage() {
  const { message, modal } = App.useApp()
  const { isStaff } = useAuthz()
  const [searchParams, setSearchParams] = useSearchParams()

  const [retryReason, setRetryReason] = useState<string>('')
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const fallbackColumnConfigs = useMemo(() => [
    { key: 'failed_at', label: 'Failed at', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'operation_id', label: 'Operation', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'error_code', label: 'Error', sortable: true, groupKey: 'details', groupLabel: 'Details' },
    { key: 'error_message', label: 'Message', groupKey: 'details', groupLabel: 'Details' },
    { key: 'worker_id', label: 'Worker', sortable: true, groupKey: 'details', groupLabel: 'Details' },
    { key: 'actions', label: 'Actions', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])
  const retryMutation = useRetryDlqMessage()

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
      message.error(`Retry failed: ${entry.dlq_message_id}`)
      return
    }
    if (result.ok) {
      message.success(`Re-enqueued ${result.id}`)
    } else {
      message.error(`Retry failed: ${result.id}`)
    }
  }, [message, retryEntry])

  const onBulkRetry = () => {
    const entries = (dlqQuery.data?.messages ?? []).filter((m) => selectedRowKeys.includes(m.dlq_message_id))
    if (entries.length === 0) return

    confirmWithTracking(modal, {
      title: 'Retry selected DLQ messages?',
      content: `Re-enqueue ${entries.length} message(s) sequentially.`,
      okText: 'Retry',
      cancelText: 'Cancel',
      onOk: async () => {
        const key = 'bulk-dlq-retry'
        let success = 0
        let failed = 0

        message.loading({ content: `Retrying ${entries.length}\u2026`, key })
        for (let i = 0; i < entries.length; i++) {
          const result = await retryEntry(entries[i])
          if (result.ok) {
            success++
          } else {
            failed++
          }
          message.loading({ content: `Retrying\u2026 (${i + 1}/${entries.length})`, key })
        }

        setSelectedRowKeys([])

        if (failed === 0) {
          message.success({ content: `Retry: ${success}/${entries.length} succeeded`, key })
        } else {
          message.warning({ content: `Retry: ${success} ok, ${failed} failed`, key })
        }
      },
    })
  }

  const columns: ColumnsType<DLQMessage> = useMemo(() => ([
    {
      title: 'Failed at',
      dataIndex: 'failed_at',
      key: 'failed_at',
      width: 190,
      render: (v: string) => (v ? new Date(v).toLocaleString() : ''),
    },
    {
      title: 'Operation',
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
                  title="Open in Operations Monitor"
                  aria-label="Open in Operations Monitor"
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
      title: 'Error',
      dataIndex: 'error_code',
      key: 'error_code',
      width: 180,
      render: (_value: unknown, record) => {
        const code = (record.error_code || '').trim()
        return code ? <Tag color="red">{code}</Tag> : ''
      },
    },
    {
      title: 'Message',
      dataIndex: 'error_message',
      key: 'error_message',
      render: (v: string) => (
        <Text ellipsis={{ tooltip: v }} style={{ maxWidth: 520, display: 'inline-block' }}>
          {v || ''}
        </Text>
      ),
    },
    {
      title: 'Worker',
      dataIndex: 'worker_id',
      key: 'worker_id',
      width: 160,
      render: (v: string) => v || '',
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 140,
      render: (_value: unknown, record) => (
        <Button
          size="small"
          icon={<RetweetOutlined />}
          loading={retryMutation.isPending}
          onClick={() => void onRetry(record)}
        >
          Retry
        </Button>
      ),
    },
  ]), [onRetry, retryMutation.isPending, updateSearchParams])

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
    ? 'Selected DLQ message could not be restored. Reload the workspace or choose another message from the catalog.'
    : null

  if (!isStaff) {
    return (
      <WorkspacePage
        header={<PageHeader title="DLQ" subtitle="Dead-letter queue remediation workspace для staff пользователей." />}
      >
        <Alert
          type="warning"
          message="DLQ доступен только для staff пользователей"
        />
      </WorkspacePage>
    )
  }

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="DLQ"
          subtitle="Remediation workspace с shell-safe handoff в Operations и URL-backed selected message context."
          actions={(
            <Space wrap>
              <Button icon={<ReloadOutlined />} onClick={() => dlqQuery.refetch()} loading={dlqQuery.isFetching}>
                Refresh
              </Button>
              <Button
                type="primary"
                icon={<RetweetOutlined />}
                onClick={onBulkRetry}
                disabled={selectedRowKeys.length === 0 || retryMutation.isPending}
              >
                Retry selected ({selectedRowKeys.length})
              </Button>
            </Space>
          )}
        />
      )}
    >
      {showStaffWarning && (
        <Alert
          type="warning"
          message="Access denied"
          description="DLQ endpoints require staff access."
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
        searchPlaceholder="Search DLQ"
        toolbarActions={(
          <Input
            placeholder="Retry reason (optional)"
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
        title={selectedMessage ? `DLQ message ${selectedMessage.dlq_message_id}` : 'DLQ message'}
        subtitle={selectedMessage?.operation_id ? `operation=${selectedMessage.operation_id}` : undefined}
        drawerTestId="dlq-message-detail-drawer"
        extra={selectedMessage ? (
          <Space wrap>
            {selectedMessage.operation_id ? (
              <RouteButton
                to={`/operations?tab=monitor&operation=${encodeURIComponent(selectedMessage.operation_id)}`}
                icon={<RightCircleOutlined />}
              >
                Open in Operations
              </RouteButton>
            ) : null}
            <Button
              type="primary"
              icon={<RetweetOutlined />}
              loading={retryMutation.isPending}
              onClick={() => { void onRetry(selectedMessage) }}
            >
              Retry
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
            message="Failed to restore selected message"
            description={selectedMessageError}
            showIcon
          />
        ) : selectedMessage ? (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Text><strong>DLQ ID:</strong> {selectedMessage.dlq_message_id}</Text>
            <Text><strong>Operation:</strong> {selectedMessage.operation_id || '—'}</Text>
            <Text><strong>Original message:</strong> {selectedMessage.original_message_id || '—'}</Text>
            <Text><strong>Worker:</strong> {selectedMessage.worker_id || '—'}</Text>
            <Text><strong>Failed at:</strong> {selectedMessage.failed_at ? new Date(selectedMessage.failed_at).toLocaleString() : '—'}</Text>
            <Text><strong>Error code:</strong> {selectedMessage.error_code || '—'}</Text>
            <Text><strong>Error message:</strong> {selectedMessage.error_message || '—'}</Text>
            <Text><strong>Retry reason:</strong> {retryReason || '—'}</Text>
          </Space>
        ) : (
          <Text type="secondary">Select a DLQ message to view details.</Text>
        )}
      </DrawerSurfaceShell>
    </WorkspacePage>
  )
}
