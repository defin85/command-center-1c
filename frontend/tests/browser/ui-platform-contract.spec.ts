import { expect, test, type Page, type Route } from '@playwright/test'

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>
  }
}

const TENANT_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
const DATABASE_ID = '10101010-1010-1010-1010-101010101010'
const NOW = '2026-03-10T12:00:00Z'
const WORKFLOW_REVISION_ID = 'wf-services-r4'

const METADATA_CONTEXT = {
  database_id: DATABASE_ID,
  snapshot_id: 'snapshot-shared-services',
  source: 'db',
  fetched_at: NOW,
  catalog_version: 'v1:shared-services',
  config_name: 'shared-profile',
  config_version: '8.3.24',
  config_generation_id: 'generation-shared-services',
  extensions_fingerprint: '',
  metadata_hash: 'a'.repeat(64),
  observed_metadata_hash: 'a'.repeat(64),
  publication_drift: false,
  resolution_mode: 'shared_scope',
  is_shared_snapshot: true,
  provenance_database_id: '20202020-2020-2020-2020-202020202020',
  provenance_confirmed_at: NOW,
  documents: [],
}

const METADATA_MANAGEMENT = {
  database_id: DATABASE_ID,
  configuration_profile: {
    status: 'verified',
    config_name: 'shared-profile',
    config_version: '8.3.24',
    config_generation_id: 'generation-shared-services',
    config_root_name: 'Accounting',
    config_vendor: '1C',
    config_name_source: 'manual',
    verification_operation_id: '',
    verified_at: NOW,
    generation_probe_requested_at: null,
    generation_probe_checked_at: null,
    observed_metadata_hash: 'a'.repeat(64),
    canonical_metadata_hash: 'a'.repeat(64),
    publication_drift: false,
    reverify_available: true,
    reverify_blocker_code: '',
    reverify_blocker_message: '',
    reverify_blocking_action: '',
  },
  metadata_snapshot: {
    status: 'available',
    missing_reason: '',
    snapshot_id: 'snapshot-shared-services',
    source: 'db',
    fetched_at: NOW,
    catalog_version: 'v1:shared-services',
    config_name: 'shared-profile',
    config_version: '8.3.24',
    config_generation_id: 'generation-shared-services',
    extensions_fingerprint: '',
    metadata_hash: 'a'.repeat(64),
    resolution_mode: 'shared_scope',
    is_shared_snapshot: true,
    provenance_database_id: '20202020-2020-2020-2020-202020202020',
    provenance_confirmed_at: NOW,
    observed_metadata_hash: 'a'.repeat(64),
    publication_drift: false,
  },
}

const DECISION = {
  id: 'decision-version-2',
  decision_table_id: 'services-publication-policy',
  decision_key: 'document_policy',
  decision_revision: 2,
  name: 'Services publication policy',
  description: 'Publishes service documents',
  inputs: [],
  outputs: [],
  rules: [
    {
      rule_id: 'default',
      priority: 0,
      conditions: {},
      outputs: {
        document_policy: {
          version: 'document_policy.v1',
          chains: [
            {
              chain_id: 'sale_chain',
              documents: [
                {
                  document_id: 'sale',
                  entity_name: 'Document_Sales',
                  document_role: 'sale',
                  field_mapping: {
                    Amount: 'allocation.amount',
                  },
                  table_parts_mapping: {},
                  link_rules: {},
                },
              ],
            },
          ],
        },
      },
    },
  ],
  hit_policy: 'first_match',
  validation_mode: 'fail_closed',
  is_active: true,
  parent_version: 'decision-version-1',
  metadata_context: {
    snapshot_id: METADATA_CONTEXT.snapshot_id,
    config_name: METADATA_CONTEXT.config_name,
    config_version: METADATA_CONTEXT.config_version,
    config_generation_id: METADATA_CONTEXT.config_generation_id,
    extensions_fingerprint: '',
    metadata_hash: 'a'.repeat(64),
    observed_metadata_hash: 'a'.repeat(64),
    publication_drift: false,
    resolution_mode: 'shared_scope',
    is_shared_snapshot: true,
    provenance_database_id: METADATA_CONTEXT.provenance_database_id,
    provenance_confirmed_at: NOW,
  },
  metadata_compatibility: {
    status: 'compatible',
    reason: null,
    is_compatible: true,
  },
  created_at: NOW,
  updated_at: NOW,
}

