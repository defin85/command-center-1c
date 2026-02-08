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

const UI_ACTION_CATALOG_KEY = 'ui.action_catalog'
const MOCK_TIMESTAMP = '2026-01-01T00:00:00Z'

const isPlainObject = (value: unknown): value is AnyRecord => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const deepClone = <T,>(value: T): T => {
  try {
    return JSON.parse(JSON.stringify(value)) as T
  } catch (_err) {
    return value
  }
}

const buildMockUuid = (seq: number): string => `00000000-0000-4000-8000-${String(seq).padStart(12, '0')}`

const parseIntParam = (raw: string | null, fallback: number, min: number, max: number): number => {
  const parsed = Number.parseInt(String(raw ?? ''), 10)
  if (!Number.isFinite(parsed)) return fallback
  return Math.min(max, Math.max(min, parsed))
}

const buildValidationErrors = (messages: string[] | undefined): AnyRecord[] => {
  const source = Array.isArray(messages) && messages.length > 0
    ? messages
    : ['extensions.actions[0].executor.command_id: unknown command_id']
  return source.map((message) => {
    const text = String(message)
    const withPath = /^extensions\.actions\[\d+\]\.([^:]+):\s*(.+)$/.exec(text)
    if (withPath) {
      return { path: withPath[1], code: 'VALIDATION_ERROR', message: withPath[2] }
    }
    const noPath = /^extensions\.actions\[\d+\]:\s*(.+)$/.exec(text)
    if (noPath) {
      return { path: '', code: 'VALIDATION_ERROR', message: noPath[1] }
    }
    return { path: '', code: 'VALIDATION_ERROR', message: text }
  })
}

const parseJsonBody = (raw: string | null): AnyRecord => {
  try {
    const parsed = JSON.parse(raw || '{}') as unknown
    return isPlainObject(parsed) ? parsed : {}
  } catch (_err) {
    return {}
  }
}

