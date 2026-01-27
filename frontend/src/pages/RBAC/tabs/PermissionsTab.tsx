import { useMemo, useState } from 'react'
import { App, Alert, Button, Card, Form, Input, Radio, Segmented, Select, Space, Tooltip, Typography } from 'antd'

import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
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
import { CLUSTER_BULK_I18N, DATABASE_BULK_I18N } from './permissions/bulkI18n'
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
  const confirmReason = useConfirmReason(modal, message, {
    placeholder: 'Причина (обязательно)',
    okText: 'Отозвать',
    cancelText: 'Отмена',
    requiredMessage: 'Укажите причину',
  })

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
  const roles = rolesQuery.data?.roles ?? []
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

      message.success('Доступ выдан')
      rbacPermissionsGrantForm.resetFields()
      setRbacPermissionsList((prev) => ({ ...prev, page: 1 }))
    } catch {
      message.error('Не удалось выдать доступ')
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {rbacPermissionsResourceKey === 'databases' && (
        <Alert
          type="info"
          showIcon
          message="Как выдать доступ на конкретную ИБ"
          description={(
            <Space direction="vertical" size={4}>
              <Text>
                1) Выберите режим <Text code>Кто → Где</Text> (подберите пользователя/группу и ИБ в фильтрах), или <Text code>Где → Кто</Text> (выберите ИБ слева и смотрите назначения справа).
              </Text>
              <Text>
                2) В блоке “Выдать доступ” укажите уровень и причину, затем нажмите “Выдать”.
              </Text>
              <Text type="secondary">
                3) Перепроверьте вкладку “Эффективный доступ”: строка = итог, раскрытие = источники (прямое/группа/через кластер/...).
              </Text>
            </Space>
          )}
        />
      )}

      <Card title="Объект и субъект" size="small">
        <Space wrap>
          <Select
            style={{ width: 260 }}
            value={rbacPermissionsResourceKey}
            options={[
              { label: 'Кластеры', value: 'clusters' },
              { label: 'Базы', value: 'databases' },
              { label: 'Шаблоны операций', value: 'operation-templates' },
              { label: 'Шаблоны рабочих процессов', value: 'workflow-templates' },
              { label: 'Артефакты', value: 'artifacts' },
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
            <Radio.Button value="user">Пользователь</Radio.Button>
            <Radio.Button value="role">Группа</Radio.Button>
          </Radio.Group>
          <Segmented
            value={rbacPermissionsViewMode}
            options={[
              { label: 'Кто -> Где', value: 'principal' },
              { label: 'Где -> Кто', value: 'resource' },
            ]}
            onChange={(value) => setRbacPermissionsViewMode(value as 'principal' | 'resource')}
          />
        </Space>
      </Card>

      <Card title="Выдать доступ" size="small">
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
              message: rbacPermissionsPrincipalType === 'user' ? 'Выберите пользователя' : 'Выберите группу',
            }]}
          >
            <RbacPrincipalPicker
              principalType={rbacPermissionsPrincipalType}
              allowClear
              placeholderUser="Пользователь"
              placeholderRole="Группа"
              userOptions={userOptions}
              userLoading={usersQuery.isFetching}
              onUserSearch={setUserSearch}
              roleOptions={roleOptions}
            />
          </Form.Item>

          <Form.Item name="resource_id" rules={[{ required: true, message: 'Выберите ресурс' }]}>
            <Tooltip title="Ресурс — куда выдаём доступ (кластер/база/шаблон/артефакт).">
              <span data-testid="rbac-permissions-grant-resource">
                <RbacResourcePicker
                  resourceKey={rbacPermissionsResourceKey}
                  clusters={clusters}
                  disabled={rbacPermissionsViewMode === 'resource'}
                  placeholder="Ресурс"
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
            <Tooltip title="Комментарий к назначению (не причина).">
              <Input placeholder="Комментарий (опционально)" style={{ width: 220 }} />
            </Tooltip>
          </Form.Item>

          <Form.Item name="reason" rules={[{ required: true, message: 'Укажите причину' }]}>
            <Input placeholder="Причина (обязательно)" style={{ width: 260 }} />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={rbacPermissionsGrantPending}
              disabled={rbacPermissionsViewMode === 'resource' && !rbacPermissionsList.resource_id}
            >
              Выдать
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {rbacPermissionsViewMode === 'resource' && (
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          {rbacPermissionsResourceKey === 'clusters' || rbacPermissionsResourceKey === 'databases' ? (
            <RbacClusterDatabaseTree
              title="Ресурсы"
              mode={rbacPermissionsResourceKey === 'clusters' ? 'clusters' : 'databases'}
              clusters={clusters}
              searchPlaceholder={rbacPermissionsResourceKey === 'clusters' ? 'Поиск кластеров' : 'Поиск баз'}
              loadingText="Загрузка…"
              loadMoreText="Загрузить ещё…"
              clearLabel="Снять выбор"
              value={rbacPermissionsList.resource_id}
              onChange={(id) => {
                setRbacPermissionsList((prev) => ({ ...prev, resource_id: id, page: 1 }))
                rbacPermissionsGrantForm.setFieldValue('resource_id', id)
              }}
              onDatabasesLoaded={handleDatabasesLoaded}
            />
          ) : (
            <RbacResourceBrowser
              title="Ресурсы"
              searchPlaceholder="Поиск ресурса"
              searchValue={resourceSearchValue}
              onSearchChange={setResourceSearchValue}
              options={resourceBrowserOptions}
              selectedValue={rbacPermissionsList.resource_id}
              onSelect={(id) => {
                setRbacPermissionsList((prev) => ({ ...prev, resource_id: id, page: 1 }))
                rbacPermissionsGrantForm.setFieldValue('resource_id', id)
              }}
              loading={resourceRef.loading}
              loadingText="Загрузка…"
              onScroll={(event) => resourceRef.onPopupScroll?.(event)}
              clearLabel="Снять выбор"
              clearDisabled={!rbacPermissionsList.resource_id}
              onClear={() => {
                setRbacPermissionsList((prev) => ({ ...prev, resource_id: undefined, page: 1 }))
                rbacPermissionsGrantForm.setFieldValue('resource_id', undefined)
              }}
            />
          )}

          <PermissionsAssignmentsTable
            title="Назначения"
            style={{ flex: 1, minWidth: 0 }}
            empty={{
              show: !rbacPermissionsList.resource_id,
              description: (
                <Space direction="vertical" size={4}>
                  <Text>Выберите ресурс слева.</Text>
                  <Text type="secondary">
                    Дальше: в блоке “Выдать доступ” выберите субъект, уровень и укажите причину.
                  </Text>
                  <Text type="secondary">
                    После изменений перепроверьте вкладку “Эффективный доступ”.
                  </Text>
                </Space>
              ),
            }}
            toolbar={(
              <>
                <Text>
                  <Text strong>Ресурс:</Text> {selectedResourceLabel}
                </Text>

                <Select
                  style={{ width: 140 }}
                  placeholder="Уровень"
                  allowClear
                  value={rbacPermissionsList.level}
                  onChange={(value) => setRbacPermissionsList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                  options={LEVEL_OPTIONS}
                />

                <Input
                  placeholder="Поиск"
                  style={{ width: 220 }}
                  value={rbacPermissionsList.search}
                  onChange={(e) => setRbacPermissionsList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                />

                <Button
                  onClick={() => tableConfig.refetch()}
                  loading={tableConfig.fetching}
                >
                  Обновить
                </Button>
              </>
            )}
            tableConfig={tableConfig}
            page={rbacPermissionsList.page}
            pageSize={rbacPermissionsList.pageSize}
            onPaginationChange={(page, pageSize) => setRbacPermissionsList((prev) => ({ ...prev, page, pageSize }))}
            errorMessage="Не удалось загрузить назначения"
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
          i18n={CLUSTER_BULK_I18N}
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
          i18n={DATABASE_BULK_I18N}
        />
      )}

      {rbacPermissionsViewMode === 'principal' && (
        <PermissionsAssignmentsTable
          title="Назначения"
          preamble={(!rbacPermissionsList.principal_id
            && !rbacPermissionsList.resource_id
            && !rbacPermissionsList.level
            && !rbacPermissionsList.search) ? (
              <Alert
                type="info"
                showIcon
                message="С чего начать"
                description={(
                  <Space direction="vertical" size={4}>
                    <Text>Выберите пользователя/группу и (опционально) ресурс/уровень — так проще найти нужные назначения.</Text>
                    <Text type="secondary">Для сценария “Где → Кто” переключите режим выше на “Где → Кто”.</Text>
                    <Text type="secondary">После изменений перепроверьте вкладку “Эффективный доступ”.</Text>
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
                placeholderUser="Пользователь"
                placeholderRole="Группа"
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
                placeholder="Ресурс"
                width={360}
                databaseLabelById={databasesLabelById.current}
                onDatabasesLoaded={handleDatabasesLoaded}
                select={resourceRef}
                clusterDatabasePickerI18n={clusterDatabasePickerI18n}
              />

              <Select
                style={{ width: 140 }}
                placeholder="Уровень"
                allowClear
                value={rbacPermissionsList.level}
                onChange={(value) => setRbacPermissionsList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                options={LEVEL_OPTIONS}
              />

              <Input
                placeholder="Поиск"
                style={{ width: 220 }}
                value={rbacPermissionsList.search}
                onChange={(e) => setRbacPermissionsList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
              />

              <Button
                onClick={() => tableConfig.refetch()}
                loading={tableConfig.fetching}
              >
                Обновить
              </Button>
            </>
          )}
          tableConfig={tableConfig}
          page={rbacPermissionsList.page}
          pageSize={rbacPermissionsList.pageSize}
          onPaginationChange={(page, pageSize) => setRbacPermissionsList((prev) => ({ ...prev, page, pageSize }))}
          errorMessage="Не удалось загрузить назначения"
        />
      )}
    </Space>
  )
}
