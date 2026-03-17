import { useDeferredValue, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Input,
  Row,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'

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
} from '../../api/poolBindingProfiles'
import { resolveApiError } from './masterData/errorUtils'
import { PoolBindingProfilesEditorModal } from './PoolBindingProfilesEditorModal'
import { POOL_BINDING_PROFILES_ROUTE, POOL_CATALOG_ROUTE } from './routes'

const { Title, Text } = Typography

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

const formatJson = (value: unknown) => JSON.stringify(value ?? {}, null, 2)

const renderStatusTag = (status: string) => (
  <Tag color={status === 'deactivated' ? 'default' : 'green'}>{status}</Tag>
)

export function PoolBindingProfilesPage() {
  const [search, setSearch] = useState('')
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isReviseOpen, setIsReviseOpen] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const deferredSearch = useDeferredValue(search)

  const bindingProfilesQuery = useBindingProfiles()
  const createBindingProfileMutation = useCreateBindingProfile()
  const reviseBindingProfileMutation = useReviseBindingProfile()
  const deactivateBindingProfileMutation = useDeactivateBindingProfile()

  const bindingProfiles = bindingProfilesQuery.data?.binding_profiles ?? []
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
      render: (value: string) => renderStatusTag(value),
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

  const handleCreateProfile = async (request: BindingProfileCreateRequest | BindingProfileRevisionCreateRequest) => {
    const response = await createBindingProfileMutation.mutateAsync(request as BindingProfileCreateRequest)
    const created = response.binding_profile
    setActionError(null)
    setSelectedProfileId(created.binding_profile_id)
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

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <Title level={2} style={{ marginBottom: 8 }}>
          Binding Profiles
        </Title>
        <Text type="secondary">
          Primary authoring catalog for reusable workflow/slot logic. Pool-local attachments remain in
          {' '}
          {POOL_CATALOG_ROUTE}
          .
        </Text>
      </div>

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
            <Space>
              <Button type="primary" onClick={() => setIsCreateOpen(true)}>
                Create profile
              </Button>
              <Button href={POOL_CATALOG_ROUTE}>
                Open attachment workspace
              </Button>
            </Space>
          </Space>
        )}
      />

      {actionError ? (
        <Alert type="error" showIcon message={actionError} />
      ) : null}

      <Row gutter={16} align="top">
        <Col span={10}>
          <Card
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
          >
            {listError ? (
              <Alert type="error" showIcon message={listError} />
            ) : bindingProfilesQuery.isLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
                <Spin />
              </div>
            ) : filteredProfiles.length === 0 ? (
              <Empty description="No binding profiles found." />
            ) : (
              <Table
                rowKey="binding_profile_id"
                size="small"
                pagination={false}
                columns={listColumns}
                dataSource={filteredProfiles}
                onRow={(record) => ({
                  onClick: () => setSelectedProfileId(record.binding_profile_id),
                  style: { cursor: 'pointer' },
                })}
                rowClassName={(record) => (
                  record.binding_profile_id === selectedProfileId ? 'ant-table-row-selected' : ''
                )}
              />
            )}
          </Card>
        </Col>

        <Col span={14}>
          <Card
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
          >
            {detailError ? (
              <Alert type="error" showIcon message={detailError} />
            ) : !selectedProfileId ? (
              <Empty description="Select a profile from the catalog." />
            ) : selectedProfileQuery.isLoading || !selectedProfile ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
                <Spin />
              </div>
            ) : (
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
                      {renderStatusTag(selectedProfile.status)}
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

                <Card title="Latest revision payload" size="small">
                  <Descriptions bordered size="small" column={1}>
                    <Descriptions.Item label="Workflow">
                      {`${selectedProfile.latest_revision.workflow.workflow_name} · ${selectedProfile.latest_revision.workflow.workflow_definition_key}`}
                    </Descriptions.Item>
                    <Descriptions.Item label="Workflow pin">
                      {`${selectedProfile.latest_revision.workflow.workflow_revision_id} · rev ${selectedProfile.latest_revision.workflow.workflow_revision}`}
                    </Descriptions.Item>
                  </Descriptions>
                  <Row gutter={12} style={{ marginTop: 12 }}>
                    <Col span={12}>
                      <Text strong>Decision refs</Text>
                      <pre style={{ marginTop: 8 }}>{formatJson(selectedProfile.latest_revision.decisions)}</pre>
                    </Col>
                    <Col span={12}>
                      <Text strong>Parameters</Text>
                      <pre style={{ marginTop: 8 }}>{formatJson(selectedProfile.latest_revision.parameters)}</pre>
                    </Col>
                    <Col span={12}>
                      <Text strong>Role mapping</Text>
                      <pre style={{ marginTop: 8 }}>{formatJson(selectedProfile.latest_revision.role_mapping)}</pre>
                    </Col>
                    <Col span={12}>
                      <Text strong>Revision metadata</Text>
                      <pre style={{ marginTop: 8 }}>{formatJson(selectedProfile.latest_revision.metadata)}</pre>
                    </Col>
                  </Row>
                </Card>

                <Table
                  rowKey="binding_profile_revision_id"
                  size="small"
                  pagination={false}
                  columns={revisionColumns}
                  dataSource={selectedProfile.revisions}
                />
              </Space>
            )}
          </Card>
        </Col>
      </Row>

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
    </Space>
  )
}
