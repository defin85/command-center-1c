import { expect, test, type Page, type Route } from '@playwright/test'

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>
  }
}

const TENANT_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
const DATABASE_ID = '10101010-1010-1010-1010-101010101010'
const NOW = '2026-03-10T12:00:00Z'

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

async function setupUiPlatformMocks(page: Page) {
  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'ui-platform', is_staff: false })
    }

    if (method === 'GET' && path === '/api/v2/rbac/get-effective-access/') {
      return fulfillJson(route, { clusters: [], databases: [] })
    }

    if (method === 'GET' && path === '/api/v2/settings/command-schemas/audit/') {
      return fulfillJson(route, { items: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/tenants/list-my-tenants/') {
      return fulfillJson(route, {
        active_tenant_id: TENANT_ID,
        tenants: [{ id: TENANT_ID, slug: 'default', name: 'Default', role: 'owner' }],
      })
    }

    if (method === 'GET' && path === '/api/v2/databases/list-databases/') {
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
      return fulfillJson(route, METADATA_MANAGEMENT)
    }

    if (method === 'GET' && path === '/api/v2/decisions/') {
      const databaseId = url.searchParams.get('database_id') || ''
      return fulfillJson(route, {
        decisions: [DECISION],
        count: 1,
        ...(databaseId ? { metadata_context: METADATA_CONTEXT } : {}),
      })
    }

    const decisionDetailMatch = path.match(/^\/api\/v2\/decisions\/([^/]+)\/$/)
    if (method === 'GET' && decisionDetailMatch) {
      return fulfillJson(route, {
        decision: DECISION,
        ...(url.searchParams.get('database_id') ? { metadata_context: METADATA_CONTEXT } : {}),
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/binding-profiles/') {
      return fulfillJson(route, {
        binding_profiles: [BINDING_PROFILE_SUMMARY],
        count: 1,
      })
    }

    const bindingProfileMatch = path.match(/^\/api\/v2\/pools\/binding-profiles\/([^/]+)\/$/)
    if (method === 'GET' && bindingProfileMatch) {
      return fulfillJson(route, {
        binding_profile: BINDING_PROFILE_DETAIL,
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/') {
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

test('UI platform: /decisions keeps mobile list stable and opens detail in a drawer', async ({ page }) => {
  await setupAuth(page)
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

test('UI platform: /pools/binding-profiles keeps mobile catalog readable and opens detail in a drawer', async ({ page }) => {
  await setupAuth(page)
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
  await expect(detailDrawer.getByText('Latest revision payload')).toBeVisible()
  await expectNoHorizontalOverflow(page)
})
