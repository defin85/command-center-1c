import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Alert, App, Button, Form, Popconfirm, Space, Switch, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  listOperationCatalogExposures,
  validateOperationCatalogExposure,
} from '../../api/operationCatalog'
import {
  type OperationTemplate,
  buildTemplateOperationCatalogUpsertPayload,
  useCreateTemplate,
  useDeleteTemplate,
  usePoolRuntimeRegistryInspect,
  useSyncTemplatesFromRegistry,
  useUpdateTemplate,
} from '../../api/queries/templates'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { useAuthz } from '../../authz/useAuthz'
import { isPlainObject } from '../Settings/actionCatalogUtils'
import type { ActionFormValues } from '../Settings/actionCatalogTypes'
import {
  OperationExposureEditorModal,
  type ModalValidationIssue,
  type TemplateModalProvenance,
} from '../Settings/actionCatalog/OperationExposureEditorModal'
import { buildTemplateEditorValues, buildTemplateWritePayloadFromEditor } from './templateEditorAdapter'

const { Title, Text } = Typography

type TemplateRow = OperationTemplate & {
  status: string
}

const TEMPLATE_EDITOR_FIELD_PATHS: Array<Array<string>> = [
  ['id'],
  ['name'],
  ['description'],
  ['capability'],
  ['is_active'],
  ['executor', 'kind'],
  ['executor', 'command_id'],
  ['executor', 'workflow_id'],
  ['executor', 'mode'],
  ['executor', 'params_json'],
  ['executor', 'additional_args'],
  ['executor', 'stdin'],
  ['executor', 'target_binding_extension_name_param'],
  ['executor', 'fixed'],
  ['executor', 'fixed', 'confirm_dangerous'],
  ['executor', 'fixed', 'timeout_seconds'],
]

const normalizeText = (value: unknown): string => (
  typeof value === 'string' ? value.trim() : ''
)

const renderCellText = (
  value: string | null | undefined,
  options?: { code?: boolean; maxWidth?: number; secondary?: boolean }
) => {
  const normalized = normalizeText(value)
  if (!normalized) return <Text type="secondary">—</Text>
  const maxWidth = options?.maxWidth ?? 220
  return (
    <Text
      code={options?.code}
      type={options?.secondary ? 'secondary' : undefined}
      ellipsis={{ tooltip: normalized }}
      style={{ maxWidth, display: 'block' }}
    >
      {normalized}
    </Text>
  )
}

const isValidationIssue = (value: unknown): value is ModalValidationIssue => (
  Boolean(value)
  && typeof value === 'object'
  && typeof (value as { message?: unknown }).message === 'string'
)

const toValidationIssues = (value: unknown): ModalValidationIssue[] => {
  if (!Array.isArray(value)) return []
  return value
    .filter(isValidationIssue)
    .map((item) => ({
      path: normalizeText(item.path) || 'global',
      code: normalizeText(item.code) || undefined,
      message: normalizeText(item.message) || 'Validation failed',
    }))
}

const extractValidationIssuesFromError = (error: unknown): ModalValidationIssue[] => {
  const err = error as {
    response?: {
      data?: {
        validation_errors?: unknown
        errors?: unknown
        error?: { message?: unknown }
      }
    }
  } | null
  const data = err?.response?.data
  const direct = [
    ...toValidationIssues(data?.validation_errors),
    ...toValidationIssues(data?.errors),
  ]
  if (direct.length > 0) return direct
  const nested = data?.error?.message
  return toValidationIssues(nested)
}

const isFormValidationError = (error: unknown): boolean => (
  Boolean(error)
  && typeof error === 'object'
  && Array.isArray((error as { errorFields?: unknown }).errorFields)
)