const FALLBACK_DECISION = {
  ...DECISION,
  id: 'decision-version-3',
  decision_revision: 3,
  name: 'Fallback services publication policy',
  description: 'Fallback policy for diagnostics',
  parent_version: DECISION.id,
}

const DECISIONS = [DECISION, FALLBACK_DECISION]

const WORKFLOW = {
  id: WORKFLOW_REVISION_ID,
  name: 'Services Publication',
  description: 'Reusable workflow for service publication.',
  workflow_type: 'complex',
  category: 'custom',
  is_valid: true,
  is_active: true,
  is_system_managed: false,
  management_mode: 'user_authored',
  visibility_surface: 'workflow_library',
  read_only_reason: null,
  version_number: 4,
  parent_version: null,
  created_by: null,
  created_by_username: 'analyst',
  node_count: 2,
  execution_count: 0,
  created_at: NOW,
  updated_at: NOW,
}

const BINDING_PROFILE_DETAIL = {
  binding_profile_id: 'bp-services',
  code: 'services-publication',
  name: 'Services Publication',
  description: 'Reusable scheme for top-down publication.',
  status: 'active',
  latest_revision_number: 2,
  latest_revision: {
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
        decision_table_id: 'services-publication-policy',
        decision_key: 'document_policy',
        slot_key: 'document_policy',
        decision_revision: 2,
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
    created_at: NOW,
  },
  revisions: [
    {
      binding_profile_revision_id: 'bp-rev-services-r2',
      binding_profile_id: 'bp-services',
      revision_number: 2,
      workflow: {
        workflow_definition_key: 'services-publication',
        workflow_revision_id: 'wf-services-r2',
        workflow_revision: 4,
        workflow_name: 'services_publication',
      },
      decisions: [],
      parameters: {},
      role_mapping: {},
      metadata: {},
      created_by: 'analyst',
      created_at: NOW,
    },
  ],
  created_by: 'analyst',
  updated_by: 'analyst',
  deactivated_by: null,
  deactivated_at: null,
  created_at: NOW,
  updated_at: NOW,
}

const BINDING_PROFILE_SUMMARY = {
  binding_profile_id: BINDING_PROFILE_DETAIL.binding_profile_id,
  code: BINDING_PROFILE_DETAIL.code,
  name: BINDING_PROFILE_DETAIL.name,
  description: BINDING_PROFILE_DETAIL.description,
  status: BINDING_PROFILE_DETAIL.status,
  latest_revision_number: BINDING_PROFILE_DETAIL.latest_revision_number,
  latest_revision: BINDING_PROFILE_DETAIL.latest_revision,
  created_by: BINDING_PROFILE_DETAIL.created_by,
  updated_by: BINDING_PROFILE_DETAIL.updated_by,
  deactivated_by: BINDING_PROFILE_DETAIL.deactivated_by,
  deactivated_at: BINDING_PROFILE_DETAIL.deactivated_at,
  created_at: BINDING_PROFILE_DETAIL.created_at,
  updated_at: BINDING_PROFILE_DETAIL.updated_at,
}

const LEGACY_BINDING_PROFILE_DETAIL = {
  ...BINDING_PROFILE_DETAIL,
  binding_profile_id: 'bp-legacy',
  code: 'legacy-archive',
  name: 'Legacy Archive',
  description: 'Legacy reusable profile kept for pinned attachments.',
  status: 'deactivated',
  latest_revision_number: 1,
  latest_revision: {
    binding_profile_revision_id: 'bp-rev-legacy-r1',
    binding_profile_id: 'bp-legacy',
    revision_number: 1,
    workflow: {
      workflow_definition_key: 'legacy-archive',
      workflow_revision_id: 'wf-legacy-r1',
      workflow_revision: 1,
      workflow_name: 'legacy_archive',
    },
    decisions: [
      {
        decision_table_id: 'services-publication-policy',
        decision_key: 'document_policy',
        slot_key: 'document_policy',
        decision_revision: 2,
      },
    ],
    parameters: {
      publication_variant: 'archive',
    },
    role_mapping: {
      initiator: 'finance',
    },
    metadata: {
      source: 'legacy',
    },
    created_by: 'analyst',
    created_at: NOW,
  },
  revisions: [
    {
      binding_profile_revision_id: 'bp-rev-legacy-r1',
      binding_profile_id: 'bp-legacy',
      revision_number: 1,
      workflow: {
        workflow_definition_key: 'legacy-archive',
        workflow_revision_id: 'wf-legacy-r1',
        workflow_revision: 1,
        workflow_name: 'legacy_archive',
      },
      decisions: [],
      parameters: {},
      role_mapping: {},
      metadata: {},
      created_by: 'analyst',
      created_at: NOW,
    },
  ],
  deactivated_by: 'analyst',
  deactivated_at: NOW,
}

