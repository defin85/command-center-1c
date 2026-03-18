import { expect, test, type Page, type Route } from '@playwright/test'

type AnyRecord = Record<string, unknown>

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>
  }
}

const TENANT_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
const POOL_ID = '90000000-0000-4000-8000-000000000777'
const BINDING_ID = 'binding-top-down'
const NOW = '2026-03-10T12:00:00Z'

const BASE_METADATA_CONTEXT = {
  database_id: '10101010-1010-1010-1010-101010101010',
  snapshot_id: 'snapshot-shared-services',
  source: 'db',
  fetched_at: NOW,
  catalog_version: 'v1:shared-services',
  config_name: 'shared-profile',
  config_version: '8.3.24',
  config_generation_id: 'generation-shared-services',
  extensions_fingerprint: '',
  metadata_hash: 'a'.repeat(64),
  observed_metadata_hash: 'a'.repeat(64),
  publication_drift: false,
  resolution_mode: 'shared_scope',
  is_shared_snapshot: true,
  provenance_database_id: '20202020-2020-2020-2020-202020202020',
  provenance_confirmed_at: NOW,
  documents: [],
}

const BASE_DECISION = {
  id: 'decision-version-2',
  decision_table_id: 'services-publication-policy',
  decision_key: 'document_policy',
  decision_revision: 2,
  name: 'Services publication policy',
  description: 'Publishes service documents',
  inputs: [],
  outputs: [],
  rules: [
    {
      rule_id: 'default',
      priority: 0,
      conditions: {},
      outputs: {
        document_policy: {
          version: 'document_policy.v1',
          chains: [
            {
              chain_id: 'sale_chain',
              documents: [
                {
                  document_id: 'sale',
                  entity_name: 'Document_Sales',
                  document_role: 'sale',
                  field_mapping: {
                    Amount: 'allocation.amount',
                  },
                  table_parts_mapping: {},
                  link_rules: {},
                },
              ],
            },
          ],
        },
      },
    },
  ],
  hit_policy: 'first_match',
  validation_mode: 'fail_closed',
  is_active: true,
  parent_version: 'decision-version-1',
  metadata_context: {
    snapshot_id: 'snapshot-shared-services',
    config_name: 'shared-profile',
    config_version: '8.3.24',
    config_generation_id: 'generation-shared-services',
    extensions_fingerprint: '',
    metadata_hash: 'a'.repeat(64),
    observed_metadata_hash: 'a'.repeat(64),
    publication_drift: false,
    resolution_mode: 'shared_scope',
    is_shared_snapshot: true,
    provenance_database_id: '20202020-2020-2020-2020-202020202020',
    provenance_confirmed_at: NOW,
  },
  metadata_compatibility: {
    status: 'compatible',
    reason: null,
    is_compatible: true,
  },
  created_at: NOW,
  updated_at: NOW,
}

const PREVIOUS_RELEASE_DECISION = {
  ...BASE_DECISION,
  id: 'decision-version-previous-release',
  decision_revision: 7,
  name: 'Previous release policy',
  metadata_context: {
    ...BASE_DECISION.metadata_context,
    config_version: '8.3.23',
    config_generation_id: 'generation-shared-services-prev',
  },
  metadata_compatibility: {
    status: 'incompatible',
    reason: 'configuration_scope_mismatch',
    is_compatible: false,
  },
}

type AcceptanceState = {
  databases: AnyRecord[]
  decisions: AnyRecord[]
  decisionListQueries: string[]
  decisionWrites: AnyRecord[]
  metadataContext: AnyRecord
  templateExposures: AnyRecord[]
  poolRuntimeRegistry: AnyRecord
  organizations: AnyRecord[]
  pools: AnyRecord[]
  graphsByPoolId: Record<string, AnyRecord>
  topologySnapshotsByPoolId: Record<string, AnyRecord>
  workflowBindingsByPoolId: Record<string, AnyRecord[]>
  migrationCalls: number
  lastMigrationPayload: AnyRecord | null
  bindingUpsertCalls: number
  bindingConflictOnce: boolean
  lastBindingPayload: AnyRecord | null
  previewCalls: number
  lastPreviewPayload: AnyRecord | null
  createRunCalls: number
  lastCreateRunPayload: AnyRecord | null
  runs: AnyRecord[]
  runReportsByRunId: Record<string, AnyRecord>
}

const deepClone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T

