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
  members: PoolMasterGLAccountSetMember[]
): CompatibilitySummary => {
  const mismatchedMembers = members.filter((member) => (
    String(member.chart_identity || '').trim() !== String(expected.chart_identity || '').trim()
    || String(member.config_name || '').trim() !== String(expected.config_name || '').trim()
    || String(member.config_version || '').trim() !== String(expected.config_version || '').trim()
  ))
  if (mismatchedMembers.length === 0) {
    return {
      status: 'compatible',
      label: 'Compatibility aligned',
      detail: members.length > 0
        ? `All ${members.length} draft member(s) match the profile compatibility class.`
        : 'Draft has no members yet.',
    }
  }
  return {
    status: 'incompatible',
    label: 'Compatibility gap',
    detail: `${mismatchedMembers.length} draft member(s) do not match chart/config compatibility class.`,
  }
}

const memberColumns: ColumnsType<PoolMasterGLAccountSetMember> = [
  { title: 'Canonical ID', dataIndex: 'canonical_id', key: 'canonical_id', width: 180 },
  { title: 'Code', dataIndex: 'code', key: 'code', width: 120 },
  { title: 'Name', dataIndex: 'name', key: 'name', width: 220 },
  { title: 'Chart Identity', dataIndex: 'chart_identity', key: 'chart_identity', width: 220 },
  {
    title: 'Config',
    key: 'config',
    width: 220,
    render: (_, row) => `${row.config_name || '—'} · ${row.config_version || '—'}`,
  },
]

const revisionColumns: ColumnsType<PoolMasterGLAccountSetRevision> = [
  { title: 'Revision', dataIndex: 'revision_number', key: 'revision_number', width: 100 },
  { title: 'Name', dataIndex: 'name', key: 'name', width: 220 },
  {
    title: 'Members',
    key: 'members',
    width: 120,
    render: (_, row) => row.members.length,
  },
  { title: 'Contract', dataIndex: 'contract_version', key: 'contract_version', width: 180 },
  {
    title: 'Created',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 220,
    render: (value: string) => formatDateTime(value),
  },
]

