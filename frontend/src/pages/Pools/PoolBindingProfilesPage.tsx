import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
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
import { useLocaleFormatters, usePoolsTranslation } from '../../i18n'
import {
  useBindingProfileDetail,
  useBindingProfiles,
  useCreateBindingProfile,
  useDeactivateBindingProfile,
  useReviseBindingProfile,
} from '../../api/queries/poolBindingProfiles'
import type {
  BindingProfileCreateRequest,
  BindingProfileRevision,
  BindingProfileRevisionCreateRequest,
  BindingProfileSummary,
  BindingProfileUsageAttachment,
} from '../../api/poolBindingProfiles'
import { resolveApiError } from './masterData/errorUtils'
import { PoolBindingProfilesEditorModal } from './PoolBindingProfilesEditorModal'
import { describeExecutionPackTopologyCompatibility } from './executionPackTopologyCompatibility'
import { POOL_CATALOG_ROUTE } from './routes'

const { Title, Text } = Typography
const { useBreakpoint } = Grid

type BindingSelector = {
  direction?: string | null
  mode?: string | null
  tags?: string[]
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

const formatBindingScope = (selector?: BindingSelector | null) => {
  const parts = [
    selector?.direction,
    selector?.mode,
  ]
  if (selector?.tags?.length) {
    parts.push(selector.tags.join(', '))
  }
  return parts.filter(Boolean).join(' · ')
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
  const { t } = usePoolsTranslation()
  const formatters = useLocaleFormatters()
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
  const [isUsageRequested, setIsUsageRequested] = useState(false)
  const deferredSearch = useDeferredValue(search)
  const formatDateTime = useCallback(
    (value?: string | null) => formatters.dateTime(value, { fallback: t('common.noValue') }),
    [formatters, t]
  )
  const formatBindingScopeLabel = useCallback(
    (selector?: BindingSelector | null) => {
      const normalized = formatBindingScope(selector)
      if (normalized) {
        return normalized
      }
      return [
        t('executionPacks.usage.anyDirection'),
        t('executionPacks.usage.anyMode'),
      ].join(' · ')
    },
    [t]
  )

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
    const attachments = selectedProfile?.usage_summary?.attachments ?? []
    return attachments.map((attachment: BindingProfileUsageAttachment) => ({
      key: `${attachment.pool_id}:${attachment.binding_id}`,
      poolId: attachment.pool_id,
      poolCode: attachment.pool_code,
      poolName: attachment.pool_name,
      bindingId: attachment.binding_id,
      attachmentRevision: attachment.attachment_revision,
      bindingProfileRevisionId: attachment.binding_profile_revision_id,
      bindingProfileRevisionNumber: attachment.binding_profile_revision_number ?? null,
      status: attachment.status,
      scope: formatBindingScopeLabel(attachment.selector),
    }))
  }, [formatBindingScopeLabel, selectedProfile])
  const selectedProfileUsageRevisionCount = useMemo(
    () => selectedProfile?.usage_summary?.revision_summary.length ?? 0,
    [selectedProfile]
  )
  const selectedProfileTopologyCompatibility = useMemo(
    () => describeExecutionPackTopologyCompatibility(selectedProfile?.latest_revision.topology_template_compatibility, {
      notAvailableStatus: t('executionPacks.compatibility.notAvailableStatus'),
      notAvailableMessage: t('executionPacks.compatibility.notAvailableMessage'),
      compatibleStatus: t('executionPacks.compatibility.compatibleStatus'),
      compatibleMessage: t('executionPacks.compatibility.compatibleMessage'),
      incompatibleStatus: t('executionPacks.compatibility.incompatibleStatus'),
      incompatibleMessage: t('executionPacks.compatibility.incompatibleMessage'),
    }),
    [selectedProfile, t]
  )
  const visibleProfileUsage = isUsageRequested ? selectedProfileUsage : []
  const visibleProfileUsageRevisionCount = isUsageRequested ? selectedProfileUsageRevisionCount : 0

  const openAttachmentWorkspace = (poolId?: string) => {
    if (!poolId) {
      navigate(POOL_CATALOG_ROUTE)
      return
    }
    navigate(`${POOL_CATALOG_ROUTE}?pool_id=${encodeURIComponent(poolId)}&tab=bindings`)
  }

  const listColumns: ColumnsType<BindingProfileSummary> = [
    {
      title: t('common.code'),
      dataIndex: 'code',
      key: 'code',
      render: (value: string, record) => (
        <Button
          type="text"
          aria-label={t('executionPacks.list.openProfile', { code: record.code })}
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
      title: t('common.name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('common.status'),
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => <StatusBadge status={value} />,
    },
    {
      title: t('executionPacks.list.latestRevision'),
      key: 'latest_revision',
      render: (_value, record) => (
        <Text>
          {t('executionPacks.list.latestRevisionSummary', {
            revision: record.latest_revision_number,
            workflow: record.latest_revision.workflow.workflow_name,
          })}
        </Text>
      ),
    },
  ]

  const revisionColumns: ColumnsType<BindingProfileRevision> = [
    {
      title: t('common.revision'),
      dataIndex: 'revision_number',
      key: 'revision_number',
      render: (value: number) => `r${value}`,
    },
    {
      title: t('common.workflow'),
      key: 'workflow',
      render: (_value, record) => (
        <Text>{`${record.workflow.workflow_name} · rev ${record.workflow.workflow_revision}`}</Text>
      ),
    },
    {
      title: t('common.createdAt'),
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => formatDateTime(value),
    },
  ]
  const immutableRevisionColumns: ColumnsType<BindingProfileRevision> = [
    {
      title: t('common.revision'),
      dataIndex: 'revision_number',
      key: 'revision_number',
      render: (value: number) => `r${value}`,
    },
    {
      title: t('executionPacks.detail.opaquePin'),
      dataIndex: 'binding_profile_revision_id',
      key: 'binding_profile_revision_id',
    },
    {
      title: t('common.createdAt'),
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => formatDateTime(value),
    },
  ]
  const usageColumns: ColumnsType<BindingProfileUsageRow> = [
    {
      title: t('executionPacks.usage.pool'),
      key: 'pool',
      render: (_value, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.poolCode}</Text>
          <Text type="secondary">{record.poolName}</Text>
        </Space>
      ),
    },
    {
      title: t('executionPacks.usage.binding'),
      dataIndex: 'bindingId',
      key: 'bindingId',
      render: (value: string) => <Text code>{value}</Text>,
    },
    {
      title: t('executionPacks.usage.pinnedRevision'),
      key: 'bindingProfileRevisionNumber',
      render: (_value, record) => (
        <Text>{record.bindingProfileRevisionNumber != null ? `r${record.bindingProfileRevisionNumber}` : record.bindingProfileRevisionId}</Text>
      ),
    },
    {
      title: t('executionPacks.usage.attachmentRevision'),
      dataIndex: 'attachmentRevision',
      key: 'attachmentRevision',
      render: (value: number) => `r${value}`,
    },
    {
      title: t('common.status'),
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => <StatusBadge status={value} />,
    },
    {
      title: t('executionPacks.usage.scope'),
      dataIndex: 'scope',
      key: 'scope',
    },
    {
      title: t('executionPacks.usage.action'),
      key: 'action',
      render: (_value, record) => (
        <Button
          size="small"
          onClick={() => openAttachmentWorkspace(record.poolId)}
        >
          {t('executionPacks.usage.openPoolAttachment')}
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
      const resolved = resolveApiError(error, t('executionPacks.messages.failedToDeactivate'))
      setActionError(resolved.message)
    }
  }

  const listError = bindingProfilesQuery.isError
    ? resolveApiError(bindingProfilesQuery.error, t('executionPacks.messages.failedToLoadList')).message
    : null
  const detailError = selectedProfileQuery.isError
    ? resolveApiError(selectedProfileQuery.error, t('executionPacks.messages.failedToLoadDetail')).message
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
    setIsUsageRequested(false)
  }, [selectedProfileId])

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t('executionPacks.page.title')}
          subtitle={t('executionPacks.page.subtitle')}
          actions={(
            <Button type="primary" onClick={() => setIsCreateOpen(true)}>
              {t('executionPacks.page.create')}
            </Button>
          )}
        />
      )}
    >

      <Alert
        type="info"
        showIcon
        message={t('executionPacks.alerts.operatorWorkflowTitle')}
        description={(
          <Space direction="vertical" size={8}>
            <Text>
              {t('executionPacks.alerts.operatorWorkflowDescription')}
            </Text>
            <Space wrap>
              <Button onClick={() => openAttachmentWorkspace()}>{t('executionPacks.page.openAttachmentWorkspace')}</Button>
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
        detailDrawerTitle={selectedProfile?.name || t('executionPacks.detail.drawerTitle')}
        list={(
          <EntityTable
            title={t('executionPacks.list.title')}
            extra={(
              <Input
                aria-label={t('executionPacks.list.searchAriaLabel')}
                allowClear
                autoComplete="off"
                name="profile-search"
                placeholder={t('executionPacks.list.searchPlaceholder')}
                value={search}
                onChange={(event) => handleSearchChange(event.target.value)}
                style={{ width: screens.sm ? 240 : '100%' }}
              />
            )}
            error={listError}
            loading={bindingProfilesQuery.isLoading}
            emptyDescription={t('executionPacks.list.emptyDescription')}
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
            title={t('executionPacks.detail.title')}
            error={detailError}
            loading={selectedProfileQuery.isLoading}
            empty={!selectedProfileId || (!selectedProfile && !selectedProfileQuery.isLoading)}
            emptyDescription={t('executionPacks.detail.emptyDescription')}
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
                    {t('executionPacks.page.publishRevision')}
                  </Button>
                  <Button
                    danger
                    onClick={() => { void handleDeactivateProfile() }}
                    disabled={!selectedProfile || selectedProfile.status === 'deactivated'}
                    loading={deactivateBindingProfileMutation.isPending}
                    style={{ width: screens.sm ? 'auto' : '100%', whiteSpace: 'normal', height: 'auto' }}
                  >
                    {t('executionPacks.page.deactivate')}
                  </Button>
                  <Button
                    onClick={() => openAttachmentWorkspace()}
                    style={{ width: screens.sm ? 'auto' : '100%', whiteSpace: 'normal', height: 'auto' }}
                  >
                    {t('executionPacks.page.openAttachmentWorkspace')}
                  </Button>
                </div>

                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label={t('common.code')}>
                    <Text strong data-testid="pool-binding-profiles-selected-code">
                      {selectedProfile.code}
                    </Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.name')}>{selectedProfile.name}</Descriptions.Item>
                  <Descriptions.Item label={t('common.status')}>
                    <span data-testid="pool-binding-profiles-status">
                      <StatusBadge status={selectedProfile.status} />
                    </span>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.latestRevisionNumber')}>
                    {`r${selectedProfile.latest_revision_number}`}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.description')}>
                    {selectedProfile.description || t('common.noValue')}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.workflow')}>
                    {`${selectedProfile.latest_revision.workflow.workflow_name} · r${selectedProfile.latest_revision.workflow.workflow_revision}`}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('executionPacks.detail.templateCompatibility')}>
                    <Text data-testid="pool-binding-profiles-topology-compatibility-status">
                      {selectedProfileTopologyCompatibility.statusText}
                    </Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.updatedAt')}>
                    {formatDateTime(selectedProfile.updated_at)}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('executionPacks.detail.deactivatedAt')}>
                    {formatDateTime(selectedProfile.deactivated_at)}
                  </Descriptions.Item>
                </Descriptions>

                {selectedProfile.status === 'deactivated' ? (
                  <Alert
                    type="warning"
                    showIcon
                    message={t('executionPacks.alerts.deactivatedWarning')}
                  />
                ) : null}

                <Alert
                  type={selectedProfileTopologyCompatibility.alertType}
                  showIcon
                  message={selectedProfileTopologyCompatibility.message}
                  description={(
                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                      <Text data-testid="pool-binding-profiles-topology-covered-slots">
                        {t('executionPacks.detail.coveredSlots', {
                          value: selectedProfileTopologyCompatibility.coveredSlotsText,
                        })}
                      </Text>
                      {selectedProfileTopologyCompatibility.diagnostics.map((diagnostic, diagnosticIndex) => (
                        <Text
                          key={`profile-topology-diagnostic:${diagnosticIndex}`}
                          type="secondary"
                          data-testid={`pool-binding-profiles-topology-diagnostic-${diagnosticIndex}`}
                        >
                          {diagnostic}
                        </Text>
                      ))}
                      {selectedProfileTopologyCompatibility.alertType === 'warning' ? (
                        <Space wrap>
                          <Button onClick={() => navigate('/decisions')}>{t('common.openDecisions')}</Button>
                          <Button onClick={() => openAttachmentWorkspace()}>{t('common.openAttachmentWorkspace')}</Button>
                        </Space>
                      ) : null}
                    </Space>
                  )}
                />

                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Title level={3} style={{ margin: 0, fontSize: 18 }}>
                    {t('executionPacks.detail.usageTitle')}
                  </Title>
                  <Text type="secondary">
                    {t('executionPacks.detail.usageSubtitle')}
                  </Text>
                </Space>

                <EntityTable
                  title={t('executionPacks.detail.poolAttachmentUsage')}
                  loading={selectedProfileQuery.isLoading && isUsageRequested}
                  emptyDescription={t('executionPacks.detail.noAttachments')}
                  dataSource={visibleProfileUsage}
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
                          {t('executionPacks.page.loadUsage')}
                        </Button>
                      ) : null}
                      <Text>
                        {t('executionPacks.detail.attachmentsCount')}
                        {' '}
                        <Text strong data-testid="pool-binding-profiles-usage-total">{visibleProfileUsage.length}</Text>
                      </Text>
                      <Text>
                        {t('executionPacks.detail.revisionsInUse')}
                        {' '}
                        <Text strong data-testid="pool-binding-profiles-usage-revisions">{visibleProfileUsageRevisionCount}</Text>
                      </Text>
                    </div>
                  )}
                />

                <EntityTable
                  title={t('executionPacks.detail.revisionHistory')}
                  rowKey="binding_profile_revision_id"
                  columns={revisionColumns}
                  dataSource={selectedProfile.revisions}
                />

                <Collapse
                  size="small"
                  items={[
                    {
                      key: 'advanced-payload',
                      label: t('executionPacks.detail.advancedPayload'),
                      children: (
                        <Space direction="vertical" size={12} style={{ width: '100%' }}>
                          <Descriptions bordered size="small" column={1}>
                            <Descriptions.Item label={t('executionPacks.detail.latestImmutableRevision')}>
                              <Text data-testid="pool-binding-profiles-latest-revision-id">
                                {selectedProfile.latest_revision.binding_profile_revision_id}
                              </Text>
                            </Descriptions.Item>
                            <Descriptions.Item label={t('executionPacks.detail.workflowDefinitionKey')}>
                              {selectedProfile.latest_revision.workflow.workflow_definition_key}
                            </Descriptions.Item>
                            <Descriptions.Item label={t('executionPacks.detail.workflowPin')}>
                              {`${selectedProfile.latest_revision.workflow.workflow_revision_id} · rev ${selectedProfile.latest_revision.workflow.workflow_revision}`}
                            </Descriptions.Item>
                          </Descriptions>
                          <EntityTable
                            title={t('executionPacks.detail.immutableRevisionLineage')}
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
                            <JsonBlock title={t('executionPacks.detail.decisionRefs')} value={selectedProfile.latest_revision.decisions} />
                            <JsonBlock title={t('executionPacks.detail.parameters')} value={selectedProfile.latest_revision.parameters} />
                            <JsonBlock title={t('executionPacks.detail.roleMapping')} value={selectedProfile.latest_revision.role_mapping} />
                            <JsonBlock title={t('executionPacks.detail.revisionMetadata')} value={selectedProfile.latest_revision.metadata} />
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
