import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'

import type { PoolRun, PoolRunReport } from '../../../api/intercompanyPools'
import { PoolRunsPage } from '../PoolRunsPage'

const mockListOrganizationPools = vi.fn()
const mockGetPoolGraph = vi.fn()
const mockListPoolRuns = vi.fn()
const mockGetPoolRunReport = vi.fn()
const mockCreatePoolRun = vi.fn()
const mockRetryPoolRunFailed = vi.fn()
const mockConfirmPoolRunPublication = vi.fn()
const mockAbortPoolRunPublication = vi.fn()

vi.mock('reactflow', () => ({
  default: ({ children }: { children?: ReactNode }) => <div data-testid="mock-reactflow">{children}</div>,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
}))

vi.mock('../../../api/intercompanyPools', () => ({
  listOrganizationPools: (...args: unknown[]) => mockListOrganizationPools(...args),
  getPoolGraph: (...args: unknown[]) => mockGetPoolGraph(...args),
  listPoolRuns: (...args: unknown[]) => mockListPoolRuns(...args),
  getPoolRunReport: (...args: unknown[]) => mockGetPoolRunReport(...args),
  createPoolRun: (...args: unknown[]) => mockCreatePoolRun(...args),
  retryPoolRunFailed: (...args: unknown[]) => mockRetryPoolRunFailed(...args),
  confirmPoolRunPublication: (...args: unknown[]) => mockConfirmPoolRunPublication(...args),
  abortPoolRunPublication: (...args: unknown[]) => mockAbortPoolRunPublication(...args),
}))

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
    source_hash: 'src-1',
    idempotency_key: 'idem-1',
    workflow_execution_id: '22222222-2222-2222-2222-222222222222',
    workflow_status: 'pending',
    approval_state: 'awaiting_approval',
    publication_step_state: 'not_enqueued',
    terminal_reason: null,
    execution_backend: 'workflow_core',
    provenance: {
      workflow_run_id: '22222222-2222-2222-2222-222222222222',
      workflow_status: 'pending',
      execution_backend: 'workflow_core',
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
        entity_name: 'Document_IntercompanyPoolDistribution',
        documents_count: 1,
        publication_identity_strategy: 'guid',
        external_document_identity: 'ref-1',
        posted: false,
        domain_error_code: 'network',
        domain_error_message: 'temporary error',
        error_message: 'temporary error',
        ...attemptOverrides,
      },
    ],
    validation_summary: { rows: 5 },
    publication_summary: { total_targets: 3, failed_targets: 1 },
    diagnostics: [{ step: 'distribution_calculation', status: 'ok' }],
    attempts_by_status: { failed: 1 },
  }
}

function renderPage() {
  return render(
    <AntApp>
      <PoolRunsPage />
    </AntApp>
  )
}

describe('PoolRunsPage', () => {
  beforeEach(() => {
    mockListOrganizationPools.mockReset()
    mockGetPoolGraph.mockReset()
    mockListPoolRuns.mockReset()
    mockGetPoolRunReport.mockReset()
    mockCreatePoolRun.mockReset()
    mockRetryPoolRunFailed.mockReset()
    mockConfirmPoolRunPublication.mockReset()
    mockAbortPoolRunPublication.mockReset()

    const run = buildRun()
    mockListOrganizationPools.mockResolvedValue([
      {
        id: run.pool_id,
        code: 'pool-code',
        name: 'Pool name',
        is_active: true,
        metadata: {},
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockGetPoolGraph.mockResolvedValue({
      pool_id: run.pool_id,
      date: '2026-01-01',
      nodes: [],
      edges: [],
    })
    mockListPoolRuns.mockResolvedValue([run])
    mockGetPoolRunReport.mockResolvedValue(buildReport(run))
    mockCreatePoolRun.mockResolvedValue({ run, created: true })
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
  })

  it('renders unified provenance and safe status details', async () => {
    renderPage()

    expect(await screen.findByTestId('pool-runs-provenance-workflow-id')).toHaveTextContent(
      '22222222-2222-2222-2222-222222222222'
    )
    expect(screen.getAllByText('awaiting_approval').length).toBeGreaterThan(0)
    expect(screen.getAllByText('workflow_core').length).toBeGreaterThan(0)
    expect(screen.getByText(/#1 initial/)).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-safe-confirm')).toBeEnabled()
    expect(screen.getByTestId('pool-runs-safe-abort')).toBeEnabled()
  })

  it('sends confirm-publication with generated idempotency key', async () => {
    const user = userEvent.setup()
    renderPage()

    const confirmButton = await screen.findByTestId('pool-runs-safe-confirm')
    await waitFor(() => expect(confirmButton).toBeEnabled())
    await user.click(confirmButton)

    await waitFor(() => expect(mockConfirmPoolRunPublication).toHaveBeenCalledTimes(1))
    expect(mockConfirmPoolRunPublication).toHaveBeenCalledWith(
      '11111111-1111-1111-1111-111111111111',
      expect.any(String)
    )
    const generatedKey = mockConfirmPoolRunPublication.mock.calls[0][1] as string
    expect(generatedKey.length).toBeGreaterThan(8)
  })

  it('renders legacy run with backward-compatible provenance and diagnostics aliases', async () => {
    const legacyRun = buildRun({
      mode: 'unsafe',
      workflow_execution_id: null,
      workflow_status: null,
      execution_backend: 'legacy_pool_runtime',
      provenance: {
        workflow_run_id: null,
        workflow_status: null,
        execution_backend: 'legacy_pool_runtime',
        retry_chain: [],
      },
    })
    mockListPoolRuns.mockResolvedValue([legacyRun])
    mockGetPoolRunReport.mockResolvedValue(
      buildReport(legacyRun, {
        domain_error_message: '',
        error_message: 'legacy alias message',
      })
    )

    renderPage()

    expect(await screen.findByTestId('pool-runs-provenance-workflow-id')).toHaveTextContent('-')
    expect(screen.getAllByText('legacy').length).toBeGreaterThan(0)
    expect(screen.getByText('legacy alias message')).toBeInTheDocument()
  })
})
