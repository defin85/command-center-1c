import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import type { BindingProfileDetail } from '../../../api/generated/model/bindingProfileDetail'
import type { BindingProfileRevision } from '../../../api/generated/model/bindingProfileRevision'
import type { BindingProfileSummary } from '../../../api/generated/model/bindingProfileSummary'
import { PoolBindingProfilesPage } from '../PoolBindingProfilesPage'

const mockUseBindingProfiles = vi.fn()
const mockUseBindingProfileDetail = vi.fn()
const mockUseCreateBindingProfile = vi.fn()
const mockUseReviseBindingProfile = vi.fn()
const mockUseDeactivateBindingProfile = vi.fn()

vi.mock('../../../api/queries/poolBindingProfiles', () => ({
  useBindingProfiles: (...args: unknown[]) => mockUseBindingProfiles(...args),
  useBindingProfileDetail: (...args: unknown[]) => mockUseBindingProfileDetail(...args),
  useCreateBindingProfile: (...args: unknown[]) => mockUseCreateBindingProfile(...args),
  useReviseBindingProfile: (...args: unknown[]) => mockUseReviseBindingProfile(...args),
  useDeactivateBindingProfile: (...args: unknown[]) => mockUseDeactivateBindingProfile(...args),
}))

const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const

function buildRevision(overrides: Partial<BindingProfileRevision> = {}): BindingProfileRevision {
  return {
    binding_profile_revision_id: 'bp-rev-services-r2',
    binding_profile_id: 'bp-services',
    revision_number: 2,
    workflow: {
      workflow_definition_key: 'services-publication',
      workflow_revision_id: 'wf-services-r2',
      workflow_revision: 4,
      workflow_name: 'services_publication',
    },
    decisions: [
      {
        decision_table_id: 'decision-1',
        decision_key: 'document_policy',
        slot_key: 'document_policy',
        decision_revision: 3,
      },
    ],
    parameters: {
      publication_variant: 'full',
    },
    role_mapping: {
      initiator: 'finance',
    },
    metadata: {
      source: 'manual',
    },
    created_by: 'analyst',
    created_at: '2026-03-16T12:00:00Z',
    ...overrides,
  }
}

function buildSummaryFromDetail(detail: BindingProfileDetail): BindingProfileSummary {
  return {
    binding_profile_id: detail.binding_profile_id,
    code: detail.code,
    name: detail.name,
    description: detail.description,
    status: detail.status,
    latest_revision_number: detail.latest_revision_number,
    latest_revision: detail.latest_revision,
    created_by: detail.created_by,
    updated_by: detail.updated_by,
    deactivated_by: detail.deactivated_by,
    deactivated_at: detail.deactivated_at,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
  }
}

const activeDetail: BindingProfileDetail = {
  binding_profile_id: 'bp-services',
  code: 'services-publication',
  name: 'Services Publication',
  description: 'Reusable scheme for top-down publication.',
  status: 'active',
  latest_revision_number: 2,
  latest_revision: buildRevision(),
  revisions: [
    buildRevision(),
    buildRevision({
      binding_profile_revision_id: 'bp-rev-services-r1',
      revision_number: 1,
      workflow: {
        workflow_definition_key: 'services-publication',
        workflow_revision_id: 'wf-services-r1',
        workflow_revision: 3,
        workflow_name: 'services_publication',
      },
      created_at: '2026-03-15T08:00:00Z',
    }),
  ],
  created_by: 'analyst',
  updated_by: 'analyst',
  deactivated_by: undefined,
  deactivated_at: null,
  created_at: '2026-03-15T08:00:00Z',
  updated_at: '2026-03-16T12:00:00Z',
}

