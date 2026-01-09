import { useEffect, useMemo, useRef, useState } from 'react'
import { App, Alert, Button, Card, Form, Input, Select, Space, Tabs, Typography, Tag, Switch, Table, Modal, Radio, Segmented, Empty } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { ClusterPermission } from '../../api/generated/model/clusterPermission'
import type { DatabasePermission } from '../../api/generated/model/databasePermission'
import type { EffectiveAccessClusterItem } from '../../api/generated/model/effectiveAccessClusterItem'
import type { EffectiveAccessDatabaseItem } from '../../api/generated/model/effectiveAccessDatabaseItem'
import type { EffectiveAccessOperationTemplateItem } from '../../api/generated/model/effectiveAccessOperationTemplateItem'
import type { EffectiveAccessWorkflowTemplateItem } from '../../api/generated/model/effectiveAccessWorkflowTemplateItem'
import type { EffectiveAccessArtifactItem } from '../../api/generated/model/effectiveAccessArtifactItem'
import { useMe } from '../../api/queries/me'
import {
  useAdminAuditLog,
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
  useRoles,
  useSetRoleCapabilities,
  useSetUserRoles,
  useUpdateRole,
  useUserRoles,
  type AdminAuditLogItem,
  type ArtifactGroupPermission,
  type ArtifactPermission,
  type ClusterGroupPermission,
  type DatabaseGroupPermission,
  type OperationTemplateGroupPermission,
  type OperationTemplatePermission,
  type RbacRole,
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
import { RbacResourceBrowser } from './components/RbacResourceBrowser'

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

function mergeSelectOptions(prev: SelectOption[], next: SelectOption[]): SelectOption[] {
  if (prev.length === 0) return next
  const map = new Map(prev.map((opt) => [opt.value, opt]))
  next.forEach((opt) => {
    if (!map.has(opt.value)) map.set(opt.value, opt)
  })
  return Array.from(map.values())
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

function isSelectScrollNearBottom(target: HTMLElement): boolean {
  return target.scrollTop + target.clientHeight >= target.scrollHeight - 24
}

export function RBACPage() {
  const { modal, message } = App.useApp()
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

	  const [databasesRefSearch, setDatabasesRefSearch] = useState<string>('')
	  const debouncedDatabasesRefSearch = useDebouncedValue(databasesRefSearch, 300)
  const [databasesRefOffset, setDatabasesRefOffset] = useState<number>(0)
  const [databasesRefOptions, setDatabasesRefOptions] = useState<SelectOption[]>([])
  const databasesLabelById = useRef<Map<string, string>>(new Map())
  const databasesRefQuery = useRbacRefDatabases({
    search: debouncedDatabasesRefSearch || undefined,
    limit: REF_PAGE_SIZE,
    offset: databasesRefOffset,
  }, { enabled: canManageRbac })
  const databasesRefTotal = typeof databasesRefQuery.data?.total === 'number'
    ? databasesRefQuery.data.total
    : databasesRefOptions.length

  useEffect(() => {
    setDatabasesRefOffset(0)
    setDatabasesRefOptions([])
  }, [debouncedDatabasesRefSearch])

  useEffect(() => {
    const page = databasesRefQuery.data?.databases
    if (!page) return
    page.forEach((db) => {
      databasesLabelById.current.set(db.id, `${db.name} #${db.id}`)
    })
    const next = page.map((db) => ({ label: `${db.name} #${db.id}`, value: db.id }))
    setDatabasesRefOptions((prev) => databasesRefOffset === 0 ? next : mergeSelectOptions(prev, next))
  }, [databasesRefQuery.data?.databases, databasesRefOffset])

  const handleDatabasesPopupScroll = (event: any) => {
    const target = event?.target as HTMLElement | undefined
    if (!target) return
    if (!isSelectScrollNearBottom(target)) return
    if (databasesRefQuery.isFetching) return
    if (databasesRefOptions.length >= databasesRefTotal) return
    setDatabasesRefOffset((prev) => prev + REF_PAGE_SIZE)
  }

  const [operationTemplatesRefSearch, setOperationTemplatesRefSearch] = useState<string>('')
  const debouncedOperationTemplatesRefSearch = useDebouncedValue(operationTemplatesRefSearch, 300)
  const [operationTemplatesRefOffset, setOperationTemplatesRefOffset] = useState<number>(0)
  const [operationTemplatesRefOptions, setOperationTemplatesRefOptions] = useState<SelectOption[]>([])
  const operationTemplatesLabelById = useRef<Map<string, string>>(new Map())
  const operationTemplatesRefQuery = useRbacRefOperationTemplates({
    search: debouncedOperationTemplatesRefSearch || undefined,
    limit: REF_PAGE_SIZE,
    offset: operationTemplatesRefOffset,
  }, { enabled: canManageRbac })
  const operationTemplatesRefTotal = typeof operationTemplatesRefQuery.data?.total === 'number'
    ? operationTemplatesRefQuery.data.total
    : operationTemplatesRefOptions.length

  useEffect(() => {
    setOperationTemplatesRefOffset(0)
    setOperationTemplatesRefOptions([])
  }, [debouncedOperationTemplatesRefSearch])

  useEffect(() => {
    const page = operationTemplatesRefQuery.data?.templates
    if (!page) return
    page.forEach((tpl) => {
      operationTemplatesLabelById.current.set(tpl.id, `${tpl.name} #${tpl.id}`)
    })
    const next = page.map((tpl) => ({ label: `${tpl.name} #${tpl.id}`, value: tpl.id }))
    setOperationTemplatesRefOptions((prev) => operationTemplatesRefOffset === 0 ? next : mergeSelectOptions(prev, next))
  }, [operationTemplatesRefQuery.data?.templates, operationTemplatesRefOffset])

  const handleOperationTemplatesPopupScroll = (event: any) => {
    const target = event?.target as HTMLElement | undefined
    if (!target) return
    if (!isSelectScrollNearBottom(target)) return
    if (operationTemplatesRefQuery.isFetching) return
    if (operationTemplatesRefOptions.length >= operationTemplatesRefTotal) return
    setOperationTemplatesRefOffset((prev) => prev + REF_PAGE_SIZE)
  }

  const [workflowTemplatesRefSearch, setWorkflowTemplatesRefSearch] = useState<string>('')
  const debouncedWorkflowTemplatesRefSearch = useDebouncedValue(workflowTemplatesRefSearch, 300)
  const [workflowTemplatesRefOffset, setWorkflowTemplatesRefOffset] = useState<number>(0)
  const [workflowTemplatesRefOptions, setWorkflowTemplatesRefOptions] = useState<SelectOption[]>([])
  const workflowTemplatesLabelById = useRef<Map<string, string>>(new Map())
  const workflowTemplatesRefQuery = useRbacRefWorkflowTemplates({
    search: debouncedWorkflowTemplatesRefSearch || undefined,
    limit: REF_PAGE_SIZE,
    offset: workflowTemplatesRefOffset,
  }, { enabled: canManageRbac })
  const workflowTemplatesRefTotal = typeof workflowTemplatesRefQuery.data?.total === 'number'
    ? workflowTemplatesRefQuery.data.total
    : workflowTemplatesRefOptions.length

  useEffect(() => {
    setWorkflowTemplatesRefOffset(0)
    setWorkflowTemplatesRefOptions([])
  }, [debouncedWorkflowTemplatesRefSearch])

  useEffect(() => {
    const page = workflowTemplatesRefQuery.data?.templates
    if (!page) return
    page.forEach((tpl) => {
      workflowTemplatesLabelById.current.set(tpl.id, `${tpl.name} #${tpl.id}`)
    })
    const next = page.map((tpl) => ({ label: `${tpl.name} #${tpl.id}`, value: tpl.id }))
    setWorkflowTemplatesRefOptions((prev) => workflowTemplatesRefOffset === 0 ? next : mergeSelectOptions(prev, next))
  }, [workflowTemplatesRefQuery.data?.templates, workflowTemplatesRefOffset])

  const handleWorkflowTemplatesPopupScroll = (event: any) => {
    const target = event?.target as HTMLElement | undefined
    if (!target) return
    if (!isSelectScrollNearBottom(target)) return
    if (workflowTemplatesRefQuery.isFetching) return
    if (workflowTemplatesRefOptions.length >= workflowTemplatesRefTotal) return
    setWorkflowTemplatesRefOffset((prev) => prev + REF_PAGE_SIZE)
  }

  const [artifactsRefSearch, setArtifactsRefSearch] = useState<string>('')
  const debouncedArtifactsRefSearch = useDebouncedValue(artifactsRefSearch, 300)
  const [artifactsRefOffset, setArtifactsRefOffset] = useState<number>(0)
  const [artifactsRefOptions, setArtifactsRefOptions] = useState<SelectOption[]>([])
  const artifactsLabelById = useRef<Map<string, string>>(new Map())
  const artifactsRefQuery = useRbacRefArtifacts({
    search: debouncedArtifactsRefSearch || undefined,
    limit: REF_PAGE_SIZE,
    offset: artifactsRefOffset,
  }, { enabled: canManageRbac })
  const artifactsRefTotal = typeof artifactsRefQuery.data?.total === 'number'
    ? artifactsRefQuery.data.total
    : artifactsRefOptions.length

  useEffect(() => {
    setArtifactsRefOffset(0)
    setArtifactsRefOptions([])
  }, [debouncedArtifactsRefSearch])

  useEffect(() => {
    const page = artifactsRefQuery.data?.artifacts
    if (!page) return
    page.forEach((artifact) => {
      artifactsLabelById.current.set(artifact.id, `${artifact.name} #${artifact.id}`)
    })
    const next = page.map((artifact) => ({ label: `${artifact.name} #${artifact.id}`, value: artifact.id }))
    setArtifactsRefOptions((prev) => artifactsRefOffset === 0 ? next : mergeSelectOptions(prev, next))
  }, [artifactsRefQuery.data?.artifacts, artifactsRefOffset])

  const handleArtifactsPopupScroll = (event: any) => {
    const target = event?.target as HTMLElement | undefined
    if (!target) return
    if (!isSelectScrollNearBottom(target)) return
    if (artifactsRefQuery.isFetching) return
    if (artifactsRefOptions.length >= artifactsRefTotal) return
    setArtifactsRefOffset((prev) => prev + REF_PAGE_SIZE)
  }

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
  const [selectedRolesUserId, setSelectedRolesUserId] = useState<number | undefined>()

  const [selectedEffectiveUserId, setSelectedEffectiveUserId] = useState<number | undefined>()
  const [effectiveIncludeClusters, setEffectiveIncludeClusters] = useState<boolean>(true)
  const [effectiveIncludeDatabases, setEffectiveIncludeDatabases] = useState<boolean>(true)
  const [effectiveIncludeOperationTemplates, setEffectiveIncludeOperationTemplates] = useState<boolean>(false)
  const [effectiveIncludeWorkflowTemplates, setEffectiveIncludeWorkflowTemplates] = useState<boolean>(false)
  const [effectiveIncludeArtifacts, setEffectiveIncludeArtifacts] = useState<boolean>(false)
  const [effectiveDbPage, setEffectiveDbPage] = useState<number>(1)
  const [effectiveDbPageSize, setEffectiveDbPageSize] = useState<number>(50)

  const [roleEditorOpen, setRoleEditorOpen] = useState<boolean>(false)
  const [roleEditorRoleId, setRoleEditorRoleId] = useState<number | null>(null)
  const [roleEditorPermissionCodes, setRoleEditorPermissionCodes] = useState<string[]>([])
  const [roleEditorReason, setRoleEditorReason] = useState<string>('')
  const [renameRoleOpen, setRenameRoleOpen] = useState<boolean>(false)
  const [renameRoleRoleId, setRenameRoleRoleId] = useState<number | null>(null)
  const [renameRoleName, setRenameRoleName] = useState<string>('')
  const [renameRoleReason, setRenameRoleReason] = useState<string>('')
  const [deleteRoleOpen, setDeleteRoleOpen] = useState<boolean>(false)
  const [deleteRoleRoleId, setDeleteRoleRoleId] = useState<number | null>(null)
  const [deleteRoleReason, setDeleteRoleReason] = useState<string>('')
  const [cloneRoleOpen, setCloneRoleOpen] = useState<boolean>(false)
  const [cloneRoleSourceRoleId, setCloneRoleSourceRoleId] = useState<number | null>(null)
  const [cloneRoleName, setCloneRoleName] = useState<string>('')
  const [cloneRoleReason, setCloneRoleReason] = useState<string>('')
  const [roleUsageOpen, setRoleUsageOpen] = useState<boolean>(false)
  const [roleUsageRoleId, setRoleUsageRoleId] = useState<number | null>(null)
  const [auditSearch, setAuditSearch] = useState<string>('')
  const [auditPage, setAuditPage] = useState<number>(1)
  const [auditPageSize, setAuditPageSize] = useState<number>(100)
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

  const [bulkGrantClusterGroupForm] = Form.useForm<{
    group_id: number
    cluster_ids: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [bulkRevokeClusterGroupForm] = Form.useForm<{
    group_id: number
    cluster_ids: string
    reason: string
  }>()

  const [bulkGrantDatabaseGroupForm] = Form.useForm<{
    group_id: number
    database_ids: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [bulkRevokeDatabaseGroupForm] = Form.useForm<{
    group_id: number
    database_ids: string
    reason: string
  }>()

  const [rbacPermissionsGrantForm] = Form.useForm<{
    principal_id: number
    resource_id: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [rbacPermissionsBulkGrantClusterGroupForm] = Form.useForm<{
    group_id: number
    cluster_ids: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [rbacPermissionsBulkRevokeClusterGroupForm] = Form.useForm<{
    group_id: number
    cluster_ids: string
    reason: string
  }>()

  const [rbacPermissionsBulkGrantDatabaseGroupForm] = Form.useForm<{
    group_id: number
    database_ids: string
    level: PermissionLevelCode
    notes?: string
    reason: string
  }>()

  const [rbacPermissionsBulkRevokeDatabaseGroupForm] = Form.useForm<{
    group_id: number
    database_ids: string
    reason: string
  }>()

  const [createRoleForm] = Form.useForm<{ name: string; reason: string }>()
  const [assignRolesForm] = Form.useForm<{
    user_id: number
    group_ids: number[]
    mode?: 'replace' | 'add' | 'remove'
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

  const parseIdListFromText = (value: unknown): string[] => {
    if (typeof value !== 'string') return []
    const parts = value
      .split(/[\n\r\t ,;]+/)
      .map((p) => p.trim())
      .filter(Boolean)

    const seen = new Set<string>()
    const out: string[] = []
    for (const part of parts) {
      if (seen.has(part)) continue
      seen.add(part)
      out.push(part)
    }
    return out
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

	  const levelsHintClustersDatabases = (
	    <Alert
	      type="info"
      showIcon
      message="Подсказка по уровням доступа (Clusters/Databases)"
      description={(
        <div>
          <div><Text strong>VIEW</Text>: видеть и читать (списки/детали/метаданные/статусы).</div>
          <div><Text strong>OPERATE</Text>: выполнять операции без изменения конфигурации.</div>
          <div><Text strong>MANAGE</Text>: менять настройки/конфигурацию объекта.</div>
          <div><Text strong>ADMIN</Text>: самый высокий уровень, потенциально разрушительные действия (если поддерживаются).</div>
        </div>
      )}
    />
  )

  const levelsHintTemplatesWorkflows = (
    <Alert
      type="info"
      showIcon
      message="Подсказка по уровням доступа (Templates/Workflows)"
      description={(
        <div>
          <div><Text strong>VIEW</Text>: читать шаблон.</div>
          <div><Text strong>OPERATE</Text>: исполнять (запускать) workflow/операции по шаблону.</div>
          <div><Text strong>MANAGE</Text>: создавать/редактировать/публиковать.</div>
          <div><Text strong>ADMIN</Text>: самый высокий уровень (если домен не разделяет отдельно).</div>
        </div>
      )}
    />
  )

  const levelsHintArtifacts = (
    <Alert
      type="info"
      showIcon
      message="Подсказка по уровням доступа (Artifacts)"
      description={(
        <div>
          <div><Text strong>VIEW</Text>: видеть артефакт и версии (read).</div>
          <div><Text strong>OPERATE</Text>: upload/публикация версий (операционные действия).</div>
          <div><Text strong>MANAGE</Text>: управлять артефактом (настройки/алиасы/soft-delete).</div>
          <div><Text strong>ADMIN</Text>: самый высокий уровень (если домен не разделяет отдельно).</div>
        </div>
      )}
    />
  )

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

  const confirmReason = (title: string, onConfirm: (reason: string) => Promise<void>) => {
    let value = ''
    modal.confirm({
      title,
      content: (
        <Input.TextArea
          placeholder="Reason (required)"
          autoSize={{ minRows: 2, maxRows: 6 }}
          onChange={(event) => {
            value = event.target.value
          }}
        />
      ),
      okText: 'Confirm',
      cancelText: 'Cancel',
      onOk: async () => {
        const reason = value.trim()
        if (!reason) {
          message.error('Reason is required')
          return Promise.reject(new Error('Reason is required'))
        }
        await onConfirm(reason)
      },
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

      message.success('Granted')
      rbacPermissionsGrantForm.resetFields()
      setRbacPermissionsList((prev) => ({ ...prev, page: 1 }))
    } catch {
      message.error('Grant failed')
    }
  }

  const clusterFallbackColumns = useMemo(() => [
    { key: 'user_id', label: 'User', groupKey: 'core', groupLabel: 'Core' },
    { key: 'cluster', label: 'Cluster', groupKey: 'core', groupLabel: 'Core' },
    { key: 'level', label: 'Level', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'granted_at', label: 'Granted At', groupKey: 'time', groupLabel: 'Time' },
    { key: 'granted_by', label: 'Granted By', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'notes', label: 'Notes', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'actions', label: 'Action', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const databaseFallbackColumns = useMemo(() => [
    { key: 'user_id', label: 'User', groupKey: 'core', groupLabel: 'Core' },
    { key: 'database', label: 'Database', groupKey: 'core', groupLabel: 'Core' },
    { key: 'database_id', label: 'Database ID', groupKey: 'core', groupLabel: 'Core' },
    { key: 'level', label: 'Level', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'granted_at', label: 'Granted At', groupKey: 'time', groupLabel: 'Time' },
    { key: 'granted_by', label: 'Granted By', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'notes', label: 'Notes', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'actions', label: 'Action', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const clusterColumns: ColumnsType<ClusterPermission> = useMemo(
    () => [
      {
        title: 'User',
        key: 'user_id',
        render: (_, row) => (
          <span>
            {row.user?.username} <Text type="secondary">#{row.user?.id}</Text>
          </span>
        ),
      },
      { title: 'Cluster', dataIndex: ['cluster', 'name'], key: 'cluster' },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      { title: 'Granted At', dataIndex: 'granted_at', key: 'granted_at' },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_, row) => (
          <Button
            danger
            size="small"
            loading={revokeCluster.isPending}
            onClick={() => {
              if (!row.user?.id || !row.cluster?.id) return
              confirmReason('Revoke cluster user permission?', async (reason) => {
                await revokeCluster.mutateAsync({ user_id: row.user.id, cluster_id: row.cluster.id, reason })
              })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [confirmReason, revokeCluster]
  )

  const databaseColumns: ColumnsType<DatabasePermission> = useMemo(
    () => [
      {
        title: 'User',
        key: 'user_id',
        render: (_, row) => (
          <span>
            {row.user?.username} <Text type="secondary">#{row.user?.id}</Text>
          </span>
        ),
      },
      { title: 'Database', dataIndex: ['database', 'name'], key: 'database' },
      { title: 'Database ID', dataIndex: ['database', 'id'], key: 'database_id' },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      { title: 'Granted At', dataIndex: 'granted_at', key: 'granted_at' },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_, row) => (
          <Button
            danger
            size="small"
            loading={revokeDatabase.isPending}
            onClick={() => {
              if (!row.user?.id || !row.database?.id) return
              confirmReason('Revoke database user permission?', async (reason) => {
                await revokeDatabase.mutateAsync({ user_id: row.user.id, database_id: row.database.id, reason })
              })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [confirmReason, revokeDatabase]
  )

  const clusterGroupColumns: ColumnsType<ClusterGroupPermission> = useMemo(
    () => [
      {
        title: 'Role',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Cluster',
        key: 'cluster',
        render: (_: unknown, row) => (
          <span>
            {row.cluster.name} <Text type="secondary">#{row.cluster.id}</Text>
          </span>
        ),
      },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      {
        title: 'Granted At',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeClusterGroup.isPending}
            onClick={() => {
              confirmReason('Revoke cluster role permission?', async (reason) => {
                await revokeClusterGroup.mutateAsync({ group_id: row.group.id, cluster_id: row.cluster.id, reason })
              })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [confirmReason, revokeClusterGroup]
  )

  const databaseGroupColumns: ColumnsType<DatabaseGroupPermission> = useMemo(
    () => [
      {
        title: 'Role',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Database',
        key: 'database',
        render: (_: unknown, row) => (
          <span>
            {row.database.name} <Text type="secondary">#{row.database.id}</Text>
          </span>
        ),
      },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      {
        title: 'Granted At',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeDatabaseGroup.isPending}
            onClick={() => {
              confirmReason('Revoke database role permission?', async (reason) => {
                await revokeDatabaseGroup.mutateAsync({ group_id: row.group.id, database_id: row.database.id, reason })
              })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [confirmReason, revokeDatabaseGroup]
  )

  const operationTemplateUserColumns: ColumnsType<OperationTemplatePermission> = useMemo(
    () => [
      {
        title: 'User',
        key: 'user',
        render: (_: unknown, row) => (
          <span>
            {row.user.username} <Text type="secondary">#{row.user.id}</Text>
          </span>
        ),
      },
      {
        title: 'Template',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      {
        title: 'Granted At',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeOperationTemplate.isPending}
            onClick={() => {
              confirmReason('Revoke operation template user permission?', async (reason) => {
                await revokeOperationTemplate.mutateAsync({ user_id: row.user.id, template_id: row.template.id, reason })
              })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [confirmReason, revokeOperationTemplate]
  )

  const operationTemplateGroupColumns: ColumnsType<OperationTemplateGroupPermission> = useMemo(
    () => [
      {
        title: 'Role',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Template',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      {
        title: 'Granted At',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeOperationTemplateGroup.isPending}
            onClick={() => {
              confirmReason('Revoke operation template role permission?', async (reason) => {
                await revokeOperationTemplateGroup.mutateAsync({ group_id: row.group.id, template_id: row.template.id, reason })
              })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [confirmReason, revokeOperationTemplateGroup]
  )

  const workflowTemplateUserColumns: ColumnsType<WorkflowTemplatePermission> = useMemo(
    () => [
      {
        title: 'User',
        key: 'user',
        render: (_: unknown, row) => (
          <span>
            {row.user.username} <Text type="secondary">#{row.user.id}</Text>
          </span>
        ),
      },
      {
        title: 'Workflow Template',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      {
        title: 'Granted At',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeWorkflowTemplate.isPending}
            onClick={() => {
              confirmReason('Revoke workflow template user permission?', async (reason) => {
                await revokeWorkflowTemplate.mutateAsync({ user_id: row.user.id, template_id: row.template.id, reason })
              })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [confirmReason, revokeWorkflowTemplate]
  )

  const workflowTemplateGroupColumns: ColumnsType<WorkflowTemplateGroupPermission> = useMemo(
    () => [
      {
        title: 'Role',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Workflow Template',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      {
        title: 'Granted At',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeWorkflowTemplateGroup.isPending}
            onClick={() => {
              confirmReason('Revoke workflow template role permission?', async (reason) => {
                await revokeWorkflowTemplateGroup.mutateAsync({ group_id: row.group.id, template_id: row.template.id, reason })
              })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [confirmReason, revokeWorkflowTemplateGroup]
  )

  const artifactUserColumns: ColumnsType<ArtifactPermission> = useMemo(
    () => [
      {
        title: 'User',
        key: 'user',
        render: (_: unknown, row) => (
          <span>
            {row.user.username} <Text type="secondary">#{row.user.id}</Text>
          </span>
        ),
      },
      {
        title: 'Artifact',
        key: 'artifact',
        render: (_: unknown, row) => (
          <span>
            {row.artifact.name} <Text type="secondary">#{row.artifact.id}</Text>
          </span>
        ),
      },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      {
        title: 'Granted At',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeArtifact.isPending}
            onClick={() => {
              confirmReason('Revoke artifact user permission?', async (reason) => {
                await revokeArtifact.mutateAsync({ user_id: row.user.id, artifact_id: row.artifact.id, reason })
              })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [confirmReason, revokeArtifact]
  )

  const artifactGroupColumns: ColumnsType<ArtifactGroupPermission> = useMemo(
    () => [
      {
        title: 'Role',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Artifact',
        key: 'artifact',
        render: (_: unknown, row) => (
          <span>
            {row.artifact.name} <Text type="secondary">#{row.artifact.id}</Text>
          </span>
        ),
      },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      {
        title: 'Granted At',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeArtifactGroup.isPending}
            onClick={() => {
              confirmReason('Revoke artifact role permission?', async (reason) => {
                await revokeArtifactGroup.mutateAsync({ group_id: row.group.id, artifact_id: row.artifact.id, reason })
              })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [confirmReason, revokeArtifactGroup]
  )

  const rolesColumns: ColumnsType<RbacRole> = useMemo(
    () => [
      { title: 'Role', dataIndex: 'name', key: 'name' },
      { title: 'Users', dataIndex: 'users_count', key: 'users_count' },
      { title: 'Capabilities', dataIndex: 'permissions_count', key: 'permissions_count' },
      {
        title: 'Actions',
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
              Usage
            </Button>
            <Button
              size="small"
              onClick={() => {
                setRoleEditorRoleId(row.id)
                setRoleEditorPermissionCodes(row.permission_codes)
                setRoleEditorReason('')
                setRoleEditorOpen(true)
              }}
            >
              Capabilities
            </Button>
            <Button
              size="small"
              onClick={() => {
                setCloneRoleSourceRoleId(row.id)
                setCloneRoleName(`${row.name} copy`)
                setCloneRoleReason('')
                setCloneRoleOpen(true)
              }}
            >
              Clone
            </Button>
            <Button
              size="small"
              onClick={() => {
                setRenameRoleRoleId(row.id)
                setRenameRoleName(row.name)
                setRenameRoleReason('')
                setRenameRoleOpen(true)
              }}
            >
              Rename
            </Button>
            <Button
              danger
              size="small"
              onClick={() => {
                setDeleteRoleRoleId(row.id)
                setDeleteRoleReason('')
                setDeleteRoleOpen(true)
              }}
            >
              Delete
            </Button>
          </Space>
        ),
      },
    ],
    []
  )

  const auditColumns: ColumnsType<AdminAuditLogItem> = useMemo(
    () => [
      {
        title: 'Created',
        dataIndex: 'created_at',
        key: 'created_at',
        render: (value: string) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Actor',
        dataIndex: 'actor_username',
        key: 'actor_username',
        render: (value: string) => value || '-',
      },
      { title: 'Action', dataIndex: 'action', key: 'action' },
      {
        title: 'Outcome',
        dataIndex: 'outcome',
        key: 'outcome',
        render: (value: string) => (
          <Tag color={value === 'success' ? 'green' : (value === 'error' ? 'red' : 'default')}>
            {value}
          </Tag>
        ),
      },
      {
        title: 'Target',
        key: 'target',
        render: (_: unknown, row) => `${row.target_type}:${row.target_id}`,
      },
      {
        title: 'Reason',
        key: 'reason',
        render: (_: unknown, row) => {
          const reason = typeof row.metadata?.reason === 'string' ? row.metadata.reason : ''
          return reason ? reason : '-'
        },
      },
      {
        title: 'Details',
        key: 'details',
        render: (_: unknown, row) => (
          <Button
            size="small"
            onClick={() => {
              modal.info({
                title: `Audit #${row.id}`,
                width: 860,
                content: (
                  <pre style={{ whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(row, null, 2)}
                  </pre>
                ),
              })
            }}
          >
            View
          </Button>
        ),
      },
    ],
    [modal]
  )

  const ibAuthTypeLabels: Record<string, string> = {
    local: 'Local',
    ad: 'AD',
    service: 'Service',
    other: 'Other',
  }

  const ibUsersColumns: ColumnsType<InfobaseUserMapping> = useMemo(
    () => [
      {
        title: 'IB User',
        key: 'ib_user',
        render: (_: unknown, row) => (
          <span>
            {row.ib_username}{' '}
            <Text type="secondary">{row.ib_display_name || '-'}</Text>
          </span>
        ),
      },
      {
        title: 'CC User',
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
        title: 'Roles',
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
        title: 'Auth',
        key: 'auth_type',
        render: (_: unknown, row) => (
          <Tag>{ibAuthTypeLabels[row.auth_type] || row.auth_type}</Tag>
        ),
      },
      {
        title: 'Service',
        key: 'is_service',
        render: (_: unknown, row) => (
          <Tag color={row.is_service ? 'blue' : 'default'}>
            {row.is_service ? 'Yes' : 'No'}
          </Tag>
        ),
      },
      {
        title: 'Password',
        key: 'password',
        render: (_: unknown, row) => (
          <Tag color={row.ib_password_configured ? 'green' : 'default'}>
            {row.ib_password_configured ? 'Configured' : 'Missing'}
          </Tag>
        ),
      },
      {
        title: 'Action',
        key: 'actions',
        render: (_: unknown, row) => (
          <Space size="small">
            <Button size="small" onClick={() => handleIbUserEdit(row)}>
              Edit
            </Button>
            <Button
              danger
              size="small"
              loading={deleteInfobaseUser.isPending}
              onClick={() => handleIbUserDelete(row)}
            >
              Delete
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
      { key: 'ib_username', label: 'IB User', groupKey: 'core', groupLabel: 'Core' },
      { key: 'ib_display_name', label: 'Display Name', groupKey: 'core', groupLabel: 'Core' },
      { key: 'cc_user', label: 'CC User', groupKey: 'core', groupLabel: 'Core' },
      { key: 'roles', label: 'Roles', groupKey: 'meta', groupLabel: 'Meta' },
      { key: 'auth_type', label: 'Auth', groupKey: 'meta', groupLabel: 'Meta' },
      { key: 'is_service', label: 'Service', groupKey: 'meta', groupLabel: 'Meta' },
      { key: 'password', label: 'Password', groupKey: 'meta', groupLabel: 'Meta' },
      { key: 'actions', label: 'Action', groupKey: 'actions', groupLabel: 'Actions' },
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

  const userRolesQuery = useUserRoles(selectedRolesUserId, { enabled: canManageRbac && Boolean(selectedRolesUserId) })

  const effectiveAccessQuery = useEffectiveAccess(selectedEffectiveUserId, {
    includeDatabases: effectiveIncludeDatabases,
    includeClusters: effectiveIncludeClusters,
    includeTemplates: effectiveIncludeOperationTemplates,
    includeWorkflows: effectiveIncludeWorkflowTemplates,
    includeArtifacts: effectiveIncludeArtifacts,
    limit: effectiveIncludeDatabases ? effectiveDbPageSize : undefined,
    offset: effectiveIncludeDatabases ? (effectiveDbPage - 1) * effectiveDbPageSize : undefined,
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

  const debouncedAuditSearch = useDebouncedValue(auditSearch, 300)
  const auditQuery = useAdminAuditLog({
    search: debouncedAuditSearch || undefined,
    limit: auditPageSize,
    offset: (auditPage - 1) * auditPageSize,
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
      ...(userRolesQuery.data?.user ? [userRolesQuery.data.user] : []),
    ]
    const combined = [...base, ...extra]
    const map = new Map<number, { label: string; value: number }>()
    combined.forEach((user) => {
      if (!map.has(user.id)) {
        map.set(user.id, { label: `${user.username} #${user.id}`, value: user.id })
      }
    })
    return Array.from(map.values())
  }, [usersQuery.data?.users, editingIbUser?.user, userRolesQuery.data?.user])

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
    capabilities.map((cap) => ({ label: cap.exists ? cap.code : `${cap.code} (missing)`, value: cap.code }))
  ), [capabilities])

  const effectiveClustersColumns: ColumnsType<EffectiveAccessClusterItem> = useMemo(() => [
    {
      title: 'Cluster',
      key: 'cluster',
      render: (_: unknown, row) => (
        <span>
          {row.cluster.name} <Text type="secondary">#{row.cluster.id}</Text>
        </span>
      ),
    },
    { title: 'Level', dataIndex: 'level', key: 'level' },
  ], [])

  const effectiveDatabasesColumns: ColumnsType<EffectiveAccessDatabaseItem> = useMemo(() => [
    {
      title: 'Database',
      key: 'database',
      render: (_: unknown, row) => (
        <span>
          {row.database.name} <Text type="secondary">#{row.database.id}</Text>
        </span>
      ),
    },
    {
      title: 'Cluster',
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
    { title: 'Level', dataIndex: 'level', key: 'level' },
    {
      title: 'Source',
      key: 'source',
      render: (_: unknown, row) => {
        const source = row.source
        const color = source === 'direct' ? 'blue' : source === 'group' ? 'purple' : 'gold'
        return <Tag color={color}>{source}</Tag>
      },
    },
    {
      title: 'Via cluster',
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
  ], [clusterNameById])

  const effectiveOperationTemplatesColumns: ColumnsType<EffectiveAccessOperationTemplateItem> = useMemo(() => [
    {
      title: 'Template',
      key: 'template',
      render: (_: unknown, row) => (
        <span>
          {row.template.name} <Text type="secondary">#{row.template.id}</Text>
        </span>
      ),
    },
    { title: 'Level', dataIndex: 'level', key: 'level' },
    {
      title: 'Source',
      key: 'source',
      render: (_: unknown, row) => <Tag color={row.source === 'direct' ? 'blue' : 'purple'}>{row.source}</Tag>,
    },
  ], [])

  const effectiveWorkflowTemplatesColumns: ColumnsType<EffectiveAccessWorkflowTemplateItem> = useMemo(() => [
    {
      title: 'Template',
      key: 'template',
      render: (_: unknown, row) => (
        <span>
          {row.template.name} <Text type="secondary">#{row.template.id}</Text>
        </span>
      ),
    },
    { title: 'Level', dataIndex: 'level', key: 'level' },
    {
      title: 'Source',
      key: 'source',
      render: (_: unknown, row) => <Tag color={row.source === 'direct' ? 'blue' : 'purple'}>{row.source}</Tag>,
    },
  ], [])

  const effectiveArtifactsColumns: ColumnsType<EffectiveAccessArtifactItem> = useMemo(() => [
    {
      title: 'Artifact',
      key: 'artifact',
      render: (_: unknown, row) => (
        <span>
          {row.artifact.name} <Text type="secondary">#{row.artifact.id}</Text>
        </span>
      ),
    },
    { title: 'Level', dataIndex: 'level', key: 'level' },
    {
      title: 'Source',
      key: 'source',
      render: (_: unknown, row) => <Tag color={row.source === 'direct' ? 'blue' : 'purple'}>{row.source}</Tag>,
    },
  ], [])

  const selectedRoleForEditor = roleEditorRoleId
    ? roles.find((role) => role.id === roleEditorRoleId) ?? null
    : null

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

  const auditItems = auditQuery.data?.items ?? []
  const totalAuditItems = typeof auditQuery.data?.total === 'number'
    ? auditQuery.data.total
    : auditItems.length

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
        <Text type="secondary">Loading...</Text>
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
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Подсказка по уровням VIEW / OPERATE / MANAGE / ADMIN"
        description={(
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
        )}
      />
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
            label: 'Roles',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Create Role" size="small">
                  <Form
                    form={createRoleForm}
                    layout="inline"
                    onFinish={(values) => createRole.mutate(values, { onSuccess: () => createRoleForm.resetFields() })}
                  >
                    <Form.Item name="name" rules={[{ required: true, message: 'name required' }]}>
                      <Input placeholder="Role name" style={{ width: 240 }} />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input placeholder="Reason" style={{ width: 320 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={createRole.isPending}>
                        Create
                      </Button>
                    </Form.Item>
                    <Form.Item>
                      <Button onClick={() => rolesQuery.refetch()} loading={rolesQuery.isFetching}>
                        Refresh
                      </Button>
                    </Form.Item>
                  </Form>
                </Card>

                <Card title="Roles" size="small">
                  <Space wrap style={{ marginBottom: 12 }}>
                    <Input
                      placeholder="Search role"
                      style={{ width: 280 }}
                      value={roleSearch}
                      onChange={(e) => setRoleSearch(e.target.value)}
                    />
                    <Button onClick={() => rolesQuery.refetch()} loading={rolesQuery.isFetching}>
                      Refresh
                    </Button>
                  </Space>
                  <Table
                    size="small"
                    columns={rolesColumns}
                    dataSource={visibleRoles}
                    loading={rolesQuery.isLoading}
                    rowKey="id"
                    pagination={{ pageSize: 50 }}
                  />
                </Card>
              </Space>
            ),
          },
          {
            key: 'permissions',
            label: 'Доступ к объектам',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                {(rbacPermissionsResourceKey === 'clusters' || rbacPermissionsResourceKey === 'databases')
                  ? levelsHintClustersDatabases
                  : (rbacPermissionsResourceKey === 'artifacts')
                    ? levelsHintArtifacts
                    : levelsHintTemplatesWorkflows}

                <Card title="Объект и субъект" size="small">
                  <Space wrap>
                    <Select
                      style={{ width: 260 }}
                      value={rbacPermissionsResourceKey}
                      options={[
                        { label: 'Clusters', value: 'clusters' },
                        { label: 'Databases', value: 'databases' },
                        { label: 'Operation Templates', value: 'operation-templates' },
                        { label: 'Workflow Templates', value: 'workflow-templates' },
                        { label: 'Artifacts', value: 'artifacts' },
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
	                      <Radio.Button value="user">User</Radio.Button>
	                      <Radio.Button value="role">Role</Radio.Button>
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
                        message: rbacPermissionsPrincipalType === 'user' ? 'user required' : 'role required',
                      }]}
                    >
                      {rbacPermissionsPrincipalType === 'user' ? (
                        <Select
                          style={{ width: 240 }}
                          placeholder="User"
                          allowClear
                          showSearch
                          filterOption={false}
                          onSearch={setUserSearch}
                          options={userOptions}
                          loading={usersQuery.isFetching}
                        />
                      ) : (
                        <Select
                          style={{ width: 240 }}
                          placeholder="Role"
                          options={roleOptions}
                          showSearch
                          optionFilterProp="label"
                        />
                      )}
                    </Form.Item>

                    <Form.Item name="resource_id" rules={[{ required: true, message: 'resource required' }]}>
                      <Select
                        style={{ width: 360 }}
                        placeholder="Resource"
                        disabled={rbacPermissionsViewMode === 'resource'}
                        showSearch={rbacPermissionsResourceRef.showSearch}
                        optionFilterProp="label"
                        filterOption={rbacPermissionsResourceRef.filterOption}
                        onSearch={rbacPermissionsResourceRef.filterOption ? undefined : rbacPermissionsResourceRef.onSearch}
                        onPopupScroll={rbacPermissionsResourceRef.filterOption ? undefined : rbacPermissionsResourceRef.onPopupScroll}
                        options={rbacPermissionsResourceRef.options}
                        loading={rbacPermissionsResourceRef.loading}
                      />
                    </Form.Item>

                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>

                    <Form.Item name="notes">
                      <Input placeholder="Notes (optional)" style={{ width: 220 }} />
                    </Form.Item>

                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input placeholder="Reason" style={{ width: 260 }} />
                    </Form.Item>

                    <Form.Item>
                      <Button
                        type="primary"
                        htmlType="submit"
                        loading={rbacPermissionsGrantPending}
                        disabled={rbacPermissionsViewMode === 'resource' && !rbacPermissionsList.resource_id}
                      >
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                </Card>

                {rbacPermissionsViewMode === 'resource' && (
                  <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                    <RbacResourceBrowser
                      title="Ресурсы"
                      searchPlaceholder="Search resource"
                      searchValue={rbacPermissionsResourceSearchValue}
                      onSearchChange={setRbacPermissionsResourceSearchValue}
                      options={rbacPermissionsResourceBrowserOptions}
                      selectedValue={rbacPermissionsList.resource_id}
                      onSelect={(id) => {
                        setRbacPermissionsList((prev) => ({ ...prev, resource_id: id, page: 1 }))
                        rbacPermissionsGrantForm.setFieldValue('resource_id', id)
                      }}
                      loading={rbacPermissionsResourceRef.loading}
                      onScroll={(event) => rbacPermissionsResourceRef.onPopupScroll?.(event)}
                      clearLabel="Снять выбор"
                      clearDisabled={!rbacPermissionsList.resource_id}
                      onClear={() => {
                        setRbacPermissionsList((prev) => ({ ...prev, resource_id: undefined, page: 1 }))
                        rbacPermissionsGrantForm.setFieldValue('resource_id', undefined)
                      }}
                    />

                    <Card title="Назначения" size="small" style={{ flex: 1, minWidth: 0 }}>
                      {!rbacPermissionsList.resource_id ? (
                        <Empty description="Выберите ресурс слева" />
                      ) : (
                        <>
                          <Space wrap style={{ marginBottom: 12 }}>
                            <Text>
                              <Text strong>Resource:</Text> {rbacPermissionsSelectedResourceLabel}
                            </Text>

                            <Select
                              style={{ width: 140 }}
                              placeholder="Level"
                              allowClear
                              value={rbacPermissionsList.level}
                              onChange={(value) => setRbacPermissionsList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                              options={LEVEL_OPTIONS}
                            />

                            <Input
                              placeholder="Search"
                              style={{ width: 220 }}
                              value={rbacPermissionsList.search}
                              onChange={(e) => setRbacPermissionsList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                            />

                            <Button
                              onClick={() => rbacPermissionsTableConfig.refetch()}
                              loading={rbacPermissionsTableConfig.fetching}
                            >
                              Refresh
                            </Button>
                          </Space>

                          {Boolean(rbacPermissionsTableConfig.error) && (
                            <Alert
                              type="warning"
                              message="Не удалось загрузить permissions"
                              style={{ marginBottom: 12 }}
                            />
                          )}

                          <Table
                            size="small"
                            columns={rbacPermissionsTableConfig.columns}
                            dataSource={rbacPermissionsTableConfig.rows}
                            loading={rbacPermissionsTableConfig.loading}
                            rowKey={rbacPermissionsTableConfig.rowKey}
                            pagination={{
                              current: rbacPermissionsList.page,
                              pageSize: rbacPermissionsList.pageSize,
                              total: rbacPermissionsTableConfig.total,
                              showSizeChanger: true,
                              onChange: (page, pageSize) => setRbacPermissionsList((prev) => ({ ...prev, page, pageSize })),
                            }}
                          />
                        </>
                      )}
                    </Card>
                  </div>
                )}

                {rbacPermissionsViewMode === 'principal'
                  && rbacPermissionsPrincipalType === 'role'
                  && rbacPermissionsResourceKey === 'clusters' && (
                  <Card title="Bulk Cluster Role Permissions" size="small">
                    <Tabs
                      items={[
                        {
                          key: 'grant',
                          label: 'Bulk Grant',
                          children: (
                            <Form
                              form={rbacPermissionsBulkGrantClusterGroupForm}
                              layout="vertical"
                              onFinish={(values) => {
                                const clusterIds = parseIdListFromText(values.cluster_ids)
                                if (clusterIds.length === 0) {
                                  message.error('cluster_ids required')
                                  return
                                }

                                const roleName = roleNameById.get(values.group_id) ?? String(values.group_id)
                                modal.confirm({
                                  title: 'Подтвердите массовую выдачу доступа (Clusters)',
                                  okText: 'Применить',
                                  cancelText: 'Отмена',
                                  content: (
                                    <Space direction="vertical" size={4}>
                                      <Text><Text strong>Роль:</Text> {roleName} #{values.group_id}</Text>
                                      <Text><Text strong>Уровень:</Text> {values.level}</Text>
                                      {values.notes ? <Text><Text strong>Notes:</Text> {values.notes}</Text> : null}
                                      <Text><Text strong>Количество:</Text> {clusterIds.length}</Text>
                                      <Text type="secondary">
                                        Пример: {clusterIds.slice(0, 5).join(', ')}{clusterIds.length > 5 ? ', ...' : ''}
                                      </Text>
                                    </Space>
                                  ),
                                  onOk: async () => {
                                    try {
                                      const result = await bulkGrantClusterGroup.mutateAsync({
                                        group_id: values.group_id,
                                        cluster_ids: clusterIds,
                                        level: values.level,
                                        notes: values.notes,
                                        reason: values.reason,
                                      })
                                      message.success(`Bulk grant: created=${result.created}, updated=${result.updated}, skipped=${result.skipped}`)
                                      rbacPermissionsBulkGrantClusterGroupForm.resetFields()
                                    } catch (error) {
                                      message.error('Bulk grant failed')
                                      throw error
                                    }
                                  },
                                })
                              }}
                              initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                            >
                              <Space wrap>
                                <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                                  <Select
                                    style={{ width: 240 }}
                                    placeholder="Role"
                                    options={roleOptions}
                                    showSearch
                                    optionFilterProp="label"
                                  />
                                </Form.Item>
                                <Form.Item name="level" rules={[{ required: true }]}>
                                  <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                                </Form.Item>
                                <Form.Item name="notes">
                                  <Input placeholder="Notes (optional)" style={{ width: 260 }} />
                                </Form.Item>
                                <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                                  <Input placeholder="Reason" style={{ width: 320 }} />
                                </Form.Item>
                              </Space>
                              <Form.Item name="cluster_ids" rules={[{ required: true, message: 'cluster_ids required' }]}>
                                <Input.TextArea
                                  placeholder="Cluster UUIDs (one per line)"
                                  autoSize={{ minRows: 3, maxRows: 6 }}
                                />
                              </Form.Item>
                              <Button type="primary" htmlType="submit" loading={bulkGrantClusterGroup.isPending}>
                                Bulk Grant
                              </Button>
                            </Form>
                          ),
                        },
                        {
                          key: 'revoke',
                          label: 'Bulk Revoke',
                          children: (
                            <Form
                              form={rbacPermissionsBulkRevokeClusterGroupForm}
                              layout="vertical"
                              onFinish={(values) => {
                                const clusterIds = parseIdListFromText(values.cluster_ids)
                                if (clusterIds.length === 0) {
                                  message.error('cluster_ids required')
                                  return
                                }

                                const roleName = roleNameById.get(values.group_id) ?? String(values.group_id)
                                modal.confirm({
                                  title: 'Подтвердите массовое снятие доступа (Clusters)',
                                  okText: 'Применить',
                                  cancelText: 'Отмена',
                                  content: (
                                    <Space direction="vertical" size={4}>
                                      <Text><Text strong>Роль:</Text> {roleName} #{values.group_id}</Text>
                                      <Text><Text strong>Количество:</Text> {clusterIds.length}</Text>
                                      <Text type="secondary">
                                        Пример: {clusterIds.slice(0, 5).join(', ')}{clusterIds.length > 5 ? ', ...' : ''}
                                      </Text>
                                    </Space>
                                  ),
                                  onOk: async () => {
                                    try {
                                      const result = await bulkRevokeClusterGroup.mutateAsync({
                                        group_id: values.group_id,
                                        cluster_ids: clusterIds,
                                        reason: values.reason,
                                      })
                                      message.success(`Bulk revoke: deleted=${result.deleted}, skipped=${result.skipped}`)
                                      rbacPermissionsBulkRevokeClusterGroupForm.resetFields()
                                    } catch (error) {
                                      message.error('Bulk revoke failed')
                                      throw error
                                    }
                                  },
                                })
                              }}
                            >
                              <Space wrap>
                                <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                                  <Select
                                    style={{ width: 240 }}
                                    placeholder="Role"
                                    options={roleOptions}
                                    showSearch
                                    optionFilterProp="label"
                                  />
                                </Form.Item>
                                <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                                  <Input placeholder="Reason" style={{ width: 320 }} />
                                </Form.Item>
                              </Space>
                              <Form.Item name="cluster_ids" rules={[{ required: true, message: 'cluster_ids required' }]}>
                                <Input.TextArea
                                  placeholder="Cluster UUIDs (one per line)"
                                  autoSize={{ minRows: 3, maxRows: 6 }}
                                />
                              </Form.Item>
                              <Button type="primary" danger htmlType="submit" loading={bulkRevokeClusterGroup.isPending}>
                                Bulk Revoke
                              </Button>
                            </Form>
                          ),
                        },
                      ]}
                    />
                  </Card>
                )}

                {rbacPermissionsViewMode === 'principal'
                  && rbacPermissionsPrincipalType === 'role'
                  && rbacPermissionsResourceKey === 'databases' && (
                  <Card title="Bulk Database Role Permissions" size="small">
                    <Tabs
                      items={[
                        {
                          key: 'grant',
                          label: 'Bulk Grant',
                          children: (
                            <Form
                              form={rbacPermissionsBulkGrantDatabaseGroupForm}
                              layout="vertical"
                              onFinish={(values) => {
                                const databaseIds = parseIdListFromText(values.database_ids)
                                if (databaseIds.length === 0) {
                                  message.error('database_ids required')
                                  return
                                }

                                const roleName = roleNameById.get(values.group_id) ?? String(values.group_id)
                                modal.confirm({
                                  title: 'Подтвердите массовую выдачу доступа (Databases)',
                                  okText: 'Применить',
                                  cancelText: 'Отмена',
                                  content: (
                                    <Space direction="vertical" size={4}>
                                      <Text><Text strong>Роль:</Text> {roleName} #{values.group_id}</Text>
                                      <Text><Text strong>Уровень:</Text> {values.level}</Text>
                                      {values.notes ? <Text><Text strong>Notes:</Text> {values.notes}</Text> : null}
                                      <Text><Text strong>Количество:</Text> {databaseIds.length}</Text>
                                      <Text type="secondary">
                                        Пример: {databaseIds.slice(0, 5).join(', ')}{databaseIds.length > 5 ? ', ...' : ''}
                                      </Text>
                                    </Space>
                                  ),
                                  onOk: async () => {
                                    try {
                                      const result = await bulkGrantDatabaseGroup.mutateAsync({
                                        group_id: values.group_id,
                                        database_ids: databaseIds,
                                        level: values.level,
                                        notes: values.notes,
                                        reason: values.reason,
                                      })
                                      message.success(`Bulk grant: created=${result.created}, updated=${result.updated}, skipped=${result.skipped}`)
                                      rbacPermissionsBulkGrantDatabaseGroupForm.resetFields()
                                    } catch (error) {
                                      message.error('Bulk grant failed')
                                      throw error
                                    }
                                  },
                                })
                              }}
                              initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                            >
                              <Space wrap>
                                <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                                  <Select
                                    style={{ width: 240 }}
                                    placeholder="Role"
                                    options={roleOptions}
                                    showSearch
                                    optionFilterProp="label"
                                  />
                                </Form.Item>
                                <Form.Item name="level" rules={[{ required: true }]}>
                                  <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                                </Form.Item>
                                <Form.Item name="notes">
                                  <Input placeholder="Notes (optional)" style={{ width: 260 }} />
                                </Form.Item>
                                <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                                  <Input placeholder="Reason" style={{ width: 320 }} />
                                </Form.Item>
                              </Space>
                              <Form.Item name="database_ids" rules={[{ required: true, message: 'database_ids required' }]}>
                                <Input.TextArea
                                  placeholder="Database IDs (one per line)"
                                  autoSize={{ minRows: 3, maxRows: 8 }}
                                />
                              </Form.Item>
                              <Button type="primary" htmlType="submit" loading={bulkGrantDatabaseGroup.isPending}>
                                Bulk Grant
                              </Button>
                            </Form>
                          ),
                        },
                        {
                          key: 'revoke',
                          label: 'Bulk Revoke',
                          children: (
                            <Form
                              form={rbacPermissionsBulkRevokeDatabaseGroupForm}
                              layout="vertical"
                              onFinish={(values) => {
                                const databaseIds = parseIdListFromText(values.database_ids)
                                if (databaseIds.length === 0) {
                                  message.error('database_ids required')
                                  return
                                }

                                const roleName = roleNameById.get(values.group_id) ?? String(values.group_id)
                                modal.confirm({
                                  title: 'Подтвердите массовое снятие доступа (Databases)',
                                  okText: 'Применить',
                                  cancelText: 'Отмена',
                                  content: (
                                    <Space direction="vertical" size={4}>
                                      <Text><Text strong>Роль:</Text> {roleName} #{values.group_id}</Text>
                                      <Text><Text strong>Количество:</Text> {databaseIds.length}</Text>
                                      <Text type="secondary">
                                        Пример: {databaseIds.slice(0, 5).join(', ')}{databaseIds.length > 5 ? ', ...' : ''}
                                      </Text>
                                    </Space>
                                  ),
                                  onOk: async () => {
                                    try {
                                      const result = await bulkRevokeDatabaseGroup.mutateAsync({
                                        group_id: values.group_id,
                                        database_ids: databaseIds,
                                        reason: values.reason,
                                      })
                                      message.success(`Bulk revoke: deleted=${result.deleted}, skipped=${result.skipped}`)
                                      rbacPermissionsBulkRevokeDatabaseGroupForm.resetFields()
                                    } catch (error) {
                                      message.error('Bulk revoke failed')
                                      throw error
                                    }
                                  },
                                })
                              }}
                            >
                              <Space wrap>
                                <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                                  <Select
                                    style={{ width: 240 }}
                                    placeholder="Role"
                                    options={roleOptions}
                                    showSearch
                                    optionFilterProp="label"
                                  />
                                </Form.Item>
                                <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                                  <Input placeholder="Reason" style={{ width: 320 }} />
                                </Form.Item>
                              </Space>
                              <Form.Item name="database_ids" rules={[{ required: true, message: 'database_ids required' }]}>
                                <Input.TextArea
                                  placeholder="Database IDs (one per line)"
                                  autoSize={{ minRows: 3, maxRows: 8 }}
                                />
                              </Form.Item>
                              <Button type="primary" danger htmlType="submit" loading={bulkRevokeDatabaseGroup.isPending}>
                                Bulk Revoke
                              </Button>
                            </Form>
                          ),
                        },
                      ]}
                    />
                  </Card>
                )}

                {rbacPermissionsViewMode === 'principal' && (
                  <Card title="Permissions" size="small">
                    <Space wrap style={{ marginBottom: 12 }}>
                      {rbacPermissionsPrincipalType === 'user' ? (
                        <Select
                          style={{ width: 240 }}
                          placeholder="User"
                          allowClear
                          showSearch
                          filterOption={false}
                          onSearch={setUserSearch}
                          value={rbacPermissionsList.principal_id}
                          onChange={(value) => setRbacPermissionsList((prev) => ({ ...prev, principal_id: value ?? undefined, page: 1 }))}
                          options={userOptions}
                          loading={usersQuery.isFetching}
                        />
                      ) : (
                        <Select
                          style={{ width: 240 }}
                          placeholder="Role"
                          allowClear
                          value={rbacPermissionsList.principal_id}
                          onChange={(value) => setRbacPermissionsList((prev) => ({ ...prev, principal_id: value ?? undefined, page: 1 }))}
                          options={roleOptions}
                          showSearch
                          optionFilterProp="label"
                        />
                      )}

                      <Select
                        style={{ width: 360 }}
                        placeholder="Resource"
                        allowClear
                        value={rbacPermissionsList.resource_id}
                        onChange={(value) => setRbacPermissionsList((prev) => ({ ...prev, resource_id: value ?? undefined, page: 1 }))}
                        showSearch={rbacPermissionsResourceRef.showSearch}
                        optionFilterProp="label"
                        filterOption={rbacPermissionsResourceRef.filterOption}
                        onSearch={rbacPermissionsResourceRef.filterOption ? undefined : rbacPermissionsResourceRef.onSearch}
                        onPopupScroll={rbacPermissionsResourceRef.filterOption ? undefined : rbacPermissionsResourceRef.onPopupScroll}
                        options={rbacPermissionsResourceRef.options}
                        loading={rbacPermissionsResourceRef.loading}
                      />

                      <Select
                        style={{ width: 140 }}
                        placeholder="Level"
                        allowClear
                        value={rbacPermissionsList.level}
                        onChange={(value) => setRbacPermissionsList((prev) => ({ ...prev, level: value ?? undefined, page: 1 }))}
                        options={LEVEL_OPTIONS}
                      />

                      <Input
                        placeholder="Search"
                        style={{ width: 220 }}
                        value={rbacPermissionsList.search}
                        onChange={(e) => setRbacPermissionsList((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                      />

                      <Button
                        onClick={() => rbacPermissionsTableConfig.refetch()}
                        loading={rbacPermissionsTableConfig.fetching}
                      >
                        Refresh
                      </Button>
                    </Space>

                    {Boolean(rbacPermissionsTableConfig.error) && (
                      <Alert
                        type="warning"
                        message="Не удалось загрузить permissions"
                        style={{ marginBottom: 12 }}
                      />
                    )}

                    <Table
                      size="small"
                      columns={rbacPermissionsTableConfig.columns}
                      dataSource={rbacPermissionsTableConfig.rows}
                      loading={rbacPermissionsTableConfig.loading}
                      rowKey={rbacPermissionsTableConfig.rowKey}
                      pagination={{
                        current: rbacPermissionsList.page,
                        pageSize: rbacPermissionsList.pageSize,
                        total: rbacPermissionsTableConfig.total,
                        showSizeChanger: true,
                        onChange: (page, pageSize) => setRbacPermissionsList((prev) => ({ ...prev, page, pageSize })),
                      }}
                    />
                  </Card>
                )}
              </Space>
            ),
          },
          {
            key: 'user-roles',
            label: 'Роли пользователей',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Assign Roles to User" size="small">
                  <Form
                    form={assignRolesForm}
                    layout="inline"
                    initialValues={{ mode: 'replace' satisfies 'replace' | 'add' | 'remove' }}
                    onFinish={(values) => {
                      setSelectedRolesUserId(values.user_id)
                      setUserRoles.mutate(values)
                    }}
                  >
                    <Form.Item name="user_id" rules={[{ required: true, message: 'user required' }]}>
                      <Select
                        style={{ width: 220 }}
                        placeholder="User"
                        allowClear
                        showSearch
                        filterOption={false}
                        onSearch={setUserSearch}
                        onChange={(value) => setSelectedRolesUserId(value)}
                        options={userOptions}
                        loading={usersQuery.isFetching}
                      />
                    </Form.Item>
                    <Form.Item name="group_ids" rules={[{ required: true, message: 'roles required' }]}>
                      <Select
                        style={{ width: 320 }}
                        placeholder="Roles"
                        mode="multiple"
                        options={roleOptions}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="mode">
                      <Select
                        style={{ width: 140 }}
                        options={[
                          { label: 'Replace', value: 'replace' },
                          { label: 'Add', value: 'add' },
                          { label: 'Remove', value: 'remove' },
                        ]}
                      />
                    </Form.Item>
                    <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                      <Input placeholder="Reason" style={{ width: 320 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={setUserRoles.isPending}>
                        Apply
                      </Button>
                    </Form.Item>
                  </Form>

                  {selectedRolesUserId && (
                    <div style={{ marginTop: 12 }}>
                      <Text type="secondary">Current roles:</Text>{' '}
                      <Space size="small" wrap>
                        {(userRolesQuery.data?.roles ?? []).length > 0
                          ? (userRolesQuery.data?.roles ?? []).map((role) => <Tag key={role.id}>{role.name}</Tag>)
                          : <Tag color="default">-</Tag>}
                      </Space>
                    </div>
                  )}
                </Card>
              </Space>
            ),
          },
          {
            key: 'effective-access',
            label: 'Effective access',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Effective access preview" size="small">
                  <Space wrap align="start">
                    <Select
                      style={{ width: 260 }}
                      placeholder="User"
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

                    <Space>
                      <Text>Clusters</Text>
                      <Switch
                        checked={effectiveIncludeClusters}
                        onChange={(checked) => setEffectiveIncludeClusters(checked)}
                      />
                    </Space>
                    <Space>
                      <Text>Databases</Text>
                      <Switch
                        checked={effectiveIncludeDatabases}
                        onChange={(checked) => {
                          setEffectiveIncludeDatabases(checked)
                          setEffectiveDbPage(1)
                        }}
                      />
                    </Space>
                    <Space>
                      <Text>Operation templates</Text>
                      <Switch
                        checked={effectiveIncludeOperationTemplates}
                        onChange={(checked) => setEffectiveIncludeOperationTemplates(checked)}
                      />
                    </Space>
                    <Space>
                      <Text>Workflow templates</Text>
                      <Switch
                        checked={effectiveIncludeWorkflowTemplates}
                        onChange={(checked) => setEffectiveIncludeWorkflowTemplates(checked)}
                      />
                    </Space>
                    <Space>
                      <Text>Artifacts</Text>
                      <Switch
                        checked={effectiveIncludeArtifacts}
                        onChange={(checked) => setEffectiveIncludeArtifacts(checked)}
                      />
                    </Space>

                    <Button
                      onClick={() => effectiveAccessQuery.refetch()}
                      loading={effectiveAccessQuery.isFetching}
                      disabled={!selectedEffectiveUserId}
                    >
                      Refresh
                    </Button>
                  </Space>

                  {!selectedEffectiveUserId && (
                    <Alert
                      style={{ marginTop: 12 }}
                      type="info"
                      message="Выберите пользователя для preview"
                      description="Показывает итоговый доступ с учётом direct/group/inherited (cluster) источников."
                    />
                  )}

                  {effectiveAccessQuery.error && selectedEffectiveUserId && (
                    <Alert
                      style={{ marginTop: 12 }}
                      type="warning"
                      message="Не удалось загрузить effective access"
                    />
                  )}
                </Card>

                {selectedEffectiveUserId && (
                  <>
                    {effectiveIncludeClusters && (
                      <Card title={`Clusters (${effectiveAccessQuery.data?.clusters?.length ?? 0})`} size="small">
                        <Table
                          size="small"
                          rowKey={(row) => row.cluster.id}
                          columns={effectiveClustersColumns}
                          dataSource={effectiveAccessQuery.data?.clusters ?? []}
                          loading={effectiveAccessQuery.isFetching}
                          pagination={{ pageSize: 50 }}
                        />
                      </Card>
                    )}

                    {effectiveIncludeDatabases && (
                      <Card title="Databases" size="small">
                        <Table
                          size="small"
                          rowKey={(row) => row.database.id}
                          columns={effectiveDatabasesColumns}
                          dataSource={effectiveAccessQuery.data?.databases ?? []}
                          loading={effectiveAccessQuery.isFetching}
                          pagination={{
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
                          }}
                        />
                      </Card>
                    )}

                    {effectiveIncludeOperationTemplates && (
                      <Card title="Operation templates" size="small">
                        <Table
                          size="small"
                          rowKey={(row) => row.template.id}
                          columns={effectiveOperationTemplatesColumns}
                          dataSource={effectiveAccessQuery.data?.operation_templates ?? []}
                          loading={effectiveAccessQuery.isFetching}
                          pagination={{ pageSize: 50 }}
                        />
                      </Card>
                    )}

                    {effectiveIncludeWorkflowTemplates && (
                      <Card title="Workflow templates" size="small">
                        <Table
                          size="small"
                          rowKey={(row) => row.template.id}
                          columns={effectiveWorkflowTemplatesColumns}
                          dataSource={effectiveAccessQuery.data?.workflow_templates ?? []}
                          loading={effectiveAccessQuery.isFetching}
                          pagination={{ pageSize: 50 }}
                        />
                      </Card>
                    )}

                    {effectiveIncludeArtifacts && (
                      <Card title="Artifacts" size="small">
                        <Table
                          size="small"
                          rowKey={(row) => row.artifact.id}
                          columns={effectiveArtifactsColumns}
                          dataSource={effectiveAccessQuery.data?.artifacts ?? []}
                          loading={effectiveAccessQuery.isFetching}
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
                {levelsHintClustersDatabases}
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
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
                  )}
                </Card>

                <Card title="Cluster Permissions" size="small">
                  {clusterPermissionsQuery.error && (
                    <Alert
                      type="warning"
                      message="Не удалось загрузить permissions"
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
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
                  )}
                </Card>

                <Card title="Bulk Cluster Permission (Role)" size="small">
                  <Tabs
                    items={[
                      {
                        key: 'grant',
                        label: 'Bulk Grant',
                        children: (
                          <Form
                            form={bulkGrantClusterGroupForm}
                            layout="vertical"
                            onFinish={async (values) => {
                              const clusterIds = parseIdListFromText(values.cluster_ids)
                              if (clusterIds.length === 0) {
                                message.error('cluster_ids required')
                                return
                              }
                              try {
                                const result = await bulkGrantClusterGroup.mutateAsync({
                                  group_id: values.group_id,
                                  cluster_ids: clusterIds,
                                  level: values.level,
                                  notes: values.notes,
                                  reason: values.reason,
                                })
                                message.success(`Bulk grant: created=${result.created}, updated=${result.updated}, skipped=${result.skipped}`)
                                bulkGrantClusterGroupForm.resetFields()
                              } catch {
                                message.error('Bulk grant failed')
                              }
                            }}
                            initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                          >
                            <Space wrap>
                              <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                                <Select
                                  style={{ width: 240 }}
                                  placeholder="Role"
                                  options={roleOptions}
                                  showSearch
                                  optionFilterProp="label"
                                />
                              </Form.Item>
                              <Form.Item name="level" rules={[{ required: true }]}>
                                <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                              </Form.Item>
                              <Form.Item name="notes">
                                <Input placeholder="Notes (optional)" style={{ width: 260 }} />
                              </Form.Item>
                              <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                                <Input placeholder="Reason" style={{ width: 320 }} />
                              </Form.Item>
                            </Space>
                            <Form.Item name="cluster_ids" rules={[{ required: true, message: 'cluster_ids required' }]}>
                              <Input.TextArea
                                placeholder="Cluster UUIDs (one per line)"
                                autoSize={{ minRows: 3, maxRows: 6 }}
                              />
                            </Form.Item>
                            <Button type="primary" htmlType="submit" loading={bulkGrantClusterGroup.isPending}>
                              Bulk Grant
                            </Button>
                          </Form>
                        ),
                      },
                      {
                        key: 'revoke',
                        label: 'Bulk Revoke',
                        children: (
                          <Form
                            form={bulkRevokeClusterGroupForm}
                            layout="vertical"
                            onFinish={async (values) => {
                              const clusterIds = parseIdListFromText(values.cluster_ids)
                              if (clusterIds.length === 0) {
                                message.error('cluster_ids required')
                                return
                              }
                              try {
                                const result = await bulkRevokeClusterGroup.mutateAsync({
                                  group_id: values.group_id,
                                  cluster_ids: clusterIds,
                                  reason: values.reason,
                                })
                                message.success(`Bulk revoke: deleted=${result.deleted}, skipped=${result.skipped}`)
                                bulkRevokeClusterGroupForm.resetFields()
                              } catch {
                                message.error('Bulk revoke failed')
                              }
                            }}
                          >
                            <Space wrap>
                              <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                                <Select
                                  style={{ width: 240 }}
                                  placeholder="Role"
                                  options={roleOptions}
                                  showSearch
                                  optionFilterProp="label"
                                />
                              </Form.Item>
                              <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                                <Input placeholder="Reason" style={{ width: 320 }} />
                              </Form.Item>
                            </Space>
                            <Form.Item name="cluster_ids" rules={[{ required: true, message: 'cluster_ids required' }]}>
                              <Input.TextArea
                                placeholder="Cluster UUIDs (one per line)"
                                autoSize={{ minRows: 3, maxRows: 6 }}
                              />
                            </Form.Item>
                            <Button type="primary" danger htmlType="submit" loading={bulkRevokeClusterGroup.isPending}>
                              Bulk Revoke
                            </Button>
                          </Form>
                        ),
                      },
                    ]}
                  />
                </Card>

                <Card title="Cluster Permissions (Role)" size="small">
                  <Space wrap style={{ marginBottom: 12 }}>
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
                  </Space>
                  <Table
                    size="small"
                    columns={clusterGroupColumns}
                    dataSource={clusterGroupPermissions}
                    loading={clusterGroupPermissionsQuery.isLoading}
                    rowKey={(row) => `${row.group.id}:${row.cluster.id}`}
                    pagination={{
                      current: clusterGroupList.page,
                      pageSize: clusterGroupList.pageSize,
                      total: totalClusterGroupPermissions,
                      showSizeChanger: true,
                      onChange: (page, pageSize) => setClusterGroupList((prev) => ({ ...prev, page, pageSize })),
                    }}
                  />
                </Card>
              </Space>
            ),
          },
          {
            key: 'databases',
            label: 'Database Permissions',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                {levelsHintClustersDatabases}
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
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
                  )}
                </Card>

                <Card title="Database Permissions" size="small">
                  {databasePermissionsQuery.error && (
                    <Alert
                      type="warning"
                      message="Не удалось загрузить permissions"
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
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
                  )}
                </Card>

                <Card title="Bulk Database Permission (Role)" size="small">
                  <Tabs
                    items={[
                      {
                        key: 'grant',
                        label: 'Bulk Grant',
                        children: (
                          <Form
                            form={bulkGrantDatabaseGroupForm}
                            layout="vertical"
                            onFinish={async (values) => {
                              const databaseIds = parseIdListFromText(values.database_ids)
                              if (databaseIds.length === 0) {
                                message.error('database_ids required')
                                return
                              }
                              try {
                                const result = await bulkGrantDatabaseGroup.mutateAsync({
                                  group_id: values.group_id,
                                  database_ids: databaseIds,
                                  level: values.level,
                                  notes: values.notes,
                                  reason: values.reason,
                                })
                                message.success(`Bulk grant: created=${result.created}, updated=${result.updated}, skipped=${result.skipped}`)
                                bulkGrantDatabaseGroupForm.resetFields()
                              } catch {
                                message.error('Bulk grant failed')
                              }
                            }}
                            initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                          >
                            <Space wrap>
                              <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                                <Select
                                  style={{ width: 240 }}
                                  placeholder="Role"
                                  options={roleOptions}
                                  showSearch
                                  optionFilterProp="label"
                                />
                              </Form.Item>
                              <Form.Item name="level" rules={[{ required: true }]}>
                                <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                              </Form.Item>
                              <Form.Item name="notes">
                                <Input placeholder="Notes (optional)" style={{ width: 260 }} />
                              </Form.Item>
                              <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                                <Input placeholder="Reason" style={{ width: 320 }} />
                              </Form.Item>
                            </Space>
                            <Form.Item name="database_ids" rules={[{ required: true, message: 'database_ids required' }]}>
                              <Input.TextArea
                                placeholder="Database IDs (one per line)"
                                autoSize={{ minRows: 3, maxRows: 8 }}
                              />
                            </Form.Item>
                            <Button type="primary" htmlType="submit" loading={bulkGrantDatabaseGroup.isPending}>
                              Bulk Grant
                            </Button>
                          </Form>
                        ),
                      },
                      {
                        key: 'revoke',
                        label: 'Bulk Revoke',
                        children: (
                          <Form
                            form={bulkRevokeDatabaseGroupForm}
                            layout="vertical"
                            onFinish={async (values) => {
                              const databaseIds = parseIdListFromText(values.database_ids)
                              if (databaseIds.length === 0) {
                                message.error('database_ids required')
                                return
                              }
                              try {
                                const result = await bulkRevokeDatabaseGroup.mutateAsync({
                                  group_id: values.group_id,
                                  database_ids: databaseIds,
                                  reason: values.reason,
                                })
                                message.success(`Bulk revoke: deleted=${result.deleted}, skipped=${result.skipped}`)
                                bulkRevokeDatabaseGroupForm.resetFields()
                              } catch {
                                message.error('Bulk revoke failed')
                              }
                            }}
                          >
                            <Space wrap>
                              <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                                <Select
                                  style={{ width: 240 }}
                                  placeholder="Role"
                                  options={roleOptions}
                                  showSearch
                                  optionFilterProp="label"
                                />
                              </Form.Item>
                              <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                                <Input placeholder="Reason" style={{ width: 320 }} />
                              </Form.Item>
                            </Space>
                            <Form.Item name="database_ids" rules={[{ required: true, message: 'database_ids required' }]}>
                              <Input.TextArea
                                placeholder="Database IDs (one per line)"
                                autoSize={{ minRows: 3, maxRows: 8 }}
                              />
                            </Form.Item>
                            <Button type="primary" danger htmlType="submit" loading={bulkRevokeDatabaseGroup.isPending}>
                              Bulk Revoke
                            </Button>
                          </Form>
                        ),
                      },
                    ]}
                  />
                </Card>

                <Card title="Database Permissions (Role)" size="small">
                  <Space wrap style={{ marginBottom: 12 }}>
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
                  </Space>
                  <Table
                    size="small"
                    columns={databaseGroupColumns}
                    dataSource={databaseGroupPermissions}
                    loading={databaseGroupPermissionsQuery.isLoading}
                    rowKey={(row) => `${row.group.id}:${row.database.id}`}
                    pagination={{
                      current: databaseGroupList.page,
                      pageSize: databaseGroupList.pageSize,
                      total: totalDatabaseGroupPermissions,
                      showSizeChanger: true,
                      onChange: (page, pageSize) => setDatabaseGroupList((prev) => ({ ...prev, page, pageSize })),
                    }}
                  />
                </Card>
              </Space>
            ),
          },
          {
            key: 'operation-templates',
            label: 'Operation Templates',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                {levelsHintTemplatesWorkflows}
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
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
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
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
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
                {levelsHintTemplatesWorkflows}
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
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
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
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
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
                {levelsHintArtifacts}
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
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
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
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
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
            label: 'Audit',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Admin Audit" size="small">
                  <Space wrap style={{ marginBottom: 12 }}>
                    <Input
                      placeholder="Search"
                      style={{ width: 320 }}
                      value={auditSearch}
                      onChange={(e) => {
                        setAuditSearch(e.target.value)
                        setAuditPage(1)
                      }}
                    />
                    <Button onClick={() => auditQuery.refetch()} loading={auditQuery.isFetching}>
                      Refresh
                    </Button>
                  </Space>
                  <Table
                    size="small"
                    columns={auditColumns}
                    dataSource={auditItems}
                    loading={auditQuery.isLoading}
                    rowKey="id"
                    pagination={{
                      current: auditPage,
                      pageSize: auditPageSize,
                      total: totalAuditItems,
                      showSizeChanger: true,
                      onChange: (page, pageSize) => {
                        setAuditPage(page)
                        setAuditPageSize(pageSize)
                      },
                    }}
                  />
                </Card>
              </Space>
            ),
          },
          ...(isStaff ? [
            {
              key: 'ib-users',
              label: 'Infobase Users',
              children: (
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  <Card title="Infobase Users" size="small">
                    {!selectedIbDatabaseId && (
                      <Alert
                        type="info"
                        message="Select a database to view infobase users"
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
                      searchPlaceholder="Search infobase users"
                      toolbarActions={(
                        <Space>
                          <Select
                            style={{ width: 320 }}
                            placeholder="Database"
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
                              { label: 'Auth: Any', value: 'any' },
                              { label: 'Auth: Local', value: 'local' },
                              { label: 'Auth: AD', value: 'ad' },
                              { label: 'Auth: Service', value: 'service' },
                              { label: 'Auth: Other', value: 'other' },
                            ]}
                          />
                          <Select
                            style={{ width: 160 }}
                            value={ibServiceFilter}
                            onChange={setIbServiceFilter}
                            options={[
                              { label: 'Service: Any', value: 'any' },
                              { label: 'Service: Yes', value: 'true' },
                              { label: 'Service: No', value: 'false' },
                            ]}
                          />
                          <Select
                            style={{ width: 160 }}
                            value={ibHasUserFilter}
                            onChange={setIbHasUserFilter}
                            options={[
                              { label: 'CC User: Any', value: 'any' },
                              { label: 'CC User: Linked', value: 'true' },
                              { label: 'CC User: Unlinked', value: 'false' },
                            ]}
                          />
                          <Button
                            onClick={() => ibUsersQuery.refetch()}
                            disabled={!selectedIbDatabaseId}
                            loading={ibUsersQuery.isFetching}
                          >
                            Refresh
                          </Button>
                        </Space>
                      )}
                    />
                  </Card>

                  <Card title={editingIbUser ? 'Edit Infobase User' : 'Add Infobase User'} size="small">
                    <Form
                      form={ibUserForm}
                      layout="vertical"
                      initialValues={{ auth_type: 'local', is_service: false }}
                    >
                      <Space size="large" align="start" wrap>
                        <Form.Item
                          label="Database"
                          name="database_id"
                          rules={[{ required: true, message: 'database_id required' }]}
                        >
                          <Select
                            style={{ width: 320 }}
                            placeholder="Database"
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
                          label="IB Username"
                          name="ib_username"
                          rules={[{ required: true, message: 'ib_username required' }]}
                        >
                          <Input placeholder="ib_user" />
                        </Form.Item>
                        <Form.Item label="IB Display Name" name="ib_display_name">
                          <Input placeholder="Display name" />
                        </Form.Item>
                        <Form.Item label="CC User" name="user_id">
                          <Select
                            showSearch
                            allowClear
                            placeholder="Select user"
                            filterOption={false}
                            onSearch={(value) => setUserSearch(value)}
                            options={userOptions}
                            loading={usersQuery.isFetching}
                            style={{ width: 220 }}
                          />
                        </Form.Item>
                        <Form.Item label="Auth Type" name="auth_type">
                          <Select
                            style={{ width: 160 }}
                            options={[
                              { label: 'Local', value: 'local' },
                              { label: 'AD', value: 'ad' },
                              { label: 'Service', value: 'service' },
                              { label: 'Other', value: 'other' },
                            ]}
                          />
                        </Form.Item>
                        <Form.Item label="Service Account" name="is_service" valuePropName="checked">
                          <Switch />
                        </Form.Item>
                      </Space>
                      <Form.Item label="Roles" name="ib_roles">
                        <Select mode="tags" tokenSeparators={[',']} placeholder="Roles (comma separated)" />
                      </Form.Item>
                      <Form.Item
                        label={editingIbUser ? 'New IB Password' : 'IB Password'}
                        name="ib_password"
                        help={(
                          <Space size="small">
                            {editingIbUser ? (
                              <span>Use Update Password to apply changes.</span>
                            ) : (
                              <span>Set password during creation (optional).</span>
                            )}
                            <Tag color={editingIbUser?.ib_password_configured ? 'green' : 'default'}>
                              {editingIbUser?.ib_password_configured ? 'Configured' : 'Missing'}
                            </Tag>
                          </Space>
                        )}
                      >
                        <Input.Password placeholder="Enter password" />
                      </Form.Item>
                      <Form.Item label="Notes" name="notes">
                        <Input placeholder="Optional notes" />
                      </Form.Item>
                      <Space>
                        <Button
                          type="primary"
                          onClick={handleIbUserSave}
                          loading={createInfobaseUser.isPending || updateInfobaseUser.isPending}
                        >
                          {editingIbUser ? 'Update' : 'Add'}
                        </Button>
                        {editingIbUser && (
                          <Button
                            onClick={handleIbUserPasswordUpdate}
                            loading={setInfobaseUserPassword.isPending}
                          >
                            Update Password
                          </Button>
                        )}
                        {editingIbUser && (
                          <Button
                            danger
                            onClick={handleIbUserPasswordReset}
                            loading={resetInfobaseUserPassword.isPending}
                          >
                            Reset Password
                          </Button>
                        )}
                        {editingIbUser && (
                          <Button onClick={handleIbUserResetForm}>Cancel edit</Button>
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
              <Tag>Users: {selectedRoleForUsage.users_count}</Tag>
              <Tag>Capabilities: {selectedRoleForUsage.permissions_count}</Tag>
            </Space>

            <div>
              <Text strong>Назначения (bindings):</Text>
              <Space wrap style={{ marginTop: 8 }}>
                <Tag>Clusters: {roleUsageTotals.clusters}</Tag>
                <Tag>Databases: {roleUsageTotals.databases}</Tag>
                <Tag>Operation templates: {roleUsageTotals.operationTemplates}</Tag>
                <Tag>Workflow templates: {roleUsageTotals.workflowTemplates}</Tag>
                <Tag>Artifacts: {roleUsageTotals.artifacts}</Tag>
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

      <Modal
        title="Clone role"
        open={cloneRoleOpen}
        okText="Create"
        onCancel={() => {
          setCloneRoleOpen(false)
          setCloneRoleSourceRoleId(null)
        }}
        okButtonProps={{
          disabled: !cloneRoleSourceRoleId || !cloneRoleName.trim() || !cloneRoleReason.trim(),
          loading: createRole.isPending || setRoleCapabilities.isPending,
        }}
        onOk={async () => {
          if (!cloneRoleSourceRoleId) return
          const source = roles.find((role) => role.id === cloneRoleSourceRoleId)
          if (!source) {
            message.error('Source role not found')
            return
          }
          const name = cloneRoleName.trim()
          const reason = cloneRoleReason.trim()
          if (!name || !reason) {
            message.error('Name and reason are required')
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
            message.success(`Role cloned: ${created.name} #${created.id}`)
            setCloneRoleOpen(false)
            setCloneRoleSourceRoleId(null)
          } catch {
            message.error('Clone failed')
          }
        }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Alert
            type="info"
            message={cloneRoleSourceRoleId ? `Source role id: ${cloneRoleSourceRoleId}` : 'Select source role'}
          />
          <Input
            placeholder="New role name"
            value={cloneRoleName}
            onChange={(e) => setCloneRoleName(e.target.value)}
          />
          <Input
            placeholder="Reason (required)"
            value={cloneRoleReason}
            onChange={(e) => setCloneRoleReason(e.target.value)}
          />
        </Space>
      </Modal>

      <Modal
        title={selectedRoleForEditor ? `Role capabilities: ${selectedRoleForEditor.name}` : 'Role capabilities'}
        open={roleEditorOpen}
        okText="Save"
        onCancel={() => setRoleEditorOpen(false)}
        okButtonProps={{
          disabled: !roleEditorRoleId || !roleEditorReason.trim(),
          loading: setRoleCapabilities.isPending,
        }}
        onOk={async () => {
          if (!roleEditorRoleId) return
          const reason = roleEditorReason.trim()
          if (!reason) {
            message.error('Reason is required')
            return
          }
          await setRoleCapabilities.mutateAsync({
            group_id: roleEditorRoleId,
            permission_codes: roleEditorPermissionCodes,
            mode: 'replace',
            reason,
          })
          setRoleEditorOpen(false)
        }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Select
            mode="multiple"
            style={{ width: '100%' }}
            placeholder="Capabilities"
            options={capabilityOptions}
            value={roleEditorPermissionCodes}
            onChange={(value) => setRoleEditorPermissionCodes(value)}
            showSearch
            optionFilterProp="label"
          />
          <Input
            placeholder="Reason (required)"
            value={roleEditorReason}
            onChange={(e) => setRoleEditorReason(e.target.value)}
          />
        </Space>
      </Modal>

      <Modal
        title="Rename role"
        open={renameRoleOpen}
        okText="Save"
        onCancel={() => setRenameRoleOpen(false)}
        okButtonProps={{
          disabled: !renameRoleRoleId || !renameRoleName.trim() || !renameRoleReason.trim(),
          loading: updateRole.isPending,
        }}
        onOk={async () => {
          if (!renameRoleRoleId) return
          const name = renameRoleName.trim()
          const reason = renameRoleReason.trim()
          if (!name || !reason) {
            message.error('Name and reason are required')
            return
          }
          await updateRole.mutateAsync({ group_id: renameRoleRoleId, name, reason })
          setRenameRoleOpen(false)
        }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Input placeholder="Role name" value={renameRoleName} onChange={(e) => setRenameRoleName(e.target.value)} />
          <Input placeholder="Reason (required)" value={renameRoleReason} onChange={(e) => setRenameRoleReason(e.target.value)} />
        </Space>
      </Modal>

      <Modal
        title="Delete role"
        open={deleteRoleOpen}
        okText="Delete"
        okButtonProps={{ danger: true, disabled: !deleteRoleRoleId || !deleteRoleReason.trim(), loading: deleteRole.isPending }}
        onCancel={() => setDeleteRoleOpen(false)}
        onOk={async () => {
          if (!deleteRoleRoleId) return
          const reason = deleteRoleReason.trim()
          if (!reason) {
            message.error('Reason is required')
            return
          }
          await deleteRole.mutateAsync({ group_id: deleteRoleRoleId, reason })
          setDeleteRoleOpen(false)
        }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Alert
            type="warning"
            message="Role будет удалена, если нет участников/perms/bindings."
          />
          <Input placeholder="Reason (required)" value={deleteRoleReason} onChange={(e) => setDeleteRoleReason(e.target.value)} />
        </Space>
      </Modal>
    </div>
  )
}
