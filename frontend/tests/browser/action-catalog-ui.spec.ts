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

async function setupApiMocks(
  page: Page,
  state: {
    runtimeSettings: AnyRecord[]
    patchFailCount?: number
    patchFailMessages?: string[]
    editorHints?: AnyRecord
  }
) {
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

    if (method === 'GET' && path === '/api/v2/tenants/list-my-tenants/') {
      return fulfillJson(route, {
        active_tenant_id: null,
        tenants: [
          { id: 't1', slug: 't1', name: 'Tenant 1', role: 'owner' },
        ],
      })
    }

    if (method === 'POST' && path === '/api/v2/tenants/set-active/') {
      let payload: AnyRecord = {}
      try {
        payload = JSON.parse(request.postData() || '{}') as AnyRecord
      } catch (_err) {
        payload = {}
      }
      const tenantId = typeof payload.tenant_id === 'string' ? payload.tenant_id : 't1'
      return fulfillJson(route, { active_tenant_id: tenantId })
    }

    if (method === 'GET' && path === '/api/v2/settings/command-schemas/audit/') {
      return fulfillJson(route, { items: [], count: 0, total: 0 })
    }

    if (method === 'GET' && (path === '/api/v2/settings/runtime/' || path === '/api/v2/settings/runtime-effective/')) {
      return fulfillJson(route, { settings: state.runtimeSettings })
    }

    if (method === 'PATCH' && path.startsWith('/api/v2/settings/runtime/')) {
      const key = decodeURIComponent(path.split('/').filter(Boolean).slice(-1)[0] ?? '')
      const existing = state.runtimeSettings.find((item) => item.key === key)

      let payload: AnyRecord = {}
      try {
        payload = JSON.parse(request.postData() || '{}') as AnyRecord
      } catch (_err) {
        payload = {}
      }

      if ((state.patchFailCount ?? 0) > 0) {
        state.patchFailCount = (state.patchFailCount ?? 0) - 1
        return fulfillJson(route, {
          success: false,
          error: {
            code: 'VALIDATION_ERROR',
            message: state.patchFailMessages ?? ['extensions.actions[0].executor.command_id: unknown command_id'],
          },
        }, 400)
      }

      const updated: AnyRecord = existing
        ? { ...existing, value: payload.value }
        : {
          key,
          value_type: 'json',
          description: '',
          min_value: null,
          max_value: null,
          default: null,
          value: payload.value,
        }

      if (existing) {
        existing.value = payload.value
      } else {
        state.runtimeSettings.push(updated)
      }

      return fulfillJson(route, updated)
    }

    if (method === 'PATCH' && path.startsWith('/api/v2/settings/runtime-overrides/')) {
      const key = decodeURIComponent(path.split('/').filter(Boolean).slice(-1)[0] ?? '')
      const existing = state.runtimeSettings.find((item) => item.key === key)

      let payload: AnyRecord = {}
      try {
        payload = JSON.parse(request.postData() || '{}') as AnyRecord
      } catch (_err) {
        payload = {}
      }

      if ((state.patchFailCount ?? 0) > 0) {
        state.patchFailCount = (state.patchFailCount ?? 0) - 1
        return fulfillJson(route, {
          success: false,
          error: {
            code: 'VALIDATION_ERROR',
            message: state.patchFailMessages ?? ['extensions.actions[0].executor.command_id: unknown command_id'],
          },
        }, 400)
      }

      const updatedValue = payload.value

      const updated: AnyRecord = existing
        ? { ...existing, value: updatedValue }
        : {
          key,
          value_type: 'json',
          description: '',
          min_value: null,
          max_value: null,
          default: null,
          value: updatedValue,
        }

      if (existing) {
        existing.value = updatedValue
      } else {
        state.runtimeSettings.push(updated)
      }

      const status = typeof payload.status === 'string' ? payload.status : 'published'
      return fulfillJson(route, { key, value: updatedValue, status })
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
	              params_by_name: {
	                format: { kind: 'flag', required: false, expects_value: true, default: 'json', description: 'Output format.' },
	                ids: { kind: 'flag', required: false, expects_value: true, repeatable: true, description: 'Extension IDs.' },
	                limit: { kind: 'flag', required: false, expects_value: true, description: 'Limit results.' },
	                remote: { kind: 'flag', required: false, expects_value: true, default: 'ssh://x:1545' },
	                legacy: { kind: 'flag', required: false, expects_value: true, disabled: true },
	              },
	            },
	            'infobase.extension.update': {
	              label: 'update extension',
	              description: 'Update extension',
	              argv: ['infobase', 'extension', 'update'],
	              scope: 'per_database',
	              risk_level: 'dangerous',
	              params_by_name: {
	                ids: { kind: 'flag', required: true, expects_value: true, repeatable: true, description: 'Extension IDs.' },
	                force: { kind: 'flag', required: false, expects_value: false, description: 'Force update.' },
	                timeout: { kind: 'flag', required: false, expects_value: true, value_type: 'int', description: 'Timeout (seconds).' },
	              },
	            },
	          },
	        },
      })
    }

    if (method === 'GET' && path === '/api/v2/ui/action-catalog/editor-hints/') {
      return fulfillJson(route, state.editorHints ?? {
        hints_version: 1,
        capabilities: {
          'extensions.set_flags': {
            fixed_schema: {
              type: 'object',
              additionalProperties: false,
              properties: {
                apply_mask: {
                  type: 'object',
                  title: 'apply_mask (preset)',
                  description: 'Optional preset mask for extensions.set_flags.',
                  additionalProperties: false,
                  required: ['active', 'safe_mode', 'unsafe_action_protection'],
                  properties: {
                    active: { type: 'boolean', title: 'active', default: false },
                    safe_mode: { type: 'boolean', title: 'safe_mode', default: false },
                    unsafe_action_protection: { type: 'boolean', title: 'unsafe_action_protection', default: false },
                  },
                },
              },
            },
            fixed_ui_schema: {
              apply_mask: {
                active: { 'ui:widget': 'switch' },
                safe_mode: { 'ui:widget': 'switch' },
                unsafe_action_protection: { 'ui:widget': 'switch' },
              },
            },
            help: {
              title: 'Set flags presets',
              description: 'Capability-specific fixed fields for extensions.set_flags.',
            },
          },
        },
      })
    }

    if (method === 'POST' && path === '/api/v2/ui/execution-plan/preview/') {
      return fulfillJson(route, {
        execution_plan: {
          kind: 'ibcmd_cli',
          argv_masked: ['infobase', 'config', 'extension', 'list', '--db-pwd=***'],
        },
        bindings: [
          { target_ref: 'command_id', source_ref: 'request.executor.command_id', resolve_at: 'api', sensitive: false, status: 'applied' },
        ],
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

  const listRow = page.locator('tr', { has: page.getByText('extensions.list', { exact: true }) })
  await listRow.getByRole('button', { name: 'Preview', exact: true }).click()
  await expect(page.getByText('Preview: extensions.list')).toBeVisible()
  const previewDatabasesInput = page.getByTestId('action-catalog-preview-database-ids').locator('input').first()
  await previewDatabasesInput.fill('db1')
  await previewDatabasesInput.press('Enter')
  const previewRunButton = page.getByLabel('Preview: extensions.list').getByRole('button', { name: 'Preview', exact: true })
  await expect(previewRunButton).toBeEnabled()
  await previewRunButton.click()
  await expect(page.getByText('execution_plan', { exact: false })).toBeVisible()
  await page.locator('.ant-modal-footer').getByRole('button', { name: 'Close', exact: true }).click()

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
  await expect(page.getByTestId('action-catalog-dirty-raw')).toBeVisible()
  await expect(page.getByTestId('action-catalog-diff-count')).toContainText('Changes: ')
  await expect(page.getByTestId('action-catalog-diff-table')).toBeVisible()

  await page.getByTestId('action-catalog-save').click()
  await expect(page.getByText('Saved', { exact: true })).toBeVisible()
  await expect(page.locator('[data-testid="action-catalog-dirty"]')).toHaveCount(0)
  await expect(page.locator('[data-testid="action-catalog-dirty-raw"]')).toHaveCount(0)
  await expect(page.locator('[data-testid="action-catalog-diff-table"]')).toHaveCount(0)
  await expect(page.getByTestId('action-catalog-reload')).toBeEnabled()
  await expect(page.getByTestId('action-catalog-save')).toBeDisabled()

  await expect(page.getByRole('button', { name: 'Format', exact: true })).toBeVisible()
})

test('Action Catalog: shows backend validation errors on save', async ({ page }) => {
  await setupAuth(page)
  await setupApiMocks(page, {
    patchFailCount: 1,
    patchFailMessages: [
      'extensions.actions[0].executor.command_id: unknown command_id "unknown.command"',
      'extensions.actions[0].id: must be unique',
    ],
    runtimeSettings: [
      {
        key: 'ui.action_catalog',
        value_type: 'json',
        description: 'UI action catalog bindings (v1).',
        min_value: null,
        max_value: null,
        default: { catalog_version: 1, extensions: { actions: [] } },
        value: { catalog_version: 1, extensions: { actions: [] } },
      },
    ],
  })

  await page.goto('/settings/action-catalog', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Action Catalog', exact: true })).toBeVisible()
  await expect(page.getByTestId('action-catalog-save')).toBeDisabled()

  await page.getByTestId('action-catalog-add').click()
  await page.getByTestId('action-catalog-editor-id').fill('extensions.bad')
  await page.getByTestId('action-catalog-editor-label').fill('Bad action')
  await page.getByTestId('action-catalog-editor-command-id').click()
  await page.keyboard.type('infobase.extension.list')
  await page.keyboard.press('Enter')
  await page.getByTestId('action-catalog-editor-apply').click()

  await expect(page.getByTestId('action-catalog-dirty')).toBeVisible()
  await expect(page.getByTestId('action-catalog-save')).toBeEnabled()

  await page.getByTestId('action-catalog-save').click()
  await expect(page.getByText('Save failed', { exact: true })).toBeVisible()
  await expect(page.getByText('extensions.actions[0].executor.command_id: unknown command_id "unknown.command"', { exact: true })).toBeVisible()
  await expect(page.getByText('extensions.actions[0].id: must be unique', { exact: true })).toBeVisible()

  await expect(page.getByTestId('action-catalog-dirty')).toBeVisible()
  await expect(page.getByTestId('action-catalog-save')).toBeEnabled()
})

test('Action Catalog: auto-fills params template from command schema and confirms overwrite', async ({ page }) => {
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
        value: { catalog_version: 1, extensions: { actions: [] } },
      },
    ],
  })

  await page.goto('/settings/action-catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Action Catalog', exact: true })).toBeVisible()

  await page.getByTestId('action-catalog-add').click()
  await page.getByTestId('action-catalog-editor-id').fill('extensions.template')
  await page.getByTestId('action-catalog-editor-label').fill('Template action')
  await page.getByTestId('action-catalog-editor-command-id').click()
  await page.keyboard.type('infobase.extension.list')
  await page.keyboard.press('Enter')

  await page.getByRole('tab', { name: 'Params', exact: true }).click()
  await expect(page.getByTestId('action-catalog-editor-params-guided')).toBeVisible()
  await page.getByTestId('action-catalog-editor-params-mode').getByText('Raw JSON', { exact: true }).click()

  const params = page.getByTestId('action-catalog-editor-params')
  await expect(params).toHaveValue(/"format": "json"/)
  await expect(params).toHaveValue(/"ids": \[\]/)
  await expect(params).toHaveValue(/"limit": null/)
  await expect(params).not.toHaveValue(/remote/)
  await expect(params).not.toHaveValue(/legacy/)

  await params.fill('{\"custom\": 1}')
  await page.getByTestId('action-catalog-editor-insert-params-template').click()
  await expect(page.getByRole('button', { name: 'Keep current', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Keep current', exact: true }).click()
  await expect(params).toHaveValue('{\"custom\": 1}')

  await page.getByTestId('action-catalog-editor-insert-params-template').click()
  await page.getByRole('button', { name: 'Overwrite', exact: true }).click()
  await expect(params).toHaveValue(/"format": "json"/)

  await page.getByTestId('action-catalog-editor-apply').click()
  await expect(page.getByText('extensions.template', { exact: true })).toBeVisible()
})

test('Action Catalog editor: params default Guided and schema panel is collapsed', async ({ page }) => {
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
        value: { catalog_version: 1, extensions: { actions: [] } },
      },
    ],
  })

  await page.goto('/settings/action-catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Action Catalog', exact: true })).toBeVisible()

  await page.getByTestId('action-catalog-add').click()
  await page.getByTestId('action-catalog-editor-command-id').click()
  await page.keyboard.type('infobase.extension.list')
  await page.keyboard.press('Enter')

  await page.getByRole('tab', { name: 'Params', exact: true }).click()
  await expect(page.getByTestId('action-catalog-editor-params-guided')).toBeVisible()
  await expect(page.getByTestId('action-catalog-editor-params-mode')).toBeVisible()

  await page.getByRole('tab', { name: 'Basics', exact: true }).click()
  const schemaPanel = page.getByTestId('action-catalog-editor-schema-panel')
  await expect(schemaPanel).toBeVisible()
  await expect(schemaPanel.locator('.ant-collapse-item-active')).toHaveCount(0)
})

