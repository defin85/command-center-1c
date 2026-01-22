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

async function setupAuth(page: Page, isStaff: boolean) {
  await page.addInitScript((staff) => {
    ;(window as any).__CC1C_ENV__ = {
      VITE_BASE_HOST: '127.0.0.1',
      VITE_API_URL: 'http://127.0.0.1:5173',
      VITE_WS_HOST: '127.0.0.1:5173',
    }
    localStorage.setItem('auth_token', 'test-token')
    ;(window as any).__TEST_IS_STAFF__ = staff
  }, isStaff)
}

async function setupCommonApiMocks(page: Page, opts: {
  isStaff: boolean
  handlers: (method: string, path: string, url: URL, request: any) => Promise<{ status: number; data: unknown } | null>
}) {
  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'admin', is_staff: opts.isStaff })
    }

    const extra = await opts.handlers(method, path, url, request)
    if (extra) {
      return fulfillJson(route, extra.data, extra.status)
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

    if (method === 'GET' && path === '/api/v2/ui/table-metadata/') {
      return fulfillJson(route, { table_id: 'unknown', version: 'test', columns: [] })
    }

    return fulfillJson(route, {}, 200)
  })
}

test('Databases: staff bulk Extensions action shows preview confirm (smoke)', async ({ page }) => {
  await setupAuth(page, true)
  await setupCommonApiMocks(page, {
    isStaff: true,
    handlers: async (method, path, url) => {
      if (method === 'GET' && path === '/api/v2/rbac/get-effective-access/') {
        return {
          status: 200,
          data: {
            user: { id: 1, username: 'admin' },
            clusters: [],
            databases: [
              {
                database: {
                  id: '11111111-1111-1111-1111-111111111111',
                  name: 'db1',
                  cluster_id: null,
                },
                level: 'OPERATE',
                source: 'direct',
                via_cluster_id: null,
              },
            ],
          },
        }
      }

      if (method === 'GET' && path === '/api/v2/clusters/list-clusters/') {
        return { status: 200, data: { clusters: [], count: 0, total: 0 } }
      }

      if (method === 'GET' && path === '/api/v2/databases/list-databases/') {
        return {
          status: 200,
          data: {
            databases: [
              {
                id: '11111111-1111-1111-1111-111111111111',
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
          },
        }
      }

      if (method === 'GET' && path === '/api/v2/ui/action-catalog/') {
        return {
          status: 200,
          data: {
            catalog_version: 1,
            extensions: {
              actions: [
                {
                  id: 'extensions.list',
                  label: 'List extensions',
                  contexts: ['bulk_page'],
                  executor: { kind: 'ibcmd_cli', driver: 'ibcmd', command_id: 'infobase.extension.list' },
                },
              ],
            },
          },
        }
      }

      if (method === 'POST' && path === '/api/v2/ui/execution-plan/preview/') {
        return {
          status: 200,
          data: {
            execution_plan: { kind: 'ibcmd_cli', argv_masked: ['infobase', 'config', 'extension', 'list', '--db-pwd=***'] },
            bindings: [],
          },
        }
      }

      if (method === 'POST' && path === '/api/v2/operations/execute-ibcmd-cli/') {
        return { status: 202, data: { operation_id: 'op-1', status: 'queued', total_tasks: 1, message: 'queued' } }
      }

      return null
    },
  })

  await page.goto('/databases', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('db1', { exact: true })).toBeVisible()

  const firstRow = page.locator('tr[data-row-key=\"11111111-1111-1111-1111-111111111111\"]')
  await firstRow.locator('input.ant-checkbox-input').check({ force: true })

  await page.getByRole('button', { name: /Extensions/ }).click()
  await page.getByRole('menuitem', { name: 'List extensions', exact: true }).click()

  await expect(page.locator('.ant-modal-confirm-title', { hasText: 'Подтвердить действие?' })).toBeVisible()
  await expect(page.getByText('argv_masked:', { exact: false })).toBeVisible()
  await expect(page.getByText('--db-pwd=***', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Отмена', exact: true }).click()
})

test('Operations: staff details modal shows Execution Plan (smoke)', async ({ page }) => {
  await setupAuth(page, true)
  await setupCommonApiMocks(page, {
    isStaff: true,
    handlers: async (method, path, url) => {
      if (method === 'GET' && path === '/api/v2/rbac/get-effective-access/') {
        return {
          status: 200,
          data: {
            user: { id: 1, username: 'admin' },
            clusters: [],
            databases: [],
          },
        }
      }

      if (method === 'GET' && path === '/api/v2/operations/list-operations/') {
        return {
          status: 200,
          data: {
            operations: [
              {
                id: 'op-1',
                name: 'ibcmd_cli infobase.extension.list - 1 databases',
                description: '',
                operation_type: 'ibcmd_cli',
                target_entity: 'Infobase',
                status: 'failed',
                progress: 100,
                total_tasks: 1,
                completed_tasks: 0,
                failed_tasks: 1,
                payload: {},
                config: {},
                task_id: null,
                started_at: null,
                completed_at: null,
                duration_seconds: 0,
                success_rate: 0,
                created_by: 'admin',
                metadata: {},
                created_at: '2026-01-01T00:00:00Z',
                updated_at: '2026-01-01T00:00:00Z',
                database_names: [],
                tasks: [],
              },
            ],
            count: 1,
            total: 1,
          },
        }
      }

      if (method === 'GET' && path === '/api/v2/operations/get-operation/') {
        const operationId = String(url.searchParams.get('operation_id') || '')
        if (operationId !== 'op-1') {
          return { status: 404, data: { success: false, error: { code: 'OPERATION_NOT_FOUND', message: 'not found' } } }
        }
        return {
          status: 200,
          data: {
            operation: {
              id: 'op-1',
              name: 'ibcmd_cli infobase.extension.list - 1 databases',
              description: '',
              operation_type: 'ibcmd_cli',
              target_entity: 'Infobase',
              status: 'failed',
              progress: 100,
              total_tasks: 1,
              completed_tasks: 0,
              failed_tasks: 1,
              payload: {},
              config: {},
              task_id: null,
              started_at: null,
              completed_at: null,
              duration_seconds: 0,
              success_rate: 0,
              created_by: 'admin',
              metadata: {},
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
              database_names: [],
              tasks: [],
            },
            execution_plan: { kind: 'ibcmd_cli', argv_masked: ['infobase', 'config', 'extension', 'list', '--db-pwd=***'] },
            bindings: [
              { target_ref: 'command_id', source_ref: 'request.command_id', resolve_at: 'api', sensitive: false, status: 'applied' },
            ],
            tasks: [],
            progress: { total: 1, completed: 0, failed: 1, pending: 0, processing: 0, percent: 100 },
          },
        }
      }

      return null
    },
  })

  await page.goto('/operations', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('ibcmd_cli infobase.extension.list - 1 databases', { exact: true })).toBeVisible()
  const row = page.locator('tr', {
    has: page.getByText('ibcmd_cli infobase.extension.list - 1 databases', { exact: true }),
  })
  await row.getByText('Details', { exact: true }).click()

  await expect(page.getByText('Execution Plan (staff):', { exact: true })).toBeVisible()
  await expect(page.getByText('argv_masked:', { exact: false })).toBeVisible()
  await expect(page.getByText('--db-pwd=***', { exact: false })).toBeVisible()
})
