import { expect, test, type Page, type Route } from '@playwright/test'

type AnyRecord = Record<string, unknown>

type MockCounters = {
  operationCatalogExposuresGets?: number
  operationCatalogExposuresWithDefinitionsGets?: number
  operationCatalogActionExposuresGets?: number
  operationCatalogDefinitionsGets?: number
  poolRuntimeRegistryGets?: number
  operationExposureHintsGets?: number
  validateCalls?: number
  upsertCalls?: number
  publishCalls?: number
  deleteCalls?: number
  legacyTemplateCalls?: number
  legacyActionHintsCalls?: number
  legacyActionCatalogCalls?: number
}

type MockUser = {
  id: number
  username: string
  is_staff: boolean
}

type MockState = {
  me?: MockUser
  templates?: Array<{
    id?: string
    name: string
    description?: string
    is_active?: boolean
    command_id?: string
    system_managed?: boolean
    domain?: string
  }>
  actions?: Array<{
    id: string
    label: string
    description?: string
    capability?: string
    contexts?: string[]
    is_active?: boolean
    status?: string
    command_id?: string
  }>
  callCounters?: MockCounters
  upsertPayloads?: AnyRecord[]
  templateAccessById?: Record<string, 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'>
  templateValidationErrors?: Array<{ path: string; code?: string; message: string }>
}

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>
  }
}

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

const parseIntParam = (raw: string | null, fallback: number, min: number, max: number): number => {
  const parsed = Number.parseInt(String(raw ?? ''), 10)
  if (!Number.isFinite(parsed)) return fallback
  return Math.min(max, Math.max(min, parsed))
}

const parseJsonBody = (raw: string | null): AnyRecord => {
  try {
    const parsed = JSON.parse(raw || '{}') as unknown
    return isPlainObject(parsed) ? parsed : {}
  } catch (_err) {
    return {}
  }
}

const slugify = (value: string): string => {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return normalized || 'template'
}

const buildMockUuid = (seq: number): string => `00000000-0000-4000-8000-${String(seq).padStart(12, '0')}`

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