async function setupApiMocks(
  page: Page,
  state: {
    runtimeSettings: AnyRecord[]
    patchFailCount?: number
    patchFailMessages?: string[]
    editorHints?: AnyRecord
    me?: { id: number; username: string; is_staff: boolean }
    callCounters?: {
      operationCatalogExposuresGets?: number
      actionCatalogEditorHintsGets?: number
    }
  }
) {
  const definitions: AnyRecord[] = []
  const exposures: AnyRecord[] = []
  let definitionSeq = 1
  let exposureSeq = 10_000

  const createDefinition = (payload: {
    tenant_scope?: string
    executor_kind?: string
    executor_payload?: AnyRecord
    contract_version?: number
    status?: string
  }): AnyRecord => {
    const id = buildMockUuid(definitionSeq)
    definitionSeq += 1
    const definition: AnyRecord = {
      id,
      tenant_scope: typeof payload.tenant_scope === 'string' && payload.tenant_scope ? payload.tenant_scope : 'global',
      executor_kind: typeof payload.executor_kind === 'string' && payload.executor_kind ? payload.executor_kind : 'ibcmd_cli',
      executor_payload: isPlainObject(payload.executor_payload) ? deepClone(payload.executor_payload) : {},
      contract_version: typeof payload.contract_version === 'number' ? payload.contract_version : 1,
      fingerprint: `mock-def-${id}`,
      status: typeof payload.status === 'string' && payload.status ? payload.status : 'active',
      created_at: MOCK_TIMESTAMP,
      updated_at: MOCK_TIMESTAMP,
    }
    definitions.push(definition)
    return definition
  }

  const createExposure = (payload: {
    id?: string
    definition_id: string
    surface: string
    alias: string
    tenant_id?: string | null
    name: string
    description?: string
    is_active?: boolean
    capability?: string
    contexts?: string[]
    display_order?: number
    capability_config?: AnyRecord
    status?: string
  }): AnyRecord => {
    const exposure: AnyRecord = {
      id: payload.id ?? buildMockUuid(exposureSeq),
      definition_id: payload.definition_id,
      surface: payload.surface,
      alias: payload.alias,
      tenant_id: payload.tenant_id ?? null,
      name: payload.name,
      description: payload.description ?? '',
      is_active: payload.is_active !== false,
      capability: payload.capability ?? '',
      contexts: Array.isArray(payload.contexts) ? payload.contexts : [],
      display_order: typeof payload.display_order === 'number' ? payload.display_order : 0,
      capability_config: isPlainObject(payload.capability_config) ? deepClone(payload.capability_config) : {},
      status: payload.status ?? 'draft',
      created_at: MOCK_TIMESTAMP,
      updated_at: MOCK_TIMESTAMP,
    }
    exposureSeq += 1
    exposures.push(exposure)
    return exposure
  }

  const splitExecutorPayload = (executorRaw: unknown): { definition_payload: AnyRecord; capability_config: AnyRecord } => {
    const executor = isPlainObject(executorRaw) ? deepClone(executorRaw) : {}
    const capabilityConfig: AnyRecord = {}
    const fixed = isPlainObject(executor.fixed) ? deepClone(executor.fixed) : null
    if (fixed && isPlainObject(fixed)) {
      const restFixed: AnyRecord = {}
      for (const [key, value] of Object.entries(fixed)) {
        if (key === 'apply_mask') {
          capabilityConfig.apply_mask = value
        } else {
          restFixed[key] = value
        }
      }
      if (Object.keys(restFixed).length > 0) capabilityConfig.fixed = restFixed
    }
    if (isPlainObject(executor.target_binding)) {
      capabilityConfig.target_binding = deepClone(executor.target_binding)
    }
    delete executor.fixed
    delete executor.target_binding
    return { definition_payload: executor, capability_config: capabilityConfig }
  }

  const runtimeSetting = state.runtimeSettings.find((item) => item.key === UI_ACTION_CATALOG_KEY)
  const runtimeValue = isPlainObject(runtimeSetting?.value) ? runtimeSetting.value : {}
  const runtimeExtensions = isPlainObject(runtimeValue.extensions) ? runtimeValue.extensions : {}
  const runtimeActions = Array.isArray(runtimeExtensions.actions) ? runtimeExtensions.actions : []

  for (let idx = 0; idx < runtimeActions.length; idx += 1) {
    const action = runtimeActions[idx]
    if (!isPlainObject(action)) continue
    const alias = typeof action.id === 'string' && action.id.trim() ? action.id.trim() : `action.${idx + 1}`
    const label = typeof action.label === 'string' && action.label.trim() ? action.label.trim() : alias
    const contexts = Array.isArray(action.contexts)
      ? action.contexts.filter((item): item is string => typeof item === 'string')
      : ['database_card']
    const { definition_payload, capability_config } = splitExecutorPayload(action.executor)
    const definitionKind = typeof definition_payload.kind === 'string' && definition_payload.kind
      ? definition_payload.kind
      : 'ibcmd_cli'
    const definition = createDefinition({
      tenant_scope: 'global',
      executor_kind: definitionKind,
      executor_payload: definition_payload,
      contract_version: 1,
      status: 'active',
    })

    createExposure({
      definition_id: String(definition.id),
      surface: 'action_catalog',
      alias,
      tenant_id: null,
      name: label,
      description: typeof action.description === 'string' ? action.description : '',
      is_active: true,
      capability: typeof action.capability === 'string' ? action.capability : '',
      contexts,
      display_order: idx,
      capability_config,
      status: 'published',
    })
  }

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, state.me ?? { id: 1, username: 'admin', is_staff: true })
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

    if (method === 'GET' && path === '/api/v2/operation-catalog/definitions/') {
      const tenantScope = url.searchParams.get('tenant_scope')
      const executorKind = url.searchParams.get('executor_kind')
      const status = url.searchParams.get('status')
      const q = (url.searchParams.get('q') || '').trim().toLowerCase()
      const limit = parseIntParam(url.searchParams.get('limit'), 50, 1, 1000)
      const offset = parseIntParam(url.searchParams.get('offset'), 0, 0, 100000)

      let rows = definitions.slice()
      if (tenantScope) rows = rows.filter((row) => row.tenant_scope === tenantScope)
      if (executorKind) rows = rows.filter((row) => row.executor_kind === executorKind)
      if (status) rows = rows.filter((row) => row.status === status)
      if (q) {
        const matchedDefinitionIds = new Set(
          exposures
            .filter((row) => (
              String(row.alias || '').toLowerCase().includes(q)
              || String(row.name || '').toLowerCase().includes(q)
              || String(row.capability || '').toLowerCase().includes(q)
            ))
            .map((row) => String(row.definition_id))
        )
        rows = rows.filter((row) => matchedDefinitionIds.has(String(row.id)))
      }
      const total = rows.length
      const paged = rows.slice(offset, offset + limit)
      return fulfillJson(route, { definitions: paged, count: paged.length, total })
    }

    if (method === 'GET' && path === '/api/v2/operation-catalog/exposures/') {
      state.callCounters = state.callCounters ?? {}
      state.callCounters.operationCatalogExposuresGets = (state.callCounters.operationCatalogExposuresGets ?? 0) + 1
      const surface = url.searchParams.get('surface')
      const tenantId = url.searchParams.get('tenant_id')
      const capability = url.searchParams.get('capability')
      const status = url.searchParams.get('status')
      const alias = url.searchParams.get('alias')
      const limit = parseIntParam(url.searchParams.get('limit'), 50, 1, 1000)
      const offset = parseIntParam(url.searchParams.get('offset'), 0, 0, 100000)

      let rows = exposures.slice()
      if (surface) rows = rows.filter((row) => row.surface === surface)
      if (tenantId) rows = rows.filter((row) => row.tenant_id === tenantId || row.tenant_id === null)
      if (capability) rows = rows.filter((row) => row.capability === capability)
      if (status) rows = rows.filter((row) => row.status === status)
      if (alias) rows = rows.filter((row) => row.alias === alias)
      rows.sort((a, b) => {
        const bySurface = String(a.surface || '').localeCompare(String(b.surface || ''))
        if (bySurface !== 0) return bySurface
        const byOrder = Number(a.display_order ?? 0) - Number(b.display_order ?? 0)
        if (byOrder !== 0) return byOrder
        return String(a.name || '').localeCompare(String(b.name || ''))
      })

      const total = rows.length
      const paged = rows.slice(offset, offset + limit)
      return fulfillJson(route, { exposures: paged, count: paged.length, total })
    }

    if (method === 'POST' && path === '/api/v2/operation-catalog/exposures/') {
      if ((state.patchFailCount ?? 0) > 0) {
        state.patchFailCount = (state.patchFailCount ?? 0) - 1
        return fulfillJson(route, { validation_errors: buildValidationErrors(state.patchFailMessages) }, 400)
      }

      const payload = parseJsonBody(request.postData())
      const exposurePayload = isPlainObject(payload.exposure) ? payload.exposure : null
      if (!exposurePayload) {
        return fulfillJson(route, { validation_errors: [{ path: 'exposure', code: 'REQUIRED', message: 'exposure is required' }] }, 400)
      }

      const rawDefinitionId = typeof payload.definition_id === 'string' ? payload.definition_id : null
      let definition: AnyRecord | undefined
      if (rawDefinitionId) {
        definition = definitions.find((row) => String(row.id) === rawDefinitionId)
      }
      if (!definition) {
        const definitionPayload = isPlainObject(payload.definition) ? payload.definition : {}
        const definitionExecutorPayload = isPlainObject(definitionPayload.executor_payload)
          ? definitionPayload.executor_payload
          : {}
        const definitionExecutorKind = typeof definitionPayload.executor_kind === 'string' && definitionPayload.executor_kind
          ? definitionPayload.executor_kind
          : (typeof definitionExecutorPayload.kind === 'string' && definitionExecutorPayload.kind
            ? definitionExecutorPayload.kind
            : 'ibcmd_cli')
        definition = createDefinition({
          tenant_scope: typeof definitionPayload.tenant_scope === 'string' && definitionPayload.tenant_scope
            ? definitionPayload.tenant_scope
            : 'global',
          executor_kind: definitionExecutorKind,
          executor_payload: definitionExecutorPayload,
          contract_version: typeof definitionPayload.contract_version === 'number'
            ? definitionPayload.contract_version
            : 1,
          status: 'active',
        })
      }

      const rawExposureId = typeof payload.exposure_id === 'string' ? payload.exposure_id : null
      const existing = rawExposureId
        ? exposures.find((row) => String(row.id) === rawExposureId)
        : undefined
      const nextAlias = typeof exposurePayload.alias === 'string' && exposurePayload.alias.trim()
        ? exposurePayload.alias.trim()
        : (existing ? String(existing.alias) : `action.${exposures.length + 1}`)
      const nextName = typeof exposurePayload.name === 'string' && exposurePayload.name.trim()
        ? exposurePayload.name.trim()
        : nextAlias
      const nextContexts = Array.isArray(exposurePayload.contexts)
        ? exposurePayload.contexts.filter((item): item is string => typeof item === 'string')
        : []
      const nextCapabilityConfig = isPlainObject(exposurePayload.capability_config)
        ? deepClone(exposurePayload.capability_config)
        : {}

      const updatedExposure: AnyRecord = existing ?? createExposure({
        id: rawExposureId ?? undefined,
        definition_id: String(definition.id),
        surface: typeof exposurePayload.surface === 'string' && exposurePayload.surface
          ? exposurePayload.surface
          : 'action_catalog',
        alias: nextAlias,
        tenant_id: typeof exposurePayload.tenant_id === 'string' ? exposurePayload.tenant_id : null,
        name: nextName,
        description: typeof exposurePayload.description === 'string' ? exposurePayload.description : '',
        is_active: exposurePayload.is_active !== false,
        capability: typeof exposurePayload.capability === 'string' ? exposurePayload.capability : '',
        contexts: nextContexts,
        display_order: typeof exposurePayload.display_order === 'number' ? exposurePayload.display_order : 0,
        capability_config: nextCapabilityConfig,
        status: typeof exposurePayload.status === 'string' ? exposurePayload.status : 'draft',
      })

      updatedExposure.definition_id = String(definition.id)
      updatedExposure.surface = typeof exposurePayload.surface === 'string' && exposurePayload.surface
        ? exposurePayload.surface
        : updatedExposure.surface
      updatedExposure.alias = nextAlias
      updatedExposure.name = nextName
      updatedExposure.description = typeof exposurePayload.description === 'string'
        ? exposurePayload.description
        : (updatedExposure.description ?? '')
      updatedExposure.is_active = exposurePayload.is_active !== false
      updatedExposure.capability = typeof exposurePayload.capability === 'string'
        ? exposurePayload.capability
        : (updatedExposure.capability ?? '')
      updatedExposure.contexts = nextContexts
      updatedExposure.display_order = typeof exposurePayload.display_order === 'number'
        ? exposurePayload.display_order
        : Number(updatedExposure.display_order ?? 0)
      updatedExposure.capability_config = nextCapabilityConfig
      updatedExposure.status = typeof exposurePayload.status === 'string' ? exposurePayload.status : 'draft'
      updatedExposure.updated_at = MOCK_TIMESTAMP

      return fulfillJson(route, { exposure: updatedExposure, definition })
    }

    if (method === 'POST' && /^\/api\/v2\/operation-catalog\/exposures\/[^/]+\/publish\/$/.test(path)) {
      const exposureId = decodeURIComponent(path.split('/').filter(Boolean)[4] ?? '')
      const exposure = exposures.find((row) => String(row.id) === exposureId)
      if (!exposure) {
        return fulfillJson(route, {
          success: false,
          error: { code: 'NOT_FOUND', message: 'Exposure not found' },
        }, 404)
      }
      exposure.status = 'published'
      exposure.updated_at = MOCK_TIMESTAMP
      return fulfillJson(route, { published: true, exposure, validation_errors: [] })
    }

    if (method === 'PATCH' && path.startsWith('/api/v2/settings/runtime/')) {
      const key = decodeURIComponent(path.split('/').filter(Boolean).slice(-1)[0] ?? '')
      const existing = state.runtimeSettings.find((item) => item.key === key)

      const payload = parseJsonBody(request.postData())

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

      const payload = parseJsonBody(request.postData())

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
      state.callCounters = state.callCounters ?? {}
      state.callCounters.actionCatalogEditorHintsGets = (state.callCounters.actionCatalogEditorHintsGets ?? 0) + 1
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

  await page.goto('/templates?surface=action_catalog', { waitUntil: 'domcontentloaded' })

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

  await page.goto('/templates?surface=action_catalog', { waitUntil: 'domcontentloaded' })

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

  await page.goto('/templates?surface=action_catalog', { waitUntil: 'domcontentloaded' })
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

  await params.fill('{"custom": 1}')
  await page.getByTestId('action-catalog-editor-insert-params-template').click()
  await expect(page.getByRole('button', { name: 'Keep current', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Keep current', exact: true }).click()
  await expect(params).toHaveValue('{"custom": 1}')

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

  await page.goto('/templates?surface=action_catalog', { waitUntil: 'domcontentloaded' })
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

  await page.goto('/templates?surface=action_catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Action Catalog', exact: true })).toBeVisible()

  await page.getByTestId('action-catalog-add').click()
  await page.getByTestId('action-catalog-editor-id').fill('extensions.unknown')
  await page.getByTestId('action-catalog-editor-label').fill('Unknown keys')
  await page.getByTestId('action-catalog-editor-command-id').click()
  await page.keyboard.type('infobase.extension.list')
  await page.keyboard.press('Enter')

  await page.getByRole('tab', { name: 'Params', exact: true }).click()
  await page.getByTestId('action-catalog-editor-params-mode').getByText('Raw JSON', { exact: true }).click()
  await page.getByTestId('action-catalog-editor-params').fill('{"custom": 1}')

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

  await page.goto('/templates?surface=action_catalog', { waitUntil: 'domcontentloaded' })
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

  await page.goto('/templates?surface=action_catalog', { waitUntil: 'domcontentloaded' })
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

  await page.goto('/templates?surface=action_catalog', { waitUntil: 'domcontentloaded' })
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

test('Templates: non-staff cannot open action-catalog surface or load management endpoints', async ({ page }) => {
  await setupAuth(page)
  const callCounters: { operationCatalogExposuresGets?: number; actionCatalogEditorHintsGets?: number } = {}
  await setupApiMocks(page, {
    runtimeSettings: [],
    me: { id: 2, username: 'operator', is_staff: false },
    callCounters,
  })

  await page.goto('/templates?surface=action_catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Operation Templates', exact: true })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Action Catalog', exact: true })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Action Catalog', exact: true })).toHaveCount(0)
  expect(callCounters.operationCatalogExposuresGets ?? 0).toBe(0)
  expect(callCounters.actionCatalogEditorHintsGets ?? 0).toBe(0)
})

test('Legacy route /settings/action-catalog does not render action-catalog editor flow', async ({ page }) => {
  await setupAuth(page)
  const callCounters: { operationCatalogExposuresGets?: number; actionCatalogEditorHintsGets?: number } = {}
  await setupApiMocks(page, {
    runtimeSettings: [],
    callCounters,
  })

  await page.goto('/settings/action-catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Action Catalog', exact: true })).toHaveCount(0)
  await expect(page.locator('.ant-layout')).toHaveCount(0)
  expect(callCounters.operationCatalogExposuresGets ?? 0).toBe(0)
  expect(callCounters.actionCatalogEditorHintsGets ?? 0).toBe(0)
})
