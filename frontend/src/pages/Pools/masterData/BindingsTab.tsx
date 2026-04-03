import { useCallback, useEffect, useMemo, useState } from 'react'
import { App as AntApp, Button, Card, Form, Input, Modal, Select, Space, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  type PoolMasterDataRegistryEntry,
  listMasterDataBindings,
  listPoolTargetDatabases,
  upsertMasterDataBinding,
  type PoolMasterBindingCatalogKind,
  type PoolMasterBindingSyncStatus,
  type PoolMasterDataBinding,
  type PoolMasterDataEntityType,
  type SimpleDatabaseRef,
} from '../../../api/intercompanyPools'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import { getDefaultDirectBindingEntityType, getDirectBindingEntityOptions } from './registry'

type BindingFormValues = {
  entity_type: PoolMasterDataEntityType
  canonical_id: string
  database_id: string
  ib_ref_key: string
  ib_catalog_kind: PoolMasterBindingCatalogKind
  owner_counterparty_canonical_id: string
  sync_status: PoolMasterBindingSyncStatus
  fingerprint: string
}

const SYNC_STATUS_OPTIONS: { value: PoolMasterBindingSyncStatus; label: string }[] = [
  { value: 'resolved', label: 'resolved' },
  { value: 'upserted', label: 'upserted' },
  { value: 'conflict', label: 'conflict' },
]

type BindingsTabProps = {
  registryEntries: PoolMasterDataRegistryEntry[]
}

