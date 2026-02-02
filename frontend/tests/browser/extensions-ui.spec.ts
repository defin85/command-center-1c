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

async function setupAuth(page: Page) {
  await page.addInitScript(() => {
    window.__CC1C_ENV__ = {
      VITE_BASE_HOST: '127.0.0.1',
      VITE_API_URL: 'http://127.0.0.1:15173',
      VITE_WS_HOST: '127.0.0.1:15173',
    }
    localStorage.setItem('auth_token', 'test-token')
  })
}

async function setupApiMocks(page: Page, state: {
  overview: AnyRecord[]
  drilldownByName: Record<string, AnyRecord[]>
}) {
  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'user', is_staff: false })
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

    if (method === 'GET' && path === '/api/v2/clusters/list-clusters/') {
      return fulfillJson(route, { clusters: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/extensions/overview/') {
      const status = (url.searchParams.get('status') || '').trim().toLowerCase()
      const search = (url.searchParams.get('search') || '').trim().toLowerCase()
      const version = (url.searchParams.get('version') || '').trim()
      let rows = [...state.overview]
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
      let rows = [...(state.drilldownByName[name] || [])]
      if (status) {
        rows = rows.filter((r) => String(r.status || '') === status)
      }
      return fulfillJson(route, { databases: rows, count: rows.length, total: rows.length })
    }

    return fulfillJson(route, {}, 200)
  })
}

test('Extensions: overview renders + drill-down opens (smoke)', async ({ page }) => {
  await setupAuth(page)
  await setupApiMocks(page, {
    overview: [
      {
        name: 'ExtA',
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
        installed_count: 2,
        active_count: 0,
        inactive_count: 2,
        missing_count: 0,
        unknown_count: 0,
        versions: [{ version: '2.0', count: 2 }],
        latest_snapshot_at: '2026-01-01T00:00:00Z',
      },
    ],
    drilldownByName: {
      ExtA: [
        { database_id: '11111111-1111-1111-1111-111111111111', database_name: 'db1', cluster_id: null, cluster_name: '', status: 'active', version: '1.0', snapshot_updated_at: '2026-01-01T00:00:00Z' },
        { database_id: '22222222-2222-2222-2222-222222222222', database_name: 'db2', cluster_id: null, cluster_name: '', status: 'missing', version: null, snapshot_updated_at: '2026-01-01T00:00:00Z' },
      ],
    },
  })

  await page.goto('/extensions', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Extensions', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'ExtA', exact: true })).toBeVisible()

  await page.getByTestId('extensions-overview-version').fill('2.0')
  await expect(page.getByRole('button', { name: 'ExtA', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'ExtB', exact: true })).toBeVisible()

  await page.getByTestId('extensions-overview-version').fill('')
  await expect(page.getByRole('button', { name: 'ExtA', exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'ExtA', exact: true }).click()
  await expect(page.getByText('Extension: ExtA', { exact: true })).toBeVisible()

  await expect(page.getByText('db1', { exact: true })).toBeVisible()
  await expect(page.getByText('db2', { exact: true })).toBeVisible()
})
