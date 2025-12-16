import { useMemo, useState } from 'react'
import { Alert, Button, Card, Form, Input, Select, Space, Switch, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { OperationTemplate } from '../../api/generated/model/operationTemplate'
import { useOperationTemplates, useSyncTemplatesFromRegistry } from '../../api/queries/templates'

const { Title, Text } = Typography

type TargetEntity = 'infobase' | 'cluster' | 'entity'

export function TemplatesPage() {
  const [dryRun, setDryRun] = useState<boolean>(false)
  const [filters, setFilters] = useState<{
    operation_type?: string
    target_entity?: TargetEntity
    is_active?: boolean
  }>({})

  const templatesQuery = useOperationTemplates({
    operation_type: filters.operation_type,
    target_entity: filters.target_entity,
    is_active: filters.is_active,
    limit: 1000,
    offset: 0,
  })

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

  const onSync = async () => {
    try {
      const result = await syncMutation.mutateAsync({ dry_run: dryRun })
      message.success(`${result.message}: created=${result.created}, updated=${result.updated}, unchanged=${result.unchanged}`)
    } catch (e: any) {
      const status = e?.response?.status
      if (status === 403) {
        message.error('Sync requires staff access')
        return
      }
      message.error('Failed to sync templates from registry')
    }
  }

  const showStaffWarning = templatesQuery.error && (templatesQuery as any).error?.response?.status === 403

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

      <Card>
        <Form
          layout="inline"
          onValuesChange={(_, values) => {
            setFilters({
              operation_type: values.operation_type || undefined,
              target_entity: values.target_entity || undefined,
              is_active: typeof values.is_active === 'boolean' ? values.is_active : undefined,
            })
          }}
        >
          <Form.Item label="Operation type" name="operation_type">
            <Input placeholder="e.g., lock_scheduled_jobs" allowClear style={{ width: 260 }} />
          </Form.Item>
          <Form.Item label="Target" name="target_entity">
            <Select
              allowClear
              style={{ width: 160 }}
              options={[
                { label: 'infobase', value: 'infobase' },
                { label: 'cluster', value: 'cluster' },
                { label: 'entity', value: 'entity' },
              ]}
            />
          </Form.Item>
          <Form.Item label="Active" name="is_active">
            <Select
              allowClear
              style={{ width: 120 }}
              options={[
                { label: 'yes', value: true },
                { label: 'no', value: false },
              ]}
            />
          </Form.Item>
        </Form>
      </Card>

      <Table
        rowKey="id"
        loading={templatesQuery.isLoading}
        dataSource={templatesQuery.data ?? []}
        columns={columns}
        pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: [25, 50, 100, 200] }}
      />
    </Space>
  )
}

