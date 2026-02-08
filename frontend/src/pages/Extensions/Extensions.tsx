import { useEffect, useMemo, useState } from 'react'
import { Alert, App, Button, Checkbox, Drawer, Input, Select, Space, Switch, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import dayjs from 'dayjs'
import { useNavigate } from 'react-router-dom'

import { getV2 } from '../../api/generated'
import { useClusters } from '../../api/queries/clusters'
import { useDatabases } from '../../api/queries/databases'
import { useMe } from '../../api/queries/me'
import { useActionCatalog } from '../../api/queries/ui'
import {
  type ExtensionsFlagAggregate,
  useExtensionsOverview,
  useExtensionsOverviewDatabases,
  type ExtensionsOverviewDatabaseRow,
  type ExtensionsOverviewRow,
} from '../../api/queries/extensions'
import type { ActionCatalogAction } from '../../api/types/actionCatalog'
import { tryShowIbcmdCliUiError } from '../../components/ibcmd/ibcmdCliUiErrors'

const { Title, Text } = Typography

const api = getV2()

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

type ExtensionsFlagsPolicyState = {
  active: boolean | null
  safe_mode: boolean | null
  unsafe_action_protection: boolean | null
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

export const Extensions = () => {
  const navigate = useNavigate()
  const { message, modal } = App.useApp()
  const meQuery = useMe()
  const isStaff = Boolean(meQuery.data?.is_staff)
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

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedExtension, setSelectedExtension] = useState<string | null>(null)
  const [drawerStatus, setDrawerStatus] = useState<Status | undefined>(undefined)
  const [drawerVersion, setDrawerVersion] = useState<string>('')
  const [drawerDatabaseId, setDrawerDatabaseId] = useState<string | undefined>(undefined)
  const [drawerPage, setDrawerPage] = useState(1)
  const [drawerPageSize, setDrawerPageSize] = useState(50)
  const [adoptPending, setAdoptPending] = useState(false)
  const [planPending, setPlanPending] = useState(false)
  const [applyPending, setApplyPending] = useState(false)

  const [drawerPolicy, setDrawerPolicy] = useState<ExtensionsFlagsPolicyState>({
    active: null,
    safe_mode: null,
    unsafe_action_protection: null,
  })

  const [applyReason, setApplyReason] = useState('')
  const [applyActiveEnabled, setApplyActiveEnabled] = useState(false)
  const [applyActiveValue, setApplyActiveValue] = useState(false)
  const [applySafeModeEnabled, setApplySafeModeEnabled] = useState(false)
  const [applySafeModeValue, setApplySafeModeValue] = useState(false)
  const [applyUnsafeActionProtectionEnabled, setApplyUnsafeActionProtectionEnabled] = useState(false)
  const [applyUnsafeActionProtectionValue, setApplyUnsafeActionProtectionValue] = useState(false)

  const actionCatalogQuery = useActionCatalog()
  const extensionsActionsRaw = (actionCatalogQuery.data as unknown as { extensions?: { actions?: unknown } } | null)?.extensions?.actions
  const extensionsActions: ActionCatalogAction[] = useMemo(
    () => (Array.isArray(extensionsActionsRaw) ? (extensionsActionsRaw as ActionCatalogAction[]) : []),
    [extensionsActionsRaw],
  )
  const setFlagsActions = useMemo(
    () => extensionsActions.filter((a) => (a.capability ?? '').trim() === 'extensions.set_flags'),
    [extensionsActions],
  )
  const setFlagsActionOptions = useMemo(
    () => setFlagsActions.map((a) => ({ value: a.id, label: `${a.label} (${a.id})` })),
    [setFlagsActions],
  )
  const [setFlagsActionId, setSetFlagsActionId] = useState<string | undefined>(undefined)
  useEffect(() => {
    if (!drawerOpen) return
    if (setFlagsActions.length === 0) {
      setSetFlagsActionId(undefined)
      return
    }
    const exists = setFlagsActionId && setFlagsActions.some((a) => a.id === setFlagsActionId)
    if (!exists) {
      setSetFlagsActionId(setFlagsActions[0].id)
    }
  }, [drawerOpen, setFlagsActions, setFlagsActionId])

  useEffect(() => {
    setDatabaseId(undefined)
    setDrawerDatabaseId(undefined)
    setPage(1)
    setDrawerPage(1)
  }, [clusterId])

  const selectedRow = useMemo(() => {
    const rows = overviewQuery.data?.extensions ?? []
    if (!selectedExtension) return null
    return rows.find((r) => r.name === selectedExtension) ?? null
  }, [overviewQuery.data?.extensions, selectedExtension])

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

  const resetApplyFormFromPolicy = (policy?: { active?: unknown; safe_mode?: unknown; unsafe_action_protection?: unknown } | null) => {
    const active = normalizePolicyBool(policy?.active)
    const safeMode = normalizePolicyBool(policy?.safe_mode)
    const unsafeActionProtection = normalizePolicyBool(policy?.unsafe_action_protection)
    setDrawerPolicy({
      active,
      safe_mode: safeMode,
      unsafe_action_protection: unsafeActionProtection,
    })
    setApplyReason('')
    setApplyActiveEnabled(active !== null)
    setApplyActiveValue(Boolean(active))
    setApplySafeModeEnabled(safeMode !== null)
    setApplySafeModeValue(Boolean(safeMode))
    setApplyUnsafeActionProtectionEnabled(unsafeActionProtection !== null)
    setApplyUnsafeActionProtectionValue(Boolean(unsafeActionProtection))
  }

  const openDrawer = (row: ExtensionsOverviewRow) => {
    setSelectedExtension(row.name)
    setDrawerOpen(true)
    // Propagate current page-level filters into drawer by default so drilldown/apply works on the same slice.
    setDrawerStatus(status)
    setDrawerVersion(version)
    setDrawerDatabaseId(databaseId)
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
    modal.confirm({
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

  const runApplyPolicy = async () => {
    if (!selectedExtension) return
    if (mutatingDisabled) return
    if (planPending || applyPending) return

    if (actionCatalogQuery.isSuccess && setFlagsActions.length === 0) {
      message.error('extensions.set_flags action is not configured in Action Catalog')
      return
    }

    const applyMask = {
      active: applyActiveEnabled,
      safe_mode: applySafeModeEnabled,
      unsafe_action_protection: applyUnsafeActionProtectionEnabled,
    }
    if (!applyMask.active && !applyMask.safe_mode && !applyMask.unsafe_action_protection) {
      message.error('Select at least one flag to apply')
      return
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
            content: `This action is limited to 500 databases per run (matched: ${total}). Narrow filters and retry.`,
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

      // IMPORTANT: do not rely on selectedRow which can disappear after pagination/filter changes.
      // Keep the latest known policy in drawer state to avoid accidental null overwrites.
      const currentPolicy = drawerPolicy

      const nextPolicy = {
        active: applyActiveEnabled ? applyActiveValue : currentPolicy.active,
        safe_mode: applySafeModeEnabled ? applySafeModeValue : currentPolicy.safe_mode,
        unsafe_action_protection: applyUnsafeActionProtectionEnabled ? applyUnsafeActionProtectionValue : currentPolicy.unsafe_action_protection,
      }

      const updatedPolicy = await api.putExtensionsFlagsPolicy(selectedExtension, {
        ...nextPolicy,
        reason: applyReason.trim() || undefined,
      })
      setDrawerPolicy({
        active: normalizePolicyBool(updatedPolicy.active),
        safe_mode: normalizePolicyBool(updatedPolicy.safe_mode),
        unsafe_action_protection: normalizePolicyBool(updatedPolicy.unsafe_action_protection),
      })
      await overviewQuery.refetch()
      if (drilldownEnabled) await drilldownQuery.refetch()

      const plan = await api.postExtensionsPlan({
        database_ids: databaseIds,
        capability: 'extensions.set_flags',
        action_id: setFlagsActionId || undefined,
        extension_name: selectedExtension,
        apply_mask: applyMask,
      })

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

      modal.confirm({
        title: 'Apply selected flags?',
        content: (
          <div>
            <div style={{ marginBottom: 8 }}>
              Extension <Text code>{selectedExtension}</Text> will be applied to {databaseIds.length} database(s).
            </div>
            <Space size={8} wrap style={{ marginBottom: 8 }}>
              <div>Active: {applyMask.active ? boolTag(applyActiveValue) : <Text type="secondary">skipped</Text>}</div>
              <div>Safe mode: {applyMask.safe_mode ? boolTag(applySafeModeValue) : <Text type="secondary">skipped</Text>}</div>
              <div>Unsafe action protection: {applyMask.unsafe_action_protection ? boolTag(applyUnsafeActionProtectionValue) : <Text type="secondary">skipped</Text>}</div>
            </Space>
            {selectedRow?.flags ? (
              <Space size={8} wrap style={{ marginBottom: 8 }}>
                <div>Active: {boolTag(selectedRow.flags.active?.policy)}</div>
                <div>Safe mode: {boolTag(selectedRow.flags.safe_mode?.policy)}</div>
                <div>Unsafe action protection: {boolTag(selectedRow.flags.unsafe_action_protection?.policy)}</div>
              </Space>
            ) : null}
            {previewText ? (
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{previewText}</pre>
            ) : (
              <div style={{ opacity: 0.7 }}>Preview not available</div>
            )}
            {isStaff && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Binding Provenance:</div>
                {bindings.length > 0 ? (
                  <Table
                    size="small"
                    rowKey={(_row, idx) => String(idx)}
                    pagination={false}
                    dataSource={bindings}
                    columns={bindingColumns}
                    scroll={{ x: 900 }}
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
            message.success('Operation queued: apply flags policy')
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
                const drift = driftRaw && typeof driftRaw === 'object' ? driftRaw as Record<string, any> : null
                const driftRows = drift
                  ? Object.entries(drift).map(([databaseId, entry]) => {
                    const base = entry?.base
                    const current = entry?.current
                    return {
                      database_id: databaseId,
                      base_at: typeof base?.at === 'string' ? base.at : '',
                      current_at: typeof current?.at === 'string' ? current.at : '',
                      base_hash: typeof base?.hash === 'string' ? base.hash : '',
                      current_hash: typeof current?.hash === 'string' ? current.hash : '',
                    }
                  })
                  : []

                modal.confirm({
                  title: 'State changed',
                  content: (
                    <div>
                      <div style={{ marginBottom: 8 }}>
                        Some target databases changed since the plan was built. Re-plan is required.
                      </div>
                      {driftRows.length > 0 ? (
                        <Table
                          size="small"
                          rowKey={(row) => row.database_id}
                          pagination={false}
                          dataSource={driftRows.slice(0, 10)}
                          columns={[
                            { title: 'Database', dataIndex: 'database_id', key: 'database_id' },
                            { title: 'Base at', dataIndex: 'base_at', key: 'base_at', width: 220 },
                            { title: 'Current at', dataIndex: 'current_at', key: 'current_at', width: 220 },
                          ]}
                          scroll={{ x: 700 }}
                        />
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
                      const nextPlan = await api.postExtensionsPlan({
                        database_ids: databaseIds,
                        capability: 'extensions.set_flags',
                        action_id: setFlagsActionId || undefined,
                        extension_name: selectedExtension,
                        apply_mask: applyMask,
                      })
                      const res = await api.postExtensionsApply({ plan_id: nextPlan.plan_id })
                      message.success('Operation queued: apply flags policy')
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
              message.error(`Failed to apply policy: ${errorMessage}`)
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
      if (code === 'CONFIGURATION_ERROR') {
        message.error('Selective apply is not supported by current action catalog configuration')
        return
      }
      if (code === 'POLICY_NOT_FOUND') {
        message.error('Flags policy is not configured for this extension')
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
        <Button type="link" style={{ padding: 0 }} onClick={() => openDrawer(row)}>
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
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>Extensions</Title>
          <Text type="secondary">Overview across accessible databases (snapshot-driven).</Text>
        </div>
        <Button onClick={() => overviewQuery.refetch()} loading={overviewQuery.isFetching}>
          Refresh
        </Button>
      </div>

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
            setDrawerDatabaseId(undefined)
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

      <Table
        rowKey="name"
        columns={overviewColumns}
        dataSource={overviewQuery.data?.extensions ?? []}
        loading={overviewQuery.isLoading}
        pagination={overviewPagination}
        size="middle"
      />

      <Drawer
        title={selectedExtension ? `Extension: ${selectedExtension}` : 'Extension'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={860}
        destroyOnHidden
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {mutatingDisabled && (
            <Alert
              type="warning"
              showIcon
              message="Mutating actions are disabled"
              description="Staff users must select a tenant (X-CC1C-Tenant-ID) to change policy or apply actions."
            />
          )}

          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Text strong>Apply flags policy</Text>
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Space align="center" wrap>
                <Text type="secondary">Action</Text>
                <Select
                  data-testid="extensions-apply-action"
                  value={setFlagsActionId}
                  onChange={(v) => setSetFlagsActionId(v)}
                  options={setFlagsActionOptions}
                  placeholder={actionCatalogQuery.isLoading ? 'Loading…' : 'Select action'}
                  loading={actionCatalogQuery.isLoading}
                  allowClear
                  style={{ minWidth: 360 }}
                  disabled={setFlagsActionOptions.length === 0}
                />
              </Space>
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
              <Input.TextArea
                data-testid="extensions-apply-reason"
                value={applyReason}
                onChange={(e) => setApplyReason(e.target.value)}
                placeholder="Reason (optional)"
                rows={2}
                style={{ maxWidth: 640 }}
              />
              <Space wrap>
                <Tooltip title={mutatingDisabled ? 'Select a tenant to enable this action' : undefined}>
                  <Button
                    type="primary"
                    onClick={runApplyPolicy}
                    loading={planPending || applyPending}
                    disabled={!selectedExtension || mutatingDisabled}
                  >
                    Apply
                  </Button>
                </Tooltip>
                <Tooltip title={!drawerDatabaseId ? 'Select a database to adopt from' : (mutatingDisabled ? 'Select a tenant to enable this action' : undefined)}>
                  <Button
                    onClick={runAdoptPolicy}
                    loading={adoptPending}
                    disabled={!selectedExtension || !drawerDatabaseId || mutatingDisabled}
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
              onChange={(v) => { setDrawerDatabaseId(v); setDrawerPage(1) }}
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

          <Table
            rowKey="database_id"
            columns={drillColumns}
            dataSource={drilldownQuery.data?.databases ?? []}
            loading={drilldownQuery.isLoading}
            pagination={drillPagination}
            size="small"
          />
        </Space>
      </Drawer>
    </Space>
  )
}
