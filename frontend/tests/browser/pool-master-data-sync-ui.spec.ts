import { expect, test, type Page, type Route } from '@playwright/test'

type AnyRecord = Record<string, unknown>

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>
  }
}

const TENANT_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
const DATABASE_ID = '10101010-1010-1010-1010-101010101010'
const NOW = '2026-01-01T00:00:00Z'

type ActionError = {
  status: number
  code: string
  detail: string
}

type SyncUiMockState = {
  statuses: AnyRecord[]
  conflicts: AnyRecord[]
  actionCalls: {
    retry: AnyRecord[]
    reconcile: AnyRecord[]
    resolve: AnyRecord[]
  }
  actionErrors?: Partial<Record<'retry' | 'reconcile' | 'resolve', ActionError>>
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

function buildListMeta(limit: number, offset: number, total: number) {
  return {
    count: total,
    limit,
    offset,
  }
}

async function setupApiMocks(page: Page, state: SyncUiMockState) {
  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/bootstrap/') {
      return fulfillJson(route, {
        me: { id: 1, username: 'sync-user', is_staff: true },
        tenant_context: {
          active_tenant_id: TENANT_ID,
          tenants: [{ id: TENANT_ID, slug: 'default', name: 'Default', role: 'owner' }],
        },
        access: {
          user: { id: 1, username: 'sync-user' },
          clusters: [],
          databases: [],
          operation_templates: [],
        },
        capabilities: {
          can_manage_rbac: false,
          can_manage_driver_catalogs: false,
        },
      })
    }
    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'sync-user', is_staff: true })
    }
    if (method === 'GET' && path === '/api/v2/rbac/get-effective-access/') {
      return fulfillJson(route, { clusters: [], databases: [] })
    }
    if (method === 'GET' && path === '/api/v2/rbac/list-roles/') {
      return fulfillJson(route, { roles: [], count: 0, total: 0 })
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
        databases: [{ id: DATABASE_ID, name: 'Main DB' }],
        count: 1,
        total: 1,
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/registry/') {
      return fulfillJson(route, {
        contract_version: 'pool_master_data_registry.v1',
        count: 1,
        entries: [
          {
            entity_type: 'item',
            label: 'Item',
            kind: 'canonical',
            display_order: 20,
            binding_scope_fields: ['canonical_id', 'database_id'],
            capabilities: {
              direct_binding: true,
              token_exposure: true,
              bootstrap_import: true,
              outbox_fanout: true,
              sync_outbound: true,
              sync_inbound: true,
              sync_reconcile: true,
            },
            token_contract: {
              enabled: true,
              qualifier_kind: 'none',
              qualifier_required: false,
              qualifier_options: [],
            },
            bootstrap_contract: { enabled: true, dependency_order: 20 },
            runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
          },
        ],
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/parties/') {
      return fulfillJson(route, { parties: [], ...buildListMeta(100, 0, 0) })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/items/') {
      return fulfillJson(route, { items: [], ...buildListMeta(100, 0, 0) })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/contracts/') {
      return fulfillJson(route, { contracts: [], ...buildListMeta(100, 0, 0) })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/tax-profiles/') {
      return fulfillJson(route, { tax_profiles: [], ...buildListMeta(100, 0, 0) })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/bindings/') {
      return fulfillJson(route, { bindings: [], ...buildListMeta(200, 0, 0) })
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/sync-status/') {
      return fulfillJson(route, { count: state.statuses.length, statuses: state.statuses })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/sync-conflicts/') {
      const statusFilter = String(url.searchParams.get('status') || '').trim()
      const rows = statusFilter
        ? state.conflicts.filter((item) => String(item.status) === statusFilter)
        : state.conflicts
      return fulfillJson(route, { count: rows.length, conflicts: rows })
    }

    if (method === 'POST' && path.endsWith('/retry/')) {
      const payload = request.postDataJSON() as AnyRecord
      state.actionCalls.retry.push(payload)
      const actionError = state.actionErrors?.retry
      if (actionError) {
        return fulfillJson(route, {
          code: actionError.code,
          title: 'Sync Conflict Action Invalid',
          detail: actionError.detail,
        }, actionError.status)
      }
      const id = path.split('/')[6]
      const target = state.conflicts.find((item) => String(item.id) === id)
      if (target) {
        target.status = 'retrying'
      }
      return fulfillJson(route, { conflict: target ?? null })
    }

    if (method === 'POST' && path.endsWith('/reconcile/')) {
      const payload = request.postDataJSON() as AnyRecord
      state.actionCalls.reconcile.push(payload)
      const actionError = state.actionErrors?.reconcile
      if (actionError) {
        return fulfillJson(route, {
          code: actionError.code,
          title: 'Sync Conflict Action Invalid',
          detail: actionError.detail,
        }, actionError.status)
      }
      const id = path.split('/')[6]
      const target = state.conflicts.find((item) => String(item.id) === id)
      if (target) {
        target.status = 'retrying'
      }
      return fulfillJson(route, { conflict: target ?? null })
    }

    if (method === 'POST' && path.endsWith('/resolve/')) {
      const payload = request.postDataJSON() as AnyRecord
      state.actionCalls.resolve.push(payload)
      const actionError = state.actionErrors?.resolve
      if (actionError) {
        return fulfillJson(route, {
          code: actionError.code,
          title: 'Sync Conflict Action Invalid',
          detail: actionError.detail,
        }, actionError.status)
      }
      const id = path.split('/')[6]
      const target = state.conflicts.find((item) => String(item.id) === id)
      if (target) {
        target.status = 'resolved'
      }
      return fulfillJson(route, { conflict: target ?? null })
    }

    return fulfillJson(route, {}, 200)
  })
}