test('Action Catalog editor: preserves unknown keys when editing schema params in Guided', async ({ page }) => {
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
        value: { catalog_version: 1, extensions: { actions: [] } },
      },
    ],
  })

  await page.goto('/settings/action-catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Action Catalog', exact: true })).toBeVisible()

  await page.getByTestId('action-catalog-add').click()
  await page.getByTestId('action-catalog-editor-id').fill('extensions.unknown')
  await page.getByTestId('action-catalog-editor-label').fill('Unknown keys')
  await page.getByTestId('action-catalog-editor-command-id').click()
  await page.keyboard.type('infobase.extension.list')
  await page.keyboard.press('Enter')

  await page.getByRole('tab', { name: 'Params', exact: true }).click()
  await page.getByTestId('action-catalog-editor-params-mode').getByText('Raw JSON', { exact: true }).click()
  await page.getByTestId('action-catalog-editor-params').fill('{\"custom\": 1}')

  await page.getByTestId('action-catalog-editor-params-mode').getByText('Guided', { exact: true }).click()
  const guided = page.getByTestId('action-catalog-editor-params-guided')
  await expect(guided).toBeVisible()
  await guided.getByText('Optional', { exact: false }).click()
  await guided.locator('.ant-form-item', { hasText: 'limit' }).locator('input').fill('5')

  await page.getByTestId('action-catalog-editor-apply').click()
  await expect(page.getByText('extensions.unknown', { exact: true })).toBeVisible()

  const row = page.locator('tr', { has: page.getByText('extensions.unknown', { exact: true }) })
  await row.getByRole('button', { name: 'Edit', exact: true }).click()
  await page.getByRole('tab', { name: 'Params', exact: true }).click()
  await page.getByTestId('action-catalog-editor-params-mode').getByText('Raw JSON', { exact: true }).click()

  const params = page.getByTestId('action-catalog-editor-params')
  await expect(params).toHaveValue(/"custom": 1/)
  await expect(params).toHaveValue(/"limit": "5"/)
})