const buildPublishedRun = () => ({
  id: 'run-published-1',
  tenant_id: TENANT_ID,
  pool_id: POOL_ID,
  schema_template_id: null,
  mode: 'safe',
  direction: 'top_down',
  status: 'published',
  status_reason: null,
  period_start: '2026-03-01',
  period_end: null,
  run_input: { starting_amount: '150.00' },
  input_contract_version: 'run_input_v1',
  idempotency_key: 'idem-published-1',
  workflow_execution_id: 'workflow-execution-1',
  workflow_status: 'completed',
  root_operation_id: 'root-operation-1',
  execution_consumer: 'pools',
  lane: 'workflows',
  approval_state: 'approved',
  publication_step_state: 'completed',
  readiness_blockers: [],
  readiness_checklist: {
    status: 'ready',
    checks: [
      {
        code: 'master_data_coverage',
        status: 'ready',
        blocker_codes: [],
        blockers: [],
      },
      {
        code: 'organization_party_bindings',
        status: 'ready',
        blocker_codes: [],
        blockers: [],
      },
      {
        code: 'policy_completeness',
        status: 'ready',
        blocker_codes: [],
        blockers: [],
      },
      {
        code: 'odata_verify_readiness',
        status: 'ready',
        blocker_codes: [],
        blockers: [],
      },
    ],
  },
  verification_status: 'passed',
  verification_summary: {
    checked_targets: 1,
    verified_documents: 2,
    mismatches_count: 0,
    mismatches: [],
  },
  terminal_reason: null,
  execution_backend: 'workflow_core',
  provenance: {
    workflow_run_id: 'workflow-run-1',
    workflow_status: 'completed',
    execution_backend: 'workflow_core',
    root_operation_id: 'root-operation-1',
    execution_consumer: 'pools',
    lane: 'workflows',
    retry_chain: [
      {
        workflow_run_id: 'workflow-run-1',
        parent_workflow_run_id: null,
        attempt_number: 1,
        attempt_kind: 'initial',
        status: 'completed',
      },
    ],
  },
  workflow_binding: {
    binding_id: BINDING_ID,
    pool_id: POOL_ID,
    workflow: {
      workflow_definition_key: 'services-publication',
      workflow_revision_id: 'workflow-revision-7',
      workflow_revision: 7,
      workflow_name: 'services_publication',
    },
    selector: {
      direction: 'top_down',
      mode: 'safe',
      tags: [],
    },
    decisions: [
      {
        decision_table_id: 'services-publication-policy',
        decision_key: 'document_policy',
        decision_revision: 2,
      },
    ],
    effective_from: '2026-03-01',
    effective_to: null,
    status: 'active',
    revision: 3,
  },
  runtime_projection: {
    version: 'pool_runtime_projection.v1',
    run_id: 'run-published-1',
    pool_id: POOL_ID,
    direction: 'top_down',
    mode: 'safe',
    workflow_definition: {
      plan_key: 'plan-services-v7',
      template_version: 'workflow-template:7',
      workflow_template_name: 'compiled-services-publication',
      workflow_type: 'sequential',
    },
    workflow_binding: {
      binding_mode: 'pool_workflow_binding',
      binding_id: BINDING_ID,
      pool_id: POOL_ID,
      workflow_definition_key: 'services-publication',
      workflow_revision_id: 'workflow-revision-7',
      workflow_revision: 7,
      workflow_name: 'services_publication',
      decision_refs: [
        {
          decision_table_id: 'services-publication-policy',
          decision_key: 'document_policy',
          decision_revision: 2,
        },
      ],
      selector: {
        direction: 'top_down',
        mode: 'safe',
        tags: [],
      },
      status: 'active',
    },
    document_policy_projection: {
      source_mode: 'decision_tables',
      policy_refs: [{ policy_id: 'services-publication-policy:r2' }],
      policy_refs_count: 1,
      targets_count: 1,
    },
    artifacts: {
      document_plan_artifact_version: 'document-plan:v7',
      topology_version_ref: 'topology:v7',
      distribution_artifact_ref: { id: 'distribution:v7' },
    },
    compile_summary: {
      steps_count: 5,
      atomic_publication_steps_count: 3,
      compiled_targets_count: 1,
    },
  },
  workflow_template_name: 'pool-template-v1',
  seed: null,
  validation_summary: { rows: 1 },
  publication_summary: { total_targets: 1 },
  diagnostics: [{ step: 'distribution_calculation', status: 'ok' }],
  last_error: '',
  created_at: NOW,
  updated_at: NOW,
  validated_at: NOW,
  publication_confirmed_at: NOW,
  publishing_started_at: NOW,
  completed_at: NOW,
})

