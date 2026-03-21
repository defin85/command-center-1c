import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Collapse,
  Descriptions,
  Grid,
  Input,
  Space,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate, useSearchParams } from 'react-router-dom'

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
const { useBreakpoint } = Grid

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

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

const filterBindingProfiles = (profiles: BindingProfileSummary[], searchTerm: string) => {
  const normalizedSearch = searchTerm.trim().toLowerCase()

  if (!normalizedSearch) {
    return profiles
  }

  return profiles.filter((profile) => (
    [
      profile.code,
      profile.name,
      profile.description ?? '',
      profile.latest_revision.workflow.workflow_name,
    ]
      .join(' ')
      .toLowerCase()
      .includes(normalizedSearch)
  ))
}

export function PoolBindingProfilesPage() {
  const screens = useBreakpoint()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const searchFromUrl = searchParams.get('q') ?? ''
  const selectedProfileFromUrl = normalizeRouteParam(searchParams.get('profile'))
  const detailOpenFromUrl = searchParams.get('detail') === '1'
  const profileRouteSyncInitializedRef = useRef(false)
  const [search, setSearch] = useState(searchFromUrl)
  const [selectedProfileId, setSelectedProfileId] = useState<string | null | undefined>(
    () => selectedProfileFromUrl ?? undefined
  )
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(detailOpenFromUrl)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isReviseOpen, setIsReviseOpen] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [organizationPools, setOrganizationPools] = useState<OrganizationPool[]>([])
  const [isUsageRequested, setIsUsageRequested] = useState(false)
  const [usageLoading, setUsageLoading] = useState(false)
  const [usageError, setUsageError] = useState<string | null>(null)
  const deferredSearch = useDeferredValue(search)

  const bindingProfilesQuery = useBindingProfiles()
  const createBindingProfileMutation = useCreateBindingProfile()
  const reviseBindingProfileMutation = useReviseBindingProfile()
  const deactivateBindingProfileMutation = useDeactivateBindingProfile()

  useEffect(() => {
    setSearch((current) => (current === searchFromUrl ? current : searchFromUrl))
  }, [searchFromUrl])

  useEffect(() => {
    setSelectedProfileId((current) => {
      if (selectedProfileFromUrl) {
        return current === selectedProfileFromUrl ? current : selectedProfileFromUrl
      }

      if (!profileRouteSyncInitializedRef.current && current === undefined) {
        return current
      }

      return current === null ? current : null
    })
    profileRouteSyncInitializedRef.current = true
  }, [selectedProfileFromUrl])

  useEffect(() => {
    setIsDetailDrawerOpen((current) => (current === detailOpenFromUrl ? current : detailOpenFromUrl))
  }, [detailOpenFromUrl])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    const normalizedSearch = search.trim()

    if (normalizedSearch) {
      next.set('q', normalizedSearch)
    } else {
      next.delete('q')
    }

    if (selectedProfileId !== undefined) {
      if (selectedProfileId) {
        next.set('profile', selectedProfileId)
      } else {
        next.delete('profile')
      }
    }

    if (selectedProfileId !== undefined) {
      if (isDetailDrawerOpen && selectedProfileId) {
        next.set('detail', '1')
      } else {
        next.delete('detail')
      }
    }

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(
        next,
        routeUpdateModeRef.current === 'replace'
          ? { replace: true }
          : undefined
      )
    }
    routeUpdateModeRef.current = 'replace'
  }, [isDetailDrawerOpen, search, searchParams, selectedProfileId, setSearchParams])

  const bindingProfiles = useMemo(
    () => bindingProfilesQuery.data?.binding_profiles ?? [],
    [bindingProfilesQuery.data?.binding_profiles],
  )
  const filteredProfiles = useMemo(
    () => filterBindingProfiles(bindingProfiles, deferredSearch),
    [bindingProfiles, deferredSearch],
  )

  const handleSearchChange = (nextSearch: string) => {
    const nextFilteredProfiles = filterBindingProfiles(bindingProfiles, nextSearch)
    const nextSelectedProfileId = selectedProfileId && nextFilteredProfiles.some(
      (profile) => profile.binding_profile_id === selectedProfileId
    )
      ? selectedProfileId
      : (nextFilteredProfiles[0]?.binding_profile_id ?? null)
    const nextDetailOpen = Boolean(nextSelectedProfileId) && isDetailDrawerOpen

    routeUpdateModeRef.current = 'push'
    setSearch(nextSearch)
    setSelectedProfileId(nextSelectedProfileId)
    setIsDetailDrawerOpen(nextDetailOpen)
  }

  useEffect(() => {
    if (bindingProfilesQuery.isLoading) {
      return
    }

    if (!filteredProfiles.length) {
      routeUpdateModeRef.current = 'replace'
      setSelectedProfileId(null)
      setIsDetailDrawerOpen(false)
      return
    }
    if (selectedProfileId && filteredProfiles.some((profile) => profile.binding_profile_id === selectedProfileId)) {
      return
    }
    routeUpdateModeRef.current = 'replace'
    setSelectedProfileId(filteredProfiles[0].binding_profile_id)
  }, [bindingProfilesQuery.isLoading, filteredProfiles, selectedProfileId])

  const selectedProfileQuery = useBindingProfileDetail(selectedProfileId ?? undefined, {
    enabled: typeof selectedProfileId === 'string' && selectedProfileId.length > 0,
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

  const openAttachmentWorkspace = (poolId?: string) => {
    if (!poolId) {
      navigate(POOL_CATALOG_ROUTE)
      return
    }
    navigate(`${POOL_CATALOG_ROUTE}?pool_id=${encodeURIComponent(poolId)}&tab=bindings`)
  }

  const listColumns: ColumnsType<BindingProfileSummary> = [
    {
      title: 'Code',
      dataIndex: 'code',
      key: 'code',
      render: (value: string, record) => (
        <Button
          type="text"
          aria-label={`Open profile ${record.code}`}
          aria-pressed={record.binding_profile_id === selectedProfileId}
          onClick={() => handleSelectProfile(record.binding_profile_id)}
          style={{
            width: '100%',
            minHeight: 36,
            paddingInline: 8,
            paddingBlock: 6,
            height: 'auto',
            fontWeight: 600,
            justifyContent: 'flex-start',
            textAlign: 'left',
            whiteSpace: 'normal',
          }}
        >
          {value}
        </Button>
      ),
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
      title: 'Created at',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => formatDateTime(value),
    },
  ]
  const immutableRevisionColumns: ColumnsType<BindingProfileRevision> = [
    {
      title: 'Revision',
      dataIndex: 'revision_number',
      key: 'revision_number',
      render: (value: number) => `r${value}`,
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
          onClick={() => openAttachmentWorkspace(record.poolId)}
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

  function handleSelectProfile(profileId: string) {
    routeUpdateModeRef.current = 'push'
    setSelectedProfileId(profileId)
    setIsDetailDrawerOpen(true)
  }

  const handleCloseDetail = () => {
    routeUpdateModeRef.current = 'push'
    setIsDetailDrawerOpen(false)
  }

  useEffect(() => {
    if (!isUsageRequested || !selectedProfileId) {
      setUsageLoading(false)
      setUsageError(null)
      return
    }

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
  }, [isUsageRequested, selectedProfileId])

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="Binding Profiles"
          subtitle={(
            <>
              Reusable profile workspace for selecting a profile, checking where it is used, and publishing the next revision.
              Pool-local attachments remain in
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
        message="Operator workflow"
        description={(
          <Space direction="vertical" size={8}>
            <Text>
              Start here when you need to inspect a reusable profile, see where it is attached, or publish the next
              revision. Use
              {' '}
              <Text code>{POOL_BINDING_PROFILES_ROUTE}</Text>
              {' '}
              for profile-level authoring and
              {' '}
              <Text code>{POOL_CATALOG_ROUTE}</Text>
              {' '}
              when you need to attach an existing revision to a concrete pool.
            </Text>
            <Space wrap>
              <Button onClick={() => openAttachmentWorkspace()}>Open attachment workspace</Button>
            </Space>
          </Space>
        )}
      />

      {actionError ? (
        <Alert type="error" showIcon message={actionError} />
      ) : null}

      <MasterDetailShell
        detailOpen={isDetailDrawerOpen}
        onCloseDetail={handleCloseDetail}
        detailDrawerTitle={selectedProfile?.name || 'Profile detail'}
        list={(
          <EntityTable
            title="Catalog"
            extra={(
              <Input
                aria-label="Search profiles"
                allowClear
                autoComplete="off"
                name="profile-search"
                placeholder="Search code, name, workflow"
                value={search}
                onChange={(event) => handleSearchChange(event.target.value)}
                style={{ width: screens.sm ? 240 : '100%' }}
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
            error={detailError}
            loading={selectedProfileQuery.isLoading}
            empty={!selectedProfileId || (!selectedProfile && !selectedProfileQuery.isLoading)}
            emptyDescription="Select a profile from the catalog."
          >
            {selectedProfile ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <div
                  style={{
                    display: 'flex',
                    flexDirection: screens.sm ? 'row' : 'column',
                    flexWrap: screens.sm ? 'wrap' : 'nowrap',
                    gap: 12,
                    width: '100%',
                  }}
                >
                  <Button
                    onClick={() => setIsReviseOpen(true)}
                    disabled={!selectedProfile || selectedProfile.status === 'deactivated'}
                    style={{ width: screens.sm ? 'auto' : '100%', whiteSpace: 'normal', height: 'auto' }}
                  >
                    Publish new revision
                  </Button>
                  <Button
                    danger
                    onClick={() => { void handleDeactivateProfile() }}
                    disabled={!selectedProfile || selectedProfile.status === 'deactivated'}
                    loading={deactivateBindingProfileMutation.isPending}
                    style={{ width: screens.sm ? 'auto' : '100%', whiteSpace: 'normal', height: 'auto' }}
                  >
                    Deactivate profile
                  </Button>
                  <Button
                    onClick={() => openAttachmentWorkspace()}
                    style={{ width: screens.sm ? 'auto' : '100%', whiteSpace: 'normal', height: 'auto' }}
                  >
                    Open attachment workspace
                  </Button>
                </div>

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
                  <Descriptions.Item label="Latest revision number">
                    {`r${selectedProfile.latest_revision_number}`}
                  </Descriptions.Item>
                  <Descriptions.Item label="Description">
                    {selectedProfile.description || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Workflow">
                    {`${selectedProfile.latest_revision.workflow.workflow_name} · r${selectedProfile.latest_revision.workflow.workflow_revision}`}
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

                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Title level={3} style={{ margin: 0, fontSize: 18 }}>
                    Where this profile is used
                  </Title>
                  <Text type="secondary">
                    Check current pool attachments before publishing a new revision or deactivating the reusable profile.
                  </Text>
                </Space>

                <EntityTable
                  title="Pool attachment usage"
                  error={usageError}
                  loading={usageLoading}
                  emptyDescription="No pool attachments are pinned on this profile yet."
                  dataSource={selectedProfileUsage}
                  columns={usageColumns}
                  rowKey="key"
                  toolbar={(
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: screens.sm ? 'row' : 'column',
                        flexWrap: screens.sm ? 'wrap' : 'nowrap',
                        gap: 16,
                        width: '100%',
                      }}
                    >
                      {!isUsageRequested ? (
                        <Button onClick={() => setIsUsageRequested(true)}>
                          Load attachment usage
                        </Button>
                      ) : null}
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
                    </div>
                  )}
                />

                <EntityTable
                  title="Revision history"
                  rowKey="binding_profile_revision_id"
                  columns={revisionColumns}
                  dataSource={selectedProfile.revisions}
                />

                <Collapse
                  size="small"
                  items={[
                    {
                      key: 'advanced-payload',
                      label: 'Advanced payload and immutable pins',
                      children: (
                        <Space direction="vertical" size={12} style={{ width: '100%' }}>
                          <Descriptions bordered size="small" column={1}>
                            <Descriptions.Item label="Latest immutable revision">
                              <Text data-testid="pool-binding-profiles-latest-revision-id">
                                {selectedProfile.latest_revision.binding_profile_revision_id}
                              </Text>
                            </Descriptions.Item>
                            <Descriptions.Item label="Workflow definition key">
                              {selectedProfile.latest_revision.workflow.workflow_definition_key}
                            </Descriptions.Item>
                            <Descriptions.Item label="Workflow pin">
                              {`${selectedProfile.latest_revision.workflow.workflow_revision_id} · rev ${selectedProfile.latest_revision.workflow.workflow_revision}`}
                            </Descriptions.Item>
                          </Descriptions>
                          <EntityTable
                            title="Immutable revision lineage"
                            rowKey="binding_profile_revision_id"
                            columns={immutableRevisionColumns}
                            dataSource={selectedProfile.revisions}
                          />
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
                      ),
                    },
                  ]}
                />
              </Space>
            ) : null}
          </EntityDetails>
        )}
      />

      {isCreateOpen ? (
        <PoolBindingProfilesEditorModal
          open={isCreateOpen}
          mode="create"
          onCancel={() => setIsCreateOpen(false)}
          onSubmit={async (request) => {
            await handleCreateProfile(request)
            setIsCreateOpen(false)
          }}
        />
      ) : null}

      {isReviseOpen ? (
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
      ) : null}
    </WorkspacePage>
  )
}
