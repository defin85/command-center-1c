import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Descriptions,
  Grid,
  Input,
  Space,
  Table,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate, useSearchParams } from 'react-router-dom'

import {
  EntityDetails,
  EntityList,
  JsonBlock,
  MasterDetailShell,
  PageHeader,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import { useLocaleFormatters, usePoolsTranslation } from '../../i18n'
import {
  useCreatePoolTopologyTemplate,
  usePoolTopologyTemplates,
  useRevisePoolTopologyTemplate,
} from '../../api/queries/poolTopologyTemplates'
import type {
  CreatePoolTopologyTemplatePayload,
  CreatePoolTopologyTemplateRevisionPayload,
  PoolTopologyTemplate,
  PoolTopologyTemplateEdge,
  PoolTopologyTemplateNode,
  PoolTopologyTemplateRevision,
} from '../../api/intercompanyPools'
import { buildPoolCatalogRoute } from './routes'
import { PoolTopologyTemplatesEditorDrawer } from './PoolTopologyTemplatesEditorDrawer'
import { resolveApiError } from './masterData/errorUtils'

const { Text } = Typography
const { useBreakpoint } = Grid
const DESKTOP_BREAKPOINT_PX = 992

type TopologyTemplatesComposeMode = 'create' | 'revise' | null

const normalizeRouteParam = (value: string | null) => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

const parseComposeMode = (value: string | null): TopologyTemplatesComposeMode => {
  if (value === 'create' || value === 'revise') {
    return value
  }
  return null
}

const filterTopologyTemplates = (templates: PoolTopologyTemplate[], searchTerm: string) => {
  const normalizedSearch = searchTerm.trim().toLowerCase()
  if (!normalizedSearch) {
    return templates
  }

  return templates.filter((template) => (
    [
      template.code,
      template.name,
      template.description ?? '',
      String(template.latest_revision_number),
    ]
      .join(' ')
      .toLowerCase()
      .includes(normalizedSearch)
  ))
}

const renderNodeSummary = (
  nodes: PoolTopologyTemplateNode[],
  options: {
    fallback: string
    rootSuffix: string
  },
) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
    {nodes.map((node) => (
      <div key={node.slot_key}>
        <Text strong>{node.slot_key}</Text>
        <Text type="secondary">
          {' '}
          {node.label || options.fallback}
          {' '}
          {node.is_root ? options.rootSuffix : ''}
        </Text>
      </div>
    ))}
  </div>
)

const renderEdgeSummary = (
  edges: PoolTopologyTemplateEdge[],
  weightLabel: (value: string) => string,
) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
    {edges.map((edge) => (
      <div key={`${edge.parent_slot_key}:${edge.child_slot_key}`}>
        <Text strong>{`${edge.parent_slot_key} -> ${edge.child_slot_key}`}</Text>
        <Text type="secondary">
          {' '}
          {weightLabel(edge.weight)}
          {edge.document_policy_key ? ` · ${edge.document_policy_key}` : ''}
        </Text>
      </div>
    ))}
  </div>
)

