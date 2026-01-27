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
      VITE_API_URL: 'http://127.0.0.1:5173',
      VITE_WS_HOST: '127.0.0.1:5173',
    }
    localStorage.setItem('auth_token', 'test-token')
  })
}

test('Operations: ibcmd driver options hide DBMS creds + save shortcut includes driver options (smoke)', async ({ page }) => {
  test.setTimeout(60_000)
  await setupAuth(page)

  const captured: { createShortcutBody?: AnyRecord } = {}

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'admin', is_staff: true })
    }

    if (method === 'GET' && path === '/api/v2/rbac/get-effective-access/') {
      return fulfillJson(route, {
        user: { id: 1, username: 'admin' },
        clusters: [],
        databases: [
          {
            database: { id: 'db-1', name: 'db1', cluster_id: null },
            level: 'OPERATE',
            source: 'direct',
            via_cluster_id: null,
          },
        ],
        operation_templates: [],
        workflow_templates: [],
        artifacts: [],
      })
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-roles/') {
      return fulfillJson(route, { roles: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/settings/command-schemas/audit/') {
      return fulfillJson(route, { items: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/ui/table-metadata/') {
      return fulfillJson(route, { table_id: 'unknown', version: 'test', columns: [] })
    }

    if (method === 'GET' && path === '/api/v2/operations/list-operations/') {
      return fulfillJson(route, { operations: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/operations/catalog/') {
      return fulfillJson(route, {
        items: [
          {
            id: 'ibcmd_cli',
            kind: 'operation',
            operation_type: 'ibcmd_cli',
            label: 'IBCMD guided',
            description: 'Schema-driven ibcmd command',
            driver: 'ibcmd',
            category: 'ibcmd',
            tags: ['ibcmd'],
            requires_config: true,
            has_ui_form: true,
            icon: 'ToolOutlined',
            deprecated: false,
          },
        ],
        count: 1,
      })
    }

    if (method === 'GET' && path === '/api/v2/clusters/list-clusters/') {
      return fulfillJson(route, { clusters: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/databases/list-databases/') {
      return fulfillJson(route, {
        databases: [
          {
            id: 'db-1',
            name: 'db1',
            description: '',
            host: 'localhost',
            port: 80,
            base_name: null,
            odata_url: 'http://localhost/odata',
            username: 'odata',
            password: '***',
            password_configured: true,
            server_address: 'localhost',
            server_port: 1540,
            infobase_name: 'db1',
            status: 'active',
            status_display: 'Active',
            version: '8.3.27',
            last_check: null,
            last_check_status: 'unknown',
            consecutive_failures: 0,
            avg_response_time: null,
            max_connections: 10,
            connection_timeout: 10,
            health_check_enabled: true,
            cluster_id: null,
            is_healthy: true,
            sessions_deny: null,
            scheduled_jobs_deny: null,
            denied_from: null,
            denied_to: null,
            denied_message: null,
            permission_code: null,
            denied_parameter: null,
            last_health_error: null,
            last_health_error_code: null,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
        count: 1,
        total: 1,
      })
    }

    if (method === 'GET' && path === '/api/v2/operations/driver-commands/') {
      const driver = String(url.searchParams.get('driver') || 'ibcmd')
      return fulfillJson(route, {
        driver,
        base_version: 'v-base',
        overrides_version: null,
        generated_at: '2026-01-01T00:00:00Z',
        catalog: {
          catalog_version: 2,
          driver,
          platform_version: '8.3.27',
          source: { type: 'test' },
          generated_at: '2026-01-01T00:00:00Z',
          driver_schema: {
            connection: {
              offline: {
                dbms: { kind: 'flag', flag: '--dbms', expects_value: true, required: false, label: 'DBMS', value_type: 'string' },
                db_server: { kind: 'flag', flag: '--db-server', expects_value: true, required: false, label: 'DB server', value_type: 'string' },
                db_name: { kind: 'flag', flag: '--db-name', expects_value: true, required: false, label: 'DB name', value_type: 'string' },
                db_user: { kind: 'flag', flag: '--db-user', expects_value: true, required: false, label: 'DB user', value_type: 'string', semantics: { credential_kind: 'db_user' } },
                db_pwd: { kind: 'flag', flag: '--db-pwd', expects_value: true, required: false, label: 'DB password', value_type: 'string', semantics: { credential_kind: 'db_password' } },
                log_data: { kind: 'flag', flag: '--log-data', expects_value: true, required: false, label: 'Log data', value_type: 'string' },
              },
            },
            timeout_seconds: { kind: 'int', default: 900, min: 1, max: 3600, label: 'Timeout (seconds)', required: false },
            stdin: { kind: 'text', label: 'Stdin (optional)', required: false, ui: { rows: 4 } },
            ui: {
              version: 1,
              sections: [
                { id: 'ibcmd.connection', title: 'Connection', paths: ['connection.offline.dbms', 'connection.offline.db_server', 'connection.offline.db_name', 'connection.offline.db_user', 'connection.offline.db_pwd', 'connection.offline.log_data'] },
                { id: 'ibcmd.execution', title: 'Execution', paths: ['timeout_seconds', 'stdin'] },
              ],
            },
          },
          commands_by_id: {
            'infobase.extension.list': {
              label: 'List extensions',
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

    if (method === 'GET' && path === '/api/v2/operations/list-command-shortcuts/') {
      return fulfillJson(route, { items: [], count: 0 })
    }

    if (method === 'POST' && path === '/api/v2/operations/create-command-shortcut/') {
      let body: AnyRecord = {}
      try {
        body = JSON.parse(request.postData() || '{}') as AnyRecord
      } catch (_err) {
        body = {}
      }
      captured.createShortcutBody = body
      return fulfillJson(route, { id: 'shortcut-1', ...body }, 201)
    }

    if (method === 'POST' && path === '/api/v2/operations/execute-ibcmd-cli/') {
      return fulfillJson(route, { operation_id: 'op-1', status: 'queued', total_tasks: 1, message: 'queued' }, 202)
    }

    return fulfillJson(route, {}, 200)
  })

  await page.goto('/operations', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'New Operation' }).click()

  const wizard = page.getByRole('dialog', { name: 'New Operation' })
  await expect(wizard).toBeVisible()

  await wizard.getByText('IBCMD guided', { exact: true }).click()
  await wizard.getByRole('button', { name: 'Next' }).click()

  // Target step: select the only database row.
  const row = wizard.locator('tr[data-row-key="db-1"]')
  await expect(row).toBeVisible()
  await row.locator('input.ant-checkbox-input').check({ force: true })
  await wizard.getByRole('button', { name: 'Next' }).click()

  // Configure step: pick command, ensure driver options render and credential fields are not shown.
  await expect(wizard.getByText('Configure: IBCMD CLI', { exact: false })).toBeVisible()
  const commandCombo = wizard.getByRole('combobox').first()
  await commandCombo.click({ force: true })
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')

  await expect(wizard.getByText('Driver options')).toBeVisible()
  await expect(wizard.getByText('Offline: advanced')).toBeVisible()
  await expect(wizard.getByText('DBMS', { exact: true })).toBeVisible()
  await expect(wizard.getByText('DB server', { exact: true })).toBeVisible()

  await expect(wizard.getByText('DB user')).toHaveCount(0)
  await expect(wizard.getByText('DB password')).toHaveCount(0)

  // Fill common offline driver options and save shortcut.
  await wizard.getByPlaceholder('--dbms').fill('PostgreSQL')
  await wizard.getByPlaceholder('--db-server').fill('127.0.0.1')

  await wizard.getByRole('button', { name: 'Save shortcut' }).click()
  const saveDialog = page.getByRole('dialog', { name: 'Save shortcut' })
  await expect(saveDialog).toBeVisible()
  await saveDialog.getByRole('button', { name: 'Save' }).click()

  await expect.poll(() => captured.createShortcutBody).toBeTruthy()
  const body = captured.createShortcutBody as AnyRecord
  expect(body.driver).toBe('ibcmd')
  expect(body.command_id).toBe('infobase.extension.list')
  const payload = body.payload as AnyRecord
  const cfg = (payload.config || {}) as AnyRecord
  expect((cfg.connection as AnyRecord)?.offline).toMatchObject({ dbms: 'PostgreSQL', db_server: '127.0.0.1' })
  expect((cfg.connection as AnyRecord)?.offline).not.toHaveProperty('db_user')
  expect((cfg.connection as AnyRecord)?.offline).not.toHaveProperty('db_pwd')
})
