import { useCallback, useEffect, useMemo, useState } from 'react'
import { App, Alert, Badge, Button, Card, Form, Input, Modal, Popover, Radio, Segmented, Select, Space, Switch, Table, Tabs, Tooltip, Typography, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { ClusterPermission } from '../../api/generated/model/clusterPermission'
import type { DatabasePermission } from '../../api/generated/model/databasePermission'
import type { EffectiveAccessClusterItem } from '../../api/generated/model/effectiveAccessClusterItem'
import type { EffectiveAccessClusterSourceItem } from '../../api/generated/model/effectiveAccessClusterSourceItem'
import type { EffectiveAccessDatabaseItem } from '../../api/generated/model/effectiveAccessDatabaseItem'
import type { EffectiveAccessDatabaseSourceItem } from '../../api/generated/model/effectiveAccessDatabaseSourceItem'
import type { EffectiveAccessOperationTemplateItem } from '../../api/generated/model/effectiveAccessOperationTemplateItem'
import type { EffectiveAccessOperationTemplateSourceItem } from '../../api/generated/model/effectiveAccessOperationTemplateSourceItem'
import type { EffectiveAccessWorkflowTemplateItem } from '../../api/generated/model/effectiveAccessWorkflowTemplateItem'
import type { EffectiveAccessWorkflowTemplateSourceItem } from '../../api/generated/model/effectiveAccessWorkflowTemplateSourceItem'
import type { EffectiveAccessArtifactItem } from '../../api/generated/model/effectiveAccessArtifactItem'
import type { EffectiveAccessArtifactSourceItem } from '../../api/generated/model/effectiveAccessArtifactSourceItem'
import { useMe } from '../../api/queries/me'
import {
  useCanManageRbac,
  useCapabilities,
  useClusterPermissions,
  useClusterGroupPermissions,
  useEffectiveAccess,
  useBulkGrantClusterGroupPermission,
  useBulkRevokeClusterGroupPermission,
  useCreateRole,
  useDeleteRole,
  useDatabasePermissions,
  useDatabaseGroupPermissions,
  useBulkGrantDatabaseGroupPermission,
  useBulkRevokeDatabaseGroupPermission,
  useGrantClusterPermission,
  useGrantClusterGroupPermission,
  useGrantDatabasePermission,
  useGrantDatabaseGroupPermission,
  useGrantOperationTemplateGroupPermission,
  useGrantOperationTemplatePermission,
  useGrantWorkflowTemplateGroupPermission,
  useGrantWorkflowTemplatePermission,
  useGrantArtifactGroupPermission,
  useGrantArtifactPermission,
  useOperationTemplateGroupPermissions,
  useOperationTemplatePermissions,
  useWorkflowTemplateGroupPermissions,
  useWorkflowTemplatePermissions,
  useArtifactGroupPermissions,
  useArtifactPermissions,
  useRbacRefClusters,
  useRbacRefDatabases,
  useRbacRefOperationTemplates,
  useRbacRefWorkflowTemplates,
  useRbacRefArtifacts,
  useRevokeClusterPermission,
  useRevokeClusterGroupPermission,
  useRevokeDatabasePermission,
  useRevokeDatabaseGroupPermission,
  useRevokeOperationTemplateGroupPermission,
  useRevokeOperationTemplatePermission,
  useRevokeWorkflowTemplateGroupPermission,
  useRevokeWorkflowTemplatePermission,
  useRevokeArtifactGroupPermission,
  useRevokeArtifactPermission,
  useRbacUsers,
  useRbacUsersWithRoles,
  useRoles,
  useSetRoleCapabilities,
  useSetUserRoles,
  useUpdateRole,
  type ArtifactGroupPermission,
  type ArtifactPermission,
  type ClusterGroupPermission,
  type DatabaseGroupPermission,
  type OperationTemplateGroupPermission,
  type OperationTemplatePermission,
  type RbacRole,
  type UserWithRolesRef,
  type WorkflowTemplateGroupPermission,
  type WorkflowTemplatePermission,
} from '../../api/queries/rbac'
import {
  useInfobaseUsers,
  useCreateInfobaseUser,
  useUpdateInfobaseUser,
  useDeleteInfobaseUser,
  useSetInfobaseUserPassword,
  useResetInfobaseUserPassword,
  type InfobaseUserMapping,
} from '../../api/queries/databases'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { RbacAuditPanel } from './components/RbacAuditPanel'
import { RbacBulkClusterRolePermissions } from './components/RbacBulkClusterRolePermissions'
import { RbacBulkDatabaseRolePermissions } from './components/RbacBulkDatabaseRolePermissions'
import { RbacClusterDatabaseTree } from './components/RbacClusterDatabaseTree'
import { PermissionsTable } from './components/PermissionsTable'
import { RbacPrincipalPicker } from './components/RbacPrincipalPicker'
import { RbacResourceBrowser } from './components/RbacResourceBrowser'
import { RbacResourcePicker } from './components/RbacResourcePicker'
import { ReasonModal } from './components/ReasonModal'
import { useConfirmReason } from './hooks/useConfirmReason'
import { usePaginatedRefSelectOptions } from './hooks/usePaginatedRefSelectOptions'
import { getEffectiveAccessSourceTagColor } from './utils/effectiveAccessSourceTag'

const { Title, Text } = Typography

type PermissionLevelCode = 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
type RbacPermissionsResourceKey = 'clusters' | 'databases' | 'operation-templates' | 'workflow-templates' | 'artifacts'
type SelectOption = { label: string; value: string }
type RbacPermissionsTableConfig = {
  columns: ColumnsType<any>
  rows: any[]
  total: number
  loading: boolean
  fetching: boolean
  error: unknown
  rowKey: (row: any) => string
  refetch: () => void
}

type UserRolesViewMode = 'user-to-roles' | 'role-to-users'

const LS_RBAC_LEVELS_HINT_DISMISSED = 'cc1c_rbac_levels_hint_dismissed'
const LS_RBAC_USER_ROLES_TABLE_HINT_DISMISSED = 'cc1c_rbac_user_roles_table_hint_dismissed'

const LEVEL_OPTIONS: Array<{ label: PermissionLevelCode; value: PermissionLevelCode }> = [
  { label: 'VIEW', value: 'VIEW' },
  { label: 'OPERATE', value: 'OPERATE' },
  { label: 'MANAGE', value: 'MANAGE' },
  { label: 'ADMIN', value: 'ADMIN' },
]

function envFlag(key: string, defaultValue: boolean): boolean {
  const raw = (import.meta.env as Record<string, unknown>)[key]
  if (typeof raw !== 'string') return defaultValue
  const normalized = raw.trim().toLowerCase()
  if (!normalized) return defaultValue
  return ['1', 'true', 'yes', 'on'].includes(normalized)
}

function ensureSelectOptionsContain(options: SelectOption[], selectedIds: Array<string | undefined>, labelById: Map<string, string>) {
  const ids = selectedIds
    .map((id) => (typeof id === 'string' ? id.trim() : ''))
    .filter((id) => id.length > 0)

  if (ids.length === 0) return options

  const existing = new Set(options.map((opt) => opt.value))
  const missing = ids.filter((id) => !existing.has(id))
  if (missing.length === 0) return options

  const injected = missing.map((id) => ({ value: id, label: labelById.get(id) ?? id }))
  return [...injected, ...options]
}

export function RBACPage() {
  const { modal, message } = App.useApp()
  const confirmReason = useConfirmReason(modal, message, {
    placeholder: 'Причина (обязательно)',
    okText: 'Отозвать',
    cancelText: 'Отмена',
    requiredMessage: 'Укажите причину',
  })
  const clusterDatabasePickerI18n = useMemo(() => ({
    clearText: 'Очистить',
    modalTitleClusters: 'Выбор кластера',
    modalTitleDatabases: 'Выбор базы',
    treeTitle: 'Ресурсы',
    searchPlaceholderClusters: 'Поиск кластеров',
    searchPlaceholderDatabases: 'Поиск баз',
    loadingText: 'Загрузка…',
    loadMoreText: 'Загрузить ещё…',
    clearSelectionText: 'Снять выбор',
  }), [])

  const [permissionLevelsHintDismissed, setPermissionLevelsHintDismissed] = useState<boolean>(() => (
    localStorage.getItem(LS_RBAC_LEVELS_HINT_DISMISSED) === '1'
  ))
  const [permissionLevelsHintExpanded, setPermissionLevelsHintExpanded] = useState<boolean>(true)

  const [userRolesTableHintDismissed, setUserRolesTableHintDismissed] = useState<boolean>(() => (
    localStorage.getItem(LS_RBAC_USER_ROLES_TABLE_HINT_DISMISSED) === '1'
  ))

  const hasToken = Boolean(localStorage.getItem('auth_token'))
  const meQuery = useMe({ enabled: hasToken })
  const isStaff = Boolean(meQuery.data?.is_staff)
  const canManageRbacQuery = useCanManageRbac({ enabled: hasToken })
  const canManageRbac = Boolean(canManageRbacQuery.data)

  const rbacLegacyTabsEnabled = envFlag('VITE_RBAC_LEGACY_TABS', false)
  const REF_PAGE_SIZE = 50

  const clustersRefQuery = useRbacRefClusters({
    limit: 1000,
    offset: 0,
  }, { enabled: canManageRbac })
  const clusters = clustersRefQuery.data?.clusters ?? []
  const [clustersRefSearch, setClustersRefSearch] = useState<string>('')

  const {
    search: databasesRefSearch,
    setSearch: setDatabasesRefSearch,
    options: databasesRefOptions,
    labelById: databasesLabelById,
    query: databasesRefQuery,
    handlePopupScroll: handleDatabasesPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled: canManageRbac,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefDatabases,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.databases,
    getId: (db) => db.id,
    getLabel: (db) => `${db.name} #${db.id}`,
  })

  const {
    search: operationTemplatesRefSearch,
    setSearch: setOperationTemplatesRefSearch,
    options: operationTemplatesRefOptions,
    labelById: operationTemplatesLabelById,
    query: operationTemplatesRefQuery,
    handlePopupScroll: handleOperationTemplatesPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled: canManageRbac,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefOperationTemplates,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.templates,
    getId: (tpl) => tpl.id,
    getLabel: (tpl) => `${tpl.name} #${tpl.id}`,
  })

  const {
    search: workflowTemplatesRefSearch,
    setSearch: setWorkflowTemplatesRefSearch,
    options: workflowTemplatesRefOptions,
    labelById: workflowTemplatesLabelById,
    query: workflowTemplatesRefQuery,
    handlePopupScroll: handleWorkflowTemplatesPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled: canManageRbac,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefWorkflowTemplates,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.templates,
    getId: (tpl) => tpl.id,
    getLabel: (tpl) => `${tpl.name} #${tpl.id}`,
  })

  const {
    search: artifactsRefSearch,
    setSearch: setArtifactsRefSearch,
    options: artifactsRefOptions,
    labelById: artifactsLabelById,
    query: artifactsRefQuery,
    handlePopupScroll: handleArtifactsPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled: canManageRbac,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefArtifacts,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.artifacts,
    getId: (artifact) => artifact.id,
    getLabel: (artifact) => `${artifact.name} #${artifact.id}`,
  })

  const { data: databasesResponse } = useRbacRefDatabases({
    limit: 2000,
    offset: 0,
  }, { enabled: canManageRbac && rbacLegacyTabsEnabled })
  const databases = databasesResponse?.databases ?? []

  const { data: operationTemplatesResponse } = useRbacRefOperationTemplates({
    limit: 2000,
    offset: 0,
  }, { enabled: canManageRbac && rbacLegacyTabsEnabled })
  const operationTemplates = operationTemplatesResponse?.templates ?? []

  const { data: workflowTemplatesResponse } = useRbacRefWorkflowTemplates({
    limit: 2000,
    offset: 0,
  }, { enabled: canManageRbac && rbacLegacyTabsEnabled })
  const workflowTemplates = workflowTemplatesResponse?.templates ?? []

  const { data: artifactsResponse } = useRbacRefArtifacts({
    limit: 2000,
    offset: 0,
  }, { enabled: canManageRbac && rbacLegacyTabsEnabled })
  const artifacts = artifactsResponse?.artifacts ?? []

  const grantCluster = useGrantClusterPermission()
  const revokeCluster = useRevokeClusterPermission()
  const grantDatabase = useGrantDatabasePermission()
  const revokeDatabase = useRevokeDatabasePermission()
  const grantClusterGroup = useGrantClusterGroupPermission()
  const revokeClusterGroup = useRevokeClusterGroupPermission()
  const bulkGrantClusterGroup = useBulkGrantClusterGroupPermission()
  const bulkRevokeClusterGroup = useBulkRevokeClusterGroupPermission()
  const grantDatabaseGroup = useGrantDatabaseGroupPermission()
  const revokeDatabaseGroup = useRevokeDatabaseGroupPermission()
  const bulkGrantDatabaseGroup = useBulkGrantDatabaseGroupPermission()
  const bulkRevokeDatabaseGroup = useBulkRevokeDatabaseGroupPermission()

  const grantOperationTemplate = useGrantOperationTemplatePermission()
  const revokeOperationTemplate = useRevokeOperationTemplatePermission()
  const grantOperationTemplateGroup = useGrantOperationTemplateGroupPermission()
  const revokeOperationTemplateGroup = useRevokeOperationTemplateGroupPermission()

  const grantWorkflowTemplate = useGrantWorkflowTemplatePermission()
  const revokeWorkflowTemplate = useRevokeWorkflowTemplatePermission()
  const grantWorkflowTemplateGroup = useGrantWorkflowTemplateGroupPermission()
  const revokeWorkflowTemplateGroup = useRevokeWorkflowTemplateGroupPermission()

  const grantArtifact = useGrantArtifactPermission()
  const revokeArtifact = useRevokeArtifactPermission()
  const grantArtifactGroup = useGrantArtifactGroupPermission()
  const revokeArtifactGroup = useRevokeArtifactGroupPermission()

  const rolesQuery = useRoles({ limit: 500, offset: 0 }, { enabled: canManageRbac })
  const createRole = useCreateRole()
  const updateRole = useUpdateRole()
  const deleteRole = useDeleteRole()
  const setRoleCapabilities = useSetRoleCapabilities()
  const setUserRoles = useSetUserRoles()
  const capabilitiesQuery = useCapabilities({ enabled: canManageRbac })

  const createInfobaseUser = useCreateInfobaseUser()
  const updateInfobaseUser = useUpdateInfobaseUser()
  const deleteInfobaseUser = useDeleteInfobaseUser()
  const setInfobaseUserPassword = useSetInfobaseUserPassword()
  const resetInfobaseUserPassword = useResetInfobaseUserPassword()

  const [selectedIbDatabaseId, setSelectedIbDatabaseId] = useState<string | undefined>()
  const [editingIbUser, setEditingIbUser] = useState<InfobaseUserMapping | null>(null)
  const [ibAuthFilter, setIbAuthFilter] = useState<string>('any')
  const [ibServiceFilter, setIbServiceFilter] = useState<string>('any')
  const [ibHasUserFilter, setIbHasUserFilter] = useState<string>('any')
  const [userSearch, setUserSearch] = useState<string>('')
  const [roleSearch, setRoleSearch] = useState<string>('')

  const [userRolesViewMode, setUserRolesViewMode] = useState<UserRolesViewMode>('user-to-roles')
  const [userRolesList, setUserRolesList] = useState<{
    search: string
    role_id?: number
    page: number
    pageSize: number
  }>({ search: '', page: 1, pageSize: 50 })
  const [userRolesEditorOpen, setUserRolesEditorOpen] = useState<boolean>(false)
  const [userRolesEditorUser, setUserRolesEditorUser] = useState<UserWithRolesRef | null>(null)

  const [selectedEffectiveUserId, setSelectedEffectiveUserId] = useState<number | undefined>()
  const [effectiveResourceKey, setEffectiveResourceKey] = useState<RbacPermissionsResourceKey>('databases')
  const [effectiveResourceId, setEffectiveResourceId] = useState<string | undefined>()
  const [effectiveDbPage, setEffectiveDbPage] = useState<number>(1)
  const [effectiveDbPageSize, setEffectiveDbPageSize] = useState<number>(50)

  useEffect(() => {
    setEffectiveResourceId(undefined)
    setEffectiveDbPage(1)
  }, [effectiveResourceKey])

  useEffect(() => {
    setEffectiveDbPage(1)
  }, [effectiveResourceId])

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

  useEffect(() => {
    if (permissionLevelsHintDismissed) return
    if (!permissionLevelsHintExpanded) return

    const startedWorking = (
      rbacMode !== 'assignments'
      || rbacActiveTabKey !== 'permissions'
      || rbacPermissionsResourceKey !== 'databases'
      || rbacPermissionsPrincipalType !== 'user'
      || rbacPermissionsViewMode !== 'principal'
      || Boolean(rbacPermissionsList.principal_id)
      || Boolean(rbacPermissionsList.resource_id)
      || Boolean(rbacPermissionsList.level)
      || rbacPermissionsList.search.trim().length > 0
      || userRolesViewMode !== 'user-to-roles'
      || userRolesList.search.trim().length > 0
      || typeof userRolesList.role_id === 'number'
      || typeof selectedEffectiveUserId === 'number'
      || effectiveResourceKey !== 'databases'
      || typeof effectiveResourceId === 'string'
    )

    if (!startedWorking) return
    setPermissionLevelsHintExpanded(false)
  }, [
    effectiveResourceId,
    effectiveResourceKey,
    permissionLevelsHintDismissed,
    permissionLevelsHintExpanded,
    rbacActiveTabKey,
    rbacMode,
    rbacPermissionsList.level,
    rbacPermissionsList.principal_id,
    rbacPermissionsList.resource_id,
    rbacPermissionsList.search,
    rbacPermissionsPrincipalType,
    rbacPermissionsResourceKey,
    rbacPermissionsViewMode,
    selectedEffectiveUserId,
    userRolesList.role_id,
    userRolesList.search,
    userRolesViewMode,
  ])

  const [clusterGroupList, setClusterGroupList] = useState<{
    group_id?: number
    cluster_id?: string
    level?: PermissionLevelCode
    search: string
    page: number
    pageSize: number
  }>({ search: '', page: 1, pageSize: 50 })

  const [databaseGroupList, setDatabaseGroupList] = useState<{
    group_id?: number
    database_id?: string
    level?: PermissionLevelCode
    search: string
    page: number
    pageSize: number
  }>({ search: '', page: 1, pageSize: 50 })

  const [operationTemplateUserList, setOperationTemplateUserList] = useState<{
    user_id?: number
    template_id?: string
    level?: PermissionLevelCode
    search: string
    page: number
    pageSize: number
  }>({ search: '', page: 1, pageSize: 50 })

  const [operationTemplateGroupList, setOperationTemplateGroupList] = useState<{
    group_id?: number
    template_id?: string
    level?: PermissionLevelCode
    search: string
    page: number
    pageSize: number
  }>({ search: '', page: 1, pageSize: 50 })

  const [workflowTemplateUserList, setWorkflowTemplateUserList] = useState<{
    user_id?: number
    template_id?: string
    level?: PermissionLevelCode
    search: string
    page: number
    pageSize: number
  }>({ search: '', page: 1, pageSize: 50 })

  const [workflowTemplateGroupList, setWorkflowTemplateGroupList] = useState<{
    group_id?: number
    template_id?: string
    level?: PermissionLevelCode
    search: string
    page: number
    pageSize: number
  }>({ search: '', page: 1, pageSize: 50 })

  const [artifactUserList, setArtifactUserList] = useState<{
    user_id?: number
    artifact_id?: string
    level?: PermissionLevelCode
    search: string
    page: number
    pageSize: number
  }>({ search: '', page: 1, pageSize: 50 })

  const [artifactGroupList, setArtifactGroupList] = useState<{
    group_id?: number
    artifact_id?: string
    level?: PermissionLevelCode
    search: string
    page: number
    pageSize: number
  }>({ search: '', page: 1, pageSize: 50 })

  const [grantClusterForm] = Form.useForm<{
    user_id: number
    cluster_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [grantClusterGroupForm] = Form.useForm<{
    group_id: number
    cluster_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [grantDatabaseForm] = Form.useForm<{
    user_id: number
    database_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [grantDatabaseGroupForm] = Form.useForm<{
    group_id: number
    database_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [rbacPermissionsGrantForm] = Form.useForm<{
    principal_id: number
    resource_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [createRoleForm] = Form.useForm<{ name: string; reason: string }>()
  const [userRolesEditorForm] = Form.useForm<{
    mode?: 'replace' | 'add' | 'remove'
    group_ids?: number[]
    reason: string
  }>()

  const [grantOperationTemplateForm] = Form.useForm<{
    user_id: number
    template_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [grantOperationTemplateGroupForm] = Form.useForm<{
    group_id: number
    template_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [grantWorkflowTemplateForm] = Form.useForm<{
    user_id: number
    template_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [grantWorkflowTemplateGroupForm] = Form.useForm<{
    group_id: number
    template_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [grantArtifactForm] = Form.useForm<{
    user_id: number
    artifact_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [grantArtifactGroupForm] = Form.useForm<{
    group_id: number
    artifact_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [ibUserForm] = Form.useForm<{
    database_id: string
    user_id?: number | null
    ib_username: string
    ib_display_name?: string
    ib_roles?: string[]
    ib_password?: string
    auth_type?: InfobaseUserMapping['auth_type']
    is_service?: boolean
    notes?: string
  }>()

	  const rbacPermissionsGrantResourceId = Form.useWatch('resource_id', rbacPermissionsGrantForm)
	  const ibUserFormDatabaseId = Form.useWatch('database_id', ibUserForm)
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

	  useEffect(() => {
	    if (rbacPermissionsViewMode !== 'resource') return
	    setRbacPermissionsList((prev) => {
	      if (prev.principal_id === undefined && prev.page === 1) return prev
	      return { ...prev, principal_id: undefined, page: 1 }
	    })
	  }, [rbacPermissionsViewMode])

	  useEffect(() => {
	    if (rbacPermissionsViewMode !== 'resource') return
	    if (!rbacPermissionsList.resource_id) return
	    rbacPermissionsGrantForm.setFieldValue('resource_id', rbacPermissionsList.resource_id)
	  }, [rbacPermissionsViewMode, rbacPermissionsList.resource_id, rbacPermissionsGrantForm])

	  const parseUserId = (value: unknown): number | undefined => {
	    if (typeof value === 'number' && Number.isFinite(value)) return value
	    if (typeof value !== 'string') return undefined
    const parsed = Number.parseInt(value, 10)
    return Number.isNaN(parsed) ? undefined : parsed
  }

  const normalizeString = (value: unknown): string | undefined => {
    if (typeof value !== 'string') return undefined
    const trimmed = value.trim()
    return trimmed ? trimmed : undefined
  }

  const handleDatabasesLoaded = (items: Array<{ id: string; name: string }>) => {
    items.forEach((db) => {
      databasesLabelById.current.set(db.id, `${db.name} #${db.id}`)
    })
  }

  const clustersSelectOptions: SelectOption[] = clusters.map((c) => ({ label: `${c.name} #${c.id}`, value: c.id }))

  const rbacPermissionsSelectedResourceIds: Array<string | undefined> = [
    typeof rbacPermissionsGrantResourceId === 'string' ? rbacPermissionsGrantResourceId : undefined,
    rbacPermissionsList.resource_id,
  ]

  const databasesSelectOptions = ensureSelectOptionsContain(
    databasesRefOptions,
    [
      ...(rbacPermissionsResourceKey === 'databases' ? rbacPermissionsSelectedResourceIds : []),
      selectedIbDatabaseId,
      typeof ibUserFormDatabaseId === 'string' ? ibUserFormDatabaseId : undefined,
    ],
    databasesLabelById.current
  )

  const operationTemplatesSelectOptions = ensureSelectOptionsContain(
    operationTemplatesRefOptions,
    rbacPermissionsResourceKey === 'operation-templates' ? rbacPermissionsSelectedResourceIds : [],
    operationTemplatesLabelById.current
  )

  const workflowTemplatesSelectOptions = ensureSelectOptionsContain(
    workflowTemplatesRefOptions,
    rbacPermissionsResourceKey === 'workflow-templates' ? rbacPermissionsSelectedResourceIds : [],
    workflowTemplatesLabelById.current
  )

  const artifactsSelectOptions = ensureSelectOptionsContain(
    artifactsRefOptions,
    rbacPermissionsResourceKey === 'artifacts' ? rbacPermissionsSelectedResourceIds : [],
    artifactsLabelById.current
  )

  const rbacPermissionsResourceRef = (() => {
    if (rbacPermissionsResourceKey === 'clusters') {
      return {
        options: clustersSelectOptions,
        loading: clustersRefQuery.isFetching,
        showSearch: true,
        filterOption: true as const,
        onSearch: undefined,
        onPopupScroll: undefined,
      }
    }

    if (rbacPermissionsResourceKey === 'databases') {
      return {
        options: databasesSelectOptions,
        loading: databasesRefQuery.isFetching,
        showSearch: true,
        filterOption: false as const,
        onSearch: setDatabasesRefSearch,
        onPopupScroll: handleDatabasesPopupScroll,
      }
    }

    if (rbacPermissionsResourceKey === 'operation-templates') {
      return {
        options: operationTemplatesSelectOptions,
        loading: operationTemplatesRefQuery.isFetching,
        showSearch: true,
        filterOption: false as const,
        onSearch: setOperationTemplatesRefSearch,
        onPopupScroll: handleOperationTemplatesPopupScroll,
      }
    }

    if (rbacPermissionsResourceKey === 'workflow-templates') {
      return {
        options: workflowTemplatesSelectOptions,
        loading: workflowTemplatesRefQuery.isFetching,
        showSearch: true,
        filterOption: false as const,
        onSearch: setWorkflowTemplatesRefSearch,
        onPopupScroll: handleWorkflowTemplatesPopupScroll,
      }
    }

    return {
      options: artifactsSelectOptions,
      loading: artifactsRefQuery.isFetching,
      showSearch: true,
      filterOption: false as const,
      onSearch: setArtifactsRefSearch,
      onPopupScroll: handleArtifactsPopupScroll,
    }
  })()

  const rbacPermissionsResourceSearchValue: string = (() => {
    switch (rbacPermissionsResourceKey) {
      case 'clusters':
        return clustersRefSearch
      case 'databases':
        return databasesRefSearch
      case 'operation-templates':
        return operationTemplatesRefSearch
      case 'workflow-templates':
        return workflowTemplatesRefSearch
      case 'artifacts':
        return artifactsRefSearch
    }
  })()

  const setRbacPermissionsResourceSearchValue = (value: string) => {
    switch (rbacPermissionsResourceKey) {
      case 'clusters':
        setClustersRefSearch(value)
        return
      case 'databases':
        setDatabasesRefSearch(value)
        return
      case 'operation-templates':
        setOperationTemplatesRefSearch(value)
        return
      case 'workflow-templates':
        setWorkflowTemplatesRefSearch(value)
        return
      case 'artifacts':
        setArtifactsRefSearch(value)
        return
    }
  }

  const rbacPermissionsResourceBrowserOptions = useMemo(() => {
    const options = rbacPermissionsResourceRef.options
    if (rbacPermissionsResourceKey !== 'clusters') return options
    const query = clustersRefSearch.trim().toLowerCase()
    if (!query) return options
    return options.filter((opt) => (
      opt.label.toLowerCase().includes(query) || opt.value.toLowerCase().includes(query)
    ))
  }, [rbacPermissionsResourceKey, clustersRefSearch, rbacPermissionsResourceRef.options])

  const rbacPermissionsSelectedResourceLabel = useMemo(() => {
    const id = rbacPermissionsList.resource_id
    if (!id) return undefined
    const match = rbacPermissionsResourceRef.options.find((opt) => opt.value === id)
    return match?.label ?? id
  }, [rbacPermissionsList.resource_id, rbacPermissionsResourceRef.options])

  const effectiveResourceRef = (() => {
    if (effectiveResourceKey === 'operation-templates') {
      return {
        options: ensureSelectOptionsContain(operationTemplatesRefOptions, [effectiveResourceId], operationTemplatesLabelById.current),
        loading: operationTemplatesRefQuery.isFetching,
        showSearch: true,
        filterOption: false as const,
        onSearch: setOperationTemplatesRefSearch,
        onPopupScroll: handleOperationTemplatesPopupScroll,
      }
    }

    if (effectiveResourceKey === 'workflow-templates') {
      return {
        options: ensureSelectOptionsContain(workflowTemplatesRefOptions, [effectiveResourceId], workflowTemplatesLabelById.current),
        loading: workflowTemplatesRefQuery.isFetching,
        showSearch: true,
        filterOption: false as const,
        onSearch: setWorkflowTemplatesRefSearch,
        onPopupScroll: handleWorkflowTemplatesPopupScroll,
      }
    }

    if (effectiveResourceKey === 'artifacts') {
      return {
        options: ensureSelectOptionsContain(artifactsRefOptions, [effectiveResourceId], artifactsLabelById.current),
        loading: artifactsRefQuery.isFetching,
        showSearch: true,
        filterOption: false as const,
        onSearch: setArtifactsRefSearch,
        onPopupScroll: handleArtifactsPopupScroll,
      }
    }

    return undefined
  })()

  const effectiveResourcePlaceholder = (() => {
    switch (effectiveResourceKey) {
      case 'clusters':
        return 'Кластер (опционально)'
      case 'databases':
        return 'База (опционально)'
      case 'operation-templates':
        return 'Шаблон операции (опционально)'
      case 'workflow-templates':
        return 'Шаблон рабочего процесса (опционально)'
      case 'artifacts':
        return 'Артефакт (опционально)'
    }
  })()

  const handleIbUserEdit = (record: InfobaseUserMapping) => {
    setSelectedIbDatabaseId(record.database_id)
    setEditingIbUser(record)
    ibUserForm.setFieldsValue({
      database_id: record.database_id,
      user_id: record.user?.id ?? null,
      ib_username: record.ib_username,
      ib_display_name: record.ib_display_name ?? '',
      ib_roles: record.ib_roles ?? [],
      ib_password: '',
      auth_type: record.auth_type,
      is_service: record.is_service,
      notes: record.notes ?? '',
    })
  }

  const handleIbUserResetForm = () => {
    setEditingIbUser(null)
    ibUserForm.resetFields()
    if (selectedIbDatabaseId) {
      ibUserForm.setFieldsValue({ database_id: selectedIbDatabaseId })
    }
  }

  const handleIbUserSave = async () => {
    const values = await ibUserForm.validateFields()
    const payloadBase = {
      user_id: values.user_id ?? null,
      ib_username: values.ib_username?.trim(),
      ib_display_name: values.ib_display_name?.trim(),
      ib_roles: (values.ib_roles ?? []).map((role: string) => role.trim()).filter(Boolean),
      auth_type: values.auth_type,
      is_service: Boolean(values.is_service),
      notes: values.notes?.trim(),
    }

    if (editingIbUser) {
      updateInfobaseUser.mutate(
        { id: editingIbUser.id, ...payloadBase },
        { onSuccess: handleIbUserResetForm }
      )
      return
    }

    createInfobaseUser.mutate(
      { database_id: values.database_id, ...payloadBase, ib_password: values.ib_password?.trim() || undefined },
      { onSuccess: handleIbUserResetForm }
    )
  }

  const handleIbUserDelete = (record: InfobaseUserMapping) => {
    modal.confirm({
      title: `Удалить пользователя ИБ ${record.ib_username}?`,
      content: 'Запись будет удалена только в Command Center.',
      okText: 'Удалить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: () => deleteInfobaseUser.mutate({ id: record.id, databaseId: record.database_id }),
    })
  }

  const handleIbUserPasswordUpdate = async () => {
    if (!editingIbUser) {
      return
    }
    const password = ibUserForm.getFieldValue('ib_password')?.trim()
    if (!password) {
      modal.warning({
        title: 'Введите пароль',
        content: 'Укажите новый пароль ИБ перед сохранением.',
      })
      return
    }
    setInfobaseUserPassword.mutate(
      { id: editingIbUser.id, password },
      {
        onSuccess: () => {
          ibUserForm.setFieldsValue({ ib_password: '' })
        },
      }
    )
  }

  const handleIbUserPasswordReset = () => {
    if (!editingIbUser) {
      return
    }
    modal.confirm({
      title: `Сбросить пароль для ${editingIbUser.ib_username}?`,
      content: 'Пароль будет очищен.',
      okText: 'Сбросить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: () => resetInfobaseUserPassword.mutate({
        id: editingIbUser.id,
        databaseId: editingIbUser.database_id,
      }),
    })
  }

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

  const clusterFallbackColumns = useMemo(() => [
    { key: 'user_id', label: 'Пользователь', groupKey: 'core', groupLabel: 'Основное' },
    { key: 'cluster', label: 'Кластер', groupKey: 'core', groupLabel: 'Основное' },
    { key: 'level', label: 'Уровень', groupKey: 'meta', groupLabel: 'Метаданные' },
    { key: 'granted_at', label: 'Выдано', groupKey: 'time', groupLabel: 'Время' },
    { key: 'granted_by', label: 'Кем выдано', groupKey: 'meta', groupLabel: 'Метаданные' },
    { key: 'notes', label: 'Комментарий', groupKey: 'meta', groupLabel: 'Метаданные' },
    { key: 'actions', label: 'Действия', groupKey: 'actions', groupLabel: 'Действия' },
  ], [])

  const databaseFallbackColumns = useMemo(() => [
    { key: 'user_id', label: 'Пользователь', groupKey: 'core', groupLabel: 'Основное' },
    { key: 'database', label: 'База', groupKey: 'core', groupLabel: 'Основное' },
    { key: 'database_id', label: 'ID базы', groupKey: 'core', groupLabel: 'Основное' },
    { key: 'level', label: 'Уровень', groupKey: 'meta', groupLabel: 'Метаданные' },
    { key: 'granted_at', label: 'Выдано', groupKey: 'time', groupLabel: 'Время' },
    { key: 'granted_by', label: 'Кем выдано', groupKey: 'meta', groupLabel: 'Метаданные' },
    { key: 'notes', label: 'Комментарий', groupKey: 'meta', groupLabel: 'Метаданные' },
    { key: 'actions', label: 'Действия', groupKey: 'actions', groupLabel: 'Действия' },
  ], [])

  const clusterColumns: ColumnsType<ClusterPermission> = useMemo(
    () => [
      {
        title: 'Пользователь',
        key: 'user_id',
        render: (_, row) => (
          <span>
            {row.user?.username} <Text type="secondary">#{row.user?.id}</Text>
          </span>
        ),
      },
      { title: 'Кластер', dataIndex: ['cluster', 'name'], key: 'cluster' },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      { title: 'Выдано', dataIndex: 'granted_at', key: 'granted_at' },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_, row) => (
          <Button
            danger
            size="small"
            loading={revokeCluster.isPending}
            onClick={() => {
              if (!row.user?.id || !row.cluster?.id) return
              confirmReason('Отозвать доступ пользователя к кластеру?', async (reason) => {
                await revokeCluster.mutateAsync({ user_id: row.user.id, cluster_id: row.cluster.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeCluster]
  )

  const databaseColumns: ColumnsType<DatabasePermission> = useMemo(
    () => [
      {
        title: 'Пользователь',
        key: 'user_id',
        render: (_, row) => (
          <span>
            {row.user?.username} <Text type="secondary">#{row.user?.id}</Text>
          </span>
        ),
      },
      { title: 'База', dataIndex: ['database', 'name'], key: 'database' },
      { title: 'ID базы', dataIndex: ['database', 'id'], key: 'database_id' },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      { title: 'Выдано', dataIndex: 'granted_at', key: 'granted_at' },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_, row) => (
          <Button
            danger
            size="small"
            loading={revokeDatabase.isPending}
            onClick={() => {
              if (!row.user?.id || !row.database?.id) return
              confirmReason('Отозвать доступ пользователя к базе?', async (reason) => {
                await revokeDatabase.mutateAsync({ user_id: row.user.id, database_id: row.database.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeDatabase]
  )

  const clusterGroupColumns: ColumnsType<ClusterGroupPermission> = useMemo(
    () => [
      {
        title: 'Группа',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Кластер',
        key: 'cluster',
        render: (_: unknown, row) => (
          <span>
            {row.cluster.name} <Text type="secondary">#{row.cluster.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeClusterGroup.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ группы к кластеру?', async (reason) => {
                await revokeClusterGroup.mutateAsync({ group_id: row.group.id, cluster_id: row.cluster.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeClusterGroup]
  )

  const databaseGroupColumns: ColumnsType<DatabaseGroupPermission> = useMemo(
    () => [
      {
        title: 'Группа',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'База',
        key: 'database',
        render: (_: unknown, row) => (
          <span>
            {row.database.name} <Text type="secondary">#{row.database.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeDatabaseGroup.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ группы к базе?', async (reason) => {
                await revokeDatabaseGroup.mutateAsync({ group_id: row.group.id, database_id: row.database.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeDatabaseGroup]
  )

  const operationTemplateUserColumns: ColumnsType<OperationTemplatePermission> = useMemo(
    () => [
      {
        title: 'Пользователь',
        key: 'user',
        render: (_: unknown, row) => (
          <span>
            {row.user.username} <Text type="secondary">#{row.user.id}</Text>
          </span>
        ),
      },
      {
        title: 'Шаблон операции',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeOperationTemplate.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ пользователя к шаблону операции?', async (reason) => {
                await revokeOperationTemplate.mutateAsync({ user_id: row.user.id, template_id: row.template.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeOperationTemplate]
  )

  const operationTemplateGroupColumns: ColumnsType<OperationTemplateGroupPermission> = useMemo(
    () => [
      {
        title: 'Группа',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Шаблон операции',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeOperationTemplateGroup.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ группы к шаблону операции?', async (reason) => {
                await revokeOperationTemplateGroup.mutateAsync({ group_id: row.group.id, template_id: row.template.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeOperationTemplateGroup]
  )

  const workflowTemplateUserColumns: ColumnsType<WorkflowTemplatePermission> = useMemo(
    () => [
      {
        title: 'Пользователь',
        key: 'user',
        render: (_: unknown, row) => (
          <span>
            {row.user.username} <Text type="secondary">#{row.user.id}</Text>
          </span>
        ),
      },
      {
        title: 'Шаблон рабочего процесса',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeWorkflowTemplate.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ пользователя к шаблону рабочего процесса?', async (reason) => {
                await revokeWorkflowTemplate.mutateAsync({ user_id: row.user.id, template_id: row.template.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeWorkflowTemplate]
  )

  const workflowTemplateGroupColumns: ColumnsType<WorkflowTemplateGroupPermission> = useMemo(
    () => [
      {
        title: 'Группа',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Шаблон рабочего процесса',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeWorkflowTemplateGroup.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ группы к шаблону рабочего процесса?', async (reason) => {
                await revokeWorkflowTemplateGroup.mutateAsync({ group_id: row.group.id, template_id: row.template.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeWorkflowTemplateGroup]
  )

  const artifactUserColumns: ColumnsType<ArtifactPermission> = useMemo(
    () => [
      {
        title: 'Пользователь',
        key: 'user',
        render: (_: unknown, row) => (
          <span>
            {row.user.username} <Text type="secondary">#{row.user.id}</Text>
          </span>
        ),
      },
      {
        title: 'Артефакт',
        key: 'artifact',
        render: (_: unknown, row) => (
          <span>
            {row.artifact.name} <Text type="secondary">#{row.artifact.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeArtifact.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ пользователя к артефакту?', async (reason) => {
                await revokeArtifact.mutateAsync({ user_id: row.user.id, artifact_id: row.artifact.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeArtifact]
  )

  const artifactGroupColumns: ColumnsType<ArtifactGroupPermission> = useMemo(
    () => [
      {
        title: 'Группа',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Артефакт',
        key: 'artifact',
        render: (_: unknown, row) => (
          <span>
            {row.artifact.name} <Text type="secondary">#{row.artifact.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeArtifactGroup.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ группы к артефакту?', async (reason) => {
                await revokeArtifactGroup.mutateAsync({ group_id: row.group.id, artifact_id: row.artifact.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeArtifactGroup]
  )

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

  const ibAuthTypeLabels: Record<string, string> = {
    local: 'Локальная',
    ad: 'AD',
    service: 'Сервисная',
    other: 'Другая',
  }

  const ibUsersColumns: ColumnsType<InfobaseUserMapping> = useMemo(
    () => [
      {
        title: 'Пользователь ИБ',
        key: 'ib_user',
        render: (_: unknown, row) => (
          <span>
            {row.ib_username}{' '}
            <Text type="secondary">{row.ib_display_name || '-'}</Text>
          </span>
        ),
      },
      {
        title: 'Пользователь CC',
        key: 'cc_user',
        render: (_: unknown, row) => (
          row.user
            ? (
              <span>
                {row.user.username} <Text type="secondary">#{row.user.id}</Text>
              </span>
            )
            : '-'
        ),
      },
      {
        title: 'Роли',
        key: 'roles',
        render: (_: unknown, row) => (
          <Space size="small" wrap>
            {(row.ib_roles || []).length > 0
              ? row.ib_roles.map((role) => <Tag key={role}>{role}</Tag>)
              : <Tag color="default">-</Tag>}
          </Space>
        ),
      },
      {
        title: 'Аутентификация',
        key: 'auth_type',
        render: (_: unknown, row) => (
          <Tag>{ibAuthTypeLabels[row.auth_type] || row.auth_type}</Tag>
        ),
      },
      {
        title: 'Сервисный',
        key: 'is_service',
        render: (_: unknown, row) => (
          <Tag color={row.is_service ? 'blue' : 'default'}>
            {row.is_service ? 'Да' : 'Нет'}
          </Tag>
        ),
      },
      {
        title: 'Пароль',
        key: 'password',
        render: (_: unknown, row) => (
          <Tag color={row.ib_password_configured ? 'green' : 'default'}>
            {row.ib_password_configured ? 'Задан' : 'Не задан'}
          </Tag>
        ),
      },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Space size="small">
            <Button size="small" onClick={() => handleIbUserEdit(row)}>
              Редактировать
            </Button>
            <Button
              danger
              size="small"
              loading={deleteInfobaseUser.isPending}
              onClick={() => handleIbUserDelete(row)}
            >
              Удалить
            </Button>
          </Space>
        ),
      },
    ],
    [deleteInfobaseUser.isPending, handleIbUserDelete, handleIbUserEdit]
  )

  const clusterTable = useTableToolkit({
    tableId: 'rbac_clusters',
    columns: clusterColumns,
    fallbackColumns: clusterFallbackColumns,
    initialPageSize: 50,
  })

  const databaseTable = useTableToolkit({
    tableId: 'rbac_databases',
    columns: databaseColumns,
    fallbackColumns: databaseFallbackColumns,
    initialPageSize: 50,
  })

  const ibUsersTable = useTableToolkit({
    tableId: 'rbac_ib_users',
    columns: ibUsersColumns,
    fallbackColumns: [
      { key: 'ib_username', label: 'Пользователь ИБ', groupKey: 'core', groupLabel: 'Основное' },
      { key: 'ib_display_name', label: 'Имя в ИБ', groupKey: 'core', groupLabel: 'Основное' },
      { key: 'cc_user', label: 'Пользователь CC', groupKey: 'core', groupLabel: 'Основное' },
      { key: 'roles', label: 'Роли', groupKey: 'meta', groupLabel: 'Метаданные' },
      { key: 'auth_type', label: 'Аутентификация', groupKey: 'meta', groupLabel: 'Метаданные' },
      { key: 'is_service', label: 'Сервисный', groupKey: 'meta', groupLabel: 'Метаданные' },
      { key: 'password', label: 'Пароль', groupKey: 'meta', groupLabel: 'Метаданные' },
      { key: 'actions', label: 'Действия', groupKey: 'actions', groupLabel: 'Действия' },
    ],
    initialPageSize: 25,
  })

  const clusterPageStart = (clusterTable.pagination.page - 1) * clusterTable.pagination.pageSize
  const databasePageStart = (databaseTable.pagination.page - 1) * databaseTable.pagination.pageSize
  const ibUsersPageStart = (ibUsersTable.pagination.page - 1) * ibUsersTable.pagination.pageSize

  const clusterPermissionsQuery = useClusterPermissions({
    user_id: parseUserId(clusterTable.filters.user_id),
    level: normalizeString(clusterTable.filters.level) as PermissionLevelCode | undefined,
    search: clusterTable.search || undefined,
    limit: clusterTable.pagination.pageSize,
    offset: clusterPageStart,
  }, { enabled: canManageRbac })
  const databasePermissionsQuery = useDatabasePermissions({
    user_id: parseUserId(databaseTable.filters.user_id),
    database_id: normalizeString(databaseTable.filters.database_id),
    level: normalizeString(databaseTable.filters.level) as PermissionLevelCode | undefined,
    search: databaseTable.search || undefined,
    limit: databaseTable.pagination.pageSize,
    offset: databasePageStart,
  }, { enabled: canManageRbac })

  const ibUsersQuery = useInfobaseUsers({
    databaseId: selectedIbDatabaseId,
    search: ibUsersTable.search || undefined,
    authType: ibAuthFilter === 'any' ? undefined : (ibAuthFilter as 'local' | 'ad' | 'service' | 'other'),
    isService: ibServiceFilter === 'any' ? undefined : ibServiceFilter === 'true',
    hasUser: ibHasUserFilter === 'any' ? undefined : ibHasUserFilter === 'true',
    limit: ibUsersTable.pagination.pageSize,
    offset: ibUsersPageStart,
  })

  const debouncedUserSearch = useDebouncedValue(userSearch, 300)
  const usersQuery = useRbacUsers({
    search: debouncedUserSearch || undefined,
    limit: 20,
    offset: 0,
  }, { enabled: canManageRbac })

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

  const effectiveIncludeClusters = effectiveResourceKey === 'clusters'
  const effectiveIncludeDatabases = effectiveResourceKey === 'databases'
  const effectiveIncludeOperationTemplates = effectiveResourceKey === 'operation-templates'
  const effectiveIncludeWorkflowTemplates = effectiveResourceKey === 'workflow-templates'
  const effectiveIncludeArtifacts = effectiveResourceKey === 'artifacts'
  const effectiveDbPaginationEnabled = effectiveIncludeDatabases && !effectiveResourceId

  const effectiveAccessQuery = useEffectiveAccess(selectedEffectiveUserId, {
    includeDatabases: effectiveIncludeDatabases,
    includeClusters: effectiveIncludeClusters,
    includeTemplates: effectiveIncludeOperationTemplates,
    includeWorkflows: effectiveIncludeWorkflowTemplates,
    includeArtifacts: effectiveIncludeArtifacts,
    limit: effectiveDbPaginationEnabled ? effectiveDbPageSize : undefined,
    offset: effectiveDbPaginationEnabled ? (effectiveDbPage - 1) * effectiveDbPageSize : undefined,
    enabled: canManageRbac && Boolean(selectedEffectiveUserId),
  })

  const clusterGroupPermissionsQuery = useClusterGroupPermissions({
    group_id: clusterGroupList.group_id,
    cluster_id: clusterGroupList.cluster_id,
    level: clusterGroupList.level,
    search: clusterGroupList.search || undefined,
    limit: clusterGroupList.pageSize,
    offset: (clusterGroupList.page - 1) * clusterGroupList.pageSize,
  }, { enabled: canManageRbac })

  const databaseGroupPermissionsQuery = useDatabaseGroupPermissions({
    group_id: databaseGroupList.group_id,
    database_id: databaseGroupList.database_id,
    level: databaseGroupList.level,
    search: databaseGroupList.search || undefined,
    limit: databaseGroupList.pageSize,
    offset: (databaseGroupList.page - 1) * databaseGroupList.pageSize,
  }, { enabled: canManageRbac })

  const operationTemplatePermissionsQuery = useOperationTemplatePermissions({
    user_id: operationTemplateUserList.user_id,
    template_id: operationTemplateUserList.template_id,
    level: operationTemplateUserList.level,
    search: operationTemplateUserList.search || undefined,
    limit: operationTemplateUserList.pageSize,
    offset: (operationTemplateUserList.page - 1) * operationTemplateUserList.pageSize,
  }, { enabled: canManageRbac })

  const operationTemplateGroupPermissionsQuery = useOperationTemplateGroupPermissions({
    group_id: operationTemplateGroupList.group_id,
    template_id: operationTemplateGroupList.template_id,
    level: operationTemplateGroupList.level,
    search: operationTemplateGroupList.search || undefined,
    limit: operationTemplateGroupList.pageSize,
    offset: (operationTemplateGroupList.page - 1) * operationTemplateGroupList.pageSize,
  }, { enabled: canManageRbac })

  const workflowTemplatePermissionsQuery = useWorkflowTemplatePermissions({
    user_id: workflowTemplateUserList.user_id,
    template_id: workflowTemplateUserList.template_id,
    level: workflowTemplateUserList.level,
    search: workflowTemplateUserList.search || undefined,
    limit: workflowTemplateUserList.pageSize,
    offset: (workflowTemplateUserList.page - 1) * workflowTemplateUserList.pageSize,
  }, { enabled: canManageRbac })

  const workflowTemplateGroupPermissionsQuery = useWorkflowTemplateGroupPermissions({
    group_id: workflowTemplateGroupList.group_id,
    template_id: workflowTemplateGroupList.template_id,
    level: workflowTemplateGroupList.level,
    search: workflowTemplateGroupList.search || undefined,
    limit: workflowTemplateGroupList.pageSize,
    offset: (workflowTemplateGroupList.page - 1) * workflowTemplateGroupList.pageSize,
  }, { enabled: canManageRbac })

  const artifactPermissionsQuery = useArtifactPermissions({
    user_id: artifactUserList.user_id,
    artifact_id: artifactUserList.artifact_id,
    level: artifactUserList.level,
    search: artifactUserList.search || undefined,
    limit: artifactUserList.pageSize,
    offset: (artifactUserList.page - 1) * artifactUserList.pageSize,
  }, { enabled: canManageRbac })

  const artifactGroupPermissionsQuery = useArtifactGroupPermissions({
    group_id: artifactGroupList.group_id,
    artifact_id: artifactGroupList.artifact_id,
    level: artifactGroupList.level,
    search: artifactGroupList.search || undefined,
    limit: artifactGroupList.pageSize,
    offset: (artifactGroupList.page - 1) * artifactGroupList.pageSize,
  }, { enabled: canManageRbac })

  const roleUsageEnabled = canManageRbac && Boolean(roleUsageRoleId)
  const roleUsageClustersQuery = useClusterGroupPermissions({
    group_id: roleUsageRoleId ?? undefined,
    limit: 1,
    offset: 0,
  }, { enabled: roleUsageEnabled })

  const roleUsageDatabasesQuery = useDatabaseGroupPermissions({
    group_id: roleUsageRoleId ?? undefined,
    limit: 1,
    offset: 0,
  }, { enabled: roleUsageEnabled })

  const roleUsageOperationTemplatesQuery = useOperationTemplateGroupPermissions({
    group_id: roleUsageRoleId ?? undefined,
    limit: 1,
    offset: 0,
  }, { enabled: roleUsageEnabled })

  const roleUsageWorkflowTemplatesQuery = useWorkflowTemplateGroupPermissions({
    group_id: roleUsageRoleId ?? undefined,
    limit: 1,
    offset: 0,
  }, { enabled: roleUsageEnabled })

  const roleUsageArtifactsQuery = useArtifactGroupPermissions({
    group_id: roleUsageRoleId ?? undefined,
    limit: 1,
    offset: 0,
  }, { enabled: roleUsageEnabled })

	  const rbacPermissionsEnabled = canManageRbac
	    && rbacActiveTabKey === 'permissions'
	    && (rbacPermissionsViewMode === 'principal' || Boolean(rbacPermissionsList.resource_id))
  const rbacPermissionsOffset = (rbacPermissionsList.page - 1) * rbacPermissionsList.pageSize
  const debouncedRbacPermissionsSearch = useDebouncedValue(rbacPermissionsList.search, 300)

  const rbacPermissionsClustersUserQuery = useClusterPermissions({
    user_id: rbacPermissionsList.principal_id,
    cluster_id: rbacPermissionsList.resource_id,
    level: rbacPermissionsList.level,
    search: debouncedRbacPermissionsSearch || undefined,
    limit: rbacPermissionsList.pageSize,
    offset: rbacPermissionsOffset,
  }, {
    enabled: rbacPermissionsEnabled && rbacPermissionsPrincipalType === 'user' && rbacPermissionsResourceKey === 'clusters',
  })

  const rbacPermissionsClustersRoleQuery = useClusterGroupPermissions({
    group_id: rbacPermissionsList.principal_id,
    cluster_id: rbacPermissionsList.resource_id,
    level: rbacPermissionsList.level,
    search: debouncedRbacPermissionsSearch || undefined,
    limit: rbacPermissionsList.pageSize,
    offset: rbacPermissionsOffset,
  }, {
    enabled: rbacPermissionsEnabled && rbacPermissionsPrincipalType === 'role' && rbacPermissionsResourceKey === 'clusters',
  })

  const rbacPermissionsDatabasesUserQuery = useDatabasePermissions({
    user_id: rbacPermissionsList.principal_id,
    database_id: rbacPermissionsList.resource_id,
    level: rbacPermissionsList.level,
    search: debouncedRbacPermissionsSearch || undefined,
    limit: rbacPermissionsList.pageSize,
    offset: rbacPermissionsOffset,
  }, {
    enabled: rbacPermissionsEnabled && rbacPermissionsPrincipalType === 'user' && rbacPermissionsResourceKey === 'databases',
  })

  const rbacPermissionsDatabasesRoleQuery = useDatabaseGroupPermissions({
    group_id: rbacPermissionsList.principal_id,
    database_id: rbacPermissionsList.resource_id,
    level: rbacPermissionsList.level,
    search: debouncedRbacPermissionsSearch || undefined,
    limit: rbacPermissionsList.pageSize,
    offset: rbacPermissionsOffset,
  }, {
    enabled: rbacPermissionsEnabled && rbacPermissionsPrincipalType === 'role' && rbacPermissionsResourceKey === 'databases',
  })

  const rbacPermissionsOperationTemplatesUserQuery = useOperationTemplatePermissions({
    user_id: rbacPermissionsList.principal_id,
    template_id: rbacPermissionsList.resource_id,
    level: rbacPermissionsList.level,
    search: debouncedRbacPermissionsSearch || undefined,
    limit: rbacPermissionsList.pageSize,
    offset: rbacPermissionsOffset,
  }, {
    enabled: rbacPermissionsEnabled && rbacPermissionsPrincipalType === 'user' && rbacPermissionsResourceKey === 'operation-templates',
  })

  const rbacPermissionsOperationTemplatesRoleQuery = useOperationTemplateGroupPermissions({
    group_id: rbacPermissionsList.principal_id,
    template_id: rbacPermissionsList.resource_id,
    level: rbacPermissionsList.level,
    search: debouncedRbacPermissionsSearch || undefined,
    limit: rbacPermissionsList.pageSize,
    offset: rbacPermissionsOffset,
  }, {
    enabled: rbacPermissionsEnabled && rbacPermissionsPrincipalType === 'role' && rbacPermissionsResourceKey === 'operation-templates',
  })

  const rbacPermissionsWorkflowTemplatesUserQuery = useWorkflowTemplatePermissions({
    user_id: rbacPermissionsList.principal_id,
    template_id: rbacPermissionsList.resource_id,
    level: rbacPermissionsList.level,
    search: debouncedRbacPermissionsSearch || undefined,
    limit: rbacPermissionsList.pageSize,
    offset: rbacPermissionsOffset,
  }, {
    enabled: rbacPermissionsEnabled && rbacPermissionsPrincipalType === 'user' && rbacPermissionsResourceKey === 'workflow-templates',
  })

  const rbacPermissionsWorkflowTemplatesRoleQuery = useWorkflowTemplateGroupPermissions({
    group_id: rbacPermissionsList.principal_id,
    template_id: rbacPermissionsList.resource_id,
    level: rbacPermissionsList.level,
    search: debouncedRbacPermissionsSearch || undefined,
    limit: rbacPermissionsList.pageSize,
    offset: rbacPermissionsOffset,
  }, {
    enabled: rbacPermissionsEnabled && rbacPermissionsPrincipalType === 'role' && rbacPermissionsResourceKey === 'workflow-templates',
  })

  const rbacPermissionsArtifactsUserQuery = useArtifactPermissions({
    user_id: rbacPermissionsList.principal_id,
    artifact_id: rbacPermissionsList.resource_id,
    level: rbacPermissionsList.level,
    search: debouncedRbacPermissionsSearch || undefined,
    limit: rbacPermissionsList.pageSize,
    offset: rbacPermissionsOffset,
  }, {
    enabled: rbacPermissionsEnabled && rbacPermissionsPrincipalType === 'user' && rbacPermissionsResourceKey === 'artifacts',
  })

  const rbacPermissionsArtifactsRoleQuery = useArtifactGroupPermissions({
    group_id: rbacPermissionsList.principal_id,
    artifact_id: rbacPermissionsList.resource_id,
    level: rbacPermissionsList.level,
    search: debouncedRbacPermissionsSearch || undefined,
    limit: rbacPermissionsList.pageSize,
    offset: rbacPermissionsOffset,
  }, {
    enabled: rbacPermissionsEnabled && rbacPermissionsPrincipalType === 'role' && rbacPermissionsResourceKey === 'artifacts',
  })

  const clusterPermissions = clusterPermissionsQuery.data?.permissions ?? []
  const totalClusterPermissions = typeof clusterPermissionsQuery.data?.total === 'number'
    ? clusterPermissionsQuery.data.total
    : clusterPermissions.length

  const databasePermissions = databasePermissionsQuery.data?.permissions ?? []
  const totalDatabasePermissions = typeof databasePermissionsQuery.data?.total === 'number'
    ? databasePermissionsQuery.data.total
    : databasePermissions.length

  const ibUsers = ibUsersQuery.data?.users ?? []
  const totalIbUsers = typeof ibUsersQuery.data?.total === 'number'
    ? ibUsersQuery.data.total
    : ibUsers.length

  const userOptions = useMemo(() => {
    const base = usersQuery.data?.users ?? []
    const extra = [
      ...(editingIbUser?.user ? [editingIbUser.user] : []),
    ]
    const combined = [...base, ...extra]
    const map = new Map<number, { label: string; value: number }>()
    combined.forEach((user) => {
      if (!map.has(user.id)) {
        map.set(user.id, { label: `${user.username} #${user.id}`, value: user.id })
      }
    })
    return Array.from(map.values())
  }, [usersQuery.data?.users, editingIbUser?.user])

  const clusterNameById = useMemo(() => (
    new Map(clusters.map((c) => [c.id, c.name]))
  ), [clusters])

  const roles = rolesQuery.data?.roles ?? []
  const roleNameById = useMemo(() => (
    new Map(roles.map((role) => [role.id, role.name]))
  ), [roles])
  const visibleRoles = useMemo(() => {
    const query = roleSearch.trim().toLowerCase()
    if (!query) return roles
    return roles.filter((role) => role.name.toLowerCase().includes(query))
  }, [roleSearch, roles])
  const roleOptions = useMemo(() => (
    roles.map((role) => ({ label: `${role.name} #${role.id}`, value: role.id }))
  ), [roles])
  const selectedRoleForUserRoles = useMemo(() => (
    typeof userRolesList.role_id === 'number'
      ? roles.find((role) => role.id === userRolesList.role_id) ?? null
      : null
  ), [roles, userRolesList.role_id])

  const userRolesUsers = userRolesUsersQuery.data?.users ?? []
  const totalUserRolesUsers = typeof userRolesUsersQuery.data?.total === 'number'
    ? userRolesUsersQuery.data.total
    : userRolesUsers.length

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

  const capabilities = capabilitiesQuery.data?.capabilities ?? []
  const capabilityOptions = useMemo(() => (
    capabilities.map((cap) => ({ label: cap.exists ? cap.code : `${cap.code} (нет)`, value: cap.code }))
  ), [capabilities])

  const effectiveSourceLabel = useCallback((source: string) => {
    if (source === 'direct') return 'прямое'
    if (source === 'group') return 'группа'
    if (source === 'cluster') return 'кластер'
    return source
  }, [])

  const effectiveClustersColumns: ColumnsType<EffectiveAccessClusterItem> = useMemo(() => [
    {
      title: 'Кластер',
      key: 'cluster',
      render: (_: unknown, row) => (
        <span>
          {row.cluster.name} <Text type="secondary">#{row.cluster.id}</Text>
        </span>
      ),
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
  ], [])

  const effectiveDatabasesColumns: ColumnsType<EffectiveAccessDatabaseItem> = useMemo(() => [
    {
      title: 'База',
      key: 'database',
      render: (_: unknown, row) => (
        <span>
          {row.database.name} <Text type="secondary">#{row.database.id}</Text>
        </span>
      ),
    },
    {
      title: 'Кластер',
      key: 'cluster',
      render: (_: unknown, row) => {
        const clusterId = row.database.cluster_id
        if (!clusterId) return '-'
        const name = clusterNameById.get(clusterId)
        return (
          <span>
            {name ?? '-'} <Text type="secondary">#{clusterId}</Text>
          </span>
        )
      },
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => {
        const source = row.source
        const color = source === 'direct' ? 'blue' : source === 'group' ? 'purple' : 'gold'
        return <Tag color={color}>{source === 'cluster' ? 'через кластер' : effectiveSourceLabel(source)}</Tag>
      },
    },
    {
      title: 'Через кластер',
      key: 'via_cluster_id',
      render: (_: unknown, row) => {
        if (row.source !== 'cluster') return '-'
        const viaId = row.via_cluster_id
        if (!viaId) return '-'
        const name = clusterNameById.get(viaId)
        return (
          <span>
            {name ?? '-'} <Text type="secondary">#{viaId}</Text>
          </span>
        )
      },
    },
  ], [clusterNameById, effectiveSourceLabel])

  const effectiveOperationTemplatesColumns: ColumnsType<EffectiveAccessOperationTemplateItem> = useMemo(() => [
    {
      title: 'Шаблон операции',
      key: 'template',
      render: (_: unknown, row) => (
        <span>
          {row.template.name} <Text type="secondary">#{row.template.id}</Text>
        </span>
      ),
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
  ], [effectiveSourceLabel])

  const effectiveWorkflowTemplatesColumns: ColumnsType<EffectiveAccessWorkflowTemplateItem> = useMemo(() => [
    {
      title: 'Шаблон рабочего процесса',
      key: 'template',
      render: (_: unknown, row) => (
        <span>
          {row.template.name} <Text type="secondary">#{row.template.id}</Text>
        </span>
      ),
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
  ], [effectiveSourceLabel])

  const effectiveArtifactsColumns: ColumnsType<EffectiveAccessArtifactItem> = useMemo(() => [
    {
      title: 'Артефакт',
      key: 'artifact',
      render: (_: unknown, row) => (
        <span>
          {row.artifact.name} <Text type="secondary">#{row.artifact.id}</Text>
        </span>
      ),
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
  ], [effectiveSourceLabel])

  const effectiveClusterSourcesColumns: ColumnsType<EffectiveAccessClusterSourceItem> = useMemo(() => [
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => {
        const source = row.source
        return <Tag color={getEffectiveAccessSourceTagColor(source)}>{effectiveSourceLabel(source)}</Tag>
      },
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
  ], [effectiveSourceLabel])

  const effectiveDatabaseSourcesColumns: ColumnsType<EffectiveAccessDatabaseSourceItem> = useMemo(() => [
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => {
        const source = row.source
        return <Tag color={getEffectiveAccessSourceTagColor(source)}>{effectiveSourceLabel(source)}</Tag>
      },
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
    {
      title: 'Через кластер',
      key: 'via_cluster_id',
      render: (_: unknown, row) => {
        if (row.source !== 'cluster') return '-'
        const viaId = row.via_cluster_id
        if (!viaId) return '-'
        const name = clusterNameById.get(viaId)
        return (
          <span>
            {name ?? '-'} <Text type="secondary">#{viaId}</Text>
          </span>
        )
      },
    },
  ], [clusterNameById, effectiveSourceLabel])

  const effectiveOperationTemplateSourcesColumns: ColumnsType<EffectiveAccessOperationTemplateSourceItem> = useMemo(() => [
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
  ], [effectiveSourceLabel])

  const effectiveWorkflowTemplateSourcesColumns: ColumnsType<EffectiveAccessWorkflowTemplateSourceItem> = useMemo(() => [
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
  ], [effectiveSourceLabel])

  const effectiveArtifactSourcesColumns: ColumnsType<EffectiveAccessArtifactSourceItem> = useMemo(() => [
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
  ], [effectiveSourceLabel])

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

  const clusterGroupPermissions = clusterGroupPermissionsQuery.data?.permissions ?? []
  const totalClusterGroupPermissions = typeof clusterGroupPermissionsQuery.data?.total === 'number'
    ? clusterGroupPermissionsQuery.data.total
    : clusterGroupPermissions.length

  const databaseGroupPermissions = databaseGroupPermissionsQuery.data?.permissions ?? []
  const totalDatabaseGroupPermissions = typeof databaseGroupPermissionsQuery.data?.total === 'number'
    ? databaseGroupPermissionsQuery.data.total
    : databaseGroupPermissions.length

  const operationTemplatePermissions = operationTemplatePermissionsQuery.data?.permissions ?? []
  const totalOperationTemplatePermissions = typeof operationTemplatePermissionsQuery.data?.total === 'number'
    ? operationTemplatePermissionsQuery.data.total
    : operationTemplatePermissions.length

  const operationTemplateGroupPermissions = operationTemplateGroupPermissionsQuery.data?.permissions ?? []
  const totalOperationTemplateGroupPermissions = typeof operationTemplateGroupPermissionsQuery.data?.total === 'number'
    ? operationTemplateGroupPermissionsQuery.data.total
    : operationTemplateGroupPermissions.length

  const workflowTemplatePermissions = workflowTemplatePermissionsQuery.data?.permissions ?? []
  const totalWorkflowTemplatePermissions = typeof workflowTemplatePermissionsQuery.data?.total === 'number'
    ? workflowTemplatePermissionsQuery.data.total
    : workflowTemplatePermissions.length

  const workflowTemplateGroupPermissions = workflowTemplateGroupPermissionsQuery.data?.permissions ?? []
  const totalWorkflowTemplateGroupPermissions = typeof workflowTemplateGroupPermissionsQuery.data?.total === 'number'
    ? workflowTemplateGroupPermissionsQuery.data.total
    : workflowTemplateGroupPermissions.length

  const artifactPermissions = artifactPermissionsQuery.data?.permissions ?? []
  const totalArtifactPermissions = typeof artifactPermissionsQuery.data?.total === 'number'
    ? artifactPermissionsQuery.data.total
    : artifactPermissions.length

  const artifactGroupPermissions = artifactGroupPermissionsQuery.data?.permissions ?? []
  const totalArtifactGroupPermissions = typeof artifactGroupPermissionsQuery.data?.total === 'number'
    ? artifactGroupPermissionsQuery.data.total
    : artifactGroupPermissions.length

  const rbacPermissionsTableConfig: RbacPermissionsTableConfig = (() => {
    if (rbacPermissionsResourceKey === 'clusters' && rbacPermissionsPrincipalType === 'user') {
      const rows = rbacPermissionsClustersUserQuery.data?.permissions ?? []
      const total = typeof rbacPermissionsClustersUserQuery.data?.total === 'number'
        ? rbacPermissionsClustersUserQuery.data.total
        : rows.length
      return {
        columns: clusterColumns,
        rows,
        total,
        loading: rbacPermissionsClustersUserQuery.isLoading,
        fetching: rbacPermissionsClustersUserQuery.isFetching,
        error: rbacPermissionsClustersUserQuery.error,
        rowKey: (row) => `${row.user?.id}:${row.cluster?.id}`,
        refetch: () => { rbacPermissionsClustersUserQuery.refetch() },
      }
    }

    if (rbacPermissionsResourceKey === 'clusters' && rbacPermissionsPrincipalType === 'role') {
      const rows = rbacPermissionsClustersRoleQuery.data?.permissions ?? []
      const total = typeof rbacPermissionsClustersRoleQuery.data?.total === 'number'
        ? rbacPermissionsClustersRoleQuery.data.total
        : rows.length
      return {
        columns: clusterGroupColumns,
        rows,
        total,
        loading: rbacPermissionsClustersRoleQuery.isLoading,
        fetching: rbacPermissionsClustersRoleQuery.isFetching,
        error: rbacPermissionsClustersRoleQuery.error,
        rowKey: (row) => `${row.group?.id}:${row.cluster?.id}`,
        refetch: () => { rbacPermissionsClustersRoleQuery.refetch() },
      }
    }

    if (rbacPermissionsResourceKey === 'databases' && rbacPermissionsPrincipalType === 'user') {
      const rows = rbacPermissionsDatabasesUserQuery.data?.permissions ?? []
      const total = typeof rbacPermissionsDatabasesUserQuery.data?.total === 'number'
        ? rbacPermissionsDatabasesUserQuery.data.total
        : rows.length
      return {
        columns: databaseColumns,
        rows,
        total,
        loading: rbacPermissionsDatabasesUserQuery.isLoading,
        fetching: rbacPermissionsDatabasesUserQuery.isFetching,
        error: rbacPermissionsDatabasesUserQuery.error,
        rowKey: (row) => `${row.user?.id}:${row.database?.id}`,
        refetch: () => { rbacPermissionsDatabasesUserQuery.refetch() },
      }
    }

    if (rbacPermissionsResourceKey === 'databases' && rbacPermissionsPrincipalType === 'role') {
      const rows = rbacPermissionsDatabasesRoleQuery.data?.permissions ?? []
      const total = typeof rbacPermissionsDatabasesRoleQuery.data?.total === 'number'
        ? rbacPermissionsDatabasesRoleQuery.data.total
        : rows.length
      return {
        columns: databaseGroupColumns,
        rows,
        total,
        loading: rbacPermissionsDatabasesRoleQuery.isLoading,
        fetching: rbacPermissionsDatabasesRoleQuery.isFetching,
        error: rbacPermissionsDatabasesRoleQuery.error,
        rowKey: (row) => `${row.group?.id}:${row.database?.id}`,
        refetch: () => { rbacPermissionsDatabasesRoleQuery.refetch() },
      }
    }

    if (rbacPermissionsResourceKey === 'operation-templates' && rbacPermissionsPrincipalType === 'user') {
      const rows = rbacPermissionsOperationTemplatesUserQuery.data?.permissions ?? []
      const total = typeof rbacPermissionsOperationTemplatesUserQuery.data?.total === 'number'
        ? rbacPermissionsOperationTemplatesUserQuery.data.total
        : rows.length
      return {
        columns: operationTemplateUserColumns,
        rows,
        total,
        loading: rbacPermissionsOperationTemplatesUserQuery.isLoading,
        fetching: rbacPermissionsOperationTemplatesUserQuery.isFetching,
        error: rbacPermissionsOperationTemplatesUserQuery.error,
        rowKey: (row) => `${row.user?.id}:${row.template?.id}`,
        refetch: () => { rbacPermissionsOperationTemplatesUserQuery.refetch() },
      }
    }

    if (rbacPermissionsResourceKey === 'operation-templates' && rbacPermissionsPrincipalType === 'role') {
      const rows = rbacPermissionsOperationTemplatesRoleQuery.data?.permissions ?? []
      const total = typeof rbacPermissionsOperationTemplatesRoleQuery.data?.total === 'number'
        ? rbacPermissionsOperationTemplatesRoleQuery.data.total
        : rows.length
      return {
        columns: operationTemplateGroupColumns,
        rows,
        total,
        loading: rbacPermissionsOperationTemplatesRoleQuery.isLoading,
        fetching: rbacPermissionsOperationTemplatesRoleQuery.isFetching,
        error: rbacPermissionsOperationTemplatesRoleQuery.error,
        rowKey: (row) => `${row.group?.id}:${row.template?.id}`,
        refetch: () => { rbacPermissionsOperationTemplatesRoleQuery.refetch() },
      }
    }

    if (rbacPermissionsResourceKey === 'workflow-templates' && rbacPermissionsPrincipalType === 'user') {
      const rows = rbacPermissionsWorkflowTemplatesUserQuery.data?.permissions ?? []
      const total = typeof rbacPermissionsWorkflowTemplatesUserQuery.data?.total === 'number'
        ? rbacPermissionsWorkflowTemplatesUserQuery.data.total
        : rows.length
      return {
        columns: workflowTemplateUserColumns,
        rows,
        total,
        loading: rbacPermissionsWorkflowTemplatesUserQuery.isLoading,
        fetching: rbacPermissionsWorkflowTemplatesUserQuery.isFetching,
        error: rbacPermissionsWorkflowTemplatesUserQuery.error,
        rowKey: (row) => `${row.user?.id}:${row.template?.id}`,
        refetch: () => { rbacPermissionsWorkflowTemplatesUserQuery.refetch() },
      }
    }

    if (rbacPermissionsResourceKey === 'workflow-templates' && rbacPermissionsPrincipalType === 'role') {
      const rows = rbacPermissionsWorkflowTemplatesRoleQuery.data?.permissions ?? []
      const total = typeof rbacPermissionsWorkflowTemplatesRoleQuery.data?.total === 'number'
        ? rbacPermissionsWorkflowTemplatesRoleQuery.data.total
        : rows.length
      return {
        columns: workflowTemplateGroupColumns,
        rows,
        total,
        loading: rbacPermissionsWorkflowTemplatesRoleQuery.isLoading,
        fetching: rbacPermissionsWorkflowTemplatesRoleQuery.isFetching,
        error: rbacPermissionsWorkflowTemplatesRoleQuery.error,
        rowKey: (row) => `${row.group?.id}:${row.template?.id}`,
        refetch: () => { rbacPermissionsWorkflowTemplatesRoleQuery.refetch() },
      }
    }

    if (rbacPermissionsResourceKey === 'artifacts' && rbacPermissionsPrincipalType === 'user') {
      const rows = rbacPermissionsArtifactsUserQuery.data?.permissions ?? []
      const total = typeof rbacPermissionsArtifactsUserQuery.data?.total === 'number'
        ? rbacPermissionsArtifactsUserQuery.data.total
        : rows.length
      return {
        columns: artifactUserColumns,
        rows,
        total,
        loading: rbacPermissionsArtifactsUserQuery.isLoading,
        fetching: rbacPermissionsArtifactsUserQuery.isFetching,
        error: rbacPermissionsArtifactsUserQuery.error,
        rowKey: (row) => `${row.user?.id}:${row.artifact?.id}`,
        refetch: () => { rbacPermissionsArtifactsUserQuery.refetch() },
      }
    }

    const rows = rbacPermissionsArtifactsRoleQuery.data?.permissions ?? []
    const total = typeof rbacPermissionsArtifactsRoleQuery.data?.total === 'number'
      ? rbacPermissionsArtifactsRoleQuery.data.total
      : rows.length
    return {
      columns: artifactGroupColumns,
      rows,
      total,
      loading: rbacPermissionsArtifactsRoleQuery.isLoading,
      fetching: rbacPermissionsArtifactsRoleQuery.isFetching,
      error: rbacPermissionsArtifactsRoleQuery.error,
      rowKey: (row) => `${row.group?.id}:${row.artifact?.id}`,
      refetch: () => { rbacPermissionsArtifactsRoleQuery.refetch() },
    }
  })()

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
        items={(() => {
          const items = [
          {
            key: 'roles',
            label: <span data-testid="rbac-tab-roles">Роли</span>,
            children: (
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
              </Space>
            ),
          },
          {
            key: 'permissions',
            label: <span data-testid="rbac-tab-permissions">Доступ к объектам</span>,
            children: (
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

	                        if (nextKey === 'clusters') setClustersRefSearch('')
	                        if (nextKey === 'databases') setDatabasesRefSearch('')
	                        if (nextKey === 'operation-templates') setOperationTemplatesRefSearch('')
	                        if (nextKey === 'workflow-templates') setWorkflowTemplatesRefSearch('')
	                        if (nextKey === 'artifacts') setArtifactsRefSearch('')
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
                            select={rbacPermissionsResourceRef}
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
                        searchValue={rbacPermissionsResourceSearchValue}
                        onSearchChange={setRbacPermissionsResourceSearchValue}
                        options={rbacPermissionsResourceBrowserOptions}
                        selectedValue={rbacPermissionsList.resource_id}
                        onSelect={(id) => {
                          setRbacPermissionsList((prev) => ({ ...prev, resource_id: id, page: 1 }))
                          rbacPermissionsGrantForm.setFieldValue('resource_id', id)
                        }}
                        loading={rbacPermissionsResourceRef.loading}
                        loadingText="Загрузка…"
                        onScroll={(event) => rbacPermissionsResourceRef.onPopupScroll?.(event)}
                        clearLabel="Снять выбор"
                        clearDisabled={!rbacPermissionsList.resource_id}
                        onClear={() => {
                          setRbacPermissionsList((prev) => ({ ...prev, resource_id: undefined, page: 1 }))
                          rbacPermissionsGrantForm.setFieldValue('resource_id', undefined)
                        }}
                      />
                    )}

                    <PermissionsTable
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
                            <Text strong>Ресурс:</Text> {rbacPermissionsSelectedResourceLabel}
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
                            onClick={() => rbacPermissionsTableConfig.refetch()}
                            loading={rbacPermissionsTableConfig.fetching}
                          >
                            Обновить
                          </Button>
                        </>
                      )}
                      columns={rbacPermissionsTableConfig.columns}
                      rows={rbacPermissionsTableConfig.rows}
                      loading={rbacPermissionsTableConfig.loading}
                      rowKey={rbacPermissionsTableConfig.rowKey}
                      total={rbacPermissionsTableConfig.total}
                      page={rbacPermissionsList.page}
                      pageSize={rbacPermissionsList.pageSize}
                      onPaginationChange={(page, pageSize) => setRbacPermissionsList((prev) => ({ ...prev, page, pageSize }))}
                      error={rbacPermissionsTableConfig.error}
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
                    i18n={{
                      title: 'Массовые назначения (кластеры)',
                      tabGrant: 'Выдать массово',
                      tabRevoke: 'Отозвать массово',
                      confirmGrantTitle: 'Подтвердить массовую выдачу (кластеры)',
                      confirmRevokeTitle: 'Подтвердить массовый отзыв (кластеры)',
                      applyText: 'Применить',
                      cancelText: 'Отмена',
                      roleLabel: 'Группа',
                      levelLabel: 'Уровень',
                      notesLabel: 'Комментарий',
                      countLabel: 'Количество',
                      exampleLabel: 'Пример',
                      rolePlaceholder: 'Группа',
                      notesPlaceholder: 'Комментарий (опционально)',
                      reasonPlaceholder: 'Причина (обязательно)',
                      idsPlaceholder: 'UUID кластеров (по одному в строке)',
                      grantButton: 'Выдать массово',
                      revokeButton: 'Отозвать массово',
                      idsRequiredMessage: 'Укажите список кластеров',
                      roleRequiredMessage: 'Выберите группу',
                      reasonRequiredMessage: 'Укажите причину',
                      grantSuccessMessage: (r) => `Массовая выдача: создано=${r.created}, обновлено=${r.updated}, пропущено=${r.skipped}`,
                      revokeSuccessMessage: (r) => `Массовый отзыв: удалено=${r.deleted}, пропущено=${r.skipped}`,
                      grantFailedMessage: 'Не удалось выполнить массовую выдачу',
                      revokeFailedMessage: 'Не удалось выполнить массовый отзыв',
                    }}
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
                    i18n={{
                      title: 'Массовые назначения (базы)',
                      tabGrant: 'Выдать массово',
                      tabRevoke: 'Отозвать массово',
                      confirmGrantTitle: 'Подтвердить массовую выдачу (базы)',
                      confirmRevokeTitle: 'Подтвердить массовый отзыв (базы)',
                      applyText: 'Применить',
                      cancelText: 'Отмена',
                      roleLabel: 'Группа',
                      levelLabel: 'Уровень',
                      notesLabel: 'Комментарий',
                      countLabel: 'Количество',
                      exampleLabel: 'Пример',
                      rolePlaceholder: 'Группа',
                      notesPlaceholder: 'Комментарий (опционально)',
                      reasonPlaceholder: 'Причина (обязательно)',
                      idsPlaceholder: 'ID баз (по одному в строке)',
                      grantButton: 'Выдать массово',
                      revokeButton: 'Отозвать массово',
                      idsRequiredMessage: 'Укажите список баз',
                      roleRequiredMessage: 'Выберите группу',
                      reasonRequiredMessage: 'Укажите причину',
                      grantSuccessMessage: (r) => `Массовая выдача: создано=${r.created}, обновлено=${r.updated}, пропущено=${r.skipped}`,
                      revokeSuccessMessage: (r) => `Массовый отзыв: удалено=${r.deleted}, пропущено=${r.skipped}`,
                      grantFailedMessage: 'Не удалось выполнить массовую выдачу',
                      revokeFailedMessage: 'Не удалось выполнить массовый отзыв',
                    }}
                  />
                )}

                {rbacPermissionsViewMode === 'principal' && (
                  <PermissionsTable
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
                          select={rbacPermissionsResourceRef}
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
                          onClick={() => rbacPermissionsTableConfig.refetch()}
                          loading={rbacPermissionsTableConfig.fetching}
                        >
                          Обновить
                        </Button>
                      </>
                    )}
                    columns={rbacPermissionsTableConfig.columns}
                    rows={rbacPermissionsTableConfig.rows}
                    loading={rbacPermissionsTableConfig.loading}
                    rowKey={rbacPermissionsTableConfig.rowKey}
                    total={rbacPermissionsTableConfig.total}
                    page={rbacPermissionsList.page}
                    pageSize={rbacPermissionsList.pageSize}
                    onPaginationChange={(page, pageSize) => setRbacPermissionsList((prev) => ({ ...prev, page, pageSize }))}
                    error={rbacPermissionsTableConfig.error}
                    errorMessage="Не удалось загрузить назначения"
                  />
                )}
              </Space>
            ),
          },
          {
            key: 'user-roles',
            label: <span data-testid="rbac-tab-user-roles">Роли пользователей</span>,
            children: (
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
            ),
          },
          {
            key: 'effective-access',
            label: <span data-testid="rbac-tab-effective-access">Эффективный доступ</span>,
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Эффективный доступ" size="small">
                  <Space wrap align="start">
                    <Select
                      style={{ width: 260 }}
                      placeholder="Пользователь"
                      allowClear
                      showSearch
                      filterOption={false}
                      onSearch={setUserSearch}
                      value={selectedEffectiveUserId}
                      onChange={(value) => {
                        setSelectedEffectiveUserId(value)
                        setEffectiveDbPage(1)
                      }}
                      options={userOptions}
                      loading={usersQuery.isFetching}
                    />

                    <Select
                      style={{ width: 260 }}
                      value={effectiveResourceKey}
                      options={[
                        { label: 'Кластеры', value: 'clusters' },
                        { label: 'Базы', value: 'databases' },
                        { label: 'Шаблоны операций', value: 'operation-templates' },
                        { label: 'Шаблоны рабочих процессов', value: 'workflow-templates' },
                        { label: 'Артефакты', value: 'artifacts' },
                      ]}
                      onChange={(value) => setEffectiveResourceKey(value as RbacPermissionsResourceKey)}
                    />

	                    <RbacResourcePicker
	                      resourceKey={effectiveResourceKey}
	                      clusters={clusters}
	                      allowClear
	                      value={effectiveResourceId}
                      onChange={setEffectiveResourceId}
	                      placeholder={effectiveResourcePlaceholder}
	                      width={360}
	                      databaseLabelById={databasesLabelById.current}
	                      onDatabasesLoaded={handleDatabasesLoaded}
	                      select={effectiveResourceRef}
                        clusterDatabasePickerI18n={clusterDatabasePickerI18n}
	                    />

                    <Button
                      data-testid="rbac-effective-access-refresh"
                      onClick={() => effectiveAccessQuery.refetch()}
                      loading={effectiveAccessQuery.isFetching}
                      disabled={!selectedEffectiveUserId}
                    >
                      Обновить
                    </Button>
                  </Space>

                  {!selectedEffectiveUserId && (
                    <Alert
                      style={{ marginTop: 12 }}
                      type="info"
                          message="Выберите пользователя для просмотра"
                          description={(
                            <Space direction="vertical" size={4}>
                              <Text>Выберите пользователя и тип ресурса. Опционально укажите конкретный ресурс для фильтра.</Text>
                              <Text type="secondary">Раскрытие строки показывает источники (прямое/группа/через кластер/...)</Text>
                            </Space>
                          )}
                        />
                  )}

                  {effectiveAccessQuery.error && selectedEffectiveUserId && (
                    <Alert
                      style={{ marginTop: 12 }}
                      type="warning"
                      message="Не удалось загрузить эффективный доступ"
                    />
                  )}
                </Card>

                {selectedEffectiveUserId && (
                  <>
                    {effectiveResourceKey === 'clusters' && (
                      <Card title="Кластеры" size="small">
                        <Table
                          size="small"
                          rowKey={(row) => row.cluster.id}
                          columns={effectiveClustersColumns}
                          dataSource={(effectiveAccessQuery.data?.clusters ?? []).filter((row) => (
                            !effectiveResourceId || row.cluster.id === effectiveResourceId
                          ))}
                          loading={effectiveAccessQuery.isFetching}
                          expandable={{
                            rowExpandable: (row) => (row.sources ?? []).length > 0,
                            expandedRowRender: (row) => (
                              <Table
                                size="small"
                                columns={effectiveClusterSourcesColumns}
                                dataSource={row.sources ?? []}
                                rowKey={(_, index) => String(index)}
                                pagination={false}
                              />
                            ),
                          }}
                          pagination={{ pageSize: 50 }}
                        />
                      </Card>
                    )}

                    {effectiveResourceKey === 'databases' && (
                      <Card title="Базы" size="small">
                        <Table
                          size="small"
                          rowKey={(row) => row.database.id}
                          columns={effectiveDatabasesColumns}
                          dataSource={(effectiveAccessQuery.data?.databases ?? []).filter((row) => (
                            !effectiveResourceId || row.database.id === effectiveResourceId
                          ))}
                          loading={effectiveAccessQuery.isFetching}
                          expandable={{
                            rowExpandable: (row) => (row.sources ?? []).length > 0,
                            expandedRowRender: (row) => (
                              <Table
                                size="small"
                                columns={effectiveDatabaseSourcesColumns}
                                dataSource={row.sources ?? []}
                                rowKey={(_, index) => String(index)}
                                pagination={false}
                              />
                            ),
                          }}
                          pagination={effectiveDbPaginationEnabled ? {
                            current: effectiveDbPage,
                            pageSize: effectiveDbPageSize,
                            total: typeof effectiveAccessQuery.data?.databases_total === 'number'
                              ? effectiveAccessQuery.data.databases_total
                              : (effectiveAccessQuery.data?.databases ?? []).length,
                            showSizeChanger: true,
                            onChange: (page, pageSize) => {
                              setEffectiveDbPage(page)
                              setEffectiveDbPageSize(pageSize)
                            },
                          } : false}
                        />
                      </Card>
                    )}

                    {effectiveResourceKey === 'operation-templates' && (
                      <Card title="Шаблоны операций" size="small">
                        <Table
                          size="small"
                          rowKey={(row) => row.template.id}
                          columns={effectiveOperationTemplatesColumns}
                          dataSource={(effectiveAccessQuery.data?.operation_templates ?? []).filter((row) => (
                            !effectiveResourceId || row.template.id === effectiveResourceId
                          ))}
                          loading={effectiveAccessQuery.isFetching}
                          expandable={{
                            rowExpandable: (row) => (row.sources ?? []).length > 0,
                            expandedRowRender: (row) => (
                              <Table
                                size="small"
                                columns={effectiveOperationTemplateSourcesColumns}
                                dataSource={row.sources ?? []}
                                rowKey={(_, index) => String(index)}
                                pagination={false}
                              />
                            ),
                          }}
                          pagination={{ pageSize: 50 }}
                        />
                      </Card>
                    )}

                    {effectiveResourceKey === 'workflow-templates' && (
                      <Card title="Шаблоны рабочих процессов" size="small">
                        <Table
                          size="small"
                          rowKey={(row) => row.template.id}
                          columns={effectiveWorkflowTemplatesColumns}
                          dataSource={(effectiveAccessQuery.data?.workflow_templates ?? []).filter((row) => (
                            !effectiveResourceId || row.template.id === effectiveResourceId
                          ))}
                          loading={effectiveAccessQuery.isFetching}
                          expandable={{
                            rowExpandable: (row) => (row.sources ?? []).length > 0,
                            expandedRowRender: (row) => (
                              <Table
                                size="small"
                                columns={effectiveWorkflowTemplateSourcesColumns}
                                dataSource={row.sources ?? []}
                                rowKey={(_, index) => String(index)}
                                pagination={false}
                              />
                            ),
                          }}
                          pagination={{ pageSize: 50 }}
                        />
                      </Card>
                    )}

                    {effectiveResourceKey === 'artifacts' && (
                      <Card title="Артефакты" size="small">
                        <Table
                          size="small"
                          rowKey={(row) => row.artifact.id}
                          columns={effectiveArtifactsColumns}
                          dataSource={(effectiveAccessQuery.data?.artifacts ?? []).filter((row) => (
                            !effectiveResourceId || row.artifact.id === effectiveResourceId
                          ))}
                          loading={effectiveAccessQuery.isFetching}
                          expandable={{
                            rowExpandable: (row) => (row.sources ?? []).length > 0,
                            expandedRowRender: (row) => (
                              <Table
                                size="small"
                                columns={effectiveArtifactSourcesColumns}
                                dataSource={row.sources ?? []}
                                rowKey={(_, index) => String(index)}
                                pagination={false}
                              />
                            ),
                          }}
                          pagination={{ pageSize: 50 }}
                        />
                      </Card>
                    )}
                  </>
                )}
              </Space>
            ),
          },
          ...(rbacLegacyTabsEnabled ? [
          {
            key: 'clusters',
            label: 'Cluster Permissions',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Grant Cluster Permission" size="small">
                  <Form
                    form={grantClusterForm}
                    layout="inline"
                    onFinish={(values) => grantCluster.mutate(values, { onSuccess: () => grantClusterForm.resetFields() })}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="user_id" rules={[{ required: true, message: 'user_id required' }]}>
                      <Select
                        id="rbac-cluster-user-id"
                        style={{ width: 220 }}
                        placeholder="User"
                        allowClear
                        showSearch
                        filterOption={false}
                        onSearch={setUserSearch}
                        options={userOptions}
                        loading={usersQuery.isFetching}
                      />
                    </Form.Item>
                    <Form.Item name="cluster_id" rules={[{ required: true, message: 'cluster_id required' }]}>
                      <Select
                        id="rbac-cluster-id"
                        style={{ width: 320 }}
                        placeholder="Cluster"
                        options={clusters.map((c) => ({ label: `${c.name} #${c.id}`, value: c.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select id="rbac-cluster-level" style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input id="rbac-cluster-notes" placeholder="Notes (optional)" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input id="rbac-cluster-reason" placeholder="Reason" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantCluster.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantCluster.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Не удалось выдать доступ" />
                  )}
                </Card>

                <Card title="Cluster Permissions" size="small">
                  {clusterPermissionsQuery.error && (
                    <Alert
                      type="warning"
                      message="Не удалось загрузить назначения"
                      style={{ marginBottom: 12 }}
                    />
                  )}

                  <TableToolkit
                    table={clusterTable}
                    data={clusterPermissions}
                    total={totalClusterPermissions}
                    loading={clusterPermissionsQuery.isLoading}
                    rowKey={(row) => `${row.user?.id}:${row.cluster?.id}`}
                    columns={clusterColumns}
                    searchPlaceholder="Search cluster permissions"
                    toolbarActions={(
                      <Button onClick={() => clusterPermissionsQuery.refetch()} loading={clusterPermissionsQuery.isFetching}>
                        Refresh
                      </Button>
                    )}
                  />
                </Card>

                <Card title="Grant Cluster Permission (Role)" size="small">
                  <Form
                    form={grantClusterGroupForm}
                    layout="inline"
                    onFinish={(values) => grantClusterGroup.mutate(values, { onSuccess: () => grantClusterGroupForm.resetFields() })}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                      <Select
                        style={{ width: 240 }}
                        placeholder="Role"
                        options={roleOptions}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="cluster_id" rules={[{ required: true, message: 'cluster required' }]}>
                      <Select
                        style={{ width: 320 }}
                        placeholder="Cluster"
                        options={clusters.map((c) => ({ label: `${c.name} #${c.id}`, value: c.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input placeholder="Notes (optional)" style={{ width: 200 }} />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input placeholder="Reason" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantClusterGroup.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantClusterGroup.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Не удалось выдать доступ" />
                  )}
                </Card>

                <RbacBulkClusterRolePermissions
                  roleOptions={roleOptions}
                  roleNameById={roleNameById}
                  levelOptions={LEVEL_OPTIONS}
                  bulkGrant={bulkGrantClusterGroup}
                  bulkRevoke={bulkRevokeClusterGroup}
                />

                <PermissionsTable
                  title="Cluster Permissions (Role)"
                  toolbar={(
                    <>
                      <Select
                        style={{ width: 240 }}
                        placeholder="Role"
                        allowClear
                        value={clusterGroupList.group_id}
                        onChange={(value) => setClusterGroupList((prev) => ({ ...prev, group_id: value ?? undefined, page: 1 }))}
                        options={roleOptions}
                        showSearch
                        optionFilterProp="label"
                      />
                      <Select
                        style={{ width: 320 }}
                        placeholder="Cluster"
                        allowClear
                        value={clusterGroupList.cluster_id}
                        onChange={(value) => setClusterGroupList((prev) => ({ ...prev, cluster_id: value ?? undefined, page: 1 }))}
                        options={clusters.map((c) => ({ label: `${c.name} #${c.id}`, value: c.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                      <Select
                        style={{ width: 140 }}
                        placeholder="Level"
                        allowClear
                        value={clusterGroupList.level}
                        onChange={(value) => setClusterGroupList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                        options={LEVEL_OPTIONS}
                      />
                      <Input
                        placeholder="Search"
                        style={{ width: 220 }}
                        value={clusterGroupList.search}
                        onChange={(e) => setClusterGroupList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                      />
                      <Button onClick={() => clusterGroupPermissionsQuery.refetch()} loading={clusterGroupPermissionsQuery.isFetching}>
                        Refresh
                      </Button>
                    </>
                  )}
                  columns={clusterGroupColumns}
                  rows={clusterGroupPermissions}
                  loading={clusterGroupPermissionsQuery.isLoading}
                  rowKey={(row) => `${row.group.id}:${row.cluster.id}`}
                  total={totalClusterGroupPermissions}
                  page={clusterGroupList.page}
                  pageSize={clusterGroupList.pageSize}
                  onPaginationChange={(page, pageSize) => setClusterGroupList((prev) => ({ ...prev, page, pageSize }))}
                  error={clusterGroupPermissionsQuery.error}
                  errorMessage="Не удалось загрузить назначения"
                />
              </Space>
            ),
          },
          {
            key: 'databases',
            label: 'Database Permissions',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Grant Database Permission" size="small">
                  <Form
                    form={grantDatabaseForm}
                    layout="inline"
                    onFinish={(values) => grantDatabase.mutate(values, { onSuccess: () => grantDatabaseForm.resetFields() })}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="user_id" rules={[{ required: true, message: 'user_id required' }]}>
                      <Select
                        id="rbac-database-user-id"
                        style={{ width: 220 }}
                        placeholder="User"
                        allowClear
                        showSearch
                        filterOption={false}
                        onSearch={setUserSearch}
                        options={userOptions}
                        loading={usersQuery.isFetching}
                      />
                    </Form.Item>
                    <Form.Item name="database_id" rules={[{ required: true, message: 'database_id required' }]}>
                      <Select
                        id="rbac-database-id"
                        style={{ width: 320 }}
                        placeholder="Database"
                        options={databases.map((db) => ({ label: `${db.name} #${db.id}`, value: db.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select id="rbac-database-level" style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input id="rbac-database-notes" placeholder="Notes (optional)" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input id="rbac-database-reason" placeholder="Reason" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantDatabase.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantDatabase.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Не удалось выдать доступ" />
                  )}
                </Card>

                <Card title="Database Permissions" size="small">
                  {databasePermissionsQuery.error && (
                    <Alert
                      type="warning"
                      message="Не удалось загрузить назначения"
                      style={{ marginBottom: 12 }}
                    />
                  )}

                  <TableToolkit
                    table={databaseTable}
                    data={databasePermissions}
                    total={totalDatabasePermissions}
                    loading={databasePermissionsQuery.isLoading}
                    rowKey={(row) => `${row.user?.id}:${row.database?.id}`}
                    columns={databaseColumns}
                    searchPlaceholder="Search database permissions"
                    toolbarActions={(
                      <Button onClick={() => databasePermissionsQuery.refetch()} loading={databasePermissionsQuery.isFetching}>
                        Refresh
                      </Button>
                    )}
                  />
                </Card>

                <Card title="Grant Database Permission (Role)" size="small">
                  <Form
                    form={grantDatabaseGroupForm}
                    layout="inline"
                    onFinish={(values) => grantDatabaseGroup.mutate(values, { onSuccess: () => grantDatabaseGroupForm.resetFields() })}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                      <Select
                        style={{ width: 240 }}
                        placeholder="Role"
                        options={roleOptions}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="database_id" rules={[{ required: true, message: 'database required' }]}>
                      <Select
                        style={{ width: 320 }}
                        placeholder="Database"
                        options={databases.map((db) => ({ label: `${db.name} #${db.id}`, value: db.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input placeholder="Notes (optional)" style={{ width: 200 }} />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input placeholder="Reason" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantDatabaseGroup.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantDatabaseGroup.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Не удалось выдать доступ" />
                  )}
                </Card>

                <RbacBulkDatabaseRolePermissions
                  roleOptions={roleOptions}
                  roleNameById={roleNameById}
                  levelOptions={LEVEL_OPTIONS}
                  bulkGrant={bulkGrantDatabaseGroup}
                  bulkRevoke={bulkRevokeDatabaseGroup}
                />

                <PermissionsTable
                  title="Database Permissions (Role)"
                  toolbar={(
                    <>
                      <Select
                        style={{ width: 240 }}
                        placeholder="Role"
                        allowClear
                        value={databaseGroupList.group_id}
                        onChange={(value) => setDatabaseGroupList((prev) => ({ ...prev, group_id: value ?? undefined, page: 1 }))}
                        options={roleOptions}
                        showSearch
                        optionFilterProp="label"
                      />
                      <Select
                        style={{ width: 320 }}
                        placeholder="Database"
                        allowClear
                        value={databaseGroupList.database_id}
                        onChange={(value) => setDatabaseGroupList((prev) => ({ ...prev, database_id: value ?? undefined, page: 1 }))}
                        options={databases.map((db) => ({ label: `${db.name} #${db.id}`, value: db.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                      <Select
                        style={{ width: 140 }}
                        placeholder="Level"
                        allowClear
                        value={databaseGroupList.level}
                        onChange={(value) => setDatabaseGroupList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                        options={LEVEL_OPTIONS}
                      />
                      <Input
                        placeholder="Search"
                        style={{ width: 220 }}
                        value={databaseGroupList.search}
                        onChange={(e) => setDatabaseGroupList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                      />
                      <Button onClick={() => databaseGroupPermissionsQuery.refetch()} loading={databaseGroupPermissionsQuery.isFetching}>
                        Refresh
                      </Button>
                    </>
                  )}
                  columns={databaseGroupColumns}
                  rows={databaseGroupPermissions}
                  loading={databaseGroupPermissionsQuery.isLoading}
                  rowKey={(row) => `${row.group.id}:${row.database.id}`}
                  total={totalDatabaseGroupPermissions}
                  page={databaseGroupList.page}
                  pageSize={databaseGroupList.pageSize}
                  onPaginationChange={(page, pageSize) => setDatabaseGroupList((prev) => ({ ...prev, page, pageSize }))}
                  error={databaseGroupPermissionsQuery.error}
                  errorMessage="Не удалось загрузить назначения"
                />
              </Space>
            ),
          },
          {
            key: 'operation-templates',
            label: 'Operation Templates',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Grant Operation Template Permission (User)" size="small">
                  <Form
                    form={grantOperationTemplateForm}
                    layout="inline"
                    onFinish={(values) => grantOperationTemplate.mutate(values, { onSuccess: () => grantOperationTemplateForm.resetFields() })}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="user_id" rules={[{ required: true, message: 'user required' }]}>
                      <Select
                        style={{ width: 220 }}
                        placeholder="User"
                        allowClear
                        showSearch
                        filterOption={false}
                        onSearch={setUserSearch}
                        options={userOptions}
                        loading={usersQuery.isFetching}
                      />
                    </Form.Item>
                    <Form.Item name="template_id" rules={[{ required: true, message: 'template required' }]}>
                      <Select
                        style={{ width: 320 }}
                        placeholder="Template"
                        options={operationTemplates.map((t) => ({ label: `${t.name} #${t.id}`, value: t.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input placeholder="Notes (optional)" style={{ width: 200 }} />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input placeholder="Reason" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantOperationTemplate.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantOperationTemplate.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Не удалось выдать доступ" />
                  )}
                </Card>

                <Card title="Operation Template Permissions (User)" size="small">
                  <Space wrap style={{ marginBottom: 12 }}>
                    <Select
                      style={{ width: 220 }}
                      placeholder="User"
                      allowClear
                      value={operationTemplateUserList.user_id}
                      onChange={(value) => setOperationTemplateUserList((prev) => ({ ...prev, user_id: value ?? undefined, page: 1 }))}
                      showSearch
                      filterOption={false}
                      onSearch={setUserSearch}
                      options={userOptions}
                      loading={usersQuery.isFetching}
                    />
                    <Select
                      style={{ width: 320 }}
                      placeholder="Template"
                      allowClear
                      value={operationTemplateUserList.template_id}
                      onChange={(value) => setOperationTemplateUserList((prev) => ({ ...prev, template_id: value ?? undefined, page: 1 }))}
                      options={operationTemplates.map((t) => ({ label: `${t.name} #${t.id}`, value: t.id }))}
                      showSearch
                      optionFilterProp="label"
                    />
                    <Select
                      style={{ width: 140 }}
                      placeholder="Level"
                      allowClear
                      value={operationTemplateUserList.level}
                      onChange={(value) => setOperationTemplateUserList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                      options={LEVEL_OPTIONS}
                    />
                    <Input
                      placeholder="Search"
                      style={{ width: 220 }}
                      value={operationTemplateUserList.search}
                      onChange={(e) => setOperationTemplateUserList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                    />
                    <Button
                      onClick={() => operationTemplatePermissionsQuery.refetch()}
                      loading={operationTemplatePermissionsQuery.isFetching}
                    >
                      Refresh
                    </Button>
                  </Space>
                  <Table
                    size="small"
                    columns={operationTemplateUserColumns}
                    dataSource={operationTemplatePermissions}
                    loading={operationTemplatePermissionsQuery.isLoading}
                    rowKey={(row) => `${row.user.id}:${row.template.id}`}
                    pagination={{
                      current: operationTemplateUserList.page,
                      pageSize: operationTemplateUserList.pageSize,
                      total: totalOperationTemplatePermissions,
                      showSizeChanger: true,
                      onChange: (page, pageSize) => setOperationTemplateUserList((prev) => ({ ...prev, page, pageSize })),
                    }}
                  />
                </Card>

                <Card title="Grant Operation Template Permission (Role)" size="small">
                  <Form
                    form={grantOperationTemplateGroupForm}
                    layout="inline"
                    onFinish={(values) => grantOperationTemplateGroup.mutate(values, { onSuccess: () => grantOperationTemplateGroupForm.resetFields() })}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                      <Select
                        style={{ width: 240 }}
                        placeholder="Role"
                        options={roleOptions}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="template_id" rules={[{ required: true, message: 'template required' }]}>
                      <Select
                        style={{ width: 320 }}
                        placeholder="Template"
                        options={operationTemplates.map((t) => ({ label: `${t.name} #${t.id}`, value: t.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input placeholder="Notes (optional)" style={{ width: 200 }} />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input placeholder="Reason" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantOperationTemplateGroup.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantOperationTemplateGroup.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Не удалось выдать доступ" />
                  )}
                </Card>

                <Card title="Operation Template Permissions (Role)" size="small">
                  <Space wrap style={{ marginBottom: 12 }}>
                    <Select
                      style={{ width: 240 }}
                      placeholder="Role"
                      allowClear
                      value={operationTemplateGroupList.group_id}
                      onChange={(value) => setOperationTemplateGroupList((prev) => ({ ...prev, group_id: value ?? undefined, page: 1 }))}
                      options={roleOptions}
                      showSearch
                      optionFilterProp="label"
                    />
                    <Select
                      style={{ width: 320 }}
                      placeholder="Template"
                      allowClear
                      value={operationTemplateGroupList.template_id}
                      onChange={(value) => setOperationTemplateGroupList((prev) => ({ ...prev, template_id: value ?? undefined, page: 1 }))}
                      options={operationTemplates.map((t) => ({ label: `${t.name} #${t.id}`, value: t.id }))}
                      showSearch
                      optionFilterProp="label"
                    />
                    <Select
                      style={{ width: 140 }}
                      placeholder="Level"
                      allowClear
                      value={operationTemplateGroupList.level}
                      onChange={(value) => setOperationTemplateGroupList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                      options={LEVEL_OPTIONS}
                    />
                    <Input
                      placeholder="Search"
                      style={{ width: 220 }}
                      value={operationTemplateGroupList.search}
                      onChange={(e) => setOperationTemplateGroupList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                    />
                    <Button
                      onClick={() => operationTemplateGroupPermissionsQuery.refetch()}
                      loading={operationTemplateGroupPermissionsQuery.isFetching}
                    >
                      Refresh
                    </Button>
                  </Space>
                  <Table
                    size="small"
                    columns={operationTemplateGroupColumns}
                    dataSource={operationTemplateGroupPermissions}
                    loading={operationTemplateGroupPermissionsQuery.isLoading}
                    rowKey={(row) => `${row.group.id}:${row.template.id}`}
                    pagination={{
                      current: operationTemplateGroupList.page,
                      pageSize: operationTemplateGroupList.pageSize,
                      total: totalOperationTemplateGroupPermissions,
                      showSizeChanger: true,
                      onChange: (page, pageSize) => setOperationTemplateGroupList((prev) => ({ ...prev, page, pageSize })),
                    }}
                  />
                </Card>
              </Space>
            ),
          },
          {
            key: 'workflow-templates',
            label: 'Workflow Templates',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Grant Workflow Template Permission (User)" size="small">
                  <Form
                    form={grantWorkflowTemplateForm}
                    layout="inline"
                    onFinish={(values) => grantWorkflowTemplate.mutate(values, { onSuccess: () => grantWorkflowTemplateForm.resetFields() })}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="user_id" rules={[{ required: true, message: 'user required' }]}>
                      <Select
                        style={{ width: 220 }}
                        placeholder="User"
                        allowClear
                        showSearch
                        filterOption={false}
                        onSearch={setUserSearch}
                        options={userOptions}
                        loading={usersQuery.isFetching}
                      />
                    </Form.Item>
                    <Form.Item name="template_id" rules={[{ required: true, message: 'template required' }]}>
                      <Select
                        style={{ width: 320 }}
                        placeholder="Workflow template"
                        options={workflowTemplates.map((t) => ({ label: `${t.name} #${t.id}`, value: t.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input placeholder="Notes (optional)" style={{ width: 200 }} />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input placeholder="Reason" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantWorkflowTemplate.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantWorkflowTemplate.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Не удалось выдать доступ" />
                  )}
                </Card>

                <Card title="Workflow Template Permissions (User)" size="small">
                  <Space wrap style={{ marginBottom: 12 }}>
                    <Select
                      style={{ width: 220 }}
                      placeholder="User"
                      allowClear
                      value={workflowTemplateUserList.user_id}
                      onChange={(value) => setWorkflowTemplateUserList((prev) => ({ ...prev, user_id: value ?? undefined, page: 1 }))}
                      showSearch
                      filterOption={false}
                      onSearch={setUserSearch}
                      options={userOptions}
                      loading={usersQuery.isFetching}
                    />
                    <Select
                      style={{ width: 320 }}
                      placeholder="Workflow template"
                      allowClear
                      value={workflowTemplateUserList.template_id}
                      onChange={(value) => setWorkflowTemplateUserList((prev) => ({ ...prev, template_id: value ?? undefined, page: 1 }))}
                      options={workflowTemplates.map((t) => ({ label: `${t.name} #${t.id}`, value: t.id }))}
                      showSearch
                      optionFilterProp="label"
                    />
                    <Select
                      style={{ width: 140 }}
                      placeholder="Level"
                      allowClear
                      value={workflowTemplateUserList.level}
                      onChange={(value) => setWorkflowTemplateUserList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                      options={LEVEL_OPTIONS}
                    />
                    <Input
                      placeholder="Search"
                      style={{ width: 220 }}
                      value={workflowTemplateUserList.search}
                      onChange={(e) => setWorkflowTemplateUserList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                    />
                    <Button
                      onClick={() => workflowTemplatePermissionsQuery.refetch()}
                      loading={workflowTemplatePermissionsQuery.isFetching}
                    >
                      Refresh
                    </Button>
                  </Space>
                  <Table
                    size="small"
                    columns={workflowTemplateUserColumns}
                    dataSource={workflowTemplatePermissions}
                    loading={workflowTemplatePermissionsQuery.isLoading}
                    rowKey={(row) => `${row.user.id}:${row.template.id}`}
                    pagination={{
                      current: workflowTemplateUserList.page,
                      pageSize: workflowTemplateUserList.pageSize,
                      total: totalWorkflowTemplatePermissions,
                      showSizeChanger: true,
                      onChange: (page, pageSize) => setWorkflowTemplateUserList((prev) => ({ ...prev, page, pageSize })),
                    }}
                  />
                </Card>

                <Card title="Grant Workflow Template Permission (Role)" size="small">
                  <Form
                    form={grantWorkflowTemplateGroupForm}
                    layout="inline"
                    onFinish={(values) => grantWorkflowTemplateGroup.mutate(values, { onSuccess: () => grantWorkflowTemplateGroupForm.resetFields() })}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                      <Select
                        style={{ width: 240 }}
                        placeholder="Role"
                        options={roleOptions}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="template_id" rules={[{ required: true, message: 'template required' }]}>
                      <Select
                        style={{ width: 320 }}
                        placeholder="Workflow template"
                        options={workflowTemplates.map((t) => ({ label: `${t.name} #${t.id}`, value: t.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input placeholder="Notes (optional)" style={{ width: 200 }} />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input placeholder="Reason" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantWorkflowTemplateGroup.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantWorkflowTemplateGroup.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Не удалось выдать доступ" />
                  )}
                </Card>

                <Card title="Workflow Template Permissions (Role)" size="small">
                  <Space wrap style={{ marginBottom: 12 }}>
                    <Select
                      style={{ width: 240 }}
                      placeholder="Role"
                      allowClear
                      value={workflowTemplateGroupList.group_id}
                      onChange={(value) => setWorkflowTemplateGroupList((prev) => ({ ...prev, group_id: value ?? undefined, page: 1 }))}
                      options={roleOptions}
                      showSearch
                      optionFilterProp="label"
                    />
                    <Select
                      style={{ width: 320 }}
                      placeholder="Workflow template"
                      allowClear
                      value={workflowTemplateGroupList.template_id}
                      onChange={(value) => setWorkflowTemplateGroupList((prev) => ({ ...prev, template_id: value ?? undefined, page: 1 }))}
                      options={workflowTemplates.map((t) => ({ label: `${t.name} #${t.id}`, value: t.id }))}
                      showSearch
                      optionFilterProp="label"
                    />
                    <Select
                      style={{ width: 140 }}
                      placeholder="Level"
                      allowClear
                      value={workflowTemplateGroupList.level}
                      onChange={(value) => setWorkflowTemplateGroupList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                      options={LEVEL_OPTIONS}
                    />
                    <Input
                      placeholder="Search"
                      style={{ width: 220 }}
                      value={workflowTemplateGroupList.search}
                      onChange={(e) => setWorkflowTemplateGroupList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                    />
                    <Button
                      onClick={() => workflowTemplateGroupPermissionsQuery.refetch()}
                      loading={workflowTemplateGroupPermissionsQuery.isFetching}
                    >
                      Refresh
                    </Button>
                  </Space>
                  <Table
                    size="small"
                    columns={workflowTemplateGroupColumns}
                    dataSource={workflowTemplateGroupPermissions}
                    loading={workflowTemplateGroupPermissionsQuery.isLoading}
                    rowKey={(row) => `${row.group.id}:${row.template.id}`}
                    pagination={{
                      current: workflowTemplateGroupList.page,
                      pageSize: workflowTemplateGroupList.pageSize,
                      total: totalWorkflowTemplateGroupPermissions,
                      showSizeChanger: true,
                      onChange: (page, pageSize) => setWorkflowTemplateGroupList((prev) => ({ ...prev, page, pageSize })),
                    }}
                  />
                </Card>
              </Space>
            ),
          },
          {
            key: 'artifacts',
            label: 'Artifacts',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Grant Artifact Permission (User)" size="small">
                  <Form
                    form={grantArtifactForm}
                    layout="inline"
                    onFinish={(values) => grantArtifact.mutate(values, { onSuccess: () => grantArtifactForm.resetFields() })}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="user_id" rules={[{ required: true, message: 'user required' }]}>
                      <Select
                        style={{ width: 220 }}
                        placeholder="User"
                        allowClear
                        showSearch
                        filterOption={false}
                        onSearch={setUserSearch}
                        options={userOptions}
                        loading={usersQuery.isFetching}
                      />
                    </Form.Item>
                    <Form.Item name="artifact_id" rules={[{ required: true, message: 'artifact required' }]}>
                      <Select
                        style={{ width: 320 }}
                        placeholder="Artifact"
                        options={artifacts.map((a) => ({ label: `${a.name} #${a.id}`, value: a.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input placeholder="Notes (optional)" style={{ width: 200 }} />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input placeholder="Reason" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantArtifact.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantArtifact.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Не удалось выдать доступ" />
                  )}
                </Card>

                <Card title="Artifact Permissions (User)" size="small">
                  <Space wrap style={{ marginBottom: 12 }}>
                    <Select
                      style={{ width: 220 }}
                      placeholder="User"
                      allowClear
                      value={artifactUserList.user_id}
                      onChange={(value) => setArtifactUserList((prev) => ({ ...prev, user_id: value ?? undefined, page: 1 }))}
                      showSearch
                      filterOption={false}
                      onSearch={setUserSearch}
                      options={userOptions}
                      loading={usersQuery.isFetching}
                    />
                    <Select
                      style={{ width: 320 }}
                      placeholder="Artifact"
                      allowClear
                      value={artifactUserList.artifact_id}
                      onChange={(value) => setArtifactUserList((prev) => ({ ...prev, artifact_id: value ?? undefined, page: 1 }))}
                      options={artifacts.map((a) => ({ label: `${a.name} #${a.id}`, value: a.id }))}
                      showSearch
                      optionFilterProp="label"
                    />
                    <Select
                      style={{ width: 140 }}
                      placeholder="Level"
                      allowClear
                      value={artifactUserList.level}
                      onChange={(value) => setArtifactUserList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                      options={LEVEL_OPTIONS}
                    />
                    <Input
                      placeholder="Search"
                      style={{ width: 220 }}
                      value={artifactUserList.search}
                      onChange={(e) => setArtifactUserList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                    />
                    <Button
                      onClick={() => artifactPermissionsQuery.refetch()}
                      loading={artifactPermissionsQuery.isFetching}
                    >
                      Refresh
                    </Button>
                  </Space>
                  <Table
                    size="small"
                    columns={artifactUserColumns}
                    dataSource={artifactPermissions}
                    loading={artifactPermissionsQuery.isLoading}
                    rowKey={(row) => `${row.user.id}:${row.artifact.id}`}
                    pagination={{
                      current: artifactUserList.page,
                      pageSize: artifactUserList.pageSize,
                      total: totalArtifactPermissions,
                      showSizeChanger: true,
                      onChange: (page, pageSize) => setArtifactUserList((prev) => ({ ...prev, page, pageSize })),
                    }}
                  />
                </Card>

                <Card title="Grant Artifact Permission (Role)" size="small">
                  <Form
                    form={grantArtifactGroupForm}
                    layout="inline"
                    onFinish={(values) => grantArtifactGroup.mutate(values, { onSuccess: () => grantArtifactGroupForm.resetFields() })}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                      <Select
                        style={{ width: 240 }}
                        placeholder="Role"
                        options={roleOptions}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="artifact_id" rules={[{ required: true, message: 'artifact required' }]}>
                      <Select
                        style={{ width: 320 }}
                        placeholder="Artifact"
                        options={artifacts.map((a) => ({ label: `${a.name} #${a.id}`, value: a.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input placeholder="Notes (optional)" style={{ width: 200 }} />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input placeholder="Reason" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantArtifactGroup.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantArtifactGroup.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Не удалось выдать доступ" />
                  )}
                </Card>

                <Card title="Artifact Permissions (Role)" size="small">
                  <Space wrap style={{ marginBottom: 12 }}>
                    <Select
                      style={{ width: 240 }}
                      placeholder="Role"
                      allowClear
                      value={artifactGroupList.group_id}
                      onChange={(value) => setArtifactGroupList((prev) => ({ ...prev, group_id: value ?? undefined, page: 1 }))}
                      options={roleOptions}
                      showSearch
                      optionFilterProp="label"
                    />
                    <Select
                      style={{ width: 320 }}
                      placeholder="Artifact"
                      allowClear
                      value={artifactGroupList.artifact_id}
                      onChange={(value) => setArtifactGroupList((prev) => ({ ...prev, artifact_id: value ?? undefined, page: 1 }))}
                      options={artifacts.map((a) => ({ label: `${a.name} #${a.id}`, value: a.id }))}
                      showSearch
                      optionFilterProp="label"
                    />
                    <Select
                      style={{ width: 140 }}
                      placeholder="Level"
                      allowClear
                      value={artifactGroupList.level}
                      onChange={(value) => setArtifactGroupList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                      options={LEVEL_OPTIONS}
                    />
                    <Input
                      placeholder="Search"
                      style={{ width: 220 }}
                      value={artifactGroupList.search}
                      onChange={(e) => setArtifactGroupList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                    />
                    <Button
                      onClick={() => artifactGroupPermissionsQuery.refetch()}
                      loading={artifactGroupPermissionsQuery.isFetching}
                    >
                      Refresh
                    </Button>
                  </Space>
                  <Table
                    size="small"
                    columns={artifactGroupColumns}
                    dataSource={artifactGroupPermissions}
                    loading={artifactGroupPermissionsQuery.isLoading}
                    rowKey={(row) => `${row.group.id}:${row.artifact.id}`}
                    pagination={{
                      current: artifactGroupList.page,
                      pageSize: artifactGroupList.pageSize,
                      total: totalArtifactGroupPermissions,
                      showSizeChanger: true,
                      onChange: (page, pageSize) => setArtifactGroupList((prev) => ({ ...prev, page, pageSize })),
                    }}
                  />
                </Card>
              </Space>
            ),
          },
          ] : []),
          {
            key: 'audit',
            label: <span data-testid="rbac-tab-audit">Аудит</span>,
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <div data-testid="rbac-audit-panel">
                  <RbacAuditPanel
                    enabled={canManageRbac}
                    title="Аудит"
                    errorMessage="Не удалось загрузить журнал аудита"
                    undoLabel="Отменить"
                    undoModalTitle="Отменить изменение"
                    undoOkText="Отменить"
                    undoCancelText="Закрыть"
                    undoReasonPlaceholder="Причина (обязательно)"
                    undoReasonRequiredMessage="Укажите причину"
                    undoSuccessMessage="Изменение отменено"
                    undoFailedMessage="Не удалось отменить изменение"
                    undoNotSupportedMessage="Для этой записи откат не поддерживается"
                    i18n={{
                      searchPlaceholder: 'Поиск',
                      refreshText: 'Обновить',
                      viewText: 'Открыть',
                      detailsModalTitle: (id) => `Аудит #${id}`,
                      columnCreatedAt: 'Время',
                      columnActor: 'Оператор',
                      columnAction: 'Действие',
                      columnOutcome: 'Результат',
                      columnTarget: 'Цель',
                      columnReason: 'Причина',
                      columnDetails: 'Детали',
                      detailsAuditIdLabel: 'ID аудита:',
                      detailsActionLabel: 'Действие:',
                      detailsTargetLabel: 'Цель:',
                      formatUndoTitle: (cmd) => {
                        const meta = cmd.meta ?? {}
                        const id = (key: string) => {
                          const value = (meta as Record<string, unknown>)[key]
                          return value === undefined || value === null ? '?' : String(value)
                        }

                        switch (cmd.code) {
                          case 'delete_role':
                            return `Откат: удалить роль #${id('groupId')}`
                          case 'rename_role':
                            return `Откат: вернуть имя роли #${id('groupId')}`
                          case 'restore_user_roles':
                            return `Откат: восстановить роли пользователя #${id('userId')}`
                          case 'restore_role_capabilities':
                            return `Откат: восстановить права роли #${id('groupId')}`

                          case 'revoke_cluster_permission':
                            return `Откат: отозвать доступ пользователя #${id('userId')} к кластеру ${id('clusterId')}`
                          case 'restore_cluster_permission_level':
                            return `Откат: восстановить уровень доступа пользователя #${id('userId')} к кластеру ${id('clusterId')}`
                          case 'restore_cluster_permission':
                            return `Откат: восстановить доступ пользователя #${id('userId')} к кластеру ${id('clusterId')}`

                          case 'revoke_database_permission':
                            return `Откат: отозвать доступ пользователя #${id('userId')} к базе ${id('databaseId')}`
                          case 'restore_database_permission_level':
                            return `Откат: восстановить уровень доступа пользователя #${id('userId')} к базе ${id('databaseId')}`
                          case 'restore_database_permission':
                            return `Откат: восстановить доступ пользователя #${id('userId')} к базе ${id('databaseId')}`

                          case 'revoke_cluster_group_permission':
                            return `Откат: отозвать доступ группы #${id('groupId')} к кластеру ${id('clusterId')}`
                          case 'restore_cluster_group_permission_level':
                            return `Откат: восстановить уровень доступа группы #${id('groupId')} к кластеру ${id('clusterId')}`
                          case 'restore_cluster_group_permission':
                            return `Откат: восстановить доступ группы #${id('groupId')} к кластеру ${id('clusterId')}`

                          case 'revoke_database_group_permission':
                            return `Откат: отозвать доступ группы #${id('groupId')} к базе ${id('databaseId')}`
                          case 'restore_database_group_permission_level':
                            return `Откат: восстановить уровень доступа группы #${id('groupId')} к базе ${id('databaseId')}`
                          case 'restore_database_group_permission':
                            return `Откат: восстановить доступ группы #${id('groupId')} к базе ${id('databaseId')}`

                          case 'revoke_operation_template_permission':
                            return `Откат: отозвать доступ пользователя #${id('userId')} к шаблону операции ${id('templateId')}`
                          case 'restore_operation_template_permission_level':
                            return `Откат: восстановить уровень доступа пользователя #${id('userId')} к шаблону операции ${id('templateId')}`
                          case 'restore_operation_template_permission':
                            return `Откат: восстановить доступ пользователя #${id('userId')} к шаблону операции ${id('templateId')}`

                          case 'revoke_operation_template_group_permission':
                            return `Откат: отозвать доступ группы #${id('groupId')} к шаблону операции ${id('templateId')}`
                          case 'restore_operation_template_group_permission_level':
                            return `Откат: восстановить уровень доступа группы #${id('groupId')} к шаблону операции ${id('templateId')}`
                          case 'restore_operation_template_group_permission':
                            return `Откат: восстановить доступ группы #${id('groupId')} к шаблону операции ${id('templateId')}`

                          case 'revoke_workflow_template_permission':
                            return `Откат: отозвать доступ пользователя #${id('userId')} к шаблону рабочего процесса ${id('templateId')}`
                          case 'restore_workflow_template_permission_level':
                            return `Откат: восстановить уровень доступа пользователя #${id('userId')} к шаблону рабочего процесса ${id('templateId')}`
                        case 'restore_workflow_template_permission':
                          return `Откат: восстановить доступ пользователя #${id('userId')} к шаблону рабочего процесса ${id('templateId')}`

                        case 'revoke_workflow_template_group_permission':
                          return `Откат: отозвать доступ группы #${id('groupId')} к шаблону рабочего процесса ${id('templateId')}`
                        case 'restore_workflow_template_group_permission_level':
                          return `Откат: восстановить уровень доступа группы #${id('groupId')} к шаблону рабочего процесса ${id('templateId')}`
                        case 'restore_workflow_template_group_permission':
                          return `Откат: восстановить доступ группы #${id('groupId')} к шаблону рабочего процесса ${id('templateId')}`

                        case 'revoke_artifact_permission':
                          return `Откат: отозвать доступ пользователя #${id('userId')} к артефакту ${id('artifactId')}`
                        case 'restore_artifact_permission_level':
                          return `Откат: восстановить уровень доступа пользователя #${id('userId')} к артефакту ${id('artifactId')}`
                        case 'restore_artifact_permission':
                          return `Откат: восстановить доступ пользователя #${id('userId')} к артефакту ${id('artifactId')}`

                        case 'revoke_artifact_group_permission':
                          return `Откат: отозвать доступ группы #${id('groupId')} к артефакту ${id('artifactId')}`
                        case 'restore_artifact_group_permission_level':
                          return `Откат: восстановить уровень доступа группы #${id('groupId')} к артефакту ${id('artifactId')}`
                        case 'restore_artifact_group_permission':
                          return `Откат: восстановить доступ группы #${id('groupId')} к артефакту ${id('artifactId')}`
                      }

                      return `Откат: ${cmd.code}`
                    },
                  }}
                />
                </div>
              </Space>
            ),
          },
          ...(isStaff ? [
            {
              key: 'ib-users',
              label: 'Пользователи ИБ',
              children: (
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  <Card title="Пользователи ИБ" size="small">
                    {!selectedIbDatabaseId && (
                      <Alert
                        type="info"
                        message="Выберите базу, чтобы посмотреть пользователей инфобазы"
                        style={{ marginBottom: 12 }}
                      />
                    )}
                    <TableToolkit
                      table={ibUsersTable}
                      data={selectedIbDatabaseId ? ibUsers : []}
                      total={selectedIbDatabaseId ? totalIbUsers : 0}
                      loading={ibUsersQuery.isLoading}
                      rowKey="id"
                      columns={ibUsersColumns}
                      searchPlaceholder="Поиск пользователей инфобазы"
                      toolbarActions={(
                        <Space>
                          <Select
                            style={{ width: 320 }}
                            placeholder="База"
                            allowClear
                            value={selectedIbDatabaseId}
                            onChange={(value) => {
                              setSelectedIbDatabaseId(value)
                              if (!editingIbUser) {
                                ibUserForm.setFieldsValue({ database_id: value })
                              }
                            }}
                            showSearch
                            filterOption={false}
                            onSearch={setDatabasesRefSearch}
                            onPopupScroll={handleDatabasesPopupScroll}
                            options={databasesSelectOptions}
                            loading={databasesRefQuery.isFetching}
                            optionFilterProp="label"
                          />
                          <Select
                            style={{ width: 160 }}
                            value={ibAuthFilter}
                            onChange={setIbAuthFilter}
                            options={[
                              { label: 'Аутентификация: любая', value: 'any' },
                              { label: 'Аутентификация: local', value: 'local' },
                              { label: 'Аутентификация: AD', value: 'ad' },
                              { label: 'Аутентификация: service', value: 'service' },
                              { label: 'Аутентификация: другое', value: 'other' },
                            ]}
                          />
                          <Select
                            style={{ width: 160 }}
                            value={ibServiceFilter}
                            onChange={setIbServiceFilter}
                            options={[
                              { label: 'Сервисный: любой', value: 'any' },
                              { label: 'Сервисный: да', value: 'true' },
                              { label: 'Сервисный: нет', value: 'false' },
                            ]}
                          />
                          <Select
                            style={{ width: 160 }}
                            value={ibHasUserFilter}
                            onChange={setIbHasUserFilter}
                            options={[
                              { label: 'CC пользователь: любой', value: 'any' },
                              { label: 'CC пользователь: привязан', value: 'true' },
                              { label: 'CC пользователь: не привязан', value: 'false' },
                            ]}
                          />
                          <Button
                            onClick={() => ibUsersQuery.refetch()}
                            disabled={!selectedIbDatabaseId}
                            loading={ibUsersQuery.isFetching}
                          >
                            Обновить
                          </Button>
                        </Space>
                      )}
                    />
                  </Card>

                  <Card title={editingIbUser ? 'Редактировать пользователя ИБ' : 'Добавить пользователя ИБ'} size="small">
                    <Form
                      form={ibUserForm}
                      layout="vertical"
                      initialValues={{ auth_type: 'local', is_service: false }}
                    >
                      <Space size="large" align="start" wrap>
                        <Form.Item
                          label="База"
                          name="database_id"
                          rules={[{ required: true, message: 'Выберите базу' }]}
                        >
                          <Select
                            style={{ width: 320 }}
                            placeholder="База"
                            showSearch
                            filterOption={false}
                            onSearch={setDatabasesRefSearch}
                            onPopupScroll={handleDatabasesPopupScroll}
                            options={databasesSelectOptions}
                            loading={databasesRefQuery.isFetching}
                            optionFilterProp="label"
                            disabled={Boolean(editingIbUser)}
                            onChange={(value) => setSelectedIbDatabaseId(value)}
                          />
                        </Form.Item>
                        <Form.Item
                          label="Логин ИБ"
                          name="ib_username"
                          rules={[{ required: true, message: 'Укажите логин ИБ' }]}
                        >
                          <Input placeholder="ib_user" />
                        </Form.Item>
                        <Form.Item label="Имя в ИБ" name="ib_display_name">
                          <Input placeholder="Имя" />
                        </Form.Item>
                        <Form.Item label="Пользователь CC" name="user_id">
                          <Select
                            showSearch
                            allowClear
                            placeholder="Выберите пользователя"
                            filterOption={false}
                            onSearch={(value) => setUserSearch(value)}
                            options={userOptions}
                            loading={usersQuery.isFetching}
                            style={{ width: 220 }}
                          />
                        </Form.Item>
                        <Form.Item label="Тип аутентификации" name="auth_type">
                          <Select
                            style={{ width: 160 }}
                            options={[
                              { label: 'Локальная', value: 'local' },
                              { label: 'AD', value: 'ad' },
                              { label: 'Сервисная', value: 'service' },
                              { label: 'Другая', value: 'other' },
                            ]}
                          />
                        </Form.Item>
                        <Form.Item label="Сервисный аккаунт" name="is_service" valuePropName="checked">
                          <Switch />
                        </Form.Item>
                      </Space>
                      <Form.Item label="Роли (ИБ)" name="ib_roles">
                        <Select mode="tags" tokenSeparators={[',']} placeholder="Роли (через запятую)" />
                      </Form.Item>
                      <Form.Item
                        label={editingIbUser ? 'Новый пароль ИБ' : 'Пароль ИБ'}
                        name="ib_password"
                        help={(
                          <Space size="small">
                            {editingIbUser ? (
                              <span>Нажмите “Обновить пароль”, чтобы применить изменения.</span>
                            ) : (
                              <span>Можно задать пароль при создании (опционально).</span>
                            )}
                            <Tag color={editingIbUser?.ib_password_configured ? 'green' : 'default'}>
                              {editingIbUser?.ib_password_configured ? 'Задан' : 'Не задан'}
                            </Tag>
                          </Space>
                        )}
                      >
                        <Input.Password placeholder="Введите пароль" />
                      </Form.Item>
                      <Form.Item label="Комментарий" name="notes">
                        <Input placeholder="Комментарий (опционально)" />
                      </Form.Item>
                      <Space>
                        <Button
                          type="primary"
                          onClick={handleIbUserSave}
                          loading={createInfobaseUser.isPending || updateInfobaseUser.isPending}
                        >
                          {editingIbUser ? 'Сохранить' : 'Добавить'}
                        </Button>
                        {editingIbUser && (
                          <Button
                            onClick={handleIbUserPasswordUpdate}
                            loading={setInfobaseUserPassword.isPending}
                          >
                            Обновить пароль
                          </Button>
                        )}
                        {editingIbUser && (
                          <Button
                            danger
                            onClick={handleIbUserPasswordReset}
                            loading={resetInfobaseUserPassword.isPending}
                          >
                            Сбросить пароль
                          </Button>
                        )}
                        {editingIbUser && (
                          <Button onClick={handleIbUserResetForm}>Отменить редактирование</Button>
                        )}
                      </Space>
                    </Form>
                  </Card>
                </Space>
              ),
            },
          ] : []),
          ]

          if (rbacMode === 'roles') {
            const allowedRoleKeys = new Set<string>(['roles', 'audit'])
            return items.filter((item) => allowedRoleKeys.has(String(item.key)))
          }

          const allowedKeys = new Set<string>([
            'permissions',
            'user-roles',
            'effective-access',
            'audit',
            ...(isStaff ? ['ib-users'] : []),
          ])
          return items.filter((item) => allowedKeys.has(String(item.key)))
        })()}
      />

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
        destroyOnClose
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

                  modal.confirm({
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
              disabled={!roleUsageRoleId}
              onClick={() => {
                if (!roleUsageRoleId) return
	                setRbacMode('assignments')
	                setRbacActiveTabKey('permissions')
	                setRbacLastAssignmentsTabKey('permissions')
	                setRbacPermissionsPrincipalType('role')
	                setRbacPermissionsViewMode('principal')
	                setRbacPermissionsList((prev) => ({ ...prev, principal_id: roleUsageRoleId, page: 1 }))
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
    </div>
  )
}