function createAcceptanceState(): AcceptanceState {
  const publishedRun = buildPublishedRun()
  return {
    databases: [
      {
        id: '10101010-1010-1010-1010-101010101010',
        name: 'Target DB',
        base_name: 'shared-profile',
        version: '8.3.24',
      },
      {
        id: '20202020-2020-2020-2020-202020202020',
        name: 'Shared provenance DB',
        base_name: 'shared-profile',
        version: '8.3.24',
      },
    ],
    decisions: [deepClone(BASE_DECISION), deepClone(PREVIOUS_RELEASE_DECISION)],
    decisionListQueries: [],
    decisionWrites: [],
    metadataContext: deepClone(BASE_METADATA_CONTEXT),
    templateExposures: [
      {
        id: 'exposure-workflow-template',
        definition_id: 'definition-workflow-template',
        surface: 'template',
        alias: 'workflow-template-compat',
        name: 'Workflow Compatibility Template',
        description: 'Compatibility wrapper for a workflow executor',
        is_active: true,
        capability: 'workflow.compatibility',
        status: 'published',
        operation_type: 'workflow',
        target_entity: 'workflow',
        template_data: {
          workflow_id: 'workflow-template-v3',
        },
        executor_kind: 'workflow',
        executor_command_id: null,
        template_exposure_id: 'template-exposure-1',
        template_exposure_revision: 4,
        created_at: NOW,
        updated_at: NOW,
      },
    ],
    poolRuntimeRegistry: {
      contract_version: 'pool_runtime.v1',
      entries: [],
      count: 0,
    },
    organizations: [
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
    ],
    pools: [
      {
        id: POOL_ID,
        code: 'pool-hardening',
        name: 'Workflow Hardening Pool',
        description: 'Pool for workflow hardening browser acceptance',
        is_active: true,
        metadata: {},
        updated_at: NOW,
      },
    ],
    graphsByPoolId: {
      [POOL_ID]: {
        pool_id: POOL_ID,
        date: '2026-03-01',
        version: 'v1:topology-hardening',
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
              document_policy: {
                version: 'document_policy.v1',
                chains: [
                  {
                    chain_id: 'sale_chain',
                    documents: [
                      {
                        document_id: 'sale',
                        entity_name: 'Document_Sales',
                        document_role: 'sale',
                        field_mapping: {
                          Amount: 'allocation.amount',
                        },
                        table_parts_mapping: {},
                        link_rules: {},
                      },
                    ],
                  },
                ],
              },
              legacy_source: 'edge.metadata.document_policy',
            },
          },
        ],
      },
    },
    topologySnapshotsByPoolId: {
      [POOL_ID]: {
        pool_id: POOL_ID,
        count: 1,
        snapshots: [
          {
            effective_from: '2026-03-01',
            effective_to: null,
            nodes_count: 2,
            edges_count: 1,
          },
        ],
      },
    },
    workflowBindingsByPoolId: {
      [POOL_ID]: [
        {
          binding_id: BINDING_ID,
          pool_id: POOL_ID,
          workflow: {
            workflow_definition_key: 'services-publication',
            workflow_revision_id: 'workflow-revision-7',
            workflow_revision: 7,
            workflow_name: 'services_publication',
          },
          selector: {
            direction: 'top_down',
            mode: 'safe',
            tags: [],
          },
          decisions: [
            {
              decision_table_id: 'services-publication-policy',
              decision_key: 'document_policy',
              decision_revision: 1,
            },
          ],
          effective_from: '2026-03-01',
          effective_to: null,
          status: 'active',
          revision: 3,
        },
      ],
    },
    migrationCalls: 0,
    lastMigrationPayload: null,
    bindingUpsertCalls: 0,
    bindingConflictOnce: false,
    lastBindingPayload: null,
    previewCalls: 0,
    lastPreviewPayload: null,
    createRunCalls: 0,
    lastCreateRunPayload: null,
    runs: [publishedRun],
    runReportsByRunId: {
      [String(publishedRun.id)]: {
        run: publishedRun,
        publication_attempts: [
          {
            id: 'publication-attempt-1',
            run_id: publishedRun.id,
            target_database_id: '20202020-2020-2020-2020-202020202020',
            attempt_number: 1,
            attempt_timestamp: NOW,
            status: 'success',
            entity_name: 'Document_Sales',
            documents_count: 2,
            publication_identity_strategy: 'guid',
            external_document_identity: 'ref-1',
            posted: true,
            domain_error_code: '',
            domain_error_message: '',
          },
        ],
        validation_summary: publishedRun.validation_summary,
        publication_summary: publishedRun.publication_summary,
        diagnostics: publishedRun.diagnostics,
        attempts_by_status: { success: 1 },
      },
    },
  }
}

