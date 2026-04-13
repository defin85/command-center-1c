import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ComponentProps } from 'react'

const { mockTrackUiAction } = vi.hoisted(() => ({
  mockTrackUiAction: vi.fn((_: unknown, handler?: () => unknown) => handler?.()),
}))

import { DatabaseMetadataManagementDrawer } from '../DatabaseMetadataManagementDrawer'

const mockUseDatabaseMetadataManagement = vi.fn()
const mockUseReverifyDatabaseConfigurationProfile = vi.fn()
const mockUseRefreshDatabaseMetadataSnapshot = vi.fn()
const mockUseUpdateDatabaseMasterDataSyncEligibility = vi.fn()
const mockReverifyMutate = vi.fn()
const mockRefreshMutate = vi.fn()
const mockUpdateEligibilityMutate = vi.fn()

vi.mock('../../../../observability/uiActionJournal', () => ({
  trackUiAction: mockTrackUiAction,
}))

vi.mock('../../../../api/queries/databases', () => ({
  useDatabaseMetadataManagement: (...args: unknown[]) => mockUseDatabaseMetadataManagement(...args),
  useReverifyDatabaseConfigurationProfile: (...args: unknown[]) => (
    mockUseReverifyDatabaseConfigurationProfile(...args)
  ),
  useRefreshDatabaseMetadataSnapshot: (...args: unknown[]) => mockUseRefreshDatabaseMetadataSnapshot(...args),
  useUpdateDatabaseMasterDataSyncEligibility: (...args: unknown[]) => (
    mockUseUpdateDatabaseMasterDataSyncEligibility(...args)
  ),
}))

const buildPoolMasterDataSyncState = (overrides: Record<string, unknown> = {}) => ({
  cluster_all_eligibility: {
    state: 'unconfigured',
  },
  readiness: {
    cluster_attached: true,
    odata_configured: true,
    credentials_configured: true,
    ibcmd_profile_configured: false,
    service_mapping_status: 'missing',
    service_mapping_count: 0,
    runtime_enabled: true,
    inbound_enabled: true,
    outbound_enabled: true,
    default_policy: 'cc_master',
    health_status: 'healthy',
  },
  ...overrides,
})

const renderDrawer = (props?: Partial<ComponentProps<typeof DatabaseMetadataManagementDrawer>>) => {
  const onClose = vi.fn()
  const onOperationQueued = vi.fn()
  const onOpenIbcmdProfile = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App>
        <DatabaseMetadataManagementDrawer
          open
          databaseId="db-1"
          databaseName="Accounting DB"
          mutatingDisabled={false}
          onClose={onClose}
          onOperationQueued={onOperationQueued}
          onOpenIbcmdProfile={onOpenIbcmdProfile}
          {...props}
        />
      </App>
    </QueryClientProvider>
  )
  return { onClose, onOperationQueued, onOpenIbcmdProfile }
}