export function GLAccountSetsTab({ registryEntries }: GLAccountSetsTabProps) {
  const { message } = AntApp.useApp()
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
      const resolved = resolveApiError(error, 'Не удалось загрузить GL Account Sets.')
      message.error(resolved.message)
    } finally {
      setLoadingRows(false)
    }
  }, [chartIdentityFilter, message, query])

  const loadSelectedSet = useCallback(async (glAccountSetId: string) => {
    setLoadingDetail(true)
    try {
      const response = await getMasterDataGlAccountSet(glAccountSetId)
      setSelectedSet(response.gl_account_set)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить детали GL Account Set.')
      setSelectedSet(null)
      message.error(resolved.message)
    } finally {
      setLoadingDetail(false)
    }
  }, [message])

  const loadGlAccounts = useCallback(async () => {
    setLoadingAccounts(true)
    try {
      const response = await listMasterDataGlAccounts({ limit: 200, offset: 0 })
      setGlAccounts(response.gl_accounts)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить каталог GL Accounts.')
      message.error(resolved.message)
    } finally {
      setLoadingAccounts(false)
    }
  }, [message])

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
      const resolved = resolveApiError(error, 'Не удалось подготовить форму GL Account Set.')
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
      message.success(editingSetId ? 'GL Account Set draft обновлён.' : 'GL Account Set создан.')
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось сохранить GL Account Set.')
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
      message.success('Опубликована новая immutable revision.')
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось опубликовать GL Account Set revision.')
      message.error(resolved.message)
    } finally {
      setIsPublishing(false)
    }
  }

  const draftCompatibility = selectedSet
    ? summarizeMembersCompatibility(selectedSet, selectedSet.draft_members)
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

  const columns: ColumnsType<PoolMasterGLAccountSetSummary> = [
    { title: 'Canonical ID', dataIndex: 'canonical_id', key: 'canonical_id', width: 180 },
    { title: 'Name', dataIndex: 'name', key: 'name', width: 220 },
    { title: 'Chart Identity', dataIndex: 'chart_identity', key: 'chart_identity', width: 220 },
    {
      title: 'Compatibility Class',
      key: 'compatibility',
      width: 260,
      render: (_, row) => (
        <Space direction="vertical" size={2}>
          <StatusBadge status="compatible" label="Profile class" />
          <Text type="secondary">{`${row.config_name} · ${row.config_version}`}</Text>
        </Space>
      ),
    },
    {
      title: 'Draft Members',
      dataIndex: 'draft_members_count',
      key: 'draft_members_count',
      width: 120,
    },
    {
      title: 'Revision State',
      key: 'revision_state',
      width: 200,
      render: (_, row) => (
        row.published_revision_number
          ? <StatusBadge status="published" label={`Published r${row.published_revision_number}`} />
          : <StatusBadge status="warning" label="Draft only" />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 160,
      render: (_, row) => (
        <Space>
          <Button size="small" onClick={() => setSelectedSetId(row.gl_account_set_id)}>Inspect</Button>
          <Button size="small" onClick={() => void openEditModal(row.gl_account_set_id)}>Edit</Button>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message={`${getRegistryEntryLabel(registryEntry) || 'GL Account Set'} capability state`}
        description={(
          <Space direction="vertical" size={4}>
            <Text>
              This surface is profile-oriented: draft edits, publish actions and revision inspection stay here,
              while direct sync mutations remain intentionally unavailable.
            </Text>
            <Space wrap>
              <StatusBadge status="warning" label="Profile state only" />
              <StatusBadge
                status={registryEntry?.capabilities.direct_binding ? 'incompatible' : 'compatible'}
                label={registryEntry?.capabilities.direct_binding ? 'Unexpected direct binding' : 'No direct binding'}
              />
              <StatusBadge
                status={registryEntry?.capabilities.sync_outbound ? 'incompatible' : 'compatible'}
                label={registryEntry?.capabilities.sync_outbound ? 'Unexpected sync mutation' : 'Non-actionable sync'}
              />
            </Space>
          </Space>
        )}
      />

      <EntityTable
        title="GL Account Sets"
        dataSource={rows}
        columns={columns}
        rowKey="gl_account_set_id"
        loading={loadingRows || loadingEditor}
        emptyDescription="GL Account Sets are not configured yet."
        toolbar={(
          <Space wrap>
            <Input
              allowClear
              placeholder="Search canonical_id / name"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onPressEnter={() => void loadRows()}
              style={{ width: 280 }}
            />
            <Input
              allowClear
              placeholder="Chart identity"
              value={chartIdentityFilter}
              onChange={(event) => setChartIdentityFilter(event.target.value)}
              style={{ width: 220 }}
            />
            <Button onClick={() => void loadRows()} loading={loadingRows}>Refresh</Button>
            <Button type="primary" onClick={openCreateModal}>Add GL Account Set</Button>
          </Space>
        )}
        onRow={(row) => ({
          onClick: () => setSelectedSetId(row.gl_account_set_id),
        })}
        rowClassName={(row) => (row.gl_account_set_id === selectedSetId ? 'ant-table-row-selected' : '')}
      />

      <EntityDetails
        title={selectedSet ? selectedSet.name : 'GL Account Set details'}
        empty={!selectedSet}
        emptyDescription="Select a GL Account Set to inspect draft members, published revision and history."
        loading={loadingDetail}
        extra={selectedSet ? (
          <Space wrap>
            {selectedSet.published_revision
              ? <StatusBadge status="published" label={`Published r${selectedSet.published_revision.revision_number}`} />
              : <StatusBadge status="warning" label="Draft only" />}
            <Button onClick={() => void openEditModal(selectedSet.gl_account_set_id)}>Edit draft</Button>
            <Button type="primary" onClick={() => void handlePublish()} loading={isPublishing}>
              Publish revision
            </Button>
          </Space>
        ) : undefined}
      >
        {selectedSet ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Canonical ID">{selectedSet.canonical_id}</Descriptions.Item>
              <Descriptions.Item label="Name">{selectedSet.name}</Descriptions.Item>
              <Descriptions.Item label="Chart Identity">{selectedSet.chart_identity}</Descriptions.Item>
              <Descriptions.Item label="Compatibility Class">{buildCompatibilityClass(selectedSet)}</Descriptions.Item>
              <Descriptions.Item label="Config Name">{selectedSet.config_name}</Descriptions.Item>
              <Descriptions.Item label="Config Version">{selectedSet.config_version}</Descriptions.Item>
              <Descriptions.Item label="Draft Members">{selectedSet.draft_members.length}</Descriptions.Item>
              <Descriptions.Item label="Selected ID">
                <Text code data-testid="pool-master-data-gl-account-set-selected-id">
                  {selectedSet.gl_account_set_id}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="Revision State" span={2}>
                <Space wrap>
                  {selectedSet.published_revision
                    ? <StatusBadge status="published" label={`Published r${selectedSet.published_revision.revision_number}`} />
                    : <StatusBadge status="warning" label="Draft only" />}
                  <StatusBadge
                    status={draftCompatibility?.status ?? 'warning'}
                    label={draftCompatibility?.label ?? 'Compatibility pending'}
                  />
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="Published Revision" span={2}>
                {selectedSet.published_revision
                  ? `r${selectedSet.published_revision.revision_number} · ${formatDateTime(selectedSet.published_revision.created_at)}`
                  : 'Not published yet'}
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
              <Text strong>Draft Members</Text>
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
                <Text strong>Published Revision Members</Text>
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
              <Text strong>Revision History</Text>
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

            <JsonBlock title="Draft Metadata" value={selectedSet.metadata ?? {}} />
          </Space>
        ) : null}
      </EntityDetails>

      <ModalFormShell
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={() => void handleSubmit()}
        title={editingSetId ? 'Edit GL Account Set draft' : 'Create GL Account Set'}
        subtitle="Draft edits stay mutable until publish creates a new immutable revision."
        submitText={editingSetId ? 'Save draft' : 'Create draft'}
        confirmLoading={isSaving}
        width={840}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_id" label="Canonical ID" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="chart_identity" label="Chart Identity" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="config_name" label="Config Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="config_version" label="Config Version" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="member_canonical_ids"
            label="Draft Members"
            rules={[{ required: true, type: 'array', min: 1, message: 'Select at least one GL Account.' }]}
            extra="Member catalog is filtered by the draft compatibility class as fields are filled."
          >
            <Select
              mode="multiple"
              showSearch
              loading={loadingAccounts}
              options={memberOptions}
              placeholder="Select canonical GL Accounts"
            />
          </Form.Item>
        </Form>
      </ModalFormShell>
    </Space>
  )
}
