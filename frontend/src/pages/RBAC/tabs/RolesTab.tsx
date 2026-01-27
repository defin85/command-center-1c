import { useMemo, useState } from 'react'
import { App, Alert, Button, Card, Form, Input, Space, Table, Typography, Tag, Select, Modal } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useArtifactGroupPermissions, useCapabilities, useClusterGroupPermissions, useCreateRole, useDatabaseGroupPermissions, useDeleteRole, useOperationTemplateGroupPermissions, useRoles, useSetRoleCapabilities, useUpdateRole, useWorkflowTemplateGroupPermissions, type Capability, type RbacRole } from '../../../api/queries/rbac'
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
    capabilities.map((cap) => ({ label: cap.exists ? cap.code : `${cap.code} (нет)`, value: cap.code }))
  ), [capabilities])

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
          <Text type="secondary">+{codes.length - max} ещё</Text>
        )}
      </Space>
    )
  }

  const rolesColumns: ColumnsType<RbacRole> = useMemo(
    () => [
      { title: 'Роль', dataIndex: 'name', key: 'name' },
      { title: 'Пользователи', dataIndex: 'users_count', key: 'users_count' },
      { title: 'Права', dataIndex: 'permissions_count', key: 'permissions_count' },
      {
        title: 'Действия',
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
              Использование
            </Button>
            <Button
              size="small"
              onClick={() => {
                setRoleEditorRoleId(row.id)
                setRoleEditorPermissionCodes(row.permission_codes)
                setRoleEditorOpen(true)
              }}
            >
              Права
            </Button>
            <Button
              size="small"
              onClick={() => {
                setCloneRoleSourceRoleId(row.id)
                setCloneRoleName(`${row.name} копия`)
                setCloneRoleOpen(true)
              }}
            >
              Клонировать
            </Button>
            <Button
              size="small"
              onClick={() => {
                setRenameRoleRoleId(row.id)
                setRenameRoleName(row.name)
                setRenameRoleOpen(true)
              }}
            >
              Переименовать
            </Button>
            <Button
              danger
              size="small"
              onClick={() => {
                setDeleteRoleRoleId(row.id)
                setDeleteRoleOpen(true)
              }}
            >
              Удалить
            </Button>
          </Space>
        ),
      },
    ],
    []
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
      <Card title="Создать роль" size="small">
        <Form
          form={createRoleForm}
          layout="inline"
          onFinish={(values) => createRole.mutate(values, { onSuccess: () => createRoleForm.resetFields() })}
        >
          <Form.Item name="name" rules={[{ required: true, message: 'Укажите название роли' }]}>
            <Input placeholder="Название роли" style={{ width: 240 }} />
          </Form.Item>
          <Form.Item name="reason" rules={[{ required: true, message: 'Укажите причину' }]}>
            <Input placeholder="Причина (обязательно)" style={{ width: 320 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={createRole.isPending}>
              Создать
            </Button>
          </Form.Item>
          <Form.Item>
            <Button onClick={() => rolesQuery.refetch()} loading={rolesQuery.isFetching}>
              Обновить
            </Button>
          </Form.Item>
        </Form>
        {createRole.error && (
          <Alert
            style={{ marginTop: 12 }}
            type="warning"
            message="Не удалось создать роль"
          />
        )}
      </Card>

      <Card title="Роли" size="small">
        <Space wrap style={{ marginBottom: 12 }}>
          <Input
            placeholder="Поиск роли"
            style={{ width: 280 }}
            value={roleSearch}
            onChange={(e) => setRoleSearch(e.target.value)}
          />
          <Button onClick={() => rolesQuery.refetch()} loading={rolesQuery.isFetching}>
            Обновить
          </Button>
        </Space>
        {rolesQuery.error && (
          <Alert
            style={{ marginBottom: 12 }}
            type="warning"
            message="Не удалось загрузить роли"
          />
        )}
        {!rolesQuery.isLoading && !rolesQuery.error && visibleRoles.length === 0 ? (
          <Alert
            type="info"
            showIcon
            message={roleSearch.trim() ? 'Роли не найдены' : 'Ролей пока нет'}
            description={roleSearch.trim() ? 'Попробуйте изменить поиск.' : 'Создайте роль выше.'}
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
        title={selectedRoleForUsage ? `Использование роли: ${selectedRoleForUsage.name}` : 'Использование роли'}
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
              Открыть в "Назначения"
            </Button>
            <Button onClick={() => {
              setRoleUsageOpen(false)
              setRoleUsageRoleId(null)
            }}>Закрыть</Button>
          </Space>
        )}
      >
        {!selectedRoleForUsage && (
          <Alert
            type="warning"
            message="Роль не найдена"
          />
        )}

        {selectedRoleForUsage && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {roleUsageHasError && (
              <Alert
                type="warning"
                message="Не удалось загрузить использование роли"
              />
            )}

            <Space wrap>
              <Tag>Пользователей: {selectedRoleForUsage.users_count}</Tag>
              <Tag>Прав: {selectedRoleForUsage.permissions_count}</Tag>
            </Space>

            <div>
              <Text strong>Назначения:</Text>
              <Space wrap style={{ marginTop: 8 }}>
                <Tag>Кластеры: {roleUsageTotals.clusters}</Tag>
                <Tag>Базы: {roleUsageTotals.databases}</Tag>
                <Tag>Шаблоны операций: {roleUsageTotals.operationTemplates}</Tag>
                <Tag>Шаблоны рабочих процессов: {roleUsageTotals.workflowTemplates}</Tag>
                <Tag>Артефакты: {roleUsageTotals.artifacts}</Tag>
              </Space>
              {roleUsageLoading && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">Загрузка…</Text>
                </div>
              )}
            </div>

            <Text type="secondary">
              Подсчёт основан на `list-*-group-permissions` (total).
            </Text>
          </Space>
        )}
      </Modal>

      <ReasonModal
        title="Клонировать роль"
        open={cloneRoleOpen}
        okText="Создать"
        cancelText="Отмена"
        reasonPlaceholder="Причина (обязательно)"
        requiredMessage="Укажите причину"
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
            message.error('Исходная роль не найдена')
            return
          }
          const name = cloneRoleName.trim()
          if (!name) {
            message.error('Укажите имя роли')
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
            message.success(`Роль склонирована: ${created.name} #${created.id}`)
            setCloneRoleOpen(false)
            setCloneRoleSourceRoleId(null)
          } catch {
            message.error('Не удалось клонировать роль')
          }
        }}
      >
        <Alert
          type="info"
          message={cloneRoleSourceRoleId ? `ID исходной роли: ${cloneRoleSourceRoleId}` : 'Выберите исходную роль'}
        />
        <Input
          placeholder="Название новой роли"
          value={cloneRoleName}
          onChange={(e) => setCloneRoleName(e.target.value)}
        />
      </ReasonModal>

      <ReasonModal
        title={selectedRoleForEditor ? `Права роли: ${selectedRoleForEditor.name}` : 'Права роли'}
        open={roleEditorOpen}
        okText="Сохранить"
        cancelText="Отмена"
        reasonPlaceholder="Причина (обязательно)"
        requiredMessage="Укажите причину"
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
            message="Роль не найдена"
          />
        ) : (
          <Alert
            style={{ marginBottom: 12 }}
            type={(roleEditorDiff.added.length > 0 || roleEditorDiff.removed.length > 0) ? 'info' : 'success'}
            showIcon
            message={(roleEditorDiff.added.length > 0 || roleEditorDiff.removed.length > 0)
              ? `Изменения прав: +${roleEditorDiff.added.length} / -${roleEditorDiff.removed.length}`
              : 'Изменений нет'}
            description={(
              <Space direction="vertical" size={4}>
                <div>
                  <Text type="secondary">Текущих:</Text> <Text>{roleEditorDiff.currentCount}</Text>
                </div>
                <div>
                  <Text type="secondary">Выбрано:</Text> <Text>{roleEditorDiff.nextCount}</Text>
                </div>
                <div>
                  <Text type="secondary">Добавится:</Text> {renderCodeTags(roleEditorDiff.added)}
                </div>
                <div>
                  <Text type="secondary">Уберётся:</Text> {renderCodeTags(roleEditorDiff.removed)}
                </div>
              </Space>
            )}
          />
        )}
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          placeholder="Права"
          options={capabilityOptions}
          value={roleEditorPermissionCodes}
          onChange={(value) => setRoleEditorPermissionCodes(value)}
          showSearch
          optionFilterProp="label"
        />
      </ReasonModal>

      <ReasonModal
        title="Переименовать роль"
        open={renameRoleOpen}
        okText="Сохранить"
        cancelText="Отмена"
        reasonPlaceholder="Причина (обязательно)"
        requiredMessage="Укажите причину"
        onCancel={() => setRenameRoleOpen(false)}
        okButtonProps={{
          disabled: !renameRoleRoleId || !renameRoleName.trim(),
          loading: updateRole.isPending,
        }}
        onOk={async (reason) => {
          if (!renameRoleRoleId) return
          const name = renameRoleName.trim()
          if (!name) {
            message.error('Укажите имя роли')
            return
          }
          await updateRole.mutateAsync({ group_id: renameRoleRoleId, name, reason })
          setRenameRoleOpen(false)
        }}
      >
        <Input placeholder="Имя роли" value={renameRoleName} onChange={(e) => setRenameRoleName(e.target.value)} />
      </ReasonModal>

      <ReasonModal
        title="Удалить роль"
        open={deleteRoleOpen}
        okText="Удалить"
        cancelText="Отмена"
        reasonPlaceholder="Причина (обязательно)"
        requiredMessage="Укажите причину"
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
          message="Роль будет удалена, если нет участников/прав/назначений."
        />
      </ReasonModal>
    </Space>
  )
}