function createDecisionFromWrite(state: AcceptanceState, payload: AnyRecord) {
  const decisionTableId = String(payload.decision_table_id || 'document-policy').trim()
  const latestRevision = state.decisions.reduce((max, item) => {
    if (String(item.decision_table_id || '') !== decisionTableId) return max
    const revision = Number(item.decision_revision || 0)
    return Number.isFinite(revision) ? Math.max(max, revision) : max
  }, 0)

  const decision = {
    id: `decision-version-${state.decisions.length + 1}`,
    decision_table_id: decisionTableId,
    decision_key: String(payload.decision_key || 'document_policy'),
    decision_revision: latestRevision + 1,
    name: String(payload.name || decisionTableId),
    description: String(payload.description || ''),
    inputs: [],
    outputs: [],
    rules: Array.isArray(payload.rules) ? deepClone(payload.rules) : [],
    hit_policy: 'first_match',
    validation_mode: 'fail_closed',
    is_active: payload.is_active !== false,
    parent_version: typeof payload.parent_version_id === 'string' && payload.parent_version_id.trim()
      ? payload.parent_version_id
      : null,
    metadata_context: deepClone(state.metadataContext),
    metadata_compatibility: {
      status: 'compatible',
      reason: null,
      is_compatible: true,
    },
    created_at: NOW,
    updated_at: NOW,
  }

  state.decisions = [decision, ...state.decisions]
  return decision
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

async function setupApiMocks(page: Page, state: AcceptanceState) {
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
      return fulfillJson(route, { id: 1, username: 'browser-user', is_staff: false })
    }

    if (method === 'GET' && path === '/api/v2/rbac/get-effective-access/') {
      return fulfillJson(route, { clusters: [], databases: [] })
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-roles/') {
      return fulfillJson(route, { roles: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-capabilities/') {
      return fulfillJson(route, { capabilities: [] })
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
        databases: state.databases,
        count: state.databases.length,
        total: state.databases.length,
      })
    }

    if (method === 'GET' && path === '/api/v2/decisions/') {
      const databaseId = url.searchParams.get('database_id') || ''
      state.decisionListQueries.push(databaseId)
      return fulfillJson(route, {
        decisions: state.decisions,
        count: state.decisions.length,
        ...(databaseId ? { metadata_context: state.metadataContext } : {}),
      })
    }

    const decisionDetailMatch = path.match(/^\/api\/v2\/decisions\/([^/]+)\/$/)
    if (method === 'GET' && decisionDetailMatch) {
      const decisionId = decisionDetailMatch[1]
      const databaseId = url.searchParams.get('database_id') || ''
      const decision = state.decisions.find((item) => String(item.id) === decisionId)
      if (!decision) {
        return fulfillJson(route, { detail: 'Decision not found' }, 404)
      }
      return fulfillJson(route, {
        decision,
        ...(databaseId ? { metadata_context: state.metadataContext } : {}),
      })
    }

    if (method === 'POST' && path === '/api/v2/decisions/') {
      const payload = (request.postDataJSON() as AnyRecord | null) ?? {}
      state.decisionWrites.push(deepClone(payload))
      const decision = createDecisionFromWrite(state, payload)
      return fulfillJson(route, {
        decision,
        metadata_context: state.metadataContext,
      }, 201)
    }

    if (method === 'GET' && path === '/api/v2/operation-catalog/exposures/') {
      return fulfillJson(route, {
        exposures: state.templateExposures,
        count: state.templateExposures.length,
        total: state.templateExposures.length,
      })
    }

    if (method === 'GET' && path === '/api/v2/templates/pool-runtime-registry/') {
      return fulfillJson(route, state.poolRuntimeRegistry)
    }

    if (method === 'GET' && path === '/api/v2/pools/organizations/') {
      return fulfillJson(route, {
        organizations: state.organizations,
        count: state.organizations.length,
      })
    }

    const organizationDetailMatch = path.match(/^\/api\/v2\/pools\/organizations\/([^/]+)\/$/)
    if (method === 'GET' && organizationDetailMatch) {
      const organization = state.organizations.find((item) => String(item.id) === organizationDetailMatch[1])
      if (!organization) {
        return fulfillJson(route, { detail: 'Organization not found' }, 404)
      }
      return fulfillJson(route, { organization, pool_bindings: [] })
    }

    if (method === 'GET' && path === '/api/v2/pools/') {
      return fulfillJson(route, {
        pools: state.pools,
        count: state.pools.length,
      })
    }

    const graphMatch = path.match(/^\/api\/v2\/pools\/([^/]+)\/graph\/$/)
    if (method === 'GET' && graphMatch) {
      const poolId = graphMatch[1]
      const graph = state.graphsByPoolId[poolId]
      if (!graph) {
        return fulfillJson(route, { detail: 'Graph not found' }, 404)
      }
      return fulfillJson(route, graph)
    }

    const topologySnapshotsMatch = path.match(/^\/api\/v2\/pools\/([^/]+)\/topology-snapshots\/$/)
    if (method === 'GET' && topologySnapshotsMatch) {
      const poolId = topologySnapshotsMatch[1]
      return fulfillJson(route, state.topologySnapshotsByPoolId[poolId] ?? {
        pool_id: poolId,
        count: 0,
        snapshots: [],
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/odata-metadata/catalog/') {
      return fulfillJson(route, state.metadataContext)
    }

    if (method === 'POST' && path === '/api/v2/pools/odata-metadata/catalog/refresh/') {
      return fulfillJson(route, state.metadataContext)
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/parties/') {
      return fulfillJson(route, { parties: [], meta: { limit: 100, offset: 0, total: 0 } })
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/items/') {
      return fulfillJson(route, { items: [], meta: { limit: 100, offset: 0, total: 0 } })
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/contracts/') {
      return fulfillJson(route, { contracts: [], meta: { limit: 100, offset: 0, total: 0 } })
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/tax-profiles/') {
      return fulfillJson(route, { tax_profiles: [], meta: { limit: 100, offset: 0, total: 0 } })
    }

    if (method === 'GET' && path === '/api/v2/pools/workflow-bindings/') {
      const poolId = String(url.searchParams.get('pool_id') || '')
      const bindings = state.workflowBindingsByPoolId[poolId] ?? []
      return fulfillJson(route, {
        pool_id: poolId,
        workflow_bindings: bindings,
        collection_etag: getBindingCollectionEtag(poolId, bindings),
        blocking_remediation: null,
      })
    }

    if (method === 'PUT' && path === '/api/v2/pools/workflow-bindings/') {
      const payload = (request.postDataJSON() as AnyRecord | null) ?? {}
      const poolId = String(payload.pool_id || POOL_ID)
      state.bindingUpsertCalls += 1
      state.lastBindingPayload = deepClone(payload)

      if (state.bindingConflictOnce) {
        state.bindingConflictOnce = false
        return fulfillJson(route, {
          type: 'about:blank',
          title: 'Workflow Binding Collection Conflict',
          status: 409,
          detail: 'Workflow binding collection was updated by another operator. Reload bindings and retry.',
          code: 'POOL_WORKFLOW_BINDING_COLLECTION_CONFLICT',
        }, 409)
      }

      const currentBindings = state.workflowBindingsByPoolId[poolId] ?? []
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
        const nextBinding = rawBinding && typeof rawBinding === 'object'
          ? deepClone(rawBinding as AnyRecord)
          : {}
        const workflow = typeof nextBinding.workflow === 'object' && nextBinding.workflow !== null
          ? nextBinding.workflow as AnyRecord
          : {}
        const selector = typeof nextBinding.selector === 'object' && nextBinding.selector !== null
          ? nextBinding.selector as AnyRecord
          : {}
        return {
          contract_version: String(nextBinding.contract_version || 'pool_workflow_binding.v1'),
          binding_id: String(nextBinding.binding_id || `binding-${index + 1}`).trim(),
          pool_id: poolId,
          workflow: {
            workflow_definition_key: String(workflow.workflow_definition_key || ''),
            workflow_revision_id: String(workflow.workflow_revision_id || ''),
            workflow_revision: Number(workflow.workflow_revision || 0),
            workflow_name: String(workflow.workflow_name || ''),
          },
          selector: {
            direction: String(selector.direction || ''),
            mode: String(selector.mode || ''),
            tags: Array.isArray(selector.tags) ? selector.tags : [],
          },
          decisions: Array.isArray(nextBinding.decisions) ? deepClone(nextBinding.decisions) : [],
          parameters: typeof nextBinding.parameters === 'object' && nextBinding.parameters !== null ? deepClone(nextBinding.parameters) : {},
          role_mapping: typeof nextBinding.role_mapping === 'object' && nextBinding.role_mapping !== null ? deepClone(nextBinding.role_mapping) : {},
          effective_from: String(nextBinding.effective_from || ''),
          effective_to: nextBinding.effective_to ?? null,
          status: String(nextBinding.status || 'draft'),
          revision: Number(nextBinding.revision || 1),
        }
      })
      state.workflowBindingsByPoolId[poolId] = nextBindings
      const nextEtag = computeBindingCollectionEtag(nextBindings)
      bindingCollectionEtags.set(poolId, nextEtag)

      return fulfillJson(route, {
        pool_id: poolId,
        workflow_bindings: nextBindings,
        collection_etag: nextEtag,
        blocking_remediation: null,
      })
    }

    if (method === 'POST' && path === '/api/v2/pools/workflow-bindings/preview/') {
      const payload = (request.postDataJSON() as AnyRecord | null) ?? {}
      state.previewCalls += 1
      state.lastPreviewPayload = deepClone(payload)
      const poolId = String(payload.pool_id || POOL_ID)
      const binding = deepClone((state.workflowBindingsByPoolId[poolId] ?? [])[0] ?? {})
      return fulfillJson(route, {
        workflow_binding: binding,
        compiled_document_policy: {
          source_mode: 'decision_tables',
          policy_refs: ['services-publication-policy:r1'],
        },
        runtime_projection: {
          version: 'pool_runtime_projection.v1',
          run_id: 'preview-run',
          pool_id: poolId,
          direction: String(payload.direction || 'top_down'),
          mode: String(payload.mode || 'safe'),
          workflow_definition: {
            plan_key: 'plan-services-v7',
            template_version: 'workflow-template:7',
            workflow_template_name: 'compiled-services-publication',
            workflow_type: 'sequential',
          },
          workflow_binding: {
            binding_mode: 'pool_workflow_binding',
            binding_id: binding.binding_id,
            pool_id: binding.pool_id,
            workflow_definition_key: binding.workflow?.workflow_definition_key,
            workflow_revision_id: binding.workflow?.workflow_revision_id,
            workflow_revision: binding.workflow?.workflow_revision,
            workflow_name: binding.workflow?.workflow_name,
            decision_refs: binding.decisions ?? [],
            selector: binding.selector ?? {},
            status: binding.status ?? 'active',
          },
          document_policy_projection: {
            source_mode: 'decision_tables',
            policy_refs: [{ policy_id: 'services-publication-policy:r1' }],
            policy_refs_count: 1,
            targets_count: 1,
          },
          artifacts: {
            document_plan_artifact_version: 'document-plan:v7',
            topology_version_ref: 'topology:v7',
            distribution_artifact_ref: { id: 'distribution:v7' },
          },
          compile_summary: {
            steps_count: 5,
            atomic_publication_steps_count: 3,
            compiled_targets_count: 1,
          },
        },
      })
    }

    const migrationMatch = path.match(/^\/api\/v2\/pools\/([^/]+)\/document-policy-migrations\/$/)
    if (method === 'POST' && migrationMatch) {
      const poolId = migrationMatch[1]
      const payload = (request.postDataJSON() as AnyRecord | null) ?? {}
      state.migrationCalls += 1
      state.lastMigrationPayload = deepClone(payload)

      const migratedDecision = deepClone(BASE_DECISION)
      const bindings = state.workflowBindingsByPoolId[poolId] ?? []
      state.workflowBindingsByPoolId[poolId] = bindings.map((binding) => ({
        ...binding,
        decisions: [
          {
            decision_table_id: migratedDecision.decision_table_id,
            decision_key: migratedDecision.decision_key,
            decision_revision: migratedDecision.decision_revision,
          },
        ],
      }))

      return fulfillJson(route, {
        decision: migratedDecision,
        metadata_context: state.metadataContext,
        migration: {
          created: true,
          reused_existing_revision: false,
          binding_update_required: false,
          source: {
            source_path: 'edge.metadata.document_policy',
            pool_id: poolId,
            pool_code: 'pool-hardening',
            edge_version_id: String(payload.edge_version_id || 'edge-v1'),
          },
          decision_ref: {
            decision_id: migratedDecision.id,
            decision_table_id: migratedDecision.decision_table_id,
            decision_revision: migratedDecision.decision_revision,
          },
        },
      }, 201)
    }

    if (method === 'GET' && path === '/api/v2/pools/schema-templates/') {
      return fulfillJson(route, { templates: [], count: 0 })
    }

    if (method === 'GET' && path === '/api/v2/pools/runs/') {
      const poolId = String(url.searchParams.get('pool_id') || '')
      const runs = poolId
        ? state.runs.filter((item) => String(item.pool_id) === poolId)
        : state.runs
      return fulfillJson(route, { runs, count: runs.length })
    }

    if (method === 'POST' && path === '/api/v2/pools/runs/') {
      const payload = (request.postDataJSON() as AnyRecord | null) ?? {}
      state.createRunCalls += 1
      state.lastCreateRunPayload = deepClone(payload)
      const poolId = String(payload.pool_id || POOL_ID)
      const binding = deepClone((state.workflowBindingsByPoolId[poolId] ?? [])[0] ?? {})
      const run = {
        ...buildPublishedRun(),
        id: `run-created-${state.createRunCalls}`,
        pool_id: poolId,
        direction: String(payload.direction || 'top_down'),
        mode: String(payload.mode || 'safe'),
        run_input: deepClone((payload.run_input as AnyRecord | null) ?? { starting_amount: '150.00' }),
        idempotency_key: `idem-created-${state.createRunCalls}`,
        workflow_binding: binding,
      }
      state.runs = [run, ...state.runs]
      state.runReportsByRunId[String(run.id)] = {
        run,
        publication_attempts: [],
        validation_summary: run.validation_summary,
        publication_summary: run.publication_summary,
        diagnostics: run.diagnostics,
        attempts_by_status: {},
      }
      return fulfillJson(route, { run, created: true }, 201)
    }

    const runReportMatch = path.match(/^\/api\/v2\/pools\/runs\/([^/]+)\/report\/$/)
    if (method === 'GET' && runReportMatch) {
      const runId = runReportMatch[1]
      const report = state.runReportsByRunId[runId]
      if (!report) {
        return fulfillJson(route, { detail: 'Run report not found' }, 404)
      }
      return fulfillJson(route, report)
    }

    return fulfillJson(route, {}, 200)
  })
}

