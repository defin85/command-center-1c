import { StrictMode, type ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp, ConfigProvider } from 'antd'
import { MemoryRouter, useLocation } from 'react-router-dom'

import type {
  PoolBatch,
  PoolRun,
  PoolRunReadinessBlocker,
  PoolRunReadinessChecklist,
  PoolRunReport,
  PoolSchemaTemplate,
  PoolWorkflowBinding,
} from '../../../api/intercompanyPools'
import { changeLanguage, ensureNamespaces } from '../../../i18n/runtime'
import { resetQueryClient } from '../../../lib/queryClient'
import { HEAVY_ROUTE_TEST_TIMEOUT_MS } from '../../../test/timeouts'
import { PoolRunsPage } from '../PoolRunsPage'

const mockListOrganizationPools = vi.fn()
const mockListPoolSchemaTemplates = vi.fn()
const mockListPoolBatches = vi.fn()
const mockGetPoolGraph = vi.fn()
const mockListPoolRuns = vi.fn()
const mockGetPoolRunReport = vi.fn()
const mockCreatePoolBatch = vi.fn()
const mockCreatePoolRun = vi.fn()
const mockPreviewPoolWorkflowBinding = vi.fn()
const mockRetryPoolRunFailed = vi.fn()
const mockConfirmPoolRunPublication = vi.fn()
const mockAbortPoolRunPublication = vi.fn()
let consoleErrorSpy: ReturnType<typeof vi.spyOn> | null = null

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd')
  const React = await import('react')

  const readValue = (record: Record<string, unknown>, dataIndex: unknown) => {
    if (Array.isArray(dataIndex)) {
      return dataIndex.reduce<unknown>((current, key) => (
        current && typeof current === 'object' ? (current as Record<string, unknown>)[String(key)] : undefined
      ), record)
    }
    if (typeof dataIndex === 'string') {
      return record[dataIndex]
    }
    return undefined
  }

  const Card = ({
    title,
    extra,
    loading,
    children,
    ...props
  }: {
    title?: ReactNode
    extra?: ReactNode
    loading?: boolean
    children?: ReactNode
    [key: string]: unknown
  }) => (
    <section {...props}>
      {title ? <h3>{title}</h3> : null}
      {extra}
      {loading ? <div>Loading</div> : children}
    </section>
  )

  const Tag = ({
    children,
    ...props
  }: {
    children?: ReactNode
    [key: string]: unknown
  }) => <span {...props}>{children}</span>

  const DescriptionsItem = ({
    label,
    children,
  }: {
    label?: ReactNode
    children?: ReactNode
  }) => (
    <div>
      {label ? <span>{label}</span> : null}
      {children}
    </div>
  )

  const Descriptions = Object.assign(
    ({ children }: { children?: ReactNode }) => <section>{children}</section>,
    { Item: DescriptionsItem }
  )

  const Table = ({
    dataSource,
    columns,
    rowKey,
    loading,
  }: {
    dataSource?: Array<Record<string, unknown>>
    columns?: Array<{
      key?: string
      title?: ReactNode
      dataIndex?: unknown
      render?: (value: unknown, record: Record<string, unknown>, index: number) => ReactNode
    }>
    rowKey?: string | ((record: Record<string, unknown>) => string)
    loading?: boolean
  }) => {
    const rows = dataSource ?? []
    if (loading) {
      return <div>Loading</div>
    }
    return (
      <table>
        <thead>
          <tr>
            {(columns ?? []).map((column, index) => (
              <th key={column.key ?? `${index}`}>{column.title}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((record, index) => {
            const resolvedRowKey = typeof rowKey === 'function'
              ? rowKey(record)
              : typeof rowKey === 'string'
                ? String(record[rowKey] ?? index)
                : String(record.id ?? index)
            return (
              <tr key={resolvedRowKey}>
                {(columns ?? []).map((column, columnIndex) => {
                  const value = readValue(record, column.dataIndex)
                  const content = column.render
                    ? column.render(value, record, index)
                    : (
                      value == null
                        ? ''
                        : typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
                          ? String(value)
                          : JSON.stringify(value)
                    )
                  return <td key={column.key ?? `${resolvedRowKey}-${columnIndex}`}>{content}</td>
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    )
  }

  const Collapse = ({
    items,
  }: {
    items?: Array<{ key: string; label: ReactNode; children: ReactNode }>
  }) => {
    const [openKeys, setOpenKeys] = React.useState<Set<string>>(() => new Set())
    return (
      <div>
        {(items ?? []).map((item) => {
          const isOpen = openKeys.has(item.key)
          return (
            <section key={item.key}>
              <button
                type="button"
                onClick={() => {
                  setOpenKeys((current) => {
                    const next = new Set(current)
                    if (next.has(item.key)) {
                      next.delete(item.key)
                    } else {
                      next.add(item.key)
                    }
                    return next
                  })
                }}
              >
                {item.label}
              </button>
              {isOpen ? <div>{item.children}</div> : null}
            </section>
          )
        })}
      </div>
    )
  }

  return {
    ...actual,
    Card,
    Collapse,
    Descriptions,
    Table,
    Tag,
  }
})

vi.mock('reactflow', () => ({
  default: ({ children }: { children?: ReactNode }) => <div data-testid="mock-reactflow">{children}</div>,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
}))

vi.mock('../../../components/platform', async () => {
  const { useNavigate } = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')

  const readValue = (record: Record<string, unknown>, dataIndex: unknown) => {
    if (Array.isArray(dataIndex)) {
      return dataIndex.reduce<unknown>((current, key) => (
        current && typeof current === 'object' ? (current as Record<string, unknown>)[String(key)] : undefined
      ), record)
    }
    if (typeof dataIndex === 'string') {
      return record[dataIndex]
    }
    return undefined
  }

  return {
    WorkspacePage: ({ header, children }: { header?: ReactNode; children: ReactNode }) => (
      <div>
        {header}
        {children}
      </div>
    ),
    PageHeader: ({
      title,
      subtitle,
      actions,
    }: {
      title: ReactNode
      subtitle?: ReactNode
      actions?: ReactNode
    }) => (
      <div>
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
        {actions}
      </div>
    ),
    RouteButton: ({
      to,
      children,
      disabled,
    }: {
      to: string
      children: ReactNode
      disabled?: boolean
    }) => {
      const navigate = useNavigate()

      return (
        <button type="button" data-to={to} disabled={disabled} onClick={() => navigate(to)}>
          {children}
        </button>
      )
    },
    MasterDetailShell: ({
      list,
      detail,
      detailOpen,
      detailDrawerTitle,
      onCloseDetail,
    }: {
      list: ReactNode
      detail: ReactNode
      detailOpen?: boolean
      detailDrawerTitle?: ReactNode
      onCloseDetail?: () => void
    }) => (
      <div>
        <section>{list}</section>
        <section data-detail-open={detailOpen ? 'true' : 'false'}>
          {detailDrawerTitle ? <h3>{detailDrawerTitle}</h3> : null}
          {detailOpen && onCloseDetail ? (
            <button type="button" onClick={onCloseDetail}>
              Close detail
            </button>
          ) : null}
          {detail}
        </section>
      </div>
    ),
    EntityTable: ({
      title,
      loading,
      emptyDescription,
      dataSource,
      columns,
      rowKey,
      onRow,
      rowClassName,
    }: {
      title?: ReactNode
      loading?: boolean
      emptyDescription?: ReactNode
      dataSource?: Array<Record<string, unknown>>
      columns?: Array<{
        key?: string
        dataIndex?: unknown
        render?: (value: unknown, record: Record<string, unknown>, index: number) => ReactNode
      }>
      rowKey?: string | ((record: Record<string, unknown>) => string)
      onRow?: (record: Record<string, unknown>) => { onClick?: () => void; style?: Record<string, unknown> }
      rowClassName?: (record: Record<string, unknown>) => string
    }) => {
      const rows = dataSource ?? []
      return (
        <div>
          {title ? <h3>{title}</h3> : null}
          {loading ? <div>Loading</div> : null}
          {!loading && rows.length === 0 ? <div>{emptyDescription}</div> : null}
          {rows.map((record, index) => {
            const resolvedRowKey = typeof rowKey === 'function'
              ? rowKey(record)
              : typeof rowKey === 'string'
                ? String(record[rowKey])
                : String(record.id ?? index)
            const rowProps = onRow?.(record) ?? {}
            return (
              <div
                key={resolvedRowKey}
                data-testid={`entity-table-row-${resolvedRowKey}`}
                className={rowClassName?.(record)}
                onClick={rowProps.onClick}
              >
                {(columns ?? []).map((column, columnIndex) => {
                  const value = readValue(record, column.dataIndex)
                  const content = column.render
                    ? column.render(value, record, index)
                    : (
                      value == null
                        ? ''
                        : typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
                          ? String(value)
                          : JSON.stringify(value)
                    )
                  return (
                    <div key={column.key ?? `${resolvedRowKey}-${columnIndex}`}>
                      {content}
                    </div>
                  )
                })}
              </div>
            )
          })}
        </div>
      )
    },
  }
})

vi.mock('../../../api/intercompanyPools', () => ({
  listOrganizationPools: (...args: unknown[]) => mockListOrganizationPools(...args),
  listPoolSchemaTemplates: (...args: unknown[]) => mockListPoolSchemaTemplates(...args),
  listPoolBatches: (...args: unknown[]) => mockListPoolBatches(...args),
  getPoolGraph: (...args: unknown[]) => mockGetPoolGraph(...args),
  listPoolRuns: (...args: unknown[]) => mockListPoolRuns(...args),
  getPoolRunReport: (...args: unknown[]) => mockGetPoolRunReport(...args),
  createPoolBatch: (...args: unknown[]) => mockCreatePoolBatch(...args),
  createPoolRun: (...args: unknown[]) => mockCreatePoolRun(...args),
  previewPoolWorkflowBinding: (...args: unknown[]) => mockPreviewPoolWorkflowBinding(...args),
  retryPoolRunFailed: (...args: unknown[]) => mockRetryPoolRunFailed(...args),
  confirmPoolRunPublication: (...args: unknown[]) => mockConfirmPoolRunPublication(...args),
  abortPoolRunPublication: (...args: unknown[]) => mockAbortPoolRunPublication(...args),
}))

vi.mock('../PoolBatchIntakeDrawer', async () => {
  const React = await import('react')
  const { createPoolBatch } = await import('../../../api/intercompanyPools')

  type MockPoolBatchIntakeDrawerProps = {
    open: boolean
    poolId: string | null
    schemaTemplates: PoolSchemaTemplate[]
    initialValues: {
      batchKind: 'sale' | 'receipt'
      periodStart: string
      periodEnd?: string | null
      poolWorkflowBindingId?: string | null
      startOrganizationId?: string | null
    }
    onClose: () => void
    onCreated: (
      response: Awaited<ReturnType<typeof createPoolBatch>>,
      context: {
        batchKind: 'sale' | 'receipt'
        periodStart: string
        periodEnd: string | null
        poolWorkflowBindingId: string | null
        startOrganizationId: string | null
      },
    ) => Promise<void> | void
  }

  const PoolBatchIntakeDrawer = ({
    open,
    poolId,
    schemaTemplates,
    initialValues,
    onClose,
    onCreated,
  }: MockPoolBatchIntakeDrawerProps) => {
    const [schemaTemplateId, setSchemaTemplateId] = React.useState('')
    const [sourceReference, setSourceReference] = React.useState('')
    const [sourcePayloadJson, setSourcePayloadJson] = React.useState('[]')

    React.useEffect(() => {
      if (!open) {
        return
      }
      setSchemaTemplateId(schemaTemplates[0]?.id ?? '')
      setSourceReference('')
      setSourcePayloadJson('[]')
    }, [open, schemaTemplates])

    if (!open) {
      return null
    }

    const handleSubmit = async () => {
      if (!poolId) {
        return
      }

      const poolWorkflowBindingId = initialValues.poolWorkflowBindingId?.trim() || null
      const startOrganizationId = initialValues.startOrganizationId?.trim() || null
      const periodEnd = initialValues.periodEnd?.trim() || initialValues.periodEnd || null
      const basePayload = {
        pool_id: poolId,
        source_type: 'schema_template_upload' as const,
        schema_template_id: schemaTemplateId,
        period_start: initialValues.periodStart,
        period_end: periodEnd,
        source_reference: sourceReference.trim(),
        raw_payload_ref: '',
        json_payload: JSON.parse(sourcePayloadJson),
      }

      const payload = initialValues.batchKind === 'receipt'
        ? {
            ...basePayload,
            batch_kind: 'receipt' as const,
            pool_workflow_binding_id: poolWorkflowBindingId ?? '',
            start_organization_id: startOrganizationId ?? '',
          }
        : {
            ...basePayload,
            batch_kind: 'sale' as const,
          }

      const response = await createPoolBatch(payload)

      await onCreated(response, {
        batchKind: initialValues.batchKind,
        periodStart: initialValues.periodStart,
        periodEnd,
        poolWorkflowBindingId,
        startOrganizationId,
      })
      onClose()
    }

    return (
      <div data-testid="pool-runs-batch-intake-drawer">
        <select
          data-testid="pool-runs-batch-intake-schema-template"
          value={schemaTemplateId}
          onChange={(event) => setSchemaTemplateId(event.target.value)}
        >
          {schemaTemplates.map((schemaTemplate) => (
            <option key={schemaTemplate.id} value={schemaTemplate.id}>
              {schemaTemplate.code} - {schemaTemplate.name}
            </option>
          ))}
        </select>
        <input
          data-testid="pool-runs-batch-intake-source-reference"
          value={sourceReference}
          onChange={(event) => setSourceReference(event.target.value)}
        />
        <textarea
          data-testid="pool-runs-batch-intake-source-payload"
          value={sourcePayloadJson}
          onChange={(event) => setSourcePayloadJson(event.target.value)}
        />
        <button type="button" data-testid="pool-runs-batch-intake-submit" onClick={() => void handleSubmit()}>
          Submit
        </button>
      </div>
    )
  }

  return { PoolBatchIntakeDrawer }
})

function buildRun(overrides: Partial<PoolRun> = {}): PoolRun {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    pool_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    schema_template_id: null,
    mode: 'safe',
    direction: 'bottom_up',
    status: 'validated',
    status_reason: 'awaiting_approval',
    period_start: '2026-01-01',
    period_end: null,
    run_input: { source_payload: [{ inn: '730000000001', amount: '100.00' }] },
    input_contract_version: 'run_input_v1',
    idempotency_key: 'idem-1',
    workflow_execution_id: '22222222-2222-2222-2222-222222222222',
    workflow_status: 'pending',
    root_operation_id: '22222222-2222-2222-2222-222222222222',
    execution_consumer: 'pools',
    lane: 'workflows',
    approval_state: 'awaiting_approval',
    publication_step_state: 'not_enqueued',
    readiness_blockers: [],
    readiness_checklist: buildReadinessChecklist({ status: 'ready' }),
    verification_status: 'not_verified',
    verification_summary: null,
    terminal_reason: null,
    execution_backend: 'workflow_core',
    provenance: {
      workflow_run_id: '22222222-2222-2222-2222-222222222222',
      workflow_status: 'pending',
      execution_backend: 'workflow_core',
      root_operation_id: '22222222-2222-2222-2222-222222222222',
      execution_consumer: 'pools',
      lane: 'workflows',
      retry_chain: [
        {
          workflow_run_id: '22222222-2222-2222-2222-222222222222',
          parent_workflow_run_id: null,
          attempt_number: 1,
          attempt_kind: 'initial',
          status: 'pending',
        },
      ],
    },
    workflow_template_name: 'pool-template-v1',
    seed: null,
    validation_summary: { rows: 5 },
    publication_summary: { total_targets: 3 },
    diagnostics: [{ step: 'prepare_input', status: 'ok' }],
    last_error: '',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:01:00Z',
    validated_at: '2026-01-01T00:00:30Z',
    publication_confirmed_at: null,
    publishing_started_at: null,
    completed_at: null,
    ...overrides,
  }
}

function buildReceiptBatch(overrides: Partial<PoolBatch> = {}): PoolBatch {
  return {
    id: '99999999-9999-9999-9999-999999999999',
    tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    pool_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    batch_kind: 'receipt',
    source_type: 'schema_template_upload',
    schema_template_id: '55555555-5555-5555-5555-555555555555',
    start_organization_id: '11111111-1111-1111-1111-111111111111',
    run_id: null,
    workflow_execution_id: null,
    operation_id: null,
    workflow_status: '',
    period_start: '2026-01-01',
    period_end: '2026-03-31',
    source_reference: 'receipt-q1',
    raw_payload_ref: 'files/receipt-q1.json',
    content_hash: 'hash-receipt-q1',
    source_metadata: {},
    normalization_summary: {},
    publication_summary: {},
    last_error_code: '',
    last_error: '',
    created_by_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    settlement: {
      id: 'settlement-receipt-q1',
      tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      batch_id: '99999999-9999-9999-9999-999999999999',
      status: 'ingested',
      incoming_amount: '125.50',
      outgoing_amount: '0.00',
      open_balance: '125.50',
      summary: {},
      freshness_at: '2026-01-01T00:00:00Z',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    ...overrides,
  }
}

function buildReadinessChecklist({
  status = 'ready',
  readinessBlockers = [],
}: {
  status?: 'ready' | 'not_ready'
  readinessBlockers?: PoolRunReadinessBlocker[]
} = {}): PoolRunReadinessChecklist {
  const blockerCodes = Array.from(new Set(
    readinessBlockers
      .map((item) => (typeof item.code === 'string' ? item.code : null))
      .filter((item): item is string => Boolean(item))
  ))

  return {
    status,
    checks: [
      {
        code: 'master_data_coverage',
        status: 'ready',
        blocker_codes: [],
        blockers: [],
      },
      {
        code: 'organization_party_bindings',
        status: 'ready',
        blocker_codes: [],
        blockers: [],
      },
      {
        code: 'policy_completeness',
        status: status === 'not_ready' ? 'not_ready' : 'ready',
        blocker_codes: status === 'not_ready' ? blockerCodes : [],
        blockers: status === 'not_ready' ? readinessBlockers : [],
      },
      {
        code: 'odata_verify_readiness',
        status: 'ready',
        blocker_codes: [],
        blockers: [],
      },
    ],
  }
}

function buildReport(
  run: PoolRun,
  attemptOverrides: Record<string, unknown> = {}
): PoolRunReport {
  return {
    run,
    publication_attempts: [
      {
        id: '33333333-3333-3333-3333-333333333333',
        run_id: run.id,
        target_database_id: '44444444-4444-4444-4444-444444444444',
        attempt_number: 1,
        attempt_timestamp: '2026-01-01T00:02:00Z',
        status: 'failed',
        entity_name: 'Document_РеализацияТоваровУслуг',
        documents_count: 1,
        publication_identity_strategy: 'guid',
        external_document_identity: 'ref-1',
        posted: false,
        domain_error_code: 'network',
        domain_error_message: 'temporary error',
        ...attemptOverrides,
      },
    ],
    validation_summary: { rows: 5 },
    publication_summary: { total_targets: 3, failed_targets: 1 },
    diagnostics: [{ step: 'distribution_calculation', status: 'ok' }],
    attempts_by_status: { failed: 1 },
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function buildWorkflowBinding(overrides: Record<string, unknown> = {}): PoolWorkflowBinding {
  const workflow = {
    workflow_definition_key: 'services-publication',
    workflow_revision_id: '77777777-7777-7777-7777-777777777777',
    workflow_revision: 3,
    workflow_name: 'services_publication',
    ...(isRecord(overrides.workflow) ? overrides.workflow : {}),
  }
  const decisions = Array.isArray(overrides.decisions)
    ? overrides.decisions
    : [
      {
        decision_table_id: 'decision-1',
        decision_key: 'invoice_mode',
        decision_revision: 2,
      },
    ]
  const parameters = isRecord(overrides.parameters)
    ? overrides.parameters
    : { publication_variant: 'full' }
  const roleMapping = isRecord(overrides.role_mapping)
    ? Object.fromEntries(
      Object.entries(overrides.role_mapping).map(([key, value]) => [key, String(value)])
    )
    : { initiator: 'finance' }
  const bindingProfileId = typeof overrides.binding_profile_id === 'string'
    ? overrides.binding_profile_id
    : 'binding-profile-services'
  const bindingProfileRevisionId = typeof overrides.binding_profile_revision_id === 'string'
    ? overrides.binding_profile_revision_id
    : 'binding-profile-revision-services-v2'
  const bindingProfileRevisionNumber = typeof overrides.binding_profile_revision_number === 'number'
    ? overrides.binding_profile_revision_number
    : 2
  const resolvedProfile = {
    binding_profile_id: bindingProfileId,
    code: 'services-publication',
    name: 'Services Publication',
    status: 'active',
    binding_profile_revision_id: bindingProfileRevisionId,
    binding_profile_revision_number: bindingProfileRevisionNumber,
    workflow,
    decisions,
    parameters,
    role_mapping: roleMapping,
    ...(isRecord(overrides.resolved_profile) ? overrides.resolved_profile : {}),
  }
  return {
    binding_id: 'binding-top-down',
    pool_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    revision: 3,
    binding_profile_id: bindingProfileId,
    binding_profile_revision_id: bindingProfileRevisionId,
    binding_profile_revision_number: bindingProfileRevisionNumber,
    workflow,
    decisions,
    parameters,
    role_mapping: roleMapping,
    selector: {
      direction: 'top_down',
      mode: 'safe',
      tags: [],
    },
    effective_from: '2026-01-01',
    effective_to: null,
    status: 'active',
    resolved_profile: resolvedProfile,
    profile_lifecycle_warning: null,
    ...overrides,
  }
}

function buildWorkflowBindingPreview(overrides: Record<string, unknown> = {}) {
  return {
    workflow_binding: buildWorkflowBinding({
      decisions: [
        {
          decision_table_id: 'decision-1',
          decision_key: 'invoice_mode',
          decision_revision: 2,
        },
      ],
    }),
    compiled_document_policy_slots: {
      invoice_mode: {
        decision_table_id: 'decision-1',
        decision_revision: 2,
        document_policy_source: 'decision_tables',
        document_policy: {
          version: 'document_policy.v1',
          targets: 3,
        },
      },
    },
    compiled_document_policy: {
      version: 'document_policy.v1',
      targets: 3,
    },
    slot_coverage_summary: {
      total_edges: 1,
      counts: {
        resolved: 1,
        missing_selector: 0,
        missing_slot: 0,
        ambiguous_slot: 0,
        ambiguous_context: 0,
        unavailable_context: 0,
      },
      items: [
        {
          edge_id: 'edge-1',
          edge_label: 'Root Org -> Child Org',
          slot_key: 'invoice_mode',
          coverage: {
            code: null,
            status: 'resolved',
            label: 'Resolved',
            detail: 'invoice_mode -> decision-1 r2',
          },
        },
      ],
    },
    runtime_projection: {
      version: 'pool_runtime_projection.v1',
      run_id: 'preview-run',
      pool_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      direction: 'top_down',
      mode: 'safe',
      workflow_definition: {
        plan_key: 'plan-services-v7',
        template_version: 'workflow-template:7',
        workflow_template_name: 'compiled-services-publication',
        workflow_type: 'sequential',
      },
      workflow_binding: {
        binding_mode: 'pool_workflow_binding',
        binding_id: 'binding-top-down',
        binding_profile_id: 'binding-profile-services',
        pool_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        binding_profile_revision_id: 'binding-profile-revision-services-v2',
        binding_profile_revision_number: 2,
        attachment_revision: 3,
        workflow_definition_key: 'services-publication',
        workflow_revision_id: '77777777-7777-7777-7777-777777777777',
        workflow_revision: 3,
        workflow_name: 'services_publication',
        decision_refs: [
          {
            decision_table_id: 'decision-1',
            decision_key: 'invoice_mode',
            decision_revision: 2,
          },
        ],
        selector: {
          direction: 'top_down',
          mode: 'safe',
          tags: [],
        },
        status: 'active',
      },
      document_policy_projection: {
        source_mode: 'decision_tables',
        policy_refs: [
          {
            slot_key: 'invoice_mode',
            edge_ref: {
              parent_node_id: 'node-root',
              child_node_id: 'node-child',
            },
            policy_version: 'document_policy.v1',
            source: 'decision_tables',
          },
        ],
        compiled_document_policy_slots: {
          invoice_mode: {
            decision_table_id: 'decision-1',
            decision_revision: 2,
            document_policy_source: 'decision_tables',
          },
        },
        slot_coverage_summary: {
          total_edges: 1,
          counts: {
            resolved: 1,
            missing_selector: 0,
            missing_slot: 0,
            ambiguous_slot: 0,
            ambiguous_context: 0,
            unavailable_context: 0,
          },
          items: [
            {
              edge_id: 'edge-1',
              edge_label: 'Root Org -> Child Org',
              slot_key: 'invoice_mode',
              coverage: {
                code: null,
                status: 'resolved',
                label: 'Resolved',
                detail: 'invoice_mode -> decision-1 r2',
              },
            },
          ],
        },
        policy_refs_count: 1,
        targets_count: 3,
      },
      artifacts: {
        document_plan_artifact_version: 'document_plan_artifact.v1',
        topology_version_ref: 'topology:v7',
        distribution_artifact_ref: { id: 'distribution-artifact:v7' },
      },
      compile_summary: {
        steps_count: 5,
        atomic_publication_steps_count: 3,
        compiled_targets_count: 3,
      },
    },
    ...overrides,
  }
}

function buildPoolGraph(slotKey = 'invoice_mode') {
  return {
    pool_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    date: '2026-01-01',
    version: 'v1:pool-runs-graph',
    nodes: [
      {
        node_version_id: 'node-root',
        organization_id: '11111111-1111-1111-1111-111111111111',
        inn: '730000000001',
        name: 'Root Org',
        is_root: true,
        metadata: {},
      },
      {
        node_version_id: 'node-child',
        organization_id: '22222222-2222-2222-2222-222222222222',
        inn: '730000000002',
        name: 'Child Org',
        is_root: false,
        metadata: {},
      },
    ],
    edges: [
      {
        edge_version_id: 'edge-1',
        parent_node_version_id: 'node-root',
        child_node_version_id: 'node-child',
        weight: '1',
        min_amount: null,
        max_amount: null,
        metadata: {
          document_policy_key: slotKey,
        },
      },
    ],
  }
}

function renderPage(initialEntry = '/pools/runs', options?: { strict?: boolean }) {
  const tree = (
    <MemoryRouter initialEntries={[initialEntry]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <ConfigProvider theme={{ token: { motion: false } }} wave={{ disabled: true }}>
        <AntApp>
          <PoolRunsPage />
          <LocationProbe />
        </AntApp>
      </ConfigProvider>
    </MemoryRouter>
  )

  return render(options?.strict ? <StrictMode>{tree}</StrictMode> : tree)
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="pool-runs-location">{`${location.pathname}${location.search}`}</div>
}

async function openRunsStage(
  stage: 'Create' | 'Inspect' | 'Safe Actions' | 'Retry Failed'
) {
  fireEvent.click(screen.getByRole('tab', { name: stage }))
}

async function selectOption(testId: string, label: string) {
  const select = await screen.findByTestId(testId)
  if (select instanceof HTMLSelectElement) {
    const option = Array.from(select.options).find((item) => item.text === label)
    expect(option).toBeTruthy()
    fireEvent.change(select, { target: { value: option?.value } })
    return
  }
  const selector = select.querySelector('.ant-select-selector')
  expect(selector).toBeTruthy()
  fireEvent.mouseDown(selector as Element)
  fireEvent.click(await screen.findByText(label))
}

async function userClick(target: Element) {
  await userEvent.setup().click(target)
}

async function openInspectDiagnostics() {
  await openRunsStage('Inspect')
  await userClick(await screen.findByText('Diagnostics JSON (Run Input, Validation, Publication, Step Diagnostics)'))
}

export function setupPoolRunsPageTestSuite() {
  beforeAll(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'pools')
  })

  beforeEach(() => {
    resetQueryClient()
    mockListOrganizationPools.mockReset()
    mockListPoolSchemaTemplates.mockReset()
    mockListPoolBatches.mockReset()
    mockGetPoolGraph.mockReset()
    mockListPoolRuns.mockReset()
    mockGetPoolRunReport.mockReset()
    mockCreatePoolBatch.mockReset()
    mockCreatePoolRun.mockReset()
    mockPreviewPoolWorkflowBinding.mockReset()
    mockRetryPoolRunFailed.mockReset()
    mockConfirmPoolRunPublication.mockReset()
    mockAbortPoolRunPublication.mockReset()

    const run = buildRun()
    mockListOrganizationPools.mockResolvedValue([
      {
        id: run.pool_id,
        code: 'pool-code',
        name: 'Pool name',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        workflow_bindings: [
          buildWorkflowBinding(),
          buildWorkflowBinding({
            binding_id: 'binding-bottom-up',
            workflow: {
              workflow_definition_key: 'bottom-up-import',
              workflow_revision_id: '88888888-8888-8888-8888-888888888888',
              workflow_revision: 5,
              workflow_name: 'bottom_up_import',
            },
            selector: {
              direction: 'bottom_up',
              mode: 'safe',
              tags: [],
            },
          }),
        ],
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockListPoolSchemaTemplates.mockResolvedValue([
      {
        id: '55555555-5555-5555-5555-555555555555',
        tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        code: 'json-template',
        name: 'JSON Template',
        format: 'json',
        is_public: true,
        is_active: true,
        schema: {},
        metadata: {},
        workflow_template_id: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockListPoolBatches.mockResolvedValue([
      buildReceiptBatch(),
    ])
    mockGetPoolGraph.mockResolvedValue({
      pool_id: run.pool_id,
      date: '2026-01-01',
      version: 'v1:pool-runs-graph',
      nodes: [],
      edges: [],
    })
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))
    mockCreatePoolBatch.mockResolvedValue({
      batch: buildReceiptBatch({ run_id: run.id }),
      settlement: buildReceiptBatch({ run_id: run.id }).settlement,
      run: buildRun({
        direction: 'top_down',
        run_input: {
          batch_id: '99999999-9999-9999-9999-999999999999',
          start_organization_id: '11111111-1111-1111-1111-111111111111',
        },
      }),
      created: true,
      sale_closing: null,
    })
    mockCreatePoolRun.mockResolvedValue({ run, created: true })
    mockPreviewPoolWorkflowBinding.mockResolvedValue(buildWorkflowBindingPreview())
    mockRetryPoolRunFailed.mockResolvedValue({
      accepted: true,
      workflow_execution_id: '22222222-2222-2222-2222-222222222222',
      operation_id: null,
      retry_target_summary: {
        requested_targets: 1,
        requested_documents: 1,
        failed_targets: 1,
        enqueued_targets: 1,
        skipped_successful_targets: 0,
      },
    })
    mockConfirmPoolRunPublication.mockResolvedValue({
      run,
      command_type: 'confirm-publication',
      result: 'accepted',
      replayed: false,
    })
    mockAbortPoolRunPublication.mockResolvedValue({
      run,
      command_type: 'abort-publication',
      result: 'accepted',
      replayed: false,
    })
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      const [firstArg] = args
      if (typeof firstArg === 'string' && firstArg.includes('not wrapped in act')) {
        return
      }
    })
  })

  afterEach(() => {
    consoleErrorSpy?.mockRestore()
    consoleErrorSpy = null
  })

  afterAll(async () => {
    await ensureNamespaces('ru', 'pools')
    await changeLanguage('ru')
  })
}

export function registerPoolRunsContextTests() {
  registerPoolRunsContextPrimaryTests()
  registerPoolRunsContextRefreshTests()
}

export function registerPoolRunsOperationsTests() {
  registerPoolRunsOperationsStageTests()
  registerPoolRunsOperationsReadinessTests()
}

export function registerPoolRunsAuthoringTests() {
  registerPoolRunsAuthoringErrorTests()
  registerPoolRunsAuthoringWorkflowTests()
}

function registerPoolRunsContextPrimaryTests() {
  it('deduplicates initial pool reads in StrictMode on the default route', async () => {
    renderPage('/pools/runs', { strict: true })

    await waitFor(() => {
      expect(mockListOrganizationPools).toHaveBeenCalledTimes(1)
      expect(mockGetPoolGraph).toHaveBeenCalledTimes(1)
      expect(mockListPoolRuns).toHaveBeenCalledTimes(1)
      expect(mockGetPoolRunReport).toHaveBeenCalledTimes(1)
    })
  })

  it('renders unified provenance and safe status details', async () => {
    renderPage()

    await openInspectDiagnostics()
    expect(await screen.findByTestId('pool-runs-provenance-workflow-id')).toHaveTextContent(
      '22222222-2222-2222-2222-222222222222'
    )
    expect(screen.getByTestId('pool-runs-provenance-root-operation-id')).toHaveTextContent(
      '22222222-2222-2222-2222-222222222222'
    )
    expect(screen.getByTestId('pool-runs-provenance-execution-consumer')).toHaveTextContent('pools')
    expect(screen.getByTestId('pool-runs-provenance-lane')).toHaveTextContent('workflows')
    expect(screen.getAllByText('awaiting_approval').length).toBeGreaterThan(0)
    expect(screen.getAllByText('workflow_core').length).toBeGreaterThan(0)
    expect(screen.getAllByText('run_input_v1').length).toBeGreaterThan(0)
    expect(screen.getByText(/#1 initial/)).toBeInTheDocument()
    expect((screen.getByTestId('pool-runs-run-input') as HTMLTextAreaElement).value).toContain(
      '"source_payload"'
    )
    await openRunsStage('Safe Actions')
    expect(screen.getByTestId('pool-runs-safe-confirm')).toBeEnabled()
    expect(screen.getByTestId('pool-runs-safe-abort')).toBeEnabled()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('shows run lineage as primary operator context and keeps workflow diagnostics secondary', async () => {
    mockGetPoolGraph.mockResolvedValueOnce(buildPoolGraph('unexpected_slot'))
    const workflowBinding = buildWorkflowBinding({
      revision: 7,
      selector: {
        direction: 'top_down',
        mode: 'safe',
        tags: ['quarter-close'],
      },
      workflow: {
        workflow_definition_key: 'services-publication',
        workflow_revision_id: '77777777-7777-7777-7777-777777777777',
        workflow_revision: 7,
        workflow_name: 'services_publication',
      },
      resolved_profile: {
        binding_profile_id: 'binding-profile-services',
        code: 'services-publication',
        name: 'Services Publication',
        status: 'active',
        binding_profile_revision_id: 'binding-profile-revision-services-v7',
        binding_profile_revision_number: 7,
        workflow: {
          workflow_definition_key: 'services-publication',
          workflow_revision_id: '77777777-7777-7777-7777-777777777777',
          workflow_revision: 7,
          workflow_name: 'services_publication',
        },
        decisions: [
          {
            decision_table_id: 'decision-1',
            decision_key: 'invoice_mode',
            decision_revision: 2,
          },
        ],
        parameters: {
          publication_variant: 'full',
        },
        role_mapping: {
          initiator: 'finance',
        },
      },
      binding_profile_revision_id: 'binding-profile-revision-services-v7',
      binding_profile_revision_number: 7,
    })
    const run = {
      ...buildRun({
        direction: 'top_down',
      }),
      workflow_binding: workflowBinding,
      runtime_projection: {
        version: 'pool_runtime_projection.v1',
        run_id: '11111111-1111-1111-1111-111111111111',
        pool_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        direction: 'top_down',
        mode: 'safe',
        workflow_definition: {
          plan_key: 'plan-services-v7',
          template_version: 'workflow-template:7',
          workflow_template_name: 'compiled-services-publication',
          workflow_type: 'sequential',
        },
        workflow_binding: {
          binding_mode: 'pool_workflow_binding',
          binding_id: 'binding-top-down',
          binding_profile_id: 'binding-profile-services',
          pool_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
          binding_profile_revision_id: 'binding-profile-revision-services-v7',
          binding_profile_revision_number: 7,
          attachment_revision: 7,
          workflow_definition_key: 'services-publication',
          workflow_revision_id: '77777777-7777-7777-7777-777777777777',
          workflow_revision: 7,
          workflow_name: 'services_publication',
          decision_refs: [
            {
              decision_table_id: 'decision-1',
              decision_key: 'invoice_mode',
              decision_revision: 2,
            },
          ],
          selector: {
            direction: 'top_down',
            mode: 'safe',
            tags: ['quarter-close'],
          },
          status: 'active',
        },
        document_policy_projection: {
          source_mode: 'document_plan_artifact',
          policy_refs: [
            {
              slot_key: 'invoice_mode',
              edge_ref: {
                parent_node_id: 'node-root',
                child_node_id: 'node-child',
              },
              policy_version: 'document_policy.v1',
              source: 'decision_tables',
            },
          ],
          compiled_document_policy_slots: {
            invoice_mode: {
              decision_table_id: 'decision-1',
              decision_revision: 2,
              document_policy_source: 'decision_tables',
              document_policy: {
                version: 'document_policy.v1',
                targets: 3,
              },
            },
          },
          slot_coverage_summary: {
            total_edges: 1,
            counts: {
              resolved: 1,
              missing_selector: 0,
              missing_slot: 0,
              ambiguous_slot: 0,
              ambiguous_context: 0,
              unavailable_context: 0,
            },
            items: [
              {
                edge_id: 'edge-1',
                edge_label: 'Root Org -> Child Org',
                slot_key: 'invoice_mode',
                coverage: {
                  code: null,
                  status: 'resolved',
                  label: 'Resolved',
                  detail: 'invoice_mode -> decision-1 r2',
                },
              },
            ],
          },
          policy_refs_count: 1,
          targets_count: 3,
        },
        artifacts: {
          document_plan_artifact_version: 'document_plan_artifact.v1',
          topology_version_ref: 'topology:v7',
          distribution_artifact_ref: {
            id: 'distribution-artifact:v7',
          },
        },
        compile_summary: {
          steps_count: 5,
          atomic_publication_steps_count: 3,
          compiled_targets_count: 3,
        },
      },
    } as PoolRun
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))

    renderPage()

    await openRunsStage('Inspect')
    expect(await screen.findByText('Run Lineage')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-lineage-pool')).toHaveTextContent('pool-code')
    expect(screen.getByTestId('pool-runs-lineage-binding-id')).toHaveTextContent('binding-top-down')
    expect(screen.getByTestId('pool-runs-lineage-attachment-revision')).toHaveTextContent('r7')
    expect(screen.getByTestId('pool-runs-lineage-profile')).toHaveTextContent('services-publication')
    expect(screen.getByTestId('pool-runs-lineage-profile-revision')).toHaveTextContent('r7')
    expect(screen.getByTestId('pool-runs-lineage-workflow')).toHaveTextContent('services_publication')
    expect(screen.getByText('invoice_mode r2')).toBeInTheDocument()
    expect(screen.getByText('compiled targets: 3')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-lineage-slot-coverage')).toHaveTextContent('resolved: 1')
    expect(screen.getByText('All topology edges are covered by the persisted run lineage binding.')).toBeInTheDocument()
    expect((screen.getByTestId('pool-runs-lineage-slot-projection') as HTMLTextAreaElement).value).toContain(
      '"invoice_mode"'
    )
    const diagnosticsButton = screen.getByRole('button', { name: 'Open Workflow Diagnostics' })
    await userClick(diagnosticsButton)
    expect(screen.getByTestId('pool-runs-location')).toHaveTextContent(
      '/workflows/executions/22222222-2222-2222-2222-222222222222'
    )
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('restores selected run and stage from query params', async () => {
    const run = buildRun()
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))

    renderPage(`/pools/runs?pool=${run.pool_id}&run=${run.id}&stage=safe&detail=1`)

    const confirmButton = await screen.findByTestId('pool-runs-safe-confirm')
    expect(confirmButton).toBeEnabled()
    expect(screen.getByRole('tab', { name: 'Safe Actions' })).toHaveAttribute('aria-selected', 'true')

    await waitFor(() => {
      const location = screen.getByTestId('pool-runs-location').textContent || ''
      expect(location).toContain(`pool=${run.pool_id}`)
      expect(location).toContain(`run=${run.id}`)
      expect(location).toContain('stage=safe')
      expect(location).toContain('detail=1')
    })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('renders inspect lineage before the delayed run report snapshot resolves', async () => {
    const run = buildRun({
      workflow_binding: buildWorkflowBinding({
        binding_id: 'binding-top-down',
        attachment_revision: 5,
      }),
    })
    const pendingReport = deferred<PoolRunReport>()

    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockReturnValue(pendingReport.promise)

    renderPage(`/pools/runs?pool=${run.pool_id}&run=${run.id}&stage=inspect&detail=1`)

    expect(await screen.findByText('Run Lineage')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-lineage-binding-id')).toHaveTextContent('binding-top-down')
    expect(
      screen.getByText('Run lineage, readiness, and runtime context are already available. Publication attempts and diagnostics JSON will appear when report loading finishes.')
    ).toBeInTheDocument()

    pendingReport.resolve(buildReport(run))

    expect(await screen.findByText('Publication Attempts')).toBeInTheDocument()
    expect(screen.getByText('attempts: 1')).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('keeps selected run and active stage in the URL when the operator switches lifecycle stages', async () => {
    const firstRun = buildRun()
    const secondRun = buildRun({
      id: 'aaaaaaaa-1111-1111-1111-111111111111',
      workflow_execution_id: 'bbbbbbbb-2222-2222-2222-222222222222',
      root_operation_id: 'bbbbbbbb-2222-2222-2222-222222222222',
      provenance: {
        ...firstRun.provenance,
        workflow_run_id: 'bbbbbbbb-2222-2222-2222-222222222222',
        root_operation_id: 'bbbbbbbb-2222-2222-2222-222222222222',
        retry_chain: [
          {
            workflow_run_id: 'bbbbbbbb-2222-2222-2222-222222222222',
            parent_workflow_run_id: null,
            attempt_number: 1,
            attempt_kind: 'initial',
            status: 'pending',
          },
        ],
      },
    })

    mockListPoolRuns.mockResolvedValue([firstRun, secondRun])
    mockGetPoolRunReport.mockImplementation(async (runId: string) => buildReport(runId === secondRun.id ? secondRun : firstRun))

    renderPage()

    fireEvent.click(await screen.findByRole('tab', { name: 'Retry Failed' }))

    await waitFor(() => {
      const location = screen.getByTestId('pool-runs-location').textContent || ''
      expect(location).toContain(`pool=${firstRun.pool_id}`)
      expect(location).toContain(`run=${firstRun.id}`)
      expect(location).toContain('stage=retry')
      expect(location).toContain('detail=1')
    })

    fireEvent.click(screen.getByRole('tab', { name: 'Inspect' }))
    await userClick(await screen.findByRole('button', { name: `Open run ${secondRun.id}` }))

    await waitFor(() => {
      const location = screen.getByTestId('pool-runs-location').textContent || ''
      expect(location).toContain(`run=${secondRun.id}`)
      expect(location).toContain('stage=inspect')
      expect(location).toContain('detail=1')
    })

    fireEvent.click(screen.getByRole('tab', { name: 'Retry Failed' }))

    await waitFor(() => {
      const location = screen.getByTestId('pool-runs-location').textContent || ''
      expect(location).toContain(`run=${secondRun.id}`)
      expect(location).toContain('stage=retry')
      expect(location).toContain('detail=1')
    })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)
}

function registerPoolRunsOperationsStageTests() {
  it('disables confirm while safe run is in pre-publish preparing state', async () => {
    const preparingRun = buildRun({
      status_reason: 'preparing',
      approval_state: 'preparing',
      publication_step_state: 'not_enqueued',
      publication_confirmed_at: null,
    })
    mockListPoolRuns.mockResolvedValue([preparingRun])
    mockGetPoolRunReport.mockResolvedValue(buildReport(preparingRun))

    renderPage()

    await openRunsStage('Safe Actions')
    expect(await screen.findByText('Pre-publish is still running')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-safe-confirm')).toBeDisabled()
    expect(screen.getByTestId('pool-runs-safe-abort')).toBeEnabled()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('keeps factual monitoring controls out of the run-local execution canvas', async () => {
    renderPage('/pools/runs?pool=bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb&run=11111111-1111-1111-1111-111111111111&stage=inspect&detail=1')

    await screen.findByText('Factual monitoring lives in a separate workspace')

    expect(screen.getByRole('button', { name: 'Open factual workspace' })).toBeInTheDocument()
    expect(screen.queryByText('Quarter summary')).not.toBeInTheDocument()
    expect(screen.queryByText('Batch settlement')).not.toBeInTheDocument()
    expect(screen.queryByText('Manual review queue')).not.toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('sends confirm-publication with generated idempotency key', async () => {
    renderPage()

    await openRunsStage('Safe Actions')
    const confirmButton = await screen.findByTestId('pool-runs-safe-confirm')
    await waitFor(() => expect(confirmButton).toBeEnabled())
    await userClick(confirmButton)

    await waitFor(() => expect(mockConfirmPoolRunPublication).toHaveBeenCalledTimes(1))
    expect(mockConfirmPoolRunPublication).toHaveBeenCalledWith(
      '11111111-1111-1111-1111-111111111111',
      expect.any(String)
    )
    const generatedKey = mockConfirmPoolRunPublication.mock.calls[0][1] as string
    expect(generatedKey.length).toBeGreaterThan(8)
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)
}

function registerPoolRunsAuthoringErrorTests() {
  it('maps create-run problem+json VALIDATION_ERROR to form field and user-facing message', async () => {
    mockCreatePoolRun.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Validation Error',
          status: 400,
          detail: 'top_down starting_amount must be greater than 0.',
          code: 'VALIDATION_ERROR',
        },
      },
    })

    renderPage()

    const submitButton = await screen.findByTestId('pool-runs-create-submit')
    await userClick(submitButton)

    await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('Check the run parameters and try again.')).toBeInTheDocument()
    expect(await screen.findByText('top_down starting_amount must be greater than 0.')).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('maps create-run topology alias errors to a localized message', async () => {
    mockCreatePoolRun.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Pool Runtime Configuration Error',
          status: 400,
          detail: 'Malformed topology-aware alias in document policy.',
          code: 'POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID',
        },
      },
    })

    renderPage()

    const submitButton = await screen.findByTestId('pool-runs-create-submit')
    await userClick(submitButton)

    await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
    expect(
      await screen.findByText(
        'Fix the topology-aware alias in document policy: the malformed alias blocks compile before publication.'
      )
    ).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('shows raw validation detail when create-run VALIDATION_ERROR is not mapped to a specific field', async () => {
    mockCreatePoolRun.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Validation Error',
          status: 400,
          detail: '“wf-top-down-execution-v1” is not a valid UUID.',
          code: 'VALIDATION_ERROR',
        },
      },
    })

    renderPage()

    const submitButton = await screen.findByTestId('pool-runs-create-submit')
    await userClick(submitButton)

    await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('“wf-top-down-execution-v1” is not a valid UUID.')).toBeInTheDocument()
    expect(screen.queryByText('Check the run parameters and try again.')).not.toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('maps missing binding create-run error to workflow binding field and localized message', async () => {
    mockCreatePoolRun.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Pool Workflow Binding Required',
          status: 400,
          detail: 'pool_workflow_binding_id is required.',
          code: 'POOL_WORKFLOW_BINDING_REQUIRED',
        },
      },
    })

    renderPage()

    await openRunsStage('Create')
    const submitButton = await screen.findByTestId('pool-runs-create-submit')
    await userClick(submitButton)

    await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
    expect(await screen.findAllByText('Select a workflow binding before proceeding.')).toHaveLength(2)
    expect(screen.queryByText('pool_workflow_binding_id is required.')).not.toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('maps missing binding preview error to workflow binding field and localized message', async () => {
    mockPreviewPoolWorkflowBinding.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Pool Workflow Binding Required',
          status: 400,
          detail: 'pool_workflow_binding_id is required.',
          code: 'POOL_WORKFLOW_BINDING_REQUIRED',
        },
      },
    })

    renderPage()

    await openRunsStage('Create')
    await userClick(await screen.findByTestId('pool-runs-create-preview'))

    await waitFor(() => expect(mockPreviewPoolWorkflowBinding).toHaveBeenCalledTimes(1))
    expect(await screen.findAllByText('Select a workflow binding before proceeding.')).toHaveLength(2)
    expect(screen.queryByText('pool_workflow_binding_id is required.')).not.toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it.each([
    [
      'ODATA_MAPPING_NOT_CONFIGURED',
      'OData Infobase Users are not configured for the target databases. Check /rbac → Infobase Users.',
    ],
    [
      'ODATA_MAPPING_AMBIGUOUS',
      'Ambiguous OData Infobase Users mappings were found. Fix the duplicates in /rbac → Infobase Users.',
    ],
    [
      'ODATA_PUBLICATION_AUTH_CONTEXT_INVALID',
      'The publication auth context is invalid. Check the run and the /rbac → Infobase Users settings.',
    ],
  ])(
    'maps create-run problem+json %s to publication mapping message',
    async (errorCode: string, expectedMessage: string) => {
      mockCreatePoolRun.mockRejectedValueOnce({
        response: {
          data: {
            type: 'about:blank',
            title: 'Pool Runtime Configuration Error',
            status: 400,
            detail: 'Configure Infobase Users in /rbac.',
            code: errorCode,
          },
        },
      })

      renderPage()

      const submitButton = await screen.findByTestId('pool-runs-create-submit')
      await userClick(submitButton)

      await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
      expect(await screen.findByText(expectedMessage)).toBeInTheDocument()
    },
    15000
  )

  it('renders explicit actor mapping remediation when backend detail includes actor_username and target database ids', async () => {
    mockCreatePoolRun.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Pool Runtime Configuration Error',
          status: 400,
          detail: (
            'Actor infobase mapping is not configured for publication auth context: '
            + 'actor_username=admin; target_database_ids=db-1. Configure Infobase Users in /rbac.'
          ),
          code: 'ODATA_MAPPING_NOT_CONFIGURED',
        },
      },
    })

    renderPage()

    const submitButton = await screen.findByTestId('pool-runs-create-submit')
    await userClick(submitButton)

    await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
    expect(
      await screen.findByText(
        'No actor OData Infobase User is configured for admin on target database db-1. Check /rbac → Infobase Users.'
      )
    ).toBeInTheDocument()
  })
}

function registerPoolRunsOperationsReadinessTests() {
  it('sends abort-publication with generated idempotency key', async () => {
    renderPage()

    await openRunsStage('Safe Actions')
    const abortButton = await screen.findByTestId('pool-runs-safe-abort')
    await waitFor(() => expect(abortButton).toBeEnabled())
    await userClick(abortButton)

    await waitFor(() => expect(mockAbortPoolRunPublication).toHaveBeenCalledTimes(1))
    expect(mockAbortPoolRunPublication).toHaveBeenCalledWith(
      '11111111-1111-1111-1111-111111111111',
      expect.any(String)
    )
    const generatedKey = mockAbortPoolRunPublication.mock.calls[0][1] as string
    expect(generatedKey.length).toBeGreaterThan(8)
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('sends retry-failed payload with parsed documents and generated idempotency key', async () => {
    renderPage()

    await openRunsStage('Retry Failed')
    const retryButton = await screen.findByRole('button', { name: 'Retry Failed' })
    await waitFor(() => expect(retryButton).toBeEnabled())
    await userClick(retryButton)

    await waitFor(() => expect(mockRetryPoolRunFailed).toHaveBeenCalledTimes(1))
    expect(mockRetryPoolRunFailed).toHaveBeenCalledWith(
      '11111111-1111-1111-1111-111111111111',
      {
        entity_name: 'Document_РеализацияТоваровУслуг',
        max_attempts: 5,
        retry_interval_seconds: 0,
        documents_by_database: {
          '<database_id>': [{ Amount: '100.00' }],
        },
      },
      expect.any(String)
    )
    const generatedKey = mockRetryPoolRunFailed.mock.calls[0][2] as string
    expect(generatedKey.length).toBeGreaterThan(8)
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('renders legacy run with canonical diagnostics payload fields', async () => {
    const legacyRun = buildRun({
      mode: 'unsafe',
      run_input: null,
      input_contract_version: 'legacy_pre_run_input',
      workflow_execution_id: null,
      workflow_status: null,
      root_operation_id: null,
      execution_consumer: null,
      lane: null,
      execution_backend: 'legacy_pool_runtime',
      provenance: {
        workflow_run_id: null,
        workflow_status: null,
        execution_backend: 'legacy_pool_runtime',
        root_operation_id: null,
        execution_consumer: null,
        lane: null,
        retry_chain: [],
      },
    })
    mockListPoolRuns.mockResolvedValue([legacyRun])
    mockGetPoolRunReport.mockResolvedValue(
      buildReport(legacyRun, {
        domain_error_message: 'canonical legacy message',
      })
    )

    renderPage()

    await openInspectDiagnostics()
    expect(await screen.findByTestId('pool-runs-provenance-workflow-id')).toHaveTextContent('-')
    expect(screen.getByTestId('pool-runs-provenance-root-operation-id')).toHaveTextContent('-')
    expect(screen.getByTestId('pool-runs-provenance-execution-consumer')).toHaveTextContent('-')
    expect(screen.getByTestId('pool-runs-provenance-lane')).toHaveTextContent('-')
    expect(screen.getAllByText('legacy').length).toBeGreaterThan(0)
    expect(screen.getAllByText('legacy_pre_run_input').length).toBeGreaterThan(0)
    expect(screen.getByTestId('pool-runs-run-input')).toHaveValue('null')
    expect(screen.getByText('canonical legacy message')).toBeInTheDocument()
  })

  it('shows remediation hint for publication mapping errors in attempts table', async () => {
    const run = buildRun()
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(
      buildReport(run, {
        domain_error_code: 'ODATA_MAPPING_NOT_CONFIGURED',
        domain_error_message: 'mapping missing',
      })
    )

    renderPage()

    await openRunsStage('Inspect')
    expect(await screen.findByText('ODATA_MAPPING_NOT_CONFIGURED')).toBeInTheDocument()
    expect(screen.getByText('Remediation: /rbac - Infobase Users')).toBeInTheDocument()
  })

  it('renders master data gate remediation hint and diagnostic context', async () => {
    const run = buildRun({
      master_data_gate: {
        status: 'failed',
        mode: 'resolve_upsert',
        targets_count: 2,
        bindings_count: 1,
        error_code: 'MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING',
        detail: 'Bindings are missing for some organizations.',
        diagnostic: {
          entity_type: 'organization',
          canonical_id: 'party-1',
          target_database_id: 'db-1',
          missing_organization_bindings: [
            {
              organization_id: 'org-1',
              name: 'Org One',
              database_id: 'db-1',
            },
          ],
        },
      },
    })
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))

    renderPage()

    await openRunsStage('Inspect')
    expect(await screen.findByText('status: failed')).toBeInTheDocument()
    expect(screen.getByText('mode: resolve_upsert')).toBeInTheDocument()
    expect(screen.getByText('targets: 2')).toBeInTheDocument()
    expect(screen.getByText('bindings: 1')).toBeInTheDocument()
    expect(screen.getByText('MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING')).toBeInTheDocument()
    expect(screen.getByText('Bindings are missing for some organizations.')).toBeInTheDocument()
    expect(screen.getByText('Remediation Hint')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Backfill Organization->Party and clear the remediation list before rerunning the run.'
      )
    ).toBeInTheDocument()
    expect(screen.getByText('Diagnostic Context')).toBeInTheDocument()
    expect(
      screen.getByText('entity_type=organization canonical_id=party-1 target_database_id=db-1')
    ).toBeInTheDocument()
    expect(screen.getByText('missing_organization_bindings=1')).toBeInTheDocument()
    expect(screen.getByText('#1: org=org-1 name=Org One database_id=db-1')).toBeInTheDocument()
  })

  it('renders historical master data gate placeholder when gate payload is missing', async () => {
    const run = buildRun({ master_data_gate: null })
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))

    renderPage()

    await openRunsStage('Inspect')
    expect(
      await screen.findByText('Historical run or gate step was not captured in this execution context.')
    ).toBeInTheDocument()
  })

  it('renders readiness blockers and verification mismatch summary', async () => {
    const readinessBlockers: PoolRunReadinessBlocker[] = [
      {
        code: 'POOL_DOCUMENT_POLICY_MAPPING_INVALID',
        detail: 'Document policy is incomplete for minimal_documents_full_payload.',
        entity_name: 'Document_Sales',
        field_or_table_path: 'Goods',
      },
    ]
    const run = buildRun({
      readiness_blockers: readinessBlockers,
      readiness_checklist: buildReadinessChecklist({
        status: 'not_ready',
        readinessBlockers,
      }),
      verification_status: 'failed',
      verification_summary: {
        checked_targets: 1,
        verified_documents: 1,
        mismatches_count: 1,
        mismatches: [
          {
            database_id: '44444444-4444-4444-4444-444444444444',
            entity_name: 'Document_Sales',
            document_idempotency_key: 'sales-doc-1',
            field_or_table_path: 'Goods',
            kind: 'missing_table_part',
          },
        ],
      },
    })
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))

    renderPage()

    await openRunsStage('Inspect')
    expect(await screen.findByText('Readiness Checklist')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-readiness-status')).toHaveTextContent('status: not_ready')
    expect(screen.getByText('POOL_DOCUMENT_POLICY_MAPPING_INVALID')).toBeInTheDocument()
    expect(screen.getByText('entity=Document_Sales path=Goods')).toBeInTheDocument()
    expect(screen.getByText('Policy completeness')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Complete the document policy: required fields and table parts must exist in the completeness profile and mapping.'
      )
    ).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-verification-status')).toHaveTextContent('status: failed')
    expect(screen.getByText('targets: 1')).toBeInTheDocument()
    expect(screen.getByText('documents: 1')).toBeInTheDocument()
    expect(screen.getByText('mismatches: 1')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Mismatches (1)'))
    expect(screen.getByText('sales-doc-1')).toBeInTheDocument()
    expect(screen.getByText('missing_table_part')).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('renders remediation transitions for master-data readiness blockers', async () => {
    const bindingBlocker: PoolRunReadinessBlocker = {
      code: 'MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING',
      detail: 'Bindings are missing for some organizations.',
      diagnostic: {
        entity_type: 'organization',
        canonical_id: 'party-1',
        target_database_id: 'db-1',
      },
    }
    const canonicalBlocker: PoolRunReadinessBlocker = {
      code: 'MASTER_DATA_ENTITY_NOT_FOUND',
      detail: 'Canonical item is missing.',
      diagnostic: {
        entity_type: 'item',
        canonical_id: 'item-missing',
        target_database_id: 'db-2',
      },
    }
    const run = buildRun({
      readiness_blockers: [bindingBlocker, canonicalBlocker],
      readiness_checklist: {
        status: 'not_ready',
        checks: [
          {
            code: 'master_data_coverage',
            status: 'not_ready',
            blocker_codes: ['MASTER_DATA_ENTITY_NOT_FOUND'],
            blockers: [canonicalBlocker],
          },
          {
            code: 'organization_party_bindings',
            status: 'not_ready',
            blocker_codes: ['MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING'],
            blockers: [bindingBlocker],
          },
          {
            code: 'policy_completeness',
            status: 'ready',
            blocker_codes: [],
            blockers: [],
          },
          {
            code: 'odata_verify_readiness',
            status: 'ready',
            blocker_codes: [],
            blockers: [],
          },
        ],
      },
    })
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))

    renderPage()

    await openRunsStage('Inspect')
    const bindingsLink = await screen.findByRole('button', { name: 'Open Bindings workspace' }, { timeout: 10000 })
    await userClick(bindingsLink)
    await waitFor(() => {
      expect(screen.getByTestId('pool-runs-location')).toHaveTextContent(
        '/pools/master-data?tab=bindings&entityType=party&canonicalId=party-1&databaseId=db-1&role=organization'
      )
    })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('routes unresolved dedupe blocker to the Dedupe Review workspace', async () => {
    const dedupeBlocker = {
      code: 'MASTER_DATA_DEDUPE_REVIEW_REQUIRED',
      detail: 'Canonical party is blocked by unresolved cross-infobase dedupe review.',
      diagnostic: {
        entity_type: 'party',
        canonical_id: 'party-1',
        target_database_id: 'db-1',
        dedupe_cluster_id: 'cluster-review-1',
        dedupe_review_item_id: 'review-1',
      },
    } as PoolRunReadinessBlocker
    const run = buildRun({
      readiness_blockers: [dedupeBlocker],
      readiness_checklist: buildReadinessChecklist({
        status: 'not_ready',
        readinessBlockers: [dedupeBlocker],
      }),
    })
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))

    renderPage()

    await openRunsStage('Inspect')
    const reviewLink = await screen.findByRole('button', { name: 'Open Dedupe Review' }, { timeout: 10000 })
    await userClick(reviewLink)
    await waitFor(() => {
      expect(screen.getByTestId('pool-runs-location')).toHaveTextContent(
        '/pools/master-data?tab=dedupe-review&entityType=party&canonicalId=party-1&databaseId=db-1&clusterId=cluster-review-1&reviewItemId=review-1'
      )
    })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('renders topology-aware readiness blockers with edge context and remediation routing', async () => {
    const roleMissingBlocker = {
      code: 'MASTER_DATA_PARTY_ROLE_MISSING',
      detail: 'Bound master party is missing the required counterparty role.',
      edge_ref: {
        parent_node_id: 'parent-node',
        child_node_id: 'child-node',
      },
      participant_side: 'child',
      required_role: 'counterparty',
      diagnostic: {
        entity_type: 'party',
        canonical_id: 'party-child',
        target_database_id: 'db-1',
      },
    } as PoolRunReadinessBlocker
    const topologyAliasBlocker = {
      code: 'POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID',
      detail: 'Malformed topology-aware alias in document policy.',
      edge_ref: {
        parent_node_id: 'parent-node',
        child_node_id: 'child-node',
      },
      participant_side: 'parent',
      required_role: 'organization',
      field_or_table_path: 'field_mapping.party',
    } as PoolRunReadinessBlocker
    const run = buildRun({
      readiness_blockers: [roleMissingBlocker, topologyAliasBlocker],
      readiness_checklist: undefined,
    })
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))

    renderPage()

    await openRunsStage('Inspect')
    expect(await screen.findByText('Organization->Party bindings')).toBeInTheDocument()
    expect(screen.getByText('Policy completeness')).toBeInTheDocument()
    expect(screen.getByText('MASTER_DATA_PARTY_ROLE_MISSING')).toBeInTheDocument()
    expect(screen.getByText('POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID')).toBeInTheDocument()
    expect(
      screen.getAllByText('edge_ref=parent_node_id=parent-node child_node_id=child-node')
    ).toHaveLength(2)
    expect(screen.getByText('participant_side=child')).toBeInTheDocument()
    expect(screen.getByText('required_role=counterparty')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Fix the topology-aware alias in document policy: only parent/child participant aliases are allowed.'
      )
    ).toBeInTheDocument()

    await userClick(screen.getByRole('button', { name: 'Open Bindings workspace' }))
    await waitFor(() => {
      expect(screen.getByTestId('pool-runs-location')).toHaveTextContent('role=counterparty')
    })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('disables confirm when readiness blockers are present', async () => {
    const readinessBlockers: PoolRunReadinessBlocker[] = [
      {
        code: 'POOL_DOCUMENT_POLICY_MAPPING_INVALID',
        detail: 'Document policy is incomplete for minimal_documents_full_payload.',
      },
    ]
    const run = buildRun({
      readiness_blockers: readinessBlockers,
      readiness_checklist: buildReadinessChecklist({
        status: 'not_ready',
        readinessBlockers,
      }),
    })
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))

    renderPage()

    await openRunsStage('Safe Actions')
    expect(await screen.findByText('Readiness blockers detected')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-safe-confirm')).toBeDisabled()
  })

  it('renders machine-readable readiness checklist for ready safe run', async () => {
    const run = buildRun({
      readiness_blockers: [],
      readiness_checklist: buildReadinessChecklist({ status: 'ready' }),
    })
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))

    renderPage()

    await openRunsStage('Inspect')
    expect(await screen.findByText('Readiness Checklist')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-readiness-status')).toHaveTextContent('status: ready')
    expect(screen.getByText('Master data coverage')).toBeInTheDocument()
    expect(screen.getByText('Organization->Party bindings')).toBeInTheDocument()
    expect(screen.getByText('Policy completeness')).toBeInTheDocument()
    expect(screen.getByText('OData verify readiness')).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('maps readiness Problem Details from confirm-publication to blocker-specific message', async () => {
    mockConfirmPoolRunPublication.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Pool Run Readiness Blocked',
          status: 409,
          detail: 'Resolve readiness blockers before confirm-publication.',
          code: 'POOL_RUN_READINESS_BLOCKED',
          errors: [
            {
              code: 'POOL_DOCUMENT_POLICY_MAPPING_INVALID',
              detail: 'Document policy is incomplete for minimal_documents_full_payload.',
            },
          ],
        },
      },
    })

    renderPage()

    await openRunsStage('Safe Actions')
    const confirmButton = await screen.findByTestId('pool-runs-safe-confirm')
    await waitFor(() => expect(confirmButton).toBeEnabled())
    await userClick(confirmButton)

    await waitFor(() => expect(mockConfirmPoolRunPublication).toHaveBeenCalledTimes(1))
    expect(
      await screen.findByText(
        'Document policy is incomplete for minimal_documents_full_payload. (POOL_DOCUMENT_POLICY_MAPPING_INVALID)'
      )
    ).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)
}

function registerPoolRunsAuthoringWorkflowTests() {
  it('renders publication credentials source hint in create run form', async () => {
    renderPage()

    await openRunsStage('Create')
    expect(await screen.findByText('Pool publication OData credentials source: /rbac')).toBeInTheDocument()
    expect(
      screen.getByText(
        '`odata_url` is loaded from Databases, and the OData user/password for publication are taken from /rbac → Infobase Users (actor/service mapping).'
      )
    ).toBeInTheDocument()
  })

  it('shows ambiguous binding context before preview until operator selects a binding', async () => {
    const run = buildRun()
    mockListOrganizationPools.mockResolvedValue([
      {
        id: run.pool_id,
        code: 'pool-code',
        name: 'Pool name',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        workflow_bindings: [
          buildWorkflowBinding({
            decisions: [
              {
                decision_table_id: 'decision-1',
                decision_key: 'invoice_mode',
                decision_revision: 2,
              },
            ],
          }),
          buildWorkflowBinding({
            binding_id: 'binding-top-down-alt',
            workflow: {
              workflow_definition_key: 'services-publication-alt',
              workflow_revision_id: '99999999-9999-9999-9999-999999999999',
              workflow_revision: 4,
              workflow_name: 'services_publication_alt',
            },
            decisions: [
              {
                decision_table_id: 'decision-2',
                decision_key: 'invoice_mode',
                decision_revision: 5,
              },
            ],
          }),
        ],
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockGetPoolGraph.mockResolvedValue(buildPoolGraph())

    renderPage()

    await openRunsStage('Create')
    expect(await screen.findByTestId('pool-runs-create-binding-ambiguity')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-create-preview')).toBeDisabled()

    const bindingSelect = screen.getByTestId('pool-runs-create-workflow-binding')
    const bindingSelector = bindingSelect.querySelector('.ant-select-selector')
    expect(bindingSelector).toBeTruthy()
    fireEvent.mouseDown(bindingSelector as Element)
    await userClick(await screen.findByText(/services_publication_alt/i))

    await waitFor(() => {
      expect(screen.queryByTestId('pool-runs-create-binding-ambiguity')).not.toBeInTheDocument()
    })
    expect(screen.getByTestId('pool-runs-create-selected-binding')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-create-attachment-revision')).toHaveTextContent('r3')
    expect(screen.getByTestId('pool-runs-create-profile-revision')).toHaveTextContent('r2')
    expect(screen.getByTestId('pool-runs-create-binding-coverage')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-create-slot-coverage-summary')).toHaveTextContent('edges: 1')
    expect(screen.getByTestId('pool-runs-create-slot-coverage-summary')).toHaveTextContent('resolved: 1')
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('surfaces blocking workflow binding read diagnostics instead of generic empty binding state', async () => {
    mockListOrganizationPools.mockResolvedValue([
      {
        id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        code: 'pool-code',
        name: 'Pool name',
        description: 'Main pool',
        is_active: true,
        metadata: {
          workflow_bindings_read_error: {
            code: 'POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING',
            detail: "Workflow binding 'binding-top-down' is missing binding_profile references.",
          },
        },
        workflow_bindings: [],
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])

    renderPage()

    await openRunsStage('Create')
    expect(await screen.findByTestId('pool-runs-create-binding-read-error')).toHaveTextContent(
      'POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING'
    )
    expect(screen.getByTestId('pool-runs-create-binding-read-error')).toHaveTextContent(
      "Workflow binding 'binding-top-down' is missing binding_profile references."
    )
    expect(screen.getByTestId('pool-runs-create-workflow-binding')).toHaveAttribute('aria-disabled', 'true')
    expect(screen.queryByText('No matching binding')).not.toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('submits top_down create-run payload with run_input and without source_hash', async () => {
    renderPage()

    await openRunsStage('Create')
    const submitButton = await screen.findByTestId('pool-runs-create-submit')
    await userClick(submitButton)

    await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
    const payload = mockCreatePoolRun.mock.calls[0][0] as Record<string, unknown>
    expect(payload.direction).toBe('top_down')
    expect(payload.pool_workflow_binding_id).toBe('binding-top-down')
    expect(payload.run_input).toEqual({ starting_amount: '100.00' })
    expect(payload).not.toHaveProperty('source_hash')
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('preserves a user-entered starting amount in top_down create-run payload', async () => {
    renderPage()

    await openRunsStage('Create')
    const startingAmountInput = await screen.findByRole('spinbutton', { name: /starting amount/i })
    fireEvent.change(startingAmountInput, { target: { value: '55555.55' } })

    await userClick(screen.getByTestId('pool-runs-create-submit'))

    await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
    const payload = mockCreatePoolRun.mock.calls[0][0] as Record<string, unknown>
    expect(payload.run_input).toEqual({ starting_amount: '55555.55' })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('submits batch-backed top_down create-run payload with explicit batch and start organization', async () => {
    mockGetPoolGraph.mockResolvedValueOnce(buildPoolGraph())
    renderPage()

    await openRunsStage('Create')
    await userClick(await screen.findByText('receipt batch'))
    await selectOption('pool-runs-create-batch-id', 'receipt-q1 · 2026-01-01')
    await selectOption('pool-runs-create-start-organization', 'Root Org')

    await userClick(screen.getByTestId('pool-runs-create-submit'))

    await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
    const payload = mockCreatePoolRun.mock.calls[0][0] as Record<string, unknown>
    expect(payload.direction).toBe('top_down')
    expect(payload.pool_workflow_binding_id).toBe('binding-top-down')
    expect(payload.run_input).toEqual({
      batch_id: '99999999-9999-9999-9999-999999999999',
      start_organization_id: '11111111-1111-1111-1111-111111111111',
    })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('maps batch-backed top_down validation errors to batch and start organization fields', async () => {
    mockGetPoolGraph.mockResolvedValueOnce(buildPoolGraph())
    mockCreatePoolRun.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Validation Error',
          status: 400,
          detail: 'top_down batch_id must reference an existing receipt batch in the selected pool.',
          code: 'VALIDATION_ERROR',
        },
      },
    })
    renderPage()

    await openRunsStage('Create')
    await userClick(await screen.findByText('receipt batch'))
    await selectOption('pool-runs-create-batch-id', 'receipt-q1 · 2026-01-01')
    await selectOption('pool-runs-create-start-organization', 'Root Org')

    await userClick(screen.getByTestId('pool-runs-create-submit'))

    await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('Check the run parameters and try again.')).toBeInTheDocument()
    expect(await screen.findByText('top_down batch_id must reference an existing receipt batch in the selected pool.')).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('creates a receipt batch from the default operator path without manual UUID entry and opens the linked run context', async () => {
    const run = buildRun({
      id: 'aaaaaaaa-1111-2222-3333-batchrun000001',
      direction: 'top_down',
      run_input: {
        batch_id: 'aaaaaaaa-1111-2222-3333-batch00000001',
        start_organization_id: '11111111-1111-1111-1111-111111111111',
      },
    })
    const batch = buildReceiptBatch({
      id: 'aaaaaaaa-1111-2222-3333-batch00000001',
      run_id: run.id,
      source_reference: 'receipt-apr',
    })
    mockGetPoolGraph.mockResolvedValueOnce(buildPoolGraph())
    mockCreatePoolBatch.mockResolvedValueOnce({
      batch,
      settlement: batch.settlement,
      run,
      created: true,
      sale_closing: null,
    })
    mockListPoolRuns.mockResolvedValueOnce([buildRun()]).mockResolvedValueOnce([run])
    renderPage()

    await openRunsStage('Create')
    await userClick(await screen.findByText('receipt batch'))
    await selectOption('pool-runs-create-start-organization', 'Root Org')
    await userClick(await screen.findByTestId('pool-runs-open-batch-intake'))

    await screen.findByTestId('pool-runs-batch-intake-drawer')
    await selectOption('pool-runs-batch-intake-schema-template', 'json-template - JSON Template')
    fireEvent.change(screen.getByTestId('pool-runs-batch-intake-source-reference'), {
      target: { value: 'receipt-apr' },
    })
    fireEvent.change(screen.getByTestId('pool-runs-batch-intake-source-payload'), {
      target: {
        value: '[{"inn":"730000000001","amount":"125.50","external_id":"receipt-apr-001"}]',
      },
    })

    await userClick(screen.getByTestId('pool-runs-batch-intake-submit'))

    await waitFor(() => expect(mockCreatePoolBatch).toHaveBeenCalledTimes(1))
    expect(mockCreatePoolBatch).toHaveBeenCalledWith({
      pool_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      batch_kind: 'receipt',
      source_type: 'schema_template_upload',
      schema_template_id: '55555555-5555-5555-5555-555555555555',
      pool_workflow_binding_id: 'binding-top-down',
      start_organization_id: '11111111-1111-1111-1111-111111111111',
      period_start: expect.any(String),
      period_end: null,
      source_reference: 'receipt-apr',
      raw_payload_ref: '',
      json_payload: [
        {
          inn: '730000000001',
          amount: '125.50',
          external_id: 'receipt-apr-001',
        },
      ],
    })
    await waitFor(() => {
      expect(screen.getByTestId('pool-runs-location').textContent).toContain(
        `/pools/runs?pool=bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb&run=${run.id}&stage=inspect&detail=1`
      )
    })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('previews effective workflow binding before run start', async () => {
    mockGetPoolGraph.mockResolvedValueOnce(buildPoolGraph())
    renderPage()

    await openRunsStage('Create')
    await userClick(await screen.findByTestId('pool-runs-create-preview'))

    await waitFor(() => expect(mockPreviewPoolWorkflowBinding).toHaveBeenCalledTimes(1))
    expect(mockPreviewPoolWorkflowBinding).toHaveBeenCalledWith(
      expect.objectContaining({
        pool_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        pool_workflow_binding_id: 'binding-top-down',
        direction: 'top_down',
        mode: 'safe',
      })
    )
    expect(await screen.findByTestId('pool-runs-binding-preview')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-binding-preview-attachment-revision')).toHaveTextContent('r3')
    expect(screen.getByTestId('pool-runs-binding-preview-profile')).toHaveTextContent('services-publication')
    expect(screen.getByTestId('pool-runs-binding-preview-profile-revision')).toHaveTextContent('r2')
    expect(screen.getByText('invoice_mode r2')).toBeInTheDocument()
    expect(screen.getByText('compiled targets: 3')).toBeInTheDocument()
    expect(screen.getByText('decision_tables')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-binding-preview-slot-coverage')).toHaveTextContent('resolved: 1')
    expect(screen.getByText('All topology edges are covered by this binding preview.')).toBeInTheDocument()
    expect((screen.getByTestId('pool-runs-binding-preview-slot-projection') as HTMLTextAreaElement).value).toContain(
      '"invoice_mode"'
    )
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('uses backend slot coverage summary for binding preview instead of recomputing it from graph', async () => {
    mockGetPoolGraph.mockResolvedValueOnce(buildPoolGraph('unexpected_slot'))
    mockPreviewPoolWorkflowBinding.mockResolvedValueOnce(buildWorkflowBindingPreview({
      slot_coverage_summary: {
        total_edges: 1,
        counts: {
          resolved: 1,
          missing_selector: 0,
          missing_slot: 0,
          ambiguous_slot: 0,
          ambiguous_context: 0,
          unavailable_context: 0,
        },
        items: [
          {
            edge_id: 'edge-1',
            edge_label: 'Root Org -> Child Org',
            slot_key: 'invoice_mode',
            coverage: {
              code: null,
              status: 'resolved',
              label: 'Resolved',
              detail: 'invoice_mode -> decision-1 r2',
            },
          },
        ],
      },
    }))

    renderPage()

    await openRunsStage('Create')
    await userClick(await screen.findByTestId('pool-runs-create-preview'))

    expect(await screen.findByTestId('pool-runs-binding-preview-slot-coverage')).toHaveTextContent('resolved: 1')
    expect(screen.getByText('All topology edges are covered by this binding preview.')).toBeInTheDocument()
    expect(screen.queryByText(/unexpected_slot/i)).not.toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('submits bottom_up create-run payload with source_payload and selected schema template', async () => {
    renderPage()

    await openRunsStage('Create')
    const bottomUpRadio = await screen.findByRole('radio', { name: 'bottom_up' })
    const bottomUpLabel = bottomUpRadio.closest('label')
    expect(bottomUpLabel).toBeTruthy()
    await userClick(bottomUpLabel as Element)

    await waitFor(() => {
      expect(screen.getByRole('radio', { name: 'bottom_up' })).toBeChecked()
    })
    const sourcePayloadInput = await screen.findByLabelText('Source payload JSON')

    const schemaSelect = screen.getByTestId('pool-runs-create-schema-template')
    const schemaSelector = schemaSelect.querySelector('.ant-select-selector')
    expect(schemaSelector).toBeTruthy()
    fireEvent.mouseDown(schemaSelector as Element)
    await userClick(await screen.findByText('json-template - JSON Template'))
    await waitFor(() => {
      expect(schemaSelect).toHaveTextContent('json-template - JSON Template')
    })

    fireEvent.change(sourcePayloadInput, {
      target: { value: '[{"inn":"730000000111","amount":"55.00"}]' },
    })

    await userClick(screen.getByTestId('pool-runs-create-submit'))

    await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
    const payload = mockCreatePoolRun.mock.calls[0][0] as Record<string, unknown>
    expect(payload.direction).toBe('bottom_up')
    expect(payload.pool_workflow_binding_id).toBe('binding-bottom-up')
    expect(payload.schema_template_id).toBe('55555555-5555-5555-5555-555555555555')
    expect(payload.run_input).toEqual({
      source_payload: [{ inn: '730000000111', amount: '55.00' }],
    })
    expect(payload).not.toHaveProperty('source_hash')
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('ignores stale listPoolRuns response after create and keeps latest awaiting_approval run selected', async () => {
    const staleRun = buildRun({
      id: '99999999-9999-9999-9999-999999999999',
      status_reason: 'preparing',
      approval_state: 'preparing',
      publication_step_state: 'not_enqueued',
    })
    const freshRun = buildRun({
      id: 'aaaaaaaa-1111-1111-1111-111111111111',
      status_reason: 'awaiting_approval',
      approval_state: 'awaiting_approval',
      publication_step_state: 'not_enqueued',
      updated_at: '2026-01-01T00:05:00Z',
    })
    const firstRunsRequest = deferred<PoolRun[]>()

    mockListPoolRuns.mockReset()
    mockListPoolRuns
      .mockImplementationOnce(() => firstRunsRequest.promise)
      .mockResolvedValueOnce([freshRun, staleRun])
      .mockResolvedValue([freshRun, staleRun])
    mockCreatePoolRun.mockResolvedValueOnce({ run: freshRun, created: true })
    mockGetPoolRunReport.mockImplementation(async (runId: string) => (
      buildReport(runId === freshRun.id ? freshRun : staleRun)
    ))

    renderPage()

    const submitButton = await screen.findByTestId('pool-runs-create-submit')
    await userClick(submitButton)

    await waitFor(() => expect(mockCreatePoolRun).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(mockListPoolRuns.mock.calls.length).toBeGreaterThanOrEqual(2))

    firstRunsRequest.resolve([staleRun])

    await openRunsStage('Safe Actions')
    await waitFor(() => expect(screen.getByTestId('pool-runs-safe-confirm')).toBeEnabled())
    expect(screen.queryByText('Pre-publish is still running')).not.toBeInTheDocument()
    expect(screen.getAllByText('awaiting_approval').length).toBeGreaterThan(0)
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)
}

function registerPoolRunsContextRefreshTests() {
  it('refreshes current run report when Refresh Data is clicked', async () => {
    const initialRun = buildRun({
      status: 'validated',
      status_reason: 'awaiting_approval',
      approval_state: 'awaiting_approval',
      publication_step_state: 'not_enqueued',
      verification_status: 'not_verified',
      verification_summary: null,
    })
    const refreshedRun = buildRun({
      status: 'published',
      status_reason: null,
      approval_state: 'approved',
      publication_step_state: 'completed',
      verification_status: 'passed',
      verification_summary: {
        checked_targets: 1,
        verified_documents: 1,
        mismatches_count: 0,
        mismatches: [],
      },
    })

    mockListPoolRuns.mockReset()
    mockListPoolRuns
      .mockResolvedValueOnce([initialRun])
      .mockResolvedValue([refreshedRun])
    mockGetPoolRunReport.mockReset()
    mockGetPoolRunReport
      .mockResolvedValueOnce(buildReport(initialRun))
      .mockResolvedValue(buildReport(refreshedRun, {
        status: 'success',
        posted: true,
        domain_error_code: '',
        domain_error_message: '',
      }))

    renderPage()

    await openRunsStage('Inspect')
    expect(await screen.findByTestId('pool-runs-verification-status')).toHaveTextContent('status: not_verified')

    await userClick(screen.getByRole('button', { name: 'Refresh Data' }))

    await waitFor(() => expect(mockGetPoolRunReport).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.getByTestId('pool-runs-verification-status')).toHaveTextContent('status: passed'))
    expect(screen.getByText('Published documents verified')).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)
}