describe('DatabaseMetadataManagementDrawer', () => {
  beforeEach(() => {
    mockUseReverifyDatabaseConfigurationProfile.mockReset()
    mockUseRefreshDatabaseMetadataSnapshot.mockReset()
    mockUseUpdateDatabaseMasterDataSyncEligibility.mockReset()
    mockUseDatabaseMetadataManagement.mockReset()
    mockTrackUiAction.mockClear()
    mockReverifyMutate.mockReset()
    mockRefreshMutate.mockReset()
    mockUpdateEligibilityMutate.mockReset()
    mockUseReverifyDatabaseConfigurationProfile.mockReturnValue({
      mutate: mockReverifyMutate,
      isPending: false,
      data: null,
    })
    mockUseRefreshDatabaseMetadataSnapshot.mockReturnValue({
      mutate: mockRefreshMutate,
      isPending: false,
      data: null,
    })
    mockUseUpdateDatabaseMasterDataSyncEligibility.mockReturnValue({
      mutate: mockUpdateEligibilityMutate,
      isPending: false,
      data: null,
    })
  })

  it('renders configuration profile and metadata snapshot sections', async () => {
    mockUseDatabaseMetadataManagement.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        database_id: 'db-1',
        configuration_profile: {
          status: 'verified',
          config_name: 'Бухгалтерия предприятия, редакция 3.0',
          config_version: '3.0.193.19',
          config_generation_id: 'gen-1',
          config_root_name: 'БухгалтерияПредприятия',
          config_vendor: '1С',
          config_name_source: 'synonym_ru',
          verification_operation_id: 'op-42',
          verified_at: '2026-03-12T00:00:00Z',
          generation_probe_requested_at: null,
          generation_probe_checked_at: null,
          observed_metadata_fetched_at: '2026-03-12T01:23:45Z',
          observed_metadata_hash: 'b'.repeat(64),
          canonical_metadata_hash: 'a'.repeat(64),
          publication_drift: true,
          reverify_available: true,
          reverify_blocker_code: '',
          reverify_blocker_message: '',
          reverify_blocking_action: '',
        },
        metadata_snapshot: {
          status: 'available',
          missing_reason: '',
          snapshot_id: 'snapshot-1',
          source: 'live_refresh',
          fetched_at: '2026-03-12T01:00:00Z',
          catalog_version: 'v1:abc',
          config_name: 'Бухгалтерия предприятия, редакция 3.0',
          config_version: '3.0.193.19',
          extensions_fingerprint: '',
          metadata_hash: 'a'.repeat(64),
          resolution_mode: 'shared_scope',
          is_shared_snapshot: true,
          provenance_database_id: 'db-2',
          provenance_confirmed_at: '2026-03-12T01:00:00Z',
          observed_metadata_hash: 'b'.repeat(64),
          publication_drift: true,
        },
        pool_master_data_sync: buildPoolMasterDataSyncState({
          cluster_all_eligibility: { state: 'eligible' },
        }),
      },
    })

    const { onOperationQueued } = renderDrawer()
    const user = userEvent.setup()

    expect(screen.getByText('Metadata management: Accounting DB')).toBeInTheDocument()
    expect(screen.getByText('Configuration profile')).toBeInTheDocument()
    expect(screen.getByText('Metadata snapshot')).toBeInTheDocument()
    expect(screen.getByText('Pool master-data cluster_all eligibility')).toBeInTheDocument()
    expect(screen.getByText('Pool master-data readiness')).toBeInTheDocument()
    expect(screen.getByText('Verified')).toBeInTheDocument()
    expect(screen.getByText('Drift')).toBeInTheDocument()
    expect(screen.getByText('Live metadata отличается от canonical snapshot.')).toBeInTheDocument()
    expect(screen.getByText(/Последний успешный live metadata refresh:/)).toBeInTheDocument()
    expect(screen.getByText(/Текущий canonical snapshot fetched at:/)).toBeInTheDocument()
    expect(
      screen.getByText(
        'Refresh metadata snapshot может завершиться успешно и всё равно оставить drift: для этой business identity reused shared snapshot, поэтому observed hash обновляется, а canonical остаётся прежним.'
      )
    ).toBeInTheDocument()
    expect(screen.getByText('Eligible')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Перепроверить configuration identity/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Обновить metadata snapshot/i })).toBeInTheDocument()

    await user.click(screen.getByTestId('database-metadata-management-open-operations'))

    expect(mockTrackUiAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Open metadata management operations',
        context: expect.objectContaining({
          database_id: 'db-1',
          operation_id: 'op-42',
        }),
      }),
      expect.any(Function),
    )
    expect(onOperationQueued).toHaveBeenCalledWith('op-42')
  })

  it('shows fail-closed guidance when configuration profile and snapshot are missing', async () => {
    mockUseDatabaseMetadataManagement.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        database_id: 'db-1',
        configuration_profile: {
          status: 'missing',
          config_name: '',
          config_version: '',
          config_generation_id: '',
          config_root_name: '',
          config_vendor: '',
          config_name_source: '',
          verification_operation_id: '',
          verified_at: null,
          generation_probe_requested_at: null,
          generation_probe_checked_at: null,
          observed_metadata_hash: '',
          canonical_metadata_hash: '',
          publication_drift: false,
          reverify_available: false,
          reverify_blocker_code: 'IBCMD_CONNECTION_PROFILE_REQUIRED',
          reverify_blocker_message: 'Configure IBCMD connection profile for the selected database before running Re-verify configuration identity.',
          reverify_blocking_action: 'configure_ibcmd_connection_profile',
        },
        metadata_snapshot: {
          status: 'missing',
          missing_reason: 'configuration_profile_unavailable',
          snapshot_id: '',
          source: '',
          fetched_at: null,
          catalog_version: '',
          config_name: '',
          config_version: '',
          extensions_fingerprint: '',
          metadata_hash: '',
          resolution_mode: '',
          is_shared_snapshot: false,
          provenance_database_id: '',
          provenance_confirmed_at: null,
          observed_metadata_hash: '',
          publication_drift: false,
        },
        pool_master_data_sync: buildPoolMasterDataSyncState(),
      },
    })

    const { onOpenIbcmdProfile } = renderDrawer()

    expect(screen.getByText('Configuration profile отсутствует.')).toBeInTheDocument()
    expect(
      screen.getByText('Metadata snapshot недоступен, пока не подтверждён configuration profile.')
    ).toBeInTheDocument()
    expect(
      screen.getAllByText(
        'Configure IBCMD connection profile for the selected database before running Re-verify configuration identity.'
      )
    ).toHaveLength(2)
    expect(screen.getByTestId('database-metadata-management-open-ibcmd-profile')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Обновить metadata snapshot/i })).toBeDisabled()

    await userEvent.setup().click(screen.getByTestId('database-metadata-management-open-ibcmd-profile'))

    expect(mockTrackUiAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Open IBCMD profile',
      }),
      expect.any(Function),
    )
    expect(onOpenIbcmdProfile).toHaveBeenCalledTimes(1)
  })

  it('disables mutate controls when database operate access is unavailable', () => {
    mockUseDatabaseMetadataManagement.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        database_id: 'db-1',
        configuration_profile: {
          status: 'verified',
          config_name: 'Бухгалтерия предприятия, редакция 3.0',
          config_version: '3.0.193.19',
          config_generation_id: 'gen-1',
          config_root_name: 'БухгалтерияПредприятия',
          config_vendor: '1С',
          config_name_source: 'synonym_ru',
          verification_operation_id: '',
          verified_at: '2026-03-12T00:00:00Z',
          generation_probe_requested_at: null,
          generation_probe_checked_at: null,
          observed_metadata_hash: '',
          canonical_metadata_hash: '',
          publication_drift: false,
          reverify_available: true,
          reverify_blocker_code: '',
          reverify_blocker_message: '',
          reverify_blocking_action: '',
        },
        metadata_snapshot: {
          status: 'available',
          missing_reason: '',
          snapshot_id: 'snapshot-1',
          source: 'db',
          fetched_at: '2026-03-12T01:00:00Z',
          catalog_version: 'v1:abc',
          config_name: 'Бухгалтерия предприятия, редакция 3.0',
          config_version: '3.0.193.19',
          extensions_fingerprint: '',
          metadata_hash: 'a'.repeat(64),
          resolution_mode: 'database_scope',
          is_shared_snapshot: false,
          provenance_database_id: 'db-1',
          provenance_confirmed_at: '2026-03-12T01:00:00Z',
          observed_metadata_hash: '',
          publication_drift: false,
        },
        pool_master_data_sync: buildPoolMasterDataSyncState({
          cluster_all_eligibility: { state: 'excluded' },
        }),
      },
    })

    renderDrawer({ mutatingDisabled: true })

    expect(screen.getByRole('button', { name: /Перепроверить configuration identity/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Обновить metadata snapshot/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Save eligibility' })).toBeDisabled()
  })

  it('tracks reverify and refresh actions from the metadata drawer', async () => {
    mockUseDatabaseMetadataManagement.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        database_id: 'db-1',
        configuration_profile: {
          status: 'verified',
          config_name: 'Бухгалтерия предприятия, редакция 3.0',
          config_version: '3.0.193.19',
          config_generation_id: 'gen-1',
          config_root_name: 'БухгалтерияПредприятия',
          config_vendor: '1С',
          config_name_source: 'synonym_ru',
          verification_operation_id: '',
          verified_at: '2026-03-12T00:00:00Z',
          generation_probe_requested_at: null,
          generation_probe_checked_at: null,
          observed_metadata_hash: '',
          canonical_metadata_hash: '',
          publication_drift: false,
          reverify_available: true,
          reverify_blocker_code: '',
          reverify_blocker_message: '',
          reverify_blocking_action: '',
        },
        metadata_snapshot: {
          status: 'available',
          missing_reason: '',
          snapshot_id: 'snapshot-1',
          source: 'db',
          fetched_at: '2026-03-12T01:00:00Z',
          catalog_version: 'v1:abc',
          config_name: 'Бухгалтерия предприятия, редакция 3.0',
          config_version: '3.0.193.19',
          extensions_fingerprint: '',
          metadata_hash: 'a'.repeat(64),
          resolution_mode: 'database_scope',
          is_shared_snapshot: false,
          provenance_database_id: 'db-1',
          provenance_confirmed_at: '2026-03-12T01:00:00Z',
          observed_metadata_hash: '',
          publication_drift: false,
        },
        pool_master_data_sync: buildPoolMasterDataSyncState(),
      },
    })

    renderDrawer()
    const user = userEvent.setup()

    await user.click(screen.getByTestId('database-metadata-management-reverify'))
    await user.click(screen.getByTestId('database-metadata-management-refresh'))

    expect(mockTrackUiAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Re-verify configuration identity',
      }),
      expect.any(Function),
    )
    expect(mockTrackUiAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Refresh metadata snapshot',
      }),
      expect.any(Function),
    )
    expect(mockReverifyMutate).toHaveBeenCalledWith(
      { database_id: 'db-1' },
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    )
    expect(mockRefreshMutate).toHaveBeenCalledWith(
      { database_id: 'db-1' },
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    )
  })

  it('updates cluster_all eligibility through the metadata drawer', async () => {
    mockUseDatabaseMetadataManagement.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        database_id: 'db-1',
        configuration_profile: {
          status: 'verified',
          config_name: 'Бухгалтерия предприятия, редакция 3.0',
          config_version: '3.0.193.19',
          config_generation_id: 'gen-1',
          config_root_name: 'БухгалтерияПредприятия',
          config_vendor: '1С',
          config_name_source: 'synonym_ru',
          verification_operation_id: '',
          verified_at: '2026-03-12T00:00:00Z',
          generation_probe_requested_at: null,
          generation_probe_checked_at: null,
          observed_metadata_hash: '',
          canonical_metadata_hash: '',
          publication_drift: false,
          reverify_available: true,
          reverify_blocker_code: '',
          reverify_blocker_message: '',
          reverify_blocking_action: '',
        },
        metadata_snapshot: {
          status: 'available',
          missing_reason: '',
          snapshot_id: 'snapshot-1',
          source: 'db',
          fetched_at: '2026-03-12T01:00:00Z',
          catalog_version: 'v1:abc',
          config_name: 'Бухгалтерия предприятия, редакция 3.0',
          config_version: '3.0.193.19',
          extensions_fingerprint: '',
          metadata_hash: 'a'.repeat(64),
          resolution_mode: 'database_scope',
          is_shared_snapshot: false,
          provenance_database_id: 'db-1',
          provenance_confirmed_at: '2026-03-12T01:00:00Z',
          observed_metadata_hash: '',
          publication_drift: false,
        },
        pool_master_data_sync: buildPoolMasterDataSyncState(),
      },
    })

    renderDrawer()
    const user = userEvent.setup()

    await user.click(screen.getByRole('radio', { name: /Eligible: include this database in cluster_all/i }))
    await user.click(screen.getByTestId('database-metadata-management-save-eligibility'))

    expect(mockTrackUiAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Update cluster_all eligibility',
      }),
      expect.any(Function),
    )
    expect(mockUpdateEligibilityMutate).toHaveBeenCalledWith(
      {
        database_id: 'db-1',
        cluster_all_eligibility_state: 'eligible',
      },
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    )
  })
})