test('Workflow hardening: /decisions shows shared metadata provenance, canonical legacy import, and decision lifecycle actions', async ({ page }) => {
  const state = createAcceptanceState()

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/decisions', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Decision Policy Library' })).toBeVisible()
  await expect(page.getByText('/decisions is the primary surface for document_policy authoring.')).toBeVisible()
  await expect(page.getByText('shared-profile').first()).toBeVisible()
  await expect(page.getByText('shared_scope').first()).toBeVisible()
  await expect(page.getByText('20202020-2020-2020-2020-202020202020').first()).toBeVisible()
  await expect(page.getByText('Services publication policy').first()).toBeVisible()
  await expect(page.getByText('Showing 1 of 2 revisions matching the selected configuration.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Show all revisions' })).toBeVisible()
  await expect(page.getByText('Previous release policy')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Import legacy edge' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Import raw JSON' })).toBeVisible()
  await expect.poll(() => state.decisionListQueries.at(-1)).toBe('10101010-1010-1010-1010-101010101010')

  await page.getByRole('button', { name: 'Show all revisions' }).click()
  await expect(page.getByText('Showing all 2 revisions for diagnostics. 1 revision does not match the selected configuration.')).toBeVisible()
  await expect(page.getByText('Previous release policy')).toBeVisible()

  await page.getByTestId('decisions-database-select').click()
  await page.getByText('Shared provenance DB (shared-profile)').click()
  await expect(page.getByText('Showing 1 of 2 revisions matching the selected configuration.')).toBeVisible()
  await expect(page.getByText('Previous release policy')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Show matching configuration only' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Import legacy edge' }).click()
  await expect(page.getByText('Import legacy edge policy')).toBeVisible()
  await page.getByLabel('Decision table ID').fill('browser-imported-policy')
  await page.getByLabel('Decision name').fill('Browser imported policy')
  await page.getByLabel('Decision description').fill('Imported from browser legacy edge')
  await page.getByRole('button', { name: 'Import to /decisions' }).click()

  await expect.poll(() => state.migrationCalls).toBe(1)
  await expect.poll(() => String(state.lastMigrationPayload?.edge_version_id || '')).toBe('edge-v1')
  await expect.poll(() => String(state.lastMigrationPayload?.decision_table_id || '')).toBe('browser-imported-policy')
  await expect.poll(() => String(state.lastMigrationPayload?.name || '')).toBe('Browser imported policy')
  await expect.poll(() => String(state.lastMigrationPayload?.description || '')).toBe('Imported from browser legacy edge')
  await expect(page.getByText('Imported to /decisions', { exact: true })).toBeVisible()
  await expect(page.getByText('Source: edge.metadata.document_policy (edge-v1)')).toBeVisible()
  await expect(page.getByText('Decision ref: services-publication-policy r2')).toBeVisible()
  await expect(page.getByText('Affected workflow bindings were updated automatically.')).toBeVisible()

  await page.getByRole('button', { name: 'New policy' }).click()
  await page.getByLabel('Decision table ID').fill('browser-policy')
  await page.getByLabel('Decision name').fill('Browser decision policy')
  await page.getByRole('button', { name: 'Add chain' }).click()
  await page.getByLabel('Chain 1 ID').fill('sale_chain')
  await page.getByRole('button', { name: 'Add document to chain 1' }).click()
  await page.getByLabel('Chain 1 document 1 ID').fill('sale')
  await page.getByLabel('Chain 1 document 1 entity').fill('Document_Sales')
  await page.getByLabel('Chain 1 document 1 role').fill('sale')
  await page.getByRole('button', { name: 'Save decision' }).click()

  await expect.poll(() => state.decisionWrites.length).toBe(1)
  await expect.poll(() => String(state.decisionWrites[0]?.decision_table_id || '')).toBe('browser-policy')
  await expect(page.getByText('Browser decision policy').first()).toBeVisible()

  await page.getByRole('button', { name: 'Edit selected decision' }).click()
  await page.getByLabel('Decision name').fill('Services publication policy v3')
  await page.getByRole('button', { name: 'Save decision' }).click()

  await expect.poll(() => state.decisionWrites.length).toBe(2)
  await expect.poll(() => String(state.decisionWrites[1]?.parent_version_id || '')).toBe('decision-version-3')
  await expect.poll(() => String(state.decisionWrites[1]?.name || '')).toBe('Services publication policy v3')

  await page.getByRole('button', { name: 'Deactivate selected decision' }).click()

  await expect.poll(() => state.decisionWrites.length).toBe(3)
  await expect.poll(() => Boolean(state.decisionWrites[2]?.is_active)).toBe(false)

  await page.getByTestId('decisions-database-select').hover()
  await page.locator('[data-testid="decisions-database-select"] .ant-select-clear').click()
  await expect.poll(() => state.decisionListQueries.at(-1)).toBe('')
  await expect(page.getByText('Select database')).toBeVisible()
})

