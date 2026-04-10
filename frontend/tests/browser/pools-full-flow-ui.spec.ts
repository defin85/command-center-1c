import { expect, test, type Page, type Route } from '@playwright/test'

type AnyRecord = Record<string, unknown>

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>
  }
}

const TENANT_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
const NOW = '2026-01-01T00:00:00Z'

type PoolsUiMockState = {
  pools: AnyRecord[]
  graphByPoolId: Record<string, AnyRecord>
  runs: AnyRecord[]
  batches?: AnyRecord[]
  createRunCalls: number
  createBatchCalls?: number
  confirmCalls: number
  topologyUpsertCalls: number
  retryCalls: number
  lastRetryPayload: AnyRecord | null
  retryResponse?: AnyRecord
  lastTopologyPayload?: AnyRecord | null
  topologyTemplates?: AnyRecord[]
  schemaTemplates?: AnyRecord[]
  lastBatchPayload?: AnyRecord | null
  masterData?: {
    parties: AnyRecord[]
    items: AnyRecord[]
    contracts: AnyRecord[]
    taxProfiles: AnyRecord[]
    bindings: AnyRecord[]
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

function buildDefaultWorkflowBinding(poolId: string): AnyRecord {
  return {
    binding_id: `binding-${poolId.slice(0, 8)}`,
    pool_id: poolId,
    revision: 1,
    status: 'active',
    binding_profile_id: 'profile-top-down',
    binding_profile_revision_id: 'profile-top-down-r1',
    binding_profile_revision_number: 1,
    selector: {
      direction: 'top_down',
      mode: 'safe',
    },
    effective_from: '2026-01-01',
    effective_to: null,
    workflow: {
      workflow_definition_key: 'pool-top-down',
      workflow_name: 'Top Down Run',
    },
    decisions: [],
    parameters: {},
    role_mapping: {},
    resolved_profile: {
      binding_profile_id: 'profile-top-down',
      code: 'profile-top-down',
      name: 'Top Down Profile',
      status: 'active',
      binding_profile_revision_id: 'profile-top-down-r1',
      binding_profile_revision_number: 1,
      workflow: {
        workflow_definition_key: 'pool-top-down',
        workflow_name: 'Top Down Run',
      },
      decisions: [],
      parameters: {},
      role_mapping: {},
      topology_template_compatibility: {
        status: 'compatible',
        topology_aware_ready: true,
        covered_slot_keys: [],
        diagnostics: [],
      },
    },
  }
}

function buildDefaultSchemaTemplate(): AnyRecord {
  return {
    id: 'schema-template-json',
    tenant_id: TENANT_ID,
    code: 'json-template',
    name: 'JSON Template',
    format: 'json',
    is_public: true,
    is_active: true,
    schema: {},
    metadata: {},
    workflow_template_id: null,
    created_at: NOW,
    updated_at: NOW,
  }
}

function buildReceiptBatchMock({
  batchId,
  poolId,
  schemaTemplateId,
  runId,
  periodStart,
  periodEnd,
  startOrganizationId,
  sourceReference,
}: {
  batchId: string
  poolId: string
  schemaTemplateId: string | null
  runId: string | null
  periodStart: string
  periodEnd: string | null
  startOrganizationId: string | null
  sourceReference: string
}): AnyRecord {
  return {
    id: batchId,
    tenant_id: TENANT_ID,
    pool_id: poolId,
    batch_kind: 'receipt',
    source_type: 'schema_template_upload',
    schema_template_id: schemaTemplateId,
    start_organization_id: startOrganizationId,
    run_id: runId,
    workflow_execution_id: runId ? `94000000-0000-4000-8000-${runId.slice(-12)}` : null,
    operation_id: null,
    workflow_status: runId ? 'pending' : 'queued',
    period_start: periodStart,
    period_end: periodEnd,
    source_reference: sourceReference,
    raw_payload_ref: '',
    content_hash: `hash-${batchId.slice(-12)}`,
    source_metadata: {},
    normalization_summary: { rows: 1 },
    publication_summary: runId ? { linked_run_id: runId } : {},
    last_error_code: '',
    last_error: '',
    created_by_id: null,
    created_at: NOW,
    updated_at: NOW,
    settlement: {
      id: `settlement-${batchId.slice(-12)}`,
      tenant_id: TENANT_ID,
      batch_id: batchId,
      status: 'ingested',
      incoming_amount: '125.50',
      outgoing_amount: '0.00',
      open_balance: '125.50',
      summary: {},
      freshness_at: NOW,
      created_at: NOW,
      updated_at: NOW,
    },
  }
}

function buildLinkedReceiptRun({
  runId,
  batchId,
  poolId,
  startOrganizationId,
  schemaTemplateId,
}: {
  runId: string
  batchId: string
  poolId: string
  startOrganizationId: string | null
  schemaTemplateId: string | null
}): AnyRecord {
  return {
    id: runId,
    tenant_id: TENANT_ID,
    pool_id: poolId,
    schema_template_id: schemaTemplateId,
    mode: 'safe',
    direction: 'top_down',
    status: 'validated',
    status_reason: 'awaiting_approval',
    period_start: '2026-01-01',
    period_end: null,
    run_input: {
      batch_id: batchId,
      start_organization_id: startOrganizationId,
    },
    input_contract_version: 'run_input_v1',
    idempotency_key: `idem-${runId}`,
    workflow_execution_id: `94000000-0000-4000-8000-${runId.slice(-12)}`,
    workflow_status: 'pending',
    approval_state: 'awaiting_approval',
    publication_step_state: 'not_enqueued',
    terminal_reason: null,
    execution_backend: 'workflow_core',
    provenance: {
      workflow_run_id: `94000000-0000-4000-8000-${runId.slice(-12)}`,
      workflow_status: 'pending',
      execution_backend: 'workflow_core',
      retry_chain: [
        {
          workflow_run_id: `94000000-0000-4000-8000-${runId.slice(-12)}`,
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
}

async function selectAntdOption(page: Page, testId: string, optionText: string) {
  await page.getByTestId(testId).click()
  await page.locator('.ant-select-dropdown .ant-select-item-option-content', { hasText: optionText }).first().click()
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

async function setupApiMocks(page: Page, state: PoolsUiMockState) {
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
  const masterData = state.masterData || {
    parties: [] as AnyRecord[],
    items: [] as AnyRecord[],
    contracts: [] as AnyRecord[],
    taxProfiles: [] as AnyRecord[],
    bindings: [] as AnyRecord[],
  }
  const topologyTemplates = state.topologyTemplates || []
  const schemaTemplates = state.schemaTemplates || [buildDefaultSchemaTemplate()]

  const buildPoolId = () => `90000000-0000-4000-8000-${String(poolSequence++).padStart(12, '0')}`
  const buildRunId = () => `91000000-0000-4000-8000-${String(runSequence++).padStart(12, '0')}`
  const nextTopologyVersion = () => `v1:pool-topology-${topologyVersionSequence++}`

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/bootstrap/') {
      return fulfillJson(route, {
        me: { id: 1, username: 'smoke-user', is_staff: false },
        tenant_context: {
          active_tenant_id: TENANT_ID,
          tenants: [{ id: TENANT_ID, slug: 'default', name: 'Default', role: 'owner' }],
        },
        access: {
          user: { id: 1, username: 'smoke-user' },
          clusters: [],
          databases: [],
          operation_templates: [],
        },
        capabilities: {
          can_manage_rbac: false,
          can_manage_driver_catalogs: false,
          can_manage_runtime_controls: false,
        },
      })
    }
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
      if (!Array.isArray(pool.workflow_bindings) || pool.workflow_bindings.length === 0) {
        pool.workflow_bindings = [buildDefaultWorkflowBinding(String(pool.id))]
      }

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
    if (method === 'GET' && path === '/api/v2/pools/workflow-bindings/') {
      const poolId = String(url.searchParams.get('pool_id') || '')
      const pool = state.pools.find((item) => String(item.id) === poolId)
      const bindings = Array.isArray(pool?.workflow_bindings) ? pool.workflow_bindings : []
      return fulfillJson(route, {
        pool_id: poolId,
        workflow_bindings: bindings,
        collection_etag: 'sha256:browser-bindings',
        blocking_remediation: null,
      })
    }
    if (method === 'GET' && path === '/api/v2/pools/topology-templates/') {
      return fulfillJson(route, {
        topology_templates: topologyTemplates,
        count: topologyTemplates.length,
      })
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
      state.lastTopologyPayload = payload
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
      const topologyTemplateRevisionId = String(payload.topology_template_revision_id || '').trim()
      let nodesPayload = Array.isArray(payload.nodes) ? payload.nodes : []
      let edgesPayload = Array.isArray(payload.edges) ? payload.edges : []
      if (topologyTemplateRevisionId) {
        const templateRevision = topologyTemplates
          .flatMap((item) => (Array.isArray(item.revisions) ? item.revisions : []))
          .find(
            (item) => String(item?.topology_template_revision_id || '').trim() === topologyTemplateRevisionId
          )
        if (!templateRevision) {
          return fulfillJson(route, {
            type: 'about:blank',
            title: 'Topology Template Revision Not Found',
            status: 404,
            detail: 'Topology template revision not found in current tenant context.',
            code: 'TOPOLOGY_TEMPLATE_REVISION_NOT_FOUND',
          }, 404)
        }

        const slotAssignments = Array.isArray(payload.slot_assignments) ? payload.slot_assignments : []
        const organizationIdBySlotKey = new Map<string, string>(
          slotAssignments.map((item) => [
            String(item?.slot_key || '').trim(),
            String(item?.organization_id || '').trim(),
          ])
        )
        const edgeSelectorOverrides = Array.isArray(payload.edge_selector_overrides)
          ? payload.edge_selector_overrides
          : []
        const selectorOverrideByEdge = new Map<string, string>(
          edgeSelectorOverrides.map((item) => [
            `${String(item?.parent_slot_key || '').trim()}->${String(item?.child_slot_key || '').trim()}`,
            String(item?.document_policy_key || '').trim(),
          ])
        )

        nodesPayload = (Array.isArray(templateRevision.nodes) ? templateRevision.nodes : []).map((node: AnyRecord) => ({
          organization_id: organizationIdBySlotKey.get(String(node.slot_key || '').trim()) || '',
          is_root: Boolean(node.is_root),
          metadata: node.metadata && typeof node.metadata === 'object' ? node.metadata : {},
        }))
        edgesPayload = (Array.isArray(templateRevision.edges) ? templateRevision.edges : []).map((edge: AnyRecord) => {
          const parentSlotKey = String(edge.parent_slot_key || '').trim()
          const childSlotKey = String(edge.child_slot_key || '').trim()
          const metadata = edge.metadata && typeof edge.metadata === 'object'
            ? { ...(edge.metadata as AnyRecord) }
            : {}
          const selectorOverride = selectorOverrideByEdge.get(`${parentSlotKey}->${childSlotKey}`) || ''
          const documentPolicyKey = selectorOverride || String(edge.document_policy_key || '').trim()
          if (documentPolicyKey) {
            metadata.document_policy_key = documentPolicyKey
          } else {
            delete metadata.document_policy_key
          }
          return {
            parent_organization_id: organizationIdBySlotKey.get(parentSlotKey) || '',
            child_organization_id: organizationIdBySlotKey.get(childSlotKey) || '',
            weight: String(edge.weight || '1'),
            min_amount: edge.min_amount == null ? null : String(edge.min_amount),
            max_amount: edge.max_amount == null ? null : String(edge.max_amount),
            metadata,
          }
        })
      }
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
          metadata: node.metadata && typeof node.metadata === 'object' ? node.metadata : {},
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
          metadata: edge.metadata && typeof edge.metadata === 'object' ? edge.metadata : {},
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
      return fulfillJson(route, { templates: schemaTemplates, count: schemaTemplates.length })
    }
    if (method === 'GET' && path === '/api/v2/pools/batches/') {
      const poolId = String(url.searchParams.get('pool_id') || '').trim()
      const batchKind = String(url.searchParams.get('batch_kind') || '').trim()
      const batches = (state.batches || []).filter((item) => {
        const matchesPool = !poolId || String(item.pool_id || '') === poolId
        const matchesKind = !batchKind || String(item.batch_kind || '') === batchKind
        return matchesPool && matchesKind
      })
      return fulfillJson(route, { batches, count: batches.length })
    }
    if (method === 'POST' && path === '/api/v2/pools/batches/') {
      state.createBatchCalls = (state.createBatchCalls ?? 0) + 1
      const payload = request.postDataJSON() as AnyRecord
      state.lastBatchPayload = payload
      const poolId = String(payload.pool_id || '').trim()
      const batchKind = String(payload.batch_kind || 'receipt').trim()
      const periodStart = String(payload.period_start || '2026-01-01')
      const periodEnd = payload.period_end == null ? null : String(payload.period_end)
      const sourceReference = String(payload.source_reference || '').trim()
      const schemaTemplateId = payload.schema_template_id == null ? null : String(payload.schema_template_id)
      const startOrganizationId = payload.start_organization_id == null ? null : String(payload.start_organization_id)
      const batchId = `92000000-0000-4000-8000-${String((state.batches || []).length + 1).padStart(12, '0')}`
      const runId = batchKind === 'receipt'
        ? `91000000-0000-4000-8000-${String((state.runs || []).length + 1).padStart(12, '0')}`
        : null
      const batch = batchKind === 'receipt'
        ? buildReceiptBatchMock({
          batchId,
          poolId,
          schemaTemplateId,
          runId,
          periodStart,
          periodEnd,
          startOrganizationId,
          sourceReference,
        })
        : {
          id: batchId,
          tenant_id: TENANT_ID,
          pool_id: poolId,
          batch_kind: 'sale',
          source_type: 'schema_template_upload',
          schema_template_id: schemaTemplateId,
          start_organization_id: null,
          run_id: null,
          workflow_execution_id: null,
          operation_id: null,
          workflow_status: 'queued',
          period_start: periodStart,
          period_end: periodEnd,
          source_reference: sourceReference,
          raw_payload_ref: '',
          content_hash: `hash-${batchId.slice(-12)}`,
          source_metadata: {},
          normalization_summary: {},
          publication_summary: {},
          last_error_code: '',
          last_error: '',
          created_by_id: null,
          created_at: NOW,
          updated_at: NOW,
          settlement: {
            id: `settlement-${batchId.slice(-12)}`,
            tenant_id: TENANT_ID,
            batch_id: batchId,
            status: 'ingested',
            incoming_amount: '125.50',
            outgoing_amount: '0.00',
            open_balance: '125.50',
            summary: {},
            freshness_at: NOW,
            created_at: NOW,
            updated_at: NOW,
          },
        }

      state.batches = [batch, ...(state.batches || []).filter((item) => String(item.id) !== batchId)]
      if (runId) {
        const linkedRun = buildLinkedReceiptRun({
          runId,
          batchId,
          poolId,
          startOrganizationId,
          schemaTemplateId,
        })
        state.runs = [linkedRun, ...(state.runs || []).filter((item) => String(item.id) !== runId)]
      }
      return fulfillJson(route, {
        batch,
        settlement: batch.settlement,
        run: runId ? state.runs.find((item) => String(item.id) === runId) ?? null : null,
        created: true,
        sale_closing: batchKind === 'sale'
          ? {
            execution_id: `sale-close-${batchId.slice(-12)}`,
            operation_id: `sale-close-op-${batchId.slice(-12)}`,
            enqueue_success: true,
            enqueue_status: 'queued',
            enqueue_error: null,
            created_execution: true,
          }
          : null,
      }, 201)
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/parties/') {
      const role = String(url.searchParams.get('role') || '').trim()
      const query = String(url.searchParams.get('query') || '').trim().toLowerCase()
      const parties = masterData.parties.filter((item) => {
        if (role === 'organization' && !item.is_our_organization) {
          return false
        }
        if (role === 'counterparty' && !item.is_counterparty) {
          return false
        }
        if (!query) return true
        const haystack = [
          String(item.canonical_id || ''),
          String(item.name || ''),
          String(item.inn || ''),
        ].join(' ').toLowerCase()
        return haystack.includes(query)
      })
      return fulfillJson(route, {
        parties,
        meta: { limit: 100, offset: 0, total: parties.length },
      })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/items/') {
      const query = String(url.searchParams.get('query') || '').trim().toLowerCase()
      const sku = String(url.searchParams.get('sku') || '').trim().toLowerCase()
      const items = masterData.items.filter((item) => {
        const matchesQuery = !query || [
          String(item.canonical_id || ''),
          String(item.name || ''),
          String(item.sku || ''),
        ].join(' ').toLowerCase().includes(query)
        const matchesSku = !sku || String(item.sku || '').toLowerCase().includes(sku)
        return matchesQuery && matchesSku
      })
      return fulfillJson(route, {
        items,
        meta: { limit: 100, offset: 0, total: items.length },
      })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/contracts/') {
      const query = String(url.searchParams.get('query') || '').trim().toLowerCase()
      const ownerCanonicalId = String(url.searchParams.get('owner_counterparty_canonical_id') || '').trim()
      const contracts = masterData.contracts.filter((item) => {
        const matchesOwner = !ownerCanonicalId || String(item.owner_counterparty_canonical_id || '') === ownerCanonicalId
        if (!matchesOwner) return false
        if (!query) return true
        const haystack = [
          String(item.canonical_id || ''),
          String(item.name || ''),
          String(item.number || ''),
        ].join(' ').toLowerCase()
        return haystack.includes(query)
      })
      return fulfillJson(route, {
        contracts,
        meta: { limit: 100, offset: 0, total: contracts.length },
      })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/tax-profiles/') {
      const query = String(url.searchParams.get('query') || '').trim().toLowerCase()
      const vatCode = String(url.searchParams.get('vat_code') || '').trim().toLowerCase()
      const taxProfiles = masterData.taxProfiles.filter((item) => {
        const matchesVatCode = !vatCode || String(item.vat_code || '').toLowerCase().includes(vatCode)
        if (!matchesVatCode) return false
        if (!query) return true
        const haystack = [
          String(item.canonical_id || ''),
          String(item.vat_code || ''),
        ].join(' ').toLowerCase()
        return haystack.includes(query)
      })
      return fulfillJson(route, {
        tax_profiles: taxProfiles,
        meta: { limit: 100, offset: 0, total: taxProfiles.length },
      })
    }
    if (method === 'GET' && path === '/api/v2/pools/master-data/bindings/') {
      const canonicalId = String(url.searchParams.get('canonical_id') || '').trim().toLowerCase()
      const entityType = String(url.searchParams.get('entity_type') || '').trim()
      const bindings = masterData.bindings.filter((item) => {
        const matchesCanonical = !canonicalId || String(item.canonical_id || '').toLowerCase().includes(canonicalId)
        const matchesEntity = !entityType || String(item.entity_type || '') === entityType
        return matchesCanonical && matchesEntity
      })
      return fulfillJson(route, {
        bindings,
        meta: { limit: 200, offset: 0, total: bindings.length },
      })
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
      state.retryCalls += 1
      state.lastRetryPayload = (request.postDataJSON() as AnyRecord) || {}
      const retryResponse = state.retryResponse && typeof state.retryResponse === 'object'
        ? state.retryResponse
        : {
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
        }
      return fulfillJson(route, retryResponse)
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
    retryCalls: 0,
    lastRetryPayload: null as AnyRecord | null,
  }

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Catalog', exact: true })).toBeVisible()
  await expect(page.getByTestId('pool-catalog-add-pool')).toBeVisible()

  await page.getByRole('tab', { name: 'Pools' }).click()
  await page.getByTestId('pool-catalog-add-pool').click()
  const poolDrawer = page.getByTestId('pool-catalog-pool-drawer')
  await poolDrawer.getByLabel('Code').fill('pool-smoke')
  await poolDrawer.getByPlaceholder('Main intercompany pool').fill('Smoke Pool')
  await poolDrawer.getByPlaceholder('Optional').fill('Pool for browser smoke flow')
  await page.getByTestId('pool-catalog-save-pool').click()

  await expect.poll(() => state.pools.length).toBe(1)
  await expect(page.getByTestId('pool-catalog-context-pool')).toContainText('pool-smoke - Smoke Pool')

  await page.getByRole('tab', { name: 'Topology Editor' }).click()
  await expect(page.getByText('Topology snapshots by date')).toBeVisible()
  await page.getByTestId('pool-catalog-topology-authoring-mode').click()
  await page.locator('.ant-select-dropdown .ant-select-item-option-content', { hasText: 'Manual snapshot editor' }).first().click()
  await page.getByTestId('pool-catalog-topology-add-node').click()
  const topologyCard = page.locator('.ant-card').filter({ hasText: 'Topology snapshot editor' })
  await topologyCard.getByLabel('Organization').click()
  await page.locator('.ant-select-dropdown .ant-select-item-option-content', { hasText: 'Org One (730000000001)' }).first().click()
  await topologyCard.getByLabel('Root').click()
  await page.getByTestId('pool-catalog-topology-save').click()

  await expect.poll(() => state.topologyUpsertCalls).toBe(1)

  await page.goto('/pools/runs', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Runs', exact: true })).toBeVisible()
  await page.getByTestId('pool-runs-create-submit').click()

  await expect.poll(() => state.createRunCalls).toBe(1)
  await page.getByRole('tab', { name: 'Safe Actions' }).click()
  await expect(page.getByTestId('pool-runs-safe-confirm')).toBeEnabled()
  await page.getByTestId('pool-runs-safe-confirm').click()

  await expect.poll(() => state.confirmCalls).toBe(1)
  await expect(page.getByText('approved', { exact: false })).toBeVisible()
})

test('Pools browser-flow: canonical batch drawer opens linked run context without manual UUID entry', async ({ page }) => {
  const state = {
    pools: [] as AnyRecord[],
    graphByPoolId: {} as Record<string, AnyRecord>,
    runs: [] as AnyRecord[],
    batches: [] as AnyRecord[],
    createRunCalls: 0,
    createBatchCalls: 0,
    confirmCalls: 0,
    topologyUpsertCalls: 0,
    retryCalls: 0,
    lastRetryPayload: null as AnyRecord | null,
    lastBatchPayload: null as AnyRecord | null,
    topologyTemplates: [
      {
        topology_template_id: 'template-top-down',
        code: 'top-down-template',
        name: 'Top Down Template',
        description: 'Browser smoke topology template',
        status: 'active',
        metadata: {},
        latest_revision_number: 3,
        latest_revision: {
          topology_template_revision_id: 'template-revision-r3',
          topology_template_id: 'template-top-down',
          revision_number: 3,
          nodes: [
            { slot_key: 'root', label: 'Root', is_root: true, metadata: {} },
            { slot_key: 'organization_1', label: 'Organization 1', is_root: false, metadata: {} },
            { slot_key: 'organization_2', label: 'Organization 2', is_root: false, metadata: {} },
            { slot_key: 'organization_3', label: 'Organization 3', is_root: false, metadata: {} },
            { slot_key: 'organization_4', label: 'Organization 4', is_root: false, metadata: {} },
          ],
          edges: [
            {
              parent_slot_key: 'root',
              child_slot_key: 'organization_1',
              weight: '1',
              min_amount: null,
              max_amount: null,
              document_policy_key: 'sale',
              metadata: {},
            },
            {
              parent_slot_key: 'organization_1',
              child_slot_key: 'organization_2',
              weight: '1',
              min_amount: null,
              max_amount: null,
              document_policy_key: 'receipt_internal',
              metadata: {},
            },
            {
              parent_slot_key: 'organization_2',
              child_slot_key: 'organization_3',
              weight: '1',
              min_amount: null,
              max_amount: null,
              document_policy_key: 'receipt_leaf',
              metadata: {},
            },
            {
              parent_slot_key: 'organization_2',
              child_slot_key: 'organization_4',
              weight: '1',
              min_amount: null,
              max_amount: null,
              document_policy_key: 'receipt_leaf',
              metadata: {},
            },
          ],
          metadata: {},
          created_at: NOW,
        },
        revisions: [
          {
            topology_template_revision_id: 'template-revision-r3',
            topology_template_id: 'template-top-down',
            revision_number: 3,
            nodes: [
              { slot_key: 'root', label: 'Root', is_root: true, metadata: {} },
              { slot_key: 'organization_1', label: 'Organization 1', is_root: false, metadata: {} },
              { slot_key: 'organization_2', label: 'Organization 2', is_root: false, metadata: {} },
              { slot_key: 'organization_3', label: 'Organization 3', is_root: false, metadata: {} },
              { slot_key: 'organization_4', label: 'Organization 4', is_root: false, metadata: {} },
            ],
            edges: [
              {
                parent_slot_key: 'root',
                child_slot_key: 'organization_1',
                weight: '1',
                min_amount: null,
                max_amount: null,
                document_policy_key: 'sale',
                metadata: {},
              },
              {
                parent_slot_key: 'organization_1',
                child_slot_key: 'organization_2',
                weight: '1',
                min_amount: null,
                max_amount: null,
                document_policy_key: 'receipt_internal',
                metadata: {},
              },
              {
                parent_slot_key: 'organization_2',
                child_slot_key: 'organization_3',
                weight: '1',
                min_amount: null,
                max_amount: null,
                document_policy_key: 'receipt_leaf',
                metadata: {},
              },
              {
                parent_slot_key: 'organization_2',
                child_slot_key: 'organization_4',
                weight: '1',
                min_amount: null,
                max_amount: null,
                document_policy_key: 'receipt_leaf',
                metadata: {},
              },
            ],
            metadata: {},
            created_at: NOW,
          },
        ],
        created_at: NOW,
        updated_at: NOW,
      },
    ] as AnyRecord[],
    schemaTemplates: [
      {
        id: 'schema-template-json',
        tenant_id: TENANT_ID,
        code: 'json-template',
        name: 'JSON Template',
        format: 'json',
        is_public: true,
        is_active: true,
        schema: {},
        metadata: {},
        workflow_template_id: null,
        created_at: NOW,
        updated_at: NOW,
      },
    ] as AnyRecord[],
  }

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Catalog', exact: true })).toBeVisible()

  await page.getByRole('tab', { name: 'Pools' }).click()
  await page.getByTestId('pool-catalog-add-pool').click()
  const poolDrawer = page.getByTestId('pool-catalog-pool-drawer')
  await poolDrawer.getByLabel('Code').fill('pool-batch-smoke')
  await poolDrawer.getByPlaceholder('Main intercompany pool').fill('Batch Smoke Pool')
  await poolDrawer.getByPlaceholder('Optional').fill('Pool for canonical batch browser flow')
  await page.getByTestId('pool-catalog-save-pool').click()

  await expect.poll(() => state.pools.length).toBe(1)
  await expect(page.getByTestId('pool-catalog-context-pool')).toContainText('pool-batch-smoke - Batch Smoke Pool')

  await page.getByRole('tab', { name: 'Topology Editor' }).click()
  await expect(page.getByText('Topology snapshots by date')).toBeVisible()
  await page.getByTestId('pool-catalog-topology-authoring-mode').click()
  await page.locator('.ant-select-dropdown .ant-select-item-option-content', { hasText: 'Manual snapshot editor' }).first().click()
  await page.getByTestId('pool-catalog-topology-add-node').click()
  const topologyCard = page.locator('.ant-card').filter({ hasText: 'Topology snapshot editor' })
  await topologyCard.getByLabel('Organization').click()
  await page.locator('.ant-select-dropdown .ant-select-item-option-content', { hasText: 'Org One (730000000001)' }).first().click()
  await topologyCard.getByLabel('Root').click()
  await page.getByTestId('pool-catalog-topology-save').click()

  await expect.poll(() => state.topologyUpsertCalls).toBe(1)

  await page.goto('/pools/runs', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Runs', exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Create' }).click()
  await page.getByTestId('pool-runs-open-batch-intake').click()

  const batchDrawer = page.getByTestId('pool-runs-batch-intake-drawer')
  await expect(batchDrawer).toBeVisible()
  await selectAntdOption(page, 'pool-runs-batch-intake-schema-template', 'json-template - JSON Template')
  await selectAntdOption(page, 'pool-runs-batch-intake-binding', 'Top Down Run')
  await selectAntdOption(page, 'pool-runs-batch-intake-start-organization', 'Org One')
  await page.getByTestId('pool-runs-batch-intake-source-reference').fill('receipt-apr')
  await page.getByTestId('pool-runs-batch-intake-submit').click()

  await expect.poll(() => state.createBatchCalls).toBe(1)
  await expect.poll(() => state.batches.length).toBe(1)
  await expect.poll(() => state.runs.length).toBe(1)
  const createdRunId = String(state.runs[0]?.id || '')
  await expect.poll(() => page.url()).toContain('stage=inspect')
  await expect.poll(() => page.url()).toContain(`run=${createdRunId}`)
  await expect(page.getByText('Lifecycle stage: Inspect')).toBeVisible()
  await expect(page.getByText('Selected run:')).toContainText(createdRunId.slice(0, 8))
  await expect(batchDrawer).toBeHidden()
})

test('Pools browser-flow: canonical sale batch stays on runs workspace and omits receipt-only linkage fields', async ({ page }) => {
  const poolId = '90000000-0000-4000-8000-000000000444'
  const state: PoolsUiMockState = {
    pools: [
      {
        id: poolId,
        code: 'pool-sale-batch',
        name: 'Sale Batch Pool',
        description: 'Pool for canonical sale batch flow',
        is_active: true,
        metadata: {},
        workflow_bindings: [buildDefaultWorkflowBinding(poolId)],
        updated_at: NOW,
      },
    ],
    graphByPoolId: {
      [poolId]: {
        pool_id: poolId,
        date: '2026-01-01',
        version: 'v1:pool-topology-sale-batch',
        nodes: [],
        edges: [],
      },
    },
    runs: [],
    batches: [],
    createRunCalls: 0,
    createBatchCalls: 0,
    confirmCalls: 0,
    topologyUpsertCalls: 0,
    retryCalls: 0,
    lastRetryPayload: null,
    lastBatchPayload: null,
  }

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto(`/pools/runs?pool=${poolId}&stage=create&detail=1`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Runs', exact: true })).toBeVisible()
  await page.getByTestId('pool-runs-open-batch-intake').click()

  const batchDrawer = page.getByTestId('pool-runs-batch-intake-drawer')
  await expect(batchDrawer).toBeVisible()
  await batchDrawer.locator('.ant-radio-button-wrapper', { hasText: 'sale' }).click()
  await expect(batchDrawer.getByTestId('pool-runs-batch-intake-binding')).toHaveCount(0)
  await expect(batchDrawer.getByTestId('pool-runs-batch-intake-start-organization')).toHaveCount(0)
  await selectAntdOption(page, 'pool-runs-batch-intake-schema-template', 'json-template - JSON Template')
  await page.getByTestId('pool-runs-batch-intake-source-reference').fill('sale-apr')
  await page.getByTestId('pool-runs-batch-intake-submit').click()

  await expect.poll(() => state.createBatchCalls).toBe(1)
  await expect.poll(() => state.batches?.length ?? 0).toBe(1)
  await expect.poll(() => state.runs.length).toBe(0)
  await expect.poll(() => String(state.lastBatchPayload?.batch_kind || '')).toBe('sale')
  await expect.poll(() => 'pool_workflow_binding_id' in (state.lastBatchPayload || {})).toBe(false)
  await expect.poll(() => 'start_organization_id' in (state.lastBatchPayload || {})).toBe(false)
  await expect(page.getByText('Sale batch accepted and closing workflow queued')).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`\\/pools\\/runs\\?pool=${poolId}$`))
  await expect(batchDrawer).toBeHidden()
})

test('Pools browser-flow: fresh pool defaults to template topology authoring path', async ({ page }) => {
  const state = {
    pools: [] as AnyRecord[],
    graphByPoolId: {} as Record<string, AnyRecord>,
    runs: [] as AnyRecord[],
    createRunCalls: 0,
    confirmCalls: 0,
    topologyUpsertCalls: 0,
    retryCalls: 0,
    lastRetryPayload: null as AnyRecord | null,
    lastTopologyPayload: null as AnyRecord | null,
    topologyTemplates: [
      {
        topology_template_id: 'template-top-down',
        code: 'top-down-template',
        name: 'Top Down Template',
        description: 'Browser smoke topology template',
        status: 'active',
        metadata: {},
        latest_revision_number: 3,
        latest_revision: {
          topology_template_revision_id: 'template-revision-r3',
          topology_template_id: 'template-top-down',
          revision_number: 3,
          nodes: [
            { slot_key: 'root', label: 'Root', is_root: true, metadata: {} },
            { slot_key: 'organization_1', label: 'Organization 1', is_root: false, metadata: {} },
            { slot_key: 'organization_2', label: 'Organization 2', is_root: false, metadata: {} },
            { slot_key: 'organization_3', label: 'Organization 3', is_root: false, metadata: {} },
            { slot_key: 'organization_4', label: 'Organization 4', is_root: false, metadata: {} },
          ],
          edges: [
            {
              parent_slot_key: 'root',
              child_slot_key: 'organization_1',
              weight: '1',
              min_amount: null,
              max_amount: null,
              document_policy_key: 'sale',
              metadata: {},
            },
            {
              parent_slot_key: 'organization_1',
              child_slot_key: 'organization_2',
              weight: '1',
              min_amount: null,
              max_amount: null,
              document_policy_key: 'receipt_internal',
              metadata: {},
            },
            {
              parent_slot_key: 'organization_2',
              child_slot_key: 'organization_3',
              weight: '1',
              min_amount: null,
              max_amount: null,
              document_policy_key: 'receipt_leaf',
              metadata: {},
            },
            {
              parent_slot_key: 'organization_2',
              child_slot_key: 'organization_4',
              weight: '1',
              min_amount: null,
              max_amount: null,
              document_policy_key: 'receipt_leaf',
              metadata: {},
            },
          ],
          metadata: {},
          created_at: NOW,
        },
        revisions: [
          {
            topology_template_revision_id: 'template-revision-r3',
            topology_template_id: 'template-top-down',
            revision_number: 3,
            nodes: [
              { slot_key: 'root', label: 'Root', is_root: true, metadata: {} },
              { slot_key: 'organization_1', label: 'Organization 1', is_root: false, metadata: {} },
              { slot_key: 'organization_2', label: 'Organization 2', is_root: false, metadata: {} },
              { slot_key: 'organization_3', label: 'Organization 3', is_root: false, metadata: {} },
              { slot_key: 'organization_4', label: 'Organization 4', is_root: false, metadata: {} },
            ],
            edges: [
              {
                parent_slot_key: 'root',
                child_slot_key: 'organization_1',
                weight: '1',
                min_amount: null,
                max_amount: null,
                document_policy_key: 'sale',
                metadata: {},
              },
              {
                parent_slot_key: 'organization_1',
                child_slot_key: 'organization_2',
                weight: '1',
                min_amount: null,
                max_amount: null,
                document_policy_key: 'receipt_internal',
                metadata: {},
              },
              {
                parent_slot_key: 'organization_2',
                child_slot_key: 'organization_3',
                weight: '1',
                min_amount: null,
                max_amount: null,
                document_policy_key: 'receipt_leaf',
                metadata: {},
              },
              {
                parent_slot_key: 'organization_2',
                child_slot_key: 'organization_4',
                weight: '1',
                min_amount: null,
                max_amount: null,
                document_policy_key: 'receipt_leaf',
                metadata: {},
              },
            ],
            metadata: {},
            created_at: NOW,
          },
        ],
        created_at: NOW,
        updated_at: NOW,
      },
    ] as AnyRecord[],
  }

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Catalog', exact: true })).toBeVisible()

  await page.getByRole('tab', { name: 'Pools' }).click()
  await page.getByTestId('pool-catalog-add-pool').click()
  const poolDrawer = page.getByTestId('pool-catalog-pool-drawer')
  await poolDrawer.getByLabel('Code').fill('pool-template')
  await poolDrawer.getByPlaceholder('Main intercompany pool').fill('Template Pool')
  await poolDrawer.getByPlaceholder('Optional').fill('Pool for template-based smoke flow')
  await page.getByTestId('pool-catalog-save-pool').click()

  await expect.poll(() => state.pools.length).toBe(1)
  await expect(page.getByTestId('pool-catalog-context-pool')).toContainText('pool-template - Template Pool')

  await page.getByRole('tab', { name: 'Topology Editor' }).click()
  await expect(page.getByText('Topology snapshots by date')).toBeVisible()
  await expect(page.getByTestId('pool-catalog-topology-authoring-mode')).toContainText('Template-based instantiation')
  await expect(page.getByText('Template-based path is the preferred reuse flow')).toBeVisible()
  await expect(page.getByTestId('pool-catalog-topology-template-revision')).toBeVisible()
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Pools retry smoke: invoice_mode=required chain keeps linkage and skips already-successful targets', async ({ page }) => {
  const run = {
    id: '91000000-0000-4000-8000-000000000111',
    tenant_id: TENANT_ID,
    pool_id: '90000000-0000-4000-8000-000000000111',
    schema_template_id: null,
    mode: 'safe',
    direction: 'top_down',
    status: 'failed',
    status_reason: null,
    period_start: '2026-01-01',
    period_end: null,
    run_input: { starting_amount: '100.00' },
    input_contract_version: 'run_input_v1',
    idempotency_key: 'idem-retry-smoke',
    workflow_execution_id: '94000000-0000-4000-8000-000000000111',
    workflow_status: 'failed',
    approval_state: 'approved',
    publication_step_state: 'completed',
    terminal_reason: null,
    execution_backend: 'workflow_core',
    provenance: {
      workflow_run_id: '94000000-0000-4000-8000-000000000111',
      workflow_status: 'failed',
      execution_backend: 'workflow_core',
      retry_chain: [
        {
          workflow_run_id: '94000000-0000-4000-8000-000000000111',
          parent_workflow_run_id: null,
          attempt_number: 1,
          attempt_kind: 'initial',
          status: 'failed',
        },
      ],
    },
    workflow_template_name: 'pool-template-v1',
    seed: null,
    validation_summary: { rows: 2 },
    publication_summary: { total_targets: 2 },
    diagnostics: [],
    last_error: 'publication failed',
    created_at: NOW,
    updated_at: NOW,
    validated_at: NOW,
    publication_confirmed_at: NOW,
    publishing_started_at: NOW,
    completed_at: NOW,
  }

  const state = {
    pools: [
      {
        id: '90000000-0000-4000-8000-000000000111',
        code: 'pool-retry',
        name: 'Retry Pool',
        description: 'Pool for retry smoke',
        is_active: true,
        metadata: {},
        updated_at: NOW,
      },
    ] as AnyRecord[],
    graphByPoolId: {
      '90000000-0000-4000-8000-000000000111': {
        pool_id: '90000000-0000-4000-8000-000000000111',
        date: '2026-01-01',
        version: 'v1:pool-topology-retry',
        nodes: [],
        edges: [],
      },
    } as Record<string, AnyRecord>,
    runs: [run] as AnyRecord[],
    createRunCalls: 0,
    confirmCalls: 0,
    topologyUpsertCalls: 0,
    retryCalls: 0,
    lastRetryPayload: null as AnyRecord | null,
    retryResponse: {
      accepted: true,
      workflow_execution_id: '95000000-0000-4000-8000-000000000222',
      operation_id: null,
      retry_target_summary: {
        requested_targets: 2,
        requested_documents: 3,
        failed_targets: 2,
        enqueued_targets: 1,
        skipped_successful_targets: 1,
      },
    } as AnyRecord,
  }

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/runs', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Runs', exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Retry Failed' }).click()

  const retryDocumentsPayload = JSON.stringify(
    {
      '20202020-2020-2020-2020-202020202020': [
        {
          document_id: 'sale-001',
          document_role: 'sale',
          invoice_mode: 'required',
        },
        {
          document_id: 'invoice-001',
          document_role: 'invoice',
          links: [{ link_kind: 'follows', source_document_id: 'sale-001' }],
        },
      ],
      '30303030-3030-3030-3030-303030303030': [
        {
          document_id: 'sale-success',
          document_role: 'sale',
        },
      ],
    },
    null,
    2
  )

  await page.getByLabel('documents_by_database JSON').fill(retryDocumentsPayload)
  await page.getByRole('button', { name: 'Retry Failed' }).click()

  await expect.poll(() => state.retryCalls).toBe(1)
  const sentPayload = state.lastRetryPayload || {}
  const sentDocuments = sentPayload.documents_by_database as Record<string, Array<Record<string, unknown>>>
  expect(Array.isArray(sentDocuments?.['20202020-2020-2020-2020-202020202020'])).toBeTruthy()
  expect(sentDocuments['20202020-2020-2020-2020-202020202020']).toHaveLength(2)
  expect(
    sentDocuments['20202020-2020-2020-2020-202020202020']?.[1]?.links
  ).toEqual([{ link_kind: 'follows', source_document_id: 'sale-001' }])

  await expect(page.getByText('Retry accepted: 1/2 failed targets enqueued')).toBeVisible()
})

test('Pools browser-flow: token authoring -> failed gate diagnostics -> remediation-ready workspace', async ({ page }) => {
  const poolId = '90000000-0000-4000-8000-000000000333'
  const run = {
    id: '91000000-0000-4000-8000-000000000333',
    tenant_id: TENANT_ID,
    pool_id: poolId,
    schema_template_id: null,
    mode: 'safe',
    direction: 'top_down',
    status: 'failed',
    status_reason: null,
    period_start: '2026-01-01',
    period_end: null,
    run_input: { starting_amount: '100.00' },
    input_contract_version: 'run_input_v1',
    idempotency_key: 'idem-master-data-flow',
    workflow_execution_id: '94000000-0000-4000-8000-000000000333',
    workflow_status: 'failed',
    approval_state: 'approved',
    publication_step_state: 'completed',
    terminal_reason: null,
    execution_backend: 'workflow_core',
    provenance: {
      workflow_run_id: '94000000-0000-4000-8000-000000000333',
      workflow_status: 'failed',
      execution_backend: 'workflow_core',
      retry_chain: [
        {
          workflow_run_id: '94000000-0000-4000-8000-000000000333',
          parent_workflow_run_id: null,
          attempt_number: 1,
          attempt_kind: 'initial',
          status: 'failed',
        },
      ],
    },
    workflow_template_name: 'pool-template-v1',
    seed: null,
    validation_summary: { rows: 2 },
    publication_summary: { total_targets: 1 },
    diagnostics: [],
    master_data_gate: {
      status: 'failed',
      mode: 'resolve_upsert',
      targets_count: 1,
      bindings_count: 0,
      error_code: 'MASTER_DATA_ENTITY_NOT_FOUND',
      detail: 'Canonical entity not found for token.',
      diagnostic: {
        entity_type: 'item',
        canonical_id: 'item-missing',
        target_database_id: '20202020-2020-2020-2020-202020202020',
      },
    },
    last_error: 'master data gate failed',
    created_at: NOW,
    updated_at: NOW,
    validated_at: NOW,
    publication_confirmed_at: NOW,
    publishing_started_at: NOW,
    completed_at: NOW,
  }

  const state: PoolsUiMockState = {
    pools: [
      {
        id: poolId,
        code: 'pool-md',
        name: 'Pool Master Data Flow',
        description: 'Pool for master-data browser flow',
        is_active: true,
        metadata: {},
        workflow_bindings: [
          {
            binding_id: 'binding-purchase',
            pool_id: poolId,
            revision: 1,
            status: 'active',
            workflow: {
              workflow_definition_key: 'services-publication',
              workflow_revision_id: 'workflow-revision-1',
              workflow_revision: 1,
              workflow_name: 'services_publication',
            },
            decisions: [
              {
                decision_table_id: 'decision-purchase',
                decision_key: 'document_policy',
                slot_key: 'purchase',
                decision_revision: 3,
              },
            ],
            selector: {
              direction: 'top_down',
              mode: 'safe',
              tags: [],
            },
            effective_from: '2026-01-01',
            effective_to: null,
          },
        ],
        updated_at: NOW,
      },
    ],
    graphByPoolId: {
      [poolId]: {
        pool_id: poolId,
        date: '2026-01-01',
        version: 'v1:pool-topology-master-data',
        nodes: [
          {
            node_version_id: 'node-v1',
            organization_id: '11111111-1111-1111-1111-111111111111',
            inn: '730000000001',
            name: 'Org One',
            is_root: true,
            metadata: {},
          },
          {
            node_version_id: 'node-v2',
            organization_id: '22222222-2222-2222-2222-222222222222',
            inn: '730000000002',
            name: 'Org Two',
            is_root: false,
            metadata: {},
          },
        ],
        edges: [
          {
            edge_version_id: 'edge-v1',
            parent_node_version_id: 'node-v1',
            child_node_version_id: 'node-v2',
            weight: '1',
            min_amount: null,
            max_amount: null,
            metadata: {
              document_policy_key: 'sale',
            },
          },
        ],
      },
    },
    runs: [run],
    createRunCalls: 0,
    confirmCalls: 0,
    topologyUpsertCalls: 0,
    retryCalls: 0,
    lastRetryPayload: null,
    lastTopologyPayload: null,
    masterData: {
      parties: [
        {
          id: 'party-001-id',
          tenant_id: TENANT_ID,
          canonical_id: 'party-001',
          name: 'Party One',
          full_name: 'Party One LLC',
          inn: '730000000001',
          kpp: '',
          is_our_organization: true,
          is_counterparty: true,
          metadata: {},
          created_at: NOW,
          updated_at: NOW,
        },
      ],
      items: [
        {
          id: 'item-001-id',
          tenant_id: TENANT_ID,
          canonical_id: 'item-001',
          name: 'Item One',
          sku: 'SKU-001',
          unit: 'pcs',
          metadata: {},
          created_at: NOW,
          updated_at: NOW,
        },
      ],
      contracts: [],
      taxProfiles: [],
      bindings: [],
    },
  }

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Catalog', exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Topology Editor' }).click()
  await expect(page.getByTestId('pool-catalog-topology-edge-slot-0')).toBeVisible()
  await page.getByTestId('pool-catalog-topology-edge-slot-0').fill('purchase')
  await page.getByTestId('pool-catalog-topology-save').click()

  await expect.poll(() => state.topologyUpsertCalls).toBe(1)
  await expect.poll(() => {
    const payload = state.lastTopologyPayload
    const edges = Array.isArray(payload?.edges) ? payload.edges as AnyRecord[] : []
    const edge = edges[0] || {}
    const metadata = edge.metadata && typeof edge.metadata === 'object' ? edge.metadata as AnyRecord : {}
    return String(metadata.document_policy_key || '')
  }).toBe('purchase')

  await page.goto('/pools/runs', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Runs', exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Inspect' }).click()
  await expect(page.getByText('Master Data Gate')).toBeVisible()
  await expect(page.getByText('MASTER_DATA_ENTITY_NOT_FOUND')).toBeVisible()
  await expect(
    page.getByText('Создайте/исправьте canonical сущность в /pools/master-data и повторите run.')
  ).toBeVisible()
  await expect(
    page.getByText(
      /entity_type=item canonical_id=item-missing target_database_id=20202020-2020-2020-2020-202020202020/
    )
  ).toBeVisible()

  await page.goto('/pools/master-data', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Pool Master Data', exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Item' }).click()
  await expect(page.getByRole('button', { name: 'Add Item' })).toBeVisible()
  await expect(page.getByText('Item One')).toBeVisible()
})
