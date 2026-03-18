import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Descriptions,
  Input,
  Space,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  EntityDetails,
  EntityTable,
  JsonBlock,
  MasterDetailShell,
  PageHeader,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import {
  useBindingProfileDetail,
  useBindingProfiles,
  useCreateBindingProfile,
  useDeactivateBindingProfile,
  useReviseBindingProfile,
} from '../../api/queries/poolBindingProfiles'
import { listOrganizationPools, type OrganizationPool, type PoolWorkflowBinding } from '../../api/intercompanyPools'
import type {
  BindingProfileCreateRequest,
  BindingProfileRevision,
  BindingProfileRevisionCreateRequest,
  BindingProfileSummary,
} from '../../api/poolBindingProfiles'
import { resolveApiError } from './masterData/errorUtils'
import { PoolBindingProfilesEditorModal } from './PoolBindingProfilesEditorModal'
import { POOL_BINDING_PROFILES_ROUTE, POOL_CATALOG_ROUTE } from './routes'

const { Title, Text } = Typography

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

type BindingProfileUsageRow = {
  key: string
  poolId: string
  poolCode: string
  poolName: string
  bindingId: string
  attachmentRevision: number
  bindingProfileRevisionId: string
  bindingProfileRevisionNumber: number | null
  status: string
  scope: string
}

const formatBindingScope = (binding: PoolWorkflowBinding) => {
  const parts = [
    binding.selector?.direction || 'any direction',
    binding.selector?.mode || 'any mode',
  ]
  if (binding.selector?.tags?.length) {
    parts.push(binding.selector.tags.join(', '))
  }
  return parts.join(' · ')
}