test('Workflow hardening: /decisions supports guided rollover from a previous-release revision', async ({ page }) => {
  const state = createAcceptanceState()

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/decisions', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Decision Policy Library' })).toBeVisible()
  await expect(page.getByText('Previous release policy')).toHaveCount(0)

  await page.getByRole('button', { name: 'Show all revisions' }).click()
  await expect(page.getByText('Previous release policy')).toBeVisible()
  await page.getByText('Previous release policy').click()

  await expect(page.getByRole('button', { name: 'Edit selected decision' })).toBeDisabled()
  await expect(page.getByText('This revision is outside the default compatible set for the selected database. Use Rollover selected revision to create a new revision for the current target metadata context.')).toBeVisible()

  await page.getByRole('button', { name: 'Rollover selected revision' }).click()

  await expect(page.getByRole('heading', { name: 'Rollover selected revision' })).toBeVisible()
  await expect(page.getByText('Source revision')).toBeVisible()
  await expect(page.getByText('Previous release policy (services-publication-policy r7)')).toBeVisible()
  await expect(page.getByText('Target database', { exact: true })).toBeVisible()
  await expect(page.getByText('Target DB (shared-profile)').last()).toBeVisible()
  await expect(page.getByText('Target metadata snapshot', { exact: true })).toBeVisible()
  await expect(page.getByText('shared-profile 8.3.24')).toBeVisible()
  await expect(page.getByText('Publishing a rollover creates a new revision only. Existing workflows, bindings, and runtime projections stay pinned until you update them explicitly.')).toBeVisible()

  await page.getByLabel('Decision name').fill('Previous release policy for Target DB')
  await page.getByRole('button', { name: 'Publish rollover revision' }).click()

  await expect.poll(() => state.decisionWrites.length).toBe(1)
  await expect.poll(() => String(state.decisionWrites[0]?.database_id || '')).toBe('10101010-1010-1010-1010-101010101010')
  await expect.poll(() => String(state.decisionWrites[0]?.parent_version_id || '')).toBe('decision-version-previous-release')
  await expect.poll(() => String(state.decisionWrites[0]?.name || '')).toBe('Previous release policy for Target DB')
  await expect.poll(() => String(state.decisions[0]?.parent_version || '')).toBe('decision-version-previous-release')
  await expect.poll(() => String((state.decisions[0]?.metadata_context as AnyRecord | undefined)?.config_version || '')).toBe('8.3.24')
})