const LEGACY_BINDING_PROFILE_SUMMARY = {
  binding_profile_id: LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id,
  code: LEGACY_BINDING_PROFILE_DETAIL.code,
  name: LEGACY_BINDING_PROFILE_DETAIL.name,
  description: LEGACY_BINDING_PROFILE_DETAIL.description,
  status: LEGACY_BINDING_PROFILE_DETAIL.status,
  latest_revision_number: LEGACY_BINDING_PROFILE_DETAIL.latest_revision_number,
  latest_revision: LEGACY_BINDING_PROFILE_DETAIL.latest_revision,
  created_by: LEGACY_BINDING_PROFILE_DETAIL.created_by,
  updated_by: LEGACY_BINDING_PROFILE_DETAIL.updated_by,
  deactivated_by: LEGACY_BINDING_PROFILE_DETAIL.deactivated_by,
  deactivated_at: LEGACY_BINDING_PROFILE_DETAIL.deactivated_at,
  created_at: LEGACY_BINDING_PROFILE_DETAIL.created_at,
  updated_at: LEGACY_BINDING_PROFILE_DETAIL.updated_at,
}

const BINDING_PROFILE_SUMMARIES = [BINDING_PROFILE_SUMMARY, LEGACY_BINDING_PROFILE_SUMMARY]
const BINDING_PROFILE_DETAILS: Record<string, typeof BINDING_PROFILE_DETAIL> = {
  [BINDING_PROFILE_DETAIL.binding_profile_id]: BINDING_PROFILE_DETAIL,
  [LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id]: LEGACY_BINDING_PROFILE_DETAIL,
}

const POOL_WITH_ATTACHMENT = {
  id: 'pool-1',
  code: 'pool-main',
  name: 'Main Pool',
  description: 'Workflow-centric pool',
  is_active: true,
  metadata: {},
  updated_at: NOW,
  workflow_bindings: [
    {
      binding_id: 'binding-top-down',
      pool_id: 'pool-1',
      revision: 3,
      status: 'active',
      contract_version: 'binding_profile.v1',
      binding_profile_id: 'bp-services',
      binding_profile_revision_id: 'bp-rev-services-r2',
      binding_profile_revision_number: 2,
      effective_from: NOW,
      effective_to: null,
      selector: {
        direction: 'top_down',
        mode: 'safe',
        tags: [],
      },
      workflow: {
        workflow_definition_key: 'services-publication',
        workflow_revision_id: 'wf-services-r2',
        workflow_revision: 4,
        workflow_name: 'services_publication',
      },
      decisions: [],
      parameters: {},
      role_mapping: {},
      resolved_profile: {
        binding_profile_id: 'bp-services',
        code: 'services-publication',
        name: 'Services Publication',
        status: 'active',
        binding_profile_revision_id: 'bp-rev-services-r2',
        binding_profile_revision_number: 2,
        workflow: {
          workflow_definition_key: 'services-publication',
          workflow_revision_id: 'wf-services-r2',
          workflow_revision: 4,
          workflow_name: 'services_publication',
        },
        decisions: [],
        parameters: {},
        role_mapping: {},
      },
      profile_lifecycle_warning: null,
    },
  ],
}

async function fulfillJson(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
    headers: { 'cache-control': 'no-store' },
  })
}

type RequestCounts = {
  bootstrap: number
  streamTickets: number
  databaseLists: number
  metadataManagementReads: number
  decisionsScoped: number
  decisionsUnscoped: number
  bindingProfilesList: number
  bindingProfileDetails: number
  organizationPools: number
}

