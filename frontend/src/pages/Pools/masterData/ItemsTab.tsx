import { useCallback, useEffect, useState } from 'react'
import { App as AntApp, Button, Card, Form, Input, Modal, Space, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { listMasterDataItems, upsertMasterDataItem, type PoolMasterItem } from '../../../api/intercompanyPools'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'

type ItemFormValues = {
  canonical_id: string
  name: string
  sku: string
  unit: string
}

export function ItemsTab() {
  const { message } = AntApp.useApp()
  const [rows, setRows] = useState<PoolMasterItem[]>([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [skuFilter, setSkuFilter] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<PoolMasterItem | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [form] = Form.useForm<ItemFormValues>()

  const loadRows = useCallback(async () => {
    setLoading(true)
    try {
      const response = await listMasterDataItems({
        query: query.trim() || undefined,
        sku: skuFilter.trim() || undefined,
        limit: 100,
        offset: 0,
      })
      setRows(response.items)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить Item.')
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [message, query, skuFilter])

  useEffect(() => {
    void loadRows()
  }, [loadRows])

  const openCreateModal = () => {
    setEditingItem(null)
    form.setFieldsValue({
      canonical_id: '',
      name: '',
      sku: '',
      unit: '',
    })
    setIsModalOpen(true)
  }

  const openEditModal = (item: PoolMasterItem) => {
    setEditingItem(item)
    form.setFieldsValue({
      canonical_id: item.canonical_id,
      name: item.name,
      sku: item.sku || '',
      unit: item.unit || '',
    })
    setIsModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setIsSaving(true)
    try {
      await upsertMasterDataItem({
        item_id: editingItem?.id,
        canonical_id: values.canonical_id.trim(),
        name: values.name.trim(),
        sku: values.sku.trim(),
        unit: values.unit.trim(),
      })
      setIsModalOpen(false)
      message.success(editingItem ? 'Item обновлён.' : 'Item создан.')
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось сохранить Item.')
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

  const columns: ColumnsType<PoolMasterItem> = [
    { title: 'Canonical ID', dataIndex: 'canonical_id', key: 'canonical_id', width: 220 },
    { title: 'Name', dataIndex: 'name', key: 'name', width: 220 },
    { title: 'SKU', dataIndex: 'sku', key: 'sku', width: 160 },
    { title: 'Unit', dataIndex: 'unit', key: 'unit', width: 140 },
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
          <Input.Search
            allowClear
            placeholder="Search canonical_id / name / SKU"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onSearch={() => void loadRows()}
            style={{ width: 320 }}
          />
          <Input
            allowClear
            placeholder="SKU filter"
            value={skuFilter}
            onChange={(event) => setSkuFilter(event.target.value)}
            style={{ width: 220 }}
          />
          <Button onClick={() => void loadRows()} loading={loading}>Refresh</Button>
          <Button type="primary" onClick={openCreateModal}>Add Item</Button>
        </Space>
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={rows}
          pagination={false}
          scroll={{ x: 1060 }}
        />
      </Card>

      <Modal
        title={editingItem ? 'Edit Item' : 'Create Item'}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onOk={() => void handleSubmit()}
        okButtonProps={{ loading: isSaving }}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_id" label="Canonical ID" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="sku" label="SKU">
            <Input />
          </Form.Item>
          <Form.Item name="unit" label="Unit">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