async function setupApiMocks(page: Page, state: MockState) {
  const counters: MockCounters = state.callCounters ?? {}
  state.callCounters = counters
  const upsertPayloads: AnyRecord[] = state.upsertPayloads ?? []
  state.upsertPayloads = upsertPayloads
  const templateAccessById = state.templateAccessById ?? {}

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
    surface: 'template' | 'action_catalog' | string
    alias: string
    name: string
    description?: string
    capability?: string
    contexts?: string[]
    is_active?: boolean
    display_order?: number
    capability_config?: AnyRecord
    status?: string
    operation_type?: string
    target_entity?: string
    template_data?: AnyRecord
    system_managed?: boolean
    domain?: string
  }): AnyRecord => {
    const exposure: AnyRecord = {
      id: payload.id ?? buildMockUuid(exposureSeq),
      definition_id: payload.definition_id,
      surface: payload.surface,
      alias: payload.alias,
      tenant_id: null,
      name: payload.name,
      description: payload.description ?? '',
      is_active: payload.is_active !== false,
      capability: payload.capability ?? '',
      contexts: Array.isArray(payload.contexts) ? payload.contexts : [],
      display_order: typeof payload.display_order === 'number' ? payload.display_order : 0,
      capability_config: isPlainObject(payload.capability_config) ? deepClone(payload.capability_config) : {},
      status: payload.status ?? 'draft',
      system_managed: payload.system_managed === true,
      domain: typeof payload.domain === 'string' ? payload.domain : '',
      operation_type: typeof payload.operation_type === 'string' ? payload.operation_type : undefined,
      target_entity: typeof payload.target_entity === 'string' ? payload.target_entity : undefined,
      template_data: isPlainObject(payload.template_data) ? deepClone(payload.template_data) : undefined,
      created_at: MOCK_TIMESTAMP,
      updated_at: MOCK_TIMESTAMP,
    }
    exposureSeq += 1
    exposures.push(exposure)
    return exposure
  }

  const seedTemplateExposure = (template: {
    id?: string
    name: string
    description?: string
    is_active?: boolean
    command_id?: string
    system_managed?: boolean
    domain?: string
  }) => {
    const alias = typeof template.id === 'string' && template.id.trim()
      ? template.id.trim()
      : `tpl-${slugify(template.name)}`
    const templateData: AnyRecord = {
      kind: 'designer_cli',
      driver: 'cli',
      mode: 'guided',
      command_id: template.command_id ?? 'infobase.extension.list',
      params: {},
      resolved_args: [],
      stdin: '',
    }
    const definition = createDefinition({
      tenant_scope: 'global',
      executor_kind: 'designer_cli',
      executor_payload: {
        kind: 'designer_cli',
        driver: 'cli',
        operation_type: 'designer_cli',
        target_entity: 'infobase',
        template_data: deepClone(templateData),
      },
      contract_version: 1,
      status: 'active',
    })
    createExposure({
      definition_id: String(definition.id),
      surface: 'template',
      alias,
      name: template.name,
      description: template.description ?? '',
      is_active: template.is_active !== false,
      capability: 'templates.designer_cli',
      contexts: [],
      display_order: 0,
      status: template.is_active === false ? 'draft' : 'published',
      system_managed: template.system_managed === true,
      domain: typeof template.domain === 'string' ? template.domain : '',
      operation_type: 'designer_cli',
      target_entity: 'infobase',
      template_data: templateData,
    })
  }

  const seedActionExposure = (action: {
    id: string
    label: string
    description?: string
    capability?: string
    contexts?: string[]
    is_active?: boolean
    status?: string
    command_id?: string
  }) => {
    const definition = createDefinition({
      tenant_scope: 'global',
      executor_kind: 'ibcmd_cli',
      executor_payload: {
        kind: 'ibcmd_cli',
        driver: 'ibcmd',
        command_id: action.command_id ?? 'infobase.extension.list',
        params: {},
      },
      contract_version: 1,
      status: 'active',
    })
    createExposure({
      definition_id: String(definition.id),
      surface: 'action_catalog',
      alias: action.id,
      name: action.label,
      description: action.description ?? '',
      capability: action.capability ?? '',
      contexts: Array.isArray(action.contexts) && action.contexts.length > 0
        ? action.contexts
        : ['database_card'],
      is_active: action.is_active !== false,
      display_order: 0,
      status: action.status ?? 'published',
    })
  }

  for (const template of state.templates ?? []) {
    seedTemplateExposure(template)
  }
  for (const action of state.actions ?? []) {
    seedActionExposure(action)
  }

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (
      path === '/api/v2/templates/list-templates/'
      || path === '/api/v2/templates/create-template/'
      || path === '/api/v2/templates/update-template/'
      || path === '/api/v2/templates/delete-template/'
    ) {
      counters.legacyTemplateCalls = (counters.legacyTemplateCalls ?? 0) + 1
      return fulfillJson(route, { success: false, error: { code: 'NOT_FOUND', message: 'Not found' } }, 404)
    }

    if (path === '/api/v2/ui/action-catalog/editor-hints/') {
      counters.legacyActionHintsCalls = (counters.legacyActionHintsCalls ?? 0) + 1
      return fulfillJson(route, { success: false, error: { code: 'NOT_FOUND', message: 'Not found' } }, 404)
    }
    if (path === '/api/v2/ui/action-catalog/') {
      counters.legacyActionCatalogCalls = (counters.legacyActionCatalogCalls ?? 0) + 1
      return fulfillJson(route, { success: false, error: { code: 'NOT_FOUND', message: 'Not found' } }, 404)
    }

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, state.me ?? { id: 1, username: 'admin', is_staff: true })
    }

    if (method === 'GET' && path === '/api/v2/rbac/get-effective-access/') {
      const defaultTemplateLevel: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN' = state.me?.is_staff ? 'ADMIN' : 'VIEW'
      const operationTemplates = exposures
        .filter((row) => row.surface === 'template')
        .map((row) => {
          const templateId = String(row.alias || '').trim()
          if (!templateId) return null
          const level = templateAccessById[templateId] ?? defaultTemplateLevel
          return {
            template: {
              id: templateId,
              name: String(row.name || templateId),
            },
            level,
            source: 'direct',
            sources: [{ source: 'direct', level }],
          }
        })
        .filter((row): row is {
          template: { id: string; name: string }
          level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
          source: 'direct'
          sources: Array<{ source: 'direct'; level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN' }>
        } => row !== null)
      return fulfillJson(route, {
        clusters: [],
        databases: [],
        operation_templates: operationTemplates,
      })
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-roles/') {
      return fulfillJson(route, { roles: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/tenants/list-my-tenants/') {
      return fulfillJson(route, {
        active_tenant_id: null,
        tenants: [{ id: 'tenant-1', slug: 'tenant-1', name: 'Tenant 1', role: 'owner' }],
      })
    }

    if (method === 'POST' && path === '/api/v2/tenants/set-active/') {
      return fulfillJson(route, { active_tenant_id: 'tenant-1' })
    }

    if (method === 'GET' && path === '/api/v2/settings/command-schemas/audit/') {
      return fulfillJson(route, { items: [], count: 0, total: 0 })
    }

    if (method === 'GET' && (path === '/api/v2/settings/runtime/' || path === '/api/v2/settings/runtime-effective/')) {
      return fulfillJson(route, { settings: [] })
    }

    if (method === 'POST' && path === '/api/v2/templates/sync-from-registry/') {
      const templateCount = exposures.filter((row) => row.surface === 'template').length
      return fulfillJson(route, {
        created: 0,
        updated: 0,
        unchanged: templateCount,
        message: 'Sync completed',
      })
    }

    if (method === 'GET' && path === '/api/v2/operation-catalog/exposures/') {
      counters.operationCatalogExposuresGets = (counters.operationCatalogExposuresGets ?? 0) + 1
      const surface = url.searchParams.get('surface')
      if (surface === 'action_catalog') {
        counters.operationCatalogActionExposuresGets = (counters.operationCatalogActionExposuresGets ?? 0) + 1
      }
      const includeRaw = String(url.searchParams.get('include') || '')
      const includeSet = new Set(
        includeRaw
          .split(',')
          .map((item) => item.trim().toLowerCase())
          .filter(Boolean)
      )
      if (includeSet.has('definitions')) {
        counters.operationCatalogExposuresWithDefinitionsGets = (counters.operationCatalogExposuresWithDefinitionsGets ?? 0) + 1
      }
      const alias = url.searchParams.get('alias')
      const status = url.searchParams.get('status')
      const capability = url.searchParams.get('capability')
      const search = String(url.searchParams.get('search') || '').trim().toLowerCase()
      const limit = parseIntParam(url.searchParams.get('limit'), 50, 1, 1000)
      const offset = parseIntParam(url.searchParams.get('offset'), 0, 0, 100_000)
      let filtersPayload: AnyRecord = {}
      const rawFilters = url.searchParams.get('filters')
      if (rawFilters) {
        try {
          const parsed = JSON.parse(rawFilters) as unknown
          if (isPlainObject(parsed)) filtersPayload = parsed
        } catch (_err) {
          return fulfillJson(route, { success: false, error: { code: 'VALIDATION_ERROR', message: 'filters must be valid JSON object' } }, 400)
        }
      }
      let sortPayload: AnyRecord = {}
      const rawSort = url.searchParams.get('sort')
      if (rawSort) {
        try {
          const parsed = JSON.parse(rawSort) as unknown
          if (isPlainObject(parsed)) sortPayload = parsed
        } catch (_err) {
          return fulfillJson(route, { success: false, error: { code: 'VALIDATION_ERROR', message: 'sort must be valid JSON object' } }, 400)
        }
      }

      let rows = exposures.slice()
      if (surface) rows = rows.filter((row) => String(row.surface) === surface)
      if (alias) rows = rows.filter((row) => String(row.alias) === alias)
      if (status) rows = rows.filter((row) => String(row.status) === status)
      if (capability) rows = rows.filter((row) => String(row.capability) === capability)
      if (search) {
        rows = rows.filter((row) => (
          String(row.alias || '').toLowerCase().includes(search)
          || String(row.name || '').toLowerCase().includes(search)
          || String(row.description || '').toLowerCase().includes(search)
          || String(row.capability || '').toLowerCase().includes(search)
          || String(row.status || '').toLowerCase().includes(search)
          || String(row.surface || '').toLowerCase().includes(search)
          || String(row.operation_type || '').toLowerCase().includes(search)
          || String(row.target_entity || '').toLowerCase().includes(search)
        ))
      }

      const applyTextFilter = (key: string, getter: (row: AnyRecord) => string) => {
        const raw = filtersPayload[key]
        if (!isPlainObject(raw)) return
        const value = String(raw.value ?? '').trim().toLowerCase()
        if (!value) return
        rows = rows.filter((row) => getter(row).toLowerCase().includes(value))
      }

      applyTextFilter('name', (row) => String(row.name || ''))
      applyTextFilter('surface', (row) => String(row.surface || ''))
      applyTextFilter('operation_type', (row) => String(row.operation_type || ''))
      applyTextFilter('target_entity', (row) => String(row.target_entity || ''))
      applyTextFilter('capability', (row) => String(row.capability || ''))
      applyTextFilter('status', (row) => String(row.status || ''))
      applyTextFilter('alias', (row) => String(row.alias || ''))

      const isActiveFilter = filtersPayload.is_active
      if (isPlainObject(isActiveFilter)) {
        const raw = String(isActiveFilter.value ?? '').trim().toLowerCase()
        if (raw === 'true' || raw === '1' || raw === 'yes') {
          rows = rows.filter((row) => row.is_active === true)
        } else if (raw === 'false' || raw === '0' || raw === 'no') {
          rows = rows.filter((row) => row.is_active === false)
        }
      }

      const sortKey = String(sortPayload.key ?? '').trim()
      const sortOrder = String(sortPayload.order ?? '').trim().toLowerCase()
      if (sortKey) {
        const direction = sortOrder === 'desc' ? -1 : 1
        rows.sort((left, right) => {
          const leftValue = (
            sortKey === 'name' ? String(left.name || '')
              : sortKey === 'surface' ? String(left.surface || '')
                : sortKey === 'operation_type' ? String(left.operation_type || '')
                  : sortKey === 'target_entity' ? String(left.target_entity || '')
                    : sortKey === 'capability' ? String(left.capability || '')
                      : sortKey === 'status' ? String(left.status || '')
                        : sortKey === 'updated_at' ? String(left.updated_at || '')
                          : sortKey === 'is_active' ? Number(left.is_active === true)
                            : sortKey === 'alias' ? String(left.alias || '')
                              : String(left.alias || '')
          )
          const rightValue = (
            sortKey === 'name' ? String(right.name || '')
              : sortKey === 'surface' ? String(right.surface || '')
                : sortKey === 'operation_type' ? String(right.operation_type || '')
                  : sortKey === 'target_entity' ? String(right.target_entity || '')
                    : sortKey === 'capability' ? String(right.capability || '')
                      : sortKey === 'status' ? String(right.status || '')
                        : sortKey === 'updated_at' ? String(right.updated_at || '')
                          : sortKey === 'is_active' ? Number(right.is_active === true)
                            : sortKey === 'alias' ? String(right.alias || '')
                              : String(right.alias || '')
          )
          if (typeof leftValue === 'number' && typeof rightValue === 'number') {
            return (leftValue - rightValue) * direction
          }
          return String(leftValue).localeCompare(String(rightValue)) * direction
        })
      } else {
        rows.sort((left, right) => {
          const bySurface = String(left.surface).localeCompare(String(right.surface))
          if (bySurface !== 0) return bySurface
          const byOrder = Number(left.display_order ?? 0) - Number(right.display_order ?? 0)
          if (byOrder !== 0) return byOrder
          return String(left.alias).localeCompare(String(right.alias))
        })
      }

      const total = rows.length
      const paged = rows.slice(offset, offset + limit).map((item) => deepClone(item))
      const response: AnyRecord = { exposures: paged, count: paged.length, total }
      if (includeSet.has('definitions')) {
        const definitionIds = new Set(paged.map((item) => String(item.definition_id || '')))
        response.definitions = definitions
          .filter((item) => definitionIds.has(String(item.id || '')))
          .map((item) => deepClone(item))
      }
      return fulfillJson(route, response)
    }

    if (method === 'GET' && path === '/api/v2/operation-catalog/definitions/') {
      counters.operationCatalogDefinitionsGets = (counters.operationCatalogDefinitionsGets ?? 0) + 1
      const limit = parseIntParam(url.searchParams.get('limit'), 50, 1, 1000)
      const offset = parseIntParam(url.searchParams.get('offset'), 0, 0, 100_000)
      const total = definitions.length
      const paged = definitions.slice(offset, offset + limit).map((item) => deepClone(item))
      return fulfillJson(route, { definitions: paged, count: paged.length, total })
    }

    if (method === 'POST' && path === '/api/v2/operation-catalog/validate/') {
      counters.validateCalls = (counters.validateCalls ?? 0) + 1
      const issues = Array.isArray(state.templateValidationErrors)
        ? state.templateValidationErrors
            .filter((item) => isPlainObject(item) && typeof item.path === 'string' && typeof item.message === 'string')
            .map((item) => ({
              path: String(item.path),
              code: typeof item.code === 'string' ? item.code : 'INVALID',
              message: String(item.message),
            }))
        : []
      if (issues.length > 0) {
        return fulfillJson(route, { valid: false, errors: issues })
      }
      return fulfillJson(route, { valid: true, errors: [] })
    }

    if (method === 'POST' && path === '/api/v2/operation-catalog/exposures/') {
      counters.upsertCalls = (counters.upsertCalls ?? 0) + 1
      const payload = parseJsonBody(request.postData())
      upsertPayloads.push(deepClone(payload))
      const exposurePayload = isPlainObject(payload.exposure) ? payload.exposure : {}
      const surface = typeof exposurePayload.surface === 'string' && exposurePayload.surface
        ? exposurePayload.surface
        : 'action_catalog'
      const name = typeof exposurePayload.name === 'string' ? exposurePayload.name.trim() : ''
      const description = typeof exposurePayload.description === 'string' ? exposurePayload.description : ''
      let alias = typeof exposurePayload.alias === 'string' ? exposurePayload.alias.trim() : ''
      if (!alias && surface === 'template') {
        alias = `tpl-custom-${slugify(name || `template-${exposures.length + 1}`)}`
      }
      if (!alias) {
        alias = `action.${exposures.length + 1}`
      }

      const rawDefinitionId = typeof payload.definition_id === 'string' ? payload.definition_id : null
      let definition = rawDefinitionId
        ? definitions.find((item) => String(item.id) === rawDefinitionId)
        : undefined

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
          contract_version: typeof definitionPayload.contract_version === 'number' ? definitionPayload.contract_version : 1,
          status: 'active',
        })
      }

      const rawExposureId = typeof payload.exposure_id === 'string' ? payload.exposure_id : null
      let exposure = rawExposureId
        ? exposures.find((item) => String(item.id) === rawExposureId)
        : undefined
      if (!exposure) {
        exposure = exposures.find((item) => item.surface === surface && String(item.alias) === alias)
      }

      const operationType = String((definition.executor_payload as AnyRecord).operation_type ?? definition.executor_kind ?? '').trim() || 'designer_cli'
      const targetEntity = String((definition.executor_payload as AnyRecord).target_entity ?? 'infobase').trim() || 'infobase'
      const templateData = isPlainObject((definition.executor_payload as AnyRecord).template_data)
        ? deepClone((definition.executor_payload as AnyRecord).template_data)
        : {}

      if (!exposure) {
        exposure = createExposure({
          definition_id: String(definition.id),
          surface,
          alias,
          name: name || alias,
          description,
          capability: typeof exposurePayload.capability === 'string' ? exposurePayload.capability : '',
          contexts: Array.isArray(exposurePayload.contexts)
            ? exposurePayload.contexts.filter((item): item is string => typeof item === 'string')
            : [],
          is_active: exposurePayload.is_active !== false,
          display_order: typeof exposurePayload.display_order === 'number' ? exposurePayload.display_order : 0,
          capability_config: isPlainObject(exposurePayload.capability_config) ? exposurePayload.capability_config : {},
          status: typeof exposurePayload.status === 'string' ? exposurePayload.status : 'draft',
          operation_type: surface === 'template' ? operationType : undefined,
          target_entity: surface === 'template' ? targetEntity : undefined,
          template_data: surface === 'template' ? templateData : undefined,
        })
      }

      exposure.definition_id = String(definition.id)
      exposure.surface = surface
      exposure.alias = alias
      exposure.name = name || exposure.name || alias
      exposure.description = description
      exposure.is_active = exposurePayload.is_active !== false
      exposure.capability = typeof exposurePayload.capability === 'string'
        ? exposurePayload.capability
        : (surface === 'template' ? `templates.${operationType}` : (String(exposure.capability ?? '')))
      exposure.contexts = surface === 'template'
        ? []
        : (Array.isArray(exposurePayload.contexts)
          ? exposurePayload.contexts.filter((item): item is string => typeof item === 'string')
          : (Array.isArray(exposure.contexts) ? exposure.contexts : []))
      exposure.display_order = surface === 'template'
        ? 0
        : (typeof exposurePayload.display_order === 'number' ? exposurePayload.display_order : Number(exposure.display_order ?? 0))
      exposure.capability_config = isPlainObject(exposurePayload.capability_config)
        ? deepClone(exposurePayload.capability_config)
        : (isPlainObject(exposure.capability_config) ? deepClone(exposure.capability_config) : {})
      exposure.status = typeof exposurePayload.status === 'string'
        ? exposurePayload.status
        : (surface === 'template' ? (exposure.is_active ? 'published' : 'draft') : String(exposure.status || 'draft'))
      exposure.updated_at = MOCK_TIMESTAMP

      if (surface === 'template') {
        exposure.operation_type = operationType
        exposure.target_entity = targetEntity
        exposure.template_data = templateData
      }

      return fulfillJson(route, { exposure: deepClone(exposure), definition: deepClone(definition) })
    }

    if (method === 'POST' && /^\/api\/v2\/operation-catalog\/exposures\/[^/]+\/publish\/$/.test(path)) {
      counters.publishCalls = (counters.publishCalls ?? 0) + 1
      const exposureId = decodeURIComponent(path.split('/').filter(Boolean)[4] ?? '')
      const exposure = exposures.find((item) => String(item.id) === exposureId)
      if (!exposure) {
        return fulfillJson(route, { success: false, error: { code: 'NOT_FOUND', message: 'Exposure not found' } }, 404)
      }
      exposure.status = 'published'
      exposure.updated_at = MOCK_TIMESTAMP
      return fulfillJson(route, { published: true, exposure: deepClone(exposure), validation_errors: [] })
    }

    if (method === 'DELETE' && /^\/api\/v2\/operation-catalog\/exposures\/[^/]+\/$/.test(path)) {
      counters.deleteCalls = (counters.deleteCalls ?? 0) + 1
      const exposureId = decodeURIComponent(path.split('/').filter(Boolean)[4] ?? '')
      const idx = exposures.findIndex((item) => String(item.id) === exposureId)
      if (idx < 0) {
        return fulfillJson(route, { success: false, error: { code: 'NOT_FOUND', message: 'Exposure not found' } }, 404)
      }

      const [deleted] = exposures.splice(idx, 1)
      const definitionId = String(deleted.definition_id)
      const hasLinked = exposures.some((item) => String(item.definition_id) === definitionId)
      if (!hasLinked) {
        const definitionIdx = definitions.findIndex((item) => String(item.id) === definitionId)
        if (definitionIdx >= 0) {
          definitions.splice(definitionIdx, 1)
        }
      }

      return fulfillJson(route, { deleted: true, exposure: deepClone(deleted) })
    }

    if (method === 'GET' && path === '/api/v2/operations/driver-commands/') {
      const driver = String(url.searchParams.get('driver') || 'ibcmd')
      return fulfillJson(route, {
        driver,
        base_version: 'v1',
        overrides_version: null,
        generated_at: MOCK_TIMESTAMP,
        catalog: {
          catalog_version: 2,
          driver,
          platform_version: '8.3.27',
          source: { type: 'test' },
          generated_at: MOCK_TIMESTAMP,
          commands_by_id: {
            'infobase.extension.list': {
              label: 'list extensions',
              description: 'List extensions',
              argv: ['infobase', 'extension', 'list'],
              scope: 'per_database',
              risk_level: 'safe',
              params_by_name: {
                format: {
                  kind: 'flag',
                  required: false,
                  expects_value: true,
                  default: 'json',
                  description: 'Output format.',
                },
              },
            },
            'infobase.extension.info': {
              label: 'extension info',
              description: 'Read extension info',
              argv: ['infobase', 'extension', 'info'],
              scope: 'per_database',
              risk_level: 'safe',
              params_by_name: {
                extension_name: {
                  kind: 'flag',
                  required: false,
                  expects_value: true,
                  default: '',
                  description: 'Extension name.',
                },
              },
            },
          },
        },
      })
    }

    if (method === 'GET' && path === '/api/v2/workflows/list-templates/') {
      return fulfillJson(route, { templates: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/ui/operation-exposures/editor-hints/') {
      counters.operationExposureHintsGets = (counters.operationExposureHintsGets ?? 0) + 1
      if (!state.me?.is_staff) {
        return fulfillJson(route, { success: false, error: { code: 'FORBIDDEN', message: 'Forbidden' } }, 403)
      }
      return fulfillJson(route, {
        hints_version: 1,
        capabilities: {
          'extensions.set_flags': {
            target_binding_schema: {
              type: 'object',
              additionalProperties: false,
              required: ['extension_name_param'],
              properties: {
                extension_name_param: {
                  type: 'string',
                  title: 'Target command param',
                  description: 'Command-level parameter name to bind runtime extension_name value.',
                  minLength: 1,
                },
              },
            },
            help: {
              title: 'Runtime source for set_flags values',
              description: 'Flag values are provided at launch via flags_values ($flags.* tokens).',
            },
          },
        },
      })
    }

    if (method === 'GET' && path === '/api/v2/templates/pool-runtime-registry/') {
      counters.poolRuntimeRegistryGets = (counters.poolRuntimeRegistryGets ?? 0) + 1
      if (!state.me?.is_staff) {
        return fulfillJson(route, { success: false, error: { code: 'FORBIDDEN', message: 'Forbidden' } }, 403)
      }
      return fulfillJson(route, {
        contract_version: 'pool_runtime.v1',
        entries: [
          {
            alias: 'pool.prepare_input',
            label: 'Pool Prepare Input',
            status: 'configured',
            issues: [],
            exposure_id: buildMockUuid(70_001),
            exposure_revision: 1,
            operation_type: 'pool.prepare_input',
            target_entity: 'pool_run',
            is_active: true,
            exposure_status: 'published',
            system_managed: true,
            domain: 'pool_runtime',
          },
        ],
        count: 1,
      })
    }

    if (method === 'POST' && path === '/api/v2/ui/execution-plan/preview/') {
      return fulfillJson(route, {
        execution_plan: {
          kind: 'ibcmd_cli',
          argv_masked: ['infobase', 'extension', 'list', '--db-pwd=***'],
        },
        bindings: [],
      })
    }

    return fulfillJson(route, {}, 200)
  })
}

