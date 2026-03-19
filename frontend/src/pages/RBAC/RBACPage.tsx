import { useState } from 'react'
import { Alert, Button, Radio, Space, Tabs, Tag, Typography } from 'antd'

import { useAuthz } from '../../authz/useAuthz'
import { useCanManageRbac } from '../../api/queries/rbac'
import { AuditTab } from './tabs/AuditTab'
import { DbmsUsersTab } from './tabs/DbmsUsersTab'
import { EffectiveAccessTab } from './tabs/EffectiveAccessTab'
import { InfobaseUsersTab } from './tabs/InfobaseUsersTab'
import { PermissionsTab } from './tabs/PermissionsTab'
import { RolesTab } from './tabs/RolesTab'
import { UserRolesTab } from './tabs/UserRolesTab'

const { Title, Text } = Typography

type PermissionLevelCode = 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
type RbacPermissionsResourceKey = 'clusters' | 'databases' | 'operation-templates' | 'workflow-templates' | 'artifacts'

const LS_RBAC_LEVELS_HINT_DISMISSED = 'cc1c_rbac_levels_hint_dismissed'

export function RBACPage() {
  const [permissionLevelsHintDismissed, setPermissionLevelsHintDismissed] = useState<boolean>(() => (
    localStorage.getItem(LS_RBAC_LEVELS_HINT_DISMISSED) === '1'
  ))
  const [permissionLevelsHintExpanded, setPermissionLevelsHintExpanded] = useState<boolean>(true)

  const hasToken = Boolean(localStorage.getItem('auth_token'))
  const { isStaff } = useAuthz()

  const canManageRbacQuery = useCanManageRbac({ enabled: hasToken })
  const canManageRbac = Boolean(canManageRbacQuery.data)

  const [rbacMode, setRbacMode] = useState<'assignments' | 'roles'>('assignments')
  const [rbacLastAssignmentsTabKey, setRbacLastAssignmentsTabKey] = useState<string>('permissions')
  const [rbacActiveTabKey, setRbacActiveTabKey] = useState<string>('permissions')

  const [rbacPermissionsResourceKey, setRbacPermissionsResourceKey] = useState<RbacPermissionsResourceKey>('databases')
  const [rbacPermissionsPrincipalType, setRbacPermissionsPrincipalType] = useState<'user' | 'role'>('user')
  const [rbacPermissionsViewMode, setRbacPermissionsViewMode] = useState<'principal' | 'resource'>('principal')
  const [rbacPermissionsList, setRbacPermissionsList] = useState<{
    principal_id?: number
    resource_id?: string
    level?: PermissionLevelCode
    search: string
    page: number
    pageSize: number
  }>({ search: '', page: 1, pageSize: 50 })

  const openAssignmentsForRole = (roleId: number) => {
    setRbacMode('assignments')
    setRbacActiveTabKey('permissions')
    setRbacLastAssignmentsTabKey('permissions')
    setRbacPermissionsPrincipalType('role')
    setRbacPermissionsViewMode('principal')
    setRbacPermissionsList((prev) => ({ ...prev, principal_id: roleId, page: 1 }))
  }

  if (canManageRbacQuery.isLoading) {
    return (
      <div>
        <Title level={2}>RBAC</Title>
        <Text type="secondary">Загрузка…</Text>
      </div>
    )
  }

  if (!canManageRbac) {
    return (
      <div>
        <Title level={2}>RBAC</Title>
        <Alert
          type="warning"
          message="Нет доступа к RBAC"
          description="Требуется capability: databases.manage_rbac"
        />
      </div>
    )
  }

  const items = [
    {
      key: 'roles',
      label: <span data-testid="rbac-tab-roles">Роли</span>,
      children: <RolesTab canManageRbac={canManageRbac} onOpenAssignmentsForRole={openAssignmentsForRole} />,
    },
    {
      key: 'permissions',
      label: <span data-testid="rbac-tab-permissions">Доступ к объектам</span>,
      children: (
        <PermissionsTab
          canManageRbac={canManageRbac}
          isActive={rbacActiveTabKey === 'permissions'}
          rbacPermissionsResourceKey={rbacPermissionsResourceKey}
          setRbacPermissionsResourceKey={setRbacPermissionsResourceKey}
          rbacPermissionsPrincipalType={rbacPermissionsPrincipalType}
          setRbacPermissionsPrincipalType={setRbacPermissionsPrincipalType}
          rbacPermissionsViewMode={rbacPermissionsViewMode}
          setRbacPermissionsViewMode={setRbacPermissionsViewMode}
          rbacPermissionsList={rbacPermissionsList}
          setRbacPermissionsList={setRbacPermissionsList}
        />
      ),
    },
    {
      key: 'user-roles',
      label: <span data-testid="rbac-tab-user-roles">Роли пользователей</span>,
      children: <UserRolesTab canManageRbac={canManageRbac} />,
    },
    {
      key: 'effective-access',
      label: <span data-testid="rbac-tab-effective-access">Эффективный доступ</span>,
      children: <EffectiveAccessTab canManageRbac={canManageRbac} />,
    },
    {
      key: 'audit',
      label: <span data-testid="rbac-tab-audit">Аудит</span>,
      children: <AuditTab canManageRbac={canManageRbac} />,
    },
    ...(isStaff ? [
      {
        key: 'ib-users',
        label: 'Пользователи ИБ',
        children: <InfobaseUsersTab enabled={isStaff} />,
      },
      {
        key: 'dbms-users',
        label: <span data-testid="rbac-tab-dbms-users">Пользователи DBMS</span>,
        children: <DbmsUsersTab enabled={isStaff} />,
      },
    ] : []),
  ]

  const visibleItems = (() => {
    if (rbacMode === 'roles') {
      const allowedRoleKeys = new Set<string>(['roles', 'audit'])
      return items.filter((item) => allowedRoleKeys.has(String(item.key)))
    }

    const allowedKeys = new Set<string>([
      'permissions',
      'user-roles',
      'effective-access',
      'audit',
      ...(isStaff ? ['ib-users', 'dbms-users'] : []),
    ])
    return items.filter((item) => allowedKeys.has(String(item.key)))
  })()

  return (
    <div>
      <Title level={2}>RBAC</Title>
      {!permissionLevelsHintDismissed && (
        <Alert
          type="info"
          showIcon
          closable
          style={{ marginBottom: 16 }}
          afterClose={() => {
            localStorage.setItem(LS_RBAC_LEVELS_HINT_DISMISSED, '1')
            setPermissionLevelsHintDismissed(true)
          }}
          message={(
            <Space size={8}>
              <Text>Подсказка по уровням VIEW / OPERATE / MANAGE / ADMIN</Text>
              <Button
                type="link"
                size="small"
                style={{ paddingInline: 0, height: 20 }}
                onClick={() => setPermissionLevelsHintExpanded((prev) => !prev)}
              >
                {permissionLevelsHintExpanded ? 'Свернуть' : 'Показать'}
              </Button>
            </Space>
          )}
          description={permissionLevelsHintExpanded ? (
            <Space direction="vertical" size={4}>
              <Text>
                <Tag>VIEW</Tag> видеть/читать (списки/детали/метаданные).
              </Text>
              <Text>
                <Tag>OPERATE</Tag> выполнять операции, без изменения конфигурации.
              </Text>
              <Text>
                <Tag>MANAGE</Tag> менять настройки/конфигурацию объекта.
              </Text>
              <Text>
                <Tag>ADMIN</Tag> самый высокий уровень (в т.ч. разрушительные/владельческие действия, если домен различает).
              </Text>
            </Space>
          ) : undefined}
        />
      )}

      <Space style={{ marginBottom: 12 }}>
        <Radio.Group
          buttonStyle="solid"
          value={rbacMode}
          onChange={(event) => {
            const nextMode = event.target.value as 'assignments' | 'roles'
            setRbacMode(nextMode)
            if (nextMode === 'roles') {
              const allowedRoleKeys = new Set<string>(['roles', 'audit'])
              setRbacActiveTabKey(allowedRoleKeys.has(rbacActiveTabKey) ? rbacActiveTabKey : 'roles')
              return
            }

            const allowedAssignmentKeys = new Set<string>([
              'permissions',
              'user-roles',
              'effective-access',
              'audit',
              ...(isStaff ? ['ib-users'] : []),
            ])
            setRbacActiveTabKey(allowedAssignmentKeys.has(rbacLastAssignmentsTabKey) ? rbacLastAssignmentsTabKey : 'permissions')
          }}
        >
          <Radio.Button value="assignments">Назначения</Radio.Button>
          <Radio.Button value="roles">Роли</Radio.Button>
        </Radio.Group>
      </Space>

      <Tabs
        activeKey={rbacActiveTabKey}
        onChange={(key) => {
          setRbacActiveTabKey(key)
          if (rbacMode === 'assignments') {
            setRbacLastAssignmentsTabKey(key)
          }
        }}
        items={visibleItems}
      />
    </div>
  )
}