test('Action Catalog editor: blocks Guided on invalid Raw JSON and does not auto-fill after touch', async ({ page }) => {
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
        value: { catalog_version: 1, extensions: { actions: [] } },
      },
    ],
  })

  await page.goto('/settings/action-catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Action Catalog', exact: true })).toBeVisible()

  await page.getByTestId('action-catalog-add').click()
  await page.getByTestId('action-catalog-editor-id').fill('extensions.touch')
  await page.getByTestId('action-catalog-editor-label').fill('Touch action')
  await page.getByTestId('action-catalog-editor-command-id').click()
  await page.keyboard.type('infobase.extension.list')
  await page.keyboard.press('Enter')

  await page.getByRole('tab', { name: 'Params', exact: true }).click()
  await page.getByTestId('action-catalog-editor-params-mode').getByText('Raw JSON', { exact: true }).click()
  const params = page.getByTestId('action-catalog-editor-params')
  await params.fill('{')

  await page.getByTestId('action-catalog-editor-params-mode').getByText('Guided', { exact: true }).click()
  await expect(page.locator('.ant-modal-confirm-title', { hasText: 'Fix params JSON' })).toBeVisible()
  await page.getByRole('button', { name: 'OK', exact: true }).click()
  await expect(params).toBeVisible()

  await params.fill('{}')
  await page.getByRole('tab', { name: 'Basics', exact: true }).click()
  await page.getByTestId('action-catalog-editor-command-id').click()
  await page.keyboard.type('infobase.extension.update')
  await page.keyboard.press('Enter')

  await expect(params).toHaveValue('{}')
  await expect(params).not.toHaveValue(/force/)
})