const mapValidationPathToField = (pathRaw: string): string[] | null => {
  const path = normalizeText(pathRaw)
  if (!path) return null

  if (path === 'exposure.alias') return ['id']
  if (path === 'exposure.name') return ['name']
  if (path === 'exposure.description') return ['description']
  if (path === 'exposure.capability') return ['capability']
  if (path === 'exposure.is_active') return ['is_active']
  if (path === 'definition.executor_kind' || path === 'definition.executor_payload.kind') return ['executor', 'kind']
  if (path === 'definition.executor_payload.command_id') return ['executor', 'command_id']
  if (path === 'definition.executor_payload.workflow_id') return ['executor', 'workflow_id']
  if (path === 'definition.executor_payload.mode') return ['executor', 'mode']
  if (path === 'definition.executor_payload.params' || path.startsWith('definition.executor_payload.params.')) return ['executor', 'params_json']
  if (path === 'definition.executor_payload.input_context' || path.startsWith('definition.executor_payload.input_context.')) return ['executor', 'params_json']
  if (path === 'definition.executor_payload.additional_args' || path.startsWith('definition.executor_payload.additional_args.')) return ['executor', 'additional_args']
  if (path === 'definition.executor_payload.stdin') return ['executor', 'stdin']
  if (path === 'definition.executor_payload.operation_type') return ['executor', 'kind']
  if (path === 'definition.executor_payload.template_data') return ['executor', 'params_json']
  if (path === 'definition.executor_payload.template_data.command_id') return ['executor', 'command_id']
  if (path === 'definition.executor_payload.template_data.workflow_id') return ['executor', 'workflow_id']
  if (path === 'definition.executor_payload.template_data.mode') return ['executor', 'mode']
  if (path === 'definition.executor_payload.template_data.params' || path.startsWith('definition.executor_payload.template_data.params.')) return ['executor', 'params_json']
  if (path === 'definition.executor_payload.template_data.input_context' || path.startsWith('definition.executor_payload.template_data.input_context.')) return ['executor', 'params_json']
  if (path === 'definition.executor_payload.template_data.additional_args' || path.startsWith('definition.executor_payload.template_data.additional_args.')) return ['executor', 'additional_args']
  if (path === 'definition.executor_payload.template_data.stdin') return ['executor', 'stdin']
  if (path === 'definition.executor_payload.target_binding.extension_name_param') return ['executor', 'target_binding_extension_name_param']
  if (path === 'definition.executor_payload.template_data.target_binding.extension_name_param') return ['executor', 'target_binding_extension_name_param']
  if (path === 'capability_config.target_binding.extension_name_param') return ['executor', 'target_binding_extension_name_param']
  if (path === 'definition.executor_payload.fixed.confirm_dangerous') return ['executor', 'fixed', 'confirm_dangerous']
  if (path === 'definition.executor_payload.fixed.timeout_seconds') return ['executor', 'fixed', 'timeout_seconds']
  if (path.startsWith('definition.executor_payload.fixed')) return ['executor', 'fixed']

  return null
}

const toErrorMessage = (error: unknown, fallback: string): string => {
  const err = error as {
    message?: string
    response?: {
      data?: {
        error?: { message?: string }
        validation_errors?: Array<{ message?: string }>
      }
    }
  } | null
  const validationMessage = err?.response?.data?.validation_errors?.[0]?.message
  if (typeof validationMessage === 'string' && validationMessage.trim()) return validationMessage
  const apiMessage = err?.response?.data?.error?.message
  if (typeof apiMessage === 'string' && apiMessage.trim()) return apiMessage
  if (typeof err?.message === 'string' && err.message.trim()) return err.message
  return fallback
}

const isSystemManagedPoolRuntimeTemplate = (template: TemplateRow): boolean => (
  template.system_managed === true
  && normalizeText(template.domain).toLowerCase() === 'pool_runtime'
)

