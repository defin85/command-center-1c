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
  organizations?: AnyRecord[]
  databases?: AnyRecord[]
}) {
  const organizations: AnyRecord[] = [...(state.organizations ?? [
    {
      id: '11111111-1111-1111-1111-111111111111',
      tenant_id: 't1',
      database_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      name: 'Org One',
      full_name: 'Org One LLC',
      inn: '730000000001',
      kpp: '123456789',
      status: 'active',
      external_ref: '',
      metadata: {},
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ])]
  const databases: AnyRecord[] = [...(state.databases ?? [
    { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', name: 'db1' },
    { id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', name: 'db2' },
  ])]

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

    if (method === 'GET' && path === '/api/v2/pools/organizations/') {
      return fulfillJson(route, { organizations, count: organizations.length })
    }

    if (method === 'GET' && path.startsWith('/api/v2/pools/organizations/')) {
      const id = path.replace('/api/v2/pools/organizations/', '').replace('/', '')
      const org = organizations.find((item) => String(item.id) === id)
      if (!org) {
        return fulfillJson(route, { success: false, error: { code: 'ORGANIZATION_NOT_FOUND', message: 'Not found' } }, 404)
      }
      return fulfillJson(route, { organization: org, pool_bindings: [] })
    }

    if (method === 'POST' && path === '/api/v2/pools/organizations/upsert/') {
      const payload = request.postDataJSON() as AnyRecord
      const organizationId = String(payload.organization_id || '').trim()
      const inn = String(payload.inn || '').trim()
      const name = String(payload.name || '').trim()
      const statusValue = String(payload.status || 'active').trim().toLowerCase()
      const databaseId = payload.database_id == null || String(payload.database_id).trim() === ''
        ? null
        : String(payload.database_id).trim()

      const now = '2026-01-01T00:00:00Z'
      let record = organizationId
        ? organizations.find((item) => String(item.id) === organizationId)
        : organizations.find((item) => String(item.inn) === inn)
      let created = false

      if (!record) {
        created = true
        record = {
          id: `${organizations.length + 1}1111111-1111-1111-1111-111111111111`.slice(0, 36),
          tenant_id: 't1',
          created_at: now,
          metadata: {},
        }
        organizations.push(record)
      }

      record.inn = inn
      record.name = name
      record.full_name = String(payload.full_name || '')
      record.kpp = String(payload.kpp || '')
      record.status = statusValue
      record.database_id = databaseId
      record.external_ref = String(payload.external_ref || '')
      record.updated_at = now

      return fulfillJson(route, { organization: record, created }, created ? 201 : 200)
    }

    if (method === 'POST' && path === '/api/v2/pools/organizations/sync/') {
      const payload = request.postDataJSON() as { rows?: AnyRecord[] }
      const rows = Array.isArray(payload.rows) ? payload.rows : []
      let created = 0
      let updated = 0
      let skipped = 0
      const now = '2026-01-01T00:00:00Z'

      for (const row of rows) {
        const inn = String(row.inn || '').trim()
        const name = String(row.name || '').trim()
        const statusValue = String(row.status || 'active').trim().toLowerCase()
        const databaseId = row.database_id == null || String(row.database_id).trim() === ''
          ? null
          : String(row.database_id).trim()

        const existing = organizations.find((item) => String(item.inn) === inn)
        if (!existing) {
          organizations.push({
            id: `${organizations.length + 1}2222222-2222-2222-2222-222222222222`.slice(0, 36),
            tenant_id: 't1',
            database_id: databaseId,
            name,
            full_name: String(row.full_name || ''),
            inn,
            kpp: String(row.kpp || ''),
            status: statusValue,
            external_ref: String(row.external_ref || ''),
            metadata: {},
            created_at: now,
            updated_at: now,
          })
          created += 1
          continue
        }

        if (
          String(existing.name) !== name
          || String(existing.status) !== statusValue
          || String(existing.database_id || '') !== String(databaseId || '')
        ) {
          existing.name = name
          existing.status = statusValue
          existing.database_id = databaseId
          existing.updated_at = now
          updated += 1
        } else {
          skipped += 1
        }
      }

      return fulfillJson(route, {
        stats: { created, updated, skipped },
        total_rows: rows.length,
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/') {
      return fulfillJson(route, {
        pools: [
          {
            id: '99999999-9999-9999-9999-999999999999',
            code: 'pool-main',
            name: 'Main Pool',
            is_active: true,
            metadata: {},
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
        count: 1,
      })
    }

    if (method === 'GET' && path.startsWith('/api/v2/pools/') && path.endsWith('/graph/')) {
      return fulfillJson(route, {
        pool_id: '99999999-9999-9999-9999-999999999999',
        date: '2026-01-01',
        nodes: [],
        edges: [],
      })
    }

    if (method === 'GET' && path === '/api/v2/databases/list-databases/') {
      return fulfillJson(route, {
        databases,
        count: databases.length,
        total: databases.length,
      })
    }

    return fulfillJson(route, {}, 200)
  })
}

test('Pool Catalog: staff without tenant context has mutating actions disabled', async ({ page }) => {
  await setupAuth(page)
  await setupApiMocks(page, {
    me: { id: 1, username: 'staff', is_staff: true },
    myTenants: { active_tenant_id: null, tenants: [] },
  })

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Pool Catalog', exact: true })).toBeVisible()
  await expect(page.getByText('Mutating actions are disabled', { exact: true })).toBeVisible()
  await expect(page.getByTestId('pool-catalog-add-org')).toBeDisabled()
  await expect(page.getByTestId('pool-catalog-edit-org')).toBeDisabled()
  await expect(page.getByTestId('pool-catalog-sync-orgs')).toBeDisabled()
})

test('Pool Catalog: non-staff can create, edit and sync organizations without extra UI blocking', async ({ page }) => {
  await setupAuth(page)
  await setupApiMocks(page, {
    me: { id: 1, username: 'user', is_staff: false },
    myTenants: { active_tenant_id: null, tenants: [] },
  })

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Pool Catalog', exact: true })).toBeVisible()
  await expect(page.getByTestId('pool-catalog-add-org')).toBeEnabled()

  await page.getByTestId('pool-catalog-add-org').click()
  await page.getByLabel('INN').fill('730000000555')
  await page.locator('#name').fill('Created Org')
  await page.getByRole('button', { name: 'Save', exact: true }).click()

  await expect(page.getByText('Created Org', { exact: true })).toBeVisible()

  await page.locator('.ant-table-tbody tr').filter({ hasText: 'Created Org' }).first().click()
  await page.getByTestId('pool-catalog-edit-org').click()
  await page.locator('#name').fill('Created Org Updated')
  await page.getByRole('button', { name: 'Save', exact: true }).click()

  await expect(page.getByText('Created Org Updated', { exact: true })).toBeVisible()

  await page.getByTestId('pool-catalog-sync-orgs').click()
  await page.getByTestId('pool-catalog-sync-input').fill(
    '{"rows":[{"inn":"730000000555","name":"Created Org Synced"},{"inn":"730000000556","name":"Synced Org"}]}'
  )
  await page.getByRole('button', { name: 'Run sync', exact: true }).click()

  await expect(page.getByText('Sync completed', { exact: true })).toBeVisible()
  await expect(page.getByText(/total_rows/i)).toBeVisible()
  await expect(page.getByText('Synced Org', { exact: true })).toBeVisible()
})