test('Templates: staff работает в templates-only shell без action surface', async ({ page }) => {
  await setupAuth(page)
  const callCounters: MockCounters = {}
  await setupApiMocks(page, {
    me: { id: 1, username: 'admin', is_staff: true },
    templates: [{ id: 'tpl-one', name: 'Template One', command_id: 'infobase.extension.list' }],
    actions: [{ id: 'extensions.list', label: 'List extensions', capability: 'extensions.list' }],
    callCounters,
  })

  await page.goto('/templates', { waitUntil: 'domcontentloaded' })

  const tableBody = page.locator('.ant-table-tbody:visible').first()

  await expect(page.getByRole('heading', { name: 'Operation Templates', exact: true })).toBeVisible()
  await expect.poll(() => new URL(page.url()).searchParams.get('surface')).toBeNull()
  await expect(tableBody).toContainText('Template One')
  await expect(tableBody).not.toContainText('extensions.list')
  await expect(page.getByTestId('action-catalog-add')).toHaveCount(0)
  await expect(page.getByTestId('templates-pool-runtime-registry')).toBeVisible()

  expect(callCounters.operationCatalogExposuresGets ?? 0).toBeGreaterThan(0)
  expect(callCounters.operationCatalogActionExposuresGets ?? 0).toBe(0)
  expect(callCounters.operationCatalogExposuresWithDefinitionsGets ?? 0).toBe(0)
  expect(callCounters.operationCatalogDefinitionsGets ?? 0).toBe(0)
  expect(callCounters.poolRuntimeRegistryGets ?? 0).toBeGreaterThan(0)
  expect(callCounters.operationExposureHintsGets ?? 0).toBe(0)
  expect(callCounters.legacyTemplateCalls ?? 0).toBe(0)
  expect(callCounters.legacyActionHintsCalls ?? 0).toBe(0)
  expect(callCounters.legacyActionCatalogCalls ?? 0).toBe(0)
})