export function PoolBindingProfilesPage() {
  const [search, setSearch] = useState('')
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null)
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(false)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isReviseOpen, setIsReviseOpen] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [organizationPools, setOrganizationPools] = useState<OrganizationPool[]>([])
  const [usageLoading, setUsageLoading] = useState(false)
  const [usageError, setUsageError] = useState<string | null>(null)
  const deferredSearch = useDeferredValue(search)

  const bindingProfilesQuery = useBindingProfiles()
  const createBindingProfileMutation = useCreateBindingProfile()
  const reviseBindingProfileMutation = useReviseBindingProfile()
  const deactivateBindingProfileMutation = useDeactivateBindingProfile()

  const bindingProfiles = useMemo(
    () => bindingProfilesQuery.data?.binding_profiles ?? [],
    [bindingProfilesQuery.data?.binding_profiles],
  )
  const normalizedSearch = deferredSearch.trim().toLowerCase()
  const filteredProfiles = bindingProfiles.filter((profile) => {
    if (!normalizedSearch) return true
    return [
      profile.code,
      profile.name,
      profile.description ?? '',
      profile.latest_revision.workflow.workflow_name,
    ]
      .join(' ')
      .toLowerCase()
      .includes(normalizedSearch)
  })

  useEffect(() => {
    if (!bindingProfiles.length) {
      setSelectedProfileId(null)
      return
    }
    if (selectedProfileId && bindingProfiles.some((profile) => profile.binding_profile_id === selectedProfileId)) {
      return
    }
    setSelectedProfileId(bindingProfiles[0].binding_profile_id)
  }, [bindingProfiles, selectedProfileId])

  const selectedProfileQuery = useBindingProfileDetail(selectedProfileId ?? undefined, {
    enabled: Boolean(selectedProfileId),
  })
  const selectedProfile = selectedProfileQuery.data?.binding_profile ?? null
  const selectedProfileUsage = useMemo<BindingProfileUsageRow[]>(() => {
    if (!selectedProfileId) {
      return []
    }
    return organizationPools.flatMap((pool) => (
      (pool.workflow_bindings ?? [])
        .filter((binding) => binding.binding_profile_id === selectedProfileId)
        .map((binding) => ({
          key: `${pool.id}:${binding.binding_id}`,
          poolId: pool.id,
          poolCode: pool.code,
          poolName: pool.name,
          bindingId: binding.binding_id,
          attachmentRevision: binding.revision,
          bindingProfileRevisionId: binding.binding_profile_revision_id,
          bindingProfileRevisionNumber: binding.binding_profile_revision_number ?? null,
          status: binding.status,
          scope: formatBindingScope(binding),
        }))
    ))
  }, [organizationPools, selectedProfileId])
  const selectedProfileUsageRevisionCount = useMemo(
    () => new Set(selectedProfileUsage.map((item) => item.bindingProfileRevisionId)).size,
    [selectedProfileUsage]
  )

  const listColumns: ColumnsType<BindingProfileSummary> = [
    {
      title: 'Code',
      dataIndex: 'code',
      key: 'code',
      render: (value: string) => <Text strong>{value}</Text>,
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => <StatusBadge status={value} />,
    },
    {
      title: 'Latest revision',
      key: 'latest_revision',
      render: (_value, record) => (
        <Text>{`r${record.latest_revision_number} · ${record.latest_revision.workflow.workflow_name}`}</Text>
      ),
    },
  ]

  const revisionColumns: ColumnsType<BindingProfileRevision> = [
    {
      title: 'Revision',
      dataIndex: 'revision_number',
      key: 'revision_number',
      render: (value: number) => `r${value}`,
    },
    {
      title: 'Workflow',
      key: 'workflow',
      render: (_value, record) => (
        <Text>{`${record.workflow.workflow_name} · rev ${record.workflow.workflow_revision}`}</Text>
      ),
    },
    {
      title: 'Opaque pin',
      dataIndex: 'binding_profile_revision_id',
      key: 'binding_profile_revision_id',
    },
    {
      title: 'Created at',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => formatDateTime(value),
    },
  ]
  const usageColumns: ColumnsType<BindingProfileUsageRow> = [
    {
      title: 'Pool',
      key: 'pool',
      render: (_value, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.poolCode}</Text>
          <Text type="secondary">{record.poolName}</Text>
        </Space>
      ),
    },
    {
      title: 'Binding',
      dataIndex: 'bindingId',
      key: 'bindingId',
      render: (value: string) => <Text code>{value}</Text>,
    },
    {
      title: 'Pinned revision',
      key: 'bindingProfileRevisionNumber',
      render: (_value, record) => (
        <Text>{record.bindingProfileRevisionNumber != null ? `r${record.bindingProfileRevisionNumber}` : record.bindingProfileRevisionId}</Text>
      ),
    },
    {
      title: 'Attachment rev',
      dataIndex: 'attachmentRevision',
      key: 'attachmentRevision',
      render: (value: number) => `r${value}`,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => <StatusBadge status={value} />,
    },
    {
      title: 'Scope',
      dataIndex: 'scope',
      key: 'scope',
    },
    {
      title: 'Action',
      key: 'action',
      render: (_value, record) => (
        <Button
          size="small"
          href={`${POOL_CATALOG_ROUTE}?pool_id=${encodeURIComponent(record.poolId)}&tab=bindings`}
        >
          Open pool attachment
        </Button>
      ),
    },
  ]

  const handleCreateProfile = async (request: BindingProfileCreateRequest | BindingProfileRevisionCreateRequest) => {
    const response = await createBindingProfileMutation.mutateAsync(request as BindingProfileCreateRequest)
    const created = response.binding_profile
    setActionError(null)
    setSelectedProfileId(created.binding_profile_id)
    setIsDetailDrawerOpen(true)
  }

  const handleReviseProfile = async (request: BindingProfileCreateRequest | BindingProfileRevisionCreateRequest) => {
    if (!selectedProfile) return
    await reviseBindingProfileMutation.mutateAsync({
      bindingProfileId: selectedProfile.binding_profile_id,
      request: request as BindingProfileRevisionCreateRequest,
    })
    setActionError(null)
  }

  const handleDeactivateProfile = async () => {
    if (!selectedProfile) return
    try {
      const response = await deactivateBindingProfileMutation.mutateAsync(selectedProfile.binding_profile_id)
      setActionError(null)
      setSelectedProfileId(response.binding_profile.binding_profile_id)
      setIsDetailDrawerOpen(true)
    } catch (error) {
      const resolved = resolveApiError(error, 'Failed to deactivate binding profile.')
      setActionError(resolved.message)
    }
  }

  const listError = bindingProfilesQuery.isError
    ? resolveApiError(bindingProfilesQuery.error, 'Failed to load binding profiles.').message
    : null
  const detailError = selectedProfileQuery.isError
    ? resolveApiError(selectedProfileQuery.error, 'Failed to load binding profile detail.').message
    : null

  const handleSelectProfile = (profileId: string) => {
    setSelectedProfileId(profileId)
    setIsDetailDrawerOpen(true)
  }

  useEffect(() => {
    let isCancelled = false
    setUsageLoading(true)
    setUsageError(null)

    void listOrganizationPools()
      .then((data) => {
        if (isCancelled) {
          return
        }
        setOrganizationPools(data)
      })
      .catch(() => {
        if (isCancelled) {
          return
        }
        setUsageError('Failed to load pool attachment usage.')
      })
      .finally(() => {
        if (!isCancelled) {
          setUsageLoading(false)
        }
      })

    return () => {
      isCancelled = true
    }
  }, [])

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="Binding Profiles"
          subtitle={(
            <>
              Primary authoring catalog for reusable workflow/slot logic. Pool-local attachments remain in
              {' '}
              {POOL_CATALOG_ROUTE}
              .
            </>
          )}
          actions={(
            <Button type="primary" onClick={() => setIsCreateOpen(true)}>
              Create profile
            </Button>
          )}
        />
      )}
    >

      <Alert
        type="info"
        showIcon
        message="Dedicated route"
        description={(
          <Space direction="vertical" size={8}>
            <Text>
              Reusable profile authoring is isolated on
              {' '}
              <Text code>{POOL_BINDING_PROFILES_ROUTE}</Text>
              . Pool operators attach existing revisions from
              {' '}
              <Text code>{POOL_CATALOG_ROUTE}</Text>
              .
            </Text>
            <Space wrap>
              <Button href={POOL_CATALOG_ROUTE}>Open attachment workspace</Button>
            </Space>
          </Space>
        )}
      />

      {actionError ? (
        <Alert type="error" showIcon message={actionError} />
      ) : null}

      <MasterDetailShell
        detailOpen={isDetailDrawerOpen}
        onCloseDetail={() => setIsDetailDrawerOpen(false)}
        detailDrawerTitle={selectedProfile?.name || 'Profile detail'}
        list={(
          <EntityTable
            title="Catalog"
            extra={(
              <Input
                allowClear
                placeholder="Search code, name, workflow"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                style={{ width: 240 }}
              />
            )}
            error={listError}
            loading={bindingProfilesQuery.isLoading}
            emptyDescription="No binding profiles found."
            dataSource={filteredProfiles}
            columns={listColumns}
            rowKey="binding_profile_id"
            onRow={(record) => ({
              onClick: () => handleSelectProfile(record.binding_profile_id),
              style: { cursor: 'pointer' },
            })}
            rowClassName={(record) => (
              record.binding_profile_id === selectedProfileId ? 'ant-table-row-selected' : ''
            )}
          />
        )}
        detail={(
          <EntityDetails
            title="Profile detail"
            extra={(
              <Space>
                <Button
                  onClick={() => setIsReviseOpen(true)}
                  disabled={!selectedProfile || selectedProfile.status === 'deactivated'}
                >
                  Publish new revision
                </Button>
                <Button
                  danger
                  onClick={() => { void handleDeactivateProfile() }}
                  disabled={!selectedProfile || selectedProfile.status === 'deactivated'}
                  loading={deactivateBindingProfileMutation.isPending}
                >
                  Deactivate profile
                </Button>
              </Space>
            )}
            error={detailError}
            loading={selectedProfileQuery.isLoading}
            empty={!selectedProfileId || (!selectedProfile && !selectedProfileQuery.isLoading)}
            emptyDescription="Select a profile from the catalog."
          >
            {selectedProfile ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label="Code">
                    <Text strong data-testid="pool-binding-profiles-selected-code">
                      {selectedProfile.code}
                    </Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Name">{selectedProfile.name}</Descriptions.Item>
                  <Descriptions.Item label="Status">
                    <span data-testid="pool-binding-profiles-status">
                      <StatusBadge status={selectedProfile.status} />
                    </span>
                  </Descriptions.Item>
                  <Descriptions.Item label="Latest immutable revision">
                    <Text data-testid="pool-binding-profiles-latest-revision-id">
                      {selectedProfile.latest_revision.binding_profile_revision_id}
                    </Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Latest revision number">
                    {`r${selectedProfile.latest_revision_number}`}
                  </Descriptions.Item>
                  <Descriptions.Item label="Description">
                    {selectedProfile.description || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Updated at">
                    {formatDateTime(selectedProfile.updated_at)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Deactivated at">
                    {formatDateTime(selectedProfile.deactivated_at)}
                  </Descriptions.Item>
                </Descriptions>

                {selectedProfile.status === 'deactivated' ? (
                  <Alert
                    type="warning"
                    showIcon
                    message="Deactivated profiles remain readable for pinned attachments, but cannot publish new revisions."
                  />
                ) : null}

                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Title level={5} style={{ margin: 0 }}>
                    Latest revision payload
                  </Title>
                  <Descriptions bordered size="small" column={1}>
                    <Descriptions.Item label="Workflow">
                      {`${selectedProfile.latest_revision.workflow.workflow_name} · ${selectedProfile.latest_revision.workflow.workflow_definition_key}`}
                    </Descriptions.Item>
                    <Descriptions.Item label="Workflow pin">
                      {`${selectedProfile.latest_revision.workflow.workflow_revision_id} · rev ${selectedProfile.latest_revision.workflow.workflow_revision}`}
                    </Descriptions.Item>
                  </Descriptions>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                      gap: 16,
                    }}
                  >
                    <JsonBlock title="Decision refs" value={selectedProfile.latest_revision.decisions} />
                    <JsonBlock title="Parameters" value={selectedProfile.latest_revision.parameters} />
                    <JsonBlock title="Role mapping" value={selectedProfile.latest_revision.role_mapping} />
                    <JsonBlock title="Revision metadata" value={selectedProfile.latest_revision.metadata} />
                  </div>
                </Space>

                <EntityTable
                  title="Revision history"
                  rowKey="binding_profile_revision_id"
                  columns={revisionColumns}
                  dataSource={selectedProfile.revisions}
                />

                <EntityTable
                  title="Pool attachment usage"
                  error={usageError}
                  loading={usageLoading}
                  emptyDescription="No pool attachments are pinned on this profile yet."
                  dataSource={selectedProfileUsage}
                  columns={usageColumns}
                  rowKey="key"
                  toolbar={(
                    <Space size={16} style={{ marginBottom: 16 }}>
                      <Text>
                        Attachments:
                        {' '}
                        <Text strong data-testid="pool-binding-profiles-usage-total">{selectedProfileUsage.length}</Text>
                      </Text>
                      <Text>
                        Revisions in use:
                        {' '}
                        <Text strong data-testid="pool-binding-profiles-usage-revisions">{selectedProfileUsageRevisionCount}</Text>
                      </Text>
                    </Space>
                  )}
                />
              </Space>
            ) : null}
          </EntityDetails>
        )}
      />

      <PoolBindingProfilesEditorModal
        open={isCreateOpen}
        mode="create"
        onCancel={() => setIsCreateOpen(false)}
        onSubmit={async (request) => {
          await handleCreateProfile(request)
          setIsCreateOpen(false)
        }}
      />

      <PoolBindingProfilesEditorModal
        open={isReviseOpen}
        mode="revise"
        profile={selectedProfile}
        onCancel={() => setIsReviseOpen(false)}
        onSubmit={async (request) => {
          await handleReviseProfile(request)
          setIsReviseOpen(false)
        }}
      />
    </WorkspacePage>
  )
}
