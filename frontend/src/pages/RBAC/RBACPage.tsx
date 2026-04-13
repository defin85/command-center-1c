import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Space, Tag, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'

import { useAuthz } from '../../authz/useAuthz'
import { useCanManageRbac } from '../../api/queries/rbac'
import { EntityDetails, EntityList, PageHeader, WorkspacePage } from '../../components/platform'
import { useRbacTranslation } from '../../i18n'
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

export function RBACPage() {
  const { t } = useRbacTranslation()
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
      label: t(($) => $.page.tabs.roles),
      children: <RolesTab canManageRbac={canManageRbac} onOpenAssignmentsForRole={openAssignmentsForRole} />,
    },
    {
      key: 'permissions',
      label: t(($) => $.page.tabs.permissions),
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
      label: t(($) => $.page.tabs.userRoles),
      children: <UserRolesTab canManageRbac={canManageRbac} />,
    },
    {
      key: 'effective-access',
      label: t(($) => $.page.tabs.effectiveAccess),
      children: <EffectiveAccessTab canManageRbac={canManageRbac} />,
    },
    {
      key: 'audit',
      label: t(($) => $.page.tabs.audit),
      children: <AuditTab canManageRbac={canManageRbac} />,
    },
    ...(isStaff ? [
      {
        key: 'ib-users',
        label: t(($) => $.page.tabs.ibUsers),
        children: <InfobaseUsersTab enabled={isStaff} />,
      },
      {
        key: 'dbms-users',
        label: t(($) => $.page.tabs.dbmsUsers),
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
    t,
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
      title={t(($) => $.page.title)}
      subtitle={t(($) => $.page.subtitle)}
      actions={(
        <Space wrap>
          <Button
            type={rbacMode === 'assignments' ? 'primary' : 'default'}
            onClick={() => handleModeChange('assignments')}
          >
            {t(($) => $.page.modes.assignments)}
          </Button>
          <Button
            type={rbacMode === 'roles' ? 'primary' : 'default'}
            onClick={() => handleModeChange('roles')}
          >
            {t(($) => $.page.modes.roles)}
          </Button>
        </Space>
      )}
    />
  )

  if (canManageRbacQuery.isLoading) {
    return (
      <WorkspacePage header={header}>
        <EntityDetails title={t(($) => $.page.loadingTitle)} loading>
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
          message={t(($) => $.page.noAccessTitle)}
          description={t(($) => $.page.noAccessDescription)}
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
              <Text>{t(($) => $.page.hints.title)}</Text>
              <Button
                type="link"
                size="small"
                style={{ paddingInline: 0, height: 20 }}
                onClick={() => setPermissionLevelsHintExpanded((prev) => !prev)}
              >
                {permissionLevelsHintExpanded ? t(($) => $.page.hints.collapse) : t(($) => $.page.hints.expand)}
              </Button>
            </Space>
          )}
          description={permissionLevelsHintExpanded ? (
            <Space direction="vertical" size={4}>
              <Text><Tag>VIEW</Tag> {t(($) => $.page.hints.view)}</Text>
              <Text><Tag>OPERATE</Tag> {t(($) => $.page.hints.operate)}</Text>
              <Text><Tag>MANAGE</Tag> {t(($) => $.page.hints.manage)}</Text>
              <Text><Tag>ADMIN</Tag> {t(($) => $.page.hints.admin)}</Text>
            </Space>
          ) : undefined}
        />
      )}

      <EntityList
        title={rbacMode === 'roles' ? t(($) => $.page.rolesManagement) : t(($) => $.page.assignmentsManagement)}
        extra={<Text type="secondary">{t(($) => $.page.modeMeta, { value: rbacMode })}</Text>}
        dataSource={visibleItems}
        renderItem={(item) => (
          <div style={{ paddingBlock: 4 }}>
            <Button
              type={String(item.key) === activeTabKey ? 'primary' : 'default'}
              onClick={() => handleSelectTab(String(item.key))}
              data-testid={`rbac-tab-${String(item.key)}`}
            >
              {item.label}
            </Button>
          </div>
        )}
      />

      <EntityDetails
        title={activeItem?.label ?? t(($) => $.page.title)}
        empty={!activeItem}
        emptyDescription={t(($) => $.page.sectionPlaceholder)}
      >
        {activeItem?.children}
      </EntityDetails>
    </WorkspacePage>
  )
}