function createRequestCounts(): RequestCounts {
  return {
    bootstrap: 0,
    streamTickets: 0,
    databaseLists: 0,
    metadataManagementReads: 0,
    decisionsScoped: 0,
    decisionsUnscoped: 0,
    bindingProfilesList: 0,
    bindingProfileDetails: 0,
    organizationPools: 0,
  }
}

async function setupAuth(page: Page) {
  await page.addInitScript((tenantId: string) => {
    window.__CC1C_ENV__ = {
      VITE_BASE_HOST: '127.0.0.1',
      VITE_API_URL: 'http://127.0.0.1:15173',
      VITE_WS_HOST: '127.0.0.1:15173',
    }
    localStorage.setItem('auth_token', 'test-token')
    localStorage.setItem('active_tenant_id', tenantId)
  }, TENANT_ID)
}

async function setupPersistentDatabaseStream(page: Page) {
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window)
    const encoder = new TextEncoder()

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url

      if (url.includes('/api/v2/databases/stream/')) {
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(encoder.encode(`id: ready-1\ndata: ${JSON.stringify({
              version: '1.0',
              type: 'database_stream_connected',
            })}\n\n`))
          },
        })

        return new Response(stream, {
          status: 200,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-store',
          },
        })
      }

      return originalFetch(input, init)
    }
  })
}

