import { test, expect, type Page, type Route } from '@playwright/test'

type AnyRecord = Record<string, unknown>

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>
  }
}

async function fulfillJson(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
    headers: { 'cache-control': 'no-store' },
  })
}

async function setupAuth(page: Page, opts?: { activeTenantId?: string }) {
  await page.addInitScript((cfg?: { activeTenantId?: string }) => {
    window.__CC1C_ENV__ = {
      VITE_BASE_HOST: '127.0.0.1',
      VITE_API_URL: 'http://127.0.0.1:15173',
      VITE_WS_HOST: '127.0.0.1:15173',
    }
    localStorage.setItem('auth_token', 'test-token')
    if (cfg?.activeTenantId) {
      localStorage.setItem('active_tenant_id', cfg.activeTenantId)
    }
  }, opts)
}

async function setupApiMocks(page: Page, state: {
  me?: AnyRecord
  myTenants?: AnyRecord
  overview: AnyRecord[]
  overviewByDatabaseId?: Record<string, AnyRecord[]>
  drilldownByName: Record<string, AnyRecord[]>
  planResponse?: AnyRecord
  applyResponse?: AnyRecord
  onPlanHeaders?: (headers: Record<string, string>) => void
  onApplyHeaders?: (headers: Record<string, string>) => void
}) {
  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, state.me ?? { id: 1, username: 'user', is_staff: false })
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
      return fulfillJson(route, state.myTenants ?? { active_tenant_id: null, tenants: [] })
    }

    if (method === 'GET' && path === '/api/v2/clusters/list-clusters/') {
      return fulfillJson(route, { clusters: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/databases/list-databases/') {
      return fulfillJson(route, {
        databases: [
          { id: '11111111-1111-1111-1111-111111111111', name: 'db1' },
          { id: '22222222-2222-2222-2222-222222222222', name: 'db2' },
        ],
        count: 2,
        total: 2,
      })
    }

    if (method === 'GET' && path === '/api/v2/extensions/overview/') {
      const status = (url.searchParams.get('status') || '').trim().toLowerCase()
      const search = (url.searchParams.get('search') || '').trim().toLowerCase()
      const version = (url.searchParams.get('version') || '').trim()
      const databaseId = (url.searchParams.get('database_id') || '').trim()
      let rows = databaseId && state.overviewByDatabaseId ? [...(state.overviewByDatabaseId[databaseId] || [])] : [...state.overview]
      if (search) {
        rows = rows.filter((r) => String(r.name || '').toLowerCase().includes(search))
      }
      if (version) {
        rows = rows.filter((r) => {
          const versions = r['versions']
          if (!Array.isArray(versions)) return false
          return versions.some((v) => {
            if (!v || typeof v !== 'object') return false
            const maybeVersion = (v as Record<string, unknown>)['version']
            return String(maybeVersion ?? '') === version
          })
        })
      }
      if (status) {
        const key = `${status}_count`
        rows = rows.filter((r) => Number(r[key] || 0) > 0)
      }
      return fulfillJson(route, {
        extensions: rows,
        count: rows.length,
        total: rows.length,
        total_databases: 2,
      })
    }

    if (method === 'GET' && path === '/api/v2/extensions/overview/databases/') {
      const name = String(url.searchParams.get('name') || '')
      const status = (url.searchParams.get('status') || '').trim().toLowerCase()
      const databaseId = (url.searchParams.get('database_id') || '').trim()
      let rows = [...(state.drilldownByName[name] || [])]
      if (status) {
        rows = rows.filter((r) => String(r.status || '') === status)
      }
      if (databaseId) {
        rows = rows.filter((r) => String((r as Record<string, unknown>).database_id || '') === databaseId)
      }
      return fulfillJson(route, { databases: rows, count: rows.length, total: rows.length })
    }

    if (method === 'POST' && path === '/api/v2/extensions/plan/') {
      try {
        state.onPlanHeaders?.(request.headers() as Record<string, string>)
      } catch (_err) {
        // ignore
      }
      return fulfillJson(route, state.planResponse ?? {
        plan_id: 'plan-1',
        preconditions: {},
        execution_plan: { kind: 'ibcmd_cli', argv_masked: ['ibcmd', 'infobase', 'extension', 'set'] },
        bindings: [],
      })
    }

    if (method === 'POST' && path === '/api/v2/extensions/apply/') {
      try {
        state.onApplyHeaders?.(request.headers() as Record<string, string>)
      } catch (_err) {
        // ignore
      }
      return fulfillJson(route, state.applyResponse ?? { operation_id: 'op-1', status: 'queued' }, 202)
    }

    return fulfillJson(route, {}, 200)
  })
}