const buildCatalogButtonStyle = (selected: boolean) => ({
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

export function PoolTopologyTemplatesPage() {
  const { message } = AntApp.useApp()
  const { t } = usePoolsTranslation()
  const formatters = useLocaleFormatters()
  const screens = useBreakpoint()
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.lg
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < DESKTOP_BREAKPOINT_PX
        : false
    )
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const detailRouteSyncInitializedRef = useRef(false)
  const searchFromUrl = searchParams.get('q') ?? ''
  const selectedTemplateFromUrl = normalizeRouteParam(searchParams.get('template'))
  const detailOpenFromUrl = searchParams.get('detail') === '1'
  const composeModeFromUrl = parseComposeMode(searchParams.get('compose'))
  const returnPoolId = normalizeRouteParam(searchParams.get('return_pool_id'))
  const returnTab = normalizeRouteParam(searchParams.get('return_tab')) ?? 'topology'
  const returnDate = normalizeRouteParam(searchParams.get('return_date'))
  const [search, setSearch] = useState(searchFromUrl)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null | undefined>(
    () => selectedTemplateFromUrl ?? undefined
  )
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(detailOpenFromUrl)
  const [composeMode, setComposeMode] = useState<TopologyTemplatesComposeMode>(composeModeFromUrl)
  const [actionError, setActionError] = useState<string | null>(null)
  const deferredSearch = useDeferredValue(search)
  const formatDateTime = useCallback(
    (value?: string | null) => formatters.dateTime(value, { fallback: t('common.noValue') }),
    [formatters, t]
  )
  const formatEdgeWeight = useCallback(
    (value: string) => t('topologyTemplates.detail.edgeWeight', { value }),
    [t]
  )

  const topologyTemplatesQuery = usePoolTopologyTemplates()
  const createTopologyTemplateMutation = useCreatePoolTopologyTemplate()
  const reviseTopologyTemplateMutation = useRevisePoolTopologyTemplate()

  useEffect(() => {
    setSearch((current) => (current === searchFromUrl ? current : searchFromUrl))
  }, [searchFromUrl])

  useEffect(() => {
    setSelectedTemplateId((current) => {
      if (selectedTemplateFromUrl) {
        return current === selectedTemplateFromUrl ? current : selectedTemplateFromUrl
      }

      if (!detailRouteSyncInitializedRef.current && current === undefined) {
        return current
      }

      return current === null ? current : null
    })
    detailRouteSyncInitializedRef.current = true
  }, [selectedTemplateFromUrl])

  useEffect(() => {
    setIsDetailDrawerOpen((current) => (current === detailOpenFromUrl ? current : detailOpenFromUrl))
  }, [detailOpenFromUrl])

  useEffect(() => {
    setComposeMode((current) => (current === composeModeFromUrl ? current : composeModeFromUrl))
  }, [composeModeFromUrl])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    const normalizedSearch = search.trim()

    if (normalizedSearch) {
      next.set('q', normalizedSearch)
    } else {
      next.delete('q')
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
  }, [composeMode, isDetailDrawerOpen, search, searchParams, selectedTemplateId, setSearchParams])

  const topologyTemplates = useMemo(
    () => topologyTemplatesQuery.data ?? [],
    [topologyTemplatesQuery.data],
  )
  const filteredTemplates = useMemo(
    () => filterTopologyTemplates(topologyTemplates, deferredSearch),
    [topologyTemplates, deferredSearch],
  )

  useEffect(() => {
    if (topologyTemplatesQuery.isLoading) {
      return
    }
    if (!filteredTemplates.length) {
      routeUpdateModeRef.current = 'replace'
      setSelectedTemplateId(null)
      setIsDetailDrawerOpen(false)
      return
    }
    if (selectedTemplateId && filteredTemplates.some((item) => item.topology_template_id === selectedTemplateId)) {
      return
    }
    routeUpdateModeRef.current = 'replace'
    setSelectedTemplateId(filteredTemplates[0].topology_template_id)
  }, [filteredTemplates, selectedTemplateId, topologyTemplatesQuery.isLoading])

  const selectedTemplate = useMemo(
    () => filteredTemplates.find((item) => item.topology_template_id === selectedTemplateId)
      ?? topologyTemplates.find((item) => item.topology_template_id === selectedTemplateId)
      ?? null,
    [filteredTemplates, selectedTemplateId, topologyTemplates]
  )
  const detailDrawerOpen = isDetailDrawerOpen && composeMode === null

  const returnRoute = useMemo(
    () => buildPoolCatalogRoute({
      poolId: returnPoolId,
      tab: returnTab,
      date: returnDate,
    }),
    [returnDate, returnPoolId, returnTab]
  )

  const revisionColumns: ColumnsType<PoolTopologyTemplateRevision> = [
    {
      title: t('common.revision'),
      dataIndex: 'revision_number',
      key: 'revision_number',
      render: (value: number) => `r${value}`,
    },
    {
      title: t('topologyTemplates.revisions.nodes'),
      key: 'nodes',
      render: (_value, record) => record.nodes.length,
    },
    {
      title: t('topologyTemplates.revisions.edges'),
      key: 'edges',
      render: (_value, record) => record.edges.length,
    },
    {
      title: t('topologyTemplates.revisions.createdAt'),
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => formatDateTime(value),
    },
  ]

  const handleReturnToPoolTopology = () => {
    navigate(returnRoute)
  }

  const handleCreateSubmit = async (
    request: CreatePoolTopologyTemplatePayload | CreatePoolTopologyTemplateRevisionPayload,
  ) => {
    const response = await createTopologyTemplateMutation.mutateAsync(request as CreatePoolTopologyTemplatePayload)
    const created = response.topology_template
    setActionError(null)
    routeUpdateModeRef.current = 'replace'
    setSelectedTemplateId(created.topology_template_id)
    setIsDetailDrawerOpen(true)
    setComposeMode(null)
    message.success(t('topologyTemplates.messages.created'))
  }

  const handleReviseSubmit = async (
    request: CreatePoolTopologyTemplatePayload | CreatePoolTopologyTemplateRevisionPayload,
  ) => {
    if (!selectedTemplate) return
    await reviseTopologyTemplateMutation.mutateAsync({
      topologyTemplateId: selectedTemplate.topology_template_id,
      request: request as CreatePoolTopologyTemplateRevisionPayload,
    })
    setActionError(null)
    routeUpdateModeRef.current = 'replace'
    setComposeMode(null)
    message.success(t('topologyTemplates.messages.revisionPublished'))
  }

  const listError = topologyTemplatesQuery.isError
    ? resolveApiError(topologyTemplatesQuery.error, t('topologyTemplates.messages.failedToLoad')).message
    : null

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t('topologyTemplates.page.title')}
          subtitle={t('topologyTemplates.page.subtitle')}
          actions={(
            <Space wrap>
              {returnPoolId ? (
                <Button onClick={handleReturnToPoolTopology}>
                  {t('topologyTemplates.page.returnToPool')}
                </Button>
              ) : null}
              <Button
                type="primary"
                onClick={() => {
                  routeUpdateModeRef.current = 'push'
                  setComposeMode('create')
                }}
              >
                {t('topologyTemplates.page.create')}
              </Button>
            </Space>
          )}
        />
      )}
    >
      {actionError ? (
        <Alert type="error" showIcon message={actionError} />
      ) : null}

      <MasterDetailShell
        detailOpen={detailDrawerOpen}
        onCloseDetail={() => {
          routeUpdateModeRef.current = 'push'
          setIsDetailDrawerOpen(false)
        }}
        detailDrawerTitle={selectedTemplate?.name || t('topologyTemplates.detail.drawerTitle')}
        list={(
          <EntityList
            title={t('topologyTemplates.list.title')}
            extra={(
              <Input
                aria-label={t('topologyTemplates.list.searchAriaLabel')}
                allowClear
                autoComplete="off"
                name="topology-template-search"
                placeholder={t('topologyTemplates.list.searchPlaceholder')}
                value={search}
                onChange={(event) => {
                  routeUpdateModeRef.current = 'push'
                  setSearch(event.target.value)
                }}
                style={{ width: isNarrow ? '100%' : 260 }}
              />
            )}
            error={listError}
            loading={topologyTemplatesQuery.isLoading}
            emptyDescription={t('topologyTemplates.list.emptyDescription')}
            dataSource={filteredTemplates}
            renderItem={(template) => {
              const selected = template.topology_template_id === selectedTemplateId

              return (
                <Button
                  key={template.topology_template_id}
                  type="text"
                  block
                  aria-label={t('topologyTemplates.list.openTemplate', { code: template.code })}
                  aria-pressed={selected}
                  onClick={() => {
                    routeUpdateModeRef.current = 'push'
                    setSelectedTemplateId(template.topology_template_id)
                    setIsDetailDrawerOpen(true)
                  }}
                  style={buildCatalogButtonStyle(selected)}
                >
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Space wrap size={[8, 8]}>
                      <Text strong>{template.name}</Text>
                      <StatusBadge status={template.status} />
                      <Text code>{template.code}</Text>
                    </Space>
                    <Text type="secondary">
                      {t('topologyTemplates.list.latestRevision', { value: template.latest_revision_number })}
                    </Text>
                    <Text type="secondary">
                      {template.description || t('topologyTemplates.list.noDescription')}
                    </Text>
                  </Space>
                </Button>
              )
            }}
          />
        )}
        detail={(
          <EntityDetails
            title={t('topologyTemplates.detail.title')}
            loading={topologyTemplatesQuery.isLoading}
            error={listError}
            empty={!selectedTemplateId || (!selectedTemplate && !topologyTemplatesQuery.isLoading)}
            emptyDescription={t('topologyTemplates.detail.emptyDescription')}
          >
            {selectedTemplate ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }} data-testid="pool-topology-templates-detail-surface">
                <div
                  style={{
                    display: 'flex',
                    flexDirection: isNarrow ? 'column' : 'row',
                    flexWrap: isNarrow ? 'nowrap' : 'wrap',
                    gap: 12,
                    width: '100%',
                  }}
                >
                  <Button
                    onClick={() => {
                      routeUpdateModeRef.current = 'push'
                      setComposeMode('revise')
                    }}
                    style={{ width: isNarrow ? '100%' : 'auto', whiteSpace: 'normal', height: 'auto' }}
                  >
                      {t('topologyTemplates.page.publishRevision')}
                    </Button>
                </div>

                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label={t('common.code')}>
                    <Text strong data-testid="pool-topology-templates-selected-code">
                      {selectedTemplate.code}
                    </Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.name')}>{selectedTemplate.name}</Descriptions.Item>
                  <Descriptions.Item label={t('common.status')}>
                    <span data-testid="pool-topology-templates-status">
                      <StatusBadge status={selectedTemplate.status} />
                    </span>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.latestRevisionNumber')}>
                    {`r${selectedTemplate.latest_revision_number}`}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.description')}>
                    {selectedTemplate.description || t('common.noValue')}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.updatedAt')}>
                    {formatDateTime(selectedTemplate.updated_at)}
                  </Descriptions.Item>
                </Descriptions>

                {!isNarrow ? (
                  <div data-testid="pool-topology-templates-revisions">
                    <Table
                      size="small"
                      pagination={false}
                      columns={revisionColumns}
                      dataSource={selectedTemplate.revisions}
                      rowKey="topology_template_revision_id"
                    />
                  </div>
                ) : (
                  <Space direction="vertical" size="small" style={{ width: '100%' }} data-testid="pool-topology-templates-revisions">
                    {selectedTemplate.revisions.map((revision) => (
                      <div
                        key={revision.topology_template_revision_id}
                        style={{
                          border: '1px solid #f0f0f0',
                          borderRadius: 8,
                          padding: 12,
                        }}
                      >
                        <Space direction="vertical" size={2} style={{ width: '100%' }}>
                          <Text strong>{`r${revision.revision_number}`}</Text>
                          <Text type="secondary">{t('topologyTemplates.revisions.compactNodes', { count: revision.nodes.length })}</Text>
                          <Text type="secondary">{t('topologyTemplates.revisions.compactEdges', { count: revision.edges.length })}</Text>
                          <Text type="secondary">{t('topologyTemplates.revisions.compactCreatedAt', { value: formatDateTime(revision.created_at) })}</Text>
                        </Space>
                      </div>
                    ))}
                  </Space>
                )}

                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label={t('topologyTemplates.detail.latestRevisionNodes')}>
                    {renderNodeSummary(selectedTemplate.latest_revision.nodes, {
                      fallback: t('topologyTemplates.detail.nodeSummaryFallback'),
                      rootSuffix: t('topologyTemplates.detail.rootSuffix'),
                    })}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('topologyTemplates.detail.latestRevisionEdges')}>
                    {selectedTemplate.latest_revision.edges.length > 0
                      ? renderEdgeSummary(selectedTemplate.latest_revision.edges, formatEdgeWeight)
                      : <Text type="secondary">{t('topologyTemplates.detail.noAbstractEdges')}</Text>}
                  </Descriptions.Item>
                </Descriptions>

                <JsonBlock title={t('topologyTemplates.detail.templateMetadata')} value={selectedTemplate.metadata} />
                <JsonBlock title={t('topologyTemplates.detail.latestRevisionMetadata')} value={selectedTemplate.latest_revision.metadata} />
              </Space>
            ) : null}
          </EntityDetails>
        )}
      />

      <PoolTopologyTemplatesEditorDrawer
        open={composeMode === 'create'}
        mode="create"
        onCancel={() => {
          if (createTopologyTemplateMutation.isPending) return
          routeUpdateModeRef.current = 'push'
          setComposeMode(null)
        }}
        onSubmit={handleCreateSubmit}
      />
      <PoolTopologyTemplatesEditorDrawer
        open={composeMode === 'revise'}
        mode="revise"
        template={selectedTemplate}
        onCancel={() => {
          if (reviseTopologyTemplateMutation.isPending) return
          routeUpdateModeRef.current = 'push'
          setComposeMode(null)
        }}
        onSubmit={handleReviseSubmit}
      />
    </WorkspacePage>
  )
}
