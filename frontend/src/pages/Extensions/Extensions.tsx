import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Alert, App, Button, Checkbox, Grid, Input, Select, Space, Switch, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import dayjs from 'dayjs'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { getV2 } from '../../api/generated'
import { useClusters } from '../../api/queries/clusters'
import { useDatabases } from '../../api/queries/databases'
import {
  type ManualOperationKey,
  useDeleteManualOperationBinding,
  useManualOperationBindings,
  useUpsertManualOperationBinding,
} from '../../api/queries/extensionsManualOperations'
import {
  type ExtensionsFlagAggregate,
  useExtensionsOverview,
  useExtensionsOverviewDatabases,
  type ExtensionsOverviewDatabaseRow,
  type ExtensionsOverviewRow,
} from '../../api/queries/extensions'
import { listOperationCatalogExposures } from '../../api/operationCatalog'
import { tryShowIbcmdCliUiError } from '../../components/ibcmd/ibcmdCliUiErrors'
import { DrawerSurfaceShell, PageHeader, WorkspacePage } from '../../components/platform'
import { useAuthz } from '../../authz/useAuthz'
import { confirmWithTracking } from '../../observability/confirmWithTracking'
import {
  ExtensionsBindingsTable,
  ExtensionsDriftTable,
  ExtensionsDrilldownTable,
  ExtensionsOverviewTable,
} from './ExtensionsTables'
import {
  buildSetFlagsRuntimeInput,
  hasSetFlagsMaskSelection,
  resolveExtensionsApplyMode,
  type SetFlagsPolicyState,
} from './setFlagsWorkflow'

const { Text } = Typography

const api = getV2()
const { useBreakpoint } = Grid

type Status = 'active' | 'inactive' | 'missing' | 'unknown'

const statusTagColor = (status: Status): string => {
  if (status === 'active') return 'green'
  if (status === 'inactive') return 'orange'
  if (status === 'missing') return 'red'
  return 'default'
}

const boolTag = (value: boolean | null | undefined) => {
  if (value === true) return <Tag color="green">on</Tag>
  if (value === false) return <Tag color="red">off</Tag>
  return <Text type="secondary">—</Text>
}

type ObservedState = 'on' | 'off' | 'mixed' | 'unknown'

const observedStateTag = (state: ObservedState | undefined) => {
  if (!state) return <Text type="secondary">—</Text>
  if (state === 'on') return <Tag color="green">observed: on</Tag>
  if (state === 'off') return <Tag color="red">observed: off</Tag>
  if (state === 'mixed') return <Tag color="gold">observed: mixed</Tag>
  return <Tag>observed: unknown</Tag>
}

const flagCell = (flag: ExtensionsFlagAggregate | undefined | null) => {
  if (!flag) return <Text type="secondary">—</Text>

  const state = (flag.observed?.state as ObservedState | undefined) ?? undefined
  const tooltip = (
    <div style={{ maxWidth: 360 }}>
      <div>Observed: true={flag.observed?.true_count ?? 0}, false={flag.observed?.false_count ?? 0}, unknown={flag.observed?.unknown_count ?? 0}</div>
      <div>Drift: {flag.drift_count ?? 0}, Unknown drift: {flag.unknown_drift_count ?? 0}</div>
    </div>
  )

  const showDrift = (flag.drift_count ?? 0) > 0
  const showUnknownDrift = (flag.unknown_drift_count ?? 0) > 0

  return (
    <Tooltip title={tooltip}>
      <Space size={6} wrap>
        {boolTag(flag.policy)}
        {observedStateTag(state)}
        {showDrift && <Tag color="red">drift: {flag.drift_count}</Tag>}
        {showUnknownDrift && <Tag color="orange">unknown drift: {flag.unknown_drift_count}</Tag>}
      </Space>
    </Tooltip>
  )
}

const normalizePolicyBool = (value: unknown): boolean | null => {
  if (value === true) return true
  if (value === false) return false
  return null
}

type UIBinding = {
  target_ref?: string
  source_ref?: string
  resolve_at?: string
  sensitive?: boolean
  status?: string
  reason?: string | null
}

const extractBindings = (bindings: unknown): UIBinding[] => {
  if (!Array.isArray(bindings)) return []
  return bindings.filter((item) => item && typeof item === 'object') as UIBinding[]
}

const formatExecutionPlan = (executionPlan: unknown): string => {
  if (!executionPlan || typeof executionPlan !== 'object') return ''
  const plan = executionPlan as Record<string, unknown>
  const kind = typeof plan.kind === 'string' ? plan.kind : ''
  const argv = Array.isArray(plan.argv_masked) ? plan.argv_masked.filter((x) => typeof x === 'string') : []
  const workflowId = typeof plan.workflow_id === 'string' ? plan.workflow_id : null
  const lines: string[] = []
  if (kind) lines.push(`kind: ${kind}`)
  if (workflowId) lines.push(`workflow_id: ${workflowId}`)
  if (argv.length > 0) {
    lines.push('argv_masked:')
    lines.push(...argv.map((x) => `  ${x}`))
  }
  return lines.join('\n')
}

const MANUAL_OPERATION_OPTIONS: Array<{ value: ManualOperationKey; label: string }> = [
  { value: 'extensions.sync', label: 'extensions.sync' },
  { value: 'extensions.set_flags', label: 'extensions.set_flags' },
]

type TemplateOption = {
  value: string
  label: string
  description?: string
  capability?: string
}

