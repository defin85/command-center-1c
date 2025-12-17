import { useCallback, useMemo, useState } from 'react'
import { Alert, App, Button, Card, DatePicker, Form, Input, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ReloadOutlined, RetweetOutlined, RightCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { Dayjs } from 'dayjs'

import type { DLQMessage } from '../../api/generated/model/dLQMessage'
import { useDlqMessages, useRetryDlqMessage } from '../../api/queries/dlq'

const { Title, Text } = Typography

type FilterState = {
  operation_id?: string
  error_code?: string
  since?: Dayjs
}

export function DLQPage() {
  const navigate = useNavigate()
  const { message, modal } = App.useApp()

  const [filters, setFilters] = useState<FilterState>({})
  const [retryReason, setRetryReason] = useState<string>('')
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(50)

  const params = useMemo(() => {
    const limit = pageSize
    const offset = (page - 1) * limit

    return {
      limit,
      offset,
      operation_id: filters.operation_id || undefined,
      error_code: filters.error_code || undefined,
      since: filters.since ? filters.since.toDate().toISOString() : undefined,
    }
  }, [filters, page, pageSize])

  const dlqQuery = useDlqMessages(params)
  const retryMutation = useRetryDlqMessage()

  type AxiosErrorLike = { response?: { status?: number } }
  const status = (dlqQuery.error as AxiosErrorLike | null)?.response?.status
  const showStaffWarning = status === 403

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

      <Card>
        <Form
          layout="inline"
          onValuesChange={(_, values) => {
            setFilters({
              operation_id: (values.operation_id || '').trim() || undefined,
              error_code: (values.error_code || '').trim() || undefined,
              since: values.since || undefined,
            })
            setPage(1)
          }}
        >
          <Form.Item label="Operation" name="operation_id">
            <Input placeholder="operation_id" allowClear style={{ width: 240 }} />
          </Form.Item>
          <Form.Item label="Error code" name="error_code">
            <Input placeholder="e.g., RAS_TIMEOUT" allowClear style={{ width: 200 }} />
          </Form.Item>
          <Form.Item label="Since" name="since">
            <DatePicker showTime allowClear style={{ width: 240 }} />
          </Form.Item>
          <Form.Item label="Retry reason">
            <Input
              placeholder="optional (stored in operation metadata)"
              value={retryReason}
              onChange={(e) => setRetryReason(e.target.value)}
              style={{ width: 320 }}
              allowClear
            />
          </Form.Item>
        </Form>
      </Card>

      <Table
        rowKey="dlq_message_id"
        loading={dlqQuery.isLoading}
        dataSource={dlqQuery.data?.messages ?? []}
        columns={columns}
        pagination={{
          current: page,
          pageSize,
          showSizeChanger: true,
          pageSizeOptions: [25, 50, 100, 200],
          total: dlqQuery.data?.total ?? 0,
        }}
        onChange={(p) => {
          setPage(p.current ?? 1)
          setPageSize(p.pageSize ?? 50)
        }}
        rowSelection={{
          selectedRowKeys,
          onChange: setSelectedRowKeys,
        }}
      />
    </Space>
  )
}
