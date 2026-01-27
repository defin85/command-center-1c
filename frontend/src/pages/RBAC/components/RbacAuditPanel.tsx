import { useMemo, useState } from 'react'
import { App, Alert, Button, Card, Input, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useAdminAuditLog, type AdminAuditLogItem } from '../../../api/queries/rbac'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { ReasonModal } from './ReasonModal'
import { getUndoCommand, type UndoCommand } from './rbacAuditUndo'

const { Text } = Typography

type RbacAuditPanelI18n = {
  searchPlaceholder?: string
  refreshText?: string
  viewText?: string
  detailsModalTitle?: (id: number) => string
  columnCreatedAt?: string
  columnActor?: string
  columnAction?: string
  columnOutcome?: string
  columnTarget?: string
  columnReason?: string
  columnDetails?: string
  detailsAuditIdLabel?: string
  detailsActionLabel?: string
  detailsTargetLabel?: string
  formatUndoTitle?: (cmd: UndoCommand, item: AdminAuditLogItem) => string
}

const EMPTY_I18N: RbacAuditPanelI18n = {}

export function RbacAuditPanel(props: {
  enabled: boolean
  title?: string
  errorMessage?: string
  undoLabel?: string
  undoModalTitle?: string
  undoOkText?: string
  undoCancelText?: string
  undoReasonPlaceholder?: string
  undoReasonRequiredMessage?: string
  undoSuccessMessage?: string
  undoFailedMessage?: string
  undoNotSupportedMessage?: string
  i18n?: RbacAuditPanelI18n
}) {
  const { modal, message } = App.useApp()
  const i18n = props.i18n ?? EMPTY_I18N
  const [search, setSearch] = useState<string>('')
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(100)
  const debouncedSearch = useDebouncedValue(search, 300)
  const [undoOpen, setUndoOpen] = useState(false)
  const [undoItem, setUndoItem] = useState<AdminAuditLogItem | null>(null)
  const [undoLoading, setUndoLoading] = useState(false)

  const query = useAdminAuditLog({
    search: debouncedSearch || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  }, { enabled: props.enabled })

  const items = query.data?.items ?? []
  const total = typeof query.data?.total === 'number' ? query.data.total : items.length

  const columns: ColumnsType<AdminAuditLogItem> = useMemo(() => [
    {
      title: i18n.columnCreatedAt ?? 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => value ? new Date(value).toLocaleString() : '-',
    },
    {
      title: i18n.columnActor ?? 'Actor',
      dataIndex: 'actor_username',
      key: 'actor_username',
      render: (value: string) => value || '-',
    },
    { title: i18n.columnAction ?? 'Action', dataIndex: 'action', key: 'action' },
    {
      title: i18n.columnOutcome ?? 'Outcome',
      dataIndex: 'outcome',
      key: 'outcome',
      render: (value: string) => (
        <Tag color={value === 'success' ? 'green' : (value === 'error' ? 'red' : 'default')}>
          {value}
        </Tag>
      ),
    },
    {
      title: i18n.columnTarget ?? 'Target',
      key: 'target',
      render: (_: unknown, row) => `${row.target_type}:${row.target_id}`,
    },
    {
      title: i18n.columnReason ?? 'Reason',
      key: 'reason',
      render: (_: unknown, row) => {
        const reason = typeof row.metadata?.reason === 'string' ? row.metadata.reason : ''
        return reason ? reason : '-'
      },
    },
    {
      title: i18n.columnDetails ?? 'Details',
      key: 'details',
      render: (_: unknown, row) => (
        <Space size="small" wrap>
          <Button
            size="small"
            onClick={() => {
              modal.info({
                title: i18n.detailsModalTitle?.(row.id) ?? `Audit #${row.id}`,
                width: 860,
                content: (
                  <pre style={{ whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(row, null, 2)}
                  </pre>
                ),
              })
            }}
          >
            {i18n.viewText ?? 'View'}
          </Button>
          {props.enabled && (
            (() => {
              const cmd = getUndoCommand(row)
              if (!cmd) return <Text type="secondary">-</Text>
              return (
                <Button
                  size="small"
                  onClick={() => {
                    setUndoItem(row)
                    setUndoOpen(true)
                  }}
                >
                  {props.undoLabel ?? 'Undo'}
                </Button>
              )
            })()
          )}
        </Space>
      ),
    },
  ], [i18n, modal, props.enabled, props.undoLabel])

  return (
    <Card title={props.title ?? 'Admin Audit'} size="small">
      <Space wrap style={{ marginBottom: 12 }}>
        <Input
          placeholder={i18n.searchPlaceholder ?? 'Search'}
          style={{ width: 320 }}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        <Button onClick={() => query.refetch()} loading={query.isFetching}>
          {i18n.refreshText ?? 'Refresh'}
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

      <ReasonModal
        title={props.undoModalTitle ?? 'Undo change'}
        open={undoOpen}
        okText={props.undoOkText ?? 'Undo'}
        cancelText={props.undoCancelText ?? 'Cancel'}
        okButtonProps={{ loading: undoLoading }}
        reasonPlaceholder={props.undoReasonPlaceholder}
        requiredMessage={props.undoReasonRequiredMessage}
        onCancel={() => {
          if (undoLoading) return
          setUndoOpen(false)
          setUndoItem(null)
        }}
        onOk={async (reason) => {
          if (!undoItem) return
          const cmd = getUndoCommand(undoItem)
          if (!cmd) {
            message.warning(props.undoNotSupportedMessage ?? 'Undo is not supported for this entry')
            setUndoOpen(false)
            setUndoItem(null)
            return
          }

          setUndoLoading(true)
          try {
            await cmd.run(reason)
            message.success(props.undoSuccessMessage ?? 'Undo completed')
            setUndoOpen(false)
            setUndoItem(null)
            query.refetch()
          } catch {
            message.error(props.undoFailedMessage ?? 'Undo failed')
          } finally {
            setUndoLoading(false)
          }
        }}
      >
        {undoItem ? (
          <Alert
            type="info"
            showIcon
            message={(() => {
              const cmd = getUndoCommand(undoItem)
              if (!cmd) return props.undoNotSupportedMessage ?? 'Undo is not supported for this entry'
              return i18n.formatUndoTitle ? i18n.formatUndoTitle(cmd, undoItem) : cmd.title
            })()}
            description={(
              <Space direction="vertical" size={4}>
                <div><Text type="secondary">{i18n.detailsAuditIdLabel ?? 'Audit ID:'}</Text> <Text>#{undoItem.id}</Text></div>
                <div><Text type="secondary">{i18n.detailsActionLabel ?? 'Action:'}</Text> <Text>{undoItem.action}</Text></div>
                <div><Text type="secondary">{i18n.detailsTargetLabel ?? 'Target:'}</Text> <Text>{undoItem.target_type}:{undoItem.target_id}</Text></div>
              </Space>
            )}
          />
        ) : null}
      </ReasonModal>
    </Card>
  )
}