test('Extensions: overview renders + drill-down opens (smoke)', async ({ page }) => {
  await setupAuth(page)
  const overview: AnyRecord[] = [
    {
      name: 'ExtA',
      purpose: 'patch',
      flags: {
        active: { policy: true, observed: { true_count: 1, false_count: 0, unknown_count: 0, state: 'on' }, drift_count: 0, unknown_drift_count: 0 },
        safe_mode: { policy: true, observed: { true_count: 1, false_count: 0, unknown_count: 0, state: 'on' }, drift_count: 0, unknown_drift_count: 0 },
        unsafe_action_protection: { policy: false, observed: { true_count: 0, false_count: 1, unknown_count: 0, state: 'off' }, drift_count: 0, unknown_drift_count: 0 },
      },
      installed_count: 1,
      active_count: 1,
      inactive_count: 0,
      missing_count: 1,
      unknown_count: 0,
      versions: [{ version: '1.0', count: 1 }],
      latest_snapshot_at: '2026-01-01T00:00:00Z',
    },
    {
      name: 'ExtB',
      purpose: 'add-on',
      flags: {
        active: { policy: null, observed: { true_count: 0, false_count: 2, unknown_count: 0, state: 'off' }, drift_count: 0, unknown_drift_count: 0 },
        safe_mode: { policy: null, observed: { true_count: 0, false_count: 0, unknown_count: 2, state: 'unknown' }, drift_count: 0, unknown_drift_count: 0 },
        unsafe_action_protection: { policy: null, observed: { true_count: 0, false_count: 0, unknown_count: 2, state: 'unknown' }, drift_count: 0, unknown_drift_count: 0 },
      },
      installed_count: 2,
      active_count: 0,
      inactive_count: 2,
      missing_count: 0,
      unknown_count: 0,
      versions: [{ version: '2.0', count: 2 }],
      latest_snapshot_at: '2026-01-01T00:00:00Z',
    },
    ...Array.from({ length: 53 }).map((_, idx) => ({
      name: `Ext${String(idx).padStart(2, '0')}`,
      installed_count: 0,
      active_count: 0,
      inactive_count: 0,
      missing_count: 2,
      unknown_count: 0,
      versions: [],
      latest_snapshot_at: null,
    })),
  ]
  await setupApiMocks(page, {
    overview,
    overviewByDatabaseId: {
      '11111111-1111-1111-1111-111111111111': [overview[0]],
      '22222222-2222-2222-2222-222222222222': [overview[1]],
    },
    drilldownByName: {
      ExtA: [
        { database_id: '11111111-1111-1111-1111-111111111111', database_name: 'db1', cluster_id: null, cluster_name: '', status: 'active', version: '1.0', snapshot_updated_at: '2026-01-01T00:00:00Z', flags: { active: true, safe_mode: true, unsafe_action_protection: false } },
        { database_id: '22222222-2222-2222-2222-222222222222', database_name: 'db2', cluster_id: null, cluster_name: '', status: 'missing', version: null, snapshot_updated_at: '2026-01-01T00:00:00Z', flags: { active: null, safe_mode: null, unsafe_action_protection: null } },
      ],
    },
  })

  await page.goto('/extensions', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Extensions', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'ExtA', exact: true })).toBeVisible()
  await expect(page.getByText('patch', { exact: true })).toBeVisible()

  await page.getByTestId('extensions-overview-version').fill('2.0')
  await expect(page.getByRole('button', { name: 'ExtA', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'ExtB', exact: true })).toBeVisible()

  await page.getByTestId('extensions-overview-version').fill('')
  await expect(page.getByRole('button', { name: 'ExtA', exact: true })).toBeVisible()

  await page.getByRole('listitem', { name: '2' }).click()
  await expect(page.getByRole('button', { name: 'ExtA', exact: true })).toHaveCount(0)

  const requestPromise = page.waitForRequest((r) => (
    r.method() === 'GET' &&
    r.url().includes('/api/v2/extensions/overview/') &&
    r.url().includes('database_id=')
  ))
  await page.getByTestId('extensions-overview-database').click()
  await page.keyboard.type('db1')
  await page.keyboard.press('Enter')
  const dbFilteredReq = await requestPromise
  expect(new URL(dbFilteredReq.url()).searchParams.get('database_id')).toBe('11111111-1111-1111-1111-111111111111')

  await expect(page.getByRole('button', { name: 'ExtA', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'ExtB', exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: 'ExtA', exact: true }).click()
  await expect(page.getByText('Extension: ExtA', { exact: true })).toBeVisible()

  await expect(page.getByRole('button', { name: 'db1', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'db2', exact: true })).toBeVisible()

  const drawerDbRequestPromise = page.waitForRequest((r) => (
    r.method() === 'GET' &&
    r.url().includes('/api/v2/extensions/overview/databases/') &&
    r.url().includes('database_id=')
  ))
  await page.getByTestId('extensions-drawer-database').click()
  await page.keyboard.type('db1')
  await page.keyboard.press('Enter')
  const drawerDbFilteredReq = await drawerDbRequestPromise
  expect(new URL(drawerDbFilteredReq.url()).searchParams.get('database_id')).toBe('11111111-1111-1111-1111-111111111111')
  await expect(page.getByRole('button', { name: 'db1', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'db2', exact: true })).toHaveCount(0)
})

test('Extensions: staff without tenant context disables mutating actions', async ({ page }) => {
  await setupAuth(page)

  await setupApiMocks(page, {
    me: { id: 1, username: 'staff', is_staff: true },
    myTenants: { active_tenant_id: null, tenants: [] },
    overview: [
      {
        name: 'ExtA',
        purpose: 'patch',
        flags: {
          active: { policy: true, observed: { true_count: 1, false_count: 0, unknown_count: 0, state: 'on' }, drift_count: 0, unknown_drift_count: 0 },
          safe_mode: { policy: null, observed: { true_count: 0, false_count: 0, unknown_count: 1, state: 'unknown' }, drift_count: 0, unknown_drift_count: 0 },
          unsafe_action_protection: { policy: null, observed: { true_count: 0, false_count: 0, unknown_count: 1, state: 'unknown' }, drift_count: 0, unknown_drift_count: 0 },
        },
        installed_count: 1,
        active_count: 1,
        inactive_count: 0,
        missing_count: 0,
        unknown_count: 0,
        versions: [{ version: '1.0', count: 1 }],
        latest_snapshot_at: '2026-01-01T00:00:00Z',
      },
    ],
    drilldownByName: {
      ExtA: [
        { database_id: '11111111-1111-1111-1111-111111111111', database_name: 'db1', cluster_id: null, cluster_name: '', status: 'active', version: '1.0', snapshot_updated_at: '2026-01-01T00:00:00Z', flags: { active: true, safe_mode: null, unsafe_action_protection: null } },
      ],
    },
  })

  await page.goto('/extensions', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'ExtA', exact: true }).click()
  await expect(page.getByText('Mutating actions are disabled', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Apply flags policy', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Adopt from database', exact: true })).toBeDisabled()
})

