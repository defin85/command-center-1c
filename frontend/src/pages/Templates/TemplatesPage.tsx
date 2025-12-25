import { useMemo, useState } from 'react'
import { Alert, App, Button, Space, Switch, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { OperationTemplate } from '../../api/generated/model/operationTemplate'
import { useOperationTemplates, useSyncTemplatesFromRegistry } from '../../api/queries/templates'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'

const { Title, Text } = Typography

export function TemplatesPage() {
  const { message } = App.useApp()
  const [dryRun, setDryRun] = useState<boolean>(false)
  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'operation_type', label: 'Operation Type', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'target_entity', label: 'Target', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'is_active', label: 'Active', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'updated_at', label: 'Updated', sortable: true, groupKey: 'time', groupLabel: 'Time' },
  ], [])

  const syncMutation = useSyncTemplatesFromRegistry()

  const columns: ColumnsType<OperationTemplate> = useMemo(() => ([
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (value: string, record) => (
        <div>
          <div style={{ fontWeight: 600 }}>{value}</div>
          <Text type="secondary">{record.id}</Text>
        </div>
      ),
    },
    {
      title: 'Operation Type',
      dataIndex: 'operation_type',
      key: 'operation_type',
      width: 220,
    },
    {
      title: 'Target',
      dataIndex: 'target_entity',
      key: 'target_entity',
      width: 120,
    },
    {
      title: 'Active',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 90,
      render: (v: boolean) => (v ? 'yes' : 'no'),
    },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (v: string) => (v ? new Date(v).toLocaleString() : ''),
    },
  ]), [])

  const table = useTableToolkit({
    tableId: 'templates',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize

  const templatesQuery = useOperationTemplates({
    search: table.search,
    filters: table.filtersPayload,
    sort: table.sortPayload,
    limit: table.pagination.pageSize,
    offset: pageStart,
  })

  const templates = templatesQuery.data?.templates ?? []
  const totalTemplates = typeof templatesQuery.data?.total === 'number'
    ? templatesQuery.data.total
    : typeof templatesQuery.data?.count === 'number'
      ? templatesQuery.data.count
      : templates.length

  const onSync = async () => {
    try {
      const result = await syncMutation.mutateAsync({ dry_run: dryRun })
      message.success(`${result.message}: created=${result.created}, updated=${result.updated}, unchanged=${result.unchanged}`)
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } } | null)?.response?.status
      if (status === 403) {
        message.error('Sync requires staff access')
        return
      }
      message.error('Failed to sync templates from registry')
    }
  }

  const showStaffWarning = templatesQuery.error
    && (templatesQuery.error as { response?: { status?: number } } | null)?.response?.status === 403

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>Operation Templates</Title>
          <Text type="secondary">List templates and sync from in-code registry (staff-only).</Text>
        </div>
        <Space>
          <Space>
            <Text>Dry run</Text>
            <Switch checked={dryRun} onChange={setDryRun} />
          </Space>
          <Button type="primary" loading={syncMutation.isPending} onClick={onSync}>
            Sync from registry
          </Button>
        </Space>
      </div>

      {showStaffWarning && (
        <Alert
          type="warning"
          message="Access denied"
          description="Templates endpoints require authentication; sync requires staff access."
          showIcon
        />
      )}

      <TableToolkit
        table={table}
        data={templates}
        total={totalTemplates}
        loading={templatesQuery.isLoading}
        rowKey="id"
        columns={columns}
        searchPlaceholder="Search templates"
      />
    </Space>
  )
}
