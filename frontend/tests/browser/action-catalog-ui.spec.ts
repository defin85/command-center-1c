import { test, expect, type Page } from '@playwright/test'

type AnyRecord = Record<string, any>

async function fulfillJson(route: any, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
    headers: { 'cache-control': 'no-store' },
  })
}

async function setupAuth(page: Page) {
  await page.addInitScript(() => {
    ;(window as any).__CC1C_ENV__ = {
      VITE_BASE_HOST: '127.0.0.1',
      VITE_API_URL: 'http://127.0.0.1:5173',
      VITE_WS_HOST: '127.0.0.1:5173',
    }
    localStorage.setItem('auth_token', 'test-token')
  })
}

async function setupApiMocks(page: Page, state: { runtimeSettings: AnyRecord[] }) {
  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'admin', is_staff: true })
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

    if (method === 'GET' && path === '/api/v2/settings/runtime/') {
      return fulfillJson(route, { settings: state.runtimeSettings })
    }

    if (method === 'GET' && path === '/api/v2/operations/driver-commands/') {
      const driver = String(url.searchParams.get('driver') || 'ibcmd')
      return fulfillJson(route, {
        driver,
        base_version: 'v1',
        overrides_version: null,
        generated_at: '2026-01-01T00:00:00Z',
        catalog: {
          catalog_version: 2,
          driver,
          platform_version: '8.3.27',
          source: { type: 'test' },
          generated_at: '2026-01-01T00:00:00Z',
          commands_by_id: {
            'infobase.extension.list': {
              label: 'list extensions',
              description: 'List extensions',
              argv: ['infobase', 'extension', 'list'],
              scope: 'per_database',
              risk_level: 'safe',
              params_by_name: {},
            },
          },
        },
      })
    }

    return fulfillJson(route, {}, 200)
  })
}

test('Action Catalog: loads ui.action_catalog and switches modes (smoke)', async ({ page }) => {
  await setupAuth(page)
  await setupApiMocks(page, {
    runtimeSettings: [
      {
        key: 'ui.action_catalog',
        value_type: 'json',
        description: 'UI action catalog bindings (v1).',
        min_value: null,
        max_value: null,
        default: { catalog_version: 1, extensions: { actions: [] } },
        value: {
          catalog_version: 1,
          extensions: {
            actions: [
              {
                id: 'extensions.list',
                label: 'List extensions',
                contexts: ['database_card'],
                executor: { kind: 'ibcmd_cli', driver: 'ibcmd', command_id: 'infobase.extension.list' },
              },
              {
                id: 'extensions.workflow',
                label: 'Workflow',
                contexts: ['database_card'],
                executor: { kind: 'workflow', workflow_id: '11111111-1111-1111-1111-111111111111' },
              },
            ],
          },
        },
      },
    ],
  })

  await page.goto('/settings/action-catalog', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Action Catalog', exact: true })).toBeVisible()
  await expect(page.getByTestId('action-catalog-actions-count')).toHaveText('2')
  await expect(page.getByText('extensions.list', { exact: true })).toBeVisible()

  await page.getByTestId('action-catalog-add').click()
  await page.getByTestId('action-catalog-editor-id').fill('extensions.new')
  await page.getByTestId('action-catalog-editor-label').fill('New action')
  await page.getByTestId('action-catalog-editor-command-id').click()
  await page.keyboard.type('infobase.extension.list')
  await page.keyboard.press('Enter')
  await page.getByTestId('action-catalog-editor-apply').click()

  await expect(page.getByTestId('action-catalog-actions-count')).toHaveText('3')
  await expect(page.getByTestId('action-catalog-dirty')).toBeVisible()
  await expect(page.getByText('extensions.new', { exact: true })).toBeVisible()

  const newRow = page.locator('tr', { has: page.getByText('extensions.new', { exact: true }) })
  await newRow.getByRole('button', { name: 'Disable', exact: true }).click()
  await expect(page.getByTestId('action-catalog-actions-count')).toHaveText('2')
  await expect(page.getByTestId('action-catalog-disabled-count')).toContainText('Disabled: 1')

  await page.getByTestId('action-catalog-restore-last').click()
  await expect(page.getByTestId('action-catalog-actions-count')).toHaveText('3')
  await expect(page.getByText('extensions.new', { exact: true })).toBeVisible()

  await page.getByRole('tab', { name: 'Raw JSON', exact: true }).click()
  await expect(page.getByText('ui.action_catalog', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Format', exact: true })).toBeVisible()
})
