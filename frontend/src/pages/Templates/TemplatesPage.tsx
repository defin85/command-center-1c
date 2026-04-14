import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  Alert,
  App,
  Button,
  Descriptions,
  Form,
  Grid,
  Input,
  Pagination,
  Popconfirm,
  Space,
  Switch,
  Tag,
  Typography,
} from 'antd'

import {
  type OperationCatalogExposure,
  listOperationCatalogExposures,
  validateOperationCatalogExposure,
} from '../../api/operationCatalog'
import {
  type OperationTemplate,
  buildTemplateOperationCatalogUpsertPayload,
  useCreateTemplate,
  useDeleteTemplate,
  usePoolRuntimeRegistryInspect,
  useSyncTemplatesFromRegistry,
  useUpdateTemplate,
} from '../../api/queries/templates'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import {
  areRouteTableFiltersEqual,
  parseRouteTableFilters,
  parseRouteTableSort,
  serializeRouteTableFilters,
  serializeRouteTableSort,
} from '../../components/table/routeState'
import { useAuthz } from '../../authz/useAuthz'
import { isPlainObject } from '../Settings/actionCatalogUtils'
import type { ActionFormValues } from '../Settings/actionCatalogTypes'
import {
  EntityDetails,
  EntityList,
  JsonBlock,
  MasterDetailShell,
  PageHeader,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import { useLocaleFormatters, useTemplatesTranslation } from '../../i18n'
import {
  type ModalValidationIssue,
  type TemplateModalProvenance,
} from '../Settings/actionCatalog/OperationExposureEditorModal'
import { TemplateOperationExposureEditorModal } from './TemplateOperationExposureEditorModal'
import { buildTemplateEditorValues, buildTemplateWritePayloadFromEditor } from './templateEditorAdapter'

const { Text } = Typography
const { useBreakpoint } = Grid

type TemplateRow = OperationTemplate & {
  status: string
}

type TemplateComposeMode = 'create' | 'edit' | null

const TEMPLATE_EDITOR_FIELD_PATHS: Array<Array<string>> = [
  ['id'],
  ['name'],
  ['description'],
  ['capability'],
  ['is_active'],
  ['executor', 'kind'],
  ['executor', 'command_id'],
  ['executor', 'workflow_id'],
  ['executor', 'mode'],
  ['executor', 'params_json'],
  ['executor', 'additional_args'],
  ['executor', 'stdin'],
  ['executor', 'target_binding_extension_name_param'],
  ['executor', 'fixed'],
  ['executor', 'fixed', 'confirm_dangerous'],
  ['executor', 'fixed', 'timeout_seconds'],
]

const normalizeText = (value: unknown): string => (
  typeof value === 'string' ? value.trim() : ''
)

const hasRouteFilterValue = (value: unknown): boolean => {
  if (value === null || value === undefined) {
    return false
  }
  if (typeof value === 'string') {
    return value.trim().length > 0
  }
  if (Array.isArray(value)) {
    return value.length > 0
  }
  return typeof value === 'number' || typeof value === 'boolean'
}

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

const parseComposeMode = (value: string | null): TemplateComposeMode => {
  if (value === 'create' || value === 'edit') {
    return value
  }
  return null
}

const buildCatalogButtonStyle = (selected: boolean) => ({
  width: '100%',
  justifyContent: 'flex-start',
  height: 'auto',
  paddingBlock: 12,
  paddingInline: 12,
  borderRadius: 8,
  border: selected ? '1px solid #91caff' : '1px solid #f0f0f0',
  borderInlineStart: selected ? '4px solid #1677ff' : '4px solid transparent',
  background: selected ? '#e6f4ff' : '#fff',
  boxShadow: selected ? '0 1px 2px rgba(22, 119, 255, 0.12)' : 'none',
})

const renderCellText = (
  value: string | null | undefined,
  options?: { code?: boolean; maxWidth?: number; secondary?: boolean }
) => {
  const normalized = normalizeText(value)
  if (!normalized) return <Text type="secondary">—</Text>
  const maxWidth = options?.maxWidth ?? 220
  return (
    <Text
      code={options?.code}
      type={options?.secondary ? 'secondary' : undefined}
      ellipsis={{ tooltip: normalized }}
      style={{ maxWidth, display: 'block' }}
    >
      {normalized}
    </Text>
  )
}

const isValidationIssue = (value: unknown): value is ModalValidationIssue => (
  Boolean(value)
  && typeof value === 'object'
  && typeof (value as { message?: unknown }).message === 'string'
)

const toValidationIssues = (value: unknown, fallbackMessage: string): ModalValidationIssue[] => {
  if (!Array.isArray(value)) return []
  return value
    .filter(isValidationIssue)
    .map((item) => ({
      path: normalizeText(item.path) || 'global',
      code: normalizeText(item.code) || undefined,
      message: normalizeText(item.message) || fallbackMessage,
    }))
}

const extractValidationIssuesFromError = (error: unknown, fallback: string): ModalValidationIssue[] => {
  const err = error as {
    response?: {
      data?: {
        validation_errors?: unknown
        errors?: unknown
        error?: { message?: unknown }
      }
    }
  } | null
  const data = err?.response?.data
  const direct = [
    ...toValidationIssues(data?.validation_errors, fallback),
    ...toValidationIssues(data?.errors, fallback),
  ]
  if (direct.length > 0) return direct
  const nested = data?.error?.message
  return toValidationIssues(nested, fallback)
}

const isFormValidationError = (error: unknown): boolean => (
  Boolean(error)
  && typeof error === 'object'
  && Array.isArray((error as { errorFields?: unknown }).errorFields)
)

const mapValidationPathToField = (pathRaw: string): string[] | null => {
  const path = normalizeText(pathRaw)
  if (!path) return null

  if (path === 'exposure.alias') return ['id']
  if (path === 'exposure.name') return ['name']
  if (path === 'exposure.description') return ['description']
  if (path === 'exposure.capability') return ['capability']
  if (path === 'exposure.is_active') return ['is_active']
  if (path === 'definition.executor_kind' || path === 'definition.executor_payload.kind') return ['executor', 'kind']
  if (path === 'definition.executor_payload.command_id') return ['executor', 'command_id']
  if (path === 'definition.executor_payload.workflow_id') return ['executor', 'workflow_id']
  if (path === 'definition.executor_payload.mode') return ['executor', 'mode']
  if (path === 'definition.executor_payload.params' || path.startsWith('definition.executor_payload.params.')) return ['executor', 'params_json']
  if (path === 'definition.executor_payload.input_context' || path.startsWith('definition.executor_payload.input_context.')) return ['executor', 'params_json']
  if (path === 'definition.executor_payload.additional_args' || path.startsWith('definition.executor_payload.additional_args.')) return ['executor', 'additional_args']
  if (path === 'definition.executor_payload.stdin') return ['executor', 'stdin']
  if (path === 'definition.executor_payload.operation_type') return ['executor', 'kind']
  if (path === 'definition.executor_payload.template_data') return ['executor', 'params_json']
  if (path === 'definition.executor_payload.template_data.command_id') return ['executor', 'command_id']
  if (path === 'definition.executor_payload.template_data.workflow_id') return ['executor', 'workflow_id']
  if (path === 'definition.executor_payload.template_data.mode') return ['executor', 'mode']
  if (path === 'definition.executor_payload.template_data.params' || path.startsWith('definition.executor_payload.template_data.params.')) return ['executor', 'params_json']
  if (path === 'definition.executor_payload.template_data.input_context' || path.startsWith('definition.executor_payload.template_data.input_context.')) return ['executor', 'params_json']
  if (path === 'definition.executor_payload.template_data.additional_args' || path.startsWith('definition.executor_payload.template_data.additional_args.')) return ['executor', 'additional_args']
  if (path === 'definition.executor_payload.template_data.stdin') return ['executor', 'stdin']
  if (path === 'definition.executor_payload.target_binding.extension_name_param') return ['executor', 'target_binding_extension_name_param']
  if (path === 'definition.executor_payload.template_data.target_binding.extension_name_param') return ['executor', 'target_binding_extension_name_param']
  if (path === 'capability_config.target_binding.extension_name_param') return ['executor', 'target_binding_extension_name_param']
  if (path === 'definition.executor_payload.fixed.confirm_dangerous') return ['executor', 'fixed', 'confirm_dangerous']
  if (path === 'definition.executor_payload.fixed.timeout_seconds') return ['executor', 'fixed', 'timeout_seconds']
  if (path.startsWith('definition.executor_payload.fixed')) return ['executor', 'fixed']

  return null
}

const toErrorMessage = (error: unknown, fallback: string): string => {
  const err = error as {
    message?: string
    response?: {
      data?: {
        error?: { message?: string }
        validation_errors?: Array<{ message?: string }>
      }
    }
  } | null
  const validationMessage = err?.response?.data?.validation_errors?.[0]?.message
  if (typeof validationMessage === 'string' && validationMessage.trim()) return validationMessage
  const apiMessage = err?.response?.data?.error?.message
  if (typeof apiMessage === 'string' && apiMessage.trim()) return apiMessage
  if (typeof err?.message === 'string' && err.message.trim()) return err.message
  return fallback
}

const isSystemManagedPoolRuntimeTemplate = (template: TemplateRow): boolean => (
  template.system_managed === true
  && normalizeText(template.domain).toLowerCase() === 'pool_runtime'
)

const isWorkflowExecutorTemplate = (template: Pick<TemplateRow, 'executor_kind'>): boolean => (
  normalizeText(template.executor_kind).toLowerCase() === 'workflow'
)

const toTemplateRow = (exposure: OperationCatalogExposure): TemplateRow | null => {
  if (exposure.surface !== 'template') return null

  const templateData = isPlainObject(exposure.template_data) ? exposure.template_data : {}
  const templateExposureId = String(exposure.template_exposure_id || exposure.id || '').trim() || undefined
  const rawTemplateExposureRevision = (
    typeof exposure.template_exposure_revision === 'number'
      ? exposure.template_exposure_revision
      : typeof exposure.exposure_revision === 'number'
        ? exposure.exposure_revision
        : undefined
  )
  const templateExposureRevision = (
    typeof rawTemplateExposureRevision === 'number'
      && Number.isFinite(rawTemplateExposureRevision)
      && rawTemplateExposureRevision >= 1
      ? Math.trunc(rawTemplateExposureRevision)
      : undefined
  )
  const commandIdFromTemplateData = (
    typeof templateData.command_id === 'string'
      ? templateData.command_id.trim()
      : ''
  )
  const executorCommandId = (
    typeof exposure.executor_command_id === 'string'
      ? exposure.executor_command_id.trim()
      : commandIdFromTemplateData
  )

  return {
    id: String(exposure.alias || ''),
    status: String(exposure.status || (exposure.is_active !== false ? 'published' : 'draft')),
    name: String(exposure.name || ''),
    description: String(exposure.description || ''),
    operation_type: String(exposure.operation_type || 'designer_cli'),
    executor_kind: String(exposure.executor_kind || exposure.operation_type || 'designer_cli'),
    executor_command_id: executorCommandId || undefined,
    target_entity: String(exposure.target_entity || 'infobase'),
    capability: String(exposure.capability || '').trim() || undefined,
    capability_config: isPlainObject(exposure.capability_config) ? exposure.capability_config : {},
    template_data: templateData,
    is_active: exposure.is_active !== false,
    created_at: String(exposure.created_at || ''),
    updated_at: String(exposure.updated_at || ''),
    exposure_id: String(exposure.id || ''),
    template_exposure_id: templateExposureId,
    template_exposure_revision: templateExposureRevision,
    definition_id: String(exposure.definition_id || ''),
    system_managed: exposure.system_managed === true,
    domain: String(exposure.domain || ''),
  }
}

function OperationTemplateListShell({
  canManageTemplate,
  canManageAnyTemplate,
  showPoolRuntimeDiagnostics,
}: {
  canManageTemplate: (templateId: string) => boolean
  canManageAnyTemplate: boolean
  showPoolRuntimeDiagnostics: boolean
}) {
  const { message } = App.useApp()
  const screens = useBreakpoint()
  const { t, ready } = useTemplatesTranslation()
  const formatters = useLocaleFormatters()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const tableRouteHydratedRef = useRef(false)
  const tableRouteSyncRef = useRef(false)
  const searchFromUrl = searchParams.get('q') ?? ''
  const selectedTemplateFromUrl = normalizeRouteParam(searchParams.get('template'))
  const detailOpenFromUrl = searchParams.get('detail') === '1'
  const composeModeFromUrl = parseComposeMode(searchParams.get('compose'))
  const [dryRun, setDryRun] = useState<boolean>(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<TemplateRow | null>(null)
  const [exposuresReloadTick, setExposuresReloadTick] = useState(0)
  const [editorValues, setEditorValues] = useState<ActionFormValues | null>(null)
  const [modalValidationErrors, setModalValidationErrors] = useState<ModalValidationIssue[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null | undefined>(
    () => selectedTemplateFromUrl ?? undefined
  )
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(detailOpenFromUrl)
  const [composeMode, setComposeMode] = useState<TemplateComposeMode>(composeModeFromUrl)
  const [form] = Form.useForm<ActionFormValues>()

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: t(($) => $.table.name), sortable: true, groupKey: 'core', groupLabel: t(($) => $.groups.core) },
    { key: 'id', label: t(($) => $.table.alias), sortable: true, groupKey: 'core', groupLabel: t(($) => $.groups.core) },
    { key: 'system_managed', label: t(($) => $.table.managed), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'domain', label: t(($) => $.table.domain), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'operation_type', label: t(($) => $.table.operationType), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'executor_kind', label: t(($) => $.table.executorKind), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'executor_command_id', label: t(($) => $.table.commandId), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'target_entity', label: t(($) => $.table.target), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'template_exposure_id', label: t(($) => $.table.exposureId), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'template_exposure_revision', label: t(($) => $.table.exposureRevision), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'capability', label: t(($) => $.table.capability), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'status', label: t(($) => $.table.status), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'is_active', label: t(($) => $.table.active), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'updated_at', label: t(($) => $.table.updated), sortable: true, groupKey: 'time', groupLabel: t(($) => $.groups.time) },
    { key: 'actions', label: t(($) => $.table.actions), sortable: false, groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
  ], [t])

  const syncMutation = useSyncTemplatesFromRegistry()
  const createMutation = useCreateTemplate()
  const updateMutation = useUpdateTemplate()
  const deleteMutation = useDeleteTemplate()
  const poolRuntimeRegistryQuery = usePoolRuntimeRegistryInspect(showPoolRuntimeDiagnostics)
  const formatDateTime = useCallback((value?: string | null) => (
    formatters.dateTime(value, { fallback: '—' })
  ), [formatters])
  const formatCompactDateTime = useCallback((value?: string | null) => (
    formatters.date(value, { fallback: '—' })
  ), [formatters])
  const getTemplateStatusLabel = useCallback((status: string) => {
    if (status === 'published') {
      return t(($) => $.detail.statusPublished)
    }
    if (status === 'draft') {
      return t(($) => $.detail.draft)
    }
    return status
  }, [t])

  const closeModal = useCallback(() => {
    routeUpdateModeRef.current = 'push'
    form.resetFields()
    setComposeMode(null)
    setModalOpen(false)
    setEditingTemplate(null)
    setEditorValues(null)
    setModalValidationErrors([])
  }, [form])

  const openCreateModal = useCallback(() => {
    routeUpdateModeRef.current = 'push'
    setComposeMode('create')
  }, [])

  const openEditTemplateModal = useCallback((template: TemplateRow) => {
    if (isSystemManagedPoolRuntimeTemplate(template)) {
      message.warning(t(($) => $.messages.readOnlySystemManaged))
      return
    }
    routeUpdateModeRef.current = 'push'
    setSelectedTemplateId(template.id)
    setIsDetailDrawerOpen(true)
    setComposeMode('edit')
  }, [message, t])

  const handleDeleteTemplate = useCallback(async (template: TemplateRow) => {
    if (isSystemManagedPoolRuntimeTemplate(template)) {
      message.warning(t(($) => $.messages.readOnlySystemManaged))
      return
    }
    try {
      await deleteMutation.mutateAsync({ template_id: template.id })
      routeUpdateModeRef.current = 'push'
      if (selectedTemplateId === template.id) {
        setComposeMode(null)
        setSelectedTemplateId(null)
        setIsDetailDrawerOpen(false)
      }
      setExposuresReloadTick((value) => value + 1)
      message.success(t(($) => $.messages.templateDeleted))
    } catch (err) {
      message.error(toErrorMessage(err, t(($) => $.errors.failedToDelete)))
    }
  }, [deleteMutation, message, selectedTemplateId, t])

  const table = useTableToolkit<TemplateRow>({
    tableId: 'operation-templates',
    columns: [],
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
    disableServerMetadata: true,
  })
  const { setFilters: setTableFilters, setSearch: setTableSearch, setSort: setTableSort } = table

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const searchValue = table.search.trim()
  const filtersParam = useMemo(() => (
    table.filtersPayload ? JSON.stringify(table.filtersPayload) : undefined
  ), [table.filtersPayload])
  const sortParam = useMemo(() => (
    table.sortPayload ? JSON.stringify(table.sortPayload) : undefined
  ), [table.sortPayload])
  const latestTableRouteStateRef = useRef({
    search: table.search,
    filters: table.filters,
    sort: table.sort,
  })
  const routeFiltersFromUrl = useMemo(
    () => parseRouteTableFilters(searchParams.get('filters'), table.filterConfigs),
    [searchParams, table.filterConfigs]
  )
  const routeSortFromUrl = useMemo(
    () => parseRouteTableSort(searchParams.get('sort'), table.sortableColumns),
    [searchParams, table.sortableColumns]
  )

  useEffect(() => {
    latestTableRouteStateRef.current = {
      search: table.search,
      filters: table.filters,
      sort: table.sort,
    }
  }, [table.filters, table.search, table.sort])

  useEffect(() => {
    const current = latestTableRouteStateRef.current
    const nextSearch = searchFromUrl
    const searchChanged = current.search !== nextSearch
    const filtersChanged = !areRouteTableFiltersEqual(current.filters, routeFiltersFromUrl)
    const sortChanged = current.sort.key !== routeSortFromUrl.key || current.sort.order !== routeSortFromUrl.order

    if (searchChanged || filtersChanged || sortChanged) {
      tableRouteSyncRef.current = true
      if (searchChanged) {
        setTableSearch(nextSearch)
      }
      if (filtersChanged) {
        setTableFilters(routeFiltersFromUrl)
      }
      if (sortChanged) {
        setTableSort(routeSortFromUrl.key, routeSortFromUrl.order)
      }
      return
    }

    tableRouteHydratedRef.current = true
  }, [
    routeFiltersFromUrl,
    routeSortFromUrl.key,
    routeSortFromUrl.order,
    searchFromUrl,
    setTableFilters,
    setTableSearch,
    setTableSort,
  ])

  useEffect(() => {
    setSelectedTemplateId((current) => {
      if (selectedTemplateFromUrl) {
        return current === selectedTemplateFromUrl ? current : selectedTemplateFromUrl
      }
      return current === null ? current : null
    })
  }, [selectedTemplateFromUrl])

  useEffect(() => {
    setIsDetailDrawerOpen((current) => (current === detailOpenFromUrl ? current : detailOpenFromUrl))
  }, [detailOpenFromUrl])

  useEffect(() => {
    setComposeMode((current) => (current === composeModeFromUrl ? current : composeModeFromUrl))
  }, [composeModeFromUrl])

  const exposuresQuery = useQuery({
    queryKey: [
      'templates',
      'operation-exposures',
      exposuresReloadTick,
      searchValue,
      filtersParam ?? '',
      sortParam ?? '',
      table.pagination.page,
      table.pagination.pageSize,
    ],
    queryFn: async () => listOperationCatalogExposures({
      surface: 'template',
      search: searchValue || undefined,
      filters: filtersParam,
      sort: sortParam,
      limit: table.pagination.pageSize,
      offset: pageStart,
    }),
  })

  const selectedTemplateQuery = useQuery({
    queryKey: ['templates', 'operation-exposure-selected', exposuresReloadTick, selectedTemplateId ?? ''],
    enabled: Boolean(selectedTemplateId) && !(exposuresQuery.data?.exposures ?? []).some((item) => item.alias === selectedTemplateId),
    queryFn: async () => {
      const response = await listOperationCatalogExposures({
        surface: 'template',
        search: selectedTemplateId ?? undefined,
        limit: 50,
        offset: 0,
      })
      const exposure = response.exposures.find((item) => item.surface === 'template' && item.alias === selectedTemplateId)
      return exposure ? toTemplateRow(exposure) : null
    },
  })

  const pagedRows = useMemo(() => {
    const rows: TemplateRow[] = []

    for (const exposure of exposuresQuery.data?.exposures ?? []) {
      const row = toTemplateRow(exposure)
      if (row) {
        rows.push(row)
      }
    }

    return {
      rows,
      total: typeof exposuresQuery.data?.total === 'number' ? exposuresQuery.data.total : rows.length,
    }
  }, [exposuresQuery.data?.exposures, exposuresQuery.data?.total])

  const selectedTemplate = useMemo(() => (
    pagedRows.rows.find((row) => row.id === selectedTemplateId)
      ?? selectedTemplateQuery.data
      ?? null
  ), [pagedRows.rows, selectedTemplateId, selectedTemplateQuery.data])

  useEffect(() => {
    if (exposuresQuery.isLoading) {
      return
    }
    if (pagedRows.rows.length === 0) {
      routeUpdateModeRef.current = 'replace'
      setSelectedTemplateId(null)
      setIsDetailDrawerOpen(false)
      return
    }
    if (selectedTemplateId) {
      if (pagedRows.rows.some((row) => row.id === selectedTemplateId)) {
        return
      }
      if (selectedTemplateQuery.data?.id === selectedTemplateId) {
        return
      }
      if (selectedTemplateFromUrl === selectedTemplateId && selectedTemplateQuery.isLoading) {
        return
      }
    }
    routeUpdateModeRef.current = 'replace'
    setSelectedTemplateId(pagedRows.rows[0]?.id ?? null)
  }, [
    exposuresQuery.isLoading,
    pagedRows.rows,
    selectedTemplateFromUrl,
    selectedTemplateId,
    selectedTemplateQuery.data?.id,
    selectedTemplateQuery.isLoading,
  ])

  useEffect(() => {
    if (tableRouteSyncRef.current) {
      tableRouteSyncRef.current = false
      return
    }
    if (!tableRouteHydratedRef.current) {
      return
    }

    const next = new URLSearchParams(searchParams)
    const normalizedSearch = table.search.trim()
    const serializedFilters = serializeRouteTableFilters(table.filters)
    const serializedSort = serializeRouteTableSort(table.sort)

    if (normalizedSearch) {
      next.set('q', normalizedSearch)
    } else {
      next.delete('q')
    }

    if (serializedFilters) {
      next.set('filters', serializedFilters)
    } else {
      next.delete('filters')
    }

    if (serializedSort) {
      next.set('sort', serializedSort)
    } else {
      next.delete('sort')
    }

    if (selectedTemplateId !== undefined) {
      if (selectedTemplateId) {
        next.set('template', selectedTemplateId)
      } else {
        next.delete('template')
      }
    }

    if (selectedTemplateId !== undefined) {
      if (isDetailDrawerOpen && selectedTemplateId) {
        next.set('detail', '1')
      } else {
        next.delete('detail')
      }
    }

    if (composeMode) {
      next.set('compose', composeMode)
    } else {
      next.delete('compose')
    }

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(
        next,
        routeUpdateModeRef.current === 'replace'
          ? { replace: true }
          : undefined
      )
    }
    routeUpdateModeRef.current = 'replace'
  }, [
    composeMode,
    isDetailDrawerOpen,
    searchParams,
    selectedTemplateId,
    setSearchParams,
    table.filters,
    table.search,
    table.sort,
  ])

  const activeError = exposuresQuery.error
  const activeErrorStatus = (activeError as { response?: { status?: number } } | null)?.response?.status
  const showAccessWarning = activeErrorStatus === 403
  const poolRuntimeRegistrySummary = useMemo(() => {
    const entries = poolRuntimeRegistryQuery.data?.entries ?? []
    const missingCount = entries.filter((entry) => entry.status === 'missing').length
    const driftCount = entries.filter((entry) => entry.status === 'drift').length
    const configuredCount = entries.filter((entry) => entry.status === 'configured').length
    const issuePreview = entries
      .filter((entry) => entry.status !== 'configured')
      .slice(0, 3)
      .map((entry) => `${entry.alias}: ${entry.issues.join(', ') || entry.status}`)
    return {
      configuredCount,
      missingCount,
      driftCount,
      issuePreview,
      contractVersion: poolRuntimeRegistryQuery.data?.contract_version || 'pool_runtime.v1',
    }
  }, [poolRuntimeRegistryQuery.data?.contract_version, poolRuntimeRegistryQuery.data?.entries])

  const selectedTemplateReadOnly = selectedTemplate ? isSystemManagedPoolRuntimeTemplate(selectedTemplate) : false
  const selectedTemplateCanMutate = selectedTemplate
    ? canManageTemplate(selectedTemplate.id) && !selectedTemplateReadOnly
    : false
  const selectedTemplateDisabledReason = selectedTemplateReadOnly
    ? 'System-managed pool runtime template is read-only'
    : undefined

  useEffect(() => {
    if (composeMode === 'create') {
      if (!canManageAnyTemplate) {
        routeUpdateModeRef.current = 'replace'
        setComposeMode(null)
        return
      }
      setEditingTemplate(null)
      setEditorValues(buildTemplateEditorValues(null))
      setModalValidationErrors([])
      setModalOpen(true)
      return
    }
    if (composeMode === 'edit' && selectedTemplate) {
      if (!selectedTemplateCanMutate) {
        routeUpdateModeRef.current = 'replace'
        setComposeMode(null)
        return
      }
      setEditingTemplate(selectedTemplate)
      setEditorValues(buildTemplateEditorValues(selectedTemplate))
      setModalValidationErrors([])
      setModalOpen(true)
      return
    }
    setModalOpen(false)
  }, [canManageAnyTemplate, composeMode, selectedTemplate, selectedTemplateCanMutate])

  const modalTitle = useMemo(() => (
    editingTemplate ? t(($) => $.page.editTemplate) : t(($) => $.page.newTemplate)
  ), [editingTemplate, t])

  const modalProvenance = useMemo<TemplateModalProvenance | null>(() => {
    if (!editingTemplate) return null
    return {
      alias: editingTemplate.id,
      templateExposureId: editingTemplate.template_exposure_id,
      templateExposureRevision: editingTemplate.template_exposure_revision,
      definitionId: editingTemplate.definition_id,
      status: editingTemplate.status,
    }
  }, [editingTemplate])

  const clearMappedFieldErrors = useCallback(() => {
    type SetFieldsPayload = Parameters<(typeof form)['setFields']>[0]
    const fields: SetFieldsPayload = TEMPLATE_EDITOR_FIELD_PATHS.map((name) => ({
      name: name as SetFieldsPayload[number]['name'],
      errors: [],
    }))
    form.setFields(fields)
  }, [form])

  const applyBackendValidationIssues = useCallback((issues: ModalValidationIssue[]) => {
    setModalValidationErrors(issues)
    clearMappedFieldErrors()

    if (issues.length === 0) return

    type SetFieldsPayload = Parameters<(typeof form)['setFields']>[0]
    const fieldIssues = new Map<string, SetFieldsPayload[number]>()
    for (const issue of issues) {
      const fieldName = mapValidationPathToField(issue.path)
      if (!fieldName) continue
      const key = fieldName.join('.')
      const entry = fieldIssues.get(key)
      if (entry) {
        const existingErrors = Array.isArray(entry.errors) ? entry.errors : []
        entry.errors = [...existingErrors, issue.message]
      } else {
        fieldIssues.set(key, {
          name: fieldName as SetFieldsPayload[number]['name'],
          errors: [issue.message],
        })
      }
    }
    if (fieldIssues.size > 0) {
      form.setFields(Array.from(fieldIssues.values()))
    }
  }, [clearMappedFieldErrors, form])

  const handleSaveTemplate = useCallback(async () => {
    if (createMutation.isPending || updateMutation.isPending) return
    applyBackendValidationIssues([])
    try {
      const values = await form.validateFields()
      const built = buildTemplateWritePayloadFromEditor(values, { existingId: editingTemplate?.id })
      if (!built.ok) {
        message.error(t(($) => $.errors[built.errorKey]))
        return
      }

      const upsertPayload = buildTemplateOperationCatalogUpsertPayload(built.payload)
      const validation = await validateOperationCatalogExposure({
        definition: upsertPayload.definition,
        exposure: upsertPayload.exposure,
      })
      if (!validation.valid) {
        const issues = toValidationIssues(validation.errors, t(($) => $.errors.validationFailed))
        applyBackendValidationIssues(issues)
        message.error(t(($) => $.errors.saveBlocked))
        return
      }

      let result
      if (editingTemplate) {
        result = await updateMutation.mutateAsync(built.payload)
        message.success(t(($) => $.messages.templateUpdated))
      } else {
        result = await createMutation.mutateAsync(built.payload)
        message.success(t(($) => $.messages.templateCreated))
      }
      routeUpdateModeRef.current = 'push'
      setSelectedTemplateId(result.template.id)
      setIsDetailDrawerOpen(true)
      setExposuresReloadTick((value) => value + 1)
      closeModal()
    } catch (err) {
      if (isFormValidationError(err)) return
      const issues = extractValidationIssuesFromError(err, t(($) => $.errors.validationFailed))
      if (issues.length > 0) {
        applyBackendValidationIssues(issues)
        message.error(t(($) => $.errors.saveBlocked))
        return
      }
      message.error(
        toErrorMessage(
          err,
          editingTemplate ? t(($) => $.errors.failedToUpdate) : t(($) => $.errors.failedToCreate)
        )
      )
    }
  }, [applyBackendValidationIssues, closeModal, createMutation, editingTemplate, form, message, t, updateMutation])

  const onSync = useCallback(async () => {
    try {
      const result = await syncMutation.mutateAsync({
        dry_run: dryRun,
        include_pool_runtime: true,
      })
      message.success(t(($) => $.messages.syncSummary, {
        message: String(result.message),
        created: String(result.created),
        updated: String(result.updated),
        unchanged: String(result.unchanged),
      }))
      setExposuresReloadTick((value) => value + 1)
    } catch (err) {
      const status = (err as { response?: { status?: number } } | null)?.response?.status
      if (status === 403) {
        message.error(t(($) => $.messages.syncRequiresStaff))
        return
      }
      message.error(t(($) => $.errors.syncFailed))
    }
  }, [dryRun, message, syncMutation, t])

  const detailLoading = Boolean(selectedTemplateId) && !selectedTemplate && (exposuresQuery.isLoading || selectedTemplateQuery.isLoading)
  const detailError = selectedTemplateId && !selectedTemplate && selectedTemplateQuery.isError
    ? t(($) => $.errors.failedToLoadSelected)
    : null
  const catalogError = !showAccessWarning && exposuresQuery.isError
    ? t(($) => $.errors.failedToLoadCatalog)
    : null
  const activeFilterSummaries = useMemo(() => (
    table.filterConfigs.flatMap((config) => {
      const value = table.filters[config.key]
      if (!hasRouteFilterValue(value)) {
        return []
      }
      return `${config.label}: ${Array.isArray(value) ? value.join(', ') : String(value)}`
    })
  ), [table.filterConfigs, table.filters])
  const activeSortSummary = useMemo(() => {
    if (!table.sort.key || !table.sort.order) {
      return null
    }
    const config = table.columnConfigs.find((item) => item.key === table.sort.key)
    const label = config?.label || table.sort.key
    return `${label}: ${table.sort.order === 'asc' ? t(($) => $.sort.ascending) : t(($) => $.sort.descending)}`
  }, [t, table.columnConfigs, table.sort.key, table.sort.order])
  const catalogStateToolbar = activeFilterSummaries.length > 0 || activeSortSummary
    ? (
      <Alert
        type="info"
        showIcon
        message={t(($) => $.alerts.routeFiltersActive)}
        description={(
          <Space wrap size={[8, 8]}>
            {activeFilterSummaries.map((summary) => (
              <Tag key={summary}>{summary}</Tag>
            ))}
            {activeSortSummary ? <Tag color="blue">{activeSortSummary}</Tag> : null}
          </Space>
        )}
        style={{ marginBottom: 16 }}
      />
    )
    : null

  if (!ready) {
    return null
  }

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t(($) => $.page.title)}
          subtitle={t(($) => $.page.subtitle)}
          actions={(
            <Space wrap>
              {canManageAnyTemplate ? <Button onClick={openCreateModal}>{t(($) => $.page.newTemplate)}</Button> : null}
              {canManageAnyTemplate ? (
                <>
                  <Space>
                    <Text>{t(($) => $.page.dryRun)}</Text>
                    <Switch checked={dryRun} onChange={setDryRun} />
                  </Space>
                  <Button type="primary" loading={syncMutation.isPending} onClick={() => void onSync()}>
                    {t(($) => $.page.syncFromRegistry)}
                  </Button>
                </>
              ) : null}
            </Space>
          )}
        />
      )}
    >
      {showAccessWarning ? (
        <Alert
          type="warning"
          message={t(($) => $.alerts.accessDeniedTitle)}
          description={t(($) => $.alerts.accessDeniedDescription)}
          showIcon
        />
      ) : null}

      <Alert
        type="info"
        showIcon
        message={t(($) => $.alerts.atomicOnlyTitle)}
        description={t(($) => $.alerts.atomicOnlyDescription)}
      />

      {showPoolRuntimeDiagnostics ? (
        <Alert
          data-testid="templates-pool-runtime-registry"
          type={poolRuntimeRegistryQuery.isError || poolRuntimeRegistrySummary.missingCount > 0 || poolRuntimeRegistrySummary.driftCount > 0 ? 'warning' : 'success'}
          message={poolRuntimeRegistryQuery.isLoading ? t(($) => $.registry.loadingTitle) : t(($) => $.registry.title)}
          description={poolRuntimeRegistryQuery.isError ? (
            t(($) => $.registry.loadFailed)
          ) : (
            <Space direction="vertical" size={2}>
              <Text type="secondary">
                {t(($) => $.registry.contractVersion, { value: String(poolRuntimeRegistrySummary.contractVersion) })}
              </Text>
              <Text type="secondary">
                {t(($) => $.registry.summary, {
                  configured: String(poolRuntimeRegistrySummary.configuredCount),
                  missing: String(poolRuntimeRegistrySummary.missingCount),
                  drift: String(poolRuntimeRegistrySummary.driftCount),
                })}
              </Text>
              {poolRuntimeRegistrySummary.issuePreview.length > 0 ? (
                <Text type="secondary">
                  {t(($) => $.registry.issues, { value: poolRuntimeRegistrySummary.issuePreview.join(' | ') })}
                </Text>
              ) : null}
            </Space>
          )}
          showIcon
        />
      ) : null}

      <MasterDetailShell
        detailOpen={isDetailDrawerOpen}
        onCloseDetail={() => {
          routeUpdateModeRef.current = 'push'
          setIsDetailDrawerOpen(false)
        }}
        detailDrawerTitle={selectedTemplate?.name || t(($) => $.detail.drawerTitle)}
        list={(
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <EntityList
              title={t(($) => $.catalog.title)}
              extra={(
                <Input.Search
                  aria-label={t(($) => $.catalog.searchAriaLabel)}
                  allowClear
                  placeholder={t(($) => $.catalog.searchPlaceholder)}
                  value={table.search}
                  onChange={(event) => table.setSearch(event.target.value)}
                  style={{ width: '100%', maxWidth: 260 }}
                />
              )}
              toolbar={catalogStateToolbar}
              error={catalogError}
              loading={exposuresQuery.isLoading}
              emptyDescription={t(($) => $.catalog.emptyDescription)}
              dataSource={pagedRows.rows}
              renderItem={(template) => {
                const selected = template.id === selectedTemplateId
                const readOnlySystemTemplate = isSystemManagedPoolRuntimeTemplate(template)
                const executionSummary = [
                  normalizeText(template.executor_kind) || normalizeText(template.operation_type) || t(($) => $.catalog.unknownExecutor),
                  normalizeText(template.executor_command_id) || normalizeText(template.capability) || t(($) => $.catalog.noCommandBinding),
                ].join(' · ')
                const provenanceSummary = [
                  template.template_exposure_revision ? t(($) => $.catalog.revision, { value: String(template.template_exposure_revision) }) : null,
                  template.target_entity ? t(($) => $.catalog.target, { value: template.target_entity }) : null,
                  template.updated_at ? t(($) => $.catalog.updated, { value: formatCompactDateTime(template.updated_at) }) : null,
                ].filter(Boolean).join(' · ')

                return (
                  <Button
                    key={template.id}
                    type="text"
                    block
                    data-testid={`templates-catalog-item-${template.id}`}
                    aria-label={t(($) => $.catalog.openTemplate, { name: template.name })}
                    aria-pressed={selected}
                    onClick={() => {
                      routeUpdateModeRef.current = 'push'
                      setSelectedTemplateId(template.id)
                      setIsDetailDrawerOpen(true)
                    }}
                    style={buildCatalogButtonStyle(selected)}
                  >
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                      <Space wrap size={[8, 8]}>
                        <Text strong>{template.name}</Text>
                        <StatusBadge
                          status={template.status === 'published' ? 'published' : 'inactive'}
                          label={getTemplateStatusLabel(template.status)}
                        />
                        <StatusBadge
                          status={template.is_active ? 'active' : 'inactive'}
                          label={template.is_active ? t(($) => $.catalog.active) : t(($) => $.catalog.inactive)}
                        />
                        {readOnlySystemTemplate ? <Tag color="gold">{t(($) => $.catalog.systemManaged)}</Tag> : null}
                        {isWorkflowExecutorTemplate(template) ? (
                          <Tag color="orange" data-testid="templates-executor-kind-compatibility-tag">
                            {t(($) => $.catalog.compatibility)}
                          </Tag>
                        ) : null}
                      </Space>
                      {renderCellText(template.id, { code: true, secondary: true, maxWidth: 360 })}
                      <Text type="secondary">{executionSummary}</Text>
                      <Text type="secondary">{provenanceSummary || t(($) => $.catalog.noProvenanceSummary)}</Text>
                    </Space>
                  </Button>
                )
              }}
            />
            <Pagination
              size="small"
              current={table.pagination.page}
              pageSize={table.pagination.pageSize}
              total={pagedRows.total}
              showSizeChanger
              pageSizeOptions={[20, 50, 100]}
              onChange={(page, pageSize) => {
                if (pageSize !== table.pagination.pageSize) {
                  table.setPageSize(pageSize)
                  return
                }
                table.setPage(page)
              }}
            />
          </Space>
        )}
        detail={(
          <EntityDetails
            title={t(($) => $.detail.title)}
            loading={detailLoading}
            error={detailError}
            empty={!selectedTemplateId || (!selectedTemplate && !detailLoading)}
            emptyDescription={t(($) => $.detail.emptyDescription)}
            extra={selectedTemplate ? (
              <Space wrap>
                <Button
                  title={selectedTemplateDisabledReason}
                  disabled={!selectedTemplateCanMutate}
                  onClick={() => openEditTemplateModal(selectedTemplate)}
                >
                  {t(($) => $.detail.edit)}
                </Button>
                <Popconfirm
                  title={t(($) => $.detail.deleteConfirmTitle)}
                  okText={t(($) => $.detail.deleteConfirmOk)}
                  cancelText={t(($) => $.detail.deleteConfirmCancel)}
                  onConfirm={() => {
                    void handleDeleteTemplate(selectedTemplate)
                  }}
                  disabled={!selectedTemplateCanMutate}
                >
                  <Button
                    danger
                    title={selectedTemplateDisabledReason}
                    disabled={!selectedTemplateCanMutate}
                  >
                    {t(($) => $.detail.delete)}
                  </Button>
                </Popconfirm>
              </Space>
            ) : undefined}
          >
            {selectedTemplate ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                {isWorkflowExecutorTemplate(selectedTemplate) ? (
                  <Alert
                    type="warning"
                    showIcon
                    message={t(($) => $.alerts.compatibilityOnlyTitle)}
                    description={t(($) => $.alerts.compatibilityOnlyDescription)}
                  />
                ) : null}

                {selectedTemplateReadOnly ? (
                  <Alert
                    type="info"
                    showIcon
                    message={t(($) => $.alerts.systemManagedTitle)}
                    description={t(($) => $.alerts.systemManagedDescription)}
                  />
                ) : null}

                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label={t(($) => $.detail.fields.name)}>
                    <Text strong data-testid="templates-selected-name">{selectedTemplate.name}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.alias)}>
                    <Text code data-testid="templates-selected-id">{selectedTemplate.id}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.status)}>
                    <span data-testid="templates-selected-status">
                      <StatusBadge status={selectedTemplate.status} label={getTemplateStatusLabel(selectedTemplate.status)} />
                    </span>
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.managed)}>
                    {selectedTemplateReadOnly ? (
                      <Space size={6}>
                        <Tag color="gold">{t(($) => $.detail.systemManaged)}</Tag>
                        {renderCellText(selectedTemplate.domain || 'pool_runtime', { code: true, maxWidth: 160 })}
                      </Space>
                    ) : (
                      <Tag>{t(($) => $.detail.userManaged)}</Tag>
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.operationType)}>
                    {renderCellText(selectedTemplate.operation_type, { code: true, maxWidth: 260 })}
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.executorKind)}>
                    {isWorkflowExecutorTemplate(selectedTemplate) ? (
                      <Space size={6} wrap>
                        <Tag color="orange">{t(($) => $.detail.compatibility)}</Tag>
                        {renderCellText(selectedTemplate.executor_kind, { code: true, maxWidth: 260 })}
                      </Space>
                    ) : renderCellText(selectedTemplate.executor_kind, { code: true, maxWidth: 260 })}
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.commandId)}>
                    {renderCellText(selectedTemplate.executor_command_id, { code: true, maxWidth: 320 })}
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.target)}>
                    {renderCellText(selectedTemplate.target_entity, { code: true, maxWidth: 260 })}
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.capability)}>
                    {renderCellText(selectedTemplate.capability, { code: true, maxWidth: 320 })}
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.active)}>
                    {selectedTemplate.is_active ? t(($) => $.detail.yes) : t(($) => $.detail.no)}
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.exposureId)}>
                    {renderCellText(selectedTemplate.template_exposure_id, { code: true, maxWidth: 360 })}
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.exposureRevision)}>
                    {typeof selectedTemplate.template_exposure_revision === 'number'
                      ? String(selectedTemplate.template_exposure_revision)
                      : '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.definitionId)}>
                    {renderCellText(selectedTemplate.definition_id, { code: true, maxWidth: 360 })}
                  </Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.updatedAt)}>{formatDateTime(selectedTemplate.updated_at)}</Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.createdAt)}>{formatDateTime(selectedTemplate.created_at)}</Descriptions.Item>
                  <Descriptions.Item label={t(($) => $.detail.fields.description)}>{selectedTemplate.description || '—'}</Descriptions.Item>
                </Descriptions>

                <JsonBlock
                  title={t(($) => $.detail.executorTemplateData)}
                  value={selectedTemplate.template_data}
                  dataTestId="templates-selected-template-data"
                  height={screens.lg ? 260 : 220}
                />

                <JsonBlock
                  title={t(($) => $.detail.capabilityConfig)}
                  value={selectedTemplate.capability_config}
                  dataTestId="templates-selected-capability-config"
                  height={screens.lg ? 220 : 180}
                />
              </Space>
            ) : null}
          </EntityDetails>
        )}
      />

      {modalOpen && editorValues ? (
        <TemplateOperationExposureEditorModal
          open={modalOpen}
          title={modalTitle}
          surface="template"
          executorKindOptions={['ibcmd_cli', 'designer_cli', 'workflow']}
          form={form}
          initialValues={editorValues}
          templateProvenance={modalProvenance}
          backendValidationErrors={modalValidationErrors}
          onCancel={closeModal}
          onApply={() => void handleSaveTemplate()}
        />
      ) : null}
    </WorkspacePage>
  )
}

export function TemplatesPage() {
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const canManageAnyTemplate = isStaff || authz.canAnyTemplate('MANAGE')
  const canManageTemplate = useCallback((templateId: string) => (
    isStaff || authz.canTemplate(templateId, 'MANAGE')
  ), [authz, isStaff])
  const [searchParams, setSearchParams] = useSearchParams()
  const surfaceParam = searchParams.get('surface')

  useEffect(() => {
    if (surfaceParam === null) return
    const next = new URLSearchParams(searchParams)
    next.delete('surface')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams, surfaceParam])

  return (
    <OperationTemplateListShell
      canManageTemplate={canManageTemplate}
      canManageAnyTemplate={canManageAnyTemplate}
      showPoolRuntimeDiagnostics={isStaff}
    />
  )
}
