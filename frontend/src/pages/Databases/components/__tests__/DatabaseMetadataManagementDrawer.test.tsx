import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { DatabaseMetadataManagementDrawer } from '../DatabaseMetadataManagementDrawer'

const mockUseDatabaseMetadataManagement = vi.fn()
const mockUseReverifyDatabaseConfigurationProfile = vi.fn()
const mockUseRefreshDatabaseMetadataSnapshot = vi.fn()

vi.mock('../../../../api/queries/databases', () => ({
  useDatabaseMetadataManagement: (...args: unknown[]) => mockUseDatabaseMetadataManagement(...args),
  useReverifyDatabaseConfigurationProfile: (...args: unknown[]) => (
    mockUseReverifyDatabaseConfigurationProfile(...args)
  ),
  useRefreshDatabaseMetadataSnapshot: (...args: unknown[]) => mockUseRefreshDatabaseMetadataSnapshot(...args),
}))

const renderDrawer = () => {
  const onClose = vi.fn()
  const onOperationQueued = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App>
        <DatabaseMetadataManagementDrawer
          open
          databaseId="db-1"
          databaseName="Accounting DB"
          onClose={onClose}
          onOperationQueued={onOperationQueued}
        />
      </App>
    </QueryClientProvider>
  )
  return { onClose, onOperationQueued }
}

describe('DatabaseMetadataManagementDrawer', () => {
  beforeEach(() => {
    mockUseReverifyDatabaseConfigurationProfile.mockReset()
    mockUseRefreshDatabaseMetadataSnapshot.mockReset()
    mockUseDatabaseMetadataManagement.mockReset()
    mockUseReverifyDatabaseConfigurationProfile.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      data: null,
    })
    mockUseRefreshDatabaseMetadataSnapshot.mockReturnValue({
      mutate: vi.fn(),
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
          observed_metadata_hash: 'b'.repeat(64),
          canonical_metadata_hash: 'a'.repeat(64),
          publication_drift: true,
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
      },
    })

    const { onOperationQueued } = renderDrawer()
    const user = userEvent.setup()

    expect(screen.getByText('Metadata management: Accounting DB')).toBeInTheDocument()
    expect(screen.getByText('Configuration profile')).toBeInTheDocument()
    expect(screen.getByText('Metadata snapshot')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Перепроверить configuration identity/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Обновить metadata snapshot/i })).toBeInTheDocument()

    await user.click(screen.getByTestId('database-metadata-management-open-operations'))
    expect(onOperationQueued).toHaveBeenCalledWith('op-42')
  })

  it('shows fail-closed guidance when configuration profile and snapshot are missing', () => {
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
      },
    })

    renderDrawer()

    expect(screen.getByText('Configuration profile отсутствует.')).toBeInTheDocument()
    expect(
      screen.getByText('Metadata snapshot недоступен, пока не подтверждён configuration profile.')
    ).toBeInTheDocument()
  })
})
