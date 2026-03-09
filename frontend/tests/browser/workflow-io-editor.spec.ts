import { test, expect, type Page, type Route } from '@playwright/test'

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>
    __TEST_IS_STAFF__?: boolean
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

async function setupAuth(page: Page, isStaff: boolean) {
  await page.addInitScript((staff) => {
    window.__CC1C_ENV__ = {
      VITE_BASE_HOST: '127.0.0.1',
      VITE_API_URL: 'http://127.0.0.1:15173',
      VITE_WS_HOST: '127.0.0.1:15173',
    }
    localStorage.setItem('auth_token', 'test-token')
    window.__TEST_IS_STAFF__ = staff
  }, isStaff)
}

test('Workflow designer: operation io mode persists explicit_strict on save', async ({ page }) => {
  await setupAuth(page, true)

  const workflowId = '11111111-1111-1111-1111-111111111111'
  const baseWorkflow = {
    id: workflowId,
    name: 'wf-io-test',
    description: '',
    workflow_type: 'complex',
    dag_structure: {
      nodes: [
        {
          id: 'step1',
          name: 'Step 1',
          type: 'operation',
          template_id: 'tpl-custom-load-extension',
          operation_ref: {
            alias: 'tpl-custom-load-extension',
            binding_mode: 'alias_latest',
          },
          io: {
            mode: 'implicit_legacy',
            input_mapping: {},
            output_mapping: {},
          },
          config: { timeout_seconds: 300, max_retries: 0 },
        },
      ],
      edges: [],
    },
    config: { timeout_seconds: 3600, max_retries: 0 },
    is_valid: true,
    is_active: true,
    version_number: 1,
    parent_version: null,
    parent_version_name: null,
    created_by: null,
    created_by_username: null,
    execution_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }

  let lastUpdatePayload: Record<string, unknown> | null = null

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'admin', is_staff: true })
    }
    if (method === 'GET' && path === '/api/v2/workflows/get-workflow/') {
      return fulfillJson(route, { workflow: baseWorkflow, statistics: {}, executions: [] })
    }
    if (method === 'GET' && path === '/api/v2/operation-catalog/exposures/') {
      return fulfillJson(route, {
        exposures: [
          {
            id: '6b5a0b0f-6f4e-4a06-8f63-10c992bd0f8f',
            definition_id: 'def-1',
            surface: 'template',
            alias: 'tpl-custom-load-extension',
            name: 'Load extension',
            description: '',
            is_active: true,
            capability: '',
            status: 'published',
            operation_type: 'designer_cli',
            template_exposure_revision: 3,
          },
        ],
        count: 1,
        total: 1,
      })
    }
    if (method === 'POST' && path === '/api/v2/workflows/update-workflow/') {
      lastUpdatePayload = request.postDataJSON() as Record<string, unknown>
      const dag = (lastUpdatePayload?.dag_structure ?? baseWorkflow.dag_structure) as Record<string, unknown>
      return fulfillJson(route, {
        workflow: {
          ...baseWorkflow,
          dag_structure: dag,
          updated_at: '2026-01-01T00:00:01Z',
        },
        updated_fields: ['dag_structure'],
        message: 'Workflow updated successfully',
      })
    }

    return fulfillJson(route, {}, 200)
  })

  await page.goto(`/workflows/${workflowId}`, { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('wf-io-test', { exact: true })).toBeVisible()
  await page.getByText('Step 1', { exact: true }).first().click()
  await expect(page.locator('#workflow-step1-operation-io-mode')).toBeVisible()

  await page
    .locator('#workflow-step1-operation-io-mode')
    .locator('xpath=ancestor::div[contains(@class,"ant-select")]')
    .first()
    .click()
  await page.getByText('explicit_strict (mapped only)', { exact: true }).click()
  await expect(page.getByText('Input Mapping (before render)', { exact: true })).toBeVisible()
  await expect(page.getByText('Output Mapping (after success)', { exact: true })).toBeVisible()

  await page.locator('.designer-header button').filter({ hasText: 'Save' }).first().click()

  await expect.poll(() => lastUpdatePayload).not.toBeNull()
  const dagStructure = lastUpdatePayload?.dag_structure as {
    nodes?: Array<{ io?: { mode?: string; input_mapping?: Record<string, string>; output_mapping?: Record<string, string> } }>
  }
  const savedIo = dagStructure.nodes?.[0]?.io
  expect(savedIo?.mode).toBe('explicit_strict')
  expect(savedIo?.input_mapping).toEqual({})
  expect(savedIo?.output_mapping).toEqual({})
})

