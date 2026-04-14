import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  App,
  Alert,
  Button,
  Descriptions,
  Input,
  Pagination,
  Popconfirm,
  Space,
  Tag,
  Typography,
} from 'antd'
import {
  ClockCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../../api/generated'
import type { WorkflowTemplateDetail, WorkflowTemplateList } from '../../api/generated/model'
import {
  EntityDetails,
  EntityList,
  JsonBlock,
  MasterDetailShell,
  PageHeader,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import type { TableFilters, TableSortState } from '../../components/table/types'
import {
  areRouteTableFiltersEqual,
  parseRouteTableFilters,
  parseRouteTableSort,
  serializeRouteTableFilters,
  serializeRouteTableSort,
} from '../../components/table/routeState'
import { useLocaleFormatters, useWorkflowTranslation } from '../../i18n'
import { buildRelativeHref } from './routeState'

const api = getV2()
const { Text } = Typography

const workflowTypeColors: Record<string, string> = {
  sequential: 'blue',
  parallel: 'green',
  conditional: 'orange',
  complex: 'purple',
}

const WORKFLOW_LIBRARY_SURFACE = 'workflow_library'
const WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE = 'runtime_diagnostics'

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

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

const countRawRouteFilterKeys = (rawValue: string | null): number => {
  if (!rawValue) {
    return 0
  }
  try {
    const parsed = JSON.parse(rawValue) as Record<string, unknown>
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return 0
    }
    return Object.values(parsed).filter((value) => hasRouteFilterValue(value)).length
  } catch {
    return 0
  }
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

const buildWorkflowHref = (
  id: string,
  {
    isSystemManaged,
    databaseId,
    execute,
    returnTo,
  }: {
    isSystemManaged?: boolean
    databaseId?: string
    execute?: boolean
    returnTo?: string | null
  } = {}
) => {
  const params = new URLSearchParams()
  if (isSystemManaged) {
    params.set('surface', WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE)
  }
  if (databaseId) {
    params.set('database_id', databaseId)
  }
  if (execute) {
    params.set('execute', 'true')
  }
  if (returnTo) {
    params.set('returnTo', returnTo)
  }
  const query = params.toString()
  return query ? `/workflows/${id}?${query}` : `/workflows/${id}`
}

const renderStatusSummary = (
  workflow: Pick<WorkflowTemplateList, 'is_active' | 'is_valid' | 'visibility_surface'>,
  t: (key: string, options?: Record<string, unknown>) => string,
) => (
  <Space wrap size={8}>
    <StatusBadge
      status={workflow.is_active ? 'active' : 'inactive'}
      label={workflow.is_active ? t('statuses.active') : t('statuses.inactive')}
    />
    <StatusBadge
      status={workflow.is_valid ? 'compatible' : 'error'}
      label={workflow.is_valid ? t('statuses.valid') : t('statuses.invalid')}
    />
    <StatusBadge
      status={workflow.visibility_surface === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE ? 'warning' : 'unknown'}
      label={workflow.visibility_surface === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE
        ? t('common.runtimeDiagnostics')
        : t('common.analystLibrary')}
    />
  </Space>
)

const resolveNodeCount = (
  workflowSummary: WorkflowTemplateList | null,
  workflowDetail: WorkflowTemplateDetail | null
) => {
  if (workflowSummary) {
    return workflowSummary.node_count ?? 0
  }
  const dag = workflowDetail?.dag_structure as { nodes?: unknown } | undefined
  return Array.isArray(dag?.nodes) ? dag.nodes.length : 0
}

const WorkflowList = () => {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { message } = App.useApp()
  const queryClient = useQueryClient()
  const { t } = useWorkflowTranslation()
  const formatters = useLocaleFormatters()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const tableRouteHydratedRef = useRef(false)
  const tableRouteSyncRef = useRef(false)
  const surface = searchParams.get('surface') === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE
    ? WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE
    : WORKFLOW_LIBRARY_SURFACE
  const decisionDatabaseId = String(searchParams.get('database_id') || '').trim()
  const searchFromUrl = searchParams.get('q') ?? ''
  const selectedWorkflowFromUrl = normalizeRouteParam(searchParams.get('workflow'))
  const detailOpenFromUrl = searchParams.get('detail') === '1'
  const rawFiltersFromUrl = searchParams.get('filters')
  const rawSortFromUrl = searchParams.get('sort')
  const isRuntimeDiagnosticsSurface = surface === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null | undefined>(
    () => selectedWorkflowFromUrl ?? undefined
  )
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(detailOpenFromUrl)
  const latestTableRouteStateRef = useRef<{
    search: string
    filters: TableFilters
    sort: TableSortState
  }>({
    search: searchFromUrl,
    filters: {},
    sort: { key: null, order: null },
  })
  const pendingRouteFiltersRef = useRef<string | null>(rawFiltersFromUrl)
  const pendingRouteSortRef = useRef<string | null>(rawSortFromUrl)
  const routeUrlSyncPrimedRef = useRef(false)

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: t('list.columns.name'), sortable: true, groupKey: 'core', groupLabel: t('list.columns.core') },
    { key: 'workflow_type', label: t('list.columns.type'), sortable: true, groupKey: 'meta', groupLabel: t('list.columns.meta') },
    { key: 'is_active', label: t('list.columns.status'), groupKey: 'meta', groupLabel: t('list.columns.meta') },
    { key: 'node_count', label: t('list.columns.nodes'), sortable: true, groupKey: 'meta', groupLabel: t('list.columns.meta') },
    { key: 'updated_at', label: t('list.columns.updated'), sortable: true, groupKey: 'time', groupLabel: t('list.columns.time') },
    { key: 'actions', label: t('list.columns.actions'), groupKey: 'actions', groupLabel: t('list.columns.actions') },
  ], [t])

  const handleDelete = useCallback(async (id: string) => {
    try {
      await api.postWorkflowsDeleteWorkflow({ workflow_id: id })
      message.success(t('list.messages.workflowDeleted'))
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      routeUpdateModeRef.current = 'push'
      if (selectedWorkflowId === id) {
        setSelectedWorkflowId(null)
        setIsDetailDrawerOpen(false)
      }
    } catch (_error) {
      message.error(t('list.messages.failedToDelete'))
    }
  }, [message, queryClient, selectedWorkflowId, t])

  const buildWorkflowLibraryHref = useCallback(({
    detailOpen,
    workflowId,
  }: {
    detailOpen?: boolean
    workflowId?: string | null
  } = {}) => {
    const next = new URLSearchParams()
    if (surface === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE) {
      next.set('surface', surface)
    }
    if (decisionDatabaseId) {
      next.set('database_id', decisionDatabaseId)
    }

    const currentTableState = latestTableRouteStateRef.current
    const routeSearch = searchParams.get('q') ?? ''
    const routeFilters = searchParams.get('filters') ?? ''
    const routeSort = searchParams.get('sort') ?? ''
    const normalizedSearch = tableRouteHydratedRef.current
      ? currentTableState.search.trim()
      : routeSearch.trim()
    const serializedFilters = tableRouteHydratedRef.current
      ? serializeRouteTableFilters(currentTableState.filters)
      : routeFilters
    const serializedSort = tableRouteHydratedRef.current
      ? serializeRouteTableSort(currentTableState.sort)
      : routeSort
    const nextWorkflowId = workflowId === undefined ? selectedWorkflowId ?? null : workflowId
    const nextDetailOpen = detailOpen ?? isDetailDrawerOpen

    if (normalizedSearch) {
      next.set('q', normalizedSearch)
    }
    if (serializedFilters) {
      next.set('filters', serializedFilters)
    }
    if (serializedSort) {
      next.set('sort', serializedSort)
    }
    if (nextWorkflowId) {
      next.set('workflow', nextWorkflowId)
    }
    if (nextWorkflowId && nextDetailOpen) {
      next.set('detail', '1')
    }

    return buildRelativeHref('/workflows', next)
  }, [decisionDatabaseId, isDetailDrawerOpen, searchParams, selectedWorkflowId, surface])

  const handleClone = useCallback(async (id: string, name: string) => {
    try {
      const cloned = await api.postWorkflowsCloneWorkflow({
        workflow_id: id,
        new_name: `${name} (Copy)`,
      })
      message.success(t('list.messages.workflowCloned'))
      navigate(buildWorkflowHref(cloned.workflow.id, {
        databaseId: decisionDatabaseId,
        returnTo: buildWorkflowLibraryHref({ workflowId: cloned.workflow.id, detailOpen: true }),
      }))
    } catch (_error) {
      message.error(t('list.messages.failedToClone'))
    }
  }, [buildWorkflowLibraryHref, decisionDatabaseId, message, navigate, t])

  const openWorkflow = useCallback((id: string, isSystemManaged?: boolean) => {
    navigate(buildWorkflowHref(id, {
      isSystemManaged,
      databaseId: decisionDatabaseId,
      returnTo: buildWorkflowLibraryHref({ workflowId: id, detailOpen: true }),
    }))
  }, [buildWorkflowLibraryHref, decisionDatabaseId, navigate])

  const table = useTableToolkit({
    tableId: 'workflows',
    columns: [],
    fallbackColumns: fallbackColumnConfigs,
    initialSearch: searchFromUrl,
    initialFiltersRaw: rawFiltersFromUrl,
    initialSortRaw: rawSortFromUrl,
    initialPageSize: 50,
  })
  const { setFilters: setTableFilters, setSearch: setTableSearch, setSort: setTableSort } = table

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const filtersParam = table.filtersPayload ? JSON.stringify(table.filtersPayload) : undefined
  const sortParam = table.sortPayload ? JSON.stringify(table.sortPayload) : undefined
  const routeFiltersFromUrl = useMemo(
    () => parseRouteTableFilters(searchParams.get('filters'), table.filterConfigs),
    [searchParams, table.filterConfigs]
  )
  const routeSortFromUrl = useMemo(
    () => parseRouteTableSort(searchParams.get('sort'), table.sortableColumns),
    [searchParams, table.sortableColumns]
  )
  const routeFiltersReady = useMemo(() => {
    const rawFilterCount = countRawRouteFilterKeys(rawFiltersFromUrl)
    if (rawFilterCount === 0) {
      return true
    }
    const recognizedFilterCount = Object.values(routeFiltersFromUrl).filter((value) => hasRouteFilterValue(value)).length
    return recognizedFilterCount === rawFilterCount
  }, [rawFiltersFromUrl, routeFiltersFromUrl])
  const routeSortReady = !rawSortFromUrl || Boolean(routeSortFromUrl.key && routeSortFromUrl.order)

  useEffect(() => {
    latestTableRouteStateRef.current = {
      search: table.search,
      filters: table.filters,
      sort: table.sort,
    }
  }, [table.filters, table.search, table.sort])

  useEffect(() => {
    pendingRouteFiltersRef.current = rawFiltersFromUrl
  }, [rawFiltersFromUrl])

  useEffect(() => {
    pendingRouteSortRef.current = rawSortFromUrl
  }, [rawSortFromUrl])

  useEffect(() => {
    const hasAppliedRouteFilters = Object.values(table.filters).some((value) => hasRouteFilterValue(value))
    if (hasAppliedRouteFilters) {
      pendingRouteFiltersRef.current = null
    }
  }, [table.filters])

  useEffect(() => {
    if (table.sort.key && table.sort.order) {
      pendingRouteSortRef.current = null
    }
  }, [table.sort.key, table.sort.order])

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

    if (!routeFiltersReady || !routeSortReady) {
      return
    }

    tableRouteHydratedRef.current = true
  }, [
    routeFiltersFromUrl,
    routeFiltersReady,
    routeSortFromUrl.key,
    routeSortFromUrl.order,
    routeSortReady,
    searchFromUrl,
    setTableFilters,
    setTableSearch,
    setTableSort,
  ])

  useEffect(() => {
    setSelectedWorkflowId((current) => {
      if (selectedWorkflowFromUrl) {
        return current === selectedWorkflowFromUrl ? current : selectedWorkflowFromUrl
      }
      return current === null ? current : null
    })
  }, [selectedWorkflowFromUrl])

  useEffect(() => {
    setIsDetailDrawerOpen((current) => (current === detailOpenFromUrl ? current : detailOpenFromUrl))
  }, [detailOpenFromUrl])

  const workflowsQuery = useQuery({
    queryKey: [
      'workflows',
      surface,
      table.search,
      table.filtersPayload,
      table.sortPayload,
      table.pagination.page,
      table.pagination.pageSize,
    ],
    queryFn: () => api.getWorkflowsListWorkflows({
      surface,
      search: table.search || undefined,
      filters: filtersParam,
      sort: sortParam,
      limit: table.pagination.pageSize,
      offset: pageStart,
    }),
  })

  const workflows = useMemo(
    () => workflowsQuery.data?.workflows ?? [],
    [workflowsQuery.data?.workflows]
  )
  const totalWorkflows = useMemo(
    () => workflowsQuery.data?.total ?? workflows.length,
    [workflows, workflowsQuery.data?.total]
  )
  const authoringPhase = useMemo(
    () => workflowsQuery.data?.authoring_phase ?? null,
    [workflowsQuery.data?.authoring_phase]
  )
  const selectedWorkflowSummary = workflows.find((workflow) => workflow.id === selectedWorkflowId) ?? null

  const selectedWorkflowDetailQuery = useQuery({
    queryKey: ['workflows', 'detail', selectedWorkflowId ?? ''],
    enabled: Boolean(selectedWorkflowId),
    queryFn: () => api.getWorkflowsGetWorkflow({ workflow_id: selectedWorkflowId ?? '' }),
  })

  const selectedWorkflowDetail = selectedWorkflowDetailQuery.data?.workflow ?? null
  const selectedWorkflow = selectedWorkflowDetail ?? selectedWorkflowSummary

  useEffect(() => {
    if (workflowsQuery.isLoading) {
      return
    }
    if (workflows.length === 0) {
      routeUpdateModeRef.current = 'replace'
      setSelectedWorkflowId(null)
      setIsDetailDrawerOpen(false)
      return
    }
    if (selectedWorkflowId) {
      if (workflows.some((workflow) => workflow.id === selectedWorkflowId)) {
        return
      }
      if (selectedWorkflowDetail?.id === selectedWorkflowId) {
        return
      }
      if (selectedWorkflowFromUrl === selectedWorkflowId && selectedWorkflowDetailQuery.isLoading) {
        return
      }
    }
    routeUpdateModeRef.current = 'replace'
    setSelectedWorkflowId(workflows[0]?.id ?? null)
  }, [
    selectedWorkflowDetail?.id,
    selectedWorkflowFromUrl,
    selectedWorkflowId,
    selectedWorkflowDetailQuery.isLoading,
    workflows,
    workflowsQuery.isLoading,
  ])

  useEffect(() => {
    if (tableRouteSyncRef.current) {
      tableRouteSyncRef.current = false
      return
    }
    if (!tableRouteHydratedRef.current) {
      return
    }
    if (!routeUrlSyncPrimedRef.current) {
      routeUrlSyncPrimedRef.current = true
      return
    }

    const next = new URLSearchParams(searchParams)
    const normalizedSearch = table.search.trim()
    const serializedFilters = serializeRouteTableFilters(table.filters)
    const serializedSort = serializeRouteTableSort(table.sort)
    const effectiveSerializedFilters = serializedFilters ?? pendingRouteFiltersRef.current
    const effectiveSerializedSort = serializedSort ?? pendingRouteSortRef.current

    if (normalizedSearch) {
      next.set('q', normalizedSearch)
    } else {
      next.delete('q')
    }

    if (effectiveSerializedFilters) {
      next.set('filters', effectiveSerializedFilters)
    } else {
      next.delete('filters')
    }

    if (effectiveSerializedSort) {
      next.set('sort', effectiveSerializedSort)
    } else {
      next.delete('sort')
    }

    if (selectedWorkflowId !== undefined) {
      if (selectedWorkflowId) {
        next.set('workflow', selectedWorkflowId)
      } else {
        next.delete('workflow')
      }
    }

    if (selectedWorkflowId !== undefined) {
      if (isDetailDrawerOpen && selectedWorkflowId) {
        next.set('detail', '1')
      } else {
        next.delete('detail')
      }
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
    isDetailDrawerOpen,
    searchParams,
    selectedWorkflowId,
    setSearchParams,
    table.filters,
    table.search,
    table.sort,
  ])

  const detailLoading = Boolean(selectedWorkflowId) && !selectedWorkflow && (workflowsQuery.isLoading || selectedWorkflowDetailQuery.isLoading)
  const detailError = selectedWorkflowId && !selectedWorkflow && selectedWorkflowDetailQuery.isError
    ? t('list.detail.failedToLoadSelected')
    : null
  const catalogError = workflowsQuery.isError
    ? t('list.detail.failedToLoadCatalog')
    : null
  const selectedWorkflowNodeCount = resolveNodeCount(selectedWorkflowSummary, selectedWorkflowDetail)
  const selectedWorkflowExecutionCount = selectedWorkflowDetail?.execution_count ?? selectedWorkflowSummary?.execution_count ?? 0
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
    return `${label}: ${table.sort.order === 'asc' ? t('sort.ascending') : t('sort.descending')}`
  }, [t, table.columnConfigs, table.sort.key, table.sort.order])
  const catalogStateToolbar = activeFilterSummaries.length > 0 || activeSortSummary
    ? (
      <Alert
        type="info"
        showIcon
        message={t('list.alerts.routeFiltersActive')}
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

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={isRuntimeDiagnosticsSurface ? t('list.page.runtimeTitle') : t('list.page.title')}
          subtitle={isRuntimeDiagnosticsSurface
            ? t('list.page.runtimeSubtitle')
            : t('list.page.subtitle')}
          actions={(
            <Space wrap>
              <Button
                icon={<ClockCircleOutlined />}
                onClick={() => navigate('/workflows/executions')}
              >
                {t('list.page.executions')}
              </Button>
              <Button
                onClick={() => {
                  routeUpdateModeRef.current = 'push'
                  const next = new URLSearchParams(searchParams)
                  if (isRuntimeDiagnosticsSurface) {
                    next.delete('surface')
                  } else {
                    next.set('surface', WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE)
                  }
                  setSearchParams(next)
                }}
              >
                {isRuntimeDiagnosticsSurface ? t('list.page.analystLibrary') : t('list.page.runtimeDiagnostics')}
              </Button>
              {!isRuntimeDiagnosticsSurface ? (
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => navigate(buildWorkflowHref('new', {
                    databaseId: decisionDatabaseId,
                    returnTo: buildWorkflowLibraryHref(),
                  }))}
                >
                  {t('list.page.newScheme')}
                </Button>
              ) : null}
            </Space>
          )}
        />
      )}
    >
      {isRuntimeDiagnosticsSurface ? (
        <Alert
          showIcon
          type="warning"
          message={t('list.alerts.runtimeSurfaceTitle')}
          description={t('list.alerts.runtimeSurfaceDescription')}
        />
      ) : null}

      {authoringPhase ? (
        <Alert
          showIcon
          type={authoringPhase.is_prerequisite_platform_phase ? 'info' : 'success'}
          message={authoringPhase.label}
          description={(
            <Space direction="vertical" size={4}>
              <span>{authoringPhase.description}</span>
              <span>{t('list.alerts.authoringPrimarySurface', { surface: authoringPhase.analyst_surface })}</span>
              <span>{t('list.alerts.authoringGuidance')}</span>
              <Space wrap size={[8, 8]}>
                {authoringPhase.rollout_scope.map((scope) => (
                  <Tag key={scope} color="blue">
                    {scope}
                  </Tag>
                ))}
                {authoringPhase.deferred_scope.map((scope) => (
                  <Tag key={scope} color="gold">
                    {t('list.alerts.deferred', { value: scope })}
                  </Tag>
                ))}
                {authoringPhase.follow_up_changes.map((changeId) => (
                  <Tag key={changeId} color="purple">
                    {t('list.alerts.followUp', { value: changeId })}
                  </Tag>
                ))}
              </Space>
            </Space>
          )}
        />
      ) : null}

      <MasterDetailShell
        detailOpen={isDetailDrawerOpen}
        onCloseDetail={() => {
          routeUpdateModeRef.current = 'push'
          setIsDetailDrawerOpen(false)
        }}
        detailDrawerTitle={selectedWorkflow?.name || t('list.detail.drawerTitle')}
        list={(
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <EntityList
              title={isRuntimeDiagnosticsSurface ? t('list.catalog.runtimeTitle') : t('list.catalog.title')}
              extra={(
                <Input.Search
                  aria-label={t('list.catalog.searchAriaLabel')}
                  allowClear
                  placeholder={t('list.catalog.searchPlaceholder')}
                  value={table.search}
                  onChange={(event) => table.setSearch(event.target.value)}
                  style={{ width: '100%', maxWidth: 260 }}
                />
              )}
              toolbar={catalogStateToolbar}
              error={catalogError}
              loading={workflowsQuery.isLoading}
              emptyDescription={t('list.catalog.emptyDescription')}
              dataSource={workflows}
              renderItem={(workflow) => {
                const selected = workflow.id === selectedWorkflowId
                const primarySummary = t('list.catalog.primarySummary', {
                  category: workflow.category || t('common.uncategorized'),
                  type: workflow.workflow_type || t('common.unknown'),
                  nodes: workflow.node_count ?? 0,
                })
                const secondarySummary = [
                  t('list.catalog.secondaryExecutionCount', { count: workflow.execution_count ?? 0 }),
                  t('list.catalog.secondaryUpdated', {
                    value: formatters.date(workflow.updated_at, { fallback: t('common.noValue') }),
                  }),
                  workflow.created_by_username || null,
                ].filter(Boolean).join(' · ')

                return (
                  <Button
                    key={workflow.id}
                    type="text"
                    block
                    data-testid={`workflow-list-catalog-item-${workflow.id}`}
                    aria-label={t('list.catalog.openWorkflow', { name: workflow.name })}
                    aria-pressed={selected}
                    onClick={() => {
                      routeUpdateModeRef.current = 'push'
                      setSelectedWorkflowId(workflow.id)
                      setIsDetailDrawerOpen(true)
                    }}
                    style={buildCatalogButtonStyle(selected)}
                  >
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                      <Space wrap size={[8, 8]}>
                        <Text strong>{workflow.name}</Text>
                        {workflow.is_system_managed ? <Tag color="gold">{t('common.systemManaged')}</Tag> : null}
                      </Space>
                      <Space wrap size={[8, 8]}>
                        {renderStatusSummary(workflow, t)}
                      </Space>
                      <Text type="secondary">{primarySummary}</Text>
                      <Text type="secondary">{secondarySummary}</Text>
                    </Space>
                  </Button>
                )
              }}
            />
            <Pagination
              size="small"
              current={table.pagination.page}
              pageSize={table.pagination.pageSize}
              total={totalWorkflows}
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
            title={t('list.detail.title')}
            loading={detailLoading}
            error={detailError}
            empty={!selectedWorkflowId || (!selectedWorkflow && !detailLoading)}
            emptyDescription={t('list.detail.emptyDescription')}
            extra={selectedWorkflow ? (
              <Space wrap>
                <Button
                  data-testid="workflow-list-detail-open"
                  onClick={() => openWorkflow(selectedWorkflow.id, selectedWorkflow.is_system_managed)}
                >
                  {selectedWorkflow.is_system_managed ? t('list.detail.inspectWorkflow') : t('list.detail.editWorkflow')}
                </Button>
                {!selectedWorkflow.is_system_managed ? (
                  <>
                    <Button
                      data-testid="workflow-list-detail-clone"
                      onClick={() => void handleClone(selectedWorkflow.id, selectedWorkflow.name)}
                    >
                      {t('list.detail.clone')}
                    </Button>
                    <Button
                      type="primary"
                      data-testid="workflow-list-detail-execute"
                      disabled={!selectedWorkflow.is_valid}
                      onClick={() => navigate(buildWorkflowHref(selectedWorkflow.id, {
                        databaseId: decisionDatabaseId,
                        execute: true,
                        returnTo: buildWorkflowLibraryHref({ workflowId: selectedWorkflow.id, detailOpen: true }),
                      }))}
                    >
                      {t('list.detail.execute')}
                    </Button>
                    <Popconfirm
                      title={t('list.detail.deleteConfirmTitle')}
                      description={t('list.detail.deleteConfirmDescription')}
                      onConfirm={() => handleDelete(selectedWorkflow.id)}
                      okText={t('list.detail.deleteConfirmOk')}
                      okButtonProps={{ danger: true }}
                    >
                      <Button danger data-testid="workflow-list-detail-delete">{t('list.detail.delete')}</Button>
                    </Popconfirm>
                  </>
                ) : null}
              </Space>
            ) : undefined}
          >
            {selectedWorkflow ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                {selectedWorkflow.is_system_managed ? (
                  <Alert
                    type="warning"
                    showIcon
                    message={t('list.alerts.systemManagedTitle')}
                    description={selectedWorkflow.read_only_reason || t('list.alerts.systemManagedDescription')}
                  />
                ) : null}

                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label={t('list.detail.fields.name')}>
                    <Text strong data-testid="workflow-list-selected-name">{selectedWorkflow.name}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.workflowId')}>
                    <Text code data-testid="workflow-list-selected-id">{selectedWorkflow.id}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.status')}>
                    {renderStatusSummary(selectedWorkflow, t)}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.category')}>{selectedWorkflow.category}</Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.workflowType')}>
                    <Tag color={workflowTypeColors[String(selectedWorkflow.workflow_type)] || 'default'}>
                      {String(selectedWorkflow.workflow_type || t('common.unknown'))}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.managementMode')}>{selectedWorkflow.management_mode}</Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.visibilitySurface')}>{selectedWorkflow.visibility_surface}</Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.version')}>{selectedWorkflow.version_number}</Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.nodes')}>{selectedWorkflowNodeCount}</Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.executions')}>{selectedWorkflowExecutionCount}</Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.createdBy')}>
                    {selectedWorkflow.created_by_username || t('common.noValue')}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.createdAt')}>
                    {formatters.dateTime(selectedWorkflow.created_at, { fallback: t('common.noValue') })}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.updatedAt')}>
                    {formatters.dateTime(selectedWorkflow.updated_at, { fallback: t('common.noValue') })}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('list.detail.fields.description')}>
                    {selectedWorkflow.description || t('common.noValue')}
                  </Descriptions.Item>
                </Descriptions>

                {selectedWorkflowDetail ? (
                  <>
                    <JsonBlock
                      title={t('list.detail.dagStructure')}
                      value={selectedWorkflowDetail.dag_structure}
                      dataTestId="workflow-list-selected-dag"
                      height={260}
                    />
                    <JsonBlock
                      title={t('list.detail.workflowConfig')}
                      value={selectedWorkflowDetail.config ?? {}}
                      dataTestId="workflow-list-selected-config"
                      height={220}
                    />
                  </>
                ) : null}
              </Space>
            ) : null}
          </EntityDetails>
        )}
      />
    </WorkspacePage>
  )
}

export default WorkflowList
