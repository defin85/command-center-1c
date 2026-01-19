import { Button, Drawer, List, Space, Spin, Typography } from 'antd'
import dayjs from 'dayjs'
import type { ActionCatalogAction } from '../../../api/generated/model/actionCatalogAction'
import type { DatabaseExtensionsSnapshotResponse } from '../../../api/generated/model/databaseExtensionsSnapshotResponse'

export interface ExtensionsDrawerProps {
  open: boolean
  databaseName?: string
  actions: ActionCatalogAction[]
  actionsLoading?: boolean
  pendingActionId?: string | null
  onClose: () => void
  onRunAction: (action: ActionCatalogAction) => Promise<void>
  snapshot?: DatabaseExtensionsSnapshotResponse | null
  snapshotLoading?: boolean
  snapshotFetching?: boolean
  onRefreshSnapshot: () => void
}

export const ExtensionsDrawer = ({
  open,
  databaseName,
  actions,
  actionsLoading = false,
  pendingActionId = null,
  onClose,
  onRunAction,
  snapshot,
  snapshotLoading = false,
  snapshotFetching = false,
  onRefreshSnapshot,
}: ExtensionsDrawerProps) => {
  return (
    <Drawer
      title={databaseName ? `Extensions: ${databaseName}` : 'Extensions'}
      open={open}
      onClose={onClose}
      width={720}
      destroyOnHidden
    >
      {actionsLoading ? (
        <Spin />
      ) : (
        <>
          <Typography.Title level={5} style={{ marginTop: 0 }}>
            Actions
          </Typography.Title>
          {actions.length === 0 ? (
            <Typography.Text type="secondary">
              Нет доступных действий для контекста database_card.
            </Typography.Text>
          ) : (
            <List
              dataSource={actions}
              renderItem={(action) => (
                <List.Item
                  actions={[
                    <Button
                      key="run"
                      type="primary"
                      size="small"
                      disabled={Boolean(pendingActionId && pendingActionId !== action.id)}
                      loading={pendingActionId === action.id}
                      onClick={() => onRunAction(action)}
                    >
                      Run
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={action.label}
                    description={`${action.id} · ${action.executor.kind}`}
                  />
                </List.Item>
              )}
            />
          )}

          <Typography.Title level={5} style={{ marginTop: 24 }}>
            Snapshot
          </Typography.Title>
          <Space style={{ marginBottom: 8 }}>
            <Button
              size="small"
              onClick={onRefreshSnapshot}
              loading={snapshotFetching}
            >
              Refresh
            </Button>
            <Typography.Text type="secondary">
              Updated:{' '}
              {snapshot?.updated_at
                ? dayjs(snapshot.updated_at).format('DD.MM.YYYY HH:mm')
                : 'n/a'}
            </Typography.Text>
            {snapshot?.source_operation_id && (
              <Typography.Text type="secondary">
                Source op: {snapshot.source_operation_id}
              </Typography.Text>
            )}
          </Space>

          {snapshotLoading ? (
            <Spin />
          ) : (
            <pre style={{ maxHeight: 360, overflow: 'auto', background: '#fafafa', padding: 12, borderRadius: 6 }}>
              {JSON.stringify(snapshot?.snapshot ?? {}, null, 2)}
            </pre>
          )}
        </>
      )}
    </Drawer>
  )
}

