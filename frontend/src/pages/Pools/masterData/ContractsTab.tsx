import { useCallback, useEffect, useState } from 'react'
import { App as AntApp, Button, Card, Form, Input, Modal, Select, Space, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  listMasterDataContracts,
  listMasterDataParties,
  upsertMasterDataContract,
  type PoolMasterContract,
  type PoolMasterParty,
} from '../../../api/intercompanyPools'
import { usePoolsTranslation } from '../../../i18n'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'

type ContractFormValues = {
  canonical_id: string
  name: string
  owner_counterparty_id: string
  number: string
  date: string
}

export function ContractsTab() {
  const { message } = AntApp.useApp()
  const { t } = usePoolsTranslation()
  const [rows, setRows] = useState<PoolMasterContract[]>([])
  const [counterparties, setCounterparties] = useState<PoolMasterParty[]>([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [ownerFilter, setOwnerFilter] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingContract, setEditingContract] = useState<PoolMasterContract | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [form] = Form.useForm<ContractFormValues>()

  const loadCounterparties = useCallback(async () => {
    try {
      const response = await listMasterDataParties({ role: 'counterparty', limit: 200, offset: 0 })
      setCounterparties(response.parties)
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.contractsTab.messages.failedToLoadCounterparties'))
      message.error(resolved.message)
    }
  }, [message, t])

  const loadRows = useCallback(async () => {
    setLoading(true)
    try {
      const response = await listMasterDataContracts({
        query: query.trim() || undefined,
        owner_counterparty_canonical_id: ownerFilter.trim() || undefined,
        limit: 100,
        offset: 0,
      })
      setRows(response.contracts)
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.contractsTab.messages.failedToLoad'))
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [message, ownerFilter, query, t])

  useEffect(() => {
    void loadRows()
  }, [loadRows])

  useEffect(() => {
    void loadCounterparties()
  }, [loadCounterparties])

  const openCreateModal = () => {
    setEditingContract(null)
    form.setFieldsValue({
      canonical_id: '',
      name: '',
      owner_counterparty_id: '',
      number: '',
      date: '',
    })
    setIsModalOpen(true)
  }

  const openEditModal = (contract: PoolMasterContract) => {
    setEditingContract(contract)
    const owner = counterparties.find((party) => party.canonical_id === contract.owner_counterparty_canonical_id)
    form.setFieldsValue({
      canonical_id: contract.canonical_id,
      name: contract.name,
      owner_counterparty_id: owner?.id || '',
      number: contract.number || '',
      date: contract.date || '',
    })
    setIsModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    if (!values.owner_counterparty_id) {
      message.error(t('masterData.contractsTab.messages.ownerRequired'))
      return
    }

    setIsSaving(true)
    try {
      await upsertMasterDataContract({
        contract_id: editingContract?.id,
        canonical_id: values.canonical_id.trim(),
        name: values.name.trim(),
        owner_counterparty_id: values.owner_counterparty_id,
        number: values.number.trim(),
        date: values.date.trim() || null,
      })
      setIsModalOpen(false)
      message.success(
        editingContract
          ? t('masterData.contractsTab.messages.updated')
          : t('masterData.contractsTab.messages.created')
      )
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.contractsTab.messages.failedToSave'))
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

  const ownerOptions = counterparties.map((party) => ({
    value: party.id,
    label: `${party.name} (${party.canonical_id})`,
  }))

  const columns: ColumnsType<PoolMasterContract> = [
    { title: t('masterData.contractsTab.columns.canonicalId'), dataIndex: 'canonical_id', key: 'canonical_id', width: 220 },
    { title: t('masterData.contractsTab.columns.name'), dataIndex: 'name', key: 'name', width: 220 },
    {
      title: t('masterData.contractsTab.columns.ownerCounterparty'),
      dataIndex: 'owner_counterparty_canonical_id',
      key: 'owner_counterparty_canonical_id',
      width: 220,
    },
    { title: t('masterData.contractsTab.columns.number'), dataIndex: 'number', key: 'number', width: 160 },
    { title: t('masterData.contractsTab.columns.date'), dataIndex: 'date', key: 'date', width: 140, render: (value: string | null) => value || '—' },
    {
      title: t('masterData.contractsTab.columns.updated'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: t('masterData.contractsTab.columns.actions'),
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
            placeholder={t('masterData.contractsTab.filters.searchPlaceholder')}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onPressEnter={() => void loadRows()}
            style={{ width: 320 }}
          />
          <Select
            allowClear
            showSearch
            placeholder={t('masterData.contractsTab.filters.ownerPlaceholder')}
            value={ownerFilter || undefined}
            options={counterparties.map((party) => ({
              value: party.canonical_id,
              label: `${party.name} (${party.canonical_id})`,
            }))}
            onChange={(value) => setOwnerFilter(value || '')}
            style={{ width: 320 }}
          />
          <Button onClick={() => void loadRows()} loading={loading}>{t('catalog.actions.refresh')}</Button>
          <Button type="primary" onClick={openCreateModal}>{t('masterData.contractsTab.actions.add')}</Button>
        </Space>
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={rows}
          pagination={false}
          scroll={{ x: 1280 }}
        />
      </Card>

      <Modal
        title={editingContract ? t('masterData.contractsTab.modal.editTitle') : t('masterData.contractsTab.modal.createTitle')}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onOk={() => void handleSubmit()}
        okButtonProps={{ loading: isSaving }}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_id" label={t('masterData.contractsTab.modal.fields.canonicalId')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name" label={t('masterData.contractsTab.modal.fields.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="owner_counterparty_id"
            label={t('masterData.contractsTab.modal.fields.ownerCounterparty')}
            rules={[{ required: true }]}
          >
            <Select
              showSearch
              options={ownerOptions}
              placeholder={t('masterData.contractsTab.modal.selectCounterparty')}
            />
          </Form.Item>
          <Form.Item name="number" label={t('masterData.contractsTab.modal.fields.number')}>
            <Input />
          </Form.Item>
          <Form.Item
            name="date"
            label={t('masterData.contractsTab.modal.fields.date')}
            rules={[
              {
                validator: (_, value: string) => {
                  if (!value || value.trim() === '') {
                    return Promise.resolve()
                  }
                  return /^\d{4}-\d{2}-\d{2}$/.test(value.trim())
                    ? Promise.resolve()
                    : Promise.reject(new Error(t('masterData.contractsTab.messages.expectedDateFormat')))
                },
              },
            ]}
          >
            <Input placeholder={t('masterData.contractsTab.modal.datePlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
