import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import type { BindingProfileDetail } from '../../../api/generated/model/bindingProfileDetail'
import type { BindingProfileRevision } from '../../../api/generated/model/bindingProfileRevision'
import type { BindingProfileSummary } from '../../../api/generated/model/bindingProfileSummary'
import type { AvailableDecisionRevision, AvailableWorkflowRevision } from '../../../types/workflow'
import { PoolBindingProfilesPage } from '../PoolBindingProfilesPage'

const mockUseBindingProfiles = vi.fn()
const mockUseBindingProfileDetail = vi.fn()
const mockUseCreateBindingProfile = vi.fn()
const mockUseReviseBindingProfile = vi.fn()
const mockUseDeactivateBindingProfile = vi.fn()
const mockUseAuthoringReferences = vi.fn()
const mockListOrganizationPools = vi.fn()

vi.mock('../../../api/queries/poolBindingProfiles', () => ({
  useBindingProfiles: (...args: unknown[]) => mockUseBindingProfiles(...args),
  useBindingProfileDetail: (...args: unknown[]) => mockUseBindingProfileDetail(...args),
  useCreateBindingProfile: (...args: unknown[]) => mockUseCreateBindingProfile(...args),
  useReviseBindingProfile: (...args: unknown[]) => mockUseReviseBindingProfile(...args),
  useDeactivateBindingProfile: (...args: unknown[]) => mockUseDeactivateBindingProfile(...args),
}))

vi.mock('../../../api/queries/authoringReferences', () => ({
  useAuthoringReferences: (...args: unknown[]) => mockUseAuthoringReferences(...args),
}))

