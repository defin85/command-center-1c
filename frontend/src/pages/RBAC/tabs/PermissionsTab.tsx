import { useMemo, useState } from 'react'
import { App, Alert, Button, Card, Form, Input, Radio, Segmented, Select, Space, Tooltip, Typography } from 'antd'

import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { useRbacTranslation } from '../../../i18n'
import {
  useBulkGrantClusterGroupPermission,
  useBulkGrantDatabaseGroupPermission,
  useBulkRevokeClusterGroupPermission,
  useBulkRevokeDatabaseGroupPermission,
  useGrantArtifactGroupPermission,
  useGrantArtifactPermission,
  useGrantClusterGroupPermission,
  useGrantClusterPermission,
  useGrantDatabaseGroupPermission,
  useGrantDatabasePermission,
  useGrantOperationTemplateGroupPermission,
  useGrantOperationTemplatePermission,
  useGrantWorkflowTemplateGroupPermission,
  useGrantWorkflowTemplatePermission,
  useRbacUsers,
  useRevokeArtifactGroupPermission,
  useRevokeArtifactPermission,
  useRevokeClusterGroupPermission,
  useRevokeClusterPermission,
  useRevokeDatabaseGroupPermission,
  useRevokeDatabasePermission,
  useRevokeOperationTemplateGroupPermission,
  useRevokeOperationTemplatePermission,
  useRevokeWorkflowTemplateGroupPermission,
  useRevokeWorkflowTemplatePermission,
  useRoles,
} from '../../../api/queries/rbac'
import { RbacBulkClusterRolePermissions } from '../components/RbacBulkClusterRolePermissions'
import { RbacBulkDatabaseRolePermissions } from '../components/RbacBulkDatabaseRolePermissions'
import { RbacClusterDatabaseTree } from '../components/RbacClusterDatabaseTree'
import { RbacPrincipalPicker } from '../components/RbacPrincipalPicker'
import { RbacResourceBrowser } from '../components/RbacResourceBrowser'
import { RbacResourcePicker } from '../components/RbacResourcePicker'
import { useConfirmReason } from '../hooks/useConfirmReason'
import { createClusterBulkI18n, createDatabaseBulkI18n } from './permissions/bulkI18n'
import { LEVEL_OPTIONS, type PermissionLevelCode, type RbacPermissionsListState, type RbacPermissionsResourceKey } from './permissions/types'
import { PermissionsAssignmentsTable } from './permissions/PermissionsAssignmentsTable'
import { usePermissionColumns } from './permissions/usePermissionColumns'
import { usePermissionsTableConfig } from './permissions/usePermissionsTableConfig'
import { useRbacResourceRefs } from './permissions/useRbacResourceRefs'

const { Text } = Typography

