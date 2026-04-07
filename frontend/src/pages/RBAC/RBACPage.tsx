import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Space, Tag, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'

import { useAuthz } from '../../authz/useAuthz'
import { useCanManageRbac } from '../../api/queries/rbac'
import { EntityDetails, EntityList, PageHeader, WorkspacePage } from '../../components/platform'
import { AuditTab } from './tabs/AuditTab'
import { DbmsUsersTab } from './tabs/DbmsUsersTab'
import { EffectiveAccessTab } from './tabs/EffectiveAccessTab'
import { InfobaseUsersTab } from './tabs/InfobaseUsersTab'
import { PermissionsTab } from './tabs/PermissionsTab'
import { RolesTab } from './tabs/RolesTab'
import { UserRolesTab } from './tabs/UserRolesTab'

const { Text } = Typography

type PermissionLevelCode = 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
type RbacPermissionsResourceKey = 'clusters' | 'databases' | 'operation-templates' | 'workflow-templates' | 'artifacts'
type RbacMode = 'assignments' | 'roles'

const LS_RBAC_LEVELS_HINT_DISMISSED = 'cc1c_rbac_levels_hint_dismissed'
const DEFAULT_ASSIGNMENTS_TAB = 'permissions'
const DEFAULT_ROLES_TAB = 'roles'

const parseRbacMode = (value: string | null): RbacMode => (
  value === 'roles' ? 'roles' : 'assignments'
)

const buildRbacSectionLabel = (key: string): string => {
  switch (key) {
    case 'roles':
      return 'Роли'
    case 'permissions':
      return 'Доступ к объектам'
    case 'user-roles':
      return 'Роли пользователей'
    case 'effective-access':
      return 'Эффективный доступ'
    case 'audit':
      return 'Аудит'
    case 'ib-users':
      return 'Пользователи ИБ'
    case 'dbms-users':
      return 'Пользователи DBMS'
    default:
      return key
  }
}