test('Extensions: apply policy triggers plan/apply with tenant header', async ({ page }) => {
  await setupAuth(page, { activeTenantId: 't1' })

  const seenTenantHeaders: string[] = []

  const overview: AnyRecord[] = [
    {
      name: 'ExtA',
      purpose: 'patch',
      flags: {
        active: { policy: true, observed: { true_count: 2, false_count: 0, unknown_count: 0, state: 'on' }, drift_count: 0, unknown_drift_count: 0 },
        safe_mode: { policy: true, observed: { true_count: 2, false_count: 0, unknown_count: 0, state: 'on' }, drift_count: 0, unknown_drift_count: 0 },
        unsafe_action_protection: { policy: false, observed: { true_count: 0, false_count: 2, unknown_count: 0, state: 'off' }, drift_count: 0, unknown_drift_count: 0 },
      },
      installed_count: 2,
      active_count: 2,
      inactive_count: 0,
      missing_count: 0,
      unknown_count: 0,
      versions: [{ version: '1.0', count: 2 }],
      latest_snapshot_at: '2026-01-01T00:00:00Z',
    },
  ]
  await setupApiMocks(page, {
    me: { id: 1, username: 'staff', is_staff: true },
    myTenants: { active_tenant_id: 't1', tenants: [{ id: 't1', name: 'Default' }] },
    overview,
    drilldownByName: {
      ExtA: [
        { database_id: '11111111-1111-1111-1111-111111111111', database_name: 'db1', cluster_id: null, cluster_name: '', status: 'active', version: '1.0', snapshot_updated_at: '2026-01-01T00:00:00Z', flags: { active: true, safe_mode: true, unsafe_action_protection: false } },
        { database_id: '22222222-2222-2222-2222-222222222222', database_name: 'db2', cluster_id: null, cluster_name: '', status: 'active', version: '1.0', snapshot_updated_at: '2026-01-01T00:00:00Z', flags: { active: true, safe_mode: true, unsafe_action_protection: false } },
      ],
    },
    onPlanHeaders: (headers) => {
      if (headers['x-cc1c-tenant-id']) seenTenantHeaders.push(headers['x-cc1c-tenant-id'])
    },
    onApplyHeaders: (headers) => {
      if (headers['x-cc1c-tenant-id']) seenTenantHeaders.push(headers['x-cc1c-tenant-id'])
    },
  })

  await page.goto('/extensions', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'ExtA', exact: true }).click()
  await expect(page.getByText('Extension: ExtA', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Apply flags policy', exact: true }).click()
  await expect(page.locator('.ant-modal-confirm-title').filter({ hasText: 'Apply flags policy?' })).toBeVisible()
  await page.getByRole('button', { name: 'Apply', exact: true }).click()

  expect(seenTenantHeaders).toEqual(['t1', 't1'])
})
