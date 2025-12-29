import { useCallback, useMemo, useState } from 'react'
import { Alert, App, Button, Input, Space, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ReloadOutlined, RetweetOutlined, RightCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

import type { DLQMessage } from '../../api/generated/model/dLQMessage'
import { useDlqMessages, useRetryDlqMessage } from '../../api/queries/dlq'
import { useMe } from '../../api/queries/me'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'

const { Title, Text } = Typography

export function DLQPage() {
  const navigate = useNavigate()
  const { message, modal } = App.useApp()
  const meQuery = useMe()
  const isStaff = Boolean(meQuery.data?.is_staff)

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
    const result = await retryEntry(entry)
    if (result.ok) {
      message.success(`Re-enqueued ${result.id}`)
    } else {
      message.error(`Retry failed: ${result.id}`)
    }
  }, [message, retryEntry])

  const onBulkRetry = () => {
    const entries = (dlqQuery.data?.messages ?? []).filter((m) => selectedRowKeys.includes(m.dlq_message_id))
    if (entries.length === 0) return

    modal.confirm({
      title: 'Retry selected DLQ messages?',
      content: `Re-enqueue ${entries.length} message(s) sequentially.`,
      okText: 'Retry',
      cancelText: 'Cancel',
      onOk: async () => {
        const key = 'bulk-dlq-retry'
        let success = 0
        let failed = 0

        message.loading({ content: `Retrying ${entries.length}...`, key })
        for (let i = 0; i < entries.length; i++) {
          const result = await retryEntry(entries[i])
          if (result.ok) {
            success++
          } else {
            failed++
          }
          message.loading({ content: `Retrying... (${i + 1}/${entries.length})`, key })
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
              <Text strong>{operationId || '-'}</Text>
              {operationId && (
                <Button
                  size="small"
                  icon={<RightCircleOutlined />}
                  onClick={() => navigate(`/operations?tab=monitor&operation=${encodeURIComponent(operationId)}`)}
                  title="Open in Operations Monitor"
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
          onClick={() => onRetry(record)}
        >
          Retry
        </Button>
      ),
    },
  ]), [navigate, onRetry, retryMutation.isPending])

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

  if (!isStaff) {
    return (
      <div>
        <Title level={2}>DLQ</Title>
        <Alert
          type="warning"
          message="DLQ доступен только для staff пользователей"
        />
      </div>
    )
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>DLQ</Title>
          <Text type="secondary">Inspect worker dead-letter queue and safely re-enqueue operations (staff-only).</Text>
        </div>
        <Space>
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
      </div>

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
      />
    </Space>
  )
}
