import { apiClient } from './client'

export type RuntimeObservedState = {
  status: string
  process_status: string
  http_status: string
  raw_probe: string
  command_status?: string
}

export type RuntimeProvider = {
  key: string
  host: string
}

export type RuntimeActionRun = {
  id: string
  provider: string
  runtime_id: string
  runtime_name: string
  action_type: 'probe' | 'restart' | 'tail_logs' | 'trigger_now'
  target_job_name: string
  status: 'accepted' | 'running' | 'success' | 'failed'
  reason: string
  requested_by_username: string
  requested_at: string | null
  started_at: string | null
  finished_at: string | null
  result_excerpt: string
  result_payload: Record<string, unknown>
  error_message: string
  scheduler_job_run_id: number | null
}

export type RuntimeSchedulerJob = {
  job_name: string
  runtime_id: string
  runtime_name: string
  display_name: string
  description: string
  enabled: boolean
  schedule: string
  schedule_apply_mode: string
  enablement_apply_mode: string
  latest_run_id: number | null
  latest_run_status: string | null
  latest_run_started_at: string | null
}

export type RuntimeDesiredState = {
  scheduler_enabled: boolean
  jobs: RuntimeSchedulerJob[]
}

export type RuntimeLogsExcerpt = {
  available: boolean
  excerpt: string
  path: string
  updated_at?: string
}

export type RuntimeInstance = {
  runtime_id: string
  runtime_name: string
  display_name: string
  provider: RuntimeProvider
  observed_state: RuntimeObservedState
  type?: string | null
  stack?: string | null
  entrypoint?: string | null
  health?: string | null
  supported_actions: Array<'probe' | 'restart' | 'tail_logs' | 'trigger_now'>
  logs_available: boolean
  scheduler_supported: boolean
  desired_state?: RuntimeDesiredState
  logs_excerpt?: RuntimeLogsExcerpt
  recent_actions?: RuntimeActionRun[]
}

export type RuntimeActionCreatePayload = {
  runtime_id: string
  action_type: RuntimeActionRun['action_type']
  reason?: string
  target_job_name?: string
}

export type RuntimeDesiredStatePatchPayload = {
  scheduler_enabled?: boolean
  jobs?: Array<{
    job_name: string
    enabled?: boolean
    schedule?: string
  }>
}

export async function getRuntimeControlCatalog(): Promise<RuntimeInstance[]> {
  const response = await apiClient.get<{ runtimes: RuntimeInstance[] }>(
    '/api/v2/system/runtime-control/catalog/',
    { skipGlobalError: true },
  )
  return response.data.runtimes ?? []
}

export async function getRuntimeControlRuntime(runtimeId: string): Promise<RuntimeInstance> {
  const response = await apiClient.get<{ runtime: RuntimeInstance }>(
    `/api/v2/system/runtime-control/runtimes/${encodeURIComponent(runtimeId)}/`,
    { skipGlobalError: true },
  )
  return response.data.runtime
}

export async function createRuntimeControlAction(
  payload: RuntimeActionCreatePayload,
): Promise<RuntimeActionRun> {
  const response = await apiClient.post<{ action: RuntimeActionRun }>(
    '/api/v2/system/runtime-control/actions/',
    payload,
    { skipGlobalError: true },
  )
  return response.data.action
}

export async function patchRuntimeControlDesiredState(
  runtimeId: string,
  payload: RuntimeDesiredStatePatchPayload,
): Promise<RuntimeDesiredState> {
  const response = await apiClient.patch<{ runtime_id: string; desired_state: RuntimeDesiredState }>(
    `/api/v2/system/runtime-control/runtimes/${encodeURIComponent(runtimeId)}/desired-state/`,
    payload,
    { skipGlobalError: true },
  )
  return response.data.desired_state
}
