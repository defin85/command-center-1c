import { useCallback, useEffect, useState } from 'react'
import { App as AntApp, Button, Card, Form, Input, Modal, Space, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { listMasterDataItems, upsertMasterDataItem, type PoolMasterItem } from '../../../api/intercompanyPools'
import { usePoolsTranslation } from '../../../i18n'
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
  const { t } = usePoolsTranslation()
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
      const resolved = resolveApiError(error, t('masterData.itemsTab.messages.failedToLoad'))
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [message, query, skuFilter, t])

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
      message.success(
        editingItem
          ? t('masterData.itemsTab.messages.updated')
          : t('masterData.itemsTab.messages.created')
      )
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.itemsTab.messages.failedToSave'))
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
    { title: t('masterData.itemsTab.columns.canonicalId'), dataIndex: 'canonical_id', key: 'canonical_id', width: 220 },
    { title: t('masterData.itemsTab.columns.name'), dataIndex: 'name', key: 'name', width: 220 },
    { title: t('masterData.itemsTab.columns.sku'), dataIndex: 'sku', key: 'sku', width: 160 },
    { title: t('masterData.itemsTab.columns.unit'), dataIndex: 'unit', key: 'unit', width: 140 },
    {
      title: t('masterData.itemsTab.columns.updated'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: t('masterData.itemsTab.columns.actions'),
      key: 'actions',
      width: 100,
      render: (_, row) => <Button size="small" onClick={() => openEditModal(row)}>{t('common.edit')}</Button>,
    },
  ]

  return (
    <>
      <Card>
        <Space wrap style={{ marginBottom: 16 }}>
          <Input
            allowClear
            placeholder={t('masterData.itemsTab.filters.searchPlaceholder')}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onPressEnter={() => void loadRows()}
            style={{ width: 320 }}
          />
          <Input
            allowClear
            placeholder={t('masterData.itemsTab.filters.skuPlaceholder')}
            value={skuFilter}
            onChange={(event) => setSkuFilter(event.target.value)}
            style={{ width: 220 }}
          />
          <Button onClick={() => void loadRows()} loading={loading}>{t('catalog.actions.refresh')}</Button>
          <Button type="primary" onClick={openCreateModal}>{t('masterData.itemsTab.actions.add')}</Button>
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
        title={editingItem ? t('masterData.itemsTab.modal.editTitle') : t('masterData.itemsTab.modal.createTitle')}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onOk={() => void handleSubmit()}
        okButtonProps={{ loading: isSaving }}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_id" label={t('masterData.itemsTab.modal.fields.canonicalId')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name" label={t('masterData.itemsTab.modal.fields.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="sku" label={t('masterData.itemsTab.modal.fields.sku')}>
            <Input />
          </Form.Item>
          <Form.Item name="unit" label={t('masterData.itemsTab.modal.fields.unit')}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