function OperationTemplateListShell({
  canManageTemplate,
  canManageAnyTemplate,
  showPoolRuntimeDiagnostics,
}: {
  canManageTemplate: (templateId: string) => boolean
  canManageAnyTemplate: boolean
  showPoolRuntimeDiagnostics: boolean
}) {
  const { message } = App.useApp()
  const [dryRun, setDryRun] = useState<boolean>(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<TemplateRow | null>(null)
  const [exposuresReloadTick, setExposuresReloadTick] = useState(0)
  const [editorValues, setEditorValues] = useState<ActionFormValues | null>(null)
  const [modalValidationErrors, setModalValidationErrors] = useState<ModalValidationIssue[]>([])
  const [form] = Form.useForm<ActionFormValues>()

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'id', label: 'Alias', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'system_managed', label: 'Managed', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'domain', label: 'Domain', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'operation_type', label: 'Operation Type', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'executor_kind', label: 'Executor Kind', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'executor_command_id', label: 'Command ID', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'target_entity', label: 'Target', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'template_exposure_id', label: 'Exposure ID', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'template_exposure_revision', label: 'Exposure Revision', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'capability', label: 'Capability', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'status', label: 'Status', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'is_active', label: 'Active', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'updated_at', label: 'Updated', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'actions', label: 'Actions', sortable: false, groupKey: 'meta', groupLabel: 'Meta' },
  ], [])

  const syncMutation = useSyncTemplatesFromRegistry()
  const createMutation = useCreateTemplate()
  const updateMutation = useUpdateTemplate()
  const deleteMutation = useDeleteTemplate()
  const poolRuntimeRegistryQuery = usePoolRuntimeRegistryInspect(showPoolRuntimeDiagnostics)

  const closeModal = useCallback(() => {
    setModalOpen(false)
    setEditingTemplate(null)
    setEditorValues(null)
    setModalValidationErrors([])
  }, [])

  const openCreateModal = useCallback(() => {
    setEditingTemplate(null)
    setEditorValues(buildTemplateEditorValues(null))
    setModalValidationErrors([])
    setModalOpen(true)
  }, [])

  const openEditTemplateModal = useCallback((template: TemplateRow) => {
    if (isSystemManagedPoolRuntimeTemplate(template)) {
      message.warning('System-managed pool runtime template is read-only')
      return
    }
    setEditingTemplate(template)
    setEditorValues(buildTemplateEditorValues(template))
    setModalValidationErrors([])
    setModalOpen(true)
  }, [message])

  const handleDeleteTemplate = useCallback(async (template: TemplateRow) => {
    if (isSystemManagedPoolRuntimeTemplate(template)) {
      message.warning('System-managed pool runtime template is read-only')
      return
    }
    try {
      await deleteMutation.mutateAsync({ template_id: template.id })
      setExposuresReloadTick((value) => value + 1)
      message.success('Template deleted')
    } catch (err) {
      message.error(toErrorMessage(err, 'Failed to delete template'))
    }
  }, [deleteMutation, message])

  const columns: ColumnsType<TemplateRow> = useMemo(() => ([
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 300,
      render: (value: string, record) => (
        <div style={{ minWidth: 0 }}>
          <Text strong ellipsis={{ tooltip: value }} style={{ maxWidth: 260, display: 'block' }}>
            {value}
          </Text>
          {renderCellText(record.id, { secondary: true, maxWidth: 260 })}
        </div>
      ),
    },
    {
      title: 'Managed',
      dataIndex: 'system_managed',
      key: 'system_managed',
      width: 190,
      render: (_value, record) => {
        if (isSystemManagedPoolRuntimeTemplate(record)) {
          return (
            <Space size={6}>
              <Tag color="gold">system-managed</Tag>
              {renderCellText(record.domain || 'pool_runtime', { code: true, maxWidth: 120 })}
            </Space>
          )
        }
        return <Tag>user-managed</Tag>
      },
    },
    {
      title: 'Operation Type',
      dataIndex: 'operation_type',
      key: 'operation_type',
      width: 160,
      render: (value: string | undefined) => renderCellText(value, { maxWidth: 140 }),
    },
    {
      title: 'Executor Kind',
      dataIndex: 'executor_kind',
      key: 'executor_kind',
      width: 140,
      render: (value: string | undefined) => renderCellText(value, { maxWidth: 130 }),
    },
    {
      title: 'Command ID',
      dataIndex: 'executor_command_id',
      key: 'executor_command_id',
      width: 220,
      render: (value: string | undefined | null) => renderCellText(value, { code: true, maxWidth: 200 }),
    },
    {
      title: 'Target',
      dataIndex: 'target_entity',
      key: 'target_entity',
      width: 140,
      render: (value: string | undefined) => renderCellText(value, { maxWidth: 120 }),
    },
    {
      title: 'Exposure ID',
      dataIndex: 'template_exposure_id',
      key: 'template_exposure_id',
      width: 240,
      render: (value: string | undefined) => renderCellText(value, { code: true, maxWidth: 220 }),
    },
    {
      title: 'Revision',
      dataIndex: 'template_exposure_revision',
      key: 'template_exposure_revision',
      width: 110,
      render: (value: number | undefined) => (
        typeof value === 'number' && Number.isFinite(value)
          ? String(value)
          : <Text type="secondary">—</Text>
      ),
    },
    {
      title: 'Capability',
      dataIndex: 'capability',
      key: 'capability',
      width: 220,
      render: (value: string | undefined) => renderCellText(value, { code: true, maxWidth: 200 }),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 130,
    },
    {
      title: 'Active',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 90,
      render: (value: boolean) => (value ? 'yes' : 'no'),
    },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (value: string) => (value ? new Date(value).toLocaleString() : ''),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      render: (_value, record) => {
        const readOnlySystemTemplate = isSystemManagedPoolRuntimeTemplate(record)
        const canMutateTemplate = canManageTemplate(record.id) && !readOnlySystemTemplate
        const disabledReason = readOnlySystemTemplate
          ? 'System-managed pool runtime template is read-only'
          : undefined

        return (
          <Space>
            <Button
              size="small"
              title={disabledReason}
              disabled={!canMutateTemplate}
              onClick={() => {
                openEditTemplateModal(record)
              }}
            >
              Edit
            </Button>
            <Popconfirm
              title="Delete template?"
              okText="Delete"
              cancelText="Cancel"
              onConfirm={() => {
                void handleDeleteTemplate(record)
              }}
              disabled={!canMutateTemplate}
            >
              <Button
                size="small"
                danger
                title={disabledReason}
                disabled={!canMutateTemplate}
              >
                Delete
              </Button>
            </Popconfirm>
          </Space>
        )
      },
    },
  ]), [canManageTemplate, handleDeleteTemplate, openEditTemplateModal])

  const table = useTableToolkit<TemplateRow>({
    tableId: 'operation-templates',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
    disableServerMetadata: true,
  })

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const searchValue = table.search.trim()
  const filtersParam = useMemo(() => (
    table.filtersPayload ? JSON.stringify(table.filtersPayload) : undefined
  ), [table.filtersPayload])
  const sortParam = useMemo(() => (
    table.sortPayload ? JSON.stringify(table.sortPayload) : undefined
  ), [table.sortPayload])

  const exposuresQuery = useQuery({
    queryKey: [
      'templates',
      'operation-exposures',
      exposuresReloadTick,
      searchValue,
      filtersParam ?? '',
      sortParam ?? '',
      table.pagination.page,
      table.pagination.pageSize,
    ],
    queryFn: async () => listOperationCatalogExposures({
      surface: 'template',
      search: searchValue || undefined,
      filters: filtersParam,
      sort: sortParam,
      limit: table.pagination.pageSize,
      offset: pageStart,
    }),
  })

  const pagedRows = useMemo(() => {
    const rows: TemplateRow[] = []

    for (const exposure of exposuresQuery.data?.exposures ?? []) {
      if (exposure.surface !== 'template') continue
      const templateData = isPlainObject(exposure.template_data) ? exposure.template_data : {}
      const templateExposureId = String(exposure.template_exposure_id || exposure.id || '').trim() || undefined
      const rawTemplateExposureRevision = (
        typeof exposure.template_exposure_revision === 'number'
          ? exposure.template_exposure_revision
          : typeof exposure.exposure_revision === 'number'
            ? exposure.exposure_revision
            : undefined
      )
      const templateExposureRevision = (
        typeof rawTemplateExposureRevision === 'number'
          && Number.isFinite(rawTemplateExposureRevision)
          && rawTemplateExposureRevision >= 1
          ? Math.trunc(rawTemplateExposureRevision)
          : undefined
      )
      const commandIdFromTemplateData = (
        typeof templateData.command_id === 'string'
          ? templateData.command_id.trim()
          : ''
      )
      const executorCommandId = (
        typeof exposure.executor_command_id === 'string'
          ? exposure.executor_command_id.trim()
          : commandIdFromTemplateData
      )

      rows.push({
        id: String(exposure.alias || ''),
        status: String(exposure.status || (exposure.is_active !== false ? 'published' : 'draft')),
        name: String(exposure.name || ''),
        description: String(exposure.description || ''),
        operation_type: String(exposure.operation_type || 'designer_cli'),
        executor_kind: String(exposure.executor_kind || exposure.operation_type || 'designer_cli'),
        executor_command_id: executorCommandId || undefined,
        target_entity: String(exposure.target_entity || 'infobase'),
        capability: String(exposure.capability || '').trim() || undefined,
        capability_config: isPlainObject(exposure.capability_config) ? exposure.capability_config : {},
        template_data: templateData,
        is_active: exposure.is_active !== false,
        created_at: String(exposure.created_at || ''),
        updated_at: String(exposure.updated_at || ''),
        exposure_id: String(exposure.id || ''),
        template_exposure_id: templateExposureId,
        template_exposure_revision: templateExposureRevision,
        definition_id: String(exposure.definition_id || ''),
        system_managed: exposure.system_managed === true,
        domain: String(exposure.domain || ''),
      })
    }

    return {
      rows,
      total: typeof exposuresQuery.data?.total === 'number' ? exposuresQuery.data.total : rows.length,
    }
  }, [exposuresQuery.data?.exposures, exposuresQuery.data?.total])

  const activeError = exposuresQuery.error
  const activeErrorStatus = (activeError as { response?: { status?: number } } | null)?.response?.status
  const showAccessWarning = activeErrorStatus === 403
  const poolRuntimeRegistrySummary = useMemo(() => {
    const entries = poolRuntimeRegistryQuery.data?.entries ?? []
    const missingCount = entries.filter((entry) => entry.status === 'missing').length
    const driftCount = entries.filter((entry) => entry.status === 'drift').length
    const configuredCount = entries.filter((entry) => entry.status === 'configured').length
    const issuePreview = entries
      .filter((entry) => entry.status !== 'configured')
      .slice(0, 3)
      .map((entry) => `${entry.alias}: ${entry.issues.join(', ') || entry.status}`)
    return {
      configuredCount,
      missingCount,
      driftCount,
      issuePreview,
      contractVersion: poolRuntimeRegistryQuery.data?.contract_version || 'pool_runtime.v1',
    }
  }, [poolRuntimeRegistryQuery.data?.contract_version, poolRuntimeRegistryQuery.data?.entries])

  const modalTitle = useMemo(() => (
    editingTemplate ? 'Edit Template' : 'New Template'
  ), [editingTemplate])

  const modalProvenance = useMemo<TemplateModalProvenance | null>(() => {
    if (!editingTemplate) return null
    return {
      alias: editingTemplate.id,
      templateExposureId: editingTemplate.template_exposure_id,
      templateExposureRevision: editingTemplate.template_exposure_revision,
      definitionId: editingTemplate.definition_id,
      status: editingTemplate.status,
    }
  }, [editingTemplate])

  const clearMappedFieldErrors = useCallback(() => {
    type SetFieldsPayload = Parameters<(typeof form)['setFields']>[0]
    const fields: SetFieldsPayload = TEMPLATE_EDITOR_FIELD_PATHS.map((name) => ({
      name: name as SetFieldsPayload[number]['name'],
      errors: [],
    }))
    form.setFields(fields)
  }, [form])

  const applyBackendValidationIssues = useCallback((issues: ModalValidationIssue[]) => {
    setModalValidationErrors(issues)
    clearMappedFieldErrors()

    if (issues.length === 0) return

    type SetFieldsPayload = Parameters<(typeof form)['setFields']>[0]
    const fieldIssues = new Map<string, SetFieldsPayload[number]>()
    for (const issue of issues) {
      const fieldName = mapValidationPathToField(issue.path)
      if (!fieldName) continue
      const key = fieldName.join('.')
      const entry = fieldIssues.get(key)
      if (entry) {
        const existingErrors = Array.isArray(entry.errors) ? entry.errors : []
        entry.errors = [...existingErrors, issue.message]
      } else {
        fieldIssues.set(key, {
          name: fieldName as SetFieldsPayload[number]['name'],
          errors: [issue.message],
        })
      }
    }
    if (fieldIssues.size > 0) {
      form.setFields(Array.from(fieldIssues.values()))
    }
  }, [clearMappedFieldErrors, form])

  const handleSaveTemplate = useCallback(async () => {
    if (createMutation.isPending || updateMutation.isPending) return
    applyBackendValidationIssues([])
    try {
      const values = await form.validateFields()
      const built = buildTemplateWritePayloadFromEditor(values, { existingId: editingTemplate?.id })
      if (!built.ok) {
        message.error(built.error)
        return
      }

      const upsertPayload = buildTemplateOperationCatalogUpsertPayload(built.payload)
      const validation = await validateOperationCatalogExposure({
        definition: upsertPayload.definition,
        exposure: upsertPayload.exposure,
      })
      if (!validation.valid) {
        const issues = toValidationIssues(validation.errors)
        applyBackendValidationIssues(issues)
        message.error('Save blocked: fix validation errors before publish/save')
        return
      }

      if (editingTemplate) {
        await updateMutation.mutateAsync(built.payload)
        message.success('Template updated')
      } else {
        await createMutation.mutateAsync(built.payload)
        message.success('Template created')
      }
      setExposuresReloadTick((value) => value + 1)
      closeModal()
    } catch (err) {
      if (isFormValidationError(err)) return
      const issues = extractValidationIssuesFromError(err)
      if (issues.length > 0) {
        applyBackendValidationIssues(issues)
        message.error('Save blocked: fix validation errors before publish/save')
        return
      }
      message.error(toErrorMessage(err, editingTemplate ? 'Failed to update template' : 'Failed to create template'))
    }
  }, [applyBackendValidationIssues, closeModal, createMutation, editingTemplate, form, message, updateMutation])

  const onSync = useCallback(async () => {
    try {
      const result = await syncMutation.mutateAsync({
        dry_run: dryRun,
        include_pool_runtime: true,
      })
      message.success(`${result.message}: created=${result.created}, updated=${result.updated}, unchanged=${result.unchanged}`)
      setExposuresReloadTick((value) => value + 1)
    } catch (err) {
      const status = (err as { response?: { status?: number } } | null)?.response?.status
      if (status === 403) {
        message.error('Sync requires staff access')
        return
      }
      message.error('Failed to sync templates from registry')
    }
  }, [dryRun, message, syncMutation])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>Operation Templates</Title>
          <Text type="secondary">
            Atomic operation catalog for manual execution and workflow nodes. Analyst-authored schemes belong in /workflows.
          </Text>
        </div>
        <Space>
          {canManageAnyTemplate && <Button onClick={openCreateModal}>New Template</Button>}
          {canManageAnyTemplate && (
            <>
              <Space>
                <Text>Dry run</Text>
                <Switch checked={dryRun} onChange={setDryRun} />
              </Space>
              <Button type="primary" loading={syncMutation.isPending} onClick={() => void onSync()}>
                Sync from registry
              </Button>
            </>
          )}
        </Space>
      </div>

      {showAccessWarning && (
        <Alert
          type="warning"
          message="Access denied"
          description="Operation templates are not available for your permissions."
          showIcon
        />
      )}

      <Alert
        type="info"
        showIcon
        message="Atomic operations only"
        description="Use /workflows to model analyst-facing schemes. workflow executor templates remain available here only as a compatibility/integration path."
      />

      {showPoolRuntimeDiagnostics && (
        <Alert
          data-testid="templates-pool-runtime-registry"
          type={poolRuntimeRegistryQuery.isError || poolRuntimeRegistrySummary.missingCount > 0 || poolRuntimeRegistrySummary.driftCount > 0 ? 'warning' : 'success'}
          message={poolRuntimeRegistryQuery.isLoading ? 'Pool runtime registry diagnostics: loading' : 'Pool runtime registry diagnostics'}
          description={poolRuntimeRegistryQuery.isError ? (
            'Failed to load pool runtime registry diagnostics.'
          ) : (
            <Space direction="vertical" size={2}>
              <Text type="secondary">
                {`contract_version=${poolRuntimeRegistrySummary.contractVersion}`}
              </Text>
              <Text type="secondary">
                {`configured=${poolRuntimeRegistrySummary.configuredCount}, missing=${poolRuntimeRegistrySummary.missingCount}, drift=${poolRuntimeRegistrySummary.driftCount}`}
              </Text>
              {poolRuntimeRegistrySummary.issuePreview.length > 0 && (
                <Text type="secondary">
                  {`issues: ${poolRuntimeRegistrySummary.issuePreview.join(' | ')}`}
                </Text>
              )}
            </Space>
          )}
          showIcon
        />
      )}

      <TableToolkit
        table={table}
        data={pagedRows.rows}
        total={pagedRows.total}
        loading={exposuresQuery.isLoading}
        rowKey={(row) => row.id}
        columns={columns}
        searchPlaceholder="Search templates"
        scroll={{ x: Math.max(1400, table.totalColumnsWidth + 120) }}
      />

      {modalOpen && (
        <OperationExposureEditorModal
          open={modalOpen}
          title={modalTitle}
          surface="template"
          executorKindOptions={['ibcmd_cli', 'designer_cli', 'workflow']}
          form={form}
          initialValues={editorValues}
          templateProvenance={modalProvenance}
          backendValidationErrors={modalValidationErrors}
          onCancel={closeModal}
          onApply={() => void handleSaveTemplate()}
        />
      )}
    </Space>
  )
}

export function TemplatesPage() {
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const canManageAnyTemplate = isStaff || authz.canAnyTemplate('MANAGE')
  const canManageTemplate = useCallback((templateId: string) => (
    isStaff || authz.canTemplate(templateId, 'MANAGE')
  ), [authz, isStaff])
  const [searchParams, setSearchParams] = useSearchParams()
  const surfaceParam = searchParams.get('surface')

  useEffect(() => {
    if (surfaceParam === null) return
    const next = new URLSearchParams(searchParams)
    next.delete('surface')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams, surfaceParam])

  return (
    <OperationTemplateListShell
      canManageTemplate={canManageTemplate}
      canManageAnyTemplate={canManageAnyTemplate}
      showPoolRuntimeDiagnostics={isStaff}
    />
  )
}
