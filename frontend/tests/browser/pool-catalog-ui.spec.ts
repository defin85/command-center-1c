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
  pools?: AnyRecord[]
  bindingProfiles?: AnyRecord[]
  bindingUpsertCalls?: number
  bindingDeleteCalls?: number
  lastBindingPayload?: AnyRecord | null
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
  const pools: AnyRecord[] = [...(state.pools ?? [
    {
      id: '99999999-9999-9999-9999-999999999999',
      code: 'pool-main',
      name: 'Main Pool',
      is_active: true,
      metadata: {},
      workflow_bindings: [],
      updated_at: '2026-01-01T00:00:00Z',
    },
  ])]
  const bindingProfiles: AnyRecord[] = [...(state.bindingProfiles ?? [
    {
      binding_profile_id: 'bp-services',
      code: 'services-publication-profile',
      name: 'Services Publication Profile',
      description: 'Reusable profile for services publication',
      status: 'active',
      latest_revision_number: 2,
      latest_revision: {
        binding_profile_revision_id: 'bp-rev-services-r2',
        binding_profile_id: 'bp-services',
        revision_number: 2,
        workflow: {
          workflow_definition_key: 'services-publication',
          workflow_revision_id: '11111111-1111-1111-1111-111111111111',
          workflow_revision: 3,
          workflow_name: 'services_publication',
        },
        decisions: [],
        parameters: {},
        role_mapping: {},
        metadata: { source: 'manual' },
        created_at: '2026-01-01T00:00:00Z',
      },
      created_by: 'test',
      updated_by: 'test',
      deactivated_by: null,
      deactivated_at: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ])]
  state.bindingUpsertCalls = state.bindingUpsertCalls ?? 0
  state.bindingDeleteCalls = state.bindingDeleteCalls ?? 0
  state.lastBindingPayload = state.lastBindingPayload ?? null
  const bindingCollectionEtags = new Map<string, string>()
  const computeBindingCollectionEtag = (bindings: AnyRecord[]) => (
    `sha256:${Buffer.from(JSON.stringify(bindings)).toString('hex').slice(0, 64).padEnd(64, '0')}`
  )
  const getBindingCollectionEtag = (poolId: string, bindings: AnyRecord[]) => {
    const existing = bindingCollectionEtags.get(poolId)
    if (existing) {
      return existing
    }
    const next = computeBindingCollectionEtag(bindings)
    bindingCollectionEtags.set(poolId, next)
    return next
  }

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
        pools,
        count: pools.length,
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/binding-profiles/') {
      return fulfillJson(route, {
        binding_profiles: bindingProfiles,
        count: bindingProfiles.length,
      })
    }

    if (method === 'POST' && path === '/api/v2/pools/upsert/') {
      const payload = request.postDataJSON() as AnyRecord
      const poolId = String(payload.pool_id || '99999999-9999-9999-9999-999999999999')
      const existingPool = pools.find((item) => String(item.id) === poolId)
      const pool = existingPool ?? {
        id: poolId,
        metadata: {},
        workflow_bindings: [],
        updated_at: '2026-01-01T00:00:00Z',
      }
      pool.code = String(payload.code || '')
      pool.name = String(payload.name || '')
      pool.description = String(payload.description || '')
      pool.is_active = payload.is_active !== false
      pool.metadata = payload.metadata && typeof payload.metadata === 'object' ? payload.metadata : {}
      pool.updated_at = '2026-01-01T00:00:00Z'
      if (!existingPool) {
        pools.push(pool)
      }
      return fulfillJson(route, { pool, created: !existingPool }, existingPool ? 200 : 201)
    }

    if (method === 'GET' && path === '/api/v2/pools/workflow-bindings/') {
      const poolId = String(url.searchParams.get('pool_id') || '')
      const pool = pools.find((item) => String(item.id) === poolId)
      const bindings = Array.isArray(pool?.workflow_bindings) ? pool.workflow_bindings : []
      return fulfillJson(route, {
        pool_id: poolId,
        workflow_bindings: bindings,
        collection_etag: getBindingCollectionEtag(poolId, bindings),
        blocking_remediation: null,
      })
    }

    if (method === 'PUT' && path === '/api/v2/pools/workflow-bindings/') {
      const payload = request.postDataJSON() as AnyRecord
      const poolId = String(payload.pool_id || '')
      const pool = pools.find((item) => String(item.id) === poolId)
      if (!pool) {
        return fulfillJson(route, { type: 'about:blank', title: 'Pool Not Found', status: 404, detail: 'Pool not found.' }, 404)
      }

      const currentBindings = Array.isArray(pool.workflow_bindings) ? [...pool.workflow_bindings] : []
      const currentEtag = getBindingCollectionEtag(poolId, currentBindings)
      if (String(payload.expected_collection_etag || '') !== currentEtag) {
        return fulfillJson(route, {
          type: 'about:blank',
          title: 'Workflow Binding Collection Conflict',
          status: 409,
          detail: 'Workflow binding collection was updated by another operator. Reload bindings and retry.',
          code: 'POOL_WORKFLOW_BINDING_COLLECTION_CONFLICT',
        }, 409)
      }

      const submittedBindings = Array.isArray(payload.workflow_bindings) ? payload.workflow_bindings : []
      const nextBindings = submittedBindings.map((rawBinding, index) => {
        const workflowBinding = rawBinding && typeof rawBinding === 'object'
          ? { ...(rawBinding as AnyRecord) }
          : {}
        return {
          ...workflowBinding,
          binding_id: String(workflowBinding.binding_id || `binding-${index + 1}`),
          pool_id: poolId,
          revision: Number(workflowBinding.revision || 1),
        }
      })

      state.bindingUpsertCalls! += 1
      state.lastBindingPayload = payload
      pool.workflow_bindings = nextBindings
      pool.updated_at = '2026-01-01T00:00:00Z'
      const nextEtag = computeBindingCollectionEtag(nextBindings)
      bindingCollectionEtags.set(poolId, nextEtag)

      return fulfillJson(route, {
        pool_id: poolId,
        workflow_bindings: nextBindings,
        collection_etag: nextEtag,
        blocking_remediation: null,
      })
    }

    if (method === 'POST' && path === '/api/v2/pools/workflow-bindings/upsert/') {
      const payload = request.postDataJSON() as AnyRecord
      const poolId = String(payload.pool_id || '')
      const pool = pools.find((item) => String(item.id) === poolId)
      if (!pool) {
        return fulfillJson(route, { type: 'about:blank', title: 'Pool Not Found', status: 404, detail: 'Pool not found.' }, 404)
      }

      const workflowBinding = payload.workflow_binding && typeof payload.workflow_binding === 'object'
        ? { ...(payload.workflow_binding as AnyRecord) }
        : {}
      const bindingId = String(workflowBinding.binding_id || `binding-${state.bindingUpsertCalls! + 1}`)
      const existingBindings = Array.isArray(pool.workflow_bindings) ? [...pool.workflow_bindings] : []
      const existingBinding = existingBindings.find((item) => String(item.binding_id || '') === bindingId)
      const nextRevision = existingBinding ? Number(existingBinding.revision || 1) + 1 : 1
      workflowBinding.binding_id = bindingId
      workflowBinding.pool_id = poolId
      workflowBinding.revision = nextRevision
      state.bindingUpsertCalls! += 1
      state.lastBindingPayload = payload

      const nextBindings = existingBindings.filter((item) => String(item.binding_id || '') !== bindingId)
      nextBindings.push(workflowBinding)
      pool.workflow_bindings = nextBindings
      pool.updated_at = '2026-01-01T00:00:00Z'
      return fulfillJson(route, { pool_id: poolId, workflow_binding: workflowBinding, created: existingBinding == null }, existingBinding == null ? 201 : 200)
    }

    if (method === 'DELETE' && path.startsWith('/api/v2/pools/workflow-bindings/')) {
      const bindingId = path.split('/')[5] || ''
      const poolId = String(url.searchParams.get('pool_id') || '')
      const revision = Number(url.searchParams.get('revision') || '')
      const pool = pools.find((item) => String(item.id) === poolId)
      if (!pool) {
        return fulfillJson(route, { type: 'about:blank', title: 'Pool Not Found', status: 404, detail: 'Pool not found.' }, 404)
      }
      const existingBindings = Array.isArray(pool.workflow_bindings) ? [...pool.workflow_bindings] : []
      const binding = existingBindings.find((item) => String(item.binding_id || '') === bindingId)
      if (!Number.isInteger(revision) || revision <= 0) {
        return fulfillJson(route, { type: 'about:blank', title: 'Validation Error', status: 400, detail: 'revision is required.' }, 400)
      }
      pool.workflow_bindings = existingBindings.filter((item) => String(item.binding_id || '') !== bindingId)
      state.bindingDeleteCalls! += 1
      return fulfillJson(route, { pool_id: poolId, workflow_binding: binding ?? { binding_id: bindingId }, deleted: true })
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
  await expect(page.getByText('Mutating actions are disabled', { exact: true }).first()).toBeVisible()
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

  await expect(page.locator('.ant-table-tbody tr').filter({ hasText: 'Created Org' }).first()).toBeVisible()

  await page.locator('.ant-table-tbody tr').filter({ hasText: 'Created Org' }).first().click()
  await page.getByTestId('pool-catalog-edit-org').click()
  await page.locator('#name').fill('Created Org Updated')
  await page.getByRole('button', { name: 'Save', exact: true }).click()

  await expect(page.locator('.ant-table-tbody tr').filter({ hasText: 'Created Org Updated' }).first()).toBeVisible()

  await page.getByTestId('pool-catalog-sync-orgs').click()
  await page.getByTestId('pool-catalog-sync-input').fill(
    '{"rows":[{"inn":"730000000555","name":"Created Org Synced"},{"inn":"730000000556","name":"Synced Org"}]}'
  )
  await page.getByRole('button', { name: 'Run sync', exact: true }).click()

  await expect(page.getByText('Sync completed', { exact: true })).toBeVisible()
  await expect(page.getByText(/total_rows/i)).toBeVisible()
  await expect(page.getByText('Synced Org', { exact: true })).toBeVisible()
})