function buildDefaultState(): SyncUiMockState {
  return {
    statuses: [
      {
        tenant_id: TENANT_ID,
        database_id: DATABASE_ID,
        entity_type: 'item',
        checkpoint_token: 'cp-001',
        pending_checkpoint_token: 'cp-002',
        checkpoint_status: 'active',
        pending_count: 1,
        retry_count: 1,
        conflict_pending_count: 1,
        conflict_retrying_count: 0,
        lag_seconds: 120,
        last_success_at: NOW,
        last_applied_at: NOW,
        last_error_code: '',
      },
    ],
    conflicts: [
      {
        id: 'conflict-1',
        tenant_id: TENANT_ID,
        database_id: DATABASE_ID,
        entity_type: 'item',
        status: 'pending',
        conflict_code: 'POLICY_VIOLATION',
        canonical_id: 'item-001',
        origin_system: 'ib',
        origin_event_id: 'evt-001',
        diagnostics: {},
        metadata: {},
        resolved_at: null,
        resolved_by_id: null,
        created_at: NOW,
        updated_at: NOW,
      },
    ],
    actionCalls: {
      retry: [],
      reconcile: [],
      resolve: [],
    },
  }
}

test('Pool Master Data Sync: list status/conflicts and execute conflict actions', async ({ page }) => {
  const state = buildDefaultState()
  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/master-data', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Master Data', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Open Sync zone' }).click()

  await expect(page.getByText('Sync Status', { exact: true })).toBeVisible()
  await expect(page.getByText('Conflict Queue', { exact: true })).toBeVisible()
  await expect(page.getByText('POLICY_VIOLATION', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Retry' }).first().click()
  await expect(page.getByText('Conflict переведён в retrying.', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Reconcile' }).first().click()
  await expect(page.getByText('Conflict отправлен в reconcile.', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Resolve' }).first().click()
  await expect(page.getByText('Conflict помечен как resolved.', { exact: true })).toBeVisible()

  expect(state.actionCalls.retry).toHaveLength(1)
  expect(state.actionCalls.retry[0]).toEqual({ note: 'Manual retry from Pool Master Data Sync UI' })

  expect(state.actionCalls.reconcile).toHaveLength(1)
  expect(state.actionCalls.reconcile[0]).toEqual({
    note: 'Manual reconcile from Pool Master Data Sync UI',
    reconcile_payload: { strategy: 'manual_reconcile' },
  })

  expect(state.actionCalls.resolve).toHaveLength(1)
  expect(state.actionCalls.resolve[0]).toEqual({
    resolution_code: 'MANUAL_RECONCILE',
    note: 'Manual resolve from Pool Master Data Sync UI',
    metadata: { source: 'ui' },
  })
})

test('Pool Master Data Sync: shows forbidden/not-found/error messages for conflict actions', async ({ page }) => {
  const state = buildDefaultState()
  state.actionErrors = {
    retry: {
      status: 403,
      code: 'FORBIDDEN',
      detail: 'Tenant admin only.',
    },
    reconcile: {
      status: 404,
      code: 'SYNC_CONFLICT_NOT_FOUND',
      detail: "Sync conflict 'conflict-1' does not exist.",
    },
    resolve: {
      status: 409,
      code: 'SYNC_CONFLICT_ACTION_INVALID',
      detail: 'Conflict is already resolved.',
    },
  }

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/master-data', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Open Sync zone' }).click()
  await expect(page.getByText('POLICY_VIOLATION', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Retry' }).first().click()
  await expect(page.getByText('Tenant admin only.', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Reconcile' }).first().click()
  await expect(page.getByText("Sync conflict 'conflict-1' does not exist.", { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Resolve' }).first().click()
  await expect(page.getByText('Conflict is already resolved.', { exact: true })).toBeVisible()
})