export function BindingsTab({ registryEntries }: BindingsTabProps) {
  const { message } = AntApp.useApp()
  const [rows, setRows] = useState<PoolMasterDataBinding[]>([])
  const [databases, setDatabases] = useState<SimpleDatabaseRef[]>([])
  const [loading, setLoading] = useState(false)
  const [queryCanonicalId, setQueryCanonicalId] = useState('')
  const [entityTypeFilter, setEntityTypeFilter] = useState<PoolMasterDataEntityType | undefined>(undefined)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingBinding, setEditingBinding] = useState<PoolMasterDataBinding | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [form] = Form.useForm<BindingFormValues>()
  const entityTypeOptions = useMemo(
    () => getDirectBindingEntityOptions(registryEntries),
    [registryEntries]
  )
  const defaultEntityType = useMemo(
    () => getDefaultDirectBindingEntityType(registryEntries),
    [registryEntries]
  )

  const loadDatabases = useCallback(async () => {
    try {
      const items = await listPoolTargetDatabases()
      setDatabases(items)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить список баз.')
      message.error(resolved.message)
    }
  }, [message])

  const loadRows = useCallback(async () => {
    setLoading(true)
    try {
      const response = await listMasterDataBindings({
        entity_type: entityTypeFilter,
        canonical_id: queryCanonicalId.trim() || undefined,
        limit: 200,
        offset: 0,
      })
      setRows(response.bindings)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить Bindings.')
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [entityTypeFilter, message, queryCanonicalId])

  useEffect(() => {
    void loadRows()
  }, [loadRows])

  useEffect(() => {
    void loadDatabases()
  }, [loadDatabases])

  const openCreateModal = () => {
    setEditingBinding(null)
    form.setFieldsValue({
      entity_type: defaultEntityType,
      canonical_id: '',
      database_id: '',
      ib_ref_key: '',
      ib_catalog_kind: 'organization',
      owner_counterparty_canonical_id: '',
      sync_status: 'resolved',
      fingerprint: '',
    })
    setIsModalOpen(true)
  }

  const openEditModal = (binding: PoolMasterDataBinding) => {
    setEditingBinding(binding)
    form.setFieldsValue({
      entity_type: binding.entity_type,
      canonical_id: binding.canonical_id,
      database_id: binding.database_id,
      ib_ref_key: binding.ib_ref_key,
      ib_catalog_kind: binding.ib_catalog_kind || '',
      owner_counterparty_canonical_id: binding.owner_counterparty_canonical_id || '',
      sync_status: binding.sync_status,
      fingerprint: binding.fingerprint || '',
    })
    setIsModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    if (values.entity_type === 'party' && !values.ib_catalog_kind) {
      form.setFields([{ name: 'ib_catalog_kind', errors: ['Required for party bindings.'] }])
      return
    }
    if (values.entity_type === 'contract' && !values.owner_counterparty_canonical_id.trim()) {
      form.setFields([
        { name: 'owner_counterparty_canonical_id', errors: ['Required for contract bindings.'] },
      ])
      return
    }

    const normalizedCatalogKind: PoolMasterBindingCatalogKind =
      values.entity_type === 'party' ? values.ib_catalog_kind : ''
    const normalizedOwnerCounterpartyCanonicalId =
      values.entity_type === 'contract' ? values.owner_counterparty_canonical_id.trim() : ''

    setIsSaving(true)
    try {
      await upsertMasterDataBinding({
        binding_id: editingBinding?.id,
        entity_type: values.entity_type,
        canonical_id: values.canonical_id.trim(),
        database_id: values.database_id,
        ib_ref_key: values.ib_ref_key.trim(),
        ib_catalog_kind: normalizedCatalogKind,
        owner_counterparty_canonical_id: normalizedOwnerCounterpartyCanonicalId,
        sync_status: values.sync_status,
        fingerprint: values.fingerprint.trim(),
      })
      setIsModalOpen(false)
      message.success(editingBinding ? 'Binding обновлён.' : 'Binding создан.')
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось сохранить Binding.')
      if (Object.keys(resolved.fieldErrors).length > 0) {
        form.setFields((
          Object.entries(resolved.fieldErrors).map(([name, errors]) => ({ name, errors }))
        ) as never)
      }
      message.error(resolved.message)
    } finally {
      setIsSaving(false)
    }
  }

  const columns: ColumnsType<PoolMasterDataBinding> = [
    { title: 'Entity Type', dataIndex: 'entity_type', key: 'entity_type', width: 120 },
    { title: 'Canonical ID', dataIndex: 'canonical_id', key: 'canonical_id', width: 220 },
    {
      title: 'Database',
      dataIndex: 'database_id',
      key: 'database_id',
      width: 260,
      render: (value: string) => databases.find((item) => item.id === value)?.name || value,
    },
    { title: 'IB Ref Key', dataIndex: 'ib_ref_key', key: 'ib_ref_key', width: 240 },
    {
      title: 'Scope',
      key: 'scope',
      width: 220,
      render: (_, row) => (
        <Space>
          {row.ib_catalog_kind && <Tag color="blue">{row.ib_catalog_kind}</Tag>}
          {row.owner_counterparty_canonical_id && (
            <Tag color="purple">{row.owner_counterparty_canonical_id}</Tag>
          )}
        </Space>
      ),
    },
    { title: 'Sync Status', dataIndex: 'sync_status', key: 'sync_status', width: 120 },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_, row) => <Button size="small" onClick={() => openEditModal(row)}>Edit</Button>,
    },
  ]

  return (
    <>
      <Card>
        <Space wrap style={{ marginBottom: 16 }}>
          <Input
            allowClear
            placeholder="Canonical ID filter"
            value={queryCanonicalId}
            onChange={(event) => setQueryCanonicalId(event.target.value)}
            style={{ width: 280 }}
          />
          <Select
            allowClear
            placeholder="Entity type"
            value={entityTypeFilter}
            options={entityTypeOptions}
            onChange={(value) => setEntityTypeFilter(value)}
            style={{ width: 180 }}
          />
          <Button onClick={() => void loadRows()} loading={loading}>Refresh</Button>
          <Button type="primary" onClick={openCreateModal}>Add Binding</Button>
        </Space>
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={rows}
          pagination={false}
          scroll={{ x: 1460 }}
        />
      </Card>

      <Modal
        title={editingBinding ? 'Edit Binding' : 'Create Binding'}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onOk={() => void handleSubmit()}
        okButtonProps={{ loading: isSaving }}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="entity_type" label="Entity Type" rules={[{ required: true }]}>
            <Select options={entityTypeOptions} />
          </Form.Item>
          <Form.Item name="canonical_id" label="Canonical ID" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="database_id" label="Database" rules={[{ required: true }]}>
            <Select
              showSearch
              options={databases.map((database) => ({ value: database.id, label: database.name }))}
            />
          </Form.Item>
          <Form.Item name="ib_ref_key" label="IB Ref Key" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="ib_catalog_kind" label="IB Catalog Kind">
            <Select
              allowClear
              options={[
                { value: 'organization', label: 'organization' },
                { value: 'counterparty', label: 'counterparty' },
              ]}
            />
          </Form.Item>
          <Form.Item name="owner_counterparty_canonical_id" label="Owner Counterparty Canonical ID">
            <Input />
          </Form.Item>
          <Form.Item name="sync_status" label="Sync Status" rules={[{ required: true }]}>
            <Select options={SYNC_STATUS_OPTIONS} />
          </Form.Item>
          <Form.Item name="fingerprint" label="Fingerprint">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
