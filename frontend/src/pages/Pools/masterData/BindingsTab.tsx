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
  type SimpleDatabaseRef,
} from '../../../api/intercompanyPools'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import {
  findRegistryEntryByEntityType,
  getBindingScopePresentationFields,
  getDefaultDirectBindingEntityType,
  getDirectBindingEntityOptions,
  getRegistryEntityLabel,
  getTokenQualifierOptions,
} from './registry'
import { usePoolsTranslation } from '../../../i18n'

type BindingFormValues = {
  entity_type: string
  canonical_id: string
  database_id: string
  ib_ref_key: string
  ib_catalog_kind: PoolMasterBindingCatalogKind
  owner_counterparty_canonical_id: string
  chart_identity: string
  sync_status: PoolMasterBindingSyncStatus
  fingerprint: string
}

const BINDING_SCOPE_FIELD_COLORS: Record<string, string> = {
  ib_catalog_kind: 'blue',
  owner_counterparty_canonical_id: 'purple',
  chart_identity: 'gold',
}

type BindingsTabProps = {
  registryEntries: PoolMasterDataRegistryEntry[]
}

export function BindingsTab({ registryEntries }: BindingsTabProps) {
  const { message } = AntApp.useApp()
  const { t } = usePoolsTranslation()
  const [rows, setRows] = useState<PoolMasterDataBinding[]>([])
  const [databases, setDatabases] = useState<SimpleDatabaseRef[]>([])
  const [loading, setLoading] = useState(false)
  const [queryCanonicalId, setQueryCanonicalId] = useState('')
  const [entityTypeFilter, setEntityTypeFilter] = useState<string | undefined>(undefined)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingBinding, setEditingBinding] = useState<PoolMasterDataBinding | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [form] = Form.useForm<BindingFormValues>()
  const selectedEntityType = Form.useWatch('entity_type', form)
  const entityTypeOptions = useMemo(
    () => getDirectBindingEntityOptions(registryEntries),
    [registryEntries]
  )
  const defaultEntityType = useMemo(
    () => getDefaultDirectBindingEntityType(registryEntries),
    [registryEntries]
  )
  const bindingScopeFields = useMemo(
    () => getBindingScopePresentationFields(registryEntries, selectedEntityType),
    [registryEntries, selectedEntityType]
  )
  const requiresCatalogKind = bindingScopeFields.includes('ib_catalog_kind')
  const requiresOwnerCounterparty = bindingScopeFields.includes('owner_counterparty_canonical_id')
  const requiresChartIdentity = bindingScopeFields.includes('chart_identity')
  const catalogKindOptions = useMemo(
    () => getTokenQualifierOptions(registryEntries, selectedEntityType),
    [registryEntries, selectedEntityType]
  )
  const syncStatusOptions = useMemo<{ value: PoolMasterBindingSyncStatus; label: string }[]>(
    () => [
      { value: 'resolved', label: t('masterData.bindingsTab.syncStatus.resolved') },
      { value: 'upserted', label: t('masterData.bindingsTab.syncStatus.upserted') },
      { value: 'conflict', label: t('masterData.bindingsTab.syncStatus.conflict') },
    ],
    [t]
  )
  const getBindingScopeFieldLabel = useCallback((field: string): string => {
    if (field === 'ib_catalog_kind') return t('masterData.bindingsTab.scopeFields.ibCatalogKind')
    if (field === 'owner_counterparty_canonical_id') return t('masterData.bindingsTab.scopeFields.ownerCounterpartyCanonicalId')
    if (field === 'chart_identity') return t('masterData.bindingsTab.scopeFields.chartIdentity')
    return field
  }, [t])

  const loadDatabases = useCallback(async () => {
    try {
      const items = await listPoolTargetDatabases()
      setDatabases(items)
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.bindingsTab.messages.failedToLoadDatabases'))
      message.error(resolved.message)
    }
  }, [message, t])

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
      const resolved = resolveApiError(error, t('masterData.bindingsTab.messages.failedToLoadBindings'))
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [entityTypeFilter, message, queryCanonicalId, t])

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
      chart_identity: '',
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
      chart_identity: binding.chart_identity || '',
      sync_status: binding.sync_status,
      fingerprint: binding.fingerprint || '',
    })
    setIsModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    const registryEntry = findRegistryEntryByEntityType(registryEntries, values.entity_type)
    if (!registryEntry) {
      message.error(t('masterData.bindingsTab.messages.missingRegistryContract'))
      return
    }
    const requiredScopeFields = getBindingScopePresentationFields(registryEntries, values.entity_type)
    const missingFieldErrors = requiredScopeFields.flatMap((field) => {
      if (field === 'ib_catalog_kind' && !values.ib_catalog_kind) {
        return [{ name: field, errors: [t('masterData.bindingsTab.messages.requiredByRegistryScope')] }]
      }
      if (field === 'owner_counterparty_canonical_id' && !values.owner_counterparty_canonical_id.trim()) {
        return [{ name: field, errors: [t('masterData.bindingsTab.messages.requiredByRegistryScope')] }]
      }
      if (field === 'chart_identity' && !values.chart_identity.trim()) {
        return [{ name: field, errors: [t('masterData.bindingsTab.messages.requiredByRegistryScope')] }]
      }
      return []
    })

    if (missingFieldErrors.length > 0) {
      form.setFields(missingFieldErrors as never)
      return
    }

    const normalizedCatalogKind: PoolMasterBindingCatalogKind = requiredScopeFields.includes('ib_catalog_kind')
      ? values.ib_catalog_kind
      : ''
    const normalizedOwnerCounterpartyCanonicalId = requiredScopeFields.includes('owner_counterparty_canonical_id')
      ? values.owner_counterparty_canonical_id.trim()
      : ''
    const normalizedChartIdentity = requiredScopeFields.includes('chart_identity')
      ? values.chart_identity.trim()
      : ''

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
        chart_identity: normalizedChartIdentity,
        sync_status: values.sync_status,
        fingerprint: values.fingerprint.trim(),
      })
      setIsModalOpen(false)
      message.success(
        editingBinding
          ? t('masterData.bindingsTab.messages.bindingUpdated')
          : t('masterData.bindingsTab.messages.bindingCreated')
      )
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.bindingsTab.messages.failedToSaveBinding'))
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

  const columns: ColumnsType<PoolMasterDataBinding> = useMemo(() => [
    {
      title: t('masterData.bindingsTab.columns.entityType'),
      dataIndex: 'entity_type',
      key: 'entity_type',
      width: 160,
      render: (value: string) => getRegistryEntityLabel(registryEntries, value),
    },
    {
      title: t('masterData.bindingsTab.columns.canonicalId'),
      dataIndex: 'canonical_id',
      key: 'canonical_id',
      width: 220,
    },
    {
      title: t('masterData.bindingsTab.columns.database'),
      dataIndex: 'database_id',
      key: 'database_id',
      width: 260,
      render: (value: string) => databases.find((item) => item.id === value)?.name || value,
    },
    {
      title: t('masterData.bindingsTab.columns.ibRefKey'),
      dataIndex: 'ib_ref_key',
      key: 'ib_ref_key',
      width: 240,
    },
    {
      title: t('masterData.bindingsTab.columns.scope'),
      key: 'scope',
      width: 320,
      render: (_, row) => {
        const scopeFields = getBindingScopePresentationFields(registryEntries, row.entity_type)
        return (
        <Space>
          {scopeFields.map((field) => {
            const rawValue = field === 'ib_catalog_kind'
              ? row.ib_catalog_kind
              : field === 'owner_counterparty_canonical_id'
                ? row.owner_counterparty_canonical_id
                : field === 'chart_identity'
                  ? row.chart_identity
                  : undefined
            const value = String(rawValue || '').trim()
            if (!value) {
              return null
            }
            return (
              <Tag key={`${row.id}:${field}`} color={BINDING_SCOPE_FIELD_COLORS[field] ?? 'default'}>
                {getBindingScopeFieldLabel(field)}: {value}
              </Tag>
            )
          })}
        </Space>
        )
      },
    },
    {
      title: t('masterData.bindingsTab.columns.syncStatus'),
      dataIndex: 'sync_status',
      key: 'sync_status',
      width: 120,
      render: (value: PoolMasterBindingSyncStatus) => (
        syncStatusOptions.find((option) => option.value === value)?.label ?? value
      ),
    },
    {
      title: t('masterData.bindingsTab.columns.updated'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: t('masterData.bindingsTab.columns.actions'),
      key: 'actions',
      width: 100,
      render: (_, row) => <Button size="small" onClick={() => openEditModal(row)}>{t('common.edit')}</Button>,
    },
  ], [
    databases,
    formatDateTime,
    getBindingScopeFieldLabel,
    openEditModal,
    registryEntries,
    syncStatusOptions,
    t,
  ])

  return (
    <>
      <Card>
        <Space wrap style={{ marginBottom: 16 }}>
          <Input
            allowClear
            placeholder={t('masterData.bindingsTab.filters.canonicalIdPlaceholder')}
            value={queryCanonicalId}
            onChange={(event) => setQueryCanonicalId(event.target.value)}
            style={{ width: 280 }}
          />
          <Select
            allowClear
            placeholder={t('masterData.bindingsTab.filters.entityTypePlaceholder')}
            value={entityTypeFilter}
            options={entityTypeOptions}
            onChange={(value) => setEntityTypeFilter(value)}
            style={{ width: 180 }}
          />
          <Button onClick={() => void loadRows()} loading={loading}>{t('masterData.bindingsTab.actions.refresh')}</Button>
          <Button type="primary" onClick={openCreateModal}>{t('masterData.bindingsTab.actions.addBinding')}</Button>
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
        title={editingBinding ? t('masterData.bindingsTab.modal.editTitle') : t('masterData.bindingsTab.modal.createTitle')}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onOk={() => void handleSubmit()}
        okButtonProps={{ loading: isSaving }}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="entity_type" label={t('masterData.bindingsTab.modal.fields.entityType')} rules={[{ required: true }]}>
            <Select options={entityTypeOptions} />
          </Form.Item>
          <Form.Item name="canonical_id" label={t('masterData.bindingsTab.modal.fields.canonicalId')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="database_id" label={t('masterData.bindingsTab.modal.fields.database')} rules={[{ required: true }]}>
            <Select
              showSearch
              options={databases.map((database) => ({ value: database.id, label: database.name }))}
            />
          </Form.Item>
          <Form.Item name="ib_ref_key" label={t('masterData.bindingsTab.modal.fields.ibRefKey')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          {requiresCatalogKind && (
            <Form.Item name="ib_catalog_kind" label={getBindingScopeFieldLabel('ib_catalog_kind')}>
              <Select allowClear options={catalogKindOptions} />
            </Form.Item>
          )}
          {requiresOwnerCounterparty && (
            <Form.Item
              name="owner_counterparty_canonical_id"
              label={getBindingScopeFieldLabel('owner_counterparty_canonical_id')}
            >
              <Input />
            </Form.Item>
          )}
          {requiresChartIdentity && (
            <Form.Item name="chart_identity" label={getBindingScopeFieldLabel('chart_identity')}>
              <Input />
            </Form.Item>
          )}
          <Form.Item name="sync_status" label={t('masterData.bindingsTab.modal.fields.syncStatus')} rules={[{ required: true }]}>
            <Select options={syncStatusOptions} />
          </Form.Item>
          <Form.Item name="fingerprint" label={t('masterData.bindingsTab.modal.fields.fingerprint')}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