test('Workflow designer: template switch persists pinned operation_ref on save', async ({ page }) => {
  await setupAuth(page, true)

  const workflowId = '22222222-2222-2222-2222-222222222222'
  const baseWorkflow = {
    id: workflowId,
    name: 'wf-operation-ref',
    description: '',
    workflow_type: 'complex',
    dag_structure: {
      nodes: [
        {
          id: 'step1',
          name: 'Step 1',
          type: 'operation',
          template_id: 'tpl-old',
          operation_ref: {
            alias: 'tpl-old',
            binding_mode: 'alias_latest',
          },
          config: { timeout_seconds: 300, max_retries: 0 },
        },
      ],
      edges: [],
    },
    config: { timeout_seconds: 3600, max_retries: 0 },
    is_valid: true,
    is_active: true,
    version_number: 1,
    parent_version: null,
    parent_version_name: null,
    created_by: null,
    created_by_username: null,
    execution_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }

  let lastUpdatePayload: Record<string, unknown> | null = null

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'admin', is_staff: true })
    }
    if (method === 'GET' && path === '/api/v2/workflows/get-workflow/') {
      return fulfillJson(route, { workflow: baseWorkflow, statistics: {}, executions: [] })
    }
    if (method === 'GET' && path === '/api/v2/operation-catalog/exposures/') {
      return fulfillJson(route, {
        exposures: [
          {
            id: 'exposure-old',
            definition_id: 'def-old',
            surface: 'template',
            alias: 'tpl-old',
            name: 'Template old',
            description: '',
            is_active: true,
            capability: '',
            status: 'published',
            operation_type: 'designer_cli',
            template_exposure_revision: 1,
          },
          {
            id: '6b5a0b0f-6f4e-4a06-8f63-10c992bd0f8f',
            definition_id: 'def-new',
            surface: 'template',
            alias: 'tpl-new',
            name: 'Template new',
            description: '',
            is_active: true,
            capability: '',
            status: 'published',
            operation_type: 'designer_cli',
            template_exposure_revision: 9,
          },
        ],
        count: 2,
        total: 2,
      })
    }
    if (method === 'POST' && path === '/api/v2/workflows/update-workflow/') {
      lastUpdatePayload = request.postDataJSON() as Record<string, unknown>
      const dag = (lastUpdatePayload?.dag_structure ?? baseWorkflow.dag_structure) as Record<string, unknown>
      return fulfillJson(route, {
        workflow: {
          ...baseWorkflow,
          dag_structure: dag,
          updated_at: '2026-01-01T00:00:01Z',
        },
        updated_fields: ['dag_structure'],
        message: 'Workflow updated successfully',
      })
    }

    return fulfillJson(route, {}, 200)
  })

  await page.goto(`/workflows/${workflowId}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('wf-operation-ref', { exact: true })).toBeVisible()

  await page.getByText('Step 1', { exact: true }).first().click()
  await expect(page.locator('#workflow-step1-operation-template')).toBeVisible()

  await page
    .locator('#workflow-step1-operation-template')
    .locator('xpath=ancestor::div[contains(@class,"ant-select")]')
    .first()
    .click()
  await page.getByText('Template new (designer_cli)', { exact: true }).click()

  await page.locator('.designer-header button').filter({ hasText: 'Save' }).first().click()
  await expect.poll(() => lastUpdatePayload).not.toBeNull()

  const dagStructure = lastUpdatePayload?.dag_structure as {
    nodes?: Array<{
      template_id?: string
      operation_ref?: {
        alias?: string
        binding_mode?: string
        template_exposure_id?: string
        template_exposure_revision?: number
      }
    }>
  }
  const node = dagStructure.nodes?.[0]
  expect(node?.template_id).toBe('tpl-new')
  expect(node?.operation_ref?.alias).toBe('tpl-new')
  expect(node?.operation_ref?.binding_mode).toBe('pinned_exposure')
  expect(node?.operation_ref?.template_exposure_id).toBe('6b5a0b0f-6f4e-4a06-8f63-10c992bd0f8f')
  expect(node?.operation_ref?.template_exposure_revision).toBe(9)
})

test('Workflow designer: explicit template contract is shown and validates required mappings', async ({ page }) => {
  await setupAuth(page, true)

  const workflowId = '33333333-3333-3333-3333-333333333333'
  const baseWorkflow = {
    id: workflowId,
    name: 'wf-template-contract',
    description: '',
    workflow_type: 'complex',
    dag_structure: {
      nodes: [
        {
          id: 'step1',
          name: 'Step 1',
          type: 'operation',
          template_id: 'tpl-sync-extension',
          operation_ref: {
            alias: 'tpl-sync-extension',
            binding_mode: 'alias_latest',
          },
          io: {
            mode: 'implicit_legacy',
            input_mapping: {
              'params.database_id': 'workflow.input.database_id',
            },
            output_mapping: {},
          },
          config: { timeout_seconds: 300, max_retries: 0 },
        },
      ],
      edges: [],
    },
    config: { timeout_seconds: 3600, max_retries: 0 },
    is_valid: true,
    is_active: true,
    version_number: 1,
    parent_version: null,
    parent_version_name: null,
    created_by: null,
    created_by_username: null,
    execution_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'admin', is_staff: true })
    }
    if (method === 'GET' && path === '/api/v2/workflows/get-workflow/') {
      return fulfillJson(route, { workflow: baseWorkflow, statistics: {}, executions: [] })
    }
    if (method === 'GET' && path === '/api/v2/operation-catalog/exposures/') {
      return fulfillJson(route, {
        exposures: [
          {
            id: 'template-exposure-1',
            definition_id: 'definition-1',
            surface: 'template',
            alias: 'tpl-sync-extension',
            name: 'Sync Extension',
            description: 'Syncs extension state',
            is_active: true,
            capability: 'extensions.sync',
            status: 'published',
            operation_type: 'designer_cli',
            template_exposure_revision: 4,
            execution_contract: {
              contract_version: 'workflow_template_execution_contract.v1',
              capability: {
                id: 'extensions.sync',
                label: 'Sync Extension',
                operation_type: 'designer_cli',
                target_entity: 'infobase',
                executor_kind: 'designer_cli',
              },
              input_contract: {
                mode: 'params',
                required_parameters: ['database_id', 'extension_name'],
                optional_parameters: ['timeout_seconds'],
                parameter_schemas: {
                  database_id: { type: 'uuid', description: 'Database identifier', required: true },
                  extension_name: { type: 'string', description: 'Extension name', required: true },
                  timeout_seconds: { type: 'integer', description: 'Timeout', required: false },
                },
              },
              output_contract: {
                result_path: 'result',
                supports_structured_mapping: true,
              },
              side_effect_profile: {
                execution_mode: 'async',
                effect_kind: 'mutating',
                summary: 'Updates extension state in the target infobase.',
                timeout_seconds: 900,
                max_retries: 5,
              },
              binding_provenance: {
                surface: 'template',
                alias: 'tpl-sync-extension',
                exposure_id: 'template-exposure-1',
                exposure_revision: 4,
                definition_id: 'definition-1',
                executor_command_id: 'infobase.extension.sync',
              },
            },
          },
        ],
        count: 1,
        total: 1,
      })
    }

    return fulfillJson(route, {}, 200)
  })

  await page.goto(`/workflows/${workflowId}`, { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('wf-template-contract', { exact: true })).toBeVisible()
  await page.getByText('Step 1', { exact: true }).first().click()
  await expect(page.getByText('Execution contract', { exact: true })).toBeVisible()
  await expect(page.getByText('extensions.sync', { exact: true })).toBeVisible()
  await expect(page.getByText('designer_cli -> infobase', { exact: true })).toBeVisible()
  await expect(page.getByText('Updates extension state in the target infobase.', { exact: true })).toBeVisible()

  await page
    .locator('#workflow-step1-operation-io-mode')
    .locator('xpath=ancestor::div[contains(@class,"ant-select")]')
    .first()
    .click()
  await page.getByText('explicit_strict (mapped only)', { exact: true }).click()

  await expect(page.getByText(/Missing required mappings: .*params\.extension_name/)).toBeVisible()
})
