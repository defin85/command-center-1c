import { useMemo, useState } from 'react'
import { App, Alert, Button, Card, Input, Space, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useAdminAuditLog, type AdminAuditLogItem } from '../../../api/queries/rbac'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'

export function RbacAuditPanel(props: {
  enabled: boolean
  title?: string
  errorMessage?: string
}) {
  const { modal } = App.useApp()
  const [search, setSearch] = useState<string>('')
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(100)
  const debouncedSearch = useDebouncedValue(search, 300)

  const query = useAdminAuditLog({
    search: debouncedSearch || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  }, { enabled: props.enabled })

  const items = query.data?.items ?? []
  const total = typeof query.data?.total === 'number' ? query.data.total : items.length

  const columns: ColumnsType<AdminAuditLogItem> = useMemo(() => [
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => value ? new Date(value).toLocaleString() : '-',
    },
    {
      title: 'Actor',
      dataIndex: 'actor_username',
      key: 'actor_username',
      render: (value: string) => value || '-',
    },
    { title: 'Action', dataIndex: 'action', key: 'action' },
    {
      title: 'Outcome',
      dataIndex: 'outcome',
      key: 'outcome',
      render: (value: string) => (
        <Tag color={value === 'success' ? 'green' : (value === 'error' ? 'red' : 'default')}>
          {value}
        </Tag>
      ),
    },
    {
      title: 'Target',
      key: 'target',
      render: (_: unknown, row) => `${row.target_type}:${row.target_id}`,
    },
    {
      title: 'Reason',
      key: 'reason',
      render: (_: unknown, row) => {
        const reason = typeof row.metadata?.reason === 'string' ? row.metadata.reason : ''
        return reason ? reason : '-'
      },
    },
    {
      title: 'Details',
      key: 'details',
      render: (_: unknown, row) => (
        <Button
          size="small"
          onClick={() => {
            modal.info({
              title: `Audit #${row.id}`,
              width: 860,
              content: (
                <pre style={{ whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(row, null, 2)}
                </pre>
              ),
            })
          }}
        >
          View
        </Button>
      ),
    },
  ], [modal])

  return (
    <Card title={props.title ?? 'Admin Audit'} size="small">
      <Space wrap style={{ marginBottom: 12 }}>
        <Input
          placeholder="Search"
          style={{ width: 320 }}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        <Button onClick={() => query.refetch()} loading={query.isFetching}>
          Refresh
        </Button>
      </Space>
      {query.error && (
        <Alert
          style={{ marginBottom: 12 }}
          type="warning"
          message={props.errorMessage ?? 'Failed to load audit log'}
        />
      )}
      <Table
        size="small"
        columns={columns}
        dataSource={items}
        loading={query.isLoading}
        rowKey="id"
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (nextPage, nextPageSize) => {
            setPage(nextPage)
            setPageSize(nextPageSize)
          },
        }}
      />
    </Card>
  )
}
