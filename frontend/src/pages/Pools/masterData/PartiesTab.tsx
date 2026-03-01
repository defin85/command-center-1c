import { useCallback, useEffect, useState } from 'react'
import { App as AntApp, Button, Card, Checkbox, Form, Input, Modal, Select, Space, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  listMasterDataParties,
  upsertMasterDataParty,
  type PoolMasterBindingCatalogKind,
  type PoolMasterParty,
} from '../../../api/intercompanyPools'
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
      const resolved = resolveApiError(error, 'Не удалось загрузить Party.')
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [message, query, roleFilter])

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
      message.error('Party должен иметь минимум одну роль: organization или counterparty.')
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
      message.success(editingParty ? 'Party обновлён.' : 'Party создан.')
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось сохранить Party.')
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
    { title: 'Canonical ID', dataIndex: 'canonical_id', key: 'canonical_id', width: 220 },
    { title: 'Name', dataIndex: 'name', key: 'name', width: 220 },
    {
      title: 'Roles',
      key: 'roles',
      width: 220,
      render: (_, row) => (
        <Space>
          {row.is_our_organization && <Tag color="blue">organization</Tag>}
          {row.is_counterparty && <Tag color="green">counterparty</Tag>}
        </Space>
      ),
    },
    { title: 'INN', dataIndex: 'inn', key: 'inn', width: 140 },
    { title: 'KPP', dataIndex: 'kpp', key: 'kpp', width: 140 },
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
            placeholder="Search canonical_id / name / INN"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onPressEnter={() => void loadRows()}
            style={{ width: 320 }}
          />
          <Select
            allowClear
            placeholder="Role"
            value={roleFilter}
            options={[
              { value: 'organization', label: 'organization' },
              { value: 'counterparty', label: 'counterparty' },
            ]}
            onChange={(value) => setRoleFilter(value)}
            style={{ width: 200 }}
          />
          <Button onClick={() => void loadRows()} loading={loading}>Refresh</Button>
          <Button type="primary" onClick={openCreateModal}>Add Party</Button>
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
        title={editingParty ? 'Edit Party' : 'Create Party'}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onOk={() => void handleSubmit()}
        okButtonProps={{ loading: isSaving }}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_id" label="Canonical ID" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="full_name" label="Full Name">
            <Input />
          </Form.Item>
          <Form.Item name="inn" label="INN">
            <Input />
          </Form.Item>
          <Form.Item name="kpp" label="KPP">
            <Input />
          </Form.Item>
          <Form.Item name="is_our_organization" valuePropName="checked">
            <Checkbox>Role: organization</Checkbox>
          </Form.Item>
          <Form.Item name="is_counterparty" valuePropName="checked">
            <Checkbox>Role: counterparty</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