test('Templates: staff deep-link на template остаётся в templates-only shell', async ({ page }) => {
  await setupAuth(page)
  const callCounters: MockCounters = {}
  await setupApiMocks(page, {
    me: { id: 11, username: 'admin', is_staff: true },
    templates: [{ id: 'tpl-one', name: 'Template One' }],
    actions: [{ id: 'extensions.list', label: 'List extensions', capability: 'extensions.list' }],
    callCounters,
  })

  await page.goto('/templates?surface=template', { waitUntil: 'domcontentloaded' })
  const tableBody = page.locator('.ant-table-tbody:visible').first()

  await expect(page.getByRole('heading', { name: 'Operation Templates', exact: true })).toBeVisible()
  await expect.poll(() => new URL(page.url()).searchParams.get('surface')).toBeNull()
  await expect(tableBody).toContainText('Template One')
  await expect(tableBody).not.toContainText('extensions.list')

  expect(callCounters.operationCatalogActionExposuresGets ?? 0).toBe(0)
  expect(callCounters.operationCatalogExposuresWithDefinitionsGets ?? 0).toBe(0)
  expect(callCounters.operationCatalogDefinitionsGets ?? 0).toBe(0)
})

test('Templates: non-staff deep-link на template открывает templates-only view', async ({ page }) => {
  await setupAuth(page)
  const callCounters: MockCounters = {}
  await setupApiMocks(page, {
    me: { id: 2, username: 'viewer', is_staff: false },
    templates: [{ id: 'tpl-view', name: 'Viewer Template' }],
    actions: [{ id: 'extensions.hidden', label: 'Hidden Action', capability: 'extensions.hidden' }],
    callCounters,
  })

  await page.goto('/templates?surface=template', { waitUntil: 'domcontentloaded' })

  const tableBody = page.locator('.ant-table-tbody:visible').first()

  await expect(page.getByRole('heading', { name: 'Operation Templates', exact: true })).toBeVisible()
  await expect(tableBody).toContainText('Viewer Template')
  await expect.poll(() => new URL(page.url()).searchParams.get('surface')).toBeNull()
  await expect(page.getByRole('button', { name: 'New Template', exact: true })).toHaveCount(0)
  await expect(page.getByTestId('templates-pool-runtime-registry')).toHaveCount(0)

  expect(callCounters.operationCatalogActionExposuresGets ?? 0).toBe(0)
  expect(callCounters.operationCatalogDefinitionsGets ?? 0).toBe(0)
  expect(callCounters.poolRuntimeRegistryGets ?? 0).toBe(0)
  expect(callCounters.operationExposureHintsGets ?? 0).toBe(0)
  expect(callCounters.legacyTemplateCalls ?? 0).toBe(0)
  expect(callCounters.legacyActionHintsCalls ?? 0).toBe(0)
})

