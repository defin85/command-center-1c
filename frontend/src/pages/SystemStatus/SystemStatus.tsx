import { useMemo, useRef, useState, useEffect, useCallback } from 'react'
import { Alert, App, Button, Descriptions, Grid, Input, List, Segmented, Space, Switch, Typography } from 'antd'
import { PauseCircleOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import axios from 'axios'
import { useSearchParams } from 'react-router-dom'

import { getV2 } from '@/api/generated/v2/v2'
import type { ServiceHealth, SystemHealthResponse } from '@/api/generated/model'
import {
  createRuntimeControlAction,
  getRuntimeControlCatalog,
  getRuntimeControlRuntime,
  patchRuntimeControlDesiredState,
  type RuntimeActionRun,
  type RuntimeDesiredState,
  type RuntimeInstance,
} from '../../api/runtimeControl'
import { useAuthz } from '../../authz/useAuthz'
import {
  EntityDetails,
  EntityList,
  JsonBlock,
  MasterDetailShell,
  ModalFormShell,
  PageHeader,
  RouteButton,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import { SystemOverview } from '../../components/SystemOverview'
import { ServiceStatusCard } from '../../components/ServiceStatusCard'
import { KNOWN_SERVICES } from '../../constants/services'

const api = getV2()
const POLL_INTERVAL_MS = 15000
const DESKTOP_BREAKPOINT_PX = 992
const { Text, Paragraph } = Typography
const { TextArea } = Input
const { useBreakpoint } = Grid

type PollMode = 'live' | 'paused'
type DetailTab = 'overview' | 'controls' | 'scheduler' | 'logs'

const SCHEDULER_SETTING_KEYS: Record<string, { enabled: string; schedule: string }> = {
  pool_factual_active_sync: {
    enabled: 'runtime.scheduler.job.pool_factual_active_sync.enabled',
    schedule: 'runtime.scheduler.job.pool_factual_active_sync.schedule',
  },
  pool_factual_closed_quarter_reconcile: {
    enabled: 'runtime.scheduler.job.pool_factual_closed_quarter_reconcile.enabled',
    schedule: 'runtime.scheduler.job.pool_factual_closed_quarter_reconcile.schedule',
  },
}

const parsePollMode = (value: string | null): PollMode => (
  value === 'paused' ? 'paused' : 'live'
)

const parseDetailTab = (value: string | null): DetailTab => {
  if (value === 'controls' || value === 'scheduler' || value === 'logs') {
    return value
  }
  return 'overview'
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

const formatTimestamp = (value: string | null | undefined) => (
  value ? new Date(value).toLocaleString('ru-RU') : '—'
)

const describeRequestError = (error: unknown, fallback: string): string => {
  if (!axios.isAxiosError(error)) {
    return fallback
  }
  const payload = error.response?.data
  const payloadMessage = payload && typeof payload === 'object'
    ? (payload as { error?: { message?: unknown } }).error?.message
    : null
  if (typeof payloadMessage === 'string' && payloadMessage.trim()) {
    return payloadMessage
  }
  return error.message || fallback
}

const runtimeStatusBadge = (status: string | null | undefined) => {
  if (status === 'online' || status === 'success' || status === 'enabled') return 'active'
  if (status === 'degraded' || status === 'running') return 'warning'
  if (status === 'offline' || status === 'failed') return 'error'
  if (status === 'disabled' || status === 'accepted' || status === 'skipped') return 'inactive'
  return 'unknown'
}

const formatActionType = (actionType: RuntimeActionRun['action_type']) => {
  if (actionType === 'trigger_now') return 'Trigger now'
  if (actionType === 'tail_logs') return 'Refresh logs excerpt'
  if (actionType === 'restart') return 'Restart runtime'
  return 'Run probe'
}

const formatSupportedActions = (actions: RuntimeInstance['supported_actions']) => (
  actions.map((action) => formatActionType(action)).join(', ') || '—'
)

const normalizeRouteServiceKey = (value: string | null | undefined) => (
  String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, '-')
)

export const SystemStatus = () => {
  const screens = useBreakpoint()
  const [searchParams, setSearchParams] = useSearchParams()
  const { message } = App.useApp()
  const { canManageRuntimeControls, isStaff } = useAuthz()

  const [health, setHealth] = useState<SystemHealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [runtimeCatalog, setRuntimeCatalog] = useState<RuntimeInstance[]>([])
  const [runtimeDetail, setRuntimeDetail] = useState<RuntimeInstance | null>(null)
  const [runtimeLoading, setRuntimeLoading] = useState(false)
  const [runtimeMutating, setRuntimeMutating] = useState<string | null>(null)
  const [runtimeError, setRuntimeError] = useState<string | null>(null)
  const [restartModalOpen, setRestartModalOpen] = useState(false)
  const [restartReason, setRestartReason] = useState('')

  const selectedServiceName = (searchParams.get('service') || '').trim() || null
  const selectedDetailTab = parseDetailTab(searchParams.get('tab'))
  const selectedSchedulerJobName = (searchParams.get('job') || '').trim() || null
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
  const runtimeRefreshTimeoutRef = useRef<number | null>(null)

  useEffect(() => (
    () => {
      if (runtimeRefreshTimeoutRef.current !== null && typeof window !== 'undefined') {
        window.clearTimeout(runtimeRefreshTimeoutRef.current)
      }
    }
  ), [])

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

  const fetchRuntimeCatalog = useCallback(async (opts?: { silent?: boolean }) => {
    if (!canManageRuntimeControls) {
      setRuntimeCatalog([])
      return
    }
    try {
      if (!opts?.silent) {
        setRuntimeLoading(true)
      }
      setRuntimeError(null)
      const runtimes = await getRuntimeControlCatalog()
      setRuntimeCatalog(runtimes)
    } catch (requestError) {
      setRuntimeError(describeRequestError(requestError, 'Не удалось загрузить runtime control catalog.'))
    } finally {
      if (!opts?.silent) {
        setRuntimeLoading(false)
      }
    }
  }, [canManageRuntimeControls])

  const fetchRuntimeDetail = useCallback(async (runtimeId: string, opts?: { silent?: boolean }) => {
    if (!canManageRuntimeControls) {
      setRuntimeDetail(null)
      return
    }
    try {
      if (!opts?.silent) {
        setRuntimeLoading(true)
      }
      setRuntimeError(null)
      const runtime = await getRuntimeControlRuntime(runtimeId)
      setRuntimeDetail(runtime)
      setRuntimeCatalog((current) => current.map((item) => (
        item.runtime_id === runtime.runtime_id ? { ...item, ...runtime } : item
      )))
    } catch (requestError) {
      setRuntimeError(describeRequestError(requestError, 'Не удалось загрузить runtime detail.'))
    } finally {
      if (!opts?.silent) {
        setRuntimeLoading(false)
      }
    }
  }, [canManageRuntimeControls])

  const scheduleRuntimeDetailRefresh = useCallback((runtimeId: string) => {
    if (typeof window === 'undefined') {
      return
    }
    if (runtimeRefreshTimeoutRef.current !== null) {
      window.clearTimeout(runtimeRefreshTimeoutRef.current)
    }
    runtimeRefreshTimeoutRef.current = window.setTimeout(() => {
      runtimeRefreshTimeoutRef.current = null
      void fetchRuntimeDetail(runtimeId, { silent: true })
    }, 1500)
  }, [fetchRuntimeDetail])

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

  useEffect(() => {
    if (!canManageRuntimeControls) {
      setRuntimeCatalog([])
      setRuntimeDetail(null)
      setRuntimeError(null)
      return
    }
    void fetchRuntimeCatalog()
  }, [canManageRuntimeControls, fetchRuntimeCatalog])

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
    const normalizedSelectedServiceKey = normalizeRouteServiceKey(selectedServiceName)
    return servicesSorted.find((service) => (
      service.name === selectedServiceName
      || normalizeRouteServiceKey(service.name) === normalizedSelectedServiceKey
    )) ?? null
  }, [selectedServiceName, servicesSorted])

  const selectedRuntimeSummary = useMemo<RuntimeInstance | null>(() => {
    if (!selectedServiceName || !canManageRuntimeControls) return null
    const candidateKeys = new Set([
      normalizeRouteServiceKey(selectedServiceName),
      normalizeRouteServiceKey(selectedService?.name),
    ].filter(Boolean))
    return runtimeCatalog.find((runtime) => (
      candidateKeys.has(normalizeRouteServiceKey(runtime.runtime_name))
      || candidateKeys.has(normalizeRouteServiceKey(runtime.display_name))
    )) ?? null
  }, [canManageRuntimeControls, runtimeCatalog, selectedService?.name, selectedServiceName])

  const selectedRuntime = runtimeDetail && selectedRuntimeSummary && runtimeDetail.runtime_id === selectedRuntimeSummary.runtime_id
    ? runtimeDetail
    : selectedRuntimeSummary

  useEffect(() => {
    if (!selectedRuntimeSummary?.runtime_id) {
      setRuntimeDetail(null)
      return
    }
    void fetchRuntimeDetail(selectedRuntimeSummary.runtime_id)
  }, [fetchRuntimeDetail, selectedRuntimeSummary?.runtime_id])

  useEffect(() => {
    if (pollMode === 'paused' || !selectedRuntimeSummary?.runtime_id) {
      return undefined
    }
    const interval = window.setInterval(() => {
      void fetchRuntimeDetail(selectedRuntimeSummary.runtime_id, { silent: true })
    }, POLL_INTERVAL_MS)
    return () => window.clearInterval(interval)
  }, [fetchRuntimeDetail, pollMode, selectedRuntimeSummary?.runtime_id])

  const detailError = selectedServiceName && !selectedService && !loading
    ? 'Selected diagnostics context is outside the current system status snapshot.'
    : null
  const selectedServiceRouteKey = selectedRuntimeSummary?.runtime_name ?? selectedService?.name ?? null

  const headerSubtitle = [
    pollMode === 'paused' ? 'Auto-refresh paused.' : `Auto-refresh every ${POLL_INTERVAL_MS / 1000}s.`,
    `Last update: ${formatTimestamp(health?.timestamp)}`,
  ].join(' ')

  const syncRuntimeDesiredState = useCallback((runtimeId: string, desiredState: RuntimeDesiredState) => {
    setRuntimeCatalog((current) => current.map((item) => (
      item.runtime_id === runtimeId ? { ...item, desired_state: desiredState } : item
    )))
    setRuntimeDetail((current) => (
      current && current.runtime_id === runtimeId
        ? { ...current, desired_state: desiredState }
        : current
    ))
  }, [])

  const handleRuntimeAction = useCallback(async ({
    actionType,
    reason = '',
    targetJobName = '',
  }: {
    actionType: RuntimeActionRun['action_type']
    reason?: string
    targetJobName?: string
  }) => {
    if (!selectedRuntimeSummary) {
      return
    }
    if (targetJobName) {
      updateSearchParams({ job: targetJobName })
    }
    const actionKey = actionType === 'trigger_now' ? `trigger_now:${targetJobName}` : actionType
    try {
      setRuntimeMutating(actionKey)
      setRuntimeError(null)
      const action = await createRuntimeControlAction({
        runtime_id: selectedRuntimeSummary.runtime_id,
        action_type: actionType,
        ...(reason ? { reason } : {}),
        ...(targetJobName ? { target_job_name: targetJobName } : {}),
      })
      setRuntimeDetail((current) => (
        current && current.runtime_id === selectedRuntimeSummary.runtime_id
          ? {
            ...current,
            recent_actions: [action, ...(current.recent_actions ?? []).filter((item) => item.id !== action.id)].slice(0, 10),
          }
          : current
      ))
      message.success(`${formatActionType(actionType)} accepted`)
      void fetchRuntimeDetail(selectedRuntimeSummary.runtime_id, { silent: true })
      scheduleRuntimeDetailRefresh(selectedRuntimeSummary.runtime_id)
    } catch (requestError) {
      const nextError = describeRequestError(requestError, 'Runtime action failed to start.')
      setRuntimeError(nextError)
      message.error(nextError)
    } finally {
      setRuntimeMutating(null)
    }
  }, [fetchRuntimeDetail, message, scheduleRuntimeDetailRefresh, selectedRuntimeSummary, updateSearchParams])

  const handleSchedulerToggle = useCallback(async (nextEnabled: boolean) => {
    if (!selectedRuntimeSummary) {
      return
    }
    try {
      setRuntimeMutating('scheduler')
      setRuntimeError(null)
      const desiredState = await patchRuntimeControlDesiredState(selectedRuntimeSummary.runtime_id, {
        scheduler_enabled: nextEnabled,
      })
      syncRuntimeDesiredState(selectedRuntimeSummary.runtime_id, desiredState)
      message.success('Scheduler desired state updated')
    } catch (requestError) {
      const nextError = describeRequestError(requestError, 'Не удалось обновить scheduler desired state.')
      setRuntimeError(nextError)
      message.error(nextError)
    } finally {
      setRuntimeMutating(null)
    }
  }, [message, selectedRuntimeSummary, syncRuntimeDesiredState])

  const handleSchedulerJobToggle = useCallback(async (jobName: string, nextEnabled: boolean) => {
    if (!selectedRuntimeSummary) {
      return
    }
    updateSearchParams({ job: jobName })
    try {
      setRuntimeMutating(`job:${jobName}`)
      setRuntimeError(null)
      const desiredState = await patchRuntimeControlDesiredState(selectedRuntimeSummary.runtime_id, {
        jobs: [{ job_name: jobName, enabled: nextEnabled }],
      })
      syncRuntimeDesiredState(selectedRuntimeSummary.runtime_id, desiredState)
      message.success('Scheduler job desired state updated')
    } catch (requestError) {
      const nextError = describeRequestError(requestError, 'Не удалось обновить desired state job.')
      setRuntimeError(nextError)
      message.error(nextError)
    } finally {
      setRuntimeMutating(null)
    }
  }, [message, selectedRuntimeSummary, syncRuntimeDesiredState, updateSearchParams])

  const schedulerJobs = useMemo(
    () => selectedRuntime?.desired_state?.jobs ?? [],
    [selectedRuntime?.desired_state?.jobs],
  )
  const selectedSchedulerJob = useMemo(
    () => schedulerJobs.find((job) => job.job_name === selectedSchedulerJobName) ?? null,
    [schedulerJobs, selectedSchedulerJobName],
  )
  const orderedSchedulerJobs = useMemo(() => {
    if (!selectedSchedulerJobName) {
      return schedulerJobs
    }
    return [...schedulerJobs].sort((left, right) => {
      const leftRank = left.job_name === selectedSchedulerJobName ? 0 : 1
      const rightRank = right.job_name === selectedSchedulerJobName ? 0 : 1
      return leftRank - rightRank
    })
  }, [schedulerJobs, selectedSchedulerJobName])

  const overviewTabContent = selectedService ? (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <ServiceStatusCard service={selectedService} />
      <JsonBlock
        title="Service details"
        value={selectedService.details ?? {}}
        dataTestId="system-status-service-details"
      />
      {canManageRuntimeControls ? (
        selectedRuntime ? (
          <Descriptions
            bordered
            column={1}
            size="small"
            title="Runtime control summary"
          >
            <Descriptions.Item label="Runtime target">{selectedRuntime.display_name}</Descriptions.Item>
            <Descriptions.Item label="Provider">{`${selectedRuntime.provider.key} @ ${selectedRuntime.provider.host}`}</Descriptions.Item>
            <Descriptions.Item label="Observed runtime state">
              <Space wrap size={[8, 8]}>
                <StatusBadge
                  status={runtimeStatusBadge(selectedRuntime.observed_state.status)}
                  label={selectedRuntime.observed_state.status}
                />
                <Text type="secondary">
                  proc={selectedRuntime.observed_state.process_status}, http={selectedRuntime.observed_state.http_status}
                </Text>
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="Supported actions">
              {formatSupportedActions(selectedRuntime.supported_actions)}
            </Descriptions.Item>
            <Descriptions.Item label="Logs surface">
              {selectedRuntime.logs_available ? 'available' : 'unavailable'}
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <Alert
            type="info"
            showIcon
            message="Runtime controls are unavailable for this service."
          />
        )
      ) : null}
    </Space>
  ) : null

  const controlsTabContent = selectedRuntime ? (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="Runtime actions execute asynchronously. Recent actions refresh automatically while polling is enabled."
      />
      <Space wrap>
        <Button
          onClick={() => {
            void handleRuntimeAction({ actionType: 'probe' })
          }}
          loading={runtimeMutating === 'probe'}
        >
          Run probe
        </Button>
        <Button
          onClick={() => {
            void handleRuntimeAction({ actionType: 'tail_logs' })
          }}
          loading={runtimeMutating === 'tail_logs'}
          disabled={!selectedRuntime.logs_available}
        >
          Refresh logs excerpt
        </Button>
        <Button
          danger
          onClick={() => setRestartModalOpen(true)}
          disabled={!selectedRuntime.supported_actions.includes('restart')}
          loading={runtimeMutating === 'restart'}
        >
          Restart runtime
        </Button>
      </Space>

      {runtimeError ? (
        <Alert type="warning" showIcon message={runtimeError} />
      ) : null}

      {(selectedRuntime.recent_actions?.length ?? 0) > 0 ? (
        <List
          dataSource={selectedRuntime.recent_actions ?? []}
          renderItem={(action) => (
            <List.Item key={action.id}>
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Space wrap size={[8, 8]}>
                  <Text strong>{formatActionType(action.action_type)}</Text>
                  <StatusBadge status={runtimeStatusBadge(action.status)} label={action.status} />
                  {action.target_job_name ? <Text code>{action.target_job_name}</Text> : null}
                </Space>
                <Space wrap size={[8, 8]}>
                  <Text type="secondary">Requested: {formatTimestamp(action.requested_at)}</Text>
                  <Text type="secondary">Finished: {formatTimestamp(action.finished_at)}</Text>
                  <Text type="secondary">Actor: {action.requested_by_username || 'system'}</Text>
                  {action.scheduler_job_run_id != null ? (
                    <Text type="secondary">Scheduler run: #{action.scheduler_job_run_id}</Text>
                  ) : null}
                </Space>
                {action.reason ? (
                  <Text type="secondary">Reason: {action.reason}</Text>
                ) : null}
                {action.result_excerpt ? (
                  <Paragraph style={{ marginBottom: 0 }}>
                    {action.result_excerpt}
                  </Paragraph>
                ) : null}
                {action.error_message ? (
                  <Alert type="error" showIcon message={action.error_message} />
                ) : null}
              </Space>
            </List.Item>
          )}
        />
      ) : (
        <Alert
          type="info"
          showIcon
          message="No runtime actions recorded yet."
        />
      )}
    </Space>
  ) : (
    <Alert
      type="info"
      showIcon
      message="Runtime controls are unavailable for this service."
    />
  )

  const schedulerTabContent = selectedRuntime?.scheduler_supported && selectedRuntime.desired_state ? (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        <Space wrap size={[12, 12]} align="center">
          <Text strong>Global scheduler enablement</Text>
          <Switch
            checked={selectedRuntime.desired_state.scheduler_enabled}
            loading={runtimeMutating === 'scheduler'}
            onChange={(checked) => {
              void handleSchedulerToggle(checked)
            }}
          />
          <StatusBadge
            status={runtimeStatusBadge(selectedRuntime.desired_state.scheduler_enabled ? 'enabled' : 'disabled')}
            label={selectedRuntime.desired_state.scheduler_enabled ? 'enabled' : 'disabled'}
          />
        </Space>
        <Text type="secondary">
          Enablement applies live. Cadence remains declarative and follows the controlled apply path.
        </Text>
      </Space>

      {isStaff ? (
        <RouteButton to="/settings/runtime?setting=runtime.scheduler.enabled">
          Open runtime settings
        </RouteButton>
      ) : null}

      {selectedSchedulerJob ? (
        <Alert
          type="success"
          showIcon
          data-testid="system-status-selected-scheduler-job"
          message={`Selected job: ${selectedSchedulerJob.display_name}`}
          description={(
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Space direction="vertical" size={4}>
                <Text type="secondary">Job key: {selectedSchedulerJob.job_name}</Text>
                <Text type="secondary">Cadence: {selectedSchedulerJob.schedule}</Text>
                <Text type="secondary">
                  Last run: {formatTimestamp(selectedSchedulerJob.latest_run_started_at)}
                  {selectedSchedulerJob.latest_run_id != null ? ` (#${selectedSchedulerJob.latest_run_id})` : ''}
                </Text>
              </Space>
              <Space wrap>
                <Button
                  onClick={() => {
                    void handleRuntimeAction({
                      actionType: 'trigger_now',
                      targetJobName: selectedSchedulerJob.job_name,
                    })
                  }}
                  loading={runtimeMutating === `trigger_now:${selectedSchedulerJob.job_name}`}
                >
                  Trigger now
                </Button>
                {isStaff && SCHEDULER_SETTING_KEYS[selectedSchedulerJob.job_name] ? (
                  <RouteButton
                    to={`/settings/runtime?setting=${encodeURIComponent(SCHEDULER_SETTING_KEYS[selectedSchedulerJob.job_name].schedule)}`}
                  >
                    Open cadence
                  </RouteButton>
                ) : null}
              </Space>
            </Space>
          )}
        />
      ) : null}

      {orderedSchedulerJobs.map((job) => {
        const settingKeys = SCHEDULER_SETTING_KEYS[job.job_name]
        const isSelectedJob = job.job_name === selectedSchedulerJobName
        return (
          <Alert
            key={job.job_name}
            type={isSelectedJob ? 'success' : 'info'}
            showIcon={false}
            message={(
              <Space wrap size={[8, 8]}>
                <Text strong>{job.display_name}</Text>
                {isSelectedJob ? (
                  <StatusBadge status="active" label="selected" />
                ) : null}
                <StatusBadge
                  status={runtimeStatusBadge(job.enabled ? 'enabled' : 'disabled')}
                  label={job.enabled ? 'enabled' : 'disabled'}
                />
                {job.latest_run_status ? (
                  <StatusBadge
                    status={runtimeStatusBadge(job.latest_run_status)}
                    label={job.latest_run_status}
                  />
                ) : null}
              </Space>
            )}
            description={(
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Text type="secondary">{job.description}</Text>
                <Space direction="vertical" size={4}>
                  <Text type="secondary">Cadence: {job.schedule}</Text>
                  <Text type="secondary">Last run: {formatTimestamp(job.latest_run_started_at)}</Text>
                  <Text type="secondary">
                    Apply modes: enablement={job.enablement_apply_mode}, schedule={job.schedule_apply_mode}
                  </Text>
                </Space>
                <Space wrap>
                  <Button
                    onClick={() => updateSearchParams({ job: job.job_name })}
                    disabled={isSelectedJob}
                  >
                    {isSelectedJob ? 'Focused' : 'Focus job'}
                  </Button>
                  <Space size="small">
                    <Text>Enabled</Text>
                    <Switch
                      checked={job.enabled}
                      loading={runtimeMutating === `job:${job.job_name}`}
                      onChange={(checked) => {
                        updateSearchParams({ job: job.job_name })
                        void handleSchedulerJobToggle(job.job_name, checked)
                      }}
                    />
                  </Space>
                  <Button
                    onClick={() => {
                      updateSearchParams({ job: job.job_name })
                      void handleRuntimeAction({ actionType: 'trigger_now', targetJobName: job.job_name })
                    }}
                    loading={runtimeMutating === `trigger_now:${job.job_name}`}
                  >
                    Trigger now
                  </Button>
                  {isStaff && settingKeys ? (
                    <RouteButton to={`/settings/runtime?setting=${encodeURIComponent(settingKeys.schedule)}`}>
                      Open cadence
                    </RouteButton>
                  ) : null}
                </Space>
              </Space>
            )}
          />
        )
      })}
    </Space>
  ) : (
    <Alert
      type="info"
      showIcon
      message="This runtime does not expose scheduler controls."
    />
  )

  const logsTabContent = selectedRuntime ? (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Space wrap size={[12, 12]}>
        <Button
          onClick={() => {
            void handleRuntimeAction({ actionType: 'tail_logs' })
          }}
          loading={runtimeMutating === 'tail_logs'}
          disabled={!selectedRuntime.logs_available}
        >
          Refresh logs excerpt
        </Button>
        {selectedRuntime.logs_excerpt?.updated_at ? (
          <Text type="secondary">Updated: {formatTimestamp(selectedRuntime.logs_excerpt.updated_at)}</Text>
        ) : null}
      </Space>
      {selectedRuntime.logs_excerpt?.path ? (
        <Text type="secondary">Path: {selectedRuntime.logs_excerpt.path}</Text>
      ) : null}
      {selectedRuntime.logs_available ? (
        <JsonBlock
          title="Latest logs excerpt"
          value={selectedRuntime.logs_excerpt?.excerpt ?? ''}
          emptyLabel="No logs excerpt available yet."
          dataTestId="system-status-runtime-logs"
        />
      ) : (
        <Alert
          type="info"
          showIcon
          message="Log surface is unavailable for this runtime."
        />
      )}
    </Space>
  ) : (
    <Alert
      type="info"
      showIcon
      message="Runtime controls are unavailable for this service."
    />
  )

  const detailTabOptions = [
    { label: 'Overview', value: 'overview' as const },
    ...(canManageRuntimeControls ? [{ label: 'Controls', value: 'controls' as const }] : []),
    ...(canManageRuntimeControls && selectedRuntime?.scheduler_supported ? [{ label: 'Scheduler', value: 'scheduler' as const }] : []),
    ...(canManageRuntimeControls ? [{ label: 'Logs', value: 'logs' as const }] : []),
  ]

  const activeDetailTab = detailTabOptions.some((item) => item.value === selectedDetailTab) ? selectedDetailTab : 'overview'

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
                  void fetchRuntimeCatalog({ silent: true })
                  if (selectedRuntimeSummary?.runtime_id) {
                    void fetchRuntimeDetail(selectedRuntimeSummary.runtime_id, { silent: true })
                  }
                }}
                loading={refreshing || runtimeLoading}
              >
                Refresh
              </Button>
              <RouteButton to={selectedServiceRouteKey ? `/service-mesh?service=${encodeURIComponent(selectedServiceRouteKey)}` : '/service-mesh'}>
                Open service mesh
              </RouteButton>
            </Space>
          )}
        />
      )}
    >
      <MasterDetailShell
        detailOpen={Boolean(selectedServiceName)}
        onCloseDetail={() => updateSearchParams({ service: null, tab: null, job: null })}
        detailDrawerTitle={selectedService ? selectedService.name : 'System diagnostics'}
        list={(
          <EntityList
            title="Services"
            loading={loading && !health}
            error={error && !health ? error : null}
            emptyDescription="No services reported by /api/v2/system/health/."
            dataSource={servicesSorted}
            renderItem={(service) => {
              const selected = selectedService?.name === service.name
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
                  {canManageRuntimeControls && runtimeLoading && !selectedRuntime ? (
                    <Alert
                      type="info"
                      showIcon
                      message="Loading runtime controls…"
                    />
                  ) : null}
                  <Segmented
                    block
                    options={detailTabOptions}
                    value={activeDetailTab}
                    onChange={(next) => updateSearchParams({
                      tab: next === 'overview' ? null : String(next),
                    })}
                  />
                  {activeDetailTab === 'overview' ? overviewTabContent : null}
                  {activeDetailTab === 'controls' ? controlsTabContent : null}
                  {activeDetailTab === 'scheduler' ? schedulerTabContent : null}
                  {activeDetailTab === 'logs' ? logsTabContent : null}
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

      <ModalFormShell
        open={restartModalOpen}
        onClose={() => {
          setRestartModalOpen(false)
          setRestartReason('')
        }}
        onSubmit={async () => {
          await handleRuntimeAction({
            actionType: 'restart',
            reason: restartReason.trim(),
          })
          setRestartModalOpen(false)
          setRestartReason('')
        }}
        title="Restart runtime"
        subtitle={selectedRuntime?.display_name ?? selectedServiceName ?? undefined}
        submitText="Restart"
        submitDisabled={!restartReason.trim()}
        confirmLoading={runtimeMutating === 'restart'}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Alert
            type="warning"
            showIcon
            message="Restart is a dangerous action and requires an explicit operator reason."
          />
          <TextArea
            value={restartReason}
            rows={4}
            onChange={(event) => setRestartReason(event.target.value)}
            placeholder="Explain why this runtime needs a restart"
          />
        </Space>
      </ModalFormShell>
    </WorkspacePage>
  )
}
