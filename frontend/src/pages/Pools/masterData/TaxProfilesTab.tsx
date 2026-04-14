import { useCallback, useEffect, useState } from 'react'
import { App as AntApp, Button, Card, Form, Input, InputNumber, Modal, Space, Switch, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  listMasterDataTaxProfiles,
  upsertMasterDataTaxProfile,
  type PoolMasterTaxProfile,
} from '../../../api/intercompanyPools'
import { usePoolsTranslation } from '../../../i18n'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'

type TaxProfileFormValues = {
  canonical_id: string
  vat_rate: number
  vat_included: boolean
  vat_code: string
}

export function TaxProfilesTab() {
  const { message } = AntApp.useApp()
  const { t } = usePoolsTranslation()
  const [rows, setRows] = useState<PoolMasterTaxProfile[]>([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [vatCodeFilter, setVatCodeFilter] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingTaxProfile, setEditingTaxProfile] = useState<PoolMasterTaxProfile | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [form] = Form.useForm<TaxProfileFormValues>()

  const loadRows = useCallback(async () => {
    setLoading(true)
    try {
      const response = await listMasterDataTaxProfiles({
        query: query.trim() || undefined,
        vat_code: vatCodeFilter.trim() || undefined,
        limit: 100,
        offset: 0,
      })
      setRows(response.tax_profiles)
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.taxProfilesTab.messages.failedToLoad'))
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [message, query, vatCodeFilter, t])

  useEffect(() => {
    void loadRows()
  }, [loadRows])

  const openCreateModal = () => {
    setEditingTaxProfile(null)
    form.setFieldsValue({
      canonical_id: '',
      vat_rate: 20,
      vat_included: true,
      vat_code: '',
    })
    setIsModalOpen(true)
  }

  const openEditModal = (taxProfile: PoolMasterTaxProfile) => {
    setEditingTaxProfile(taxProfile)
    form.setFieldsValue({
      canonical_id: taxProfile.canonical_id,
      vat_rate: taxProfile.vat_rate,
      vat_included: taxProfile.vat_included,
      vat_code: taxProfile.vat_code,
    })
    setIsModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setIsSaving(true)
    try {
      await upsertMasterDataTaxProfile({
        tax_profile_id: editingTaxProfile?.id,
        canonical_id: values.canonical_id.trim(),
        vat_rate: values.vat_rate,
        vat_included: values.vat_included,
        vat_code: values.vat_code.trim(),
      })
      setIsModalOpen(false)
      message.success(
        editingTaxProfile
          ? t('masterData.taxProfilesTab.messages.updated')
          : t('masterData.taxProfilesTab.messages.created')
      )
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.taxProfilesTab.messages.failedToSave'))
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

  const columns: ColumnsType<PoolMasterTaxProfile> = [
    { title: t('masterData.taxProfilesTab.columns.canonicalId'), dataIndex: 'canonical_id', key: 'canonical_id', width: 240 },
    { title: t('masterData.taxProfilesTab.columns.vatCode'), dataIndex: 'vat_code', key: 'vat_code', width: 180 },
    { title: t('masterData.taxProfilesTab.columns.vatRate'), dataIndex: 'vat_rate', key: 'vat_rate', width: 120 },
    {
      title: t('masterData.taxProfilesTab.columns.vatIncluded'),
      dataIndex: 'vat_included',
      key: 'vat_included',
      width: 140,
      render: (value: boolean) => (
        value
          ? t('masterData.taxProfilesTab.columns.yes')
          : t('masterData.taxProfilesTab.columns.no')
      ),
    },
    {
      title: t('masterData.taxProfilesTab.columns.updated'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: t('masterData.taxProfilesTab.columns.actions'),
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
            placeholder={t('masterData.taxProfilesTab.filters.searchPlaceholder')}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onPressEnter={() => void loadRows()}
            style={{ width: 320 }}
          />
          <Input
            allowClear
            placeholder={t('masterData.taxProfilesTab.filters.vatCodePlaceholder')}
            value={vatCodeFilter}
            onChange={(event) => setVatCodeFilter(event.target.value)}
            style={{ width: 220 }}
          />
          <Button onClick={() => void loadRows()} loading={loading}>{t('catalog.actions.refresh')}</Button>
          <Button type="primary" onClick={openCreateModal}>{t('masterData.taxProfilesTab.actions.add')}</Button>
        </Space>
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={rows}
          pagination={false}
          scroll={{ x: 1100 }}
        />
      </Card>

      <Modal
        title={editingTaxProfile ? t('masterData.taxProfilesTab.modal.editTitle') : t('masterData.taxProfilesTab.modal.createTitle')}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onOk={() => void handleSubmit()}
        okButtonProps={{ loading: isSaving }}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_id" label={t('masterData.taxProfilesTab.modal.fields.canonicalId')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="vat_code" label={t('masterData.taxProfilesTab.modal.fields.vatCode')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="vat_rate" label={t('masterData.taxProfilesTab.modal.fields.vatRate')} rules={[{ required: true }]}>
            <InputNumber min={0} max={100} precision={2} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="vat_included" label={t('masterData.taxProfilesTab.modal.fields.vatIncluded')} valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