const deactivatedDetail: BindingProfileDetail = {
  binding_profile_id: 'bp-legacy',
  code: 'legacy-archive',
  name: 'Legacy Archive',
  description: 'Old profile kept only for pinned attachments.',
  status: 'deactivated',
  latest_revision_number: 1,
  latest_revision: buildRevision({
    binding_profile_id: 'bp-legacy',
    binding_profile_revision_id: 'bp-rev-legacy-r1',
    revision_number: 1,
    workflow: {
      workflow_definition_key: 'legacy-publication',
      workflow_revision_id: 'wf-legacy-r1',
      workflow_revision: 1,
      workflow_name: 'legacy_publication',
    },
  }),
  revisions: [
    buildRevision({
      binding_profile_id: 'bp-legacy',
      binding_profile_revision_id: 'bp-rev-legacy-r1',
      revision_number: 1,
      workflow: {
        workflow_definition_key: 'legacy-publication',
        workflow_revision_id: 'wf-legacy-r1',
        workflow_revision: 1,
        workflow_name: 'legacy_publication',
      },
    }),
  ],
  created_by: 'analyst',
  updated_by: 'analyst',
  deactivated_by: 'staff',
  deactivated_at: '2026-03-16T16:00:00Z',
  created_at: '2026-03-10T08:00:00Z',
  updated_at: '2026-03-16T16:00:00Z',
}

const profileDetails: Record<string, BindingProfileDetail> = {
  [activeDetail.binding_profile_id]: activeDetail,
  [deactivatedDetail.binding_profile_id]: deactivatedDetail,
}