export const Extensions = () => {
  const navigate = useNavigate()
  const { message, modal } = App.useApp()
  const { isStaff } = useAuthz()
  const [searchParams, setSearchParams] = useSearchParams()
  const screens = useBreakpoint()
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.lg
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < 992
        : false
    )
  const hasTenantContext = Boolean(localStorage.getItem('active_tenant_id'))
  const mutatingDisabled = isStaff && !hasTenantContext

  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<Status | undefined>(undefined)
  const [version, setVersion] = useState('')
  const [databaseId, setDatabaseId] = useState<string | undefined>(undefined)
  const [clusterId, setClusterId] = useState<string | undefined>(undefined)

  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  const clustersQuery = useClusters({ limit: 500, offset: 0 })
  const clusterOptions = useMemo(() => {
    const clusters = clustersQuery.data?.clusters ?? []
    return clusters
      .map((c) => ({ label: c.name || c.id, value: c.id }))
      .sort((a, b) => a.label.localeCompare(b.label))
  }, [clustersQuery.data?.clusters])

  const databasesQuery = useDatabases({ filters: { cluster_id: clusterId, limit: 500, offset: 0 } })
  const databaseOptions = useMemo(() => {
    const databases = databasesQuery.data?.databases ?? []
    return databases
      .map((db) => ({ label: db.name || db.id, value: db.id }))
      .sort((a, b) => a.label.localeCompare(b.label))
  }, [databasesQuery.data?.databases])

  const overviewQuery = useExtensionsOverview({
    search: search.trim() || undefined,
    status,
    version: version.trim() || undefined,
    database_id: databaseId,
    cluster_id: clusterId,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  })

  const selectedExtension = (searchParams.get('extension') || '').trim() || null
  const drawerOpen = Boolean(selectedExtension)
  const [drawerStatus, setDrawerStatus] = useState<Status | undefined>(undefined)
  const [drawerVersion, setDrawerVersion] = useState<string>('')
  const [drawerPage, setDrawerPage] = useState(1)
  const [drawerPageSize, setDrawerPageSize] = useState(50)
  const [adoptPending, setAdoptPending] = useState(false)
  const [planPending, setPlanPending] = useState(false)
  const [applyPending, setApplyPending] = useState(false)

  const [drawerPolicy, setDrawerPolicy] = useState<SetFlagsPolicyState>({
    active: null,
    safe_mode: null,
    unsafe_action_protection: null,
  })

  const [applyActiveEnabled, setApplyActiveEnabled] = useState(false)
  const [applyActiveValue, setApplyActiveValue] = useState(false)
  const [applySafeModeEnabled, setApplySafeModeEnabled] = useState(false)
  const [applySafeModeValue, setApplySafeModeValue] = useState(false)
  const [applyUnsafeActionProtectionEnabled, setApplyUnsafeActionProtectionEnabled] = useState(false)
  const [applyUnsafeActionProtectionValue, setApplyUnsafeActionProtectionValue] = useState(false)

  const [manualOperation, setManualOperation] = useState<ManualOperationKey>('extensions.set_flags')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | undefined>(undefined)
  const drawerDatabaseId = (searchParams.get('database') || '').trim() || undefined
  const selectedDrawerDatabaseLabel = useMemo(() => {
    if (!drawerDatabaseId) {
      return null
    }
    return databaseOptions.find((option) => option.value === drawerDatabaseId)?.label ?? drawerDatabaseId
  }, [databaseOptions, drawerDatabaseId])

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
      if (next.toString() === searchParams.toString()) {
        return
      }
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )

  const bindingsQuery = useManualOperationBindings()
  const upsertBindingMutation = useUpsertManualOperationBinding()
  const deleteBindingMutation = useDeleteManualOperationBinding()

  const preferredBindingByOperation = useMemo(() => {
    const map = new Map<ManualOperationKey, { template_id: string; updated_at?: string | null; updated_by?: string | null }>()
    for (const row of bindingsQuery.data ?? []) {
      const operation = row?.manual_operation
      if (operation === 'extensions.sync' || operation === 'extensions.set_flags') {
        map.set(operation, {
          template_id: String(row.template_id || ''),
          updated_at: row.updated_at,
          updated_by: row.updated_by,
        })
      }
    }
    return map
  }, [bindingsQuery.data])
  const preferredBinding = preferredBindingByOperation.get(manualOperation) ?? null

  const templatesQuery = useQuery({
    queryKey: ['extensions', 'manual-operation-templates', manualOperation],
    enabled: drawerOpen,
    queryFn: async () => listOperationCatalogExposures({
      surface: 'template',
      capability: manualOperation,
      status: 'published',
      limit: 500,
      offset: 0,
    }),
  })
  const templateOptions = useMemo<TemplateOption[]>(() => {
    const items: TemplateOption[] = []
    for (const exposure of templatesQuery.data?.exposures ?? []) {
      if (exposure.surface !== 'template') continue
      const alias = String(exposure.alias || '').trim()
      if (!alias) continue
      const name = String(exposure.name || alias).trim() || alias
      const description = String(exposure.description || '').trim()
      const capability = String(exposure.capability || '').trim()
      items.push({
        value: alias,
        label: description ? `${name} (${alias})` : name,
        description,
        capability: capability || undefined,
      })
    }
    items.sort((a, b) => a.label.localeCompare(b.label))
    return items
  }, [templatesQuery.data?.exposures])
  const templatesById = useMemo(() => {
    const map = new Map<string, TemplateOption>()
    for (const option of templateOptions) {
      map.set(option.value, option)
    }
    return map
  }, [templateOptions])
  const selectedTemplate = useMemo(() => {
    if (!selectedTemplateId) return null
    return templatesById.get(selectedTemplateId) ?? null
  }, [selectedTemplateId, templatesById])
  const templateSelectionMissing = !selectedTemplateId && !preferredBinding
  const setFlagsOperationSelected = manualOperation === 'extensions.set_flags'

  useEffect(() => {
    if (!drawerOpen) return
    const optionValues = new Set(templateOptions.map((item) => item.value))
    if (selectedTemplateId && optionValues.has(selectedTemplateId)) return
    const preferredTemplateId = preferredBinding?.template_id
    if (preferredTemplateId && optionValues.has(preferredTemplateId)) {
      setSelectedTemplateId(preferredTemplateId)
      return
    }
    setSelectedTemplateId(undefined)
  }, [drawerOpen, preferredBinding?.template_id, selectedTemplateId, templateOptions])

  const drilldownEnabled = drawerOpen && Boolean(selectedExtension)
  const drilldownQuery = useExtensionsOverviewDatabases({
    name: selectedExtension || '',
    database_id: drawerDatabaseId,
    status: drawerStatus,
    version: drawerVersion.trim() || undefined,
    cluster_id: clusterId,
    limit: drawerDatabaseId ? 100 : drawerPageSize,
    offset: drawerDatabaseId ? 0 : (drawerPage - 1) * drawerPageSize,
  }, drilldownEnabled)
  const applyMode = resolveExtensionsApplyMode(drawerDatabaseId)
  const fallbackMode = applyMode === 'targeted_fallback'
  const runtimeInputPreview = useMemo(() => buildSetFlagsRuntimeInput(
    {
      applyActiveEnabled,
      applyActiveValue,
      applySafeModeEnabled,
      applySafeModeValue,
      applyUnsafeActionProtectionEnabled,
      applyUnsafeActionProtectionValue,
    },
    drawerPolicy,
  ), [
    applyActiveEnabled,
    applyActiveValue,
    applySafeModeEnabled,
    applySafeModeValue,
    applyUnsafeActionProtectionEnabled,
    applyUnsafeActionProtectionValue,
    drawerPolicy,
  ])
  const hasRuntimeMaskSelection = hasSetFlagsMaskSelection(runtimeInputPreview.applyMask)

  const resetApplyFormFromPolicy = (policy?: { active?: unknown; safe_mode?: unknown; unsafe_action_protection?: unknown } | null) => {
    const active = normalizePolicyBool(policy?.active)
    const safeMode = normalizePolicyBool(policy?.safe_mode)
    const unsafeActionProtection = normalizePolicyBool(policy?.unsafe_action_protection)
    setDrawerPolicy({
      active,
      safe_mode: safeMode,
      unsafe_action_protection: unsafeActionProtection,
    })
    setApplyActiveEnabled(active !== null)
    setApplyActiveValue(Boolean(active))
    setApplySafeModeEnabled(safeMode !== null)
    setApplySafeModeValue(Boolean(safeMode))
    setApplyUnsafeActionProtectionEnabled(unsafeActionProtection !== null)
    setApplyUnsafeActionProtectionValue(Boolean(unsafeActionProtection))
  }

  const openDrawer = (row: ExtensionsOverviewRow) => {
    updateSearchParams({
      extension: row.name,
      database: databaseId ?? null,
    })
    // Propagate current page-level filters into drawer by default so drilldown/apply works on the same slice.
    setDrawerStatus(status)
    setDrawerVersion(version)
    setDrawerPage(1)
    setDrawerPageSize(50)
    resetApplyFormFromPolicy(row.flags ? {
      active: row.flags.active?.policy,
      safe_mode: row.flags.safe_mode?.policy,
      unsafe_action_protection: row.flags.unsafe_action_protection?.policy,
    } : null)
  }

  const runAdoptPolicy = () => {
    if (!selectedExtension) return
    if (!drawerDatabaseId) return
    if (mutatingDisabled) return
    if (adoptPending) return

    let reason = ''
    confirmWithTracking(modal, {
      title: 'Adopt flags policy from database?',
      content: (
        <Space direction="vertical" size="small">
          <div>
            This will overwrite policy for <Text code>{selectedExtension}</Text> using the observed snapshot from database <Text code>{drawerDatabaseId}</Text>.
          </div>
          <Input.TextArea
            placeholder="Reason (optional)"
            rows={3}
            onChange={(e) => { reason = e.target.value }}
          />
        </Space>
      ),
      okText: 'Adopt',
      cancelText: 'Cancel',
      onOk: async () => {
        setAdoptPending(true)
        try {
          const policy = await api.postExtensionsFlagsPolicyAdopt({
            database_id: drawerDatabaseId,
            extension_name: selectedExtension,
            reason: reason.trim() || undefined,
          })
          message.success('Policy updated from database snapshot')
          resetApplyFormFromPolicy(policy)
          await overviewQuery.refetch()
          if (drilldownEnabled) await drilldownQuery.refetch()
        } catch (e: unknown) {
          if (!tryShowIbcmdCliUiError(e, modal, message)) {
            const errorMessage = e instanceof Error ? e.message : 'unknown error'
            message.error(`Failed to adopt policy: ${errorMessage}`)
          }
        } finally {
          setAdoptPending(false)
        }
      },
    })
  }

  const savePreferredBinding = async () => {
    if (!selectedTemplateId) {
      message.info('Select template first')
      return
    }
    if (mutatingDisabled) return
    try {
      await upsertBindingMutation.mutateAsync({
        manualOperation,
        templateId: selectedTemplateId,
      })
      message.success('Preferred template binding updated')
    } catch (e: unknown) {
      if (!tryShowIbcmdCliUiError(e, modal, message)) {
        const errorMessage = e instanceof Error ? e.message : 'unknown error'
        message.error(`Failed to update preferred binding: ${errorMessage}`)
      }
    }
  }

  const clearPreferredBinding = async () => {
    if (!preferredBinding) return
    if (mutatingDisabled) return
    try {
      await deleteBindingMutation.mutateAsync(manualOperation)
      message.success('Preferred template binding removed')
    } catch (e: unknown) {
      if (!tryShowIbcmdCliUiError(e, modal, message)) {
        const errorMessage = e instanceof Error ? e.message : 'unknown error'
        message.error(`Failed to remove preferred binding: ${errorMessage}`)
      }
    }
  }

  const runApplyPolicy = async () => {
    if (!selectedExtension) return
    if (mutatingDisabled) return
    if (planPending || applyPending) return
    if (templateSelectionMissing) {
      message.error('Select template or configure preferred binding')
      return
    }

    const isSetFlagsOperation = manualOperation === 'extensions.set_flags'
    const mode = resolveExtensionsApplyMode(drawerDatabaseId)
    const applyTitle = isSetFlagsOperation
      ? (mode === 'targeted_fallback' ? 'Apply selected flags in fallback mode?' : 'Launch workflow-first flags rollout?')
      : 'Launch extensions sync?'
    const applySuccessMessage = isSetFlagsOperation
      ? (mode === 'targeted_fallback'
        ? 'Operation queued: targeted fallback apply'
        : 'Operation queued: workflow-first rollout')
      : 'Operation queued: extensions sync'

    const { applyMask, flagsValues } = buildSetFlagsRuntimeInput(
      {
        applyActiveEnabled,
        applyActiveValue,
        applySafeModeEnabled,
        applySafeModeValue,
        applyUnsafeActionProtectionEnabled,
        applyUnsafeActionProtectionValue,
      },
      drawerPolicy,
    )
    if (isSetFlagsOperation && !hasSetFlagsMaskSelection(applyMask)) {
      message.error('Select at least one flag to apply')
      return
    }

    const buildPlanRequest = (databaseIds: string[]) => {
      if (isSetFlagsOperation) {
        return {
          database_ids: databaseIds,
          manual_operation: manualOperation,
          template_id: selectedTemplateId || undefined,
          extension_name: selectedExtension,
          flags_values: flagsValues,
          apply_mask: applyMask,
        }
      }
      return {
        database_ids: databaseIds,
        manual_operation: manualOperation,
        template_id: selectedTemplateId || undefined,
      }
    }

    setPlanPending(true)
    try {
      const dbIds: string[] = []

      if (drawerDatabaseId) {
        dbIds.push(drawerDatabaseId)
      } else {
        const resp = await api.getExtensionsOverviewDatabases({
          name: selectedExtension,
          status: drawerStatus,
          version: drawerVersion.trim() || undefined,
          cluster_id: clusterId,
          limit: 500,
          offset: 0,
        })
        const total = resp.total ?? 0
        if (total > 500) {
          modal.error({
            title: 'Too many databases',
            content: `This operation is limited to 500 databases per run (matched: ${total}). Narrow filters and retry.`,
          })
          return
        }
        for (const item of resp.databases ?? []) {
          if (item?.database_id) dbIds.push(String(item.database_id))
        }
      }

      const databaseIds = Array.from(new Set(dbIds)).filter(Boolean)
      if (databaseIds.length === 0) {
        message.info('No target databases matched current filters')
        return
      }

      const plan = await api.postExtensionsPlan(buildPlanRequest(databaseIds))

      const previewText = formatExecutionPlan(plan.execution_plan)
      const bindings = extractBindings(plan.bindings)
      const bindingColumns: ColumnsType<UIBinding> = [
        { title: 'Target', dataIndex: 'target_ref', key: 'target_ref' },
        { title: 'Source', dataIndex: 'source_ref', key: 'source_ref' },
        { title: 'Resolve', dataIndex: 'resolve_at', key: 'resolve_at', width: 90 },
        {
          title: 'Sensitive',
          dataIndex: 'sensitive',
          key: 'sensitive',
          width: 90,
          render: (value: boolean | undefined) => (value ? <Tag color="red">yes</Tag> : <Tag>no</Tag>),
        },
        { title: 'Status', dataIndex: 'status', key: 'status', width: 110 },
        { title: 'Reason', dataIndex: 'reason', key: 'reason' },
      ]

      confirmWithTracking(modal, {
        title: applyTitle,
        content: (
          <div>
            <div style={{ marginBottom: 8 }}>
              Extension <Text code>{selectedExtension}</Text> will be processed on {databaseIds.length} database(s).
            </div>
            <div style={{ marginBottom: 8 }}>
              Manual operation: <Text code>{manualOperation}</Text>
            </div>
            <div style={{ marginBottom: 8 }}>
              Template: <Text code>{selectedTemplateId || preferredBinding?.template_id || 'preferred binding'}</Text>
            </div>
            {isSetFlagsOperation && (
              <>
                <div style={{ marginBottom: 8 }}>
                  Mode:{' '}
                  {mode === 'targeted_fallback'
                    ? <Tag color="orange">fallback / targeted</Tag>
                    : <Tag color="blue">workflow-first / bulk</Tag>}
                </div>
                <Space size={8} wrap style={{ marginBottom: 8 }}>
                  <div>Active: {applyMask.active ? boolTag(flagsValues.active) : <Text type="secondary">skipped</Text>}</div>
                  <div>Safe mode: {applyMask.safe_mode ? boolTag(flagsValues.safe_mode) : <Text type="secondary">skipped</Text>}</div>
                  <div>Unsafe action protection: {applyMask.unsafe_action_protection ? boolTag(flagsValues.unsafe_action_protection) : <Text type="secondary">skipped</Text>}</div>
                </Space>
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary">
                    Runtime source: this launch request sends explicit <Text code>flags_values</Text> and <Text code>apply_mask</Text>.
                  </Text>
                </div>
              </>
            )}
            {previewText ? (
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{previewText}</pre>
            ) : (
              <div style={{ opacity: 0.7 }}>Preview not available</div>
            )}
            {isStaff && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Binding Provenance:</div>
                {bindings.length > 0 ? (
                  <ExtensionsBindingsTable
                    data={bindings}
                    columns={bindingColumns}
                  />
                ) : (
                  <div style={{ opacity: 0.7 }}>No bindings</div>
                )}
              </div>
            )}
          </div>
        ),
        okText: 'Apply',
        cancelText: 'Cancel',
        onOk: async () => {
          setApplyPending(true)
          try {
            const res = await api.postExtensionsApply({ plan_id: plan.plan_id })
            message.success(applySuccessMessage)
            if (res.operation_id) {
              navigate(`/operations?operation=${res.operation_id}`)
            }
          } catch (e: unknown) {
            const maybe = e as { response?: { status?: number; data?: unknown } } | null
            if (maybe?.response?.status === 409) {
              const data = maybe?.response?.data
              const extractCode = (value: unknown): string | null => {
                if (!value || typeof value !== 'object') return null
                const err = (value as Record<string, unknown>).error
                if (!err || typeof err !== 'object') return null
                const code = (err as Record<string, unknown>).code
                return typeof code === 'string' ? code : null
              }
              const code = extractCode(data)

              if (code === 'DRIFT_CONFLICT' && data && typeof data === 'object') {
                const driftRaw = (data as Record<string, unknown>).drift
                const drift = driftRaw && typeof driftRaw === 'object' ? driftRaw as Record<string, unknown> : null
                const driftRows = drift
                  ? Object.entries(drift).map(([databaseId, entry]) => {
                    const entryRecord = entry && typeof entry === 'object'
                      ? entry as Record<string, unknown>
                      : null
                    const base = entryRecord?.base
                    const current = entryRecord?.current
                    const baseRecord = base && typeof base === 'object' ? base as Record<string, unknown> : null
                    const currentRecord = current && typeof current === 'object' ? current as Record<string, unknown> : null
                    return {
                      database_id: databaseId,
                      base_at: typeof baseRecord?.at === 'string' ? baseRecord.at : '',
                      current_at: typeof currentRecord?.at === 'string' ? currentRecord.at : '',
                      base_hash: typeof baseRecord?.hash === 'string' ? baseRecord.hash : '',
                      current_hash: typeof currentRecord?.hash === 'string' ? currentRecord.hash : '',
                    }
                  })
                  : []

                confirmWithTracking(modal, {
                  title: 'State changed',
                  content: (
                    <div>
                      <div style={{ marginBottom: 8 }}>
                        Some target databases changed since the plan was built. Re-plan is required.
                      </div>
                      {driftRows.length > 0 ? (
                        <ExtensionsDriftTable data={driftRows.slice(0, 10)} />
                      ) : (
                        <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
                          {JSON.stringify(data ?? {}, null, 2)}
                        </pre>
                      )}
                      {driftRows.length > 10 ? (
                        <div style={{ marginTop: 8, opacity: 0.7 }}>
                          Showing 10 of {driftRows.length} drifted databases.
                        </div>
                      ) : null}
                    </div>
                  ),
                  okText: 'Re-plan and retry',
                  cancelText: 'Close',
                  onOk: async () => {
                    setApplyPending(true)
                    try {
                      const nextPlan = await api.postExtensionsPlan(buildPlanRequest(databaseIds))
                      const res = await api.postExtensionsApply({ plan_id: nextPlan.plan_id })
                      message.success(applySuccessMessage)
                      if (res.operation_id) {
                        navigate(`/operations?operation=${res.operation_id}`)
                      }
                    } finally {
                      setApplyPending(false)
                    }
                  },
                })
                return
              }

              modal.error({
                title: 'Conflict',
                content: (
                  <pre style={{ whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(data ?? {}, null, 2)}
                  </pre>
                ),
              })
            } else if (!tryShowIbcmdCliUiError(e, modal, message)) {
              const errorMessage = e instanceof Error ? e.message : 'unknown error'
              message.error(`Failed to apply rollout: ${errorMessage}`)
            }
          } finally {
            setApplyPending(false)
          }
        },
      })
    } catch (e: unknown) {
      const maybe = e as { response?: { data?: unknown } } | null
      const extractErrorCode = (data: unknown): string | null => {
        if (!data || typeof data !== 'object') return null
        const err = (data as Record<string, unknown>).error
        if (!err || typeof err !== 'object') return null
        const code = (err as Record<string, unknown>).code
        return typeof code === 'string' ? code : null
      }
      const code = extractErrorCode(maybe?.response?.data)
      if (code === 'MISSING_TEMPLATE_BINDING') {
        message.error('Preferred template binding is missing. Select a template or configure preferred binding.')
        return
      }
      if (code === 'CONFIGURATION_ERROR') {
        message.error('Selected template is incompatible with this manual operation.')
        return
      }
      if (!tryShowIbcmdCliUiError(e, modal, message)) {
        const errorMessage = e instanceof Error ? e.message : 'unknown error'
        message.error(`Failed to build plan: ${errorMessage}`)
      }
    } finally {
      setPlanPending(false)
    }
  }

  const overviewColumns: ColumnsType<ExtensionsOverviewRow> = [
    {
      title: 'Extension',
      dataIndex: 'name',
      key: 'name',
      render: (value: string, row) => (
        <Button
          type="link"
          style={{ padding: 0 }}
          onClick={() => openDrawer(row)}
          aria-label={`Open extension ${value}`}
        >
          {value}
        </Button>
      ),
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: 'Purpose',
      dataIndex: 'purpose',
      key: 'purpose',
      render: (v: string | null | undefined) => v ? <Text>{v}</Text> : <Text type="secondary">—</Text>,
    },
    {
      title: 'Active',
      key: 'active_policy',
      render: (_: unknown, row) => flagCell(row.flags?.active),
    },
    {
      title: 'Safe mode',
      key: 'safe_mode_policy',
      render: (_: unknown, row) => flagCell(row.flags?.safe_mode),
    },
    {
      title: 'Unsafe action protection',
      key: 'unsafe_action_protection_policy',
      render: (_: unknown, row) => flagCell(row.flags?.unsafe_action_protection),
    },
    {
      title: 'Installed',
      key: 'installed',
      align: 'right',
      render: (_: unknown, row) => <Text>{row.installed_count}</Text>,
    },
    {
      title: 'Missing',
      dataIndex: 'missing_count',
      key: 'missing_count',
      align: 'right',
      render: (v: number) => <Text>{v}</Text>,
    },
    {
      title: 'Unknown',
      dataIndex: 'unknown_count',
      key: 'unknown_count',
      align: 'right',
      render: (v: number) => <Text>{v}</Text>,
    },
    {
      title: 'Versions',
      dataIndex: 'versions',
      key: 'versions',
      render: (versions: { version: string | null; count: number }[]) => {
        const top = [...(versions || [])]
          .filter((v) => v.count > 0)
          .sort((a, b) => b.count - a.count)
          .slice(0, 4)
        if (top.length === 0) {
          return <Text type="secondary">—</Text>
        }
        return (
          <Space size={4} wrap>
            {top.map((v) => (
              <Tag key={`${v.version ?? 'null'}-${v.count}`}>{v.version ?? '—'}: {v.count}</Tag>
            ))}
          </Space>
        )
      },
    },
    {
      title: 'Latest snapshot',
      dataIndex: 'latest_snapshot_at',
      key: 'latest_snapshot_at',
      render: (value?: string | null) => (
        value ? <Text>{dayjs(value).format('DD.MM.YYYY HH:mm')}</Text> : <Text type="secondary">—</Text>
      ),
    },
  ]

  const overviewPagination: TablePaginationConfig = {
    current: page,
    pageSize,
    total: overviewQuery.data?.total ?? 0,
    showSizeChanger: true,
    pageSizeOptions: [20, 50, 100, 200],
    onChange: (nextPage, nextPageSize) => {
      setPage(nextPage)
      if (nextPageSize && nextPageSize !== pageSize) {
        setPageSize(nextPageSize)
        setPage(1)
      }
    },
  }

  const drillColumns: ColumnsType<ExtensionsOverviewDatabaseRow> = [
    {
      title: 'Database',
      dataIndex: 'database_name',
      key: 'database_name',
      render: (value: string) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => navigate('/databases')}>
          {value}
        </Button>
      ),
    },
    {
      title: 'Cluster',
      key: 'cluster',
      render: (_: unknown, row) => (
        <Text type="secondary">{row.cluster_name || row.cluster_id || '—'}</Text>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (value: Status) => (
        <Tag color={statusTagColor(value)}>{value}</Tag>
      ),
    },
    {
      title: 'Active',
      key: 'active_observed',
      render: (_: unknown, row) => boolTag(row.flags?.active),
    },
    {
      title: 'Safe mode',
      key: 'safe_mode_observed',
      render: (_: unknown, row) => boolTag(row.flags?.safe_mode),
    },
    {
      title: 'Unsafe action protection',
      key: 'unsafe_action_protection_observed',
      render: (_: unknown, row) => boolTag(row.flags?.unsafe_action_protection),
    },
    {
      title: 'Version',
      dataIndex: 'version',
      key: 'version',
      render: (value?: string | null) => (
        value ? <Text>{value}</Text> : <Text type="secondary">—</Text>
      ),
    },
    {
      title: 'Snapshot',
      dataIndex: 'snapshot_updated_at',
      key: 'snapshot_updated_at',
      render: (value?: string | null) => (
        value ? <Text>{dayjs(value).format('DD.MM.YYYY HH:mm')}</Text> : <Text type="secondary">—</Text>
      ),
    },
  ]

  const drillPagination: TablePaginationConfig | false = drawerDatabaseId ? false : {
    current: drawerPage,
    pageSize: drawerPageSize,
    total: drilldownQuery.data?.total ?? 0,
    showSizeChanger: true,
    pageSizeOptions: [20, 50, 100, 200],
    onChange: (nextPage, nextPageSize) => {
      setDrawerPage(nextPage)
      if (nextPageSize && nextPageSize !== drawerPageSize) {
        setDrawerPageSize(nextPageSize)
        setDrawerPage(1)
      }
    },
  }

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="Extensions"
          subtitle="Management workspace with URL-backed selected extension context and secondary drill-down surface."
          actions={(
            <Button
              data-testid="extensions-refresh"
              onClick={() => overviewQuery.refetch()}
              loading={overviewQuery.isFetching}
            >
              Refresh
            </Button>
          )}
        />
      )}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }} data-testid="extensions-page">
        <Space wrap>
        <Input
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          placeholder="Search extension name"
          style={{ width: 260 }}
          allowClear
        />
        <Select
          value={status}
          onChange={(v) => { setStatus(v); setPage(1) }}
          allowClear
          placeholder="Status"
          style={{ width: 180 }}
          options={[
            { value: 'active', label: 'active' },
            { value: 'inactive', label: 'inactive' },
            { value: 'missing', label: 'missing' },
            { value: 'unknown', label: 'unknown' },
          ]}
        />
        <Input
          data-testid="extensions-overview-version"
          value={version}
          onChange={(e) => { setVersion(e.target.value); setPage(1) }}
          placeholder="Version (exact)"
          style={{ width: 220 }}
          allowClear
        />
        <Select
          data-testid="extensions-overview-database"
          value={databaseId}
          onChange={(v) => { setDatabaseId(v); setPage(1) }}
          allowClear
          placeholder="Database"
          style={{ width: 320 }}
          options={databaseOptions}
          loading={databasesQuery.isLoading}
          showSearch
          optionFilterProp="label"
        />
        <Select
          value={clusterId}
          onChange={(v) => {
            setClusterId(v)
            setDatabaseId(undefined)
            updateSearchParams({ database: null })
            setPage(1)
            setDrawerPage(1)
          }}
          allowClear
          placeholder="Cluster"
          style={{ width: 260 }}
          options={clusterOptions}
          loading={clustersQuery.isLoading}
          showSearch
          optionFilterProp="label"
        />
        <Text type="secondary">
          Total DBs: {overviewQuery.data?.total_databases ?? '—'}
        </Text>
        </Space>

        {overviewQuery.isError && (
          <Alert type="error" showIcon message="Failed to load extensions overview" />
        )}

        <ExtensionsOverviewTable
          columns={overviewColumns}
          data={overviewQuery.data?.extensions ?? []}
          loading={overviewQuery.isLoading}
          pagination={overviewPagination}
        />

        <DrawerSurfaceShell
          title={selectedExtension ? `Extension: ${selectedExtension}` : 'Extension'}
          open={drawerOpen}
          onClose={() => updateSearchParams({ extension: null, database: null })}
          width={860}
          drawerTestId="extensions-management-drawer"
        >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {selectedExtension ? (
            <Text data-testid="extensions-selected-name" strong>
              {selectedExtension}
            </Text>
          ) : null}
          {selectedDrawerDatabaseLabel ? (
            <Text data-testid="extensions-selected-database" type="secondary">
              {selectedDrawerDatabaseLabel}
            </Text>
          ) : null}
          {mutatingDisabled && (
            <Alert
              type="warning"
              showIcon
              message="Mutating actions are disabled"
              description="Staff users must select a tenant (X-CC1C-Tenant-ID) to run mutating actions."
            />
          )}

          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Text strong>Run manual operation</Text>
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Alert
                type={setFlagsOperationSelected && fallbackMode ? 'warning' : 'info'}
                showIcon
                data-testid="extensions-apply-mode-hint"
                message={setFlagsOperationSelected
                  ? (fallbackMode ? 'Fallback mode (targeted)' : 'Workflow-first mode (bulk)')
                  : 'Template-based sync mode'}
                description={setFlagsOperationSelected
                  ? (fallbackMode
                    ? 'Use for emergency/single DB changes only.'
                    : 'Primary path for mass rollout. Progress is tracked in Operations.')
                  : 'Runs extensions.sync through selected template and manual-operation contract.'}
              />
              <Space
                align={isNarrow ? 'start' : 'center'}
                direction={isNarrow ? 'vertical' : 'horizontal'}
                style={{ width: '100%' }}
              >
                <Text type="secondary">Operation</Text>
                <Select
                  data-testid="extensions-apply-manual-operation"
                  value={manualOperation}
                  options={MANUAL_OPERATION_OPTIONS}
                  onChange={(value) => setManualOperation(value)}
                  style={{ width: isNarrow ? '100%' : 280 }}
                />
              </Space>
              <Space
                align={isNarrow ? 'start' : 'center'}
                direction={isNarrow ? 'vertical' : 'horizontal'}
                style={{ width: '100%' }}
              >
                <Text type="secondary">Template</Text>
                <Select
                  data-testid="extensions-apply-template"
                  value={selectedTemplateId}
                  onChange={(value) => setSelectedTemplateId(value)}
                  options={templateOptions}
                  placeholder={templatesQuery.isLoading ? 'Loading templates…' : 'Select template (or rely on preferred)'}
                  loading={templatesQuery.isLoading}
                  allowClear
                  style={{ width: isNarrow ? '100%' : 420 }}
                />
                <Space wrap style={{ width: isNarrow ? '100%' : undefined }}>
                  <Button
                    size="small"
                    onClick={() => void savePreferredBinding()}
                    loading={upsertBindingMutation.isPending}
                    disabled={!selectedTemplateId || mutatingDisabled}
                  >
                    Save preferred
                  </Button>
                  <Button
                    size="small"
                    onClick={() => void clearPreferredBinding()}
                    loading={deleteBindingMutation.isPending}
                    disabled={!preferredBinding || mutatingDisabled}
                  >
                    Clear preferred
                  </Button>
                </Space>
              </Space>
              {templatesQuery.isError && (
                <Alert
                  type="error"
                  showIcon
                  message="Failed to load compatible templates"
                  description="Template list is unavailable. Retry later or reload the page."
                />
              )}
              {bindingsQuery.isError && (
                <Alert
                  type="warning"
                  showIcon
                  message="Preferred binding is unavailable"
                  description="Binding API is temporarily unavailable. You can still launch with explicit template override."
                />
              )}
              {preferredBinding && (
                <Space size={8} wrap data-testid="extensions-preferred-binding-summary">
                  <Tag color="geekblue">preferred</Tag>
                  <Tag>{preferredBinding.template_id}</Tag>
                  {preferredBinding.updated_at && (
                    <Tag>{dayjs(preferredBinding.updated_at).format('DD.MM.YYYY HH:mm')}</Tag>
                  )}
                  {preferredBinding.updated_by && <Tag>{preferredBinding.updated_by}</Tag>}
                </Space>
              )}
              {selectedTemplate && (
                <Space size={8} wrap data-testid="extensions-apply-template-summary">
                  <Tag color="blue">{selectedTemplate.value}</Tag>
                  <Tag>{selectedTemplate.capability || 'no capability'}</Tag>
                </Space>
              )}
              {templateSelectionMissing && (
                <Alert
                  type="warning"
                  showIcon
                  message="Template is not resolved"
                  description="Choose a template override or configure preferred template binding for this manual operation."
                />
              )}
              {setFlagsOperationSelected && (
                <>
                  <Alert
                    type="info"
                    showIcon
                    data-testid="extensions-apply-runtime-source-hint"
                    message="Runtime source of truth"
                    description={(
                      <Space direction="vertical" size={2}>
                        <Text>Values below are sent as <Text code>flags_values</Text> + <Text code>apply_mask</Text> in launch request.</Text>
                        <Text type="secondary">Template stores transport/binding only (`$flags.*` mapping).</Text>
                      </Space>
                    )}
                  />
                  <Space align="center" wrap>
                    <Checkbox
                      data-testid="extensions-apply-flag-active-enabled"
                      checked={applyActiveEnabled}
                      onChange={(e) => setApplyActiveEnabled(e.target.checked)}
                    >
                      Active
                    </Checkbox>
                    <Switch
                      data-testid="extensions-apply-flag-active-value"
                      checked={applyActiveValue}
                      onChange={setApplyActiveValue}
                      disabled={!applyActiveEnabled}
                    />
                  </Space>
                  <Space align="center" wrap>
                    <Checkbox
                      data-testid="extensions-apply-flag-safe-mode-enabled"
                      checked={applySafeModeEnabled}
                      onChange={(e) => setApplySafeModeEnabled(e.target.checked)}
                    >
                      Safe mode
                    </Checkbox>
                    <Switch
                      data-testid="extensions-apply-flag-safe-mode-value"
                      checked={applySafeModeValue}
                      onChange={setApplySafeModeValue}
                      disabled={!applySafeModeEnabled}
                    />
                  </Space>
                  <Space align="center" wrap>
                    <Checkbox
                      data-testid="extensions-apply-flag-unsafe-action-protection-enabled"
                      checked={applyUnsafeActionProtectionEnabled}
                      onChange={(e) => setApplyUnsafeActionProtectionEnabled(e.target.checked)}
                    >
                      Unsafe action protection
                    </Checkbox>
                    <Switch
                      data-testid="extensions-apply-flag-unsafe-action-protection-value"
                      checked={applyUnsafeActionProtectionValue}
                      onChange={setApplyUnsafeActionProtectionValue}
                      disabled={!applyUnsafeActionProtectionEnabled}
                    />
                  </Space>
                </>
              )}
              <Space wrap>
                <Tooltip
                  title={
                    mutatingDisabled
                      ? 'Select a tenant to enable this action'
                      : templateSelectionMissing
                        ? 'Template is not resolved'
                        : setFlagsOperationSelected && !hasRuntimeMaskSelection
                          ? 'Select at least one flag to apply'
                          : undefined
                  }
                >
                  <Button
                    type="primary"
                    onClick={runApplyPolicy}
                    loading={planPending || applyPending}
                    disabled={!selectedExtension || mutatingDisabled || templateSelectionMissing || (setFlagsOperationSelected && !hasRuntimeMaskSelection)}
                  >
                    Apply
                  </Button>
                </Tooltip>
                <Tooltip title={!drawerDatabaseId ? 'Select a database to adopt from' : (mutatingDisabled ? 'Select a tenant to enable this action' : undefined)}>
                  <Button
                    onClick={runAdoptPolicy}
                    loading={adoptPending}
                    disabled={!selectedExtension || !drawerDatabaseId || mutatingDisabled || !setFlagsOperationSelected}
                  >
                    Adopt from database
                  </Button>
                </Tooltip>
              </Space>
            </Space>
          </Space>

          <Space wrap>
            <Select
              data-testid="extensions-drawer-database"
              value={drawerDatabaseId}
              onChange={(v) => {
                updateSearchParams({ database: v ?? null })
                setDrawerPage(1)
              }}
              allowClear
              placeholder="Database"
              style={{ width: 320 }}
              options={databaseOptions}
              loading={databasesQuery.isLoading}
              showSearch
              optionFilterProp="label"
            />
            <Select
              value={drawerStatus}
              onChange={(v) => { setDrawerStatus(v); setDrawerPage(1) }}
              allowClear
              placeholder="Status"
              style={{ width: 180 }}
              options={[
                { value: 'active', label: 'active' },
                { value: 'inactive', label: 'inactive' },
                { value: 'missing', label: 'missing' },
                { value: 'unknown', label: 'unknown' },
              ]}
            />
            <Input
              value={drawerVersion}
              onChange={(e) => { setDrawerVersion(e.target.value); setDrawerPage(1) }}
              placeholder="Version (exact)"
              style={{ width: 220 }}
              allowClear
            />
            <Button onClick={() => drilldownQuery.refetch()} loading={drilldownQuery.isFetching} disabled={!drilldownEnabled}>
              Refresh
            </Button>
          </Space>

          {drilldownQuery.isError && (
            <Alert type="error" showIcon message="Failed to load databases" />
          )}

          <ExtensionsDrilldownTable
            columns={drillColumns}
            data={drilldownQuery.data?.databases ?? []}
            loading={drilldownQuery.isLoading}
            pagination={drillPagination}
          />
        </Space>
        </DrawerSurfaceShell>
      </Space>
    </WorkspacePage>
  )
}
