import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Alert, App, Button, Checkbox, Select, Space, Spin, Switch, Typography } from 'antd'
import dayjs from 'dayjs'

import { getV2 } from '../../../api/generated'
import type { DatabaseExtensionsSnapshotResponse } from '../../../api/generated/model/databaseExtensionsSnapshotResponse'
import {
  type ManualOperationKey,
  useDeleteManualOperationBinding,
  useManualOperationBindings,
  useUpsertManualOperationBinding,
} from '../../../api/queries/extensionsManualOperations'
import { listOperationCatalogExposures } from '../../../api/operationCatalog'
import { tryShowIbcmdCliUiError } from '../../../components/ibcmd/ibcmdCliUiErrors'
import { DrawerFormShell } from '../../../components/platform'
import { trackUiAction } from '../../../observability/uiActionJournal'

const api = getV2()

const MANUAL_OPERATION_OPTIONS: Array<{ value: ManualOperationKey; label: string }> = [
  { value: 'extensions.sync', label: 'extensions.sync' },
  { value: 'extensions.set_flags', label: 'extensions.set_flags' },
]

type TemplateOption = {
  value: string
  label: string
  capability?: string
}

type UIBinding = {
  target_ref?: string
  source_ref?: string
  resolve_at?: string
  sensitive?: boolean
  status?: string
  reason?: string | null
}

type BindingPreviewField = {
  key: string
  label: string
  value: string
}

type InlinePillTone = 'default' | 'blue' | 'geekblue' | 'green' | 'red'

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

const hasSetFlagsMaskSelection = (applyMask: { active: boolean; safe_mode: boolean; unsafe_action_protection: boolean }) => (
  Boolean(applyMask.active || applyMask.safe_mode || applyMask.unsafe_action_protection)
)

const renderBindingPreviewFields = (binding: UIBinding): BindingPreviewField[] => [
  {
    key: 'target',
    label: 'Target',
    value: typeof binding.target_ref === 'string' && binding.target_ref.trim() ? binding.target_ref : 'n/a',
  },
  {
    key: 'source',
    label: 'Source',
    value: typeof binding.source_ref === 'string' && binding.source_ref.trim() ? binding.source_ref : 'n/a',
  },
  {
    key: 'resolve',
    label: 'Resolve',
    value: typeof binding.resolve_at === 'string' && binding.resolve_at.trim() ? binding.resolve_at : 'n/a',
  },
  {
    key: 'status',
    label: 'Status',
    value: typeof binding.status === 'string' && binding.status.trim() ? binding.status : 'n/a',
  },
  {
    key: 'reason',
    label: 'Reason',
    value: typeof binding.reason === 'string' && binding.reason.trim() ? binding.reason : 'n/a',
  },
]

const renderInlinePill = (label: string, tone: InlinePillTone = 'default') => {
  const palette: Record<InlinePillTone, { background: string; border: string; color: string }> = {
    default: { background: '#f8fafc', border: '#d1d5db', color: '#374151' },
    blue: { background: '#eff6ff', border: '#bfdbfe', color: '#1d4ed8' },
    geekblue: { background: '#eef2ff', border: '#c7d2fe', color: '#3730a3' },
    green: { background: '#ecfdf3', border: '#a7f3d0', color: '#166534' },
    red: { background: '#fef2f2', border: '#fecaca', color: '#b91c1c' },
  }
  const resolved = palette[tone]

  return (
    <span
      style={{
        background: resolved.background,
        border: `1px solid ${resolved.border}`,
        borderRadius: 999,
        color: resolved.color,
        display: 'inline-flex',
        fontSize: 12,
        fontWeight: 600,
        lineHeight: 1.4,
        padding: '2px 10px',
      }}
    >
      {label}
    </span>
  )
}

const renderBindingProvenancePreview = (bindings: UIBinding[]) => (
  <div data-testid="database-extensions-binding-provenance" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
    {bindings.map((binding, index) => (
      <div
        key={`${binding.target_ref || 'binding'}-${binding.source_ref || index}`}
        data-testid={`database-extensions-binding-provenance-row-${index}`}
        style={{
          border: '1px solid #f0f0f0',
          borderRadius: 8,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          padding: '12px 14px',
        }}
      >
        <Space size={8} wrap>
          {renderInlinePill(`binding ${index + 1}`, 'geekblue')}
          {renderInlinePill(`sensitive: ${binding.sensitive ? 'yes' : 'no'}`, binding.sensitive ? 'red' : 'default')}
        </Space>
        <div
          style={{
            display: 'grid',
            gap: 8,
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          }}
        >
          {renderBindingPreviewFields(binding).map((field) => (
            <div
              key={field.key}
              style={{ display: 'flex', flexDirection: 'column', gap: 4 }}
            >
              <Typography.Text type="secondary">{field.label}</Typography.Text>
              <Typography.Text>{field.value}</Typography.Text>
            </div>
          ))}
        </div>
      </div>
    ))}
  </div>
)

