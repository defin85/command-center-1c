import { useEffect, useMemo, useState } from 'react'
import { Alert, Space, Typography } from 'antd'
import { useLocation, useSearchParams } from 'react-router-dom'

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
import { usePoolFactualTranslation } from '../../i18n'
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
    return '—'
  }
  return value.slice(0, 8)
}

const parseAmount = (value: string | null | undefined) => {
  const parsed = Number(value ?? '0')
  return Number.isFinite(parsed) ? parsed : 0
}

export function PoolFactualWorkspacePage() {
  const { t } = usePoolFactualTranslation()
  const formatters = useLocaleFormatters()
  const location = useLocation()
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
        const resolved = resolveApiError(error, t('messages.failedLoadOverview'))
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
  }, [quarterStartFromUrl, t])

  useEffect(() => {
    if (location.pathname !== POOL_FACTUAL_ROUTE) {
      return
    }

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
  }, [focusFromUrl, isDetailOpen, location.pathname, quarterStartFromUrl, runFromUrl, searchParams, selectedPoolId, setSearchParams])

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
          title={t('page.title')}
          subtitle={(
            <>
              {t('page.subtitle', {
                route: POOL_FACTUAL_ROUTE,
                runsRoute: POOL_RUNS_ROUTE,
              })}
            </>
          )}
          actions={(
            <Space wrap>
              <RouteButton to={runWorkspaceHref}>{t('page.actions.openPoolRuns')}</RouteButton>
              <RouteButton type="primary" to={poolCatalogHref} disabled={!selectedPoolId}>
                {t('page.actions.openPoolCatalog')}
              </RouteButton>
            </Space>
          )}
        />
      )}
    >
      <MasterDetailShell
        detailOpen={Boolean(selectedPoolId) && isDetailOpen}
        onCloseDetail={handleCloseDetail}
        detailDrawerTitle={selectedPool
          ? t('page.drawerTitle', { code: selectedPool.code })
          : t('page.drawerTitleFallback')}
        list={(
          <EntityList
            title={t('page.list.title')}
            loading={loadingOverview}
            error={loadError}
            emptyDescription={t('page.list.emptyDescription')}
            dataSource={sortedOverviewItems}
            renderItem={(pool) => {
              const selected = pool.pool_id === selectedPoolId
              const verdict = resolvePoolFactualVerdict(pool.summary)
              const verdictTone = getPoolFactualVerdictTone(verdict)
              const moneyLine = t('page.list.compactMoneyLine', {
                incoming: formatters.number(parseAmount(pool.summary.incoming_amount), {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                }),
                outgoing: formatters.number(parseAmount(pool.summary.outgoing_amount), {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                }),
                open: formatters.number(parseAmount(pool.summary.open_balance), {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                }),
              })
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
                  aria-label={t('page.list.openWorkspaceAria', { name: pool.pool_name })}
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
                      <StatusBadge status={verdictTone} label={getPoolFactualVerdictLabel(t, verdict)} />
                      <StatusBadge status={pool.pool_is_active ? 'active' : 'inactive'} />
                    </Space>
                    <Text>{pool.pool_name}</Text>
                    <Text type="secondary">{getPoolFactualCompactSummary(t, pool.summary)}</Text>
                    <Text type="secondary">
                      {pool.summary.quarter}
                      {' · '}
                      {t('page.list.compactResolvedFrom', {
                        value: formatters.date(pool.summary.quarter_start),
                      })}
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
            title={t('page.detail.title')}
            extra={selectedPoolId ? <RouteButton to={poolCatalogHref}>{t('page.actions.openPoolDetail')}</RouteButton> : null}
            loading={loadingOverview}
            error={loadError}
            empty={!selectedPoolId}
            emptyDescription={t('page.detail.emptyDescription')}
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
        message={t('page.executionControls.title')}
        description={(
          <Space direction="vertical" size={8}>
            <Text>{t('page.executionControls.description')}</Text>
            <Space wrap>
              <RouteButton to={runWorkspaceHref}>{t('page.actions.openPoolRuns')}</RouteButton>
              {runFromUrl ? (
                <Text type="secondary">
                  {t('page.executionControls.linkedRun', { value: formatShortId(runFromUrl) })}
                </Text>
              ) : null}
            </Space>
          </Space>
        )}
      />
    </WorkspacePage>
  )
}
