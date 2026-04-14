import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, App as AntApp, Button, Descriptions, Form, Input, Select, Space, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  getMasterDataGlAccountSet,
  listMasterDataGlAccounts,
  listMasterDataGlAccountSets,
  publishMasterDataGlAccountSet,
  type PoolMasterDataRegistryEntry,
  type PoolMasterGLAccount,
  type PoolMasterGLAccountSet,
  type PoolMasterGLAccountSetMember,
  type PoolMasterGLAccountSetRevision,
  type PoolMasterGLAccountSetSummary,
  upsertMasterDataGlAccountSet,
} from '../../../api/intercompanyPools'
import {
  EntityDetails,
  EntityTable,
  JsonBlock,
  ModalFormShell,
  StatusBadge,
} from '../../../components/platform'
import { usePoolsTranslation } from '../../../i18n'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import { findRegistryEntryByEntityType, getRegistryEntryLabel } from './registry'

const { Text } = Typography

type GLAccountSetFormValues = {
  canonical_id: string
  name: string
  description: string
  chart_identity: string
  config_name: string
  config_version: string
  member_canonical_ids: string[]
}

type GLAccountSetsTabProps = {
  registryEntries: PoolMasterDataRegistryEntry[]
}

type CompatibilitySummary = {
  status: 'compatible' | 'incompatible'
  label: string
  detail: string
}

const buildCompatibilityClass = (
  source: Pick<PoolMasterGLAccountSet | PoolMasterGLAccountSetSummary, 'chart_identity' | 'config_name' | 'config_version'>
) => `${source.chart_identity} · ${source.config_name} · ${source.config_version}`

const summarizeMembersCompatibility = (
  expected: Pick<PoolMasterGLAccountSet, 'chart_identity' | 'config_name' | 'config_version'>,
  members: PoolMasterGLAccountSetMember[],
  t: (key: string, options?: Record<string, unknown>) => string,
): CompatibilitySummary => {
  const mismatchedMembers = members.filter((member) => (
    String(member.chart_identity || '').trim() !== String(expected.chart_identity || '').trim()
    || String(member.config_name || '').trim() !== String(expected.config_name || '').trim()
    || String(member.config_version || '').trim() !== String(expected.config_version || '').trim()
  ))
  if (mismatchedMembers.length === 0) {
    return {
      status: 'compatible',
      label: t('masterData.glAccountSetsTab.compatibility.aligned'),
      detail: members.length > 0
        ? t('masterData.glAccountSetsTab.compatibility.alignedDetail', { count: members.length })
        : t('masterData.glAccountSetsTab.compatibility.noMembers'),
    }
  }
  return {
    status: 'incompatible',
    label: t('masterData.glAccountSetsTab.compatibility.gap'),
    detail: t('masterData.glAccountSetsTab.compatibility.gapDetail', { count: mismatchedMembers.length }),
  }
}

