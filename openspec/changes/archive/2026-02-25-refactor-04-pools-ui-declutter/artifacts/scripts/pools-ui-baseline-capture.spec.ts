import { mkdirSync } from 'node:fs'
import path from 'node:path'

import { expect, test, type Page, type Route } from '@playwright/test'

type AnyRecord = Record<string, unknown>

const TENANT_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
const NOW = '2026-02-23T10:00:00Z'
const OUTPUT_DIR = path.resolve(
  process.cwd(),
  '../openspec/changes/refactor-04-pools-ui-declutter/artifacts/2026-02-23-baseline'
)

const ORGANIZATIONS: AnyRecord[] = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    tenant_id: TENANT_ID,
    database_id: '10101010-1010-1010-1010-101010101010',
    name: 'Org One',
    full_name: 'Org One LLC',
    inn: '730000000001',
    kpp: '123456789',
    status: 'active',
    external_ref: '',
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
  {
    id: '22222222-2222-2222-2222-222222222222',
    tenant_id: TENANT_ID,
    database_id: '20202020-2020-2020-2020-202020202020',
    name: 'Org Two',
    full_name: 'Org Two LLC',
    inn: '730000000002',
    kpp: '123456789',
    status: 'active',
    external_ref: '',
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
  {
    id: '33333333-3333-3333-3333-333333333333',
    tenant_id: TENANT_ID,
    database_id: '30303030-3030-3030-3030-303030303030',
    name: 'Org Three',
    full_name: 'Org Three LLC',
    inn: '730000000003',
    kpp: '123456789',
    status: 'active',
    external_ref: '',
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
]

const POOL_ID = '90000000-0000-4000-8000-000000000111'
const RUN_ID = '91000000-0000-4000-8000-000000000111'

const POOLS: AnyRecord[] = [
  {
    id: POOL_ID,
    code: 'pool-main',
    name: 'Main Pool',
    description: 'Baseline pool for UX declutter audit',
    is_active: true,
    metadata: {},
    updated_at: NOW,
  },
]

const GRAPH: AnyRecord = {
  pool_id: POOL_ID,
  date: '2026-02-01',
  version: 'v1:topology-baseline',
  nodes: [
    {
      node_version_id: '92000000-0000-4000-8000-000000000001',
      organization_id: '11111111-1111-1111-1111-111111111111',
      inn: '730000000001',
      name: 'Org One',
      is_root: true,
      metadata: { role: 'root' },
    },
    {
      node_version_id: '92000000-0000-4000-8000-000000000002',
      organization_id: '22222222-2222-2222-2222-222222222222',
      inn: '730000000002',
      name: 'Org Two',
      is_root: false,
      metadata: { role: 'branch' },
    },
  ],
  edges: [
    {
      edge_version_id: '93000000-0000-4000-8000-000000000001',
      parent_node_version_id: '92000000-0000-4000-8000-000000000001',
      child_node_version_id: '92000000-0000-4000-8000-000000000002',
      weight: '0.5',
      min_amount: null,
      max_amount: null,
      metadata: {
        notes: 'baseline edge',
        document_policy: {
          version: 'document_policy.v1',
          chains: [
            {
              chain_id: 'sale-chain',
              documents: [
                {
                  document_id: 'sale-001',
                  entity_name: 'Document_РеализацияТоваровУслуг',
                  document_role: 'sale',
                  invoice_mode: 'required',
                },
              ],
            },
          ],
        },
      },
    },
  ],
}

const RUN: AnyRecord = {
  id: RUN_ID,
  tenant_id: TENANT_ID,
  pool_id: POOL_ID,
  schema_template_id: null,
  mode: 'safe',
  direction: 'top_down',
  status: 'validated',
  status_reason: 'awaiting_approval',
  period_start: '2026-02-01',
  period_end: null,
  run_input: { starting_amount: '100.00', source_payload: [{ inn: '730000000001', amount: '100.00' }] },
  input_contract_version: 'run_input_v1',
  idempotency_key: 'idem-baseline-run',
  workflow_execution_id: '94000000-0000-4000-8000-000000000111',
  workflow_status: 'pending',
  approval_state: 'awaiting_approval',
  publication_step_state: 'not_enqueued',
  terminal_reason: null,
  execution_backend: 'workflow_core',
  provenance: {
    workflow_run_id: '94000000-0000-4000-8000-000000000111',
    workflow_status: 'pending',
    execution_backend: 'workflow_core',
    retry_chain: [
      {
        workflow_run_id: '94000000-0000-4000-8000-000000000111',
        parent_workflow_run_id: null,
        attempt_number: 1,
        attempt_kind: 'initial',
        status: 'pending',
      },
    ],
  },
  workflow_template_name: 'pool-template-v1',
  seed: null,
  validation_summary: { rows: 3 },
  publication_summary: { total_targets: 2, failed_targets: 1 },
  diagnostics: [
    { code: 'VALIDATION_WARN', message: 'Invoice mode fallback applied' },
  ],
  last_error: '',
  created_at: NOW,
  updated_at: NOW,
  validated_at: NOW,
  publication_confirmed_at: null,
  publishing_started_at: null,
  completed_at: null,
}

const TEMPLATES: AnyRecord[] = [
  {
    id: '96000000-0000-4000-8000-000000000001',
    code: 'xlsx-sales-v1',
    name: 'Sales XLSX V1',
    format: 'xlsx',
    is_public: true,
    is_active: true,
    workflow_template_id: 'workflow-template-001',
    schema: { columns: { inn: 'inn', amount: 'amount' } },
    metadata: {
      workflow_binding: {
        workflow_template_id: 'workflow-template-001',
        version: 'v1',
      },
    },
    created_at: NOW,
    updated_at: NOW,
  },
]

async function fulfillJson(route: Route, data: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
    headers: { 'cache-control': 'no-store' },
  })
}

