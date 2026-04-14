import { useMemo, useState } from 'react'
import { App, Alert, Button, Card, Form, Input, Modal, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  useArtifactGroupPermissions,
  useCapabilities,
  useClusterGroupPermissions,
  useCreateRole,
  useDatabaseGroupPermissions,
  useDeleteRole,
  useOperationTemplateGroupPermissions,
  useRoles,
  useSetRoleCapabilities,
  useUpdateRole,
  useWorkflowTemplateGroupPermissions,
  type Capability,
  type RbacRole,
} from '../../../api/queries/rbac'
import { useRbacTranslation } from '../../../i18n'
import { ReasonModal } from '../components/ReasonModal'

const { Text } = Typography

const EMPTY_ROLES: RbacRole[] = []
const EMPTY_CAPABILITIES: Capability[] = []

export function RolesTab(props: {
  canManageRbac: boolean
  onOpenAssignmentsForRole?: (roleId: number) => void
}) {
  const { canManageRbac, onOpenAssignmentsForRole } = props
  const { message } = App.useApp()
  const { t } = useRbacTranslation()

  const rolesQuery = useRoles({ limit: 500, offset: 0 }, { enabled: canManageRbac })
  const createRole = useCreateRole()
  const updateRole = useUpdateRole()
  const deleteRole = useDeleteRole()
  const setRoleCapabilities = useSetRoleCapabilities()
  const capabilitiesQuery = useCapabilities({ enabled: canManageRbac })

  const roles = rolesQuery.data?.roles ?? EMPTY_ROLES
  const capabilities = capabilitiesQuery.data?.capabilities ?? EMPTY_CAPABILITIES

  const [createRoleForm] = Form.useForm<{ name: string; reason: string }>()

  const [roleSearch, setRoleSearch] = useState<string>('')

  const [roleEditorOpen, setRoleEditorOpen] = useState<boolean>(false)
  const [roleEditorRoleId, setRoleEditorRoleId] = useState<number | null>(null)
  const [roleEditorPermissionCodes, setRoleEditorPermissionCodes] = useState<string[]>([])

  const [renameRoleOpen, setRenameRoleOpen] = useState<boolean>(false)
  const [renameRoleRoleId, setRenameRoleRoleId] = useState<number | null>(null)
  const [renameRoleName, setRenameRoleName] = useState<string>('')

  const [deleteRoleOpen, setDeleteRoleOpen] = useState<boolean>(false)
  const [deleteRoleRoleId, setDeleteRoleRoleId] = useState<number | null>(null)

  const [cloneRoleOpen, setCloneRoleOpen] = useState<boolean>(false)
  const [cloneRoleSourceRoleId, setCloneRoleSourceRoleId] = useState<number | null>(null)
  const [cloneRoleName, setCloneRoleName] = useState<string>('')

  const [roleUsageOpen, setRoleUsageOpen] = useState<boolean>(false)
  const [roleUsageRoleId, setRoleUsageRoleId] = useState<number | null>(null)

  const visibleRoles = useMemo(() => {
    const query = roleSearch.trim().toLowerCase()
    if (!query) return roles
    return roles.filter((role) => role.name.toLowerCase().includes(query))
  }, [roleSearch, roles])

  const capabilityOptions = useMemo(() => (
    capabilities.map((cap) => ({
      label: cap.exists ? cap.code : `${cap.code} ${t(($) => $.roles.capabilityMissingSuffix)}`,
      value: cap.code,
    }))
  ), [capabilities, t])

  const selectedRoleForEditor = roleEditorRoleId
    ? roles.find((role) => role.id === roleEditorRoleId) ?? null
    : null

  const roleEditorDiff = useMemo(() => {
    const current = new Set(selectedRoleForEditor?.permission_codes ?? [])
    const next = new Set(roleEditorPermissionCodes ?? [])
    const added = Array.from(next).filter((code) => !current.has(code)).sort()
    const removed = Array.from(current).filter((code) => !next.has(code)).sort()
    return {
      currentCount: current.size,
      nextCount: next.size,
      added,
      removed,
    }
  }, [roleEditorPermissionCodes, selectedRoleForEditor])

  const renderCodeTags = (codes: string[]) => {
    if (codes.length === 0) {
      return <Tag color="default">-</Tag>
    }

    const max = 12
    const shown = codes.slice(0, max)
    return (
      <Space size={4} wrap>
        {shown.map((code) => (
          <Tag key={code}>{code}</Tag>
        ))}
        {codes.length > max && (
          <Text type="secondary">{t(($) => $.roles.more, { count: codes.length - max })}</Text>
        )}
      </Space>
    )
  }

  const rolesColumns: ColumnsType<RbacRole> = useMemo(
    () => [
      { title: t(($) => $.roles.columns.role), dataIndex: 'name', key: 'name' },
      { title: t(($) => $.roles.columns.users), dataIndex: 'users_count', key: 'users_count' },
      { title: t(($) => $.roles.columns.permissions), dataIndex: 'permissions_count', key: 'permissions_count' },
      {
        title: t(($) => $.roles.columns.actions),
        key: 'actions',
        render: (_: unknown, row) => (
          <Space size="small">
            <Button
              size="small"
              onClick={() => {
                setRoleUsageRoleId(row.id)
                setRoleUsageOpen(true)
              }}
            >
              {t(($) => $.roles.actions.usage)}
            </Button>
            <Button
              size="small"
              onClick={() => {
                setRoleEditorRoleId(row.id)
                setRoleEditorPermissionCodes(row.permission_codes)
                setRoleEditorOpen(true)
              }}
            >
              {t(($) => $.roles.actions.permissions)}
            </Button>
            <Button
              size="small"
              onClick={() => {
                setCloneRoleSourceRoleId(row.id)
                setCloneRoleName(`${row.name} ${t(($) => $.roles.cloneNameSuffix)}`)
                setCloneRoleOpen(true)
              }}
            >
              {t(($) => $.roles.actions.clone)}
            </Button>
            <Button
              size="small"
              onClick={() => {
                setRenameRoleRoleId(row.id)
                setRenameRoleName(row.name)
                setRenameRoleOpen(true)
              }}
            >
              {t(($) => $.roles.actions.rename)}
            </Button>
            <Button
              danger
              size="small"
              onClick={() => {
                setDeleteRoleRoleId(row.id)
                setDeleteRoleOpen(true)
              }}
            >
              {t(($) => $.roles.actions.delete)}
            </Button>
          </Space>
        ),
      },
    ],
    [t]
  )

  const roleUsageEnabled = canManageRbac && Boolean(roleUsageRoleId)
  const roleUsageClustersQuery = useClusterGroupPermissions({ group_id: roleUsageRoleId ?? undefined, limit: 1, offset: 0 }, { enabled: roleUsageEnabled })
  const roleUsageDatabasesQuery = useDatabaseGroupPermissions({ group_id: roleUsageRoleId ?? undefined, limit: 1, offset: 0 }, { enabled: roleUsageEnabled })
  const roleUsageOperationTemplatesQuery = useOperationTemplateGroupPermissions({ group_id: roleUsageRoleId ?? undefined, limit: 1, offset: 0 }, { enabled: roleUsageEnabled })
  const roleUsageWorkflowTemplatesQuery = useWorkflowTemplateGroupPermissions({ group_id: roleUsageRoleId ?? undefined, limit: 1, offset: 0 }, { enabled: roleUsageEnabled })
  const roleUsageArtifactsQuery = useArtifactGroupPermissions({ group_id: roleUsageRoleId ?? undefined, limit: 1, offset: 0 }, { enabled: roleUsageEnabled })

  const selectedRoleForUsage = useMemo(() => (
    roles.find((role) => role.id === roleUsageRoleId) ?? null
  ), [roles, roleUsageRoleId])

  const roleUsageTotals = useMemo(() => {
    const clusters = typeof roleUsageClustersQuery.data?.total === 'number' ? roleUsageClustersQuery.data.total : 0
    const databases = typeof roleUsageDatabasesQuery.data?.total === 'number' ? roleUsageDatabasesQuery.data.total : 0
    const operationTemplates = typeof roleUsageOperationTemplatesQuery.data?.total === 'number' ? roleUsageOperationTemplatesQuery.data.total : 0
    const workflowTemplates = typeof roleUsageWorkflowTemplatesQuery.data?.total === 'number' ? roleUsageWorkflowTemplatesQuery.data.total : 0
    const artifacts = typeof roleUsageArtifactsQuery.data?.total === 'number' ? roleUsageArtifactsQuery.data.total : 0
    return { clusters, databases, operationTemplates, workflowTemplates, artifacts }
  }, [
    roleUsageArtifactsQuery.data?.total,
    roleUsageClustersQuery.data?.total,
    roleUsageDatabasesQuery.data?.total,
    roleUsageOperationTemplatesQuery.data?.total,
    roleUsageWorkflowTemplatesQuery.data?.total,
  ])

  const roleUsageLoading = roleUsageClustersQuery.isFetching
    || roleUsageDatabasesQuery.isFetching
    || roleUsageOperationTemplatesQuery.isFetching
    || roleUsageWorkflowTemplatesQuery.isFetching
    || roleUsageArtifactsQuery.isFetching

  const roleUsageHasError = Boolean(
    roleUsageClustersQuery.error
    || roleUsageDatabasesQuery.error
    || roleUsageOperationTemplatesQuery.error
    || roleUsageWorkflowTemplatesQuery.error
    || roleUsageArtifactsQuery.error
  )

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title={t(($) => $.roles.createCardTitle)} size="small">
        <Form
          form={createRoleForm}
          layout="inline"
          onFinish={(values) => createRole.mutate(values, { onSuccess: () => createRoleForm.resetFields() })}
        >
          <Form.Item name="name" rules={[{ required: true, message: t(($) => $.roles.roleNameRequired) }]}>
            <Input placeholder={t(($) => $.roles.roleNamePlaceholder)} style={{ width: 240 }} />
          </Form.Item>
          <Form.Item name="reason" rules={[{ required: true, message: t(($) => $.roles.reasonRequired) }]}>
            <Input placeholder={t(($) => $.roles.reasonPlaceholder)} style={{ width: 320 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={createRole.isPending}>
              {t(($) => $.roles.create)}
            </Button>
          </Form.Item>
          <Form.Item>
            <Button onClick={() => rolesQuery.refetch()} loading={rolesQuery.isFetching}>
              {t(($) => $.roles.refresh)}
            </Button>
          </Form.Item>
        </Form>
        {createRole.error && (
          <Alert
            style={{ marginTop: 12 }}
            type="warning"
            message={t(($) => $.roles.createFailed)}
          />
        )}
      </Card>

      <Card title={t(($) => $.roles.listTitle)} size="small">
        <Space wrap style={{ marginBottom: 12 }}>
          <Input
            placeholder={t(($) => $.roles.searchPlaceholder)}
            style={{ width: 280 }}
            value={roleSearch}
            onChange={(e) => setRoleSearch(e.target.value)}
          />
          <Button onClick={() => rolesQuery.refetch()} loading={rolesQuery.isFetching}>
            {t(($) => $.roles.refresh)}
          </Button>
        </Space>
        {rolesQuery.error && (
          <Alert
            style={{ marginBottom: 12 }}
            type="warning"
            message={t(($) => $.roles.loadFailed)}
          />
        )}
        {!rolesQuery.isLoading && !rolesQuery.error && visibleRoles.length === 0 ? (
          <Alert
            type="info"
            showIcon
            message={roleSearch.trim() ? t(($) => $.roles.emptyFilteredTitle) : t(($) => $.roles.emptyTitle)}
            description={roleSearch.trim() ? t(($) => $.roles.emptyFilteredDescription) : t(($) => $.roles.emptyDescription)}
          />
        ) : (
          <Table
            size="small"
            columns={rolesColumns}
            dataSource={visibleRoles}
            loading={rolesQuery.isLoading}
            rowKey="id"
            pagination={{ pageSize: 50 }}
          />
        )}
      </Card>

      <Modal
        title={selectedRoleForUsage
          ? t(($) => $.roles.usageModalTitle, { name: selectedRoleForUsage.name })
          : t(($) => $.roles.usageModalFallbackTitle)}
        open={roleUsageOpen}
        onCancel={() => {
          setRoleUsageOpen(false)
          setRoleUsageRoleId(null)
        }}
        footer={(
          <Space>
            <Button
              type="primary"
              disabled={!roleUsageRoleId || !onOpenAssignmentsForRole}
              onClick={() => {
                if (!roleUsageRoleId) return
                onOpenAssignmentsForRole?.(roleUsageRoleId)
                setRoleUsageOpen(false)
                setRoleUsageRoleId(null)
              }}
            >
              {t(($) => $.roles.openAssignments)}
            </Button>
            <Button onClick={() => {
              setRoleUsageOpen(false)
              setRoleUsageRoleId(null)
            }}>{t(($) => $.roles.close)}</Button>
          </Space>
        )}
      >
        {!selectedRoleForUsage && (
          <Alert
            type="warning"
            message={t(($) => $.roles.notFound)}
          />
        )}

        {selectedRoleForUsage && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {roleUsageHasError && (
              <Alert
                type="warning"
                message={t(($) => $.roles.usageLoadFailed)}
              />
            )}

            <Space wrap>
              <Tag>{t(($) => $.roles.usageUsersTag, { count: selectedRoleForUsage.users_count })}</Tag>
              <Tag>{t(($) => $.roles.usagePermissionsTag, { count: selectedRoleForUsage.permissions_count })}</Tag>
            </Space>

            <div>
              <Text strong>{t(($) => $.roles.assignmentsTitle)}</Text>
              <Space wrap style={{ marginTop: 8 }}>
                <Tag>{t(($) => $.roles.assignmentTags.clusters, { count: roleUsageTotals.clusters })}</Tag>
                <Tag>{t(($) => $.roles.assignmentTags.databases, { count: roleUsageTotals.databases })}</Tag>
                <Tag>{t(($) => $.roles.assignmentTags.operationTemplates, { count: roleUsageTotals.operationTemplates })}</Tag>
                <Tag>{t(($) => $.roles.assignmentTags.workflowTemplates, { count: roleUsageTotals.workflowTemplates })}</Tag>
                <Tag>{t(($) => $.roles.assignmentTags.artifacts, { count: roleUsageTotals.artifacts })}</Tag>
              </Space>
              {roleUsageLoading && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">{t(($) => $.roles.loading)}</Text>
                </div>
              )}
            </div>

            <Text type="secondary">
              {t(($) => $.roles.usageNote)}
            </Text>
          </Space>
        )}
      </Modal>

      <ReasonModal
        title={t(($) => $.roles.cloneModalTitle)}
        open={cloneRoleOpen}
        okText={t(($) => $.roles.create)}
        cancelText={t(($) => $.userRoles.cancel)}
        reasonPlaceholder={t(($) => $.roles.reasonPlaceholder)}
        requiredMessage={t(($) => $.roles.reasonRequired)}
        onCancel={() => {
          setCloneRoleOpen(false)
          setCloneRoleSourceRoleId(null)
        }}
        okButtonProps={{
          disabled: !cloneRoleSourceRoleId || !cloneRoleName.trim(),
          loading: createRole.isPending || setRoleCapabilities.isPending,
        }}
        onOk={async (reason) => {
          if (!cloneRoleSourceRoleId) return
          const source = roles.find((role) => role.id === cloneRoleSourceRoleId)
          if (!source) {
            message.error(t(($) => $.roles.sourceRoleNotFound))
            return
          }
          const name = cloneRoleName.trim()
          if (!name) {
            message.error(t(($) => $.roles.roleNameRequired))
            return
          }

          try {
            const created = await createRole.mutateAsync({ name, reason })
            await setRoleCapabilities.mutateAsync({
              group_id: created.id,
              permission_codes: source.permission_codes,
              mode: 'replace',
              reason,
            })
            message.success(t(($) => $.roles.clonedSuccess, { name: created.name, id: String(created.id) }))
            setCloneRoleOpen(false)
            setCloneRoleSourceRoleId(null)
          } catch {
            message.error(t(($) => $.roles.cloneFailed))
          }
        }}
      >
        <Alert
          type="info"
          message={cloneRoleSourceRoleId
            ? t(($) => $.roles.sourceRoleId, { id: String(cloneRoleSourceRoleId) })
            : t(($) => $.roles.selectSourceRole)}
        />
        <Input
          placeholder={t(($) => $.roles.newRoleNamePlaceholder)}
          value={cloneRoleName}
          onChange={(e) => setCloneRoleName(e.target.value)}
        />
      </ReasonModal>

      <ReasonModal
        title={selectedRoleForEditor
          ? t(($) => $.roles.permissionsModalTitle, { name: selectedRoleForEditor.name })
          : t(($) => $.roles.permissionsModalFallbackTitle)}
        open={roleEditorOpen}
        okText={t(($) => $.dbmsUsers.form.save)}
        cancelText={t(($) => $.userRoles.cancel)}
        reasonPlaceholder={t(($) => $.roles.reasonPlaceholder)}
        requiredMessage={t(($) => $.roles.reasonRequired)}
        onCancel={() => setRoleEditorOpen(false)}
        okButtonProps={{
          disabled: !roleEditorRoleId,
          loading: setRoleCapabilities.isPending,
        }}
        onOk={async (reason) => {
          if (!roleEditorRoleId) return
          await setRoleCapabilities.mutateAsync({
            group_id: roleEditorRoleId,
            permission_codes: roleEditorPermissionCodes,
            mode: 'replace',
            reason,
          })
          setRoleEditorOpen(false)
        }}
      >
        {!selectedRoleForEditor ? (
          <Alert
            style={{ marginBottom: 12 }}
            type="warning"
            showIcon
            message={t(($) => $.roles.permissionsNotFound)}
          />
        ) : (
          <Alert
            style={{ marginBottom: 12 }}
            type={(roleEditorDiff.added.length > 0 || roleEditorDiff.removed.length > 0) ? 'info' : 'success'}
            showIcon
            message={(roleEditorDiff.added.length > 0 || roleEditorDiff.removed.length > 0)
              ? t(($) => $.roles.permissionsChanged, {
                added: String(roleEditorDiff.added.length),
                removed: String(roleEditorDiff.removed.length),
              })
              : t(($) => $.roles.permissionsUnchanged)}
            description={(
              <Space direction="vertical" size={4}>
                <div>
                  <Text type="secondary">{t(($) => $.roles.diffLabels.current)}</Text> <Text>{roleEditorDiff.currentCount}</Text>
                </div>
                <div>
                  <Text type="secondary">{t(($) => $.roles.diffLabels.selected)}</Text> <Text>{roleEditorDiff.nextCount}</Text>
                </div>
                <div>
                  <Text type="secondary">{t(($) => $.roles.diffLabels.added)}</Text> {renderCodeTags(roleEditorDiff.added)}
                </div>
                <div>
                  <Text type="secondary">{t(($) => $.roles.diffLabels.removed)}</Text> {renderCodeTags(roleEditorDiff.removed)}
                </div>
              </Space>
            )}
          />
        )}
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          placeholder={t(($) => $.roles.permissionsPlaceholder)}
          options={capabilityOptions}
          value={roleEditorPermissionCodes}
          onChange={(value) => setRoleEditorPermissionCodes(value)}
          showSearch
          optionFilterProp="label"
        />
      </ReasonModal>

      <ReasonModal
        title={t(($) => $.roles.renameModalTitle)}
        open={renameRoleOpen}
        okText={t(($) => $.dbmsUsers.form.save)}
        cancelText={t(($) => $.userRoles.cancel)}
        reasonPlaceholder={t(($) => $.roles.reasonPlaceholder)}
        requiredMessage={t(($) => $.roles.reasonRequired)}
        onCancel={() => setRenameRoleOpen(false)}
        okButtonProps={{
          disabled: !renameRoleRoleId || !renameRoleName.trim(),
          loading: updateRole.isPending,
        }}
        onOk={async (reason) => {
          if (!renameRoleRoleId) return
          const name = renameRoleName.trim()
          if (!name) {
            message.error(t(($) => $.roles.roleNameRequired))
            return
          }
          await updateRole.mutateAsync({ group_id: renameRoleRoleId, name, reason })
          setRenameRoleOpen(false)
        }}
      >
        <Input
          placeholder={t(($) => $.roles.roleNameInputPlaceholder)}
          value={renameRoleName}
          onChange={(e) => setRenameRoleName(e.target.value)}
        />
      </ReasonModal>

      <ReasonModal
        title={t(($) => $.roles.deleteModalTitle)}
        open={deleteRoleOpen}
        okText={t(($) => $.roles.actions.delete)}
        cancelText={t(($) => $.userRoles.cancel)}
        reasonPlaceholder={t(($) => $.roles.reasonPlaceholder)}
        requiredMessage={t(($) => $.roles.reasonRequired)}
        okButtonProps={{ danger: true, disabled: !deleteRoleRoleId, loading: deleteRole.isPending }}
        onCancel={() => setDeleteRoleOpen(false)}
        onOk={async (reason) => {
          if (!deleteRoleRoleId) return
          await deleteRole.mutateAsync({ group_id: deleteRoleRoleId, reason })
          setDeleteRoleOpen(false)
        }}
      >
        <Alert
          type="warning"
          message={t(($) => $.roles.deleteWarning)}
        />
      </ReasonModal>
    </Space>
  )
}