export function GLAccountSetsTab({ registryEntries }: GLAccountSetsTabProps) {
  const { message } = AntApp.useApp()
  const { t } = usePoolsTranslation()
  const [rows, setRows] = useState<PoolMasterGLAccountSetSummary[]>([])
  const [selectedSetId, setSelectedSetId] = useState<string | null>(null)
  const [selectedSet, setSelectedSet] = useState<PoolMasterGLAccountSet | null>(null)
  const [glAccounts, setGlAccounts] = useState<PoolMasterGLAccount[]>([])
  const [loadingRows, setLoadingRows] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [loadingAccounts, setLoadingAccounts] = useState(false)
  const [loadingEditor, setLoadingEditor] = useState(false)
  const [query, setQuery] = useState('')
  const [chartIdentityFilter, setChartIdentityFilter] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingSetId, setEditingSetId] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isPublishing, setIsPublishing] = useState(false)
  const [form] = Form.useForm<GLAccountSetFormValues>()

  const registryEntry = useMemo(
    () => findRegistryEntryByEntityType(registryEntries, 'gl_account_set'),
    [registryEntries]
  )

  const watchedChartIdentity = Form.useWatch('chart_identity', form)
  const watchedConfigName = Form.useWatch('config_name', form)
  const watchedConfigVersion = Form.useWatch('config_version', form)

  const loadRows = useCallback(async () => {
    setLoadingRows(true)
    try {
      const response = await listMasterDataGlAccountSets({
        query: query.trim() || undefined,
        chart_identity: chartIdentityFilter.trim() || undefined,
        limit: 100,
        offset: 0,
      })
      setRows(response.gl_account_sets)
      setSelectedSetId((current) => {
        if (current && response.gl_account_sets.some((item) => item.gl_account_set_id === current)) {
          return current
        }
        return response.gl_account_sets[0]?.gl_account_set_id ?? null
      })
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.glAccountSetsTab.messages.failedToLoadList'))
      message.error(resolved.message)
    } finally {
      setLoadingRows(false)
    }
  }, [chartIdentityFilter, message, query, t])

  const loadSelectedSet = useCallback(async (glAccountSetId: string) => {
    setLoadingDetail(true)
    try {
      const response = await getMasterDataGlAccountSet(glAccountSetId)
      setSelectedSet(response.gl_account_set)
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.glAccountSetsTab.messages.failedToLoadDetail'))
      setSelectedSet(null)
      message.error(resolved.message)
    } finally {
      setLoadingDetail(false)
    }
  }, [message, t])

  const loadGlAccounts = useCallback(async () => {
    setLoadingAccounts(true)
    try {
      const response = await listMasterDataGlAccounts({ limit: 200, offset: 0 })
      setGlAccounts(response.gl_accounts)
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.glAccountSetsTab.messages.failedToLoadAccounts'))
      message.error(resolved.message)
    } finally {
      setLoadingAccounts(false)
    }
  }, [message, t])

  useEffect(() => {
    void loadRows()
    void loadGlAccounts()
  }, [loadGlAccounts, loadRows])

  useEffect(() => {
    if (!selectedSetId) {
      setSelectedSet(null)
      return
    }
    void loadSelectedSet(selectedSetId)
  }, [loadSelectedSet, selectedSetId])

  const hydrateFormFromDetail = (detail: PoolMasterGLAccountSet) => {
    form.setFieldsValue({
      canonical_id: detail.canonical_id,
      name: detail.name,
      description: detail.description || '',
      chart_identity: detail.chart_identity,
      config_name: detail.config_name,
      config_version: detail.config_version,
      member_canonical_ids: detail.draft_members.map((member) => member.canonical_id),
    })
  }

  const openCreateModal = () => {
    setEditingSetId(null)
    form.setFieldsValue({
      canonical_id: '',
      name: '',
      description: '',
      chart_identity: '',
      config_name: '',
      config_version: '',
      member_canonical_ids: [],
    })
    setIsModalOpen(true)
  }

  const openEditModal = async (glAccountSetId: string) => {
    setLoadingEditor(true)
    try {
      const detail = selectedSet?.gl_account_set_id === glAccountSetId
        ? selectedSet
        : (await getMasterDataGlAccountSet(glAccountSetId)).gl_account_set
      setEditingSetId(glAccountSetId)
      hydrateFormFromDetail(detail)
      setIsModalOpen(true)
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.glAccountSetsTab.messages.failedToPrepareForm'))
      message.error(resolved.message)
    } finally {
      setLoadingEditor(false)
    }
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setIsSaving(true)
    try {
      const response = await upsertMasterDataGlAccountSet({
        gl_account_set_id: editingSetId || undefined,
        canonical_id: values.canonical_id.trim(),
        name: values.name.trim(),
        description: values.description.trim(),
        chart_identity: values.chart_identity.trim(),
        config_name: values.config_name.trim(),
        config_version: values.config_version.trim(),
        members: values.member_canonical_ids.map((canonicalId) => ({
          canonical_id: canonicalId,
        })),
      })
      setIsModalOpen(false)
      setSelectedSetId(response.gl_account_set.gl_account_set_id)
      setSelectedSet(response.gl_account_set)
      message.success(
        editingSetId
          ? t('masterData.glAccountSetsTab.messages.draftUpdated')
          : t('masterData.glAccountSetsTab.messages.created')
      )
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.glAccountSetsTab.messages.failedToSave'))
      if (Object.keys(resolved.fieldErrors).length > 0) {
        form.setFields(
          Object.entries(resolved.fieldErrors).map(([name, errors]) => ({ name, errors })) as never
        )
      }
      message.error(resolved.message)
    } finally {
      setIsSaving(false)
    }
  }

  const handlePublish = async () => {
    if (!selectedSet) {
      return
    }
    setIsPublishing(true)
    try {
      const response = await publishMasterDataGlAccountSet(selectedSet.gl_account_set_id)
      setSelectedSet(response.gl_account_set)
      message.success(t('masterData.glAccountSetsTab.messages.publishedRevision'))
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.glAccountSetsTab.messages.failedToPublish'))
      message.error(resolved.message)
    } finally {
      setIsPublishing(false)
    }
  }

  const draftCompatibility = selectedSet
    ? summarizeMembersCompatibility(selectedSet, selectedSet.draft_members, t)
    : null

  const memberOptions = glAccounts
    .filter((account) => {
      const chartIdentity = String(watchedChartIdentity || '').trim()
      const configName = String(watchedConfigName || '').trim()
      const configVersion = String(watchedConfigVersion || '').trim()
      if (chartIdentity && account.chart_identity !== chartIdentity) {
        return false
      }
      if (configName && account.config_name !== configName) {
        return false
      }
      if (configVersion && account.config_version !== configVersion) {
        return false
      }
      return true
    })
    .map((account) => ({
      value: account.canonical_id,
      label: `${account.canonical_id} - ${account.name} (${account.code} · ${account.chart_identity})`,
    }))

  const memberColumns: ColumnsType<PoolMasterGLAccountSetMember> = useMemo(() => [
    {
      title: t('masterData.glAccountSetsTab.columns.canonicalId'),
      dataIndex: 'canonical_id',
      key: 'canonical_id',
      width: 180,
    },
    { title: t('masterData.glAccountSetsTab.columns.code'), dataIndex: 'code', key: 'code', width: 120 },
    { title: t('masterData.glAccountSetsTab.columns.name'), dataIndex: 'name', key: 'name', width: 220 },
    {
      title: t('masterData.glAccountSetsTab.columns.chartIdentity'),
      dataIndex: 'chart_identity',
      key: 'chart_identity',
      width: 220,
    },
    {
      title: t('masterData.glAccountSetsTab.columns.config'),
      key: 'config',
      width: 220,
      render: (_, row) => `${row.config_name || '—'} · ${row.config_version || '—'}`,
    },
  ], [t])

  const revisionColumns: ColumnsType<PoolMasterGLAccountSetRevision> = useMemo(() => [
    { title: t('masterData.glAccountSetsTab.columns.revision'), dataIndex: 'revision_number', key: 'revision_number', width: 100 },
    { title: t('masterData.glAccountSetsTab.columns.name'), dataIndex: 'name', key: 'name', width: 220 },
    {
      title: t('masterData.glAccountSetsTab.columns.members'),
      key: 'members',
      width: 120,
      render: (_, row) => row.members.length,
    },
    {
      title: t('masterData.glAccountSetsTab.columns.contract'),
      dataIndex: 'contract_version',
      key: 'contract_version',
      width: 180,
    },
    {
      title: t('masterData.glAccountSetsTab.columns.created'),
      dataIndex: 'created_at',
      key: 'created_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
  ], [t])

  const columns: ColumnsType<PoolMasterGLAccountSetSummary> = useMemo(() => [
    {
      title: t('masterData.glAccountSetsTab.columns.canonicalId'),
      dataIndex: 'canonical_id',
      key: 'canonical_id',
      width: 180,
    },
    { title: t('masterData.glAccountSetsTab.columns.name'), dataIndex: 'name', key: 'name', width: 220 },
    {
      title: t('masterData.glAccountSetsTab.columns.chartIdentity'),
      dataIndex: 'chart_identity',
      key: 'chart_identity',
      width: 220,
    },
    {
      title: t('masterData.glAccountSetsTab.columns.compatibilityClass'),
      key: 'compatibility',
      width: 260,
      render: (_, row) => (
        <Space direction="vertical" size={2}>
          <StatusBadge status="compatible" label={t('masterData.glAccountSetsTab.columns.profileClass')} />
          <Text type="secondary">{`${row.config_name} · ${row.config_version}`}</Text>
        </Space>
      ),
    },
    {
      title: t('masterData.glAccountSetsTab.columns.draftMembers'),
      dataIndex: 'draft_members_count',
      key: 'draft_members_count',
      width: 120,
    },
    {
      title: t('masterData.glAccountSetsTab.columns.revisionState'),
      key: 'revision_state',
      width: 200,
      render: (_, row) => (
        row.published_revision_number
          ? <StatusBadge status="published" label={t('masterData.glAccountSetsTab.details.publishedRevisionLabel', { revision: row.published_revision_number })} />
          : <StatusBadge status="warning" label={t('masterData.glAccountSetsTab.details.draftOnly')} />
      ),
    },
    {
      title: t('masterData.glAccountSetsTab.columns.actions'),
      key: 'actions',
      width: 160,
      render: (_, row) => (
        <Space>
          <Button size="small" onClick={() => setSelectedSetId(row.gl_account_set_id)}>{t('masterData.glAccountSetsTab.actions.inspect')}</Button>
          <Button size="small" onClick={() => void openEditModal(row.gl_account_set_id)}>{t('masterData.glAccountSetsTab.actions.edit')}</Button>
        </Space>
      ),
    },
  ], [openEditModal, t])

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message={t('masterData.glAccountSetsTab.alerts.capabilityState', {
          label: getRegistryEntryLabel(registryEntry) || 'GL Account Set',
        })}
        description={(
          <Space direction="vertical" size={4}>
            <Text>{t('masterData.glAccountSetsTab.alerts.capabilityDescription')}</Text>
            <Space wrap>
              <StatusBadge status="warning" label={t('masterData.glAccountSetsTab.alerts.profileStateOnly')} />
              <StatusBadge
                status={registryEntry?.capabilities.direct_binding ? 'incompatible' : 'compatible'}
                label={registryEntry?.capabilities.direct_binding
                  ? t('masterData.glAccountSetsTab.alerts.unexpectedDirectBinding')
                  : t('masterData.glAccountSetsTab.alerts.noDirectBinding')}
              />
              <StatusBadge
                status={registryEntry?.capabilities.sync_outbound ? 'incompatible' : 'compatible'}
                label={registryEntry?.capabilities.sync_outbound
                  ? t('masterData.glAccountSetsTab.alerts.unexpectedSyncMutation')
                  : t('masterData.glAccountSetsTab.alerts.nonActionableSync')}
              />
            </Space>
          </Space>
        )}
      />

      <EntityTable
        title={t('masterData.glAccountSetsTab.table.title')}
        dataSource={rows}
        columns={columns}
        rowKey="gl_account_set_id"
        loading={loadingRows || loadingEditor}
        emptyDescription={t('masterData.glAccountSetsTab.table.emptyDescription')}
        toolbar={(
          <Space wrap>
            <Input
              allowClear
              placeholder={t('masterData.glAccountSetsTab.table.searchPlaceholder')}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onPressEnter={() => void loadRows()}
              style={{ width: 280 }}
            />
            <Input
              allowClear
              placeholder={t('masterData.glAccountSetsTab.table.chartIdentityFilter')}
              value={chartIdentityFilter}
              onChange={(event) => setChartIdentityFilter(event.target.value)}
              style={{ width: 220 }}
            />
            <Button onClick={() => void loadRows()} loading={loadingRows}>{t('catalog.actions.refresh')}</Button>
            <Button type="primary" onClick={openCreateModal}>{t('masterData.glAccountSetsTab.actions.add')}</Button>
          </Space>
        )}
        onRow={(row) => ({
          onClick: () => setSelectedSetId(row.gl_account_set_id),
        })}
        rowClassName={(row) => (row.gl_account_set_id === selectedSetId ? 'ant-table-row-selected' : '')}
      />

      <EntityDetails
        title={selectedSet ? selectedSet.name : t('masterData.glAccountSetsTab.details.title')}
        empty={!selectedSet}
        emptyDescription={t('masterData.glAccountSetsTab.details.emptyDescription')}
        loading={loadingDetail}
        extra={selectedSet ? (
          <Space wrap>
            {selectedSet.published_revision
              ? <StatusBadge status="published" label={t('masterData.glAccountSetsTab.details.publishedRevisionLabel', { revision: selectedSet.published_revision.revision_number })} />
              : <StatusBadge status="warning" label={t('masterData.glAccountSetsTab.details.draftOnly')} />}
            <Button onClick={() => void openEditModal(selectedSet.gl_account_set_id)}>{t('masterData.glAccountSetsTab.actions.editDraft')}</Button>
            <Button type="primary" onClick={() => void handlePublish()} loading={isPublishing}>
              {t('masterData.glAccountSetsTab.actions.publishRevision')}
            </Button>
          </Space>
        ) : undefined}
      >
        {selectedSet ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label={t('masterData.glAccountSetsTab.columns.canonicalId')}>{selectedSet.canonical_id}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountSetsTab.columns.name')}>{selectedSet.name}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountSetsTab.columns.chartIdentity')}>{selectedSet.chart_identity}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountSetsTab.columns.compatibilityClass')}>{buildCompatibilityClass(selectedSet)}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountSetsTab.details.configName')}>{selectedSet.config_name}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountSetsTab.details.configVersion')}>{selectedSet.config_version}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountSetsTab.columns.draftMembers')}>{selectedSet.draft_members.length}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountSetsTab.details.selectedId')}>
                <Text code data-testid="pool-master-data-gl-account-set-selected-id">
                  {selectedSet.gl_account_set_id}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountSetsTab.details.revisionState')} span={2}>
                <Space wrap>
                  {selectedSet.published_revision
                    ? <StatusBadge status="published" label={t('masterData.glAccountSetsTab.details.publishedRevisionLabel', { revision: selectedSet.published_revision.revision_number })} />
                    : <StatusBadge status="warning" label={t('masterData.glAccountSetsTab.details.draftOnly')} />}
                  <StatusBadge
                    status={draftCompatibility?.status ?? 'warning'}
                    label={draftCompatibility?.label ?? t('masterData.glAccountSetsTab.details.compatibilityPending')}
                  />
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountSetsTab.details.publishedRevision')} span={2}>
                {selectedSet.published_revision
                  ? `r${selectedSet.published_revision.revision_number} · ${formatDateTime(selectedSet.published_revision.created_at)}`
                  : t('masterData.glAccountSetsTab.details.notPublishedYet')}
              </Descriptions.Item>
            </Descriptions>

            {draftCompatibility ? (
              <Alert
                type={draftCompatibility.status === 'compatible' ? 'success' : 'warning'}
                showIcon
                message={draftCompatibility.label}
                description={draftCompatibility.detail}
              />
            ) : null}

            <div>
              <Text strong>{t('masterData.glAccountSetsTab.details.draftMembers')}</Text>
              <div style={{ width: '100%', overflowX: 'auto', marginTop: 8 }}>
                <Table
                  rowKey="gl_account_id"
                  columns={memberColumns}
                  dataSource={selectedSet.draft_members}
                  pagination={false}
                  size="small"
                  scroll={{ x: 'max-content' }}
                />
              </div>
            </div>

            {selectedSet.published_revision ? (
              <div>
                <Text strong>{t('masterData.glAccountSetsTab.details.publishedRevisionMembers')}</Text>
                <div style={{ width: '100%', overflowX: 'auto', marginTop: 8 }}>
                  <Table
                    rowKey="gl_account_id"
                    columns={memberColumns}
                    dataSource={selectedSet.published_revision.members}
                    pagination={false}
                    size="small"
                    scroll={{ x: 'max-content' }}
                  />
                </div>
              </div>
            ) : null}

            <div>
              <Text strong>{t('masterData.glAccountSetsTab.details.revisionHistory')}</Text>
              <div style={{ width: '100%', overflowX: 'auto', marginTop: 8 }}>
                <Table
                  rowKey="gl_account_set_revision_id"
                  columns={revisionColumns}
                  dataSource={selectedSet.revisions}
                  pagination={false}
                  size="small"
                  scroll={{ x: 'max-content' }}
                />
              </div>
            </div>

            <JsonBlock title={t('masterData.glAccountSetsTab.details.draftMetadata')} value={selectedSet.metadata ?? {}} />
          </Space>
        ) : null}
      </EntityDetails>

      <ModalFormShell
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={() => void handleSubmit()}
        title={editingSetId ? t('masterData.glAccountSetsTab.modal.editTitle') : t('masterData.glAccountSetsTab.modal.createTitle')}
        subtitle={t('masterData.glAccountSetsTab.modal.subtitle')}
        submitText={editingSetId ? t('masterData.glAccountSetsTab.modal.saveDraft') : t('masterData.glAccountSetsTab.modal.createDraft')}
        confirmLoading={isSaving}
        width={840}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_id" label={t('masterData.glAccountSetsTab.modal.fields.canonicalId')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name" label={t('masterData.glAccountSetsTab.modal.fields.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label={t('masterData.glAccountSetsTab.modal.fields.description')}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="chart_identity" label={t('masterData.glAccountSetsTab.modal.fields.chartIdentity')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="config_name" label={t('masterData.glAccountSetsTab.modal.fields.configName')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="config_version" label={t('masterData.glAccountSetsTab.modal.fields.configVersion')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="member_canonical_ids"
            label={t('masterData.glAccountSetsTab.modal.fields.draftMembers')}
            rules={[{
              required: true,
              type: 'array',
              min: 1,
              message: t('masterData.glAccountSetsTab.modal.validation.selectAtLeastOne'),
            }]}
            extra={t('masterData.glAccountSetsTab.modal.memberExtra')}
          >
            <Select
              mode="multiple"
              showSearch
              loading={loadingAccounts}
              options={memberOptions}
              placeholder={t('masterData.glAccountSetsTab.modal.memberPlaceholder')}
            />
          </Form.Item>
        </Form>
      </ModalFormShell>
    </Space>
  )
}
