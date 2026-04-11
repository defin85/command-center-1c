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
  launches: AnyRecord[]
  actionCalls: {
    retry: AnyRecord[]
    reconcile: AnyRecord[]
    resolve: AnyRecord[]
    launch: AnyRecord[]
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

async function expectNoHorizontalOverflow(page: Page) {
  const hasOverflow = await page.evaluate(() => {
    const root = document.documentElement
    return root.scrollWidth - root.clientWidth > 1
  })
  expect(hasOverflow).toBe(false)
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
          can_manage_runtime_controls: false,
        },
      })
    }
    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'sync-user', is_staff: true })
    }
    if (method === 'GET' && path === '/api/v2/rbac/get-effective-access/') {
      return fulfillJson(route, { clusters: [], databases: [] })
    }
    if (method === 'GET' && path === '/api/v2/rbac/ref-clusters/') {
      return fulfillJson(route, {
        clusters: [{ id: 'cluster-1', name: 'Main Cluster' }],
        count: 1,
        total: 1,
      })
    }
    if (method === 'GET' && path === '/api/v2/rbac/ref-databases/') {
      return fulfillJson(route, {
        databases: [{ id: DATABASE_ID, name: 'Main DB', cluster_id: 'cluster-1' }],
        count: 1,
        total: 1,
      })
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
        count: 3,
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
          {
            entity_type: 'gl_account',
            label: 'GL Account',
            kind: 'canonical',
            display_order: 45,
            binding_scope_fields: ['canonical_id', 'database_id', 'chart_identity'],
            capabilities: {
              direct_binding: true,
              token_exposure: true,
              bootstrap_import: true,
              outbox_fanout: false,
              sync_outbound: false,
              sync_inbound: false,
              sync_reconcile: false,
            },
            token_contract: {
              enabled: true,
              qualifier_kind: 'none',
              qualifier_required: false,
              qualifier_options: [],
            },
            bootstrap_contract: { enabled: true, dependency_order: 35 },
            runtime_consumers: ['bindings', 'bootstrap_import', 'token_catalog', 'token_parser'],
          },
          {
            entity_type: 'gl_account_set',
            label: 'GL Account Set',
            kind: 'profile',
            display_order: 50,
            binding_scope_fields: [],
            capabilities: {
              direct_binding: false,
              token_exposure: false,
              bootstrap_import: false,
              outbox_fanout: false,
              sync_outbound: false,
              sync_inbound: false,
              sync_reconcile: false,
            },
            token_contract: {
              enabled: false,
              qualifier_kind: 'none',
              qualifier_required: false,
              qualifier_options: [],
            },
            bootstrap_contract: { enabled: false, dependency_order: null },
            runtime_consumers: ['profiles'],
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
    if (method === 'GET' && path === '/api/v2/pools/master-data/gl-accounts/') {
      return fulfillJson(route, {
        gl_accounts: [
          {
            id: 'gl-account-1',
            tenant_id: TENANT_ID,
            canonical_id: 'gl-account-001',
            code: '10.01',
            name: 'Main Account',
            chart_identity: 'ChartOfAccounts_Main',
            config_name: 'Accounting Enterprise',
            config_version: '3.0.1',
            metadata: {},
            created_at: NOW,
            updated_at: NOW,
          },
        ],
        ...buildListMeta(100, 0, 1),
      })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/gl-accounts/gl-account-1/') {
      return fulfillJson(route, {
        gl_account: {
          id: 'gl-account-1',
          tenant_id: TENANT_ID,
          canonical_id: 'gl-account-001',
          code: '10.01',
          name: 'Main Account',
          chart_identity: 'ChartOfAccounts_Main',
          config_name: 'Accounting Enterprise',
          config_version: '3.0.1',
          metadata: {},
          created_at: NOW,
          updated_at: NOW,
        },
      })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/gl-account-sets/') {
      return fulfillJson(route, {
        gl_account_sets: [
          {
            gl_account_set_id: 'gl-set-1',
            canonical_id: 'gl-set-001',
            name: 'Quarter Scope',
            description: 'Draft for Q1',
            chart_identity: 'ChartOfAccounts_Main',
            config_name: 'Accounting Enterprise',
            config_version: '3.0.1',
            draft_members_count: 1,
            published_revision_number: 1,
            published_revision_id: 'gl-set-rev-1',
            metadata: {},
            created_at: NOW,
            updated_at: NOW,
          },
        ],
        ...buildListMeta(100, 0, 1),
      })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/gl-account-sets/gl-set-1/') {
      return fulfillJson(route, {
        gl_account_set: {
          gl_account_set_id: 'gl-set-1',
          canonical_id: 'gl-set-001',
          name: 'Quarter Scope',
          description: 'Draft for Q1',
          chart_identity: 'ChartOfAccounts_Main',
          config_name: 'Accounting Enterprise',
          config_version: '3.0.1',
          draft_members_count: 1,
          published_revision_number: 1,
          published_revision_id: 'gl-set-rev-1',
          metadata: {},
          created_at: NOW,
          updated_at: NOW,
          draft_members: [
            {
              gl_account_id: 'gl-account-1',
              canonical_id: 'gl-account-001',
              code: '10.01',
              name: 'Main Account',
              chart_identity: 'ChartOfAccounts_Main',
              config_name: 'Accounting Enterprise',
              config_version: '3.0.1',
              sort_order: 0,
              metadata: {},
            },
          ],
          revisions: [
            {
              gl_account_set_revision_id: 'gl-set-rev-1',
              gl_account_set_id: 'gl-set-1',
              contract_version: 'pool_master_gl_account_set.v1',
              revision_number: 1,
              name: 'Quarter Scope',
              description: 'Draft for Q1',
              chart_identity: 'ChartOfAccounts_Main',
              config_name: 'Accounting Enterprise',
              config_version: '3.0.1',
              members: [
                {
                  gl_account_id: 'gl-account-1',
                  canonical_id: 'gl-account-001',
                  code: '10.01',
                  name: 'Main Account',
                  chart_identity: 'ChartOfAccounts_Main',
                  config_name: 'Accounting Enterprise',
                  config_version: '3.0.1',
                  sort_order: 0,
                  metadata: {},
                },
              ],
              metadata: {},
              created_by: 'sync-user',
              created_at: NOW,
            },
          ],
          published_revision: {
            gl_account_set_revision_id: 'gl-set-rev-1',
            gl_account_set_id: 'gl-set-1',
            contract_version: 'pool_master_gl_account_set.v1',
            revision_number: 1,
            name: 'Quarter Scope',
            description: 'Draft for Q1',
            chart_identity: 'ChartOfAccounts_Main',
            config_name: 'Accounting Enterprise',
            config_version: '3.0.1',
            members: [
              {
                gl_account_id: 'gl-account-1',
                canonical_id: 'gl-account-001',
                code: '10.01',
                name: 'Main Account',
                chart_identity: 'ChartOfAccounts_Main',
                config_name: 'Accounting Enterprise',
                config_version: '3.0.1',
                sort_order: 0,
                metadata: {},
              },
            ],
            metadata: {},
            created_by: 'sync-user',
            created_at: NOW,
          },
        },
      })
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
    if (method === 'GET' && path === '/api/v2/pools/master-data/sync-launches/') {
      return fulfillJson(route, {
        launches: state.launches,
        count: state.launches.length,
        limit: 20,
        offset: 0,
      })
    }
    if (method === 'GET' && path.startsWith('/api/v2/pools/master-data/sync-launches/')) {
      const launchId = path.split('/')[6]
      const launch = state.launches.find((item) => String(item.id) === launchId) ?? null
      return fulfillJson(route, { launch }, launch ? 200 : 404)
    }
    if (method === 'POST' && path === '/api/v2/pools/master-data/sync-launches/') {
      const payload = request.postDataJSON() as AnyRecord
      state.actionCalls.launch.push(payload)
      const launch = {
        id: 'launch-1',
        tenant_id: TENANT_ID,
        mode: payload.mode ?? 'inbound',
        target_mode: payload.target_mode ?? 'database_set',
        cluster_id: payload.cluster_id ?? null,
        database_ids: Array.isArray(payload.database_ids) ? payload.database_ids : [DATABASE_ID],
        entity_scope: Array.isArray(payload.entity_scope) ? payload.entity_scope : ['item'],
        status: 'completed',
        workflow_execution_id: 'wf-launch-1',
        operation_id: 'op-launch-1',
        requested_by_id: 1,
        requested_by_username: 'sync-user',
        last_error_code: '',
        last_error: '',
        aggregate_counters: {
          total_items: 1,
          scheduled: 1,
          coalesced: 0,
          skipped: 0,
          failed: 0,
          completed: 1,
        },
        progress: {
          total_items: 1,
          scheduled: 1,
          coalesced: 0,
          skipped: 0,
          failed: 0,
          completed: 1,
          terminal_items: 1,
          completion_ratio: 1,
        },
        child_job_status_counts: { completed: 1 },
        audit_trail: [],
        items: [
          {
            id: 'launch-item-1',
            database_id: DATABASE_ID,
            database_name: 'Main DB',
            cluster_id: 'cluster-1',
            entity_type: Array.isArray(payload.entity_scope) && payload.entity_scope.length > 0
              ? payload.entity_scope[0]
              : 'item',
            status: 'scheduled',
            reason_code: '',
            reason_detail: '',
            child_job_id: 'sync-job-1',
            child_job_status: 'queued',
            child_workflow_execution_id: 'wf-child-1',
            child_operation_id: 'op-child-1',
            metadata: {},
            created_at: NOW,
            updated_at: NOW,
          },
        ],
        created_at: NOW,
        updated_at: NOW,
      }
      state.launches = [launch]
      return fulfillJson(route, { launch })
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
    launches: [],
    actionCalls: {
      retry: [],
      reconcile: [],
      resolve: [],
      launch: [],
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

test('Pool Master Data Sync: creates manual launch and shows launch detail/history', async ({ page }) => {
  const state = buildDefaultState()
  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/master-data?tab=sync', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Master Data', exact: true })).toBeVisible()
  await expect(page.getByText('Launch History', { exact: true })).toBeVisible()

  await page.getByTestId('sync-launch-open-drawer').click()
  await page.getByTestId('sync-launch-database-set').click()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await page.getByTestId('sync-launch-submit').click()

  await expect(page.getByText('Launch Detail', { exact: true })).toBeVisible()
  await expect(page.getByText('launch-1', { exact: true })).toBeVisible()
  await expect(page.getByText('sync-job-1', { exact: true })).toBeVisible()

  expect(state.actionCalls.launch).toHaveLength(1)
  expect(state.actionCalls.launch[0]).toEqual({
    mode: 'inbound',
    target_mode: 'database_set',
    database_ids: [DATABASE_ID],
    entity_scope: ['item'],
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

test('Pool Master Data Accounts: restores GL Account Set zone from deep-link route state', async ({ page }) => {
  const state = buildDefaultState()
  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/master-data?tab=gl-account-set&detail=1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Pool Master Data', exact: true })).toBeVisible()
  await expect(page.getByText('Current zone: GL Account Set')).toBeVisible()
  await expect(page.getByTestId('pool-master-data-gl-account-set-selected-id')).toHaveText('gl-set-1')
  await expect(page.getByText('Published r1').first()).toBeVisible()
})

test('Pool Master Data Accounts: mobile shell opens GL Account zone without horizontal overflow', async ({ page }) => {
  const state = buildDefaultState()
  await setupAuth(page)
  await setupApiMocks(page, state)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/pools/master-data', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Master Data', exact: true })).toBeVisible()
  await expectNoHorizontalOverflow(page)

  await page.getByRole('button', { name: 'Open GL Account zone' }).click()

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('pool-master-data-gl-account-selected-id')).toHaveText('gl-account-1')
  await expect(detailDrawer.getByText('Compatible class').first()).toBeVisible()
  await expectNoHorizontalOverflow(page)
})