export interface ExtensionsDrawerProps {
  open: boolean
  databaseId?: string
  databaseName?: string
  mutatingDisabled?: boolean
  onClose: () => void
  snapshot?: DatabaseExtensionsSnapshotResponse | null
  snapshotLoading?: boolean
  snapshotFetching?: boolean
  onRefreshSnapshot: () => void
  onOperationQueued?: (operationId: string) => void
}

export const ExtensionsDrawer = ({
  open,
  databaseId,
  databaseName,
  mutatingDisabled = false,
  onClose,
  snapshot,
  snapshotLoading = false,
  snapshotFetching = false,
  onRefreshSnapshot,
  onOperationQueued,
}: ExtensionsDrawerProps) => {
  const { message, modal } = App.useApp()

  const [manualOperation, setManualOperation] = useState<ManualOperationKey>('extensions.sync')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | undefined>(undefined)
  const [extensionName, setExtensionName] = useState<string>('')
  const [applyActiveEnabled, setApplyActiveEnabled] = useState(false)
  const [applyActiveValue, setApplyActiveValue] = useState(false)
  const [applySafeModeEnabled, setApplySafeModeEnabled] = useState(false)
  const [applySafeModeValue, setApplySafeModeValue] = useState(false)
  const [applyUnsafeActionProtectionEnabled, setApplyUnsafeActionProtectionEnabled] = useState(false)
  const [applyUnsafeActionProtectionValue, setApplyUnsafeActionProtectionValue] = useState(false)
  const [planPending, setPlanPending] = useState(false)
  const [applyPending, setApplyPending] = useState(false)

  const bindingsQuery = useManualOperationBindings()
  const upsertBindingMutation = useUpsertManualOperationBinding()
  const deleteBindingMutation = useDeleteManualOperationBinding()

  const preferredBindingByOperation = useMemo(() => {
    const map = new Map<ManualOperationKey, { template_id: string; updated_at?: string | null; updated_by?: string | null }>()
    for (const row of bindingsQuery.data ?? []) {
      const op = row?.manual_operation
      if (op === 'extensions.sync' || op === 'extensions.set_flags') {
        map.set(op, {
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
    queryKey: ['databases', 'extensions', 'manual-operation-templates', manualOperation],
    enabled: open,
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

  useEffect(() => {
    if (!open) return
    const optionValues = new Set(templateOptions.map((item) => item.value))
    if (selectedTemplateId && optionValues.has(selectedTemplateId)) return
    const preferredTemplateId = preferredBinding?.template_id
    if (preferredTemplateId && optionValues.has(preferredTemplateId)) {
      setSelectedTemplateId(preferredTemplateId)
      return
    }
    setSelectedTemplateId(undefined)
  }, [open, preferredBinding?.template_id, selectedTemplateId, templateOptions])

  useEffect(() => {
    if (!open) return
    if (manualOperation === 'extensions.sync') {
      setExtensionName('')
      setApplyActiveEnabled(false)
      setApplySafeModeEnabled(false)
      setApplyUnsafeActionProtectionEnabled(false)
    }
  }, [manualOperation, open])

  const extensionNameOptions = useMemo(() => {
    const root = snapshot?.snapshot
    if (!root || typeof root !== 'object') return [] as Array<{ value: string; label: string }>
    const rawList = (root as Record<string, unknown>).extensions
    if (!Array.isArray(rawList)) return [] as Array<{ value: string; label: string }>
    const names = new Set<string>()
    for (const row of rawList) {
      if (!row || typeof row !== 'object') continue
      const record = row as Record<string, unknown>
      const candidates = [record.name, record.extension_name, record.id]
      for (const candidate of candidates) {
        if (typeof candidate !== 'string') continue
        const trimmed = candidate.trim()
        if (!trimmed) continue
        names.add(trimmed)
      }
    }
    return Array.from(names)
      .sort((a, b) => a.localeCompare(b))
      .map((value) => ({ value, label: value }))
  }, [snapshot?.snapshot])

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

  const runManualOperation = async () => {
    if (!databaseId) return
    if (planPending || applyPending) return
    if (mutatingDisabled) return
    if (templateSelectionMissing) {
      message.error('Select template or configure preferred binding')
      return
    }

    const isSetFlagsOperation = manualOperation === 'extensions.set_flags'
    const flagsValues = {
      active: applyActiveValue,
      safe_mode: applySafeModeValue,
      unsafe_action_protection: applyUnsafeActionProtectionValue,
    }
    const applyMask = {
      active: applyActiveEnabled,
      safe_mode: applySafeModeEnabled,
      unsafe_action_protection: applyUnsafeActionProtectionEnabled,
    }

    if (isSetFlagsOperation) {
      const name = extensionName.trim()
      if (!name) {
        message.error('extension_name is required for extensions.set_flags')
        return
      }
      if (!hasSetFlagsMaskSelection(applyMask)) {
        message.error('Select at least one flag to apply')
        return
      }
    }

    const buildPlanRequest = () => {
      if (isSetFlagsOperation) {
        return {
          database_ids: [databaseId],
          manual_operation: manualOperation,
          template_id: selectedTemplateId || undefined,
          extension_name: extensionName.trim(),
          flags_values: flagsValues,
          apply_mask: applyMask,
        }
      }
      return {
        database_ids: [databaseId],
        manual_operation: manualOperation,
        template_id: selectedTemplateId || undefined,
      }
    }

    setPlanPending(true)
    try {
      const plan = await api.postExtensionsPlan(buildPlanRequest())
      const previewText = formatExecutionPlan(plan.execution_plan)
      const bindings = extractBindings(plan.bindings)

      modal.confirm({
        title: isSetFlagsOperation ? 'Apply selected flags?' : 'Launch extensions sync?',
        content: (
          <div>
            <div style={{ marginBottom: 8 }}>
              Database: <Typography.Text code>{databaseName || databaseId}</Typography.Text>
            </div>
            <div style={{ marginBottom: 8 }}>
              Manual operation: <Typography.Text code>{manualOperation}</Typography.Text>
            </div>
            <div style={{ marginBottom: 8 }}>
              Template: <Typography.Text code>{selectedTemplateId || preferredBinding?.template_id || 'preferred binding'}</Typography.Text>
            </div>
            {isSetFlagsOperation && (
              <>
                <div style={{ marginBottom: 8 }}>
                  Extension: <Typography.Text code>{extensionName.trim()}</Typography.Text>
                </div>
                <Space size={8} wrap style={{ marginBottom: 8 }}>
                  <div>Active: {applyMask.active ? renderInlinePill(flagsValues.active ? 'on' : 'off', flagsValues.active ? 'green' : 'red') : <Typography.Text type="secondary">skipped</Typography.Text>}</div>
                  <div>Safe mode: {applyMask.safe_mode ? renderInlinePill(flagsValues.safe_mode ? 'on' : 'off', flagsValues.safe_mode ? 'green' : 'red') : <Typography.Text type="secondary">skipped</Typography.Text>}</div>
                  <div>Unsafe action protection: {applyMask.unsafe_action_protection ? renderInlinePill(flagsValues.unsafe_action_protection ? 'on' : 'off', flagsValues.unsafe_action_protection ? 'green' : 'red') : <Typography.Text type="secondary">skipped</Typography.Text>}</div>
                </Space>
              </>
            )}
            {previewText ? (
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{previewText}</pre>
            ) : (
              <div style={{ opacity: 0.7 }}>Preview not available</div>
            )}
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Binding Provenance:</div>
              {bindings.length > 0 ? (
                renderBindingProvenancePreview(bindings)
              ) : (
                <div style={{ opacity: 0.7 }}>No bindings</div>
              )}
            </div>
          </div>
        ),
        okText: 'Apply',
        cancelText: 'Cancel',
        onOk: async () => {
          setApplyPending(true)
          try {
            const res = await api.postExtensionsApply({ plan_id: plan.plan_id })
            message.success(isSetFlagsOperation ? 'Operation queued: set_flags rollout' : 'Operation queued: extensions sync')
            const operationId = typeof res.operation_id === 'string' ? res.operation_id : null
            if (operationId) {
              onOperationQueued?.(operationId)
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
        message.error(`Failed to launch manual operation: ${errorMessage}`)
      }
    } finally {
      setPlanPending(false)
    }
  }

  const setFlagsOperationSelected = manualOperation === 'extensions.set_flags'
  const trackExtensionsAction = <T,>(
    actionName: string,
    handler: () => T,
  ) => trackUiAction({
    actionKind: 'operator.action',
    actionName,
    context: {
      database_id: databaseId,
      manual_operation: manualOperation,
      template_id: selectedTemplateId || preferredBinding?.template_id,
    },
  }, handler)

  return (
    <DrawerFormShell
      title={databaseName ? `Extensions: ${databaseName}` : 'Extensions'}
      open={open}
      onClose={onClose}
      width={760}
      drawerTestId="database-extensions-drawer"
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {mutatingDisabled && (
          <Alert
            type="warning"
            showIcon
            message="Mutating actions are disabled"
            description="Staff users must select a tenant (X-CC1C-Tenant-ID) to run mutating actions."
          />
        )}

        <Typography.Title level={5} style={{ marginTop: 0 }}>
          Manual Operations
        </Typography.Title>
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Space align="center" wrap>
            <Typography.Text type="secondary">Operation</Typography.Text>
            <Select
              value={manualOperation}
              options={MANUAL_OPERATION_OPTIONS}
              onChange={(value) => setManualOperation(value)}
              style={{ minWidth: 260 }}
            />
          </Space>
          <Space align="center" wrap>
            <Typography.Text type="secondary">Template</Typography.Text>
            <Select
              value={selectedTemplateId}
              options={templateOptions}
              onChange={(value) => setSelectedTemplateId(value)}
              allowClear
              loading={templatesQuery.isLoading}
              placeholder={templatesQuery.isLoading ? 'Loading templates…' : 'Select template (or rely on preferred)'}
              style={{ minWidth: 420 }}
            />
            <Button
              size="small"
              onClick={() => {
                void trackExtensionsAction('Save preferred template binding', savePreferredBinding)
              }}
              loading={upsertBindingMutation.isPending}
              disabled={!selectedTemplateId || mutatingDisabled}
            >
              Save preferred
            </Button>
            <Button
              size="small"
              onClick={() => {
                void trackExtensionsAction('Clear preferred template binding', clearPreferredBinding)
              }}
              loading={deleteBindingMutation.isPending}
              disabled={!preferredBinding || mutatingDisabled}
            >
              Clear preferred
            </Button>
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
            <Space size={8} wrap>
              {renderInlinePill('preferred', 'geekblue')}
              {renderInlinePill(preferredBinding.template_id)}
              {preferredBinding.updated_at && renderInlinePill(dayjs(preferredBinding.updated_at).format('DD.MM.YYYY HH:mm'))}
              {preferredBinding.updated_by && renderInlinePill(preferredBinding.updated_by)}
            </Space>
          )}
          {selectedTemplate && (
            <Space size={8} wrap>
              {renderInlinePill(selectedTemplate.value, 'blue')}
              {renderInlinePill(selectedTemplate.capability || 'no capability')}
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
              <Select
                showSearch
                allowClear
                value={extensionName || undefined}
                options={extensionNameOptions}
                onChange={(value) => setExtensionName(value || '')}
                onSearch={(value) => setExtensionName(value)}
                placeholder="extension_name"
                style={{ minWidth: 320 }}
              />
              <Space align="center" wrap>
                <Checkbox checked={applyActiveEnabled} onChange={(e) => setApplyActiveEnabled(e.target.checked)}>
                  Active
                </Checkbox>
                <Switch checked={applyActiveValue} onChange={setApplyActiveValue} disabled={!applyActiveEnabled} />
              </Space>
              <Space align="center" wrap>
                <Checkbox checked={applySafeModeEnabled} onChange={(e) => setApplySafeModeEnabled(e.target.checked)}>
                  Safe mode
                </Checkbox>
                <Switch checked={applySafeModeValue} onChange={setApplySafeModeValue} disabled={!applySafeModeEnabled} />
              </Space>
              <Space align="center" wrap>
                <Checkbox checked={applyUnsafeActionProtectionEnabled} onChange={(e) => setApplyUnsafeActionProtectionEnabled(e.target.checked)}>
                  Unsafe action protection
                </Checkbox>
                <Switch
                  checked={applyUnsafeActionProtectionValue}
                  onChange={setApplyUnsafeActionProtectionValue}
                  disabled={!applyUnsafeActionProtectionEnabled}
                />
              </Space>
            </>
          )}
          <Button
            type="primary"
            onClick={() => {
              void trackExtensionsAction('Apply extensions manual operation', runManualOperation)
            }}
            loading={planPending || applyPending}
            disabled={mutatingDisabled || templateSelectionMissing || !databaseId}
          >
            Apply
          </Button>
        </Space>

        <Typography.Title level={5} style={{ marginTop: 8 }}>
          Snapshot
        </Typography.Title>
        <Space style={{ marginBottom: 8 }}>
          <Button
            size="small"
            onClick={() => {
              void trackExtensionsAction('Refresh extensions snapshot', onRefreshSnapshot)
            }}
            loading={snapshotFetching}
          >
            Refresh
          </Button>
          <Typography.Text type="secondary">
            Updated:{' '}
            {snapshot?.updated_at
              ? dayjs(snapshot.updated_at).format('DD.MM.YYYY HH:mm')
              : 'n/a'}
          </Typography.Text>
          {snapshot?.source_operation_id && (
            <Typography.Text type="secondary">
              Source op: {snapshot.source_operation_id}
            </Typography.Text>
          )}
        </Space>

        {snapshotLoading ? (
          <Spin />
        ) : (
          <pre style={{ maxHeight: 360, overflow: 'auto', background: '#fafafa', padding: 12, borderRadius: 6 }}>
            {JSON.stringify(snapshot?.snapshot ?? {}, null, 2)}
          </pre>
        )}
      </Space>
    </DrawerFormShell>
  )
}