test('Templates: non-staff с MANAGE по templates получает template controls без action controls', async ({ page }) => {
  await setupAuth(page)
  const callCounters: MockCounters = {}
  await setupApiMocks(page, {
    me: { id: 4, username: 'template-manager', is_staff: false },
    templates: [{ id: 'tpl-manage', name: 'Template Manage' }],
    actions: [{ id: 'extensions.hidden', label: 'Hidden Action', capability: 'extensions.hidden' }],
    templateAccessById: {
      'tpl-manage': 'MANAGE',
    },
    callCounters,
  })

  await page.goto('/templates', { waitUntil: 'domcontentloaded' })
  const tableBody = page.locator('.ant-table-tbody:visible').first()

  await expect(page.getByRole('heading', { name: 'Operation Templates', exact: true })).toBeVisible()
  await expect.poll(() => new URL(page.url()).searchParams.get('surface')).toBeNull()
  await expect(tableBody).toContainText('Template Manage')
  await expect(page.getByRole('button', { name: 'New Template', exact: true })).toBeVisible()
  await expect(page.getByTestId('action-catalog-add')).toHaveCount(0)

  await tableBody.getByRole('button', { name: 'Edit', exact: true }).first().click()
  await expect(page.getByTestId('operation-exposure-editor-name')).toBeVisible()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(page.getByTestId('operation-exposure-editor-name')).toBeHidden()

  expect(callCounters.operationCatalogActionExposuresGets ?? 0).toBe(0)
  expect(callCounters.operationCatalogDefinitionsGets ?? 0).toBe(0)
})