async function setupUiPlatformMocks(
  page: Page,
  options?: {
    isStaff?: boolean
    counts?: RequestCounts
  },
) {
  const counts = options?.counts
  const isStaff = options?.isStaff ?? false

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/bootstrap/') {
      if (counts) {
        counts.bootstrap += 1
      }
      return fulfillJson(route, {
        me: { id: 1, username: 'ui-platform', is_staff: isStaff },
        tenant_context: {
          active_tenant_id: TENANT_ID,
          tenants: [{ id: TENANT_ID, slug: 'default', name: 'Default', role: 'owner' }],
        },
        access: {
          user: { id: 1, username: 'ui-platform' },
          clusters: [],
          databases: [],
          operation_templates: [],
        },
        capabilities: {
          can_manage_rbac: isStaff,
          can_manage_driver_catalogs: false,
        },
      })
    }

    if (method === 'GET' && path === '/api/v2/databases/list-databases/') {
      if (counts) {
        counts.databaseLists += 1
      }
      return fulfillJson(route, {
        databases: [
          {
            id: DATABASE_ID,
            name: 'db-services',
            base_name: 'shared-profile',
            version: '8.3.24',
          },
        ],
        count: 1,
        total: 1,
      })
    }

    if (method === 'GET' && path === '/api/v2/databases/get-metadata-management/') {
      if (counts) {
        counts.metadataManagementReads += 1
      }
      return fulfillJson(route, METADATA_MANAGEMENT)
    }

    if (method === 'POST' && path === '/api/v2/databases/stream-ticket/') {
      if (counts) {
        counts.streamTickets += 1
      }
      return fulfillJson(route, {
        ticket: `ticket-${counts?.streamTickets ?? 1}`,
        expires_in: 30,
        stream_url: `/api/v2/databases/stream/?ticket=ticket-${counts?.streamTickets ?? 1}`,
        session_id: 'browser-session',
        lease_id: `lease-${counts?.streamTickets ?? 1}`,
        client_instance_id: 'browser-instance',
        scope: '__all__',
        message: 'Database stream ticket issued',
      })
    }

    if (method === 'GET' && path === '/api/v2/decisions/') {
      const databaseId = url.searchParams.get('database_id') || ''
      if (databaseId) {
        if (counts) {
          counts.decisionsScoped += 1
        }
      } else if (counts) {
        counts.decisionsUnscoped += 1
      }
      return fulfillJson(route, {
        decisions: DECISIONS,
        count: DECISIONS.length,
        ...(databaseId ? { metadata_context: METADATA_CONTEXT } : {}),
      })
    }

    if (method === 'GET' && path === '/api/v2/workflows/list-workflows/') {
      return fulfillJson(route, {
        workflows: [WORKFLOW],
        count: 1,
        total: 1,
        authoring_phase: null,
      })
    }

    const decisionDetailMatch = path.match(/^\/api\/v2\/decisions\/([^/]+)\/$/)
    if (method === 'GET' && decisionDetailMatch) {
      const decisionId = decisionDetailMatch[1] ?? DECISION.id
      return fulfillJson(route, {
        decision: DECISIONS.find((candidate) => candidate.id === decisionId) ?? DECISION,
        ...(url.searchParams.get('database_id') ? { metadata_context: METADATA_CONTEXT } : {}),
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/binding-profiles/') {
      if (counts) {
        counts.bindingProfilesList += 1
      }
      return fulfillJson(route, {
        binding_profiles: BINDING_PROFILE_SUMMARIES,
        count: BINDING_PROFILE_SUMMARIES.length,
      })
    }

    const bindingProfileMatch = path.match(/^\/api\/v2\/pools\/binding-profiles\/([^/]+)\/$/)
    if (method === 'GET' && bindingProfileMatch) {
      const bindingProfileId = bindingProfileMatch[1] ?? BINDING_PROFILE_DETAIL.binding_profile_id
      if (counts) {
        counts.bindingProfileDetails += 1
      }
      return fulfillJson(route, {
        binding_profile: BINDING_PROFILE_DETAILS[bindingProfileId] ?? BINDING_PROFILE_DETAIL,
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/') {
      if (counts) {
        counts.organizationPools += 1
      }
      return fulfillJson(route, {
        pools: [POOL_WITH_ATTACHMENT],
        count: 1,
      })
    }

    return fulfillJson(route, { detail: `Unhandled mock for ${method} ${path}` }, 404)
  })
}

async function expectNoHorizontalOverflow(page: Page) {
  const hasOverflow = await page.evaluate(() => (
    document.documentElement.scrollWidth - window.innerWidth > 1
  ))
  expect(hasOverflow).toBe(false)
}

async function expectVisibleWithinContainer(
  locator: ReturnType<Page['locator']>,
  container: ReturnType<Page['locator']>,
) {
  const [box, containerBox] = await Promise.all([locator.boundingBox(), container.boundingBox()])

  if (!box || !containerBox) {
    throw new Error('Expected visible element and container bounding boxes.')
  }

  expect(box.x).toBeGreaterThanOrEqual(containerBox.x)
  expect(box.y).toBeGreaterThanOrEqual(containerBox.y)
  expect(box.x + box.width).toBeLessThanOrEqual(containerBox.x + containerBox.width)
  expect(box.y + box.height).toBeLessThanOrEqual(containerBox.y + containerBox.height)
}

async function expectContrastAtLeast(locator: ReturnType<Page['locator']>, minimumRatio: number) {
  const contrastRatio = await locator.evaluate((element) => {
    const parseColor = (value: string) => {
      const match = value.match(/rgba?\(([^)]+)\)/)
      if (!match) {
        return [0, 0, 0, 1] as const
      }

      const [r = '0', g = '0', b = '0', a = '1'] = match[1].split(',').map((part) => part.trim())
      return [Number(r), Number(g), Number(b), Number(a)] as const
    }

    const composite = (
      foreground: readonly [number, number, number, number],
      background: readonly [number, number, number, number],
    ) => {
      const alpha = foreground[3]
      const channel = (index: number) => (
        foreground[index] * alpha + background[index] * (1 - alpha)
      )

      return [channel(0), channel(1), channel(2), 1] as const
    }

    const luminance = (rgb: readonly [number, number, number, number]) => {
      const toLinear = (channel: number) => {
        const normalized = channel / 255
        return normalized <= 0.04045
          ? normalized / 12.92
          : ((normalized + 0.055) / 1.055) ** 2.4
      }

      const [r, g, b] = rgb
      return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b)
    }

    const resolveBackground = (node: HTMLElement | null) => {
      let current = node
      while (current) {
        const background = parseColor(window.getComputedStyle(current).backgroundColor)
        if (background[3] > 0) {
          return background
        }
        current = current.parentElement
      }

      return [255, 255, 255, 1] as const
    }

    const styles = window.getComputedStyle(element)
    const foreground = composite(parseColor(styles.color), resolveBackground(element.parentElement))
    const background = resolveBackground(element as HTMLElement)
    const lighter = Math.max(luminance(foreground), luminance(background))
    const darker = Math.min(luminance(foreground), luminance(background))

    return (lighter + 0.05) / (darker + 0.05)
  })

  expect(contrastRatio).toBeGreaterThanOrEqual(minimumRatio)
}