test('Pool Catalog: workflow bindings editor saves through canonical collection API', async ({ page }) => {
  const state = {
    me: { id: 1, username: 'user', is_staff: false },
    myTenants: { active_tenant_id: 't1', tenants: [{ id: 't1', slug: 'default', name: 'Default' }] },
    bindingUpsertCalls: 0,
    bindingDeleteCalls: 0,
    lastBindingPayload: null as AnyRecord | null,
  }

  await setupAuth(page, { activeTenantId: 't1' })
  await setupApiMocks(page, state)

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: 'Bindings' }).click()

  await expect(page.getByTestId('pool-catalog-workflow-binding-add')).toBeVisible()
  await expect(page.getByLabel('Workflow bindings JSON')).toHaveCount(0)

  await page.getByTestId('pool-catalog-workflow-binding-add').click()
  await page.getByTestId('pool-catalog-workflow-binding-profile-revision-0').click()
  await page.getByText('services-publication-profile · Services Publication Profile · r2 · active', { exact: true }).click()
  await page.getByTestId('pool-catalog-workflow-binding-effective-from-0').fill('2026-01-01')
  await page.getByTestId('pool-catalog-workflow-binding-selector-direction-0').fill('top_down')
  await page.getByTestId('pool-catalog-workflow-binding-selector-mode-0').fill('safe')
  await page.getByTestId('pool-catalog-workflow-binding-selector-tags-0').fill('baseline, monthly')
  await page.getByTestId('pool-catalog-save-bindings').click()

  await expect.poll(() => state.bindingUpsertCalls).toBe(1)
  await expect.poll(() => state.bindingDeleteCalls).toBe(0)
  await expect.poll(() => state.lastBindingPayload).toMatchObject({
    pool_id: '99999999-9999-9999-9999-999999999999',
    workflow_bindings: [
      {
        binding_profile_revision_id: 'bp-rev-services-r2',
        selector: {
          direction: 'top_down',
          mode: 'safe',
          tags: ['baseline', 'monthly'],
        },
        effective_from: '2026-01-01',
        status: 'draft',
      },
    ],
  })
  expect(String(state.lastBindingPayload?.expected_collection_etag || '')).toMatch(/^sha256:/)
})