test('Workflow hardening: /templates, /pools/catalog, and /decisions expose compatibility guidance and legacy migration outcome', async ({ page }) => {
  const state = createAcceptanceState()

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/templates', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Operation Templates' })).toBeVisible()
  await expect(page.getByText('Atomic operations only')).toBeVisible()
  await expect(page.getByText('Use /workflows to model analyst-facing schemes. workflow executor templates remain available here only as a compatibility/integration path.')).toBeVisible()
  await expect(page.getByText('Workflow Compatibility Template')).toBeVisible()
  await expect(page.getByTestId('templates-executor-kind-compatibility-tag')).toHaveText('compatibility')

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Pool Catalog' })).toBeVisible()
  await page.getByRole('tab', { name: 'Bindings' }).click()
  await expect(page.getByText('Workflow bindings workspace')).toBeVisible()
  await expect(page.getByText('Workflow bindings are managed separately from pool fields')).toBeVisible()
  await expect(page.getByTestId('pool-catalog-save-bindings')).toBeVisible()
  await expect(page.getByTestId('pool-catalog-workflow-binding-workflow-key-0')).toHaveValue('services-publication')
  await page.getByRole('tab', { name: 'Topology Editor' }).click()
  const topologyEditorPanel = page.getByLabel('Topology Editor')
  await expect(topologyEditorPanel.getByText('Topology snapshots by date')).toBeVisible()
  await expect(topologyEditorPanel.getByText('Workflow-centric authoring is the default path')).toBeVisible()
  await expect(topologyEditorPanel.getByText('Legacy topology remediation required')).toBeVisible()
  await expect(
    topologyEditorPanel.getByText('Move concrete policy authoring to /decisions, pin named slots in Bindings, then keep only document_policy_key on topology edges.')
  ).toBeVisible()

  await topologyEditorPanel.getByRole('button', { name: 'Open /decisions' }).first().click()

  await expect(page.getByRole('heading', { name: 'Decision Policy Library' })).toBeVisible()
  await page.getByRole('button', { name: 'Import legacy edge' }).click()
  await expect(page.getByText('Import legacy edge policy')).toBeVisible()
  await page.getByLabel('Decision table ID').fill('browser-imported-policy')
  await page.getByLabel('Decision name').fill('Browser imported policy')
  await page.getByLabel('Decision description').fill('Imported from browser legacy edge')
  await page.getByRole('button', { name: 'Import to /decisions' }).click()

  await expect.poll(() => state.migrationCalls).toBe(1)
  await expect.poll(() => String(state.lastMigrationPayload?.edge_version_id || '')).toBe('edge-v1')
  await expect.poll(() => String(state.lastMigrationPayload?.decision_table_id || '')).toBe('browser-imported-policy')
  await expect.poll(() => String(state.lastMigrationPayload?.name || '')).toBe('Browser imported policy')
  await expect.poll(() => String(state.lastMigrationPayload?.description || '')).toBe('Imported from browser legacy edge')
  await expect(page.getByText('Imported to /decisions', { exact: true })).toBeVisible()
  await expect(page.getByText('Source: edge.metadata.document_policy (edge-v1)')).toBeVisible()
  await expect(page.getByText('Decision ref: services-publication-policy r2')).toBeVisible()
  await expect(page.getByText('Affected workflow bindings were updated automatically.')).toBeVisible()
})