test('UI platform: /decisions keeps mobile list stable and opens detail in a drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/decisions', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Decision Policy Library')).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.getByText('Services publication policy').first().click()

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByText('Compiled document_policy JSON')).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /decisions opens authoring in a mobile-safe drawer with labeled fields', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/decisions', { waitUntil: 'domcontentloaded' })

  await page.getByRole('button', { name: 'New policy' }).click()

  const authoringDrawer = page.getByRole('dialog')
  await expect(authoringDrawer).toBeVisible()
  await expect(authoringDrawer.getByLabel('Decision table ID')).toBeVisible()
  await expect(authoringDrawer.getByLabel('Decision name')).toBeVisible()
  await expect(authoringDrawer.getByRole('button', { name: 'Save decision' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /pools/binding-profiles keeps mobile catalog readable and opens detail in a drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/pools/binding-profiles', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Binding Profiles')).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.getByText('services-publication').first().click()

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('pool-binding-profiles-selected-code')).toHaveText('services-publication')
  await expect(detailDrawer.getByRole('heading', { name: 'Where this profile is used', level: 3 })).toBeVisible()
  await expect(detailDrawer.getByRole('button', { name: 'Publish new revision' })).toBeVisible()
  await expect(detailDrawer.getByRole('button', { name: 'Deactivate profile' })).toBeVisible()
  await expect(detailDrawer.getByRole('columnheader', { name: 'Opaque pin' })).toHaveCount(0)
  await expect(detailDrawer.getByRole('button', { name: /Advanced payload and immutable pins/i })).toBeVisible()
  await expectVisibleWithinContainer(detailDrawer.getByRole('button', { name: 'Publish new revision' }), detailDrawer)
  await expectVisibleWithinContainer(detailDrawer.getByRole('button', { name: 'Deactivate profile' }), detailDrawer)
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /pools/binding-profiles opens create-profile authoring in a mobile-safe modal shell', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/pools/binding-profiles', { waitUntil: 'domcontentloaded' })

  await page.getByRole('button', { name: 'Create profile' }).click()

  const authoringModal = page.getByRole('dialog')
  await expect(authoringModal).toBeVisible()
  await expect(authoringModal.getByLabel('Profile code')).toBeVisible()
  await expect(authoringModal.getByLabel('Profile name')).toBeVisible()
  await expect(authoringModal.getByTestId('pool-binding-profiles-create-workflow-revision-select')).toBeVisible()
  await expect(authoringModal.getByRole('button', { name: 'Create profile' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('Runtime contract: /decisions avoids mount-time waterfall and duplicate notifications on the default path', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/decisions', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Decision Policy Library')).toBeVisible()
  await expect(page.getByText('Services publication policy').first()).toBeVisible()

  await expect.poll(() => counts.bootstrap).toBe(1)
  await expect.poll(() => counts.streamTickets).toBe(1)
  await expect.poll(() => counts.databaseLists).toBe(1)
  await expect.poll(() => counts.metadataManagementReads).toBe(1)
  await expect.poll(() => counts.decisionsScoped).toBe(1)
  await expect.poll(() => counts.decisionsUnscoped).toBe(0)
  await expect.poll(() => counts.organizationPools).toBe(0)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /pools/binding-profiles defers usage reads until the user requests them', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/pools/binding-profiles', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Binding Profiles')).toBeVisible()
  await expect.poll(() => counts.organizationPools).toBe(0)

  await page.getByRole('button', { name: 'Load attachment usage' }).click()

  await expect.poll(() => counts.organizationPools).toBe(1)
  await expect(page.getByText('Main Pool')).toBeVisible()
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('UI platform: /decisions restores deep-link context and keeps diagnostics behind disclosure', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto(`/decisions?database=${DATABASE_ID}&decision=${FALLBACK_DECISION.id}&snapshot=all`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('combobox', { name: 'Target database' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open decision Fallback services publication policy' })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('button', { name: 'Show matching configuration only' })).toBeVisible()
  await expect(page.getByText('shared_scope')).toHaveCount(0)

  await page.getByRole('button', { name: /Target metadata context/i }).click()

  await expect(page.getByText('shared_scope')).toBeVisible()
  await expect(page.getByText('snapshot-shared-services')).toBeVisible()
})

test('UI platform: /decisions keeps selected revision on browser back and forward', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto(`/decisions?database=${DATABASE_ID}&decision=${DECISION.id}`, {
    waitUntil: 'domcontentloaded',
  })

  const primaryDecisionButton = page.getByRole('button', { name: `Open decision ${DECISION.name}` })
  const fallbackDecisionButton = page.getByRole('button', { name: `Open decision ${FALLBACK_DECISION.name}` })

  await expect(primaryDecisionButton).toHaveAttribute('aria-pressed', 'true')

  await fallbackDecisionButton.click()

  await expect(page).toHaveURL(new RegExp(`\\?database=${DATABASE_ID}&decision=${FALLBACK_DECISION.id}$`))
  await expect(fallbackDecisionButton).toHaveAttribute('aria-pressed', 'true')

  await page.goBack()

  await expect(page).toHaveURL(new RegExp(`\\?database=${DATABASE_ID}&decision=${DECISION.id}$`))
  await expect(primaryDecisionButton).toHaveAttribute('aria-pressed', 'true')

  await page.goForward()

  await expect(page).toHaveURL(new RegExp(`\\?database=${DATABASE_ID}&decision=${FALLBACK_DECISION.id}$`))
  await expect(fallbackDecisionButton).toHaveAttribute('aria-pressed', 'true')
})

test('Runtime contract: /decisions ignores same-route menu re-entry and keeps catalog state stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/decisions?database=${DATABASE_ID}&decision=${DECISION.id}`, {
    waitUntil: 'domcontentloaded',
  })

  const decisionsMenuItem = page.getByRole('menuitem', { name: /Decisions/i })
  const primaryDecisionButton = page.getByRole('button', { name: `Open decision ${DECISION.name}` })

  await expect(primaryDecisionButton).toHaveAttribute('aria-pressed', 'true')
  await expect.poll(() => counts.databaseLists).toBe(1)
  await expect.poll(() => counts.metadataManagementReads).toBe(1)
  await expect.poll(() => counts.decisionsScoped).toBe(1)

  await decisionsMenuItem.click()
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(new RegExp(`\\?database=${DATABASE_ID}&decision=${DECISION.id}$`))
  await expect(primaryDecisionButton).toHaveAttribute('aria-pressed', 'true')
  await expect(counts.databaseLists).toBe(1)
  await expect(counts.metadataManagementReads).toBe(1)
  await expect(counts.decisionsScoped).toBe(1)
  await expect(counts.decisionsUnscoped).toBe(0)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('UI platform: /pools/binding-profiles restores catalog context and keeps selection keyboard-first', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto('/pools/binding-profiles?q=legacy&profile=bp-legacy&detail=1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByLabel('Search profiles')).toHaveValue('legacy')
  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('legacy-archive')
  await expect(page.getByText('legacy_archive · r1')).toBeVisible()
  await expect(page.getByText('Workflow definition key')).toHaveCount(0)

  await page.goto('/pools/binding-profiles', { waitUntil: 'domcontentloaded' })

  const legacyProfileButton = page.getByRole('button', { name: 'Open profile legacy-archive' })
  await legacyProfileButton.focus()
  await page.keyboard.press('Enter')

  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('legacy-archive')
  await expect(legacyProfileButton).toHaveAttribute('aria-pressed', 'true')
})

test('UI platform: /pools/binding-profiles keeps selected profile on browser back and forward', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto(`/pools/binding-profiles?profile=${BINDING_PROFILE_DETAIL.binding_profile_id}`, {
    waitUntil: 'domcontentloaded',
  })

  const servicesProfileButton = page.getByRole('button', { name: 'Open profile services-publication' })
  const legacyProfileButton = page.getByRole('button', { name: 'Open profile legacy-archive' })

  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('services-publication')
  await expect(servicesProfileButton).toHaveAttribute('aria-pressed', 'true')

  await legacyProfileButton.click()

  await expect(page).toHaveURL(new RegExp(`\\?profile=${LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id}&detail=1$`))
  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('legacy-archive')
  await expect(legacyProfileButton).toHaveAttribute('aria-pressed', 'true')

  await page.goBack()

  await expect(page).toHaveURL(new RegExp(`\\?profile=${BINDING_PROFILE_DETAIL.binding_profile_id}$`))
  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('services-publication')
  await expect(servicesProfileButton).toHaveAttribute('aria-pressed', 'true')

  await page.goForward()

  await expect(page).toHaveURL(new RegExp(`\\?profile=${LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id}&detail=1$`))
  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('legacy-archive')
  await expect(legacyProfileButton).toHaveAttribute('aria-pressed', 'true')
})

test('UI platform: /pools/binding-profiles keeps shell labels accessible and primary states above contrast floor', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  await page.goto('/pools/binding-profiles', { waitUntil: 'domcontentloaded' })

  const streamStatusButton = page.getByRole('button', { name: 'Stream: Connected' })
  const selectedMenuItem = page.getByRole('menuitem', { name: /Pool Binding Profiles/i })
  const subtitle = page.getByText(/Reusable profile workspace for selecting a profile/i).first()
  const createProfileButton = page.getByRole('button', { name: 'Create profile' })
  const deactivateProfileButton = page.getByRole('button', { name: 'Deactivate profile' })
  const activeStatusBadge = page.getByTestId('pool-binding-profiles-status').locator('.ant-tag')

  await expect(streamStatusButton).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Where this profile is used', level: 3 })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Opaque pin' })).toHaveCount(0)

  await page.getByRole('button', { name: /Advanced payload and immutable pins/i }).click()

  await expect(page.getByRole('columnheader', { name: 'Opaque pin' })).toBeVisible()
  await expect(page.getByText('Latest immutable revision')).toBeVisible()

  await expectContrastAtLeast(selectedMenuItem, 4.5)
  await expectContrastAtLeast(streamStatusButton.locator('.ant-tag'), 4.5)
  await expectContrastAtLeast(subtitle, 4.5)
  await expectContrastAtLeast(createProfileButton, 4.5)
  await expectContrastAtLeast(deactivateProfileButton, 4.5)
  await expectContrastAtLeast(activeStatusBadge, 4.5)
})

