import { useEffect, useMemo, useState } from 'react'
import { Alert, Space, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'

import type { PoolFactualOverviewItem } from '../../api/intercompanyPools'
import { listPoolFactualOverview } from '../../api/intercompanyPools'
import {
  EntityDetails,
  EntityList,
  MasterDetailShell,
  PageHeader,
  RouteButton,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import { useLocaleFormatters } from '../../i18n/formatters'
import { resolveApiError } from './masterData/errorUtils'
import { PoolFactualWorkspaceDetail } from './PoolFactualWorkspaceDetail'
import {
  getPoolFactualCompactSummary,
  getPoolFactualVerdictLabel,
  getPoolFactualVerdictPriority,
  getPoolFactualVerdictTone,
  resolvePoolFactualVerdict,
} from './poolFactualHealth'
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

const parseAmount = (value: string | null | undefined) => {
  const parsed = Number(value ?? '0')
  return Number.isFinite(parsed) ? parsed : 0
}

export function PoolFactualWorkspacePage() {
  const formatters = useLocaleFormatters()
  const [searchParams, setSearchParams] = useSearchParams()
  const poolFromUrl = normalizeRouteParam(searchParams.get('pool'))
  const runFromUrl = normalizeRouteParam(searchParams.get('run'))
  const quarterStartFromUrl = normalizeRouteParam(searchParams.get('quarter_start'))
  const focusFromUrl = normalizeFactualFocus(searchParams.get('focus'))
  const detailOpenFromUrl = searchParams.get('detail') === '1'

  const [overviewItems, setOverviewItems] = useState<PoolFactualOverviewItem[]>([])
  const [selectedPoolId, setSelectedPoolId] = useState<string | null>(poolFromUrl)
  const [isDetailOpen, setIsDetailOpen] = useState(detailOpenFromUrl)
  const [loadingOverview, setLoadingOverview] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    setSelectedPoolId((current) => (current === poolFromUrl ? current : poolFromUrl))
  }, [poolFromUrl])

  useEffect(() => {
    setIsDetailOpen((current) => (current === detailOpenFromUrl ? current : detailOpenFromUrl))
  }, [detailOpenFromUrl])

  useEffect(() => {
    let cancelled = false

    const loadOverview = async () => {
      setLoadingOverview(true)
      setLoadError(null)

      try {
        const data = await listPoolFactualOverview({
          quarterStart: quarterStartFromUrl ?? undefined,
        })
        if (cancelled) {
          return
        }
        setOverviewItems(data)
      } catch (error) {
        if (cancelled) {
          return
        }
        const resolved = resolveApiError(error, 'Failed to load factual overview rows.')
        setLoadError(resolved.message)
      } finally {
        if (!cancelled) {
          setLoadingOverview(false)
        }
      }
    }

    void loadOverview()

    return () => {
      cancelled = true
    }
  }, [quarterStartFromUrl])

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

  const sortedOverviewItems = useMemo(() => {
    return [...overviewItems].sort((left, right) => {
      const leftVerdict = resolvePoolFactualVerdict(left.summary)
      const rightVerdict = resolvePoolFactualVerdict(right.summary)
      const priorityDelta = getPoolFactualVerdictPriority(leftVerdict) - getPoolFactualVerdictPriority(rightVerdict)
      if (priorityDelta !== 0) {
        return priorityDelta
      }
      return left.pool_name.localeCompare(right.pool_name)
    })
  }, [overviewItems])

  const selectedOverviewItem = useMemo(
    () => overviewItems.find((pool) => pool.pool_id === selectedPoolId) ?? null,
    [overviewItems, selectedPoolId]
  )

  const selectedPool = useMemo(() => (
    selectedOverviewItem
      ? {
          id: selectedOverviewItem.pool_id,
          code: selectedOverviewItem.pool_code,
          name: selectedOverviewItem.pool_name,
        }
      : null
  ), [selectedOverviewItem])

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
      <MasterDetailShell
        detailOpen={Boolean(selectedPoolId) && isDetailOpen}
        onCloseDetail={handleCloseDetail}
        detailDrawerTitle={selectedPool ? `${selectedPool.code} · factual workspace` : 'Factual workspace'}
        list={(
          <EntityList
            title="Pools"
            loading={loadingOverview}
            error={loadError}
            emptyDescription="No pools available for factual monitoring yet."
            dataSource={sortedOverviewItems}
            renderItem={(pool) => {
              const selected = pool.pool_id === selectedPoolId
              const verdict = resolvePoolFactualVerdict(pool.summary)
              const verdictTone = getPoolFactualVerdictTone(verdict)
              const moneyLine = `In ${formatters.number(parseAmount(pool.summary.incoming_amount), {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })} · Out ${formatters.number(parseAmount(pool.summary.outgoing_amount), {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })} · Open ${formatters.number(parseAmount(pool.summary.open_balance), {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}`
              return (
                <RouteButton
                  key={pool.pool_id}
                  type="text"
                  block
                  to={POOL_FACTUAL_ROUTE}
                  onClick={(event) => {
                    event.preventDefault()
                    handleSelectPool(pool.pool_id)
                  }}
                  aria-label={`Open factual workspace for ${pool.pool_name}`}
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
                      <Text strong>{pool.pool_code}</Text>
                      <StatusBadge status={verdictTone} label={getPoolFactualVerdictLabel(verdict)} />
                      <StatusBadge status={pool.pool_is_active ? 'active' : 'inactive'} />
                    </Space>
                    <Text>{pool.pool_name}</Text>
                    <Text type="secondary">{getPoolFactualCompactSummary(pool.summary)}</Text>
                    <Text type="secondary">
                      {pool.summary.quarter}
                      {' · '}
                      resolved from {formatters.date(pool.summary.quarter_start)}
                    </Text>
                    <Text type="secondary">{moneyLine}</Text>
                    {pool.pool_description ? <Text type="secondary">{pool.pool_description}</Text> : null}
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
            loading={loadingOverview}
            error={loadError}
            empty={!selectedPoolId}
            emptyDescription="Select a pool to open the factual workspace."
          >
            {selectedPool ? (
              <PoolFactualWorkspaceDetail
                selectedPool={selectedPool}
                focus={focusFromUrl}
                runId={runFromUrl}
                quarterStart={quarterStartFromUrl}
                poolCatalogHref={poolCatalogHref}
                runWorkspaceHref={runWorkspaceHref}
              />
            ) : null}
          </EntityDetails>
        )}
      />

      <Alert
        type="info"
        showIcon
        message="Execution controls stay in Pool Runs"
        description={(
          <Space direction="vertical" size={8}>
            <Text>
              This route answers whether the selected pool is healthy, how much money came in and went out, and where
              manual follow-up is still required. Create-run, retry, and approvals remain in Pool Runs.
            </Text>
            <Space wrap>
              <RouteButton to={runWorkspaceHref}>Open Pool Runs</RouteButton>
              {runFromUrl ? <Text type="secondary">Linked run: {formatShortId(runFromUrl)}</Text> : null}
            </Space>
          </Space>
        )}
      />
    </WorkspacePage>
  )
}
