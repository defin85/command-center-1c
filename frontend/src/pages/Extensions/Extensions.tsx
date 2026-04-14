import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Alert, App, Button, Checkbox, Grid, Input, Select, Space, Switch, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAdminSupportTranslation, useCommonTranslation, useLocaleFormatters } from '@/i18n'

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

type ObservedState = 'on' | 'off' | 'mixed' | 'unknown'

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
  const { t } = useAdminSupportTranslation()
  const { t: tCommon } = useCommonTranslation()
  const formatters = useLocaleFormatters()
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
  const unavailable = tCommon(($) => $.values.unavailableShort)

  const formatStatusLabel = useCallback((value: Status | string | null | undefined) => {
    switch (value) {
      case 'active':
        return t(($) => $.extensions.status.active)
      case 'inactive':
        return t(($) => $.extensions.status.inactive)
      case 'missing':
        return t(($) => $.extensions.status.missing)
      case 'unknown':
        return t(($) => $.extensions.status.unknown)
      default:
        return value || unavailable
    }
  }, [t, unavailable])

  const formatBoolTag = useCallback((value: boolean | null | undefined) => {
    if (value === true) return <Tag color="green">{t(($) => $.extensions.flags.on)}</Tag>
    if (value === false) return <Tag color="red">{t(($) => $.extensions.flags.off)}</Tag>
    return <Text type="secondary">{unavailable}</Text>
  }, [t, unavailable])

  const formatObservedStateTag = useCallback((state: ObservedState | undefined) => {
    if (!state) return <Text type="secondary">{unavailable}</Text>
    if (state === 'on') return <Tag color="green">{t(($) => $.extensions.flags.observedOn)}</Tag>
    if (state === 'off') return <Tag color="red">{t(($) => $.extensions.flags.observedOff)}</Tag>
    if (state === 'mixed') return <Tag color="gold">{t(($) => $.extensions.flags.observedMixed)}</Tag>
    return <Tag>{t(($) => $.extensions.flags.observedUnknown)}</Tag>
  }, [t, unavailable])

  const renderFlagCell = useCallback((flag: ExtensionsFlagAggregate | undefined | null) => {
    if (!flag) return <Text type="secondary">{unavailable}</Text>

    const state = (flag.observed?.state as ObservedState | undefined) ?? undefined
    const tooltip = (
      <div style={{ maxWidth: 360 }}>
        <div>{t(($) => $.extensions.flags.counts, {
          trueCount: String(flag.observed?.true_count ?? 0),
          falseCount: String(flag.observed?.false_count ?? 0),
          unknownCount: String(flag.observed?.unknown_count ?? 0),
        })}</div>
        <div>{t(($) => $.extensions.flags.driftSummary, {
          driftCount: String(flag.drift_count ?? 0),
          unknownDriftCount: String(flag.unknown_drift_count ?? 0),
        })}</div>
      </div>
    )

    const showDrift = (flag.drift_count ?? 0) > 0
    const showUnknownDrift = (flag.unknown_drift_count ?? 0) > 0

    return (
      <Tooltip title={tooltip}>
        <Space size={6} wrap>
          {formatBoolTag(flag.policy)}
          {formatObservedStateTag(state)}
          {showDrift && <Tag color="red">{t(($) => $.extensions.flags.drift, { count: flag.drift_count ?? 0 })}</Tag>}
          {showUnknownDrift && (
            <Tag color="orange">{t(($) => $.extensions.flags.unknownDrift, { count: flag.unknown_drift_count ?? 0 })}</Tag>
          )}
        </Space>
      </Tooltip>
    )
  }, [formatBoolTag, formatObservedStateTag, t, unavailable])

  const formatDateTime = useCallback((value: string | null | undefined) => (
    formatters.dateTime(value, { fallback: unavailable })
  ), [formatters, unavailable])

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
      title: t(($) => $.extensions.confirm.adoptTitle),
      content: (
        <Space direction="vertical" size="small">
          <div>
            {t(($) => $.extensions.confirm.adoptDescription, {
              extension: selectedExtension,
              databaseId: drawerDatabaseId,
            })}
          </div>
          <Input.TextArea
            placeholder={t(($) => $.extensions.confirm.adoptReasonPlaceholder)}
            rows={3}
            onChange={(e) => { reason = e.target.value }}
          />
        </Space>
      ),
      okText: t(($) => $.extensions.confirm.adoptOk),
      cancelText: tCommon(($) => $.actions.cancel),
      onOk: async () => {
        setAdoptPending(true)
        try {
          const policy = await api.postExtensionsFlagsPolicyAdopt({
            database_id: drawerDatabaseId,
            extension_name: selectedExtension,
            reason: reason.trim() || undefined,
          })
          message.success(t(($) => $.extensions.messages.policyUpdated))
          resetApplyFormFromPolicy(policy)
          await overviewQuery.refetch()
          if (drilldownEnabled) await drilldownQuery.refetch()
        } catch (e: unknown) {
          if (!tryShowIbcmdCliUiError(e, modal, message)) {
            const errorMessage = e instanceof Error ? e.message : 'unknown error'
            message.error(t(($) => $.extensions.messages.failedAdoptPolicy, { error: errorMessage }))
          }
        } finally {
          setAdoptPending(false)
        }
      },
    })
  }

  const savePreferredBinding = async () => {
    if (!selectedTemplateId) {
      message.info(t(($) => $.extensions.messages.selectTemplateFirst))
      return
    }
    if (mutatingDisabled) return
    try {
      await upsertBindingMutation.mutateAsync({
        manualOperation,
        templateId: selectedTemplateId,
      })
      message.success(t(($) => $.extensions.messages.preferredBindingUpdated))
    } catch (e: unknown) {
      if (!tryShowIbcmdCliUiError(e, modal, message)) {
        const errorMessage = e instanceof Error ? e.message : 'unknown error'
        message.error(t(($) => $.extensions.messages.failedUpdatePreferredBinding, { error: errorMessage }))
      }
    }
  }

  const clearPreferredBinding = async () => {
    if (!preferredBinding) return
    if (mutatingDisabled) return
    try {
      await deleteBindingMutation.mutateAsync(manualOperation)
      message.success(t(($) => $.extensions.messages.preferredBindingRemoved))
    } catch (e: unknown) {
      if (!tryShowIbcmdCliUiError(e, modal, message)) {
        const errorMessage = e instanceof Error ? e.message : 'unknown error'
        message.error(t(($) => $.extensions.messages.failedRemovePreferredBinding, { error: errorMessage }))
      }
    }
  }

  const runApplyPolicy = async () => {
    if (!selectedExtension) return
    if (mutatingDisabled) return
    if (planPending || applyPending) return
    if (templateSelectionMissing) {
      message.error(t(($) => $.extensions.messages.selectTemplateOrBinding))
      return
    }

    const isSetFlagsOperation = manualOperation === 'extensions.set_flags'
    const mode = resolveExtensionsApplyMode(drawerDatabaseId)
    const applyTitle = isSetFlagsOperation
      ? (mode === 'targeted_fallback'
          ? t(($) => $.extensions.confirm.applyTargetedTitle)
          : t(($) => $.extensions.confirm.applyWorkflowTitle))
      : t(($) => $.extensions.confirm.applySyncTitle)
    const applySuccessMessage = isSetFlagsOperation
      ? (mode === 'targeted_fallback'
        ? t(($) => $.extensions.messages.applyQueuedTargeted)
        : t(($) => $.extensions.messages.applyQueuedWorkflow))
      : t(($) => $.extensions.messages.applyQueuedSync)

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
      message.error(t(($) => $.extensions.messages.selectAtLeastOneFlag))
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
            title: t(($) => $.extensions.confirm.tooManyDatabasesTitle),
            content: t(($) => $.extensions.confirm.tooManyDatabasesDescription, { total: String(total) }),
          })
          return
        }
        for (const item of resp.databases ?? []) {
          if (item?.database_id) dbIds.push(String(item.database_id))
        }
      }

      const databaseIds = Array.from(new Set(dbIds)).filter(Boolean)
      if (databaseIds.length === 0) {
        message.info(t(($) => $.extensions.messages.noTargetDatabases))
        return
      }

      const plan = await api.postExtensionsPlan(buildPlanRequest(databaseIds))

      const previewText = formatExecutionPlan(plan.execution_plan)
      const bindings = extractBindings(plan.bindings)
      const bindingColumns: ColumnsType<UIBinding> = [
        { title: t(($) => $.extensions.bindings.target), dataIndex: 'target_ref', key: 'target_ref' },
        { title: t(($) => $.extensions.bindings.source), dataIndex: 'source_ref', key: 'source_ref' },
        { title: t(($) => $.extensions.bindings.resolve), dataIndex: 'resolve_at', key: 'resolve_at', width: 90 },
        {
          title: t(($) => $.extensions.bindings.sensitive),
          dataIndex: 'sensitive',
          key: 'sensitive',
          width: 90,
          render: (value: boolean | undefined) => (
            value
              ? <Tag color="red">{t(($) => $.shared.yes)}</Tag>
              : <Tag>{t(($) => $.shared.no)}</Tag>
          ),
        },
        { title: t(($) => $.extensions.bindings.status), dataIndex: 'status', key: 'status', width: 110 },
        { title: t(($) => $.extensions.bindings.reason), dataIndex: 'reason', key: 'reason' },
      ]

      confirmWithTracking(modal, {
        title: applyTitle,
        content: (
          <div>
            <div style={{ marginBottom: 8 }}>
              {t(($) => $.extensions.confirm.extensionSummary, {
                extension: selectedExtension,
                count: databaseIds.length,
              })}
            </div>
            <div style={{ marginBottom: 8 }}>
              {t(($) => $.extensions.confirm.manualOperationSummary, { operation: manualOperation })}
            </div>
            <div style={{ marginBottom: 8 }}>
              {t(($) => $.extensions.confirm.templateSummary, {
                template: selectedTemplateId || preferredBinding?.template_id || t(($) => $.extensions.bindings.preferred),
              })}
            </div>
            {isSetFlagsOperation && (
              <>
                <div style={{ marginBottom: 8 }}>
                  {t(($) => $.extensions.confirm.modeSummary)}{' '}
                  {mode === 'targeted_fallback'
                    ? <Tag color="orange">{t(($) => $.extensions.mode.targetedTag)}</Tag>
                    : <Tag color="blue">{t(($) => $.extensions.mode.workflowTag)}</Tag>}
                </div>
                <Space size={8} wrap style={{ marginBottom: 8 }}>
                  <div>{t(($) => $.extensions.flags.active)}: {applyMask.active ? formatBoolTag(flagsValues.active) : <Text type="secondary">{t(($) => $.extensions.flags.skipped)}</Text>}</div>
                  <div>{t(($) => $.extensions.flags.safeMode)}: {applyMask.safe_mode ? formatBoolTag(flagsValues.safe_mode) : <Text type="secondary">{t(($) => $.extensions.flags.skipped)}</Text>}</div>
                  <div>{t(($) => $.extensions.flags.unsafeActionProtection)}: {applyMask.unsafe_action_protection ? formatBoolTag(flagsValues.unsafe_action_protection) : <Text type="secondary">{t(($) => $.extensions.flags.skipped)}</Text>}</div>
                </Space>
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary">{t(($) => $.extensions.confirm.runtimeSourceSummary)}</Text>
                </div>
              </>
            )}
            {previewText ? (
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{previewText}</pre>
            ) : (
              <div style={{ opacity: 0.7 }}>{t(($) => $.extensions.confirm.previewNotAvailable)}</div>
            )}
            {isStaff && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>{t(($) => $.extensions.confirm.bindingProvenanceTitle)}</div>
                {bindings.length > 0 ? (
                  <ExtensionsBindingsTable
                    data={bindings}
                    columns={bindingColumns}
                  />
                ) : (
                  <div style={{ opacity: 0.7 }}>{t(($) => $.extensions.confirm.noBindings)}</div>
                )}
              </div>
            )}
          </div>
        ),
        okText: t(($) => $.extensions.confirm.applyOk),
        cancelText: tCommon(($) => $.actions.cancel),
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
                  title: t(($) => $.extensions.confirm.stateChangedTitle),
                  content: (
                    <div>
                      <div style={{ marginBottom: 8 }}>
                        {t(($) => $.extensions.confirm.stateChangedDescription)}
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
                          {t(($) => $.extensions.confirm.showingFirst, { count: driftRows.length })}
                        </div>
                      ) : null}
                    </div>
                  ),
                  okText: t(($) => $.extensions.confirm.replanAndRetry),
                  cancelText: t(($) => $.extensions.confirm.close),
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
                title: t(($) => $.extensions.confirm.conflictTitle),
                content: (
                  <pre style={{ whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(data ?? {}, null, 2)}
                  </pre>
                ),
              })
            } else if (!tryShowIbcmdCliUiError(e, modal, message)) {
              const errorMessage = e instanceof Error ? e.message : 'unknown error'
              message.error(t(($) => $.extensions.messages.failedApplyRollout, { error: errorMessage }))
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
        message.error(t(($) => $.extensions.messages.missingTemplateBinding))
        return
      }
      if (code === 'CONFIGURATION_ERROR') {
        message.error(t(($) => $.extensions.messages.configurationError))
        return
      }
      if (!tryShowIbcmdCliUiError(e, modal, message)) {
        const errorMessage = e instanceof Error ? e.message : 'unknown error'
        message.error(t(($) => $.extensions.messages.failedBuildPlan, { error: errorMessage }))
      }
    } finally {
      setPlanPending(false)
    }
  }

  const overviewColumns: ColumnsType<ExtensionsOverviewRow> = [
    {
      title: t(($) => $.extensions.table.extension),
      dataIndex: 'name',
      key: 'name',
      render: (value: string, row) => (
        <Button
          type="link"
          style={{ padding: 0 }}
          onClick={() => openDrawer(row)}
          aria-label={t(($) => $.extensions.drawer.title, { name: value })}
        >
          {value}
        </Button>
      ),
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: t(($) => $.extensions.table.purpose),
      dataIndex: 'purpose',
      key: 'purpose',
      render: (v: string | null | undefined) => v ? <Text>{v}</Text> : <Text type="secondary">{unavailable}</Text>,
    },
    {
      title: t(($) => $.extensions.table.active),
      key: 'active_policy',
      render: (_: unknown, row) => renderFlagCell(row.flags?.active),
    },
    {
      title: t(($) => $.extensions.table.safeMode),
      key: 'safe_mode_policy',
      render: (_: unknown, row) => renderFlagCell(row.flags?.safe_mode),
    },
    {
      title: t(($) => $.extensions.table.unsafeActionProtection),
      key: 'unsafe_action_protection_policy',
      render: (_: unknown, row) => renderFlagCell(row.flags?.unsafe_action_protection),
    },
    {
      title: t(($) => $.extensions.table.installed),
      key: 'installed',
      align: 'right',
      render: (_: unknown, row) => <Text>{row.installed_count}</Text>,
    },
    {
      title: t(($) => $.extensions.table.missing),
      dataIndex: 'missing_count',
      key: 'missing_count',
      align: 'right',
      render: (v: number) => <Text>{v}</Text>,
    },
    {
      title: t(($) => $.extensions.table.unknown),
      dataIndex: 'unknown_count',
      key: 'unknown_count',
      align: 'right',
      render: (v: number) => <Text>{v}</Text>,
    },
    {
      title: t(($) => $.extensions.table.versions),
      dataIndex: 'versions',
      key: 'versions',
      render: (versions: { version: string | null; count: number }[]) => {
        const top = [...(versions || [])]
          .filter((v) => v.count > 0)
          .sort((a, b) => b.count - a.count)
          .slice(0, 4)
        if (top.length === 0) {
          return <Text type="secondary">{unavailable}</Text>
        }
        return (
          <Space size={4} wrap>
            {top.map((v) => (
              <Tag key={`${v.version ?? 'null'}-${v.count}`}>{v.version ?? unavailable}: {v.count}</Tag>
            ))}
          </Space>
        )
      },
    },
    {
      title: t(($) => $.extensions.table.latestSnapshot),
      dataIndex: 'latest_snapshot_at',
      key: 'latest_snapshot_at',
      render: (value?: string | null) => (
        <Text>{formatDateTime(value)}</Text>
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
      title: t(($) => $.extensions.table.database),
      dataIndex: 'database_name',
      key: 'database_name',
      render: (value: string) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => navigate('/databases')}>
          {value}
        </Button>
      ),
    },
    {
      title: t(($) => $.extensions.table.cluster),
      key: 'cluster',
      render: (_: unknown, row) => (
        <Text type="secondary">{row.cluster_name || row.cluster_id || unavailable}</Text>
      ),
    },
    {
      title: t(($) => $.extensions.table.status),
      dataIndex: 'status',
      key: 'status',
      render: (value: Status) => (
        <Tag color={statusTagColor(value)}>{formatStatusLabel(value)}</Tag>
      ),
    },
    {
      title: t(($) => $.extensions.table.active),
      key: 'active_observed',
      render: (_: unknown, row) => formatBoolTag(row.flags?.active),
    },
    {
      title: t(($) => $.extensions.table.safeMode),
      key: 'safe_mode_observed',
      render: (_: unknown, row) => formatBoolTag(row.flags?.safe_mode),
    },
    {
      title: t(($) => $.extensions.table.unsafeActionProtection),
      key: 'unsafe_action_protection_observed',
      render: (_: unknown, row) => formatBoolTag(row.flags?.unsafe_action_protection),
    },
    {
      title: t(($) => $.extensions.table.version),
      dataIndex: 'version',
      key: 'version',
      render: (value?: string | null) => (
        value ? <Text>{value}</Text> : <Text type="secondary">{unavailable}</Text>
      ),
    },
    {
      title: t(($) => $.extensions.table.snapshot),
      dataIndex: 'snapshot_updated_at',
      key: 'snapshot_updated_at',
      render: (value?: string | null) => (
        <Text>{formatDateTime(value)}</Text>
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
          title={t(($) => $.extensions.page.title)}
          subtitle={t(($) => $.extensions.page.subtitle)}
          actions={(
            <Button
              data-testid="extensions-refresh"
              onClick={() => overviewQuery.refetch()}
              loading={overviewQuery.isFetching}
            >
              {t(($) => $.extensions.page.refresh)}
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
          placeholder={t(($) => $.extensions.page.searchPlaceholder)}
          style={{ width: 260 }}
          allowClear
        />
        <Select
          value={status}
          onChange={(v) => { setStatus(v); setPage(1) }}
          allowClear
          placeholder={t(($) => $.extensions.page.statusPlaceholder)}
          style={{ width: 180 }}
          options={[
            { value: 'active', label: t(($) => $.extensions.status.active) },
            { value: 'inactive', label: t(($) => $.extensions.status.inactive) },
            { value: 'missing', label: t(($) => $.extensions.status.missing) },
            { value: 'unknown', label: t(($) => $.extensions.status.unknown) },
          ]}
        />
        <Input
          data-testid="extensions-overview-version"
          value={version}
          onChange={(e) => { setVersion(e.target.value); setPage(1) }}
          placeholder={t(($) => $.extensions.page.versionPlaceholder)}
          style={{ width: 220 }}
          allowClear
        />
        <Select
          data-testid="extensions-overview-database"
          value={databaseId}
          onChange={(v) => { setDatabaseId(v); setPage(1) }}
          allowClear
          placeholder={t(($) => $.extensions.page.databasePlaceholder)}
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
          placeholder={t(($) => $.extensions.page.clusterPlaceholder)}
          style={{ width: 260 }}
          options={clusterOptions}
          loading={clustersQuery.isLoading}
          showSearch
          optionFilterProp="label"
        />
        <Text type="secondary">
          {typeof overviewQuery.data?.total_databases === 'number'
            ? t(($) => $.extensions.page.totalDatabases, { count: overviewQuery.data.total_databases })
            : t(($) => $.extensions.page.totalDatabasesUnavailable)}
        </Text>
        </Space>

        {overviewQuery.isError && (
          <Alert type="error" showIcon message={t(($) => $.extensions.page.loadFailed)} />
        )}

        <ExtensionsOverviewTable
          columns={overviewColumns}
          data={overviewQuery.data?.extensions ?? []}
          loading={overviewQuery.isLoading}
          pagination={overviewPagination}
        />

        <DrawerSurfaceShell
          title={selectedExtension
            ? t(($) => $.extensions.drawer.title, { name: selectedExtension })
            : t(($) => $.extensions.drawer.titleFallback)}
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
              message={t(($) => $.extensions.drawer.mutatingDisabledTitle)}
              description={t(($) => $.extensions.drawer.mutatingDisabledDescription)}
            />
          )}

          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Text strong>{t(($) => $.extensions.drawer.manualOperationTitle)}</Text>
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Alert
                type={setFlagsOperationSelected && fallbackMode ? 'warning' : 'info'}
                showIcon
                data-testid="extensions-apply-mode-hint"
                message={setFlagsOperationSelected
                  ? (fallbackMode
                      ? t(($) => $.extensions.mode.fallbackTitle)
                      : t(($) => $.extensions.mode.workflowTitle))
                  : t(($) => $.extensions.mode.templateSyncTitle)}
                description={setFlagsOperationSelected
                  ? (fallbackMode
                    ? t(($) => $.extensions.mode.fallbackDescription)
                    : t(($) => $.extensions.mode.workflowDescription))
                  : t(($) => $.extensions.mode.templateSyncDescription)}
              />
              <Space
                align={isNarrow ? 'start' : 'center'}
                direction={isNarrow ? 'vertical' : 'horizontal'}
                style={{ width: '100%' }}
              >
                <Text type="secondary">{t(($) => $.extensions.drawer.operationLabel)}</Text>
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
                <Text type="secondary">{t(($) => $.extensions.drawer.templateLabel)}</Text>
                <Select
                  data-testid="extensions-apply-template"
                  value={selectedTemplateId}
                  onChange={(value) => setSelectedTemplateId(value)}
                  options={templateOptions}
                  placeholder={templatesQuery.isLoading
                    ? t(($) => $.extensions.drawer.templateLabel)
                    : t(($) => $.extensions.messages.selectTemplateOrBinding)}
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
                    {t(($) => $.extensions.drawer.savePreferred)}
                  </Button>
                  <Button
                    size="small"
                    onClick={() => void clearPreferredBinding()}
                    loading={deleteBindingMutation.isPending}
                    disabled={!preferredBinding || mutatingDisabled}
                  >
                    {t(($) => $.extensions.drawer.clearPreferred)}
                  </Button>
                </Space>
              </Space>
              {templatesQuery.isError && (
                <Alert
                  type="error"
                  showIcon
                  message={t(($) => $.extensions.drawer.compatibleTemplatesFailedTitle)}
                  description={t(($) => $.extensions.drawer.compatibleTemplatesFailedDescription)}
                />
              )}
              {bindingsQuery.isError && (
                <Alert
                  type="warning"
                  showIcon
                  message={t(($) => $.extensions.drawer.preferredBindingUnavailableTitle)}
                  description={t(($) => $.extensions.drawer.preferredBindingUnavailableDescription)}
                />
              )}
              {preferredBinding && (
                <Space size={8} wrap data-testid="extensions-preferred-binding-summary">
                  <Tag color="geekblue">{t(($) => $.extensions.bindings.preferred)}</Tag>
                  <Tag>{preferredBinding.template_id}</Tag>
                  {preferredBinding.updated_at && (
                    <Tag>{formatDateTime(preferredBinding.updated_at)}</Tag>
                  )}
                  {preferredBinding.updated_by && <Tag>{preferredBinding.updated_by}</Tag>}
                </Space>
              )}
              {selectedTemplate && (
                <Space size={8} wrap data-testid="extensions-apply-template-summary">
                  <Tag color="blue">{selectedTemplate.value}</Tag>
                  <Tag>{selectedTemplate.capability || t(($) => $.extensions.bindings.noCapability)}</Tag>
                </Space>
              )}
              {templateSelectionMissing && (
                <Alert
                  type="warning"
                  showIcon
                  message={t(($) => $.extensions.drawer.templateNotResolvedTitle)}
                  description={t(($) => $.extensions.drawer.templateNotResolvedDescription)}
                />
              )}
              {setFlagsOperationSelected && (
                <>
                  <Alert
                    type="info"
                    showIcon
                    data-testid="extensions-apply-runtime-source-hint"
                    message={t(($) => $.extensions.drawer.runtimeSourceTitle)}
                    description={(
                      <Space direction="vertical" size={2}>
                        <Text>{t(($) => $.extensions.drawer.runtimeSourceDescription)}</Text>
                        <Text type="secondary">{t(($) => $.extensions.drawer.runtimeSourceSecondary)}</Text>
                      </Space>
                    )}
                  />
                  <Space align="center" wrap>
                    <Checkbox
                      data-testid="extensions-apply-flag-active-enabled"
                      checked={applyActiveEnabled}
                      onChange={(e) => setApplyActiveEnabled(e.target.checked)}
                    >
                      {t(($) => $.extensions.flags.active)}
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
                      {t(($) => $.extensions.flags.safeMode)}
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
                      {t(($) => $.extensions.flags.unsafeActionProtection)}
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
                      ? t(($) => $.extensions.drawer.selectTenantToEnable)
                      : templateSelectionMissing
                        ? t(($) => $.extensions.drawer.templateNotResolvedTooltip)
                        : setFlagsOperationSelected && !hasRuntimeMaskSelection
                          ? t(($) => $.extensions.drawer.selectAtLeastOneFlagTooltip)
                          : undefined
                  }
                >
                  <Button
                    type="primary"
                    onClick={runApplyPolicy}
                    loading={planPending || applyPending}
                    disabled={!selectedExtension || mutatingDisabled || templateSelectionMissing || (setFlagsOperationSelected && !hasRuntimeMaskSelection)}
                  >
                    {t(($) => $.extensions.drawer.apply)}
                  </Button>
                </Tooltip>
                <Tooltip title={!drawerDatabaseId
                  ? t(($) => $.extensions.drawer.selectDatabaseToAdopt)
                  : (mutatingDisabled ? t(($) => $.extensions.drawer.selectTenantToEnable) : undefined)}>
                  <Button
                    onClick={runAdoptPolicy}
                    loading={adoptPending}
                    disabled={!selectedExtension || !drawerDatabaseId || mutatingDisabled || !setFlagsOperationSelected}
                  >
                    {t(($) => $.extensions.drawer.adoptFromDatabase)}
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
              placeholder={t(($) => $.extensions.page.databasePlaceholder)}
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
              placeholder={t(($) => $.extensions.page.statusPlaceholder)}
              style={{ width: 180 }}
              options={[
                { value: 'active', label: t(($) => $.extensions.status.active) },
                { value: 'inactive', label: t(($) => $.extensions.status.inactive) },
                { value: 'missing', label: t(($) => $.extensions.status.missing) },
                { value: 'unknown', label: t(($) => $.extensions.status.unknown) },
              ]}
            />
            <Input
              value={drawerVersion}
              onChange={(e) => { setDrawerVersion(e.target.value); setDrawerPage(1) }}
              placeholder={t(($) => $.extensions.page.versionPlaceholder)}
              style={{ width: 220 }}
              allowClear
            />
            <Button onClick={() => drilldownQuery.refetch()} loading={drilldownQuery.isFetching} disabled={!drilldownEnabled}>
              {t(($) => $.extensions.page.refresh)}
            </Button>
          </Space>

          {drilldownQuery.isError && (
            <Alert type="error" showIcon message={t(($) => $.extensions.page.loadDatabasesFailed)} />
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