export function PermissionsTab(props: {
  canManageRbac: boolean
  isActive: boolean
  rbacPermissionsResourceKey: RbacPermissionsResourceKey
  setRbacPermissionsResourceKey: (value: RbacPermissionsResourceKey) => void
  rbacPermissionsPrincipalType: 'user' | 'role'
  setRbacPermissionsPrincipalType: (value: 'user' | 'role') => void
  rbacPermissionsViewMode: 'principal' | 'resource'
  setRbacPermissionsViewMode: (value: 'principal' | 'resource') => void
  rbacPermissionsList: RbacPermissionsListState
  setRbacPermissionsList: (value: (prev: RbacPermissionsListState) => RbacPermissionsListState) => void
}) {
  const {
    canManageRbac,
    isActive,
    rbacPermissionsResourceKey,
    setRbacPermissionsResourceKey,
    rbacPermissionsPrincipalType,
    setRbacPermissionsPrincipalType,
    rbacPermissionsViewMode,
    setRbacPermissionsViewMode,
    rbacPermissionsList,
    setRbacPermissionsList,
  } = props

  const { modal, message } = App.useApp()
  const { t } = useRbacTranslation()
  const confirmReason = useConfirmReason(modal, message, {
    placeholder: t(($) => $.permissions.reasonPlaceholder),
    okText: t(($) => $.permissions.actions.revoke),
    cancelText: t(($) => $.permissions.cancel),
    requiredMessage: t(($) => $.permissions.reasonRequired),
  })
  const clusterBulkI18n = useMemo(() => createClusterBulkI18n(t), [t])
  const databaseBulkI18n = useMemo(() => createDatabaseBulkI18n(t), [t])

  const [userSearch, setUserSearch] = useState<string>('')
  const debouncedUserSearch = useDebouncedValue(userSearch, 300)
  const usersQuery = useRbacUsers({ search: debouncedUserSearch || undefined, limit: 20, offset: 0 }, { enabled: canManageRbac })

  const userOptions = useMemo(() => {
    const base = usersQuery.data?.users ?? []
    const map = new Map<number, { label: string; value: number }>()
    base.forEach((user) => {
      if (!map.has(user.id)) {
        map.set(user.id, { label: `${user.username} #${user.id}`, value: user.id })
      }
    })
    return Array.from(map.values())
  }, [usersQuery.data?.users])

  const rolesQuery = useRoles({ limit: 500, offset: 0 }, { enabled: canManageRbac })
  const roles = useMemo(() => (
    rolesQuery.data?.roles ?? []
  ), [rolesQuery.data?.roles])
  const roleNameById = useMemo(() => (
    new Map(roles.map((role) => [role.id, role.name]))
  ), [roles])
  const roleOptions = useMemo(() => (
    roles.map((role) => ({ label: `${role.name} #${role.id}`, value: role.id }))
  ), [roles])

  const [rbacPermissionsGrantForm] = Form.useForm<{
    principal_id: number
    resource_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()
  const rbacPermissionsGrantResourceId = Form.useWatch('resource_id', rbacPermissionsGrantForm)

  const rbacPermissionsSelectedResourceIds: Array<string | undefined> = [
    typeof rbacPermissionsGrantResourceId === 'string' ? rbacPermissionsGrantResourceId : undefined,
    rbacPermissionsList.resource_id,
  ]

  const {
    clusterDatabasePickerI18n,
    clusters,
    databasesLabelById,
    handleDatabasesLoaded,
    resourceRef,
    resourceSearchValue,
    setResourceSearchValue,
    resourceBrowserOptions,
    selectedResourceLabel,
    resetSearchForKey,
  } = useRbacResourceRefs({
    enabled: canManageRbac,
    resourceKey: rbacPermissionsResourceKey,
    selectedResourceIds: rbacPermissionsSelectedResourceIds,
    selectedResourceId: rbacPermissionsList.resource_id,
  })

  const grantCluster = useGrantClusterPermission()
  const grantDatabase = useGrantDatabasePermission()
  const grantClusterGroup = useGrantClusterGroupPermission()
  const bulkGrantClusterGroup = useBulkGrantClusterGroupPermission()
  const bulkRevokeClusterGroup = useBulkRevokeClusterGroupPermission()
  const grantDatabaseGroup = useGrantDatabaseGroupPermission()
  const bulkGrantDatabaseGroup = useBulkGrantDatabaseGroupPermission()
  const bulkRevokeDatabaseGroup = useBulkRevokeDatabaseGroupPermission()
  const grantOperationTemplate = useGrantOperationTemplatePermission()
  const grantOperationTemplateGroup = useGrantOperationTemplateGroupPermission()
  const grantWorkflowTemplate = useGrantWorkflowTemplatePermission()
  const grantWorkflowTemplateGroup = useGrantWorkflowTemplateGroupPermission()
  const grantArtifact = useGrantArtifactPermission()
  const grantArtifactGroup = useGrantArtifactGroupPermission()

  const revokeCluster = useRevokeClusterPermission()
  const revokeDatabase = useRevokeDatabasePermission()
  const revokeClusterGroup = useRevokeClusterGroupPermission()
  const revokeDatabaseGroup = useRevokeDatabaseGroupPermission()
  const revokeOperationTemplate = useRevokeOperationTemplatePermission()
  const revokeOperationTemplateGroup = useRevokeOperationTemplateGroupPermission()
  const revokeWorkflowTemplate = useRevokeWorkflowTemplatePermission()
  const revokeWorkflowTemplateGroup = useRevokeWorkflowTemplateGroupPermission()
  const revokeArtifact = useRevokeArtifactPermission()
  const revokeArtifactGroup = useRevokeArtifactGroupPermission()

  const columns = usePermissionColumns({
    confirmReason,
    revokeCluster,
    revokeDatabase,
    revokeClusterGroup,
    revokeDatabaseGroup,
    revokeOperationTemplate,
    revokeOperationTemplateGroup,
    revokeWorkflowTemplate,
    revokeWorkflowTemplateGroup,
    revokeArtifact,
    revokeArtifactGroup,
  })

  const rbacPermissionsEnabled = canManageRbac
    && isActive
    && (rbacPermissionsViewMode === 'principal' || Boolean(rbacPermissionsList.resource_id))
  const debouncedRbacPermissionsSearch = useDebouncedValue(rbacPermissionsList.search, 300)
  const tableConfig = usePermissionsTableConfig({
    enabled: rbacPermissionsEnabled,
    resourceKey: rbacPermissionsResourceKey,
    principalType: rbacPermissionsPrincipalType,
    list: rbacPermissionsList,
    debouncedSearch: debouncedRbacPermissionsSearch,
    columns: {
      clusterColumns: columns.clusterColumns,
      databaseColumns: columns.databaseColumns,
      clusterGroupColumns: columns.clusterGroupColumns,
      databaseGroupColumns: columns.databaseGroupColumns,
      operationTemplateUserColumns: columns.operationTemplateUserColumns,
      operationTemplateGroupColumns: columns.operationTemplateGroupColumns,
      workflowTemplateUserColumns: columns.workflowTemplateUserColumns,
      workflowTemplateGroupColumns: columns.workflowTemplateGroupColumns,
      artifactUserColumns: columns.artifactUserColumns,
      artifactGroupColumns: columns.artifactGroupColumns,
    },
  })

  const rbacPermissionsGrantPending = (() => {
    if (rbacPermissionsPrincipalType === 'user') {
      switch (rbacPermissionsResourceKey) {
        case 'clusters':
          return grantCluster.isPending
        case 'databases':
          return grantDatabase.isPending
        case 'operation-templates':
          return grantOperationTemplate.isPending
        case 'workflow-templates':
          return grantWorkflowTemplate.isPending
        case 'artifacts':
          return grantArtifact.isPending
      }
    }
    switch (rbacPermissionsResourceKey) {
      case 'clusters':
        return grantClusterGroup.isPending
      case 'databases':
        return grantDatabaseGroup.isPending
      case 'operation-templates':
        return grantOperationTemplateGroup.isPending
      case 'workflow-templates':
        return grantWorkflowTemplateGroup.isPending
      case 'artifacts':
        return grantArtifactGroup.isPending
    }
    return false
  })()

  const handleRbacPermissionsGrant = async (values: {
    principal_id: number
    resource_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }) => {
    try {
      if (rbacPermissionsPrincipalType === 'user') {
        switch (rbacPermissionsResourceKey) {
          case 'clusters':
            await grantCluster.mutateAsync({
              user_id: values.principal_id,
              cluster_id: values.resource_id,
              level: values.level,
              notes: values.notes,
              reason: values.reason,
            })
            break
          case 'databases':
            await grantDatabase.mutateAsync({
              user_id: values.principal_id,
              database_id: values.resource_id,
              level: values.level,
              notes: values.notes,
              reason: values.reason,
            })
            break
          case 'operation-templates':
            await grantOperationTemplate.mutateAsync({
              user_id: values.principal_id,
              template_id: values.resource_id,
              level: values.level,
              notes: values.notes,
              reason: values.reason,
            })
            break
          case 'workflow-templates':
            await grantWorkflowTemplate.mutateAsync({
              user_id: values.principal_id,
              template_id: values.resource_id,
              level: values.level,
              notes: values.notes,
              reason: values.reason,
            })
            break
          case 'artifacts':
            await grantArtifact.mutateAsync({
              user_id: values.principal_id,
              artifact_id: values.resource_id,
              level: values.level,
              notes: values.notes,
              reason: values.reason,
            })
            break
        }
      } else {
        switch (rbacPermissionsResourceKey) {
          case 'clusters':
            await grantClusterGroup.mutateAsync({
              group_id: values.principal_id,
              cluster_id: values.resource_id,
              level: values.level,
              notes: values.notes,
              reason: values.reason,
            })
            break
          case 'databases':
            await grantDatabaseGroup.mutateAsync({
              group_id: values.principal_id,
              database_id: values.resource_id,
              level: values.level,
              notes: values.notes,
              reason: values.reason,
            })
            break
          case 'operation-templates':
            await grantOperationTemplateGroup.mutateAsync({
              group_id: values.principal_id,
              template_id: values.resource_id,
              level: values.level,
              notes: values.notes,
              reason: values.reason,
            })
            break
          case 'workflow-templates':
            await grantWorkflowTemplateGroup.mutateAsync({
              group_id: values.principal_id,
              template_id: values.resource_id,
              level: values.level,
              notes: values.notes,
              reason: values.reason,
            })
            break
          case 'artifacts':
            await grantArtifactGroup.mutateAsync({
              group_id: values.principal_id,
              artifact_id: values.resource_id,
              level: values.level,
              notes: values.notes,
              reason: values.reason,
            })
            break
        }
      }

      message.success(t(($) => $.permissions.granted))
      rbacPermissionsGrantForm.resetFields()
      setRbacPermissionsList((prev) => ({ ...prev, page: 1 }))
    } catch {
      message.error(t(($) => $.permissions.grantFailed))
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {rbacPermissionsResourceKey === 'databases' && (
        <Alert
          type="info"
          showIcon
          message={t(($) => $.permissions.helpDatabaseTitle)}
          description={(
            <Space direction="vertical" size={4}>
              <Text>
                {t(($) => $.permissions.helpDatabaseStep1)}
              </Text>
              <Text>
                {t(($) => $.permissions.helpDatabaseStep2)}
              </Text>
              <Text type="secondary">
                {t(($) => $.permissions.helpDatabaseStep3)}
              </Text>
            </Space>
          )}
        />
      )}

      <Card title={t(($) => $.permissions.objectAndSubjectTitle)} size="small">
        <Space wrap>
          <Select
            style={{ width: 260 }}
            value={rbacPermissionsResourceKey}
            options={[
              { label: t(($) => $.permissions.resourceOptions.clusters), value: 'clusters' },
              { label: t(($) => $.permissions.resourceOptions.databases), value: 'databases' },
              { label: t(($) => $.permissions.resourceOptions.operationTemplates), value: 'operation-templates' },
              { label: t(($) => $.permissions.resourceOptions.workflowTemplates), value: 'workflow-templates' },
              { label: t(($) => $.permissions.resourceOptions.artifacts), value: 'artifacts' },
            ]}
            onChange={(value) => {
              const nextKey = value as RbacPermissionsResourceKey
              setRbacPermissionsResourceKey(nextKey)
              rbacPermissionsGrantForm.resetFields()
              setRbacPermissionsList((prev) => ({ ...prev, resource_id: undefined, page: 1 }))
              resetSearchForKey(nextKey)
            }}
          />
          <Radio.Group
            buttonStyle="solid"
            value={rbacPermissionsPrincipalType}
            onChange={(event) => {
              setRbacPermissionsPrincipalType(event.target.value as 'user' | 'role')
              rbacPermissionsGrantForm.resetFields()
              setRbacPermissionsList((prev) => ({ ...prev, principal_id: undefined, page: 1 }))
            }}
          >
            <Radio.Button value="user">{t(($) => $.permissions.principalUser)}</Radio.Button>
            <Radio.Button value="role">{t(($) => $.permissions.principalRole)}</Radio.Button>
          </Radio.Group>
          <Segmented
            value={rbacPermissionsViewMode}
            options={[
              { label: t(($) => $.permissions.viewModes.principal), value: 'principal' },
              { label: t(($) => $.permissions.viewModes.resource), value: 'resource' },
            ]}
            onChange={(value) => setRbacPermissionsViewMode(value as 'principal' | 'resource')}
          />
        </Space>
      </Card>

      <Card title={t(($) => $.permissions.grantTitle)} size="small">
        <Form
          form={rbacPermissionsGrantForm}
          layout="inline"
          onFinish={handleRbacPermissionsGrant}
          initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
        >
          <Form.Item
            name="principal_id"
            rules={[{
              required: true,
              message: rbacPermissionsPrincipalType === 'user'
                ? t(($) => $.permissions.selectUser)
                : t(($) => $.permissions.selectGroup),
            }]}
          >
            <RbacPrincipalPicker
              principalType={rbacPermissionsPrincipalType}
              allowClear
              placeholderUser={t(($) => $.permissions.principalUser)}
              placeholderRole={t(($) => $.permissions.principalRole)}
              userOptions={userOptions}
              userLoading={usersQuery.isFetching}
              onUserSearch={setUserSearch}
              roleOptions={roleOptions}
            />
          </Form.Item>

          <Form.Item name="resource_id" rules={[{ required: true, message: t(($) => $.permissions.selectResource) }]}>
            <Tooltip title={t(($) => $.permissions.resourceTooltip)}>
              <span data-testid="rbac-permissions-grant-resource">
                <RbacResourcePicker
                  resourceKey={rbacPermissionsResourceKey}
                  clusters={clusters}
                  disabled={rbacPermissionsViewMode === 'resource'}
                  placeholder={t(($) => $.permissions.resourceGeneric)}
                  width={360}
                  databaseLabelById={databasesLabelById.current}
                  onDatabasesLoaded={handleDatabasesLoaded}
                  select={resourceRef}
                  clusterDatabasePickerI18n={clusterDatabasePickerI18n}
                />
              </span>
            </Tooltip>
          </Form.Item>

          <Form.Item name="level" rules={[{ required: true }]}>
            <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
          </Form.Item>

          <Form.Item name="notes">
            <Tooltip title={t(($) => $.permissions.notesTooltip)}>
              <Input placeholder={t(($) => $.permissions.notesPlaceholder)} style={{ width: 220 }} />
            </Tooltip>
          </Form.Item>

          <Form.Item name="reason" rules={[{ required: true, message: t(($) => $.permissions.reasonRequired) }]}>
            <Input placeholder={t(($) => $.permissions.reasonPlaceholder)} style={{ width: 260 }} />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={rbacPermissionsGrantPending}
              disabled={rbacPermissionsViewMode === 'resource' && !rbacPermissionsList.resource_id}
            >
              {t(($) => $.permissions.grant)}
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {rbacPermissionsViewMode === 'resource' && (
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          {rbacPermissionsResourceKey === 'clusters' || rbacPermissionsResourceKey === 'databases' ? (
            <RbacClusterDatabaseTree
              title={t(($) => $.permissions.resources)}
              mode={rbacPermissionsResourceKey === 'clusters' ? 'clusters' : 'databases'}
              clusters={clusters}
              searchPlaceholder={rbacPermissionsResourceKey === 'clusters'
                ? t(($) => $.permissions.searchClusters)
                : t(($) => $.permissions.searchDatabases)}
              loadingText={t(($) => $.permissions.loading)}
              loadMoreText={t(($) => $.permissions.loadMore)}
              clearLabel={t(($) => $.permissions.clearSelection)}
              value={rbacPermissionsList.resource_id}
              onChange={(id) => {
                setRbacPermissionsList((prev) => ({ ...prev, resource_id: id, page: 1 }))
                rbacPermissionsGrantForm.setFieldValue('resource_id', id)
              }}
              onDatabasesLoaded={handleDatabasesLoaded}
            />
          ) : (
            <RbacResourceBrowser
              title={t(($) => $.permissions.resources)}
              searchPlaceholder={t(($) => $.permissions.search)}
              searchValue={resourceSearchValue}
              onSearchChange={setResourceSearchValue}
              options={resourceBrowserOptions}
              selectedValue={rbacPermissionsList.resource_id}
              onSelect={(id) => {
                setRbacPermissionsList((prev) => ({ ...prev, resource_id: id, page: 1 }))
                rbacPermissionsGrantForm.setFieldValue('resource_id', id)
              }}
              loading={resourceRef.loading}
              loadingText={t(($) => $.permissions.loading)}
              onScroll={(event) => resourceRef.onPopupScroll?.(event)}
              clearLabel={t(($) => $.permissions.clearSelection)}
              clearDisabled={!rbacPermissionsList.resource_id}
              onClear={() => {
                setRbacPermissionsList((prev) => ({ ...prev, resource_id: undefined, page: 1 }))
                rbacPermissionsGrantForm.setFieldValue('resource_id', undefined)
              }}
            />
          )}

          <PermissionsAssignmentsTable
            title={t(($) => $.permissions.assignments)}
            style={{ flex: 1, minWidth: 0 }}
            empty={{
              show: !rbacPermissionsList.resource_id,
              description: (
                <Space direction="vertical" size={4}>
                  <Text>{t(($) => $.permissions.resourceSelectionEmptyTitle)}</Text>
                  <Text type="secondary">
                    {t(($) => $.permissions.resourceSelectionEmptyStep1)}
                  </Text>
                  <Text type="secondary">
                    {t(($) => $.permissions.resourceSelectionEmptyStep2)}
                  </Text>
                </Space>
              ),
            }}
            toolbar={(
              <>
                <Text>
                  <Text strong>{t(($) => $.permissions.resourceGeneric)}:</Text> {selectedResourceLabel}
                </Text>

                <Select
                  style={{ width: 140 }}
                  placeholder={t(($) => $.permissions.columns.level)}
                  allowClear
                  value={rbacPermissionsList.level}
                  onChange={(value) => setRbacPermissionsList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                  options={LEVEL_OPTIONS}
                />

                <Input
                  placeholder={t(($) => $.permissions.search)}
                  style={{ width: 220 }}
                  value={rbacPermissionsList.search}
                  onChange={(e) => setRbacPermissionsList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                />

                <Button
                  onClick={() => tableConfig.refetch()}
                  loading={tableConfig.fetching}
                >
                  {t(($) => $.permissions.refresh)}
                </Button>
              </>
            )}
            tableConfig={tableConfig}
            page={rbacPermissionsList.page}
            pageSize={rbacPermissionsList.pageSize}
            onPaginationChange={(page, pageSize) => setRbacPermissionsList((prev) => ({ ...prev, page, pageSize }))}
            errorMessage={t(($) => $.permissions.loadFailed)}
          />
        </div>
      )}

      {rbacPermissionsViewMode === 'principal'
        && rbacPermissionsPrincipalType === 'role'
        && rbacPermissionsResourceKey === 'clusters' && (
        <RbacBulkClusterRolePermissions
          roleOptions={roleOptions}
          roleNameById={roleNameById}
          levelOptions={LEVEL_OPTIONS}
          bulkGrant={bulkGrantClusterGroup}
          bulkRevoke={bulkRevokeClusterGroup}
          i18n={clusterBulkI18n}
        />
      )}

      {rbacPermissionsViewMode === 'principal'
        && rbacPermissionsPrincipalType === 'role'
        && rbacPermissionsResourceKey === 'databases' && (
        <RbacBulkDatabaseRolePermissions
          roleOptions={roleOptions}
          roleNameById={roleNameById}
          levelOptions={LEVEL_OPTIONS}
          bulkGrant={bulkGrantDatabaseGroup}
          bulkRevoke={bulkRevokeDatabaseGroup}
          i18n={databaseBulkI18n}
        />
      )}

      {rbacPermissionsViewMode === 'principal' && (
        <PermissionsAssignmentsTable
          title={t(($) => $.permissions.assignments)}
          preamble={(!rbacPermissionsList.principal_id
            && !rbacPermissionsList.resource_id
            && !rbacPermissionsList.level
            && !rbacPermissionsList.search) ? (
              <Alert
                type="info"
                showIcon
                message={t(($) => $.permissions.gettingStartedTitle)}
                description={(
                  <Space direction="vertical" size={4}>
                    <Text>{t(($) => $.permissions.gettingStartedStep1)}</Text>
                    <Text type="secondary">{t(($) => $.permissions.gettingStartedStep2)}</Text>
                    <Text type="secondary">{t(($) => $.permissions.gettingStartedStep3)}</Text>
                  </Space>
                )}
              />
            ) : null}
          toolbar={(
            <>
              <RbacPrincipalPicker
                principalType={rbacPermissionsPrincipalType}
                allowClear
                value={rbacPermissionsList.principal_id}
                onChange={(value) => setRbacPermissionsList((prev) => ({ ...prev, principal_id: value, page: 1 }))}
                placeholderUser={t(($) => $.permissions.principalUser)}
                placeholderRole={t(($) => $.permissions.principalRole)}
                userOptions={userOptions}
                userLoading={usersQuery.isFetching}
                onUserSearch={setUserSearch}
                roleOptions={roleOptions}
              />

              <RbacResourcePicker
                resourceKey={rbacPermissionsResourceKey}
                clusters={clusters}
                allowClear
                value={rbacPermissionsList.resource_id}
                onChange={(value) => setRbacPermissionsList((prev) => ({ ...prev, resource_id: value, page: 1 }))}
                placeholder={t(($) => $.permissions.resourceGeneric)}
                width={360}
                databaseLabelById={databasesLabelById.current}
                onDatabasesLoaded={handleDatabasesLoaded}
                select={resourceRef}
                clusterDatabasePickerI18n={clusterDatabasePickerI18n}
              />

              <Select
                style={{ width: 140 }}
                placeholder={t(($) => $.permissions.columns.level)}
                allowClear
                value={rbacPermissionsList.level}
                onChange={(value) => setRbacPermissionsList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                options={LEVEL_OPTIONS}
              />

              <Input
                placeholder={t(($) => $.permissions.search)}
                style={{ width: 220 }}
                value={rbacPermissionsList.search}
                onChange={(e) => setRbacPermissionsList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
              />

              <Button
                onClick={() => tableConfig.refetch()}
                loading={tableConfig.fetching}
              >
                {t(($) => $.permissions.refresh)}
              </Button>
            </>
          )}
          tableConfig={tableConfig}
          page={rbacPermissionsList.page}
          pageSize={rbacPermissionsList.pageSize}
          onPaginationChange={(page, pageSize) => setRbacPermissionsList((prev) => ({ ...prev, page, pageSize }))}
          errorMessage={t(($) => $.permissions.loadFailed)}
        />
      )}
    </Space>
  )
}