vi.mock('../../../api/intercompanyPools', () => ({
  listOrganizationPools: (...args: unknown[]) => mockListOrganizationPools(...args),
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

const availableWorkflows: AvailableWorkflowRevision[] = [
  {
    id: 'workflow-revision-4',
    name: 'Services Publication',
    workflowDefinitionKey: 'services-publication',
    workflowRevisionId: 'wf-services-r2',
    workflowRevision: 4,
  },
  {
    id: 'workflow-revision-5',
    name: 'Services Publication',
    workflowDefinitionKey: 'services-publication',
    workflowRevisionId: 'wf-services-r5',
    workflowRevision: 5,
  },
  {
    id: 'workflow-revision-6',
    name: 'New Services Publication',
    workflowDefinitionKey: 'services-publication',
    workflowRevisionId: 'wf-new-r1',
    workflowRevision: 6,
  },
]

const availableDecisions: AvailableDecisionRevision[] = [
  {
    id: 'decision-version-3',
    name: 'Services Policy',
    decisionTableId: 'decision-1',
    decisionKey: 'document_policy',
    decisionRevision: 3,
  },
  {
    id: 'decision-version-4',
    name: 'Fallback Policy',
    decisionTableId: 'decision-2',
    decisionKey: 'document_policy',
    decisionRevision: 4,
  },
]

function openSelect(testId: string) {
  const select = screen.getByTestId(testId)
  const selector = select.querySelector('.ant-select-selector')
  expect(selector).toBeTruthy()
  fireEvent.mouseDown(selector as Element)
}

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
    mockUseAuthoringReferences.mockReset()
    mockListOrganizationPools.mockReset()

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
    mockUseAuthoringReferences.mockReturnValue({
      data: {
        availableWorkflows,
        availableDecisions,
      },
      isLoading: false,
      isError: false,
      error: null,
    })
    mockListOrganizationPools.mockResolvedValue([])
  })

  it('renders a dedicated reusable profile catalog with list and detail states on a separate authoring surface', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Binding Profiles' })).toBeInTheDocument()
    expect(screen.getByText(/Primary authoring catalog for reusable workflow\/slot logic/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open attachment workspace' })).toHaveAttribute('href', '/pools/catalog')
    expect(screen.getAllByText('services-publication').length).toBeGreaterThan(0)
    expect(screen.getByText('legacy-archive')).toBeInTheDocument()

    expect(screen.getByTestId('pool-binding-profiles-selected-code')).toHaveTextContent('services-publication')
    expect(screen.getByTestId('pool-binding-profiles-latest-revision-id')).toHaveTextContent('bp-rev-services-r2')
    expect(screen.getByRole('button', { name: 'Publish new revision' })).toBeEnabled()

    fireEvent.click(screen.getByText('legacy-archive'))

    expect(await screen.findByTestId('pool-binding-profiles-selected-code')).toHaveTextContent('legacy-archive')
    expect(screen.getByTestId('pool-binding-profiles-status')).toHaveTextContent('deactivated')
    expect(screen.getByRole('button', { name: 'Publish new revision' })).toBeDisabled()
  }, 25000)

  it('creates a reusable profile from the dedicated catalog form', async () => {
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

    fireEvent.click(await screen.findByRole('button', { name: 'Create profile' }))
    expect(screen.getByRole('link', { name: 'Open /workflows' })).toHaveAttribute('href', '/workflows')
    expect(screen.getByRole('link', { name: 'Open /decisions' })).toHaveAttribute('href', '/decisions')

    fireEvent.change(await screen.findByTestId('pool-binding-profiles-create-code'), {
      target: { value: 'new-profile' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-name'), {
      target: { value: 'New Profile' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-description'), {
      target: { value: 'Reusable authoring surface' },
    })
    expect(screen.queryByTestId('pool-binding-profiles-create-parameters-json')).not.toBeInTheDocument()
    openSelect('pool-binding-profiles-create-workflow-revision-select')
    fireEvent.click(await screen.findByText('New Services Publication · r6'))
    expect(await screen.findByText('wf-new-r1')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('pool-binding-profiles-create-add-slot'))
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-slot-key-0'), {
      target: { value: 'document_policy' },
    })
    openSelect('pool-binding-profiles-create-decision-select-0')
    fireEvent.click(await screen.findByText('Services Policy · decision-1 · r3'))
    await waitFor(() => {
      expect(screen.getByTestId('pool-binding-profiles-create-slot-ref-0')).toHaveTextContent('decision-1')
    })
    fireEvent.click(screen.getByTestId('pool-binding-profiles-create-advanced-toggle'))
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-parameters-json'), {
      target: { value: JSON.stringify({ publication_variant: 'full' }, null, 2) },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-role-mapping-json'), {
      target: { value: JSON.stringify({ initiator: 'finance' }, null, 2) },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-metadata-json'), {
      target: { value: JSON.stringify({ source: 'manual' }, null, 2) },
    })

    fireEvent.click(screen.getByTestId('pool-binding-profiles-create-submit'))

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
            workflow_name: 'New Services Publication',
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
  }, 25000)

  it('publishes a new immutable revision and deactivates the selected profile from the catalog', async () => {
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

    fireEvent.click(await screen.findByRole('button', { name: 'Publish new revision' }))

    openSelect('pool-binding-profiles-revise-workflow-revision-select')
    fireEvent.click(await screen.findByText('Services Publication · r5'))
    await waitFor(() => {
      expect(screen.getAllByText('wf-services-r5').length).toBeGreaterThan(0)
    })
    fireEvent.click(screen.getByTestId('pool-binding-profiles-revise-advanced-toggle'))
    fireEvent.change(screen.getByTestId('pool-binding-profiles-revise-metadata-json'), {
      target: { value: JSON.stringify({ source: 'catalog-update' }, null, 2) },
    })

    fireEvent.click(screen.getByTestId('pool-binding-profiles-revise-submit'))

    await waitFor(() => {
      expect(reviseMutateAsync).toHaveBeenCalledWith({
        bindingProfileId: activeDetail.binding_profile_id,
        request: {
          revision: {
            workflow: {
              workflow_definition_key: 'services-publication',
              workflow_revision_id: 'wf-services-r5',
              workflow_revision: 5,
              workflow_name: 'Services Publication',
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

    fireEvent.click(screen.getByRole('button', { name: 'Deactivate profile' }))

    await waitFor(() => {
      expect(deactivateMutateAsync).toHaveBeenCalledWith(activeDetail.binding_profile_id)
    })
  }, 25000)

  it('shows pool attachment usage for selected profile revisions', async () => {
    mockListOrganizationPools.mockResolvedValue([
      {
        id: 'pool-1',
        code: 'pool-main',
        name: 'Pool Main',
        description: '',
        is_active: true,
        metadata: {},
        workflow_bindings: [
          {
            binding_id: 'binding-1',
            pool_id: 'pool-1',
            revision: 4,
            status: 'active',
            binding_profile_id: activeDetail.binding_profile_id,
            binding_profile_revision_id: 'bp-rev-services-r2',
            binding_profile_revision_number: 2,
            resolved_profile: {
              binding_profile_id: activeDetail.binding_profile_id,
              code: activeDetail.code,
              name: activeDetail.name,
              status: activeDetail.status,
              binding_profile_revision_id: 'bp-rev-services-r2',
              binding_profile_revision_number: 2,
              workflow: activeDetail.latest_revision.workflow,
              decisions: activeDetail.latest_revision.decisions,
              parameters: activeDetail.latest_revision.parameters,
              role_mapping: activeDetail.latest_revision.role_mapping,
            },
            selector: { direction: 'top_down', mode: 'safe', tags: ['baseline'] },
            effective_from: '2026-01-01',
            effective_to: null,
          },
          {
            binding_id: 'binding-2',
            pool_id: 'pool-1',
            revision: 2,
            status: 'draft',
            binding_profile_id: activeDetail.binding_profile_id,
            binding_profile_revision_id: 'bp-rev-services-r1',
            binding_profile_revision_number: 1,
            resolved_profile: {
              binding_profile_id: activeDetail.binding_profile_id,
              code: activeDetail.code,
              name: activeDetail.name,
              status: activeDetail.status,
              binding_profile_revision_id: 'bp-rev-services-r1',
              binding_profile_revision_number: 1,
              workflow: activeDetail.revisions[1].workflow,
              decisions: activeDetail.revisions[1].decisions,
              parameters: activeDetail.revisions[1].parameters,
              role_mapping: activeDetail.revisions[1].role_mapping,
            },
            selector: { direction: 'bottom_up', mode: 'safe', tags: [] },
            effective_from: '2026-02-01',
            effective_to: null,
          },
        ],
        updated_at: '2026-03-16T12:00:00Z',
      },
    ])

    renderPage()

    expect(mockListOrganizationPools).not.toHaveBeenCalled()
    expect(await screen.findByText('Pool attachment usage')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Load attachment usage' }))

    await waitFor(() => {
      expect(mockListOrganizationPools).toHaveBeenCalledTimes(1)
    })

    expect(screen.getByTestId('pool-binding-profiles-usage-total')).toHaveTextContent('2')
    expect(screen.getByTestId('pool-binding-profiles-usage-revisions')).toHaveTextContent('2')
    expect(screen.getAllByText('pool-main')).toHaveLength(2)
    expect(screen.getByText('binding-1')).toBeInTheDocument()
    expect(screen.getByText('binding-2')).toBeInTheDocument()
  })

  it('fails closed on primary catalog load errors without triggering usage reads', async () => {
    mockUseBindingProfiles.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: {
        response: {
          data: {
            detail: 'Backend refused to load binding profiles.',
          },
        },
      },
    })
    mockUseBindingProfileDetail.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    })

    renderPage()

    expect(await screen.findByText('Backend refused to load binding profiles.')).toBeInTheDocument()
    expect(screen.getByText('Select a profile from the catalog.')).toBeInTheDocument()
    expect(mockListOrganizationPools).not.toHaveBeenCalled()
  })
})
