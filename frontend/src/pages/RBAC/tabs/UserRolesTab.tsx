import { useCallback, useMemo, useState } from 'react'
import { App, Alert, Badge, Button, Card, Form, Input, Modal, Popover, Segmented, Select, Space, Table, Typography, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { useRbacUsersWithRoles, useRoles, useSetUserRoles, type RbacRole, type UserWithRolesRef } from '../../../api/queries/rbac'
import { confirmWithTracking } from '../../../observability/confirmWithTracking'

const { Text } = Typography

type UserRolesViewMode = 'user-to-roles' | 'role-to-users'

const LS_RBAC_USER_ROLES_TABLE_HINT_DISMISSED = 'cc1c_rbac_user_roles_table_hint_dismissed'
const EMPTY_ROLES: RbacRole[] = []

export function UserRolesTab(props: { canManageRbac: boolean }) {
  const { canManageRbac } = props
  const { modal, message } = App.useApp()

  const rolesQuery = useRoles({ limit: 500, offset: 0 }, { enabled: canManageRbac })
  const roles = rolesQuery.data?.roles ?? EMPTY_ROLES
  const roleNameById = useMemo(() => (
    new Map(roles.map((role) => [role.id, role.name]))
  ), [roles])
  const roleOptions = useMemo(() => (
    roles.map((role) => ({ label: `${role.name} #${role.id}`, value: role.id }))
  ), [roles])

  const [userRolesTableHintDismissed, setUserRolesTableHintDismissed] = useState<boolean>(() => (
    localStorage.getItem(LS_RBAC_USER_ROLES_TABLE_HINT_DISMISSED) === '1'
  ))

  const [userRolesViewMode, setUserRolesViewMode] = useState<UserRolesViewMode>('user-to-roles')
  const [userRolesList, setUserRolesList] = useState<{
    search: string
    role_id?: number
    page: number
    pageSize: number
  }>({ search: '', page: 1, pageSize: 50 })

  const selectedRoleForUserRoles = useMemo(() => (
    typeof userRolesList.role_id === 'number'
      ? roles.find((role) => role.id === userRolesList.role_id) ?? null
      : null
  ), [roles, userRolesList.role_id])

  const debouncedUserRolesSearch = useDebouncedValue(userRolesList.search, 300)
  const userRolesUsersQuery = useRbacUsersWithRoles({
    search: debouncedUserRolesSearch || undefined,
    role_id: userRolesList.role_id,
    limit: userRolesList.pageSize,
    offset: (userRolesList.page - 1) * userRolesList.pageSize,
  }, {
    enabled: canManageRbac && (
      userRolesViewMode === 'user-to-roles' || Boolean(userRolesList.role_id)
    ),
  })

  const userRolesUsers = userRolesUsersQuery.data?.users ?? []
  const totalUserRolesUsers = typeof userRolesUsersQuery.data?.total === 'number'
    ? userRolesUsersQuery.data.total
    : userRolesUsers.length

  const setUserRoles = useSetUserRoles()
  const [userRolesEditorForm] = Form.useForm<{
    mode?: 'replace' | 'add' | 'remove'
    group_ids?: number[]
    reason: string
  }>()
  const [userRolesEditorOpen, setUserRolesEditorOpen] = useState<boolean>(false)
  const [userRolesEditorUser, setUserRolesEditorUser] = useState<UserWithRolesRef | null>(null)

  const userRolesEditorMode = Form.useWatch('mode', userRolesEditorForm)
  const userRolesEditorGroupIds = Form.useWatch('group_ids', userRolesEditorForm)
  const userRolesEditorReason = Form.useWatch('reason', userRolesEditorForm)

  const userRolesEditorModeValue = (userRolesEditorMode ?? 'replace') as 'replace' | 'add' | 'remove'
  const userRolesEditorSelectedIds = Array.isArray(userRolesEditorGroupIds)
    ? userRolesEditorGroupIds.filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
    : []
  const userRolesEditorSelectedIdsUnique = Array.from(new Set(userRolesEditorSelectedIds)).sort((a, b) => a - b)
  const userRolesEditorTrimmedReason = typeof userRolesEditorReason === 'string' ? userRolesEditorReason.trim() : ''
  const userRolesEditorCanSubmit = Boolean(userRolesEditorUser)
    && Boolean(userRolesEditorTrimmedReason)
    && (userRolesEditorModeValue === 'replace' || userRolesEditorSelectedIdsUnique.length > 0)

  const openUserRolesEditor = useCallback((user: UserWithRolesRef) => {
    setUserRolesEditorUser(user)
    setUserRolesEditorOpen(true)
    userRolesEditorForm.setFieldsValue({
      mode: 'replace',
      group_ids: (user.roles ?? []).map((r) => r.id).sort((a, b) => a - b),
      reason: '',
    })
  }, [userRolesEditorForm])

  const renderLimitedRoleTags = useCallback((roles: Array<{ id: number; name: string }>) => {
    if (!roles || roles.length === 0) {
      return <Tag color="default">-</Tag>
    }

    const shown = roles.slice(0, 3)
    const rest = roles.slice(3)

    const content = (
      <Space size={4} wrap>
        {roles.map((role) => (
          <Tag key={role.id}>{role.name}</Tag>
        ))}
      </Space>
    )

    return (
      <Space size={4} wrap>
        {shown.map((role) => (
          <Tag key={role.id}>{role.name}</Tag>
        ))}
        {rest.length > 0 && (
          <Popover content={content} title="Роли" trigger="click">
            <Button type="link" size="small" style={{ paddingInline: 0, height: 22 }}>
              ещё {rest.length}
            </Button>
          </Popover>
        )}
      </Space>
    )
  }, [])

  const renderRoleIdTags = useCallback((ids: number[]) => {
    if (ids.length === 0) {
      return <Tag color="default">-</Tag>
    }

    const max = 10
    const shown = ids.slice(0, max)
    return (
      <Space size={4} wrap>
        {shown.map((id) => (
          <Tag key={id}>{roleNameById.get(id) ?? `#${id}`}</Tag>
        ))}
        {ids.length > max && (
          <Text type="secondary">+{ids.length - max} ещё</Text>
        )}
      </Space>
    )
  }, [roleNameById])

  const userRolesColumns: ColumnsType<UserWithRolesRef> = useMemo(() => [
    {
      title: 'Пользователь',
      key: 'user',
      render: (_: unknown, row) => (
        <span>
          {row.username} <Text type="secondary">#{row.id}</Text>
        </span>
      ),
    },
    {
      title: 'Роли',
      key: 'roles',
      render: (_: unknown, row) => {
        const roles = row.roles ?? []
        return (
          <Space size={8} wrap>
            <Badge count={roles.length} showZero />
            {renderLimitedRoleTags(roles)}
          </Space>
        )
      },
    },
    {
      title: '',
      key: 'actions',
      width: 120,
      render: (_: unknown, row) => (
        <Button size="small" data-testid={`rbac-user-roles-edit-${row.id}`} onClick={() => openUserRolesEditor(row)}>
          Изменить
        </Button>
      ),
    },
  ], [openUserRolesEditor, renderLimitedRoleTags])

  return (
    <>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card title="Роли пользователей" size="small">
          <Space wrap style={{ marginBottom: 12 }}>
            <Segmented
              value={userRolesViewMode}
              options={[
                { label: 'Пользователь → Роли', value: 'user-to-roles' },
                { label: 'Роль → Пользователи', value: 'role-to-users' },
              ]}
              onChange={(value) => {
                setUserRolesViewMode(value as UserRolesViewMode)
                setUserRolesList((prev) => ({ ...prev, page: 1 }))
              }}
            />

            <Input
              placeholder="Поиск пользователя"
              style={{ width: 240 }}
              value={userRolesList.search}
              onChange={(e) => setUserRolesList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
            />

            <Select
              style={{ width: 360 }}
              placeholder={userRolesViewMode === 'role-to-users' ? 'Роль (обязательно)' : 'Фильтр по роли (опционально)'}
              allowClear={userRolesViewMode !== 'role-to-users'}
              value={userRolesList.role_id}
              onChange={(value) => setUserRolesList((prev) => ({ ...prev, role_id: value ?? undefined, page: 1 }))}
              options={roleOptions}
              showSearch
              optionFilterProp="label"
            />

            {userRolesViewMode === 'role-to-users' && selectedRoleForUserRoles && (
              <Space size={6}>
                <Text type="secondary">Пользователей в роли:</Text>
                <Badge count={selectedRoleForUserRoles.users_count} showZero />
              </Space>
            )}

            <Button
              onClick={() => userRolesUsersQuery.refetch()}
              loading={userRolesUsersQuery.isFetching}
              disabled={userRolesViewMode === 'role-to-users' && !userRolesList.role_id}
            >
              Обновить
            </Button>

            {userRolesTableHintDismissed && (
              <Button
                type="link"
                size="small"
                style={{ paddingInline: 0, height: 22 }}
                onClick={() => {
                  localStorage.removeItem(LS_RBAC_USER_ROLES_TABLE_HINT_DISMISSED)
                  setUserRolesTableHintDismissed(false)
                }}
              >
                Показать подсказку
              </Button>
            )}
          </Space>

          {!userRolesTableHintDismissed && (
            <Alert
              style={{ marginBottom: 12 }}
              type="info"
              showIcon
              closable
              message="Как читать таблицу"
              description={(
                <Space direction="vertical" size={4}>
                  <Text>
                    <Text code>Пользователь → Роли</Text>: строка = пользователь, в колонке “Роли” показываются первые 3 (остальное — через “ещё N”).
                  </Text>
                  <Text>
                    <Text code>Роль → Пользователи</Text>: выберите роль — появится список пользователей с этой ролью.
                  </Text>
                  <Text type="secondary">
                    “Изменить” открывает назначение ролей. Перед применением показывается список изменений; режим “Заменить” с пустым списком снимает все роли.
                  </Text>
                </Space>
              )}
              afterClose={() => {
                localStorage.setItem(LS_RBAC_USER_ROLES_TABLE_HINT_DISMISSED, '1')
                setUserRolesTableHintDismissed(true)
              }}
            />
          )}

          {userRolesViewMode === 'role-to-users' && !userRolesList.role_id && (
            <Alert
              style={{ marginBottom: 12 }}
              type="info"
              showIcon
              message="Выберите роль"
              description="Режим “Роль → Пользователи” показывает пользователей, у которых назначена выбранная роль."
            />
          )}

          {userRolesUsersQuery.error && (
            <Alert
              style={{ marginBottom: 12 }}
              type="warning"
              showIcon
              message="Не удалось загрузить пользователей и роли"
            />
          )}

          <Table
            size="small"
            columns={userRolesColumns}
            dataSource={(userRolesViewMode === 'role-to-users' && !userRolesList.role_id) ? [] : userRolesUsers}
            loading={userRolesUsersQuery.isFetching}
            rowKey="id"
            pagination={{
              current: userRolesList.page,
              pageSize: userRolesList.pageSize,
              total: (userRolesViewMode === 'role-to-users' && !userRolesList.role_id) ? 0 : totalUserRolesUsers,
              showSizeChanger: true,
              onChange: (page, pageSize) => setUserRolesList((prev) => ({ ...prev, page, pageSize })),
            }}
          />
        </Card>
      </Space>

      <Modal
        title={userRolesEditorUser ? `Роли пользователя: ${userRolesEditorUser.username} #${userRolesEditorUser.id}` : 'Роли пользователя'}
        open={userRolesEditorOpen}
        width={760}
        okText="Продолжить"
        cancelText="Отмена"
        okButtonProps={{
          'data-testid': 'rbac-user-roles-editor-ok',
          disabled: !userRolesEditorCanSubmit,
          loading: setUserRoles.isPending,
        }}
        onCancel={() => {
          if (setUserRoles.isPending) return
          setUserRolesEditorOpen(false)
          setUserRolesEditorUser(null)
          userRolesEditorForm.resetFields()
        }}
        onOk={() => userRolesEditorForm.submit()}
        destroyOnHidden
      >
        <div data-testid="rbac-user-roles-editor">
          {!userRolesEditorUser ? (
            <Alert type="warning" showIcon message="Пользователь не выбран" />
          ) : (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">Текущие роли:</Text>{' '}
                {renderLimitedRoleTags(userRolesEditorUser.roles ?? [])}
              </div>

              {userRolesEditorModeValue === 'replace' && (
                <Alert
                  type="info"
                  showIcon
                  message="Режим “Заменить” — итоговый список ролей"
                  description="Можно оставить пустым, чтобы снять все роли у пользователя."
                />
              )}

              <Form
                form={userRolesEditorForm}
                layout="vertical"
                initialValues={{ mode: 'replace' as const }}
                onFinish={(values) => {
                  if (!userRolesEditorUser) return

                  const mode = (values.mode ?? 'replace') as 'replace' | 'add' | 'remove'
                  const selectedRoleIds = Array.from(new Set(values.group_ids ?? [])).sort((a, b) => a - b)
                  const reason = String(values.reason ?? '').trim()

                  if (!reason) {
                    message.error('Причина обязательна')
                    return
                  }
                  if (mode !== 'replace' && selectedRoleIds.length === 0) {
                    message.error('Выберите роли')
                    return
                  }

                  const currentRoleIds = (userRolesEditorUser.roles ?? []).map((r) => r.id).sort((a, b) => a - b)
                  const currentRoleIdSet = new Set(currentRoleIds)
                  const selectedRoleIdSet = new Set(selectedRoleIds)

                  const modeLabel = mode === 'replace' ? 'Заменить' : (mode === 'add' ? 'Добавить' : 'Убрать')

                  const computeDiff = () => {
                    if (mode === 'replace') {
                      const added = selectedRoleIds.filter((id) => !currentRoleIdSet.has(id))
                      const removed = currentRoleIds.filter((id) => !selectedRoleIdSet.has(id))
                      return { added, removed, next: selectedRoleIds }
                    }

                    if (mode === 'add') {
                      const added = selectedRoleIds.filter((id) => !currentRoleIdSet.has(id))
                      const next = Array.from(new Set([...currentRoleIds, ...selectedRoleIds])).sort((a, b) => a - b)
                      return { added, removed: [] as number[], next }
                    }

                    const removed = selectedRoleIds.filter((id) => currentRoleIdSet.has(id))
                    const next = currentRoleIds.filter((id) => !selectedRoleIdSet.has(id)).sort((a, b) => a - b)
                    return { added: [] as number[], removed, next }
                  }

                  const diff = computeDiff()
                  const isReplaceRemoveAll = mode === 'replace' && selectedRoleIds.length === 0 && currentRoleIds.length > 0

                  confirmWithTracking(modal, {
                    title: isReplaceRemoveAll ? 'Снять все роли у пользователя?' : 'Применить роли пользователю?',
                    okText: 'Применить',
                    cancelText: 'Отмена',
                    okButtonProps: { danger: isReplaceRemoveAll, 'data-testid': 'rbac-user-roles-confirm-ok' },
                    cancelButtonProps: { 'data-testid': 'rbac-user-roles-confirm-cancel' },
                    content: (
                      <div data-testid="rbac-user-roles-confirm-content">
                        <Space direction="vertical" size={8} style={{ width: '100%' }}>
                          {isReplaceRemoveAll && (
                            <div data-testid="rbac-user-roles-confirm-remove-all-warning">
                              <Alert
                                type="warning"
                                showIcon
                                message={`Будут сняты все роли (${currentRoleIds.length}).`}
                                description="Это эквивалентно режиму “Заменить” с пустым списком ролей."
                              />
                            </div>
                          )}

                          <div>
                            <Text type="secondary">Пользователь:</Text>{' '}
                            <Text>{userRolesEditorUser.username} #{userRolesEditorUser.id}</Text>
                          </div>
                          <div>
                            <Text type="secondary">Режим:</Text> <Tag>{modeLabel}</Tag>
                          </div>

                          <div data-testid="rbac-user-roles-confirm-selected-count">
                            <Text type="secondary">Выбрано:</Text> <Text>{selectedRoleIds.length}</Text>
                          </div>
                          <div data-testid="rbac-user-roles-confirm-selected-roles">
                            <Text type="secondary">Выбранные роли:</Text> {renderRoleIdTags(selectedRoleIds)}
                          </div>

                          <div data-testid="rbac-user-roles-confirm-current-roles">
                            <Text type="secondary">Текущие роли:</Text> {renderRoleIdTags(currentRoleIds)}
                          </div>

                          <div data-testid="rbac-user-roles-confirm-diff-added">
                            <Text type="secondary">Добавится:</Text> {renderRoleIdTags(diff.added)}
                          </div>
                          <div data-testid="rbac-user-roles-confirm-diff-removed">
                            <Text type="secondary">Уберётся:</Text> {renderRoleIdTags(diff.removed)}
                          </div>
                          <div data-testid="rbac-user-roles-confirm-next-count">
                            <Text type="secondary">Итого после применения:</Text>{' '}
                            <Text>{diff.next.length}</Text>
                          </div>

                          <div data-testid="rbac-user-roles-confirm-reason">
                            <Text type="secondary">Причина:</Text> <Text>{reason}</Text>
                          </div>
                        </Space>
                      </div>
                    ),
                    onOk: async () => {
                      try {
                        await setUserRoles.mutateAsync({
                          user_id: userRolesEditorUser.id,
                          group_ids: selectedRoleIds,
                          mode,
                          reason,
                        })
                        message.success('Роли применены')
                        setUserRolesEditorOpen(false)
                        setUserRolesEditorUser(null)
                        userRolesEditorForm.resetFields()
                        userRolesUsersQuery.refetch()
                      } catch {
                        message.error('Не удалось применить роли')
                        throw new Error('Failed to apply roles')
                      }
                    },
                  })
                }}
              >
                <Form.Item label="Режим" name="mode">
                  <Select
                    data-testid="rbac-user-roles-editor-mode"
                    style={{ width: 240 }}
                    options={[
                      { label: 'Заменить', value: 'replace' },
                      { label: 'Добавить', value: 'add' },
                      { label: 'Убрать', value: 'remove' },
                    ]}
                  />
                </Form.Item>

                <Form.Item
                  label={
                    userRolesEditorModeValue === 'replace'
                      ? 'Роли (итоговый список)'
                      : (userRolesEditorModeValue === 'add' ? 'Роли для добавления' : 'Роли для удаления')
                  }
                  name="group_ids"
                >
                  <Select
                    data-testid="rbac-user-roles-editor-group-ids"
                    allowClear
                    mode="multiple"
                    style={{ width: '100%' }}
                    placeholder={
                      userRolesEditorModeValue === 'replace'
                        ? 'Выберите роли (можно очистить, чтобы снять все)'
                        : (userRolesEditorModeValue === 'add' ? 'Выберите роли' : 'Выберите роли из текущих')
                    }
                    options={userRolesEditorModeValue === 'remove'
                      ? (userRolesEditorUser.roles ?? []).map((r) => ({ label: `${r.name} #${r.id}`, value: r.id }))
                      : roleOptions}
                    showSearch
                    optionFilterProp="label"
                  />
                </Form.Item>

                <Form.Item
                  label="Причина"
                  name="reason"
                  rules={[{ required: true, message: 'Укажите причину' }]}
                >
                  <Input data-testid="rbac-user-roles-editor-reason" placeholder="Причина (обязательно)" />
                </Form.Item>
              </Form>
            </Space>
          )}
        </div>
      </Modal>
    </>
  )
}