export function RBACPage() {
  const [permissionLevelsHintDismissed, setPermissionLevelsHintDismissed] = useState<boolean>(() => (
    localStorage.getItem(LS_RBAC_LEVELS_HINT_DISMISSED) === '1'
  ))
  const [permissionLevelsHintExpanded, setPermissionLevelsHintExpanded] = useState<boolean>(true)
  const [searchParams, setSearchParams] = useSearchParams()

  const hasToken = Boolean(localStorage.getItem('auth_token'))
  const { isStaff } = useAuthz()

  const canManageRbacQuery = useCanManageRbac({ enabled: hasToken })
  const canManageRbac = Boolean(canManageRbacQuery.data)

  const rbacMode = parseRbacMode(searchParams.get('mode'))
  const requestedTabKey = (searchParams.get('tab') || '').trim()
  const [rbacLastAssignmentsTabKey, setRbacLastAssignmentsTabKey] = useState<string>(() => (
    requestedTabKey || DEFAULT_ASSIGNMENTS_TAB
  ))

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

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(updates).forEach(([key, value]) => {
        if (!value) {
          next.delete(key)
        } else {
          next.set(key, value)
        }
      })
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )

  const openAssignmentsForRole = useCallback((roleId: number) => {
    updateSearchParams({
      mode: 'assignments',
      tab: DEFAULT_ASSIGNMENTS_TAB,
    })
    setRbacLastAssignmentsTabKey(DEFAULT_ASSIGNMENTS_TAB)
    setRbacPermissionsPrincipalType('role')
    setRbacPermissionsViewMode('principal')
    setRbacPermissionsList((prev) => ({ ...prev, principal_id: roleId, page: 1 }))
  }, [updateSearchParams])

  const items = useMemo(() => ([
    {
      key: 'roles',
      label: 'Роли',
      children: <RolesTab canManageRbac={canManageRbac} onOpenAssignmentsForRole={openAssignmentsForRole} />,
    },
    {
      key: 'permissions',
      label: 'Доступ к объектам',
      children: (
        <PermissionsTab
          canManageRbac={canManageRbac}
          isActive={requestedTabKey === 'permissions'}
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
      label: 'Роли пользователей',
      children: <UserRolesTab canManageRbac={canManageRbac} />,
    },
    {
      key: 'effective-access',
      label: 'Эффективный доступ',
      children: <EffectiveAccessTab canManageRbac={canManageRbac} />,
    },
    {
      key: 'audit',
      label: 'Аудит',
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
        label: 'Пользователи DBMS',
        children: <DbmsUsersTab enabled={isStaff} />,
      },
    ] : []),
  ]), [
    canManageRbac,
    isStaff,
    openAssignmentsForRole,
    requestedTabKey,
    rbacPermissionsList,
    rbacPermissionsPrincipalType,
    rbacPermissionsResourceKey,
    rbacPermissionsViewMode,
  ])

  const visibleItems = useMemo(() => {
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
  }, [isStaff, items, rbacMode])

  const activeTabKey = useMemo(() => {
    const visibleKeys = new Set(visibleItems.map((item) => String(item.key)))
    if (visibleKeys.has(requestedTabKey)) {
      return requestedTabKey
    }
    return rbacMode === 'roles' ? DEFAULT_ROLES_TAB : rbacLastAssignmentsTabKey
  }, [rbacLastAssignmentsTabKey, rbacMode, requestedTabKey, visibleItems])

  useEffect(() => {
    if (rbacMode !== 'assignments') {
      return
    }
    if (!activeTabKey || activeTabKey === 'roles') {
      return
    }
    setRbacLastAssignmentsTabKey(activeTabKey)
  }, [activeTabKey, rbacMode])

  useEffect(() => {
    const visibleKeys = new Set(visibleItems.map((item) => String(item.key)))
    const nextTabKey = visibleKeys.has(activeTabKey)
      ? activeTabKey
      : visibleItems[0]
        ? String(visibleItems[0].key)
        : ''
    if (!nextTabKey || requestedTabKey === nextTabKey) {
      return
    }
    updateSearchParams({ tab: nextTabKey })
  }, [activeTabKey, requestedTabKey, updateSearchParams, visibleItems])

  const activeItem = visibleItems.find((item) => String(item.key) === activeTabKey) ?? visibleItems[0] ?? null

  const handleModeChange = useCallback((nextMode: RbacMode) => {
    const nextTab = nextMode === 'roles'
      ? (requestedTabKey === 'roles' || requestedTabKey === 'audit' ? requestedTabKey : DEFAULT_ROLES_TAB)
      : (rbacLastAssignmentsTabKey || DEFAULT_ASSIGNMENTS_TAB)

    updateSearchParams({
      mode: nextMode,
      tab: nextTab,
    })
  }, [rbacLastAssignmentsTabKey, requestedTabKey, updateSearchParams])

  const handleSelectTab = useCallback((key: string) => {
    if (rbacMode === 'assignments') {
      setRbacLastAssignmentsTabKey(key)
    }
    updateSearchParams({ tab: key })
  }, [rbacMode, updateSearchParams])

  const header = (
    <PageHeader
      title="RBAC"
      subtitle="Привилегированный governance workspace для ролей, назначений и аудита."
      actions={(
        <Space wrap>
          <Button
            type={rbacMode === 'assignments' ? 'primary' : 'default'}
            onClick={() => handleModeChange('assignments')}
          >
            Назначения
          </Button>
          <Button
            type={rbacMode === 'roles' ? 'primary' : 'default'}
            onClick={() => handleModeChange('roles')}
          >
            Роли
          </Button>
        </Space>
      )}
    />
  )

  if (canManageRbacQuery.isLoading) {
    return (
      <WorkspacePage header={header}>
        <EntityDetails title="RBAC" loading>
          <div />
        </EntityDetails>
      </WorkspacePage>
    )
  }

  if (!canManageRbac) {
    return (
      <WorkspacePage header={header}>
        <Alert
          type="warning"
          message="Нет доступа к RBAC"
          description="Требуется capability: databases.manage_rbac"
          showIcon
        />
      </WorkspacePage>
    )
  }

  return (
    <WorkspacePage header={header}>
      {!permissionLevelsHintDismissed && (
        <Alert
          type="info"
          showIcon
          closable
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
              <Text><Tag>VIEW</Tag> видеть/читать (списки/детали/метаданные).</Text>
              <Text><Tag>OPERATE</Tag> выполнять операции, без изменения конфигурации.</Text>
              <Text><Tag>MANAGE</Tag> менять настройки/конфигурацию объекта.</Text>
              <Text><Tag>ADMIN</Tag> самый высокий уровень, включая разрушительные действия.</Text>
            </Space>
          ) : undefined}
        />
      )}

      <EntityList
        title={rbacMode === 'roles' ? 'Управление ролями' : 'Управление назначениями'}
        extra={<Text type="secondary">mode={rbacMode}</Text>}
        dataSource={visibleItems}
        renderItem={(item) => (
          <div style={{ paddingBlock: 4 }}>
            <Button
              type={String(item.key) === activeTabKey ? 'primary' : 'default'}
              onClick={() => handleSelectTab(String(item.key))}
              data-testid={`rbac-tab-${String(item.key)}`}
            >
              {buildRbacSectionLabel(String(item.key))}
            </Button>
          </div>
        )}
      />

      <EntityDetails
        title={activeItem?.label ?? 'RBAC section'}
        empty={!activeItem}
        emptyDescription="Выберите раздел RBAC workspace."
      >
        {activeItem?.children}
      </EntityDetails>
    </WorkspacePage>
  )
}