async function setupAuth(page: Page): Promise<void> {
  await page.addInitScript((tenantId: string) => {
    window.localStorage.setItem('auth_token', 'baseline-token')
    window.localStorage.setItem('active_tenant_id', tenantId)
  }, TENANT_ID)
}

async function setupApiMocks(page: Page): Promise<void> {
  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const pathName = url.pathname
    const method = request.method()

    if (method === 'GET' && pathName === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'baseline-user', is_staff: false })
    }
    if (method === 'GET' && pathName === '/api/v2/rbac/get-effective-access/') {
      return fulfillJson(route, { clusters: [], databases: [] })
    }
    if (method === 'GET' && pathName === '/api/v2/rbac/list-roles/') {
      return fulfillJson(route, { roles: [], count: 0, total: 0 })
    }
    if (method === 'GET' && pathName === '/api/v2/settings/command-schemas/audit/') {
      return fulfillJson(route, { items: [], count: 0, total: 0 })
    }
    if (method === 'GET' && pathName === '/api/v2/tenants/list-my-tenants/') {
      return fulfillJson(route, {
        active_tenant_id: TENANT_ID,
        tenants: [{ id: TENANT_ID, slug: 'default', name: 'Default', role: 'owner' }],
      })
    }
    if (method === 'GET' && pathName === '/api/v2/databases/list-databases/') {
      return fulfillJson(route, {
        databases: ORGANIZATIONS.map((item) => ({
          id: item.database_id,
          name: `${String(item.name)}-db`,
        })),
        count: ORGANIZATIONS.length,
        total: ORGANIZATIONS.length,
      })
    }
    if (method === 'GET' && pathName === '/api/v2/pools/organizations/') {
      return fulfillJson(route, { organizations: ORGANIZATIONS, count: ORGANIZATIONS.length })
    }
    if (method === 'GET' && pathName.startsWith('/api/v2/pools/organizations/') && pathName !== '/api/v2/pools/organizations/') {
      const organizationId = pathName.replace('/api/v2/pools/organizations/', '').replace('/', '')
      const organization = ORGANIZATIONS.find((item) => String(item.id) === organizationId)
      if (!organization) {
        return fulfillJson(route, { success: false, error: { code: 'ORGANIZATION_NOT_FOUND', message: 'Not found' } }, 404)
      }
      return fulfillJson(route, {
        organization,
        pool_bindings: [
          {
            pool_id: POOL_ID,
            pool_code: 'pool-main',
            pool_name: 'Main Pool',
            is_root: true,
            effective_from: '2026-02-01',
            effective_to: null,
          },
        ],
      })
    }
    if (method === 'GET' && pathName === '/api/v2/pools/') {
      return fulfillJson(route, { pools: POOLS, count: POOLS.length })
    }
    if (method === 'GET' && pathName.startsWith('/api/v2/pools/') && pathName.endsWith('/graph/')) {
      return fulfillJson(route, GRAPH)
    }
    if (method === 'GET' && pathName === '/api/v2/pools/schema-templates/') {
      return fulfillJson(route, { templates: TEMPLATES, count: TEMPLATES.length })
    }
    if (method === 'GET' && pathName === '/api/v2/pools/runs/') {
      return fulfillJson(route, { runs: [RUN], count: 1 })
    }
    if (method === 'GET' && pathName.startsWith('/api/v2/pools/runs/') && pathName.endsWith('/report/')) {
      return fulfillJson(route, {
        run: RUN,
        publication_attempts: [
          {
            id: 'attempt-001',
            target_database_id: '20202020-2020-2020-2020-202020202020',
            status: 'failed',
            attempt_number: 1,
            attempt_timestamp: NOW,
            publication_identity_strategy: 'normalized_document_key_v1',
            external_document_identity: 'sale-001',
            domain_error_code: 'ODATA_MAPPING_NOT_CONFIGURED',
            domain_error_message: 'No publication actor mapping',
            http_error: { status: 409 },
            transport_error: { message: 'timeout' },
          },
        ],
        validation_summary: RUN.validation_summary,
        publication_summary: RUN.publication_summary,
        diagnostics: RUN.diagnostics,
        attempts_by_status: { failed: 1 },
      })
    }

    return fulfillJson(route, {}, 200)
  })
}

test('capture pools UI baseline screenshots', async ({ page }) => {
  mkdirSync(OUTPUT_DIR, { recursive: true })

  await setupAuth(page)
  await setupApiMocks(page)

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Catalog', exact: true })).toBeVisible()
  await expect(page.locator('.ant-card', { hasText: 'Organizations' }).first()).toBeVisible()
  await page.screenshot({ path: path.join(OUTPUT_DIR, 'pools-catalog-baseline.png'), fullPage: true })

  await page.goto('/pools/runs', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Runs', exact: true })).toBeVisible()
  await expect(page.locator('.ant-card', { hasText: 'Execution Provenance / Report' }).first()).toBeVisible()
  await page.screenshot({ path: path.join(OUTPUT_DIR, 'pools-runs-baseline.png'), fullPage: true })

  await page.goto('/pools/templates', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Schema Templates', exact: true })).toBeVisible()
  await expect(page.locator('.ant-card').first()).toBeVisible()
  await page.screenshot({ path: path.join(OUTPUT_DIR, 'pools-templates-baseline.png'), fullPage: true })
})