test('Templates: system-managed pool runtime template блокирует edit/delete controls', async ({ page }) => {
  await setupAuth(page)
  const callCounters: MockCounters = {}
  await setupApiMocks(page, {
    me: { id: 5, username: 'admin', is_staff: true },
    templates: [{
      id: 'pool.prepare_input',
      name: 'Pool Prepare Input',
      system_managed: true,
      domain: 'pool_runtime',
    }],
    callCounters,
  })

  await page.goto('/templates', { waitUntil: 'domcontentloaded' })
  const tableBody = page.locator('.ant-table-tbody:visible').first()
  const row = tableBody.locator('tr').filter({ hasText: 'pool.prepare_input' }).first()

  await expect(row).toBeVisible()
  await expect(row).toContainText('system-managed')
  await expect(row).toContainText('pool_runtime')
  await expect(row.getByRole('button', { name: 'Edit', exact: true })).toBeDisabled()
  await expect(row.getByRole('button', { name: 'Delete', exact: true })).toBeDisabled()
  expect(callCounters.poolRuntimeRegistryGets ?? 0).toBeGreaterThan(0)
})

test('Templates: единый editor shell работает только для template flow', async ({ page }) => {
  await setupAuth(page)
  const callCounters: MockCounters = {}
  const upsertPayloads: AnyRecord[] = []
  await setupApiMocks(page, {
    me: { id: 3, username: 'staff', is_staff: true },
    templates: [],
    actions: [],
    callCounters,
    upsertPayloads,
  })

  await page.goto('/templates', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Operation Templates', exact: true })).toBeVisible()
  await expect.poll(() => new URL(page.url()).searchParams.get('surface')).toBeNull()
  await expect(page.getByTestId('action-catalog-add')).toHaveCount(0)

  await page.getByRole('button', { name: 'New Template', exact: true }).click()
  await expect(page.getByRole('tab', { name: 'Basics', exact: true })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Executor', exact: true })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Params', exact: true })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Safety & Fixed', exact: true })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Preview', exact: true })).toBeVisible()
  await expect(page.getByText('OperationExposure.alias', { exact: true })).toBeHidden()
  await page.getByText('Source of truth (binding provenance)', { exact: true }).click()
  await expect(page.getByTestId('operation-exposure-editor-source-of-truth')).toContainText('OperationExposure.alias')

  await page.getByTestId('operation-exposure-editor-name').fill('Template via unified modal')
  await page.getByTestId('action-catalog-editor-command-id').click()
  await page.keyboard.type('infobase.extension.info')
  await page.keyboard.press('Enter')
  await page.getByTestId('action-catalog-editor-open-preview-tab').click()
  await expect(page.getByTestId('operation-exposure-editor-execution-preview-json')).toContainText('infobase.extension.info')
  await expect(page.getByTestId('operation-exposure-editor-field-origins')).toContainText('OperationDefinition.executor_payload.operation_type')
  await page.getByTestId('action-catalog-editor-apply').click()

  await expect(page.locator('.ant-table-tbody:visible').first()).toContainText('Template via unified modal')

  expect(callCounters.upsertCalls ?? 0).toBeGreaterThanOrEqual(1)
  expect(callCounters.operationExposureHintsGets ?? 0).toBeGreaterThanOrEqual(1)
  expect(callCounters.operationCatalogActionExposuresGets ?? 0).toBe(0)
  expect(callCounters.legacyActionHintsCalls ?? 0).toBe(0)
  expect(callCounters.legacyActionCatalogCalls ?? 0).toBe(0)

  expect(upsertPayloads.some((payload) => {
    const exposure = isPlainObject(payload.exposure) ? payload.exposure : null
    if (!exposure) return false
    return exposure.surface === 'template'
  })).toBe(true)
})

