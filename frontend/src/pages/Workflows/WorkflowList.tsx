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

const formatDateTime = (value: string | null | undefined) => (
  value ? new Date(value).toLocaleString() : '—'
)

const formatCompactDateTime = (value: string | null | undefined) => (
  value ? new Date(value).toLocaleDateString() : '—'
)

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

const renderStatusSummary = (workflow: Pick<WorkflowTemplateList, 'is_active' | 'is_valid' | 'visibility_surface'>) => (
  <Space wrap size={8}>
    <StatusBadge
      status={workflow.is_active ? 'active' : 'inactive'}
      label={workflow.is_active ? 'Active' : 'Inactive'}
    />
    <StatusBadge
      status={workflow.is_valid ? 'compatible' : 'error'}
      label={workflow.is_valid ? 'Valid' : 'Invalid'}
    />
    <StatusBadge
      status={workflow.visibility_surface === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE ? 'warning' : 'unknown'}
      label={workflow.visibility_surface === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE ? 'Runtime diagnostics' : 'Analyst library'}
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
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'workflow_type', label: 'Type', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'is_active', label: 'Status', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'node_count', label: 'Nodes', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'updated_at', label: 'Updated', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'actions', label: 'Actions', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const handleDelete = useCallback(async (id: string) => {
    try {
      await api.postWorkflowsDeleteWorkflow({ workflow_id: id })
      message.success('Workflow deleted')
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      routeUpdateModeRef.current = 'push'
      if (selectedWorkflowId === id) {
        setSelectedWorkflowId(null)
        setIsDetailDrawerOpen(false)
      }
    } catch (_error) {
      message.error('Failed to delete workflow')
    }
  }, [message, queryClient, selectedWorkflowId])

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
      message.success('Workflow cloned')
      navigate(buildWorkflowHref(cloned.workflow.id, {
        databaseId: decisionDatabaseId,
        returnTo: buildWorkflowLibraryHref({ workflowId: cloned.workflow.id, detailOpen: true }),
      }))
    } catch (_error) {
      message.error('Failed to clone workflow')
    }
  }, [buildWorkflowLibraryHref, decisionDatabaseId, message, navigate])

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
    ? 'Failed to load the selected workflow.'
    : null
  const catalogError = workflowsQuery.isError
    ? 'Failed to load workflow catalog.'
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
    return `${label}: ${table.sort.order === 'asc' ? 'ascending' : 'descending'}`
  }, [table.columnConfigs, table.sort.key, table.sort.order])
  const catalogStateToolbar = activeFilterSummaries.length > 0 || activeSortSummary
    ? (
      <Alert
        type="info"
        showIcon
        message="Route filters active"
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
          title={isRuntimeDiagnosticsSurface ? 'Workflow Runtime Diagnostics' : 'Workflow Scheme Library'}
          subtitle={isRuntimeDiagnosticsSurface
            ? 'Read-only generated projections compiled from pool bindings and analyst-authored definitions.'
            : 'Reusable analyst-authored workflow definitions for pool distribution and publication.'}
          actions={(
            <Space wrap>
              <Button
                icon={<ClockCircleOutlined />}
                onClick={() => navigate('/workflows/executions')}
              >
                Executions
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
                {isRuntimeDiagnosticsSurface ? 'Analyst Library' : 'Runtime Diagnostics'}
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
                  New Scheme
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
          message="Runtime diagnostics surface"
          description="System-managed runtime workflow projections are listed separately and remain read-only."
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
              <span>{`Primary analyst surface: ${authoringPhase.analyst_surface}`}</span>
              <span>
                Compose analyst-authored schemes in /workflows. Use /templates for atomic
                operations and /decisions for versioned decision resources.
              </span>
              <Space wrap size={[8, 8]}>
                {authoringPhase.rollout_scope.map((scope) => (
                  <Tag key={scope} color="blue">
                    {scope}
                  </Tag>
                ))}
                {authoringPhase.deferred_scope.map((scope) => (
                  <Tag key={scope} color="gold">
                    {`Deferred: ${scope}`}
                  </Tag>
                ))}
                {authoringPhase.follow_up_changes.map((changeId) => (
                  <Tag key={changeId} color="purple">
                    {`Follow-up: ${changeId}`}
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
        detailDrawerTitle={selectedWorkflow?.name || 'Workflow detail'}
        list={(
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <EntityList
              title={isRuntimeDiagnosticsSurface ? 'Runtime Workflow Catalog' : 'Workflow Catalog'}
              extra={(
                <Input.Search
                  aria-label="Search workflows"
                  allowClear
                  placeholder="Search workflow schemes"
                  value={table.search}
                  onChange={(event) => table.setSearch(event.target.value)}
                  style={{ width: '100%', maxWidth: 260 }}
                />
              )}
              toolbar={catalogStateToolbar}
              error={catalogError}
              loading={workflowsQuery.isLoading}
              emptyDescription="No workflows match the current catalog state."
              dataSource={workflows}
              renderItem={(workflow) => {
                const selected = workflow.id === selectedWorkflowId
                const primarySummary = [
                  workflow.category || 'uncategorized',
                  workflow.workflow_type || 'unknown',
                  `${workflow.node_count ?? 0} node(s)`,
                ].join(' · ')
                const secondarySummary = [
                  `${workflow.execution_count ?? 0} execution(s)`,
                  `Updated ${formatCompactDateTime(workflow.updated_at)}`,
                  workflow.created_by_username || null,
                ].filter(Boolean).join(' · ')

                return (
                  <Button
                    key={workflow.id}
                    type="text"
                    block
                    data-testid={`workflow-list-catalog-item-${workflow.id}`}
                    aria-label={`Open workflow ${workflow.name}`}
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
                        {workflow.is_system_managed ? <Tag color="gold">System managed</Tag> : null}
                      </Space>
                      <Space wrap size={[8, 8]}>
                        {renderStatusSummary(workflow)}
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
            title="Workflow detail"
            loading={detailLoading}
            error={detailError}
            empty={!selectedWorkflowId || (!selectedWorkflow && !detailLoading)}
            emptyDescription="Select a workflow from the library to inspect authoring context and runtime posture."
            extra={selectedWorkflow ? (
              <Space wrap>
                <Button
                  data-testid="workflow-list-detail-open"
                  onClick={() => openWorkflow(selectedWorkflow.id, selectedWorkflow.is_system_managed)}
                >
                  {selectedWorkflow.is_system_managed ? 'Inspect workflow' : 'Edit workflow'}
                </Button>
                {!selectedWorkflow.is_system_managed ? (
                  <>
                    <Button
                      data-testid="workflow-list-detail-clone"
                      onClick={() => void handleClone(selectedWorkflow.id, selectedWorkflow.name)}
                    >
                      Clone
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
                      Execute
                    </Button>
                    <Popconfirm
                      title="Delete workflow?"
                      description="This action cannot be undone."
                      onConfirm={() => handleDelete(selectedWorkflow.id)}
                      okText="Delete"
                      okButtonProps={{ danger: true }}
                    >
                      <Button danger data-testid="workflow-list-detail-delete">Delete</Button>
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
                    message="System-managed runtime projection"
                    description={selectedWorkflow.read_only_reason || 'This workflow is generated for runtime diagnostics and remains read-only.'}
                  />
                ) : null}

                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label="Name">
                    <Text strong data-testid="workflow-list-selected-name">{selectedWorkflow.name}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Workflow ID">
                    <Text code data-testid="workflow-list-selected-id">{selectedWorkflow.id}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Status">
                    {renderStatusSummary(selectedWorkflow)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Category">{selectedWorkflow.category}</Descriptions.Item>
                  <Descriptions.Item label="Workflow type">
                    <Tag color={workflowTypeColors[String(selectedWorkflow.workflow_type)] || 'default'}>
                      {String(selectedWorkflow.workflow_type || 'unknown')}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Management mode">{selectedWorkflow.management_mode}</Descriptions.Item>
                  <Descriptions.Item label="Visibility surface">{selectedWorkflow.visibility_surface}</Descriptions.Item>
                  <Descriptions.Item label="Version">{selectedWorkflow.version_number}</Descriptions.Item>
                  <Descriptions.Item label="Nodes">{selectedWorkflowNodeCount}</Descriptions.Item>
                  <Descriptions.Item label="Executions">{selectedWorkflowExecutionCount}</Descriptions.Item>
                  <Descriptions.Item label="Created by">
                    {selectedWorkflow.created_by_username || '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Created at">{formatDateTime(selectedWorkflow.created_at)}</Descriptions.Item>
                  <Descriptions.Item label="Updated at">{formatDateTime(selectedWorkflow.updated_at)}</Descriptions.Item>
                  <Descriptions.Item label="Description">{selectedWorkflow.description || '—'}</Descriptions.Item>
                </Descriptions>

                {selectedWorkflowDetail ? (
                  <>
                    <JsonBlock
                      title="DAG structure"
                      value={selectedWorkflowDetail.dag_structure}
                      dataTestId="workflow-list-selected-dag"
                      height={260}
                    />
                    <JsonBlock
                      title="Workflow config"
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