test('UI platform: /pools/binding-profiles keeps fallback stream labels and deactivated states above contrast floor', async ({ page }) => {
  await setupAuth(page)
  await setupUiPlatformMocks(page, { isStaff: false })

  await page.goto(`/pools/binding-profiles?profile=${LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id}&detail=1`, { waitUntil: 'domcontentloaded' })

  const streamStatusButton = page.getByRole('button', { name: 'Stream: Fallback' })
  const deactivatedStatusBadge = page.getByTestId('pool-binding-profiles-status').locator('.ant-tag')

  await expect(streamStatusButton).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Where this profile is used', level: 3 })).toBeVisible()
  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('legacy-archive')
  await expect(deactivatedStatusBadge).toContainText('deactivated')

  await expectContrastAtLeast(streamStatusButton.locator('.ant-tag'), 4.5)
  await expectContrastAtLeast(deactivatedStatusBadge, 4.5)
})

test('Runtime contract: one browser instance keeps a single database stream owner across tabs', async ({ context }) => {
  const counts = createRequestCounts()
  const firstPage = await context.newPage()

  await setupAuth(firstPage)
  await setupPersistentDatabaseStream(firstPage)
  await setupUiPlatformMocks(firstPage, { isStaff: true, counts })

  await firstPage.goto('/decisions', { waitUntil: 'domcontentloaded' })
  await expect(firstPage.getByText('Decision Policy Library')).toBeVisible()
  await expect.poll(() => counts.streamTickets).toBe(1)

  const secondPage = await context.newPage()
  await setupAuth(secondPage)
  await setupPersistentDatabaseStream(secondPage)
  await setupUiPlatformMocks(secondPage, { isStaff: true, counts })

  await secondPage.goto('/pools/binding-profiles', { waitUntil: 'domcontentloaded' })
  await expect(secondPage.getByText('Binding Profiles')).toBeVisible()
  await expect.poll(() => counts.streamTickets).toBe(1)
  await expect(firstPage.getByText('Request Error')).toHaveCount(0)
  await expect(secondPage.getByText('Request Error')).toHaveCount(0)
})