test('Templates: backend validation_errors подсвечивают поля модалки и блокируют save', async ({ page }) => {
  await setupAuth(page)
  const callCounters: MockCounters = {}
  await setupApiMocks(page, {
    me: { id: 5, username: 'staff', is_staff: true },
    templates: [],
    actions: [],
    callCounters,
    templateValidationErrors: [
      {
        path: 'definition.executor_payload.command_id',
        code: 'UNKNOWN_COMMAND',
        message: 'unknown command_id: infobase.extension.info',
      },
      {
        path: 'definition.executor_payload.template_data',
        code: 'INVALID_TYPE',
        message: 'template_data must be an object',
      },
    ],
  })

  await page.goto('/templates', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'New Template', exact: true }).click()
  await page.getByTestId('operation-exposure-editor-name').fill('Template blocked by validation')
  await page.getByTestId('action-catalog-editor-command-id').click()
  await page.keyboard.type('infobase.extension.info')
  await page.keyboard.press('Enter')
  await page.getByTestId('action-catalog-editor-apply').click()

  await expect(page.getByTestId('operation-exposure-editor-backend-validation-errors')).toContainText('definition.executor_payload.command_id')
  await expect(page.getByTestId('operation-exposure-editor-backend-validation-errors')).toContainText('unknown command_id: infobase.extension.info')
  await expect(page.getByTestId('operation-exposure-editor-backend-validation-errors')).toContainText('template_data must be an object')
  await expect(page.locator('.ant-form-item-explain-error').filter({ hasText: 'unknown command_id: infobase.extension.info' })).toHaveCount(1)
  await expect(page.locator('.ant-form-item-explain-error').filter({ hasText: 'template_data must be an object' })).toHaveCount(1)

  expect(callCounters.validateCalls ?? 0).toBeGreaterThanOrEqual(1)
  expect(callCounters.upsertCalls ?? 0).toBe(0)
})
