import { useCallback, useEffect, useState } from 'react'
import { App as AntApp, Button, Card, Checkbox, Form, Input, Modal, Select, Space, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  listMasterDataParties,
  upsertMasterDataParty,
  type PoolMasterBindingCatalogKind,
  type PoolMasterParty,
} from '../../../api/intercompanyPools'
import { usePoolsTranslation } from '../../../i18n'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'

type PartyFormValues = {
  canonical_id: string
  name: string
  full_name: string
  inn: string
  kpp: string
  is_our_organization: boolean
  is_counterparty: boolean
}

export function PartiesTab() {
  const { message } = AntApp.useApp()
  const { t } = usePoolsTranslation()
  const [rows, setRows] = useState<PoolMasterParty[]>([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<Exclude<PoolMasterBindingCatalogKind, ''> | undefined>(undefined)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingParty, setEditingParty] = useState<PoolMasterParty | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [form] = Form.useForm<PartyFormValues>()

  const loadRows = useCallback(async () => {
    setLoading(true)
    try {
      const response = await listMasterDataParties({
        query: query.trim() || undefined,
        role: roleFilter,
        limit: 100,
        offset: 0,
      })
      setRows(response.parties)
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.partiesTab.messages.failedToLoad'))
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [message, query, roleFilter, t])

  useEffect(() => {
    void loadRows()
  }, [loadRows])

  const openCreateModal = () => {
    setEditingParty(null)
    form.setFieldsValue({
      canonical_id: '',
      name: '',
      full_name: '',
      inn: '',
      kpp: '',
      is_our_organization: false,
      is_counterparty: true,
    })
    setIsModalOpen(true)
  }

  const openEditModal = (party: PoolMasterParty) => {
    setEditingParty(party)
    form.setFieldsValue({
      canonical_id: party.canonical_id,
      name: party.name,
      full_name: party.full_name || '',
      inn: party.inn || '',
      kpp: party.kpp || '',
      is_our_organization: party.is_our_organization,
      is_counterparty: party.is_counterparty,
    })
    setIsModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    if (!values.is_our_organization && !values.is_counterparty) {
      message.error(t('masterData.partiesTab.messages.roleRequired'))
      return
    }

    setIsSaving(true)
    try {
      await upsertMasterDataParty({
        party_id: editingParty?.id,
        canonical_id: values.canonical_id.trim(),
        name: values.name.trim(),
        full_name: values.full_name.trim(),
        inn: values.inn.trim(),
        kpp: values.kpp.trim(),
        is_our_organization: values.is_our_organization,
        is_counterparty: values.is_counterparty,
      })
      setIsModalOpen(false)
      message.success(
        editingParty
          ? t('masterData.partiesTab.messages.updated')
          : t('masterData.partiesTab.messages.created')
      )
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.partiesTab.messages.failedToSave'))
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

  const columns: ColumnsType<PoolMasterParty> = [
    { title: t('masterData.partiesTab.columns.canonicalId'), dataIndex: 'canonical_id', key: 'canonical_id', width: 220 },
    { title: t('masterData.partiesTab.columns.name'), dataIndex: 'name', key: 'name', width: 220 },
    {
      title: t('masterData.partiesTab.columns.roles'),
      key: 'roles',
      width: 220,
      render: (_, row) => (
        <Space>
          {row.is_our_organization && <Tag color="blue">{t('masterData.partiesTab.columns.organization')}</Tag>}
          {row.is_counterparty && <Tag color="green">{t('masterData.partiesTab.columns.counterparty')}</Tag>}
        </Space>
      ),
    },
    { title: t('masterData.partiesTab.columns.inn'), dataIndex: 'inn', key: 'inn', width: 140 },
    { title: t('masterData.partiesTab.columns.kpp'), dataIndex: 'kpp', key: 'kpp', width: 140 },
    {
      title: t('masterData.partiesTab.columns.updated'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: t('masterData.partiesTab.columns.actions'),
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
            placeholder={t('masterData.partiesTab.filters.searchPlaceholder')}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onPressEnter={() => void loadRows()}
            style={{ width: 320 }}
          />
          <Select
            allowClear
            placeholder={t('masterData.partiesTab.filters.rolePlaceholder')}
            value={roleFilter}
            options={[
              { value: 'organization', label: t('masterData.partiesTab.columns.organization') },
              { value: 'counterparty', label: t('masterData.partiesTab.columns.counterparty') },
            ]}
            onChange={(value) => setRoleFilter(value)}
            style={{ width: 200 }}
          />
          <Button onClick={() => void loadRows()} loading={loading}>{t('catalog.actions.refresh')}</Button>
          <Button type="primary" onClick={openCreateModal}>{t('masterData.partiesTab.actions.add')}</Button>
        </Space>
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={rows}
          pagination={false}
          scroll={{ x: 1200 }}
        />
      </Card>

      <Modal
        title={editingParty ? t('masterData.partiesTab.modal.editTitle') : t('masterData.partiesTab.modal.createTitle')}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onOk={() => void handleSubmit()}
        okButtonProps={{ loading: isSaving }}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_id" label={t('masterData.partiesTab.modal.fields.canonicalId')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name" label={t('masterData.partiesTab.modal.fields.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="full_name" label={t('masterData.partiesTab.modal.fields.fullName')}>
            <Input />
          </Form.Item>
          <Form.Item name="inn" label={t('masterData.partiesTab.modal.fields.inn')}>
            <Input />
          </Form.Item>
          <Form.Item name="kpp" label={t('masterData.partiesTab.modal.fields.kpp')}>
            <Input />
          </Form.Item>
          <Form.Item name="is_our_organization" valuePropName="checked">
            <Checkbox>{t('masterData.partiesTab.modal.roles.organization')}</Checkbox>
          </Form.Item>
          <Form.Item name="is_counterparty" valuePropName="checked">
            <Checkbox>{t('masterData.partiesTab.modal.roles.counterparty')}</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
