import { useEffect, useMemo, useState } from 'react'
import { Alert, Space, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'

import type { OrganizationPool } from '../../api/intercompanyPools'
import { listOrganizationPools } from '../../api/intercompanyPools'
import { queryKeys } from '../../api/queries/queryKeys'
import {
  EntityDetails,
  EntityList,
  MasterDetailShell,
  PageHeader,
  RouteButton,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import { queryClient } from '../../lib/queryClient'
import { withQueryPolicy } from '../../lib/queryRuntime'
import { resolveApiError } from './masterData/errorUtils'
import { PoolFactualWorkspaceDetail } from './PoolFactualWorkspaceDetail'
import {
  buildPoolCatalogRoute,
  buildPoolRunsRoute,
  POOL_FACTUAL_ROUTE,
  POOL_RUNS_ROUTE,
} from './routes'

const { Text } = Typography

type PoolFactualFocus = 'summary' | 'settlement' | 'drilldown' | 'review'

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

const normalizeFactualFocus = (value: string | null): PoolFactualFocus => {
  switch (value?.trim()) {
    case 'summary':
      return 'summary'
    case 'settlement':
      return 'settlement'
    case 'drilldown':
      return 'drilldown'
    case 'review':
      return 'review'
    default:
      return 'summary'
  }
}

const formatShortId = (value: string | null | undefined) => {
  if (!value) {
    return '-'
  }
  return value.slice(0, 8)
}

export function PoolFactualWorkspacePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const poolFromUrl = normalizeRouteParam(searchParams.get('pool'))
  const runFromUrl = normalizeRouteParam(searchParams.get('run'))
  const quarterStartFromUrl = normalizeRouteParam(searchParams.get('quarter_start'))
  const focusFromUrl = normalizeFactualFocus(searchParams.get('focus'))
  const detailOpenFromUrl = searchParams.get('detail') === '1'

  const [pools, setPools] = useState<OrganizationPool[]>([])
  const [selectedPoolId, setSelectedPoolId] = useState<string | null>(poolFromUrl)
  const [isDetailOpen, setIsDetailOpen] = useState(detailOpenFromUrl)
  const [loadingPools, setLoadingPools] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    setSelectedPoolId((current) => (current === poolFromUrl ? current : poolFromUrl))
  }, [poolFromUrl])

  useEffect(() => {
    setIsDetailOpen((current) => (current === detailOpenFromUrl ? current : detailOpenFromUrl))
  }, [detailOpenFromUrl])

  useEffect(() => {
    let cancelled = false

    const loadPools = async () => {
      setLoadingPools(true)
      setLoadError(null)

      try {
        const data = await queryClient.fetchQuery(withQueryPolicy('interactive', {
          queryKey: queryKeys.poolCatalog.pools(),
          queryFn: () => listOrganizationPools(),
        }))
        if (cancelled) {
          return
        }
        setPools(data)
      } catch (error) {
        if (cancelled) {
          return
        }
        const resolved = resolveApiError(error, 'Failed to load pools for the factual workspace.')
        setLoadError(resolved.message)
      } finally {
        if (!cancelled) {
          setLoadingPools(false)
        }
      }
    }

    void loadPools()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)

    if (selectedPoolId) {
      next.set('pool', selectedPoolId)
    } else {
      next.delete('pool')
    }

    if (runFromUrl) {
      next.set('run', runFromUrl)
    } else {
      next.delete('run')
    }

    if (quarterStartFromUrl) {
      next.set('quarter_start', quarterStartFromUrl)
    } else {
      next.delete('quarter_start')
    }

    if (focusFromUrl && focusFromUrl !== 'summary') {
      next.set('focus', focusFromUrl)
    } else {
      next.delete('focus')
    }

    if (isDetailOpen && selectedPoolId) {
      next.set('detail', '1')
    } else {
      next.delete('detail')
    }

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [focusFromUrl, isDetailOpen, quarterStartFromUrl, runFromUrl, searchParams, selectedPoolId, setSearchParams])

  const selectedPool = useMemo(
    () => pools.find((pool) => pool.id === selectedPoolId) ?? null,
    [pools, selectedPoolId]
  )

  const runWorkspaceHref = buildPoolRunsRoute({
    poolId: selectedPoolId,
    runId: runFromUrl,
    stage: runFromUrl ? 'inspect' : null,
    detail: Boolean(runFromUrl),
  })

  const poolCatalogHref = buildPoolCatalogRoute({
    poolId: selectedPoolId,
  })

  const handleSelectPool = (poolId: string) => {
    setSelectedPoolId(poolId)
    setIsDetailOpen(true)
  }

  const handleCloseDetail = () => {
    setIsDetailOpen(false)
  }

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="Pool Factual Monitoring"
          subtitle={(
            <>
              Separate operator workspace on <Text code>{POOL_FACTUAL_ROUTE}</Text> for factual balances,
              settlement state, and manual review without turning <Text code>{POOL_RUNS_ROUTE}</Text> into a
              mixed execution dashboard.
            </>
          )}
          actions={(
            <Space wrap>
              <RouteButton to={runWorkspaceHref}>Open Pool Runs</RouteButton>
              <RouteButton type="primary" to={poolCatalogHref} disabled={!selectedPoolId}>
                Open Pool Catalog
              </RouteButton>
            </Space>
          )}
        />
      )}
    >
      <Alert
        type="info"
        showIcon
        message="Execution diagnostics stay in Pool Runs"
        description={(
          <Space direction="vertical" size={8}>
            <Text>
              Use this workspace for factual summary, settlement handoff, and manual review. Create-run, approvals,
              retry, lineage, and runtime diagnostics remain in the execution-centric Pool Runs surface.
            </Text>
            <Space wrap>
              <RouteButton to={runWorkspaceHref}>Return to execution lineage</RouteButton>
              {runFromUrl ? <Text type="secondary">Linked run: {formatShortId(runFromUrl)}</Text> : null}
            </Space>
          </Space>
        )}
      />

      <MasterDetailShell
        detailOpen={Boolean(selectedPoolId) && isDetailOpen}
        onCloseDetail={handleCloseDetail}
        detailDrawerTitle={selectedPool ? `${selectedPool.code} · factual workspace` : 'Factual workspace'}
        list={(
          <EntityList
            title="Pools"
            loading={loadingPools}
            error={loadError}
            emptyDescription="No pools available for factual monitoring yet."
            dataSource={pools}
            renderItem={(pool) => {
              const selected = pool.id === selectedPoolId
              return (
                <RouteButton
                  key={pool.id}
                  type="text"
                  block
                  to={POOL_FACTUAL_ROUTE}
                  onClick={(event) => {
                    event.preventDefault()
                    handleSelectPool(pool.id)
                  }}
                  aria-label={`Open factual workspace for ${pool.name}`}
                  aria-pressed={selected}
                  style={{
                    justifyContent: 'flex-start',
                    height: 'auto',
                    paddingBlock: 12,
                    paddingInline: 12,
                    borderRadius: 8,
                    border: selected ? '1px solid #91caff' : '1px solid #f0f0f0',
                    borderInlineStart: selected ? '4px solid #1677ff' : '4px solid transparent',
                    background: selected ? '#e6f4ff' : '#fff',
                    boxShadow: selected ? '0 1px 2px rgba(22, 119, 255, 0.12)' : 'none',
                  }}
                >
                  <Space direction="vertical" size={2} style={{ width: '100%', textAlign: 'left' }}>
                    <Space wrap>
                      <Text strong>{pool.code}</Text>
                      <StatusBadge status={pool.is_active ? 'active' : 'inactive'} />
                    </Space>
                    <Text>{pool.name}</Text>
                    {pool.description ? <Text type="secondary">{pool.description}</Text> : null}
                  </Space>
                </RouteButton>
              )
            }}
          />
        )}
        detail={(
          <EntityDetails
            title="Factual operator workspace"
            extra={selectedPoolId ? <RouteButton to={poolCatalogHref}>Open pool detail</RouteButton> : null}
            loading={loadingPools}
            error={loadError}
            empty={!selectedPoolId}
            emptyDescription="Select a pool to open the factual workspace."
          >
            {selectedPool ? (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Alert
                  type="warning"
                  showIcon
                  message="Factual data surfaces are intentionally isolated from run-local controls"
                  description={(
                    <Space direction="vertical" size={8}>
                      <Text>
                        This workspace is the only entry point for factual balance monitoring and manual review.
                        Pool Runs keeps execution lineage, safe actions, and retry context.
                      </Text>
                      <Space wrap>
                        <RouteButton to={runWorkspaceHref}>Open linked run context</RouteButton>
                        <RouteButton to={poolCatalogHref}>Open pool topology context</RouteButton>
                      </Space>
                    </Space>
                  )}
                />

                <PoolFactualWorkspaceDetail
                  selectedPool={selectedPool}
                  focus={focusFromUrl}
                  runId={runFromUrl}
                  quarterStart={quarterStartFromUrl}
                  poolCatalogHref={poolCatalogHref}
                  runWorkspaceHref={runWorkspaceHref}
                />

                <Alert
                  type="success"
                  showIcon
                  message="UI governance contract is active"
                  description={(
                    <Space direction="vertical" size={8}>
                      <Text>
                        The route uses the project platform layer with a compact selection pane. On narrow viewports
                        the detail surface moves into the built-in drawer path from `MasterDetailShell` instead of
                        introducing page-wide horizontal overflow.
                      </Text>
                      {runFromUrl ? (
                        <Text type="secondary">
                          The linked run context is preserved while the workspace stays separate from execution tabs.
                        </Text>
                      ) : null}
                    </Space>
                  )}
                />
              </Space>
            ) : null}
          </EntityDetails>
        )}
      />
    </WorkspacePage>
  )
}