test('Workflow hardening: /pools/catalog preserves edited binding fields on stale revision conflict', async ({ page }) => {
  const state = createAcceptanceState()
  state.bindingConflictOnce = true

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })

  await page.getByRole('tab', { name: 'Bindings' }).click()
  const workflowNameField = page.getByTestId('pool-catalog-workflow-binding-workflow-name-0')

  await expect(workflowNameField).toHaveValue('services_publication')

  await workflowNameField.fill('services_publication_conflicted')
  await page.getByTestId('pool-catalog-save-bindings').click()

  await expect.poll(() => state.bindingUpsertCalls).toBe(1)
  await expect(page.getByText('Набор workflow bindings уже был изменён другим оператором. Обновите bindings и повторите сохранение.')).toBeVisible()
  await expect(workflowNameField).toHaveValue('services_publication_conflicted')
})

test('Workflow hardening: /pools/runs blocks submit when no workflow binding is selected', async ({ page }) => {
  const state = createAcceptanceState()
  state.workflowBindingsByPoolId[POOL_ID] = [
    deepClone(state.workflowBindingsByPoolId[POOL_ID][0]),
    {
      ...deepClone(state.workflowBindingsByPoolId[POOL_ID][0]),
      binding_id: 'binding-top-down-secondary',
      workflow: {
        workflow_definition_key: 'services-publication-alt',
        workflow_revision_id: 'workflow-revision-9',
        workflow_revision: 9,
        workflow_name: 'services_publication_alt',
      },
      revision: 1,
    },
  ]
  state.pools = state.pools.map((pool) => (
    String(pool.id) === POOL_ID
      ? {
        ...pool,
        workflow_bindings: deepClone(state.workflowBindingsByPoolId[POOL_ID]),
      }
      : pool
  ))

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/runs', { waitUntil: 'domcontentloaded' })

  await page.getByRole('tab', { name: 'Create' }).click()
  await expect(page.getByTestId('pool-runs-create-preview')).toBeDisabled()

  await page.getByTestId('pool-runs-create-submit').click()

  await expect.poll(() => state.previewCalls).toBe(0)
  await expect.poll(() => state.createRunCalls).toBe(0)
  await expect(page.getByText('workflow binding required')).toBeVisible()
})

test('Workflow hardening: /pools/runs shipped flow shows pinned decision lineage and verification outcome', async ({ page }) => {
  const state = createAcceptanceState()

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/runs', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Pool Runs' })).toBeVisible()
  await page.getByRole('tab', { name: 'Inspect' }).click()
  await expect(page.getByTestId('pool-runs-verification-status')).toHaveText('status: passed')
  await expect(page.getByText('Published documents verified')).toBeVisible()
  await expect(page.getByText('document_policy r2')).toBeVisible()
  await expect(page.getByTestId('pool-runs-provenance-workflow-id')).toContainText('workflow-run-1')
  await expect(page.getByRole('link', { name: 'Open Workflow Diagnostics' })).toHaveAttribute('href', '/workflows/executions/workflow-execution-1')
})

test('Workflow hardening: operator canary covers preview, create-run and inspect on the default path', async ({ page }) => {
  const state = createAcceptanceState()
  state.pools = state.pools.map((pool) => (
    String(pool.id) === POOL_ID
      ? {
        ...pool,
        workflow_bindings: deepClone(state.workflowBindingsByPoolId[POOL_ID] ?? []),
      }
      : pool
  ))

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/pools/runs', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Pool Runs' })).toBeVisible()
  await page.getByRole('tab', { name: 'Create' }).click()
  await expect(page.getByTestId('pool-runs-create-workflow-binding')).toContainText('services_publication')

  await page.getByTestId('pool-runs-create-preview').click()

  await expect.poll(() => state.previewCalls).toBe(1)
  await expect.poll(() => String(state.lastPreviewPayload?.pool_workflow_binding_id || '')).toBe(BINDING_ID)
  await expect.poll(() => String(state.lastPreviewPayload?.direction || '')).toBe('top_down')
  await expect.poll(() => String(state.lastPreviewPayload?.mode || '')).toBe('safe')

  await expect(page.getByTestId('pool-runs-binding-preview')).toBeVisible()
  await expect(page.getByText('decision_tables', { exact: true })).toBeVisible()
  await expect(page.getByText('compiled targets: 1')).toBeVisible()
  await expect(page.getByText('services-publication-policy:r1')).toBeVisible()

  await page.getByTestId('pool-runs-create-submit').click()

  await expect.poll(() => state.createRunCalls).toBe(1)
  await expect.poll(() => String(state.lastCreateRunPayload?.pool_workflow_binding_id || '')).toBe(BINDING_ID)
  await expect.poll(() => String(state.lastCreateRunPayload?.direction || '')).toBe('top_down')

  await page.getByRole('tab', { name: 'Inspect' }).click()
  await expect(page.getByTestId('pool-runs-lineage-binding-id')).toContainText(BINDING_ID)
  await expect(page.getByText('document_policy r1')).toBeVisible()
  await expect(page.getByTestId('pool-runs-provenance-workflow-id')).toContainText('workflow-run-1')
  await expect(page.getByRole('link', { name: 'Open Workflow Diagnostics' })).toHaveAttribute('href', '/workflows/executions/workflow-execution-1')
})
