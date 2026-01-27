import { useMemo } from 'react'
import { Alert, Button, Card, Space, Table, Tabs, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, RollbackOutlined } from '@ant-design/icons'

import { LazyJsonCodeEditor } from '../../../components/code/LazyJsonCodeEditor'
import type { ActionCatalogMode, ActionRow, DiffItem, SaveErrorHint } from '../actionCatalogTypes'
import { safeText } from '../actionCatalogUtils'
import type { ActionCatalogValidationResult } from './actionCatalogValidation'

const { Text } = Typography

export type ActionCatalogTabsProps = {
  mode: ActionCatalogMode
  onModeChange: (next: ActionCatalogMode) => void

  actionCatalogKey: string
  actionRows: ActionRow[]
  columns: ColumnsType<ActionRow>

  draftIsValidJson: boolean
  dirty: boolean
  actionsEditable: boolean
  disabledActionsCount: number
  saveErrorHints: SaveErrorHint[]

  onAddAction: () => void
  onRestoreLastDisabled: () => void

  rawValidation: ActionCatalogValidationResult
  diffItems: DiffItem[]
  diffSummary: { added: number; removed: number; changed: number }
  draftRaw: string
  onDraftRawChange: (raw: string) => void
  serverRaw: string | null
}

export function ActionCatalogTabs({
  mode,
  onModeChange,
  actionCatalogKey,
  actionRows,
  columns,
  draftIsValidJson,
  dirty,
  actionsEditable,
  disabledActionsCount,
  saveErrorHints,
  onAddAction,
  onRestoreLastDisabled,
  rawValidation,
  diffItems,
  diffSummary,
  draftRaw,
  onDraftRawChange,
  serverRaw,
}: ActionCatalogTabsProps) {
  const items = useMemo(() => ([
    {
      key: 'guided',
      label: 'Guided',
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {!draftIsValidJson && (
            <Alert
              type="warning"
              showIcon
              message="Текущий draft не является валидным JSON"
              description="Перейдите в Raw режим, чтобы исправить JSON."
            />
          )}
          {saveErrorHints.length > 0 && (
            <Alert
              type="error"
              showIcon
              message="Server validation errors"
              description="См. список ошибок выше; строки таблицы с ошибками помечены ERR."
            />
          )}

          <Card size="small">
            <Space size="middle" wrap align="center">
              <Text strong>Actions:</Text>
              <Tag data-testid="action-catalog-actions-count">{actionRows.length}</Tag>
              {dirty && <Tag color="orange" data-testid="action-catalog-dirty">Unsaved changes</Tag>}
              <Button
                size="small"
                icon={<PlusOutlined />}
                onClick={onAddAction}
                disabled={!actionsEditable}
                data-testid="action-catalog-add"
              >
                Add
              </Button>
              <Button
                size="small"
                icon={<RollbackOutlined />}
                onClick={onRestoreLastDisabled}
                disabled={!actionsEditable || disabledActionsCount === 0}
                data-testid="action-catalog-restore-last"
              >
                Restore last disabled
              </Button>
              {disabledActionsCount > 0 && (
                <Text type="secondary" data-testid="action-catalog-disabled-count">
                  Disabled: {disabledActionsCount}
                </Text>
              )}
            </Space>
          </Card>

          <Table<ActionRow>
            data-testid="action-catalog-guided-table"
            size="small"
            bordered
            pagination={false}
            columns={columns}
            dataSource={actionRows}
            rowKey={(row) => row.pos}
            locale={{ emptyText: 'Нет actions' }}
          />
        </Space>
      ),
    },
    {
      key: 'raw',
      label: 'Raw JSON',
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {dirty && <Tag color="orange" data-testid="action-catalog-dirty-raw">Unsaved changes</Tag>}
          {!rawValidation.ok && (
            <Alert
              type="error"
              showIcon
              message="Draft JSON is invalid"
              description={rawValidation.errors.join('; ')}
            />
          )}
          {rawValidation.ok && rawValidation.warnings.length > 0 && (
            <Alert
              type="warning"
              showIcon
              message="Draft JSON warnings"
              description={rawValidation.warnings.join('; ')}
            />
          )}

          <Card size="small">
            <Space size="middle" wrap>
              <Text strong>Preview:</Text>
              <Tag>Actions: {rawValidation.actionsCount}</Tag>
              {dirty && (
                <Tag data-testid="action-catalog-diff-count">
                  Changes: {diffItems.length}
                </Tag>
              )}
              {dirty && (
                <Text type="secondary">
                  Added: {diffSummary.added}, Removed: {diffSummary.removed}, Changed: {diffSummary.changed}
                </Text>
              )}
            </Space>
          </Card>

          {dirty && diffItems.length > 0 && (
            <Table<DiffItem>
              data-testid="action-catalog-diff-table"
              size="small"
              bordered
              pagination={{ pageSize: 10, showSizeChanger: false }}
              rowKey={(row) => `${row.kind}:${row.path}`}
              columns={[
                { title: 'Path', dataIndex: 'path', key: 'path', width: 320, render: (v: string) => <Text code>{v || '(root)'}</Text> },
                { title: 'Kind', dataIndex: 'kind', key: 'kind', width: 110, render: (v: string) => <Tag>{v}</Tag> },
                { title: 'Before', dataIndex: 'before', key: 'before', render: (v: unknown) => <Text>{safeText(v)}</Text> },
                { title: 'After', dataIndex: 'after', key: 'after', render: (v: unknown) => <Text>{safeText(v)}</Text> },
              ]}
              dataSource={diffItems}
            />
          )}

          <LazyJsonCodeEditor
            id="action-catalog-raw"
            title={actionCatalogKey}
            value={draftRaw}
            onChange={onDraftRawChange}
            height={520}
            readOnly={false}
            enableFormat
            enableCopy
            path="ui.action_catalog"
          />

          {serverRaw !== null && (
            <LazyJsonCodeEditor
              id="action-catalog-server"
              title="Server snapshot (read-only)"
              value={serverRaw}
              onChange={() => {}}
              height={280}
              readOnly
              enableFormat={false}
              enableCopy
              path="ui.action_catalog.server"
            />
          )}
        </Space>
      ),
    },
  ]), [
    actionCatalogKey,
    actionRows,
    actionsEditable,
    columns,
    diffItems,
    diffSummary,
    dirty,
    disabledActionsCount,
    draftIsValidJson,
    draftRaw,
    onAddAction,
    onDraftRawChange,
    onRestoreLastDisabled,
    rawValidation,
    saveErrorHints.length,
    serverRaw,
  ])

  return (
    <Tabs
      activeKey={mode}
      onChange={(next) => onModeChange(next as ActionCatalogMode)}
      items={items}
    />
  )
}