const bindingProfiles = [
  buildSummaryFromDetail(activeDetail),
  buildSummaryFromDetail(deactivatedDetail),
]

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={ROUTER_FUTURE}>
        <AntApp>
          <PoolBindingProfilesPage />
        </AntApp>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('PoolBindingProfilesPage', () => {
  beforeEach(() => {
    mockUseBindingProfiles.mockReset()
    mockUseBindingProfileDetail.mockReset()
    mockUseCreateBindingProfile.mockReset()
    mockUseReviseBindingProfile.mockReset()
    mockUseDeactivateBindingProfile.mockReset()

    mockUseBindingProfiles.mockReturnValue({
      data: {
        binding_profiles: bindingProfiles,
        count: bindingProfiles.length,
      },
      isLoading: false,
      isError: false,
      error: null,
    })
    mockUseBindingProfileDetail.mockImplementation((bindingProfileId?: string) => ({
      data: bindingProfileId ? { binding_profile: profileDetails[bindingProfileId] } : undefined,
      isLoading: false,
      isError: false,
      error: null,
    }))
    mockUseCreateBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue({ binding_profile: activeDetail }),
    })
    mockUseReviseBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue({ binding_profile: activeDetail }),
    })
    mockUseDeactivateBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue({ binding_profile: deactivatedDetail }),
    })
  })

  it('renders a dedicated reusable profile catalog with list and detail states on a separate authoring surface', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Binding Profiles' })).toBeInTheDocument()
    expect(screen.getByText(/Primary authoring catalog for reusable workflow\/slot logic/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open attachment workspace' })).toHaveAttribute('href', '/pools/catalog')
    expect(screen.getAllByText('services-publication').length).toBeGreaterThan(0)
    expect(screen.getByText('legacy-archive')).toBeInTheDocument()

    await waitFor(() => {
      expect(mockUseBindingProfileDetail).toHaveBeenLastCalledWith(activeDetail.binding_profile_id, {
        enabled: true,
      })
    })

    expect(screen.getByTestId('pool-binding-profiles-selected-code')).toHaveTextContent('services-publication')
    expect(screen.getByTestId('pool-binding-profiles-latest-revision-id')).toHaveTextContent('bp-rev-services-r2')
    expect(screen.getByRole('button', { name: 'Publish new revision' })).toBeEnabled()

    await user.click(screen.getByText('legacy-archive'))

    expect(await screen.findByTestId('pool-binding-profiles-selected-code')).toHaveTextContent('legacy-archive')
    expect(screen.getByTestId('pool-binding-profiles-status')).toHaveTextContent('deactivated')
    expect(screen.getByRole('button', { name: 'Publish new revision' })).toBeDisabled()
  })

  it('creates a reusable profile from the dedicated catalog form', async () => {
    const user = userEvent.setup()
    const mutateAsync = vi.fn().mockResolvedValue({
      binding_profile: {
        ...activeDetail,
        binding_profile_id: 'bp-new',
        code: 'new-profile',
        name: 'New Profile',
      },
    })
    mockUseCreateBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync,
    })

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Create profile' }))

    fireEvent.change(await screen.findByTestId('pool-binding-profiles-create-code'), {
      target: { value: 'new-profile' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-name'), {
      target: { value: 'New Profile' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-description'), {
      target: { value: 'Reusable authoring surface' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-workflow-key'), {
      target: { value: 'services-publication' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-workflow-revision-id'), {
      target: { value: 'wf-new-r1' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-workflow-revision'), {
      target: { value: '6' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-workflow-name'), {
      target: { value: 'services_publication' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-decisions-json'), {
      target: {
        value: JSON.stringify([
          {
            decision_table_id: 'decision-1',
            decision_key: 'document_policy',
            slot_key: 'document_policy',
            decision_revision: 3,
          },
        ], null, 2),
      },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-parameters-json'), {
      target: { value: JSON.stringify({ publication_variant: 'full' }, null, 2) },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-role-mapping-json'), {
      target: { value: JSON.stringify({ initiator: 'finance' }, null, 2) },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-metadata-json'), {
      target: { value: JSON.stringify({ source: 'manual' }, null, 2) },
    })

    await user.click(screen.getByTestId('pool-binding-profiles-create-submit'))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        code: 'new-profile',
        name: 'New Profile',
        description: 'Reusable authoring surface',
        revision: {
          workflow: {
            workflow_definition_key: 'services-publication',
            workflow_revision_id: 'wf-new-r1',
            workflow_revision: 6,
            workflow_name: 'services_publication',
          },
          decisions: [
            {
              decision_table_id: 'decision-1',
              decision_key: 'document_policy',
              slot_key: 'document_policy',
              decision_revision: 3,
            },
          ],
          parameters: {
            publication_variant: 'full',
          },
          role_mapping: {
            initiator: 'finance',
          },
          metadata: {
            source: 'manual',
          },
        },
      })
    })
  })

  it('publishes a new immutable revision and deactivates the selected profile from the catalog', async () => {
    const user = userEvent.setup()
    const reviseMutateAsync = vi.fn().mockResolvedValue({ binding_profile: activeDetail })
    const deactivateMutateAsync = vi.fn().mockResolvedValue({ binding_profile: deactivatedDetail })
    mockUseReviseBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync: reviseMutateAsync,
    })
    mockUseDeactivateBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync: deactivateMutateAsync,
    })

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Publish new revision' }))

    fireEvent.change(screen.getByTestId('pool-binding-profiles-revise-workflow-revision'), {
      target: { value: '5' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-revise-metadata-json'), {
      target: { value: JSON.stringify({ source: 'catalog-update' }, null, 2) },
    })

    await user.click(screen.getByTestId('pool-binding-profiles-revise-submit'))

    await waitFor(() => {
      expect(reviseMutateAsync).toHaveBeenCalledWith({
        bindingProfileId: activeDetail.binding_profile_id,
        request: {
          revision: {
            workflow: {
              workflow_definition_key: 'services-publication',
              workflow_revision_id: 'wf-services-r2',
              workflow_revision: 5,
              workflow_name: 'services_publication',
            },
            decisions: [
              {
                decision_table_id: 'decision-1',
                decision_key: 'document_policy',
                slot_key: 'document_policy',
                decision_revision: 3,
              },
            ],
            parameters: {
              publication_variant: 'full',
            },
            role_mapping: {
              initiator: 'finance',
            },
            metadata: {
              source: 'catalog-update',
            },
          },
        },
      })
    })

    await user.click(screen.getByRole('button', { name: 'Deactivate profile' }))

    await waitFor(() => {
      expect(deactivateMutateAsync).toHaveBeenCalledWith(activeDetail.binding_profile_id)
    })
  })
})
