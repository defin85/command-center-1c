import { useMemo, useRef, useState, useEffect, useCallback } from 'react'
import { Alert, App, Button, Grid, List, Space, Typography } from 'antd'
import { PauseCircleOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import axios from 'axios'
import { useSearchParams } from 'react-router-dom'

import { getV2 } from '@/api/generated/v2/v2'
import type { ServiceHealth, SystemHealthResponse } from '@/api/generated/model'
import { RouteButton, EntityDetails, EntityList, JsonBlock, MasterDetailShell, PageHeader, StatusBadge, WorkspacePage } from '../../components/platform'
import { SystemOverview } from '../../components/SystemOverview'
import { ServiceStatusCard } from '../../components/ServiceStatusCard'
import { KNOWN_SERVICES } from '../../constants/services'

const api = getV2()
const POLL_INTERVAL_MS = 15000
const DESKTOP_BREAKPOINT_PX = 992
const { Text } = Typography
const { useBreakpoint } = Grid

type PollMode = 'live' | 'paused'

const parsePollMode = (value: string | null): PollMode => (
  value === 'paused' ? 'paused' : 'live'
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

const formatTimestamp = (value: string | null | undefined) => (
  value ? new Date(value).toLocaleString('ru-RU') : '—'
)

export const SystemStatus = () => {
  const screens = useBreakpoint()
  const [searchParams, setSearchParams] = useSearchParams()
  const { message } = App.useApp()
  const [health, setHealth] = useState<SystemHealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedServiceName = (searchParams.get('service') || '').trim() || null
  const pollMode = parsePollMode(searchParams.get('poll'))
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.lg
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < DESKTOP_BREAKPOINT_PX
        : false
    )

  const hasLoadedOnceRef = useRef(false)
  const pollCooldownUntilMsRef = useRef<number>(0)
  const lastRateLimitNoticeAtMsRef = useRef<number>(0)

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

  const fetchHealth = useCallback(async (opts?: { silent?: boolean; reason?: 'initial' | 'manual' | 'auto' }) => {
    try {
      if (!opts?.silent) {
        if (hasLoadedOnceRef.current) setRefreshing(true)
        else setLoading(true)
      }
      setError(null)
      const data = await api.getSystemHealth()
      setHealth(data)
    } catch (requestError) {
      if (axios.isAxiosError(requestError) && requestError.response?.status === 429) {
        const retryAfterHeader = requestError.response.headers?.['retry-after']
        const retryAfterSeconds = typeof retryAfterHeader === 'string' ? Number(retryAfterHeader) : Number.NaN
        const cooldownMs = Number.isFinite(retryAfterSeconds) ? retryAfterSeconds * 1000 : 30_000
        pollCooldownUntilMsRef.current = Date.now() + cooldownMs

        setError(`Слишком много запросов (429). Повтор через ~${Math.ceil(cooldownMs / 1000)}с`)

        const now = Date.now()
        if (!opts?.silent && now - lastRateLimitNoticeAtMsRef.current > 10_000) {
          lastRateLimitNoticeAtMsRef.current = now
          message.warning('API Gateway returned 429; auto-refresh is slowing down')
        }
        return
      }

      setError('Failed to load system status')
      if (!opts?.silent) {
        message.error('Failed to load system status')
      }
    } finally {
      setLoading(false)
      setRefreshing(false)
      hasLoadedOnceRef.current = true
    }
  }, [message])

  useEffect(() => {
    void fetchHealth({ reason: 'initial' })
  }, [fetchHealth])

  useEffect(() => {
    if (pollMode === 'paused') {
      return undefined
    }

    const interval = setInterval(() => {
      if (Date.now() < pollCooldownUntilMsRef.current) {
        return
      }
      void fetchHealth({ silent: true, reason: 'auto' })
    }, POLL_INTERVAL_MS)

    return () => clearInterval(interval)
  }, [fetchHealth, pollMode])

  const servicesSorted = useMemo(() => {
    const services = health?.services ?? []
    const rank = (status: string) => (status === 'offline' ? 0 : status === 'degraded' ? 1 : 2)
    return [...services].sort((left, right) => {
      const difference = rank(left.status) - rank(right.status)
      if (difference !== 0) return difference
      return String(left.name).localeCompare(String(right.name))
    })
  }, [health])

  const missing = useMemo(() => {
    const knownTitles = new Set((health?.services ?? []).map((service) => service.name))
    return KNOWN_SERVICES.filter((service) => !knownTitles.has(service.title))
  }, [health])

  const selectedService = useMemo<ServiceHealth | null>(() => {
    if (!selectedServiceName) return null
    return servicesSorted.find((service) => service.name === selectedServiceName) ?? null
  }, [selectedServiceName, servicesSorted])

  const detailError = selectedServiceName && !selectedService && !loading
    ? 'Selected diagnostics context is outside the current system status snapshot.'
    : null

  const headerSubtitle = [
    pollMode === 'paused' ? 'Auto-refresh paused.' : `Auto-refresh every ${POLL_INTERVAL_MS / 1000}s.`,
    `Last update: ${formatTimestamp(health?.timestamp)}`,
  ].join(' ')

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="System status"
          subtitle={headerSubtitle}
          actions={(
            <Space wrap>
              <Button
                icon={pollMode === 'paused' ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
                onClick={() => updateSearchParams({ poll: pollMode === 'paused' ? null : 'paused' })}
              >
                {pollMode === 'paused' ? 'Resume auto-refresh' : 'Pause auto-refresh'}
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => {
                  void fetchHealth({ reason: 'manual' })
                }}
                loading={refreshing}
              >
                Refresh
              </Button>
              <RouteButton to={selectedService ? `/service-mesh?service=${encodeURIComponent(selectedService.name)}` : '/service-mesh'}>
                Open service mesh
              </RouteButton>
            </Space>
          )}
        />
      )}
    >
      <MasterDetailShell
        detailOpen={Boolean(selectedServiceName)}
        onCloseDetail={() => updateSearchParams({ service: null })}
        detailDrawerTitle={selectedService ? selectedService.name : 'System diagnostics'}
        list={(
          <EntityList
            title="Services"
            loading={loading && !health}
            error={error && !health ? error : null}
            emptyDescription="No services reported by /api/v2/system/health/."
            dataSource={servicesSorted}
            renderItem={(service) => {
              const selected = service.name === selectedServiceName
              return (
                <List.Item key={service.name}>
                  <Button
                    type="text"
                    style={buildCatalogButtonStyle(selected)}
                    onClick={() => updateSearchParams({ service: service.name })}
                  >
                    <Space direction="vertical" size={4} style={{ width: '100%', alignItems: 'flex-start' }}>
                      <Space wrap size={[8, 8]}>
                        <Text strong>{service.name}</Text>
                        <StatusBadge status={service.status === 'online' ? 'active' : service.status === 'degraded' ? 'warning' : 'error'} label={service.status} />
                      </Space>
                      <Space wrap size={[8, 8]}>
                        <Text type="secondary">{service.type}</Text>
                        <Text type="secondary">Last check: {formatTimestamp(service.last_check)}</Text>
                        <Text type="secondary">
                          Response: {service.response_time_ms == null ? '—' : `${service.response_time_ms} ms`}
                        </Text>
                      </Space>
                    </Space>
                  </Button>
                </List.Item>
              )
            }}
          />
        )}
        detail={(
          <EntityDetails
            title={selectedService ? selectedService.name : 'System overview'}
            loading={loading && !health}
            error={detailError}
            empty={!selectedServiceName && !health}
            emptyDescription="Select a service to inspect its diagnostics context."
          >
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              {error && health ? (
                <Alert
                  type="warning"
                  showIcon
                  message={error}
                  action={(
                    <Button size="small" onClick={() => {
                      void fetchHealth({ reason: 'manual' })
                    }}>
                      Retry
                    </Button>
                  )}
                />
              ) : null}

              {health && (!isNarrow || !selectedServiceName) ? <SystemOverview health={health} /> : null}

              {health && isNarrow && selectedServiceName ? (
                <Alert
                  type="info"
                  showIcon
                  message={`System summary: ${health.statistics.online}/${health.statistics.total} services online, ${health.statistics.degraded} degraded.`}
                />
              ) : null}

              {missing.length > 0 ? (
                <Alert
                  type="warning"
                  showIcon
                  message="Some expected services are missing from /api/v2/system/health/."
                  description={missing.map((service) => service.title).join(', ')}
                />
              ) : null}

              {selectedService ? (
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  <ServiceStatusCard service={selectedService} />
                  <JsonBlock
                    title="Service details"
                    value={selectedService.details ?? {}}
                    dataTestId="system-status-service-details"
                  />
                </Space>
              ) : (
                <Alert
                  type="info"
                  showIcon
                  message="Select a service from the catalog to inspect its diagnostics payload."
                />
              )}
            </Space>
          </EntityDetails>
        )}
      />
    </WorkspacePage>
  )
}