test('Action Catalog editor: footer quick actions Preview and Reset', async ({ page }) => {
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
        value: { catalog_version: 1, extensions: { actions: [] } },
      },
    ],
  })

  await page.goto('/settings/action-catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Action Catalog', exact: true })).toBeVisible()

  await page.getByTestId('action-catalog-add').click()
  await page.getByTestId('action-catalog-editor-id').fill('extensions.quick')
  await page.getByTestId('action-catalog-editor-label').fill('Quick actions')

  await page.getByTestId('action-catalog-editor-open-preview-tab').click()
  const previewJson = page.getByTestId('action-catalog-editor-preview-json')
  await expect(previewJson).toBeVisible()
  await expect(previewJson).toHaveValue(/"id": "extensions\.quick"/)

  await page.getByTestId('action-catalog-editor-reset-form').click()
  await expect(page.getByTestId('action-catalog-editor-id')).toHaveValue('')
  await expect(page.getByTestId('action-catalog-editor-label')).toHaveValue('')
})

test('Action Catalog editor: capability fixed section follows uiSchema widgets', async ({ page }) => {
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
        value: { catalog_version: 1, extensions: { actions: [] } },
      },
    ],
    editorHints: {
      hints_version: 1,
      capabilities: {
        'extensions.set_flags': {
          fixed_schema: {
            type: 'object',
            additionalProperties: false,
            properties: {
              apply_mask: {
                type: 'object',
                title: 'apply_mask',
                additionalProperties: false,
                required: ['active', 'safe_mode', 'unsafe_action_protection'],
                properties: {
                  active: { type: 'boolean', title: 'active' },
                  safe_mode: { type: 'boolean', title: 'safe_mode' },
                  unsafe_action_protection: { type: 'boolean', title: 'unsafe_action_protection' },
                },
              },
            },
          },
          fixed_ui_schema: {
            apply_mask: {
              active: { 'ui:widget': 'checkbox' },
              safe_mode: { 'ui:widget': 'hidden' },
              unsafe_action_protection: { 'ui:widget': 'switch' },
            },
          },
        },
      },
    },
  })

  await page.goto('/settings/action-catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Action Catalog', exact: true })).toBeVisible()

  await page.getByTestId('action-catalog-add').click()
  await page.getByTestId('action-catalog-editor-capability').click()
  await page.keyboard.type('extensions.set_flags')
  await page.keyboard.press('Enter')

  await page.getByRole('tab', { name: 'Safety & Fixed', exact: true }).click()
  await page.getByTestId('action-catalog-editor-fixed-apply_mask-enable').click()

  await expect(page.getByTestId('action-catalog-editor-fixed-apply_mask-active-checkbox')).toBeVisible()
  await expect(page.getByText('unsafe_action_protection', { exact: true })).toBeVisible()
  await expect(page.getByText('safe_mode', { exact: true })).toHaveCount(0)
})
