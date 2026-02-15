import { expect, test, type Page, type Route } from '@playwright/test'

type AnyRecord = Record<string, unknown>

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>
  }
}

const TENANT_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
const NOW = '2026-01-01T00:00:00Z'

async function fulfillJson(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
    headers: { 'cache-control': 'no-store' },
  })
}

async function setupAuth(page: Page) {
  await page.addInitScript((tenantId: string) => {
    window.__CC1C_ENV__ = {
      VITE_BASE_HOST: '127.0.0.1',
      VITE_API_URL: 'http://127.0.0.1:15173',
      VITE_WS_HOST: '127.0.0.1:15173',
    }
    localStorage.setItem('auth_token', 'test-token')
    localStorage.setItem('active_tenant_id', tenantId)
  }, TENANT_ID)
}

async function setupApiMocks(page: Page, state: {
  pools: AnyRecord[]
  graphByPoolId: Record<string, AnyRecord>
  runs: AnyRecord[]
  createRunCalls: number
  confirmCalls: number
  topologyUpsertCalls: number
}) {
  const organizations: AnyRecord[] = [
    {
      id: '11111111-1111-1111-1111-111111111111',
      tenant_id: TENANT_ID,
      database_id: '10101010-1010-1010-1010-101010101010',
      name: 'Org One',
      full_name: 'Org One LLC',
      inn: '730000000001',
      kpp: '123456789',
      status: 'active',
      external_ref: '',
      metadata: {},
      created_at: NOW,
      updated_at: NOW,
    },
    {
      id: '22222222-2222-2222-2222-222222222222',
      tenant_id: TENANT_ID,
      database_id: '20202020-2020-2020-2020-202020202020',
      name: 'Org Two',
      full_name: 'Org Two LLC',
      inn: '730000000002',
      kpp: '123456789',
      status: 'active',
      external_ref: '',
      metadata: {},
      created_at: NOW,
      updated_at: NOW,
    },
    {
      id: '33333333-3333-3333-3333-333333333333',
      tenant_id: TENANT_ID,
      database_id: '30303030-3030-3030-3030-303030303030',
      name: 'Org Three',
      full_name: 'Org Three LLC',
      inn: '730000000003',
      kpp: '123456789',
      status: 'active',
      external_ref: '',
      metadata: {},
      created_at: NOW,
      updated_at: NOW,
    },
  ]

  let poolSequence = 1
  let runSequence = 1
  let topologyVersionSequence = 1

  const buildPoolId = () => `90000000-0000-4000-8000-${String(poolSequence++).padStart(12, '0')}`
  const buildRunId = () => `91000000-0000-4000-8000-${String(runSequence++).padStart(12, '0')}`
  const nextTopologyVersion = () => `v1:pool-topology-${topologyVersionSequence++}`

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'smoke-user', is_staff: false })
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
      return fulfillJson(route, {
        active_tenant_id: TENANT_ID,
        tenants: [{ id: TENANT_ID, slug: 'default', name: 'Default', role: 'owner' }],
      })
    }
    if (method === 'GET' && path === '/api/v2/databases/list-databases/') {
      return fulfillJson(route, {
        databases: organizations.map((item) => ({ id: item.database_id, name: `${item.name}-db` })),
        count: organizations.length,
        total: organizations.length,
      })
    }
    if (method === 'GET' && path === '/api/v2/pools/organizations/') {
      return fulfillJson(route, { organizations, count: organizations.length })
    }
    if (method === 'GET' && path.startsWith('/api/v2/pools/organizations/')) {
      const organizationId = path.replace('/api/v2/pools/organizations/', '').replace('/', '')
      const organization = organizations.find((item) => String(item.id) === organizationId)
      if (!organization) {
        return fulfillJson(route, { success: false, error: { code: 'ORGANIZATION_NOT_FOUND', message: 'Not found' } }, 404)
      }
      return fulfillJson(route, { organization, pool_bindings: [] })
    }
    if (method === 'POST' && path === '/api/v2/pools/upsert/') {
      const payload = request.postDataJSON() as AnyRecord
      const now = NOW
      const requestedId = String(payload.pool_id || '').trim()
      let pool = requestedId
        ? state.pools.find((item) => String(item.id) === requestedId)
        : undefined
      const created = !pool
      if (!pool) {
        pool = {
          id: buildPoolId(),
          metadata: {},
          updated_at: now,
        }
        state.pools.push(pool)
      }
      pool.code = String(payload.code || '').trim() || 'pool-smoke'
      pool.name = String(payload.name || '').trim() || 'Smoke Pool'
      pool.description = String(payload.description || '')
      pool.is_active = payload.is_active !== false
      pool.metadata = payload.metadata && typeof payload.metadata === 'object' ? payload.metadata : {}
      pool.updated_at = now

      const poolId = String(pool.id)
      if (!state.graphByPoolId[poolId]) {
        state.graphByPoolId[poolId] = {
          pool_id: poolId,
          date: '2026-01-01',
          version: nextTopologyVersion(),
          nodes: [],
          edges: [],
        }
      }
      return fulfillJson(route, { pool, created }, created ? 201 : 200)
    }
    if (method === 'GET' && path === '/api/v2/pools/') {
      return fulfillJson(route, { pools: state.pools, count: state.pools.length })
    }
    if (method === 'GET' && path.startsWith('/api/v2/pools/') && path.endsWith('/graph/')) {
      const poolId = path.split('/')[4] || ''
      const graph = state.graphByPoolId[poolId] || {
        pool_id: poolId,
        date: '2026-01-01',
        version: nextTopologyVersion(),
        nodes: [],
        edges: [],
      }
      state.graphByPoolId[poolId] = graph
      const requestedDate = String(url.searchParams.get('date') || graph.date || '2026-01-01')
      return fulfillJson(route, { ...graph, date: requestedDate })
    }
    if (method === 'POST' && path.startsWith('/api/v2/pools/') && path.endsWith('/topology-snapshot/upsert/')) {
      const poolId = path.split('/')[4] || ''
      const payload = request.postDataJSON() as AnyRecord
      const graph = state.graphByPoolId[poolId] || {
        pool_id: poolId,
        date: '2026-01-01',
        version: nextTopologyVersion(),
        nodes: [],
        edges: [],
      }
      if (String(payload.version || '') !== String(graph.version || '')) {
        return fulfillJson(route, {
          type: 'about:blank',
          title: 'Topology Version Conflict',
          status: 409,
          detail: 'Topology snapshot was changed by another session.',
          code: 'TOPOLOGY_VERSION_CONFLICT',
        }, 409)
      }

      state.topologyUpsertCalls += 1
      const nodesPayload = Array.isArray(payload.nodes) ? payload.nodes : []
      const edgesPayload = Array.isArray(payload.edges) ? payload.edges : []
      const nodeIdByOrganization = new Map<string, string>()
      const nextNodes = nodesPayload.map((node: AnyRecord, index: number) => {
        const organizationId = String(node.organization_id || '')
        const organization = organizations.find((item) => String(item.id) === organizationId)
        const nodeVersionId = `92000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`
        nodeIdByOrganization.set(organizationId, nodeVersionId)
        return {
          node_version_id: nodeVersionId,
          organization_id: organizationId,
          inn: organization?.inn || '',
          name: organization?.name || organizationId,
          is_root: Boolean(node.is_root),
        }
      })
      const nextEdges = edgesPayload.map((edge: AnyRecord, index: number) => {
        const parentOrganizationId = String(edge.parent_organization_id || '')
        const childOrganizationId = String(edge.child_organization_id || '')
        return {
          edge_version_id: `93000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
          parent_node_version_id: nodeIdByOrganization.get(parentOrganizationId) || '',
          child_node_version_id: nodeIdByOrganization.get(childOrganizationId) || '',
          weight: String(edge.weight || '1.0'),
          min_amount: edge.min_amount == null ? null : String(edge.min_amount),
          max_amount: edge.max_amount == null ? null : String(edge.max_amount),
        }
      })

      const nextGraph = {
        pool_id: poolId,
        date: String(payload.effective_from || graph.date || '2026-01-01'),
        version: nextTopologyVersion(),
        nodes: nextNodes,
        edges: nextEdges,
      }
      state.graphByPoolId[poolId] = nextGraph
      return fulfillJson(route, {
        pool_id: poolId,
        version: nextGraph.version,
        effective_from: nextGraph.date,
        effective_to: payload.effective_to == null ? null : String(payload.effective_to),
        nodes_count: nextNodes.length,
        edges_count: nextEdges.length,
      })
    }
    if (method === 'GET' && path === '/api/v2/pools/schema-templates/') {
      return fulfillJson(route, { templates: [], count: 0 })
    }
    if (method === 'GET' && path === '/api/v2/pools/runs/') {
      const poolId = String(url.searchParams.get('pool_id') || '')
      const runs = state.runs.filter((item) => !poolId || String(item.pool_id) === poolId)
      return fulfillJson(route, { runs, count: runs.length })
    }
    if (method === 'POST' && path === '/api/v2/pools/runs/') {
      state.createRunCalls += 1
      const payload = request.postDataJSON() as AnyRecord
      const runId = buildRunId()
      const workflowRunId = `94000000-0000-4000-8000-${String(runSequence).padStart(12, '0')}`
      const run = {
        id: runId,
        tenant_id: TENANT_ID,
        pool_id: String(payload.pool_id || ''),
        schema_template_id: payload.schema_template_id == null ? null : String(payload.schema_template_id),
        mode: String(payload.mode || 'safe'),
        direction: String(payload.direction || 'top_down'),
        status: 'validated',
        status_reason: 'awaiting_approval',
        period_start: String(payload.period_start || '2026-01-01'),
        period_end: payload.period_end == null ? null : String(payload.period_end),
        run_input: payload.run_input && typeof payload.run_input === 'object' ? payload.run_input : null,
        input_contract_version: 'run_input_v1',
        idempotency_key: `idem-${runId}`,
        workflow_execution_id: workflowRunId,
        workflow_status: 'pending',
        approval_state: 'awaiting_approval',
        publication_step_state: 'not_enqueued',
        terminal_reason: null,
        execution_backend: 'workflow_core',
        provenance: {
          workflow_run_id: workflowRunId,
          workflow_status: 'pending',
          execution_backend: 'workflow_core',
          retry_chain: [
            {
              workflow_run_id: workflowRunId,
              parent_workflow_run_id: null,
              attempt_number: 1,
              attempt_kind: 'initial',
              status: 'pending',
            },
          ],
        },
        workflow_template_name: 'pool-template-v1',
        seed: null,
        validation_summary: { rows: 1 },
        publication_summary: { total_targets: 1 },
        diagnostics: [],
        last_error: '',
        created_at: NOW,
        updated_at: NOW,
        validated_at: NOW,
        publication_confirmed_at: null,
        publishing_started_at: null,
        completed_at: null,
      }
      state.runs = [run, ...state.runs.filter((item) => String(item.id) !== runId)]
      return fulfillJson(route, { run, created: true }, 201)
    }
    if (method === 'POST' && path.startsWith('/api/v2/pools/runs/') && path.endsWith('/confirm-publication/')) {
      const runId = path.split('/')[5] || ''
      const run = state.runs.find((item) => String(item.id) === runId)
      if (!run) {
        return fulfillJson(route, { success: false, error: { code: 'RUN_NOT_FOUND', message: 'Not found' } }, 404)
      }
      state.confirmCalls += 1
      run.approval_state = 'approved'
      run.publication_step_state = 'queued'
      run.status_reason = 'queued'
      run.workflow_status = 'running'
      run.updated_at = NOW
      run.publication_confirmed_at = NOW
      if (run.provenance && typeof run.provenance === 'object') {
        ;(run.provenance as AnyRecord).workflow_status = 'running'
      }
      return fulfillJson(route, {
        run,
        command_type: 'confirm-publication',
        result: 'accepted',
        replayed: false,
      })
    }
    if (method === 'POST' && path.startsWith('/api/v2/pools/runs/') && path.endsWith('/abort-publication/')) {
      return fulfillJson(route, {
        success: false,
        error_code: 'COMMAND_CONFLICT',
        error_message: 'abort is disabled in smoke test',
        conflict_reason: 'terminal_state',
        retryable: false,
      }, 409)
    }
    if (method === 'GET' && path.startsWith('/api/v2/pools/runs/') && path.endsWith('/report/')) {
      const runId = path.split('/')[5] || ''
      const run = state.runs.find((item) => String(item.id) === runId)
      if (!run) {
        return fulfillJson(route, { success: false, error: { code: 'RUN_NOT_FOUND', message: 'Not found' } }, 404)
      }
      return fulfillJson(route, {
        run,
        publication_attempts: [],
        validation_summary: run.validation_summary || { rows: 1 },
        publication_summary: run.publication_summary || { total_targets: 1 },
        diagnostics: run.diagnostics || [],
        attempts_by_status: {},
      })
    }
    if (method === 'POST' && path.startsWith('/api/v2/pools/runs/') && path.endsWith('/retry/')) {
      return fulfillJson(route, {
        accepted: true,
        workflow_execution_id: '95000000-0000-4000-8000-000000000001',
        operation_id: null,
        retry_target_summary: {
          requested_targets: 0,
          requested_documents: 0,
          failed_targets: 0,
          enqueued_targets: 0,
          skipped_successful_targets: 0,
        },
      })
    }

    return fulfillJson(route, {}, 200)
  })
}

test('Pools full flow smoke: 3 org -> minimal pool -> top_down run -> confirm publication', async ({ page }) => {
  const state = {
    pools: [] as AnyRecord[],
    graphByPoolId: {} as Record<string, AnyRecord>,
    runs: [] as AnyRecord[],
    createRunCalls: 0,
    confirmCalls: 0,
    topologyUpsertCalls: 0,
  }

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Catalog', exact: true })).toBeVisible()
  await expect(page.locator('.ant-table-tbody tr', { hasText: 'Org One' }).first()).toBeVisible()
  await expect(page.locator('.ant-table-tbody tr', { hasText: 'Org Two' }).first()).toBeVisible()
  await expect(page.locator('.ant-table-tbody tr', { hasText: 'Org Three' }).first()).toBeVisible()

  await page.getByTestId('pool-catalog-add-pool').click()
  await page.getByLabel('Code').fill('pool-smoke')
  await page.getByLabel('Name').fill('Smoke Pool')
  await page.getByLabel('Description').fill('Pool for browser smoke flow')
  await page.getByTestId('pool-catalog-save-pool').click()

  await expect.poll(() => state.pools.length).toBe(1)

  await page.getByTestId('pool-catalog-topology-add-node').click()
  const topologyCard = page.locator('.ant-card').filter({ hasText: 'Topology snapshot editor' })
  await topologyCard.locator('.ant-select').first().click()
  await page.locator('.ant-select-dropdown .ant-select-item-option-content', { hasText: 'Org One (730000000001)' }).first().click()
  await topologyCard.getByRole('switch').first().click()
  await page.getByTestId('pool-catalog-topology-save').click()

  await expect.poll(() => state.topologyUpsertCalls).toBe(1)

  await page.goto('/pools/runs', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Runs', exact: true })).toBeVisible()
  await page.getByTestId('pool-runs-create-submit').click()

  await expect.poll(() => state.createRunCalls).toBe(1)
  await expect(page.getByTestId('pool-runs-safe-confirm')).toBeEnabled()
  await page.getByTestId('pool-runs-safe-confirm').click()

  await expect.poll(() => state.confirmCalls).toBe(1)
  await expect(page.getByText('approved', { exact: false })).toBeVisible()
})
