import { expect, test, type Locator, type Page, type Route } from '@playwright/test'

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>
  }
}

const TENANT_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
const DATABASE_ID = '10101010-1010-1010-1010-101010101010'
const NOW = '2026-03-10T12:00:00Z'
const WORKFLOW_REVISION_ID = 'wf-services-r4'
const ROUTE_MOUNT_TIMEOUT_MS = 15000
const DATABASE_RECORD = {
  id: DATABASE_ID,
  name: 'db-services',
  host: 'srv-1c.local',
  port: 1541,
  base_name: 'shared-profile',
  odata_url: 'http://srv-1c.local/odata',
  username: 'odata_user',
  password: '',
  password_configured: true,
  server_address: 'srv-1c.local',
  server_port: 1540,
  infobase_name: 'shared-profile',
  status: 'active',
  status_display: 'Active',
  version: '8.3.24',
  last_check: NOW,
  last_check_status: 'ok',
  consecutive_failures: 0,
  avg_response_time: 12,
  cluster_id: 'cluster-1',
  is_healthy: true,
  sessions_deny: false,
  scheduled_jobs_deny: false,
  dbms: 'PostgreSQL',
  db_server: 'pg-db.internal',
  db_name: 'shared_profile',
  ibcmd_connection: {
    remote: 'ssh://srv-1c.local:22',
    pid: 1200,
    offline: {
      path: '/srv/ibcmd',
    },
  },
  denied_from: null,
  denied_to: null,
  denied_message: null,
  permission_code: null,
  denied_parameter: null,
  last_health_error: null,
  last_health_error_code: null,
  created_at: NOW,
  updated_at: NOW,
}

const CLUSTER_RECORD = {
  id: 'cluster-1',
  name: 'Main Cluster',
  description: 'Primary RAS cluster for shared services',
  ras_host: 'srv-ras.local',
  ras_port: 1545,
  ras_server: 'srv-ras.local:1545',
  rmngr_host: 'srv-rmngr.local',
  rmngr_port: 1541,
  ragent_host: 'srv-ragent.local',
  ragent_port: 1540,
  rphost_port_from: 1560,
  rphost_port_to: 1591,
  cluster_service_url: 'http://srv-ragent.local:8188',
  cluster_user: 'cluster-admin',
  cluster_pwd_configured: true,
  status: 'active',
  status_display: 'Active',
  last_sync: NOW,
  metadata: {
    deployment: 'primary',
    region: 'eu-central',
  },
  databases_count: 1,
  created_at: NOW,
  updated_at: NOW,
}

const CLUSTER_DETAIL_RESPONSE = {
  cluster: CLUSTER_RECORD,
  databases: [DATABASE_RECORD],
  statistics: {
    total_databases: 1,
    healthy_databases: 1,
    databases_by_status: {
      active: 1,
      inactive: 0,
      error: 0,
      maintenance: 0,
    },
  },
}

const SYSTEM_HEALTH_RESPONSE = {
  timestamp: NOW,
  overall_status: 'degraded',
  services: [
    {
      name: 'api-gateway',
      type: 'go-service',
      url: 'http://gateway.local/health',
      status: 'online',
      response_time_ms: 24,
      last_check: NOW,
      details: {
        version: '1.0.0',
      },
    },
    {
      name: 'orchestrator',
      type: 'django',
      url: 'http://orchestrator.local/health',
      status: 'degraded',
      response_time_ms: 148,
      last_check: NOW,
      details: {
        reason: 'Delayed queue drain',
      },
    },
    {
      name: 'worker',
      type: 'go-service',
      url: 'http://worker.local/health',
      status: 'online',
      response_time_ms: 41,
      last_check: NOW,
      details: {
        active_jobs: 3,
      },
    },
  ],
  statistics: {
    total: 3,
    online: 2,
    offline: 0,
    degraded: 1,
  },
}

const SERVICE_MESH_METRICS_MESSAGE = {
  type: 'metrics_update',
  timestamp: NOW,
  overallHealth: 'degraded',
  services: [
    {
      name: 'api-gateway',
      display_name: 'API Gateway',
      status: 'healthy',
      ops_per_minute: 124,
      active_operations: 2,
      p95_latency_ms: 32,
      error_rate: 0.003,
      last_updated: NOW,
    },
    {
      name: 'orchestrator',
      display_name: 'Orchestrator',
      status: 'degraded',
      ops_per_minute: 76,
      active_operations: 1,
      p95_latency_ms: 190,
      error_rate: 0.018,
      last_updated: NOW,
    },
    {
      name: 'worker',
      display_name: 'Worker',
      status: 'healthy',
      ops_per_minute: 58,
      active_operations: 1,
      p95_latency_ms: 64,
      error_rate: 0.001,
      last_updated: NOW,
    },
  ],
  connections: [
    {
      source: 'api-gateway',
      target: 'orchestrator',
      requests_per_minute: 124,
      avg_latency_ms: 18,
    },
    {
      source: 'orchestrator',
      target: 'worker',
      requests_per_minute: 58,
      avg_latency_ms: 42,
    },
  ],
}

const SERVICE_MESH_HISTORY: Record<string, {
  service: string
  display_name: string
  minutes: number
  data_points: Array<{
    timestamp: string
    ops_per_minute: number
    p95_latency_ms: number
    error_rate: number
  }>
}> = {
  orchestrator: {
    service: 'orchestrator',
    display_name: 'Orchestrator',
    minutes: 30,
    data_points: [
      { timestamp: '2026-03-10T11:40:00Z', ops_per_minute: 68, p95_latency_ms: 160, error_rate: 0.01 },
      { timestamp: '2026-03-10T11:50:00Z', ops_per_minute: 74, p95_latency_ms: 176, error_rate: 0.015 },
      { timestamp: '2026-03-10T12:00:00Z', ops_per_minute: 76, p95_latency_ms: 190, error_rate: 0.018 },
    ],
  },
  'api-gateway': {
    service: 'api-gateway',
    display_name: 'API Gateway',
    minutes: 30,
    data_points: [
      { timestamp: '2026-03-10T11:40:00Z', ops_per_minute: 118, p95_latency_ms: 28, error_rate: 0.002 },
      { timestamp: '2026-03-10T11:50:00Z', ops_per_minute: 122, p95_latency_ms: 30, error_rate: 0.003 },
      { timestamp: '2026-03-10T12:00:00Z', ops_per_minute: 124, p95_latency_ms: 32, error_rate: 0.003 },
    ],
  },
  worker: {
    service: 'worker',
    display_name: 'Worker',
    minutes: 30,
    data_points: [
      { timestamp: '2026-03-10T11:40:00Z', ops_per_minute: 52, p95_latency_ms: 58, error_rate: 0.001 },
      { timestamp: '2026-03-10T11:50:00Z', ops_per_minute: 55, p95_latency_ms: 61, error_rate: 0.001 },
      { timestamp: '2026-03-10T12:00:00Z', ops_per_minute: 58, p95_latency_ms: 64, error_rate: 0.001 },
    ],
  },
}

const METADATA_CONTEXT = {
  database_id: DATABASE_ID,
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

const METADATA_MANAGEMENT = {
  database_id: DATABASE_ID,
  configuration_profile: {
    status: 'verified',
    config_name: 'shared-profile',
    config_version: '8.3.24',
    config_generation_id: 'generation-shared-services',
    config_root_name: 'Accounting',
    config_vendor: '1C',
    config_name_source: 'manual',
    verification_operation_id: '',
    verified_at: NOW,
    generation_probe_requested_at: null,
    generation_probe_checked_at: null,
    observed_metadata_hash: 'a'.repeat(64),
    canonical_metadata_hash: 'a'.repeat(64),
    publication_drift: false,
    reverify_available: true,
    reverify_blocker_code: '',
    reverify_blocker_message: '',
    reverify_blocking_action: '',
  },
  metadata_snapshot: {
    status: 'available',
    missing_reason: '',
    snapshot_id: 'snapshot-shared-services',
    source: 'db',
    fetched_at: NOW,
    catalog_version: 'v1:shared-services',
    config_name: 'shared-profile',
    config_version: '8.3.24',
    config_generation_id: 'generation-shared-services',
    extensions_fingerprint: '',
    metadata_hash: 'a'.repeat(64),
    resolution_mode: 'shared_scope',
    is_shared_snapshot: true,
    provenance_database_id: '20202020-2020-2020-2020-202020202020',
    provenance_confirmed_at: NOW,
    observed_metadata_hash: 'a'.repeat(64),
    publication_drift: false,
  },
}

const DECISION = {
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
    snapshot_id: METADATA_CONTEXT.snapshot_id,
    config_name: METADATA_CONTEXT.config_name,
    config_version: METADATA_CONTEXT.config_version,
    config_generation_id: METADATA_CONTEXT.config_generation_id,
    extensions_fingerprint: '',
    metadata_hash: 'a'.repeat(64),
    observed_metadata_hash: 'a'.repeat(64),
    publication_drift: false,
    resolution_mode: 'shared_scope',
    is_shared_snapshot: true,
    provenance_database_id: METADATA_CONTEXT.provenance_database_id,
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

const FALLBACK_DECISION = {
  ...DECISION,
  id: 'decision-version-3',
  decision_revision: 3,
  name: 'Fallback services publication policy',
  description: 'Fallback policy for diagnostics',
  parent_version: DECISION.id,
}

const DECISIONS = [DECISION, FALLBACK_DECISION]

const WORKFLOW = {
  id: WORKFLOW_REVISION_ID,
  name: 'Services Publication',
  description: 'Reusable workflow for service publication.',
  workflow_type: 'complex',
  category: 'custom',
  is_valid: true,
  is_active: true,
  is_system_managed: false,
  management_mode: 'user_authored',
  visibility_surface: 'workflow_library',
  read_only_reason: null,
  version_number: 4,
  parent_version: null,
  created_by: null,
  created_by_username: 'analyst',
  node_count: 2,
  execution_count: 0,
  created_at: NOW,
  updated_at: NOW,
}

const BINDING_PROFILE_DETAIL = {
  binding_profile_id: 'bp-services',
  code: 'services-publication',
  name: 'Services Publication',
  description: 'Reusable scheme for top-down publication.',
  status: 'active',
  latest_revision_number: 2,
  latest_revision: {
    binding_profile_revision_id: 'bp-rev-services-r2',
    binding_profile_id: 'bp-services',
    revision_number: 2,
    workflow: {
      workflow_definition_key: 'services-publication',
      workflow_revision_id: 'wf-services-r2',
      workflow_revision: 4,
      workflow_name: 'services_publication',
    },
    decisions: [
      {
        decision_table_id: 'services-publication-policy',
        decision_key: 'document_policy',
        slot_key: 'document_policy',
        decision_revision: 2,
      },
    ],
    parameters: {
      publication_variant: 'full',
    },
    role_mapping: {
      initiator: 'finance',
    },
    metadata: {
      source: 'manual',
    },
    created_by: 'analyst',
    created_at: NOW,
  },
  revisions: [
    {
      binding_profile_revision_id: 'bp-rev-services-r2',
      binding_profile_id: 'bp-services',
      revision_number: 2,
      workflow: {
        workflow_definition_key: 'services-publication',
        workflow_revision_id: 'wf-services-r2',
        workflow_revision: 4,
        workflow_name: 'services_publication',
      },
      decisions: [],
      parameters: {},
      role_mapping: {},
      metadata: {},
      created_by: 'analyst',
      created_at: NOW,
    },
  ],
  usage_summary: {
    attachment_count: 1,
    revision_summary: [
      {
        binding_profile_revision_id: 'bp-rev-services-r2',
        binding_profile_revision_number: 2,
        attachment_count: 1,
      },
    ],
    attachments: [
      {
        pool_id: 'pool-1',
        pool_code: 'pool-main',
        pool_name: 'Main Pool',
        binding_id: 'binding-top-down',
        attachment_revision: 3,
        binding_profile_revision_id: 'bp-rev-services-r2',
        binding_profile_revision_number: 2,
        status: 'active',
        selector: {
          direction: 'top_down',
          mode: 'safe',
          tags: [],
        },
        effective_from: NOW,
        effective_to: null,
      },
    ],
  },
  created_by: 'analyst',
  updated_by: 'analyst',
  deactivated_by: null,
  deactivated_at: null,
  created_at: NOW,
  updated_at: NOW,
}

const BINDING_PROFILE_SUMMARY = {
  binding_profile_id: BINDING_PROFILE_DETAIL.binding_profile_id,
  code: BINDING_PROFILE_DETAIL.code,
  name: BINDING_PROFILE_DETAIL.name,
  description: BINDING_PROFILE_DETAIL.description,
  status: BINDING_PROFILE_DETAIL.status,
  latest_revision_number: BINDING_PROFILE_DETAIL.latest_revision_number,
  latest_revision: BINDING_PROFILE_DETAIL.latest_revision,
  created_by: BINDING_PROFILE_DETAIL.created_by,
  updated_by: BINDING_PROFILE_DETAIL.updated_by,
  deactivated_by: BINDING_PROFILE_DETAIL.deactivated_by,
  deactivated_at: BINDING_PROFILE_DETAIL.deactivated_at,
  created_at: BINDING_PROFILE_DETAIL.created_at,
  updated_at: BINDING_PROFILE_DETAIL.updated_at,
}

const LEGACY_BINDING_PROFILE_DETAIL = {
  ...BINDING_PROFILE_DETAIL,
  binding_profile_id: 'bp-legacy',
  code: 'legacy-archive',
  name: 'Legacy Archive',
  description: 'Legacy reusable profile kept for pinned attachments.',
  status: 'deactivated',
  latest_revision_number: 1,
  latest_revision: {
    binding_profile_revision_id: 'bp-rev-legacy-r1',
    binding_profile_id: 'bp-legacy',
    revision_number: 1,
    workflow: {
      workflow_definition_key: 'legacy-archive',
      workflow_revision_id: 'wf-legacy-r1',
      workflow_revision: 1,
      workflow_name: 'legacy_archive',
    },
    decisions: [
      {
        decision_table_id: 'services-publication-policy',
        decision_key: 'document_policy',
        slot_key: 'document_policy',
        decision_revision: 2,
      },
    ],
    parameters: {
      publication_variant: 'archive',
    },
    role_mapping: {
      initiator: 'finance',
    },
    metadata: {
      source: 'legacy',
    },
    created_by: 'analyst',
    created_at: NOW,
  },
  revisions: [
    {
      binding_profile_revision_id: 'bp-rev-legacy-r1',
      binding_profile_id: 'bp-legacy',
      revision_number: 1,
      workflow: {
        workflow_definition_key: 'legacy-archive',
        workflow_revision_id: 'wf-legacy-r1',
        workflow_revision: 1,
        workflow_name: 'legacy_archive',
      },
      decisions: [],
      parameters: {},
      role_mapping: {},
      metadata: {},
      created_by: 'analyst',
      created_at: NOW,
    },
  ],
  usage_summary: {
    attachment_count: 0,
    revision_summary: [],
    attachments: [],
  },
  deactivated_by: 'analyst',
  deactivated_at: NOW,
}

const LEGACY_BINDING_PROFILE_SUMMARY = {
  binding_profile_id: LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id,
  code: LEGACY_BINDING_PROFILE_DETAIL.code,
  name: LEGACY_BINDING_PROFILE_DETAIL.name,
  description: LEGACY_BINDING_PROFILE_DETAIL.description,
  status: LEGACY_BINDING_PROFILE_DETAIL.status,
  latest_revision_number: LEGACY_BINDING_PROFILE_DETAIL.latest_revision_number,
  latest_revision: LEGACY_BINDING_PROFILE_DETAIL.latest_revision,
  created_by: LEGACY_BINDING_PROFILE_DETAIL.created_by,
  updated_by: LEGACY_BINDING_PROFILE_DETAIL.updated_by,
  deactivated_by: LEGACY_BINDING_PROFILE_DETAIL.deactivated_by,
  deactivated_at: LEGACY_BINDING_PROFILE_DETAIL.deactivated_at,
  created_at: LEGACY_BINDING_PROFILE_DETAIL.created_at,
  updated_at: LEGACY_BINDING_PROFILE_DETAIL.updated_at,
}

const BINDING_PROFILE_SUMMARIES = [BINDING_PROFILE_SUMMARY, LEGACY_BINDING_PROFILE_SUMMARY]
const BINDING_PROFILE_DETAILS: Record<string, typeof BINDING_PROFILE_DETAIL> = {
  [BINDING_PROFILE_DETAIL.binding_profile_id]: BINDING_PROFILE_DETAIL,
  [LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id]: LEGACY_BINDING_PROFILE_DETAIL,
}

const TOPOLOGY_TEMPLATE = {
  topology_template_id: 'template-top-down',
  code: 'top-down-template',
  name: 'Top Down Template',
  description: 'Reusable topology for top-down publication.',
  status: 'active',
  metadata: {},
  latest_revision_number: 3,
  latest_revision: {
    topology_template_revision_id: 'template-revision-r3',
    topology_template_id: 'template-top-down',
    revision_number: 3,
    nodes: [
      {
        slot_key: 'root',
        label: 'Root',
        is_root: true,
        metadata: {},
      },
      {
        slot_key: 'organization_1',
        label: 'Organization 1',
        is_root: false,
        metadata: {},
      },
      {
        slot_key: 'organization_2',
        label: 'Organization 2',
        is_root: false,
        metadata: {},
      },
      {
        slot_key: 'organization_3',
        label: 'Organization 3',
        is_root: false,
        metadata: {},
      },
      {
        slot_key: 'organization_4',
        label: 'Organization 4',
        is_root: false,
        metadata: {},
      },
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
        {
          slot_key: 'root',
          label: 'Root',
          is_root: true,
          metadata: {},
        },
        {
          slot_key: 'organization_1',
          label: 'Organization 1',
          is_root: false,
          metadata: {},
        },
        {
          slot_key: 'organization_2',
          label: 'Organization 2',
          is_root: false,
          metadata: {},
        },
        {
          slot_key: 'organization_3',
          label: 'Organization 3',
          is_root: false,
          metadata: {},
        },
        {
          slot_key: 'organization_4',
          label: 'Organization 4',
          is_root: false,
          metadata: {},
        },
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
    {
      topology_template_revision_id: 'template-revision-r2',
      topology_template_id: 'template-top-down',
      revision_number: 2,
      nodes: [
        {
          slot_key: 'root',
          label: 'Root',
          is_root: true,
          metadata: {},
        },
        {
          slot_key: 'organization_1',
          label: 'Organization 1',
          is_root: false,
          metadata: {},
        },
        {
          slot_key: 'organization_2',
          label: 'Organization 2',
          is_root: false,
          metadata: {},
        },
        {
          slot_key: 'organization_3',
          label: 'Organization 3',
          is_root: false,
          metadata: {},
        },
        {
          slot_key: 'organization_4',
          label: 'Organization 4',
          is_root: false,
          metadata: {},
        },
      ],
      edges: [
        {
          parent_slot_key: 'root',
          child_slot_key: 'organization_1',
          weight: '1',
          min_amount: null,
          max_amount: null,
          document_policy_key: 'receipt',
          metadata: {},
        },
        {
          parent_slot_key: 'organization_1',
          child_slot_key: 'organization_2',
          weight: '1',
          min_amount: null,
          max_amount: null,
          document_policy_key: 'receipt',
          metadata: {},
        },
        {
          parent_slot_key: 'organization_2',
          child_slot_key: 'organization_3',
          weight: '1',
          min_amount: null,
          max_amount: null,
          document_policy_key: 'receipt',
          metadata: {},
        },
        {
          parent_slot_key: 'organization_2',
          child_slot_key: 'organization_4',
          weight: '1',
          min_amount: null,
          max_amount: null,
          document_policy_key: 'receipt',
          metadata: {},
        },
      ],
      metadata: {},
      created_at: NOW,
    },
  ],
  created_at: NOW,
  updated_at: NOW,
}

const MASTER_DATA_REGISTRY_RESPONSE = {
  contract_version: 'pool_master_data_registry.v1',
  count: 5,
  entries: [
    {
      entity_type: 'party',
      label: 'Party',
      kind: 'canonical',
      display_order: 10,
      binding_scope_fields: ['canonical_id', 'database_id', 'ib_catalog_kind'],
      capabilities: {
        direct_binding: true,
        token_exposure: true,
        bootstrap_import: true,
        outbox_fanout: true,
        sync_outbound: true,
        sync_inbound: true,
        sync_reconcile: true,
      },
      token_contract: {
        enabled: true,
        qualifier_kind: 'ib_catalog_kind',
        qualifier_required: true,
        qualifier_options: ['organization', 'counterparty'],
      },
      bootstrap_contract: { enabled: true, dependency_order: 10 },
      runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
    },
    {
      entity_type: 'item',
      label: 'Item',
      kind: 'canonical',
      display_order: 20,
      binding_scope_fields: ['canonical_id', 'database_id'],
      capabilities: {
        direct_binding: true,
        token_exposure: true,
        bootstrap_import: true,
        outbox_fanout: true,
        sync_outbound: true,
        sync_inbound: true,
        sync_reconcile: true,
      },
      token_contract: {
        enabled: true,
        qualifier_kind: 'none',
        qualifier_required: false,
        qualifier_options: [],
      },
      bootstrap_contract: { enabled: true, dependency_order: 20 },
      runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
    },
    {
      entity_type: 'contract',
      label: 'Contract',
      kind: 'canonical',
      display_order: 30,
      binding_scope_fields: ['canonical_id', 'database_id', 'owner_counterparty_canonical_id'],
      capabilities: {
        direct_binding: true,
        token_exposure: true,
        bootstrap_import: true,
        outbox_fanout: true,
        sync_outbound: true,
        sync_inbound: true,
        sync_reconcile: true,
      },
      token_contract: {
        enabled: true,
        qualifier_kind: 'owner_counterparty_canonical_id',
        qualifier_required: true,
        qualifier_options: [],
      },
      bootstrap_contract: { enabled: true, dependency_order: 30 },
      runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
    },
    {
      entity_type: 'gl_account',
      label: 'GL Account',
      kind: 'canonical',
      display_order: 35,
      binding_scope_fields: ['canonical_id', 'database_id', 'chart_identity'],
      capabilities: {
        direct_binding: true,
        token_exposure: true,
        bootstrap_import: true,
        outbox_fanout: false,
        sync_outbound: false,
        sync_inbound: false,
        sync_reconcile: false,
      },
      token_contract: {
        enabled: true,
        qualifier_kind: 'none',
        qualifier_required: false,
        qualifier_options: [],
      },
      bootstrap_contract: { enabled: true, dependency_order: 35 },
      runtime_consumers: ['bindings', 'bootstrap_import', 'token_catalog', 'token_parser'],
    },
    {
      entity_type: 'tax_profile',
      label: 'Tax Profile',
      kind: 'canonical',
      display_order: 40,
      binding_scope_fields: ['canonical_id', 'database_id'],
      capabilities: {
        direct_binding: true,
        token_exposure: true,
        bootstrap_import: true,
        outbox_fanout: true,
        sync_outbound: true,
        sync_inbound: true,
        sync_reconcile: true,
      },
      token_contract: {
        enabled: true,
        qualifier_kind: 'none',
        qualifier_required: false,
        qualifier_options: [],
      },
      bootstrap_contract: { enabled: true, dependency_order: 40 },
      runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
    },
  ],
}

const MASTER_DATA_PARTIES = [
  {
    id: 'party-1',
    tenant_id: TENANT_ID,
    canonical_id: 'party-org',
    name: 'Org One',
    full_name: 'Org One LLC',
    inn: '730000000001',
    kpp: '123456789',
    is_our_organization: true,
    is_counterparty: true,
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
]

const MASTER_DATA_ITEMS = [
  {
    id: 'item-1',
    tenant_id: TENANT_ID,
    canonical_id: 'item-1',
    name: 'Service package',
    sku: 'svc-1',
    unit: 'pcs',
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
]

const MASTER_DATA_CONTRACTS = [
  {
    id: 'contract-1',
    tenant_id: TENANT_ID,
    canonical_id: 'contract-1',
    name: 'Main service contract',
    owner_counterparty_id: 'party-1',
    owner_counterparty_canonical_id: 'party-org',
    number: 'C-001',
    date: '2026-01-01',
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
]

const MASTER_DATA_TAX_PROFILES = [
  {
    id: 'tax-profile-1',
    tenant_id: TENANT_ID,
    canonical_id: 'tax-profile-1',
    vat_rate: 20,
    vat_included: true,
    vat_code: 'VAT20',
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
]

const MASTER_DATA_GL_ACCOUNTS = [
  {
    id: 'gl-account-1',
    tenant_id: TENANT_ID,
    canonical_id: 'gl-account-001',
    code: '10.01',
    name: 'Main Account',
    chart_identity: 'ChartOfAccounts_Main',
    config_name: 'Accounting Enterprise',
    config_version: '3.0.1',
    compatibility_class: 'current',
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
]

const POOL_WITH_ATTACHMENT = {
  id: 'pool-1',
  code: 'pool-main',
  name: 'Main Pool',
  description: 'Workflow-centric pool',
  is_active: true,
  metadata: {},
  updated_at: NOW,
  workflow_bindings: [
    {
      binding_id: 'binding-top-down',
      pool_id: 'pool-1',
      revision: 3,
      status: 'active',
      contract_version: 'binding_profile.v1',
      binding_profile_id: 'bp-services',
      binding_profile_revision_id: 'bp-rev-services-r2',
      binding_profile_revision_number: 2,
      effective_from: NOW,
      effective_to: null,
      selector: {
        direction: 'top_down',
        mode: 'safe',
        tags: [],
      },
      workflow: {
        workflow_definition_key: 'services-publication',
        workflow_revision_id: 'wf-services-r2',
        workflow_revision: 4,
        workflow_name: 'services_publication',
      },
      decisions: [],
      parameters: {},
      role_mapping: {},
      resolved_profile: {
        binding_profile_id: 'bp-services',
        code: 'services-publication',
        name: 'Services Publication',
        status: 'active',
        binding_profile_revision_id: 'bp-rev-services-r2',
        binding_profile_revision_number: 2,
        workflow: {
          workflow_definition_key: 'services-publication',
          workflow_revision_id: 'wf-services-r2',
          workflow_revision: 4,
          workflow_name: 'services_publication',
        },
        decisions: [],
        parameters: {},
        role_mapping: {},
      },
      profile_lifecycle_warning: null,
    },
  ],
}

const POOL_RUN = {
  id: 'run-1',
  tenant_id: TENANT_ID,
  pool_id: POOL_WITH_ATTACHMENT.id,
  schema_template_id: null,
  mode: 'safe',
  direction: 'top_down',
  status: 'validated',
  status_reason: 'awaiting_approval',
  period_start: '2026-01-01',
  period_end: null,
  run_input: {
    starting_amount: '100.00',
  },
  input_contract_version: 'run_input_v1',
  idempotency_key: 'idem-run-1',
  workflow_execution_id: 'workflow-run-1',
  workflow_status: 'pending',
  root_operation_id: 'operation-root-1',
  execution_consumer: 'pools',
  lane: 'workflows',
  approval_state: 'awaiting_approval',
  publication_step_state: 'not_enqueued',
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
  verification_status: 'not_verified',
  verification_summary: null,
  terminal_reason: null,
  execution_backend: 'workflow_core',
  workflow_template_name: 'pool-template-v1',
  seed: null,
  validation_summary: { rows: 3 },
  publication_summary: { total_targets: 1 },
  diagnostics: [{ step: 'prepare_input', status: 'ok' }],
  last_error: '',
  created_at: NOW,
  updated_at: NOW,
  validated_at: NOW,
  publication_confirmed_at: null,
  publishing_started_at: null,
  completed_at: null,
  provenance: {
    workflow_run_id: 'workflow-run-1',
    workflow_status: 'pending',
    execution_backend: 'workflow_core',
    root_operation_id: 'operation-root-1',
    execution_consumer: 'pools',
    lane: 'workflows',
    retry_chain: [
      {
        workflow_run_id: 'workflow-run-1',
        parent_workflow_run_id: null,
        attempt_number: 1,
        attempt_kind: 'initial',
        status: 'pending',
      },
    ],
  },
  workflow_binding: POOL_WITH_ATTACHMENT.workflow_bindings[0],
  runtime_projection: {
    version: 'pool_runtime_projection.v1',
    run_id: 'run-1',
    pool_id: POOL_WITH_ATTACHMENT.id,
    direction: 'top_down',
    mode: 'safe',
    workflow_definition: {
      plan_key: 'plan-services-v4',
      template_version: 'workflow-template:4',
      workflow_template_name: 'compiled-services-publication',
      workflow_type: 'sequential',
    },
    workflow_binding: {
      binding_mode: 'pool_workflow_binding',
      binding_id: 'binding-top-down',
      binding_profile_id: 'bp-services',
      pool_id: POOL_WITH_ATTACHMENT.id,
      binding_profile_revision_id: 'bp-rev-services-r2',
      binding_profile_revision_number: 2,
      attachment_revision: 3,
      workflow_definition_key: 'services-publication',
      workflow_revision_id: 'wf-services-r2',
      workflow_revision: 4,
      workflow_name: 'services_publication',
      decision_refs: [
        {
          decision_table_id: 'services-publication-policy',
          decision_key: 'document_policy',
          slot_key: 'document_policy',
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
      policy_refs: [
        {
          slot_key: 'document_policy',
          edge_ref: {
            parent_node_id: 'node-root',
            child_node_id: 'node-child',
          },
          policy_version: 'document_policy.v1',
          source: 'decision_tables',
        },
      ],
      compiled_document_policy_slots: {
        document_policy: {
          decision_table_id: 'services-publication-policy',
          decision_revision: 2,
          document_policy_source: 'decision_tables',
          document_policy: {
            version: 'document_policy.v1',
            targets: 1,
          },
        },
      },
      slot_coverage_summary: {
        total_edges: 1,
        counts: {
          resolved: 1,
          missing_selector: 0,
          missing_slot: 0,
          ambiguous_slot: 0,
          ambiguous_context: 0,
          unavailable_context: 0,
        },
        items: [
          {
            edge_id: 'edge-1',
            edge_label: 'Root Org -> Child Org',
            slot_key: 'document_policy',
            coverage: {
              code: null,
              status: 'resolved',
              label: 'Resolved',
              detail: 'document_policy -> services-publication-policy r2',
            },
          },
        ],
      },
      policy_refs_count: 1,
      targets_count: 1,
    },
    artifacts: {
      document_plan_artifact_version: 'document_plan_artifact.v1',
      topology_version_ref: 'topology:v1',
      distribution_artifact_ref: { id: 'distribution-artifact:v1' },
    },
    compile_summary: {
      steps_count: 4,
      atomic_publication_steps_count: 1,
      compiled_targets_count: 1,
    },
  },
}

const POOL_RUN_REPORT = {
  run: POOL_RUN,
  publication_attempts: [
    {
      id: 'publication-attempt-1',
      run_id: POOL_RUN.id,
      target_database_id: DATABASE_ID,
      attempt_number: 1,
      attempt_timestamp: NOW,
      status: 'failed',
      entity_name: 'Document_Sales',
      documents_count: 1,
      publication_identity_strategy: 'guid',
      external_document_identity: 'sale-1',
      posted: false,
      domain_error_code: 'network',
      domain_error_message: 'temporary error',
      http_error: null,
      transport_error: null,
    },
  ],
  validation_summary: { rows: 3 },
  publication_summary: { total_targets: 1, failed_targets: 1 },
  diagnostics: [{ step: 'distribution_calculation', status: 'ok' }],
  attempts_by_status: { failed: 1 },
}

const POOL_FACTUAL_WORKSPACE = {
  pool_id: POOL_WITH_ATTACHMENT.id,
  summary: {
    quarter: '2026Q1',
    quarter_start: '2026-01-01',
    quarter_end: '2026-03-31',
    amount_with_vat: '120.00',
    amount_without_vat: '100.00',
    vat_amount: '20.00',
    incoming_amount: '170.00',
    outgoing_amount: '115.00',
    open_balance: '55.00',
    pending_review_total: 1,
    attention_required_total: 1,
    backlog_total: 2,
    freshness_state: 'stale',
    source_availability: 'available',
    source_availability_detail: '',
    last_synced_at: NOW,
    sync_status: 'success',
    checkpoints_pending: 0,
    checkpoints_running: 0,
    checkpoints_failed: 0,
    checkpoints_ready: 1,
    activity: 'active',
    polling_tier: 'active',
    poll_interval_seconds: 120,
    freshness_target_seconds: 120,
    scope_fingerprint: '',
    scope_contract_version: '',
    gl_account_set_revision_id: '',
    scope_contract: null,
    settlement_total: 2,
    checkpoint_total: 1,
  },
  checkpoints: [
    {
      checkpoint_id: 'checkpoint-ready-1',
      database_id: DATABASE_ID,
      database_name: DATABASE_RECORD.name,
      workflow_status: '',
      freshness_state: 'stale',
      last_synced_at: NOW,
      last_error_code: '',
      last_error: '',
      execution_id: null,
      operation_id: null,
      activity: 'active',
      polling_tier: 'active',
      poll_interval_seconds: 120,
      freshness_target_seconds: 120,
    },
  ],
  settlements: [
    {
      id: 'batch-receipt-1',
      tenant_id: TENANT_ID,
      pool_id: POOL_WITH_ATTACHMENT.id,
      batch_kind: 'receipt',
      source_type: 'manual',
      schema_template_id: null,
      start_organization_id: 'organization-main',
      run_id: POOL_RUN.id,
      workflow_execution_id: null,
      operation_id: null,
      workflow_status: '',
      period_start: '2026-01-01',
      period_end: '2026-03-31',
      source_reference: 'receipt-q1',
      raw_payload_ref: '',
      content_hash: 'receipt-hash-1',
      source_metadata: {},
      normalization_summary: {},
      publication_summary: {},
      last_error_code: '',
      last_error: '',
      created_by_id: null,
      created_at: NOW,
      updated_at: NOW,
      settlement: {
        id: 'settlement-receipt-1',
        tenant_id: TENANT_ID,
        batch_id: 'batch-receipt-1',
        status: 'partially_closed',
        incoming_amount: '120.00',
        outgoing_amount: '80.00',
        open_balance: '40.00',
        summary: {},
        freshness_at: NOW,
        created_at: NOW,
        updated_at: NOW,
      },
    },
    {
      id: 'batch-sale-1',
      tenant_id: TENANT_ID,
      pool_id: POOL_WITH_ATTACHMENT.id,
      batch_kind: 'sale',
      source_type: 'manual',
      schema_template_id: null,
      start_organization_id: null,
      run_id: null,
      workflow_execution_id: 'workflow-sale-1',
      operation_id: 'operation-sale-1',
      workflow_status: 'completed',
      period_start: '2026-01-01',
      period_end: '2026-03-31',
      source_reference: 'sale-q1',
      raw_payload_ref: '',
      content_hash: 'sale-hash-1',
      source_metadata: {},
      normalization_summary: {},
      publication_summary: {},
      last_error_code: '',
      last_error: '',
      created_by_id: null,
      created_at: NOW,
      updated_at: NOW,
      settlement: {
        id: 'settlement-sale-1',
        tenant_id: TENANT_ID,
        batch_id: 'batch-sale-1',
        status: 'attention_required',
        incoming_amount: '50.00',
        outgoing_amount: '35.00',
        open_balance: '15.00',
        summary: {},
        freshness_at: NOW,
        created_at: NOW,
        updated_at: NOW,
      },
    },
  ],
  edge_balances: [
    {
      id: 'edge-balance-1',
      pool_id: POOL_WITH_ATTACHMENT.id,
      batch_id: 'batch-receipt-1',
      organization_id: 'organization-leaf-1',
      organization_name: 'Leaf Alpha',
      edge_id: 'edge-alpha-1',
      parent_node_id: 'node-root',
      child_node_id: 'node-child',
      quarter: '2026Q1',
      quarter_start: '2026-01-01',
      quarter_end: '2026-03-31',
      amount_with_vat: '120.00',
      amount_without_vat: '100.00',
      vat_amount: '20.00',
      incoming_amount: '120.00',
      outgoing_amount: '80.00',
      open_balance: '40.00',
      freshness_at: NOW,
      metadata: {},
    },
  ],
  review_queue: {
    contract_version: 'pool_factual_review_queue.v1',
    subsystem: 'reconcile_review',
    summary: {
      pending_total: 1,
      unattributed_total: 1,
      late_correction_total: 0,
      attention_required_total: 1,
    },
    items: [
      {
        id: 'unattributed-pool-main',
        pool_id: POOL_WITH_ATTACHMENT.id,
        batch_id: 'batch-receipt-1',
        organization_id: 'organization-leaf-1',
        edge_id: 'edge-alpha-1',
        reason: 'unattributed',
        status: 'pending',
        quarter: '2026Q1',
        source_document_ref: "Document_РеализацияТоваровУслуг(guid'pool-main-sale')",
        allowed_actions: ['attribute', 'resolve_without_change'],
        attention_required: true,
        resolved_at: null,
      },
    ],
  },
}

const POOL_FACTUAL_OVERVIEW = {
  items: [
    {
      pool_id: POOL_WITH_ATTACHMENT.id,
      pool_code: POOL_WITH_ATTACHMENT.code,
      pool_name: POOL_WITH_ATTACHMENT.name,
      pool_description: POOL_WITH_ATTACHMENT.description,
      pool_is_active: true,
      summary: POOL_FACTUAL_WORKSPACE.summary,
    },
  ],
  count: 1,
}

const WORKFLOW_EXECUTION_DETAIL = {
  id: POOL_RUN.workflow_execution_id,
  workflow_template: WORKFLOW.id,
  template_name: WORKFLOW.name,
  template_version: WORKFLOW.version_number,
  status: 'pending',
  input_context: {
    pool_id: POOL_RUN.pool_id,
  },
  final_result: null,
  current_node_id: '',
  completed_nodes: {},
  failed_nodes: {},
  node_statuses: {},
  progress_percent: '0.00',
  error_message: '',
  error_node_id: '',
  trace_id: '',
  started_at: NOW,
  completed_at: null,
  duration: 0,
  step_results: [],
}

const WORKFLOW_TEMPLATE_DETAIL = {
  id: WORKFLOW.id,
  name: WORKFLOW.name,
  description: WORKFLOW.description,
  workflow_type: 'sequential',
  category: WORKFLOW.category,
  dag_structure: {
    nodes: [
      {
        id: 'start',
        name: 'Start',
        type: 'operation',
        template_id: 'noop',
        config: {
          timeout_seconds: 300,
          max_retries: 0,
        },
      },
    ],
    edges: [],
  },
  config: {
    timeout_seconds: 300,
    max_retries: 0,
  },
  is_valid: true,
  is_active: true,
  is_system_managed: false,
  management_mode: 'user_authored',
  visibility_surface: 'workflow_library',
  read_only_reason: null,
  version_number: WORKFLOW.version_number,
  parent_version: null,
  parent_version_name: null,
  created_by: null,
  created_by_username: 'analyst',
  execution_count: 0,
  created_at: NOW,
  updated_at: NOW,
}

const WORKFLOW_OPERATION = {
  id: 'workflow-operation-1',
  name: 'workflow root execute',
  description: '',
  operation_type: 'query',
  target_entity: 'Workflow',
  status: 'processing',
  progress: 50,
  total_tasks: 2,
  completed_tasks: 1,
  failed_tasks: 0,
  payload: {},
  config: {},
  task_id: null,
  started_at: NOW,
  completed_at: null,
  duration_seconds: 1,
  success_rate: 50,
  created_by: 'admin',
  metadata: {
    workflow_execution_id: POOL_RUN.workflow_execution_id,
    node_id: 'services-node-1',
    root_operation_id: 'workflow-operation-1',
    execution_consumer: 'workflows',
    lane: 'workflows',
    trace_id: 'trace-services-1',
  },
  created_at: NOW,
  updated_at: NOW,
  database_names: ['db-services'],
  tasks: [],
}

const MANUAL_OPERATION = {
  id: 'manual-operation-1',
  name: 'manual lock scheduled jobs',
  description: '',
  operation_type: 'lock_scheduled_jobs',
  target_entity: 'Infobase',
  status: 'completed',
  progress: 100,
  total_tasks: 1,
  completed_tasks: 1,
  failed_tasks: 0,
  payload: {},
  config: {},
  task_id: null,
  started_at: NOW,
  completed_at: NOW,
  duration_seconds: 1,
  success_rate: 100,
  created_by: 'admin',
  metadata: {},
  created_at: NOW,
  updated_at: NOW,
  database_names: ['db-services'],
  tasks: [],
}

const ZERO_TASK_OPERATION = {
  id: 'zero-task-operation-1',
  name: 'workflow telemetry pending',
  description: '',
  operation_type: 'query',
  target_entity: 'Workflow',
  status: 'completed',
  progress: 100,
  total_tasks: 0,
  completed_tasks: 0,
  failed_tasks: 0,
  payload: {},
  config: {},
  task_id: null,
  started_at: NOW,
  completed_at: NOW,
  duration_seconds: 1,
  success_rate: 100,
  created_by: 'admin',
  metadata: {
    workflow_execution_id: POOL_RUN.workflow_execution_id,
  },
  created_at: NOW,
  updated_at: NOW,
  database_names: ['db-services'],
  tasks: [],
}

const OPERATIONS = [WORKFLOW_OPERATION, MANUAL_OPERATION, ZERO_TASK_OPERATION]

const OPERATION_DETAILS: Record<string, {
  operation: typeof WORKFLOW_OPERATION
  execution_plan: Record<string, unknown> | null
  bindings: Array<Record<string, unknown>>
  tasks: Array<Record<string, unknown>>
  progress: Record<string, number>
}> = {
  [WORKFLOW_OPERATION.id]: {
    operation: {
      ...WORKFLOW_OPERATION,
      tasks: [
        {
          id: 'task-workflow-1',
          database: DATABASE_ID,
          database_name: 'db-services',
          status: 'processing',
          result: {},
          error_message: '',
          error_code: '',
          retry_count: 0,
          max_retries: 3,
          worker_id: 'worker-1',
          started_at: NOW,
          completed_at: null,
          duration_seconds: 1,
          created_at: NOW,
          updated_at: NOW,
        },
      ],
    },
    execution_plan: {
      kind: 'workflow',
      workflow_id: WORKFLOW.id,
      input_context_masked: {
        workflow_execution_id: POOL_RUN.workflow_execution_id,
      },
    },
    bindings: [
      {
        target_ref: 'workflow_execution_id',
        source_ref: 'request.workflow_execution_id',
        resolve_at: 'api',
        sensitive: false,
        status: 'applied',
      },
    ],
    tasks: [
      {
        id: 'task-workflow-1',
        database: DATABASE_ID,
        database_name: 'db-services',
        status: 'processing',
        result: {},
        error_message: '',
        error_code: '',
        retry_count: 0,
        max_retries: 3,
        worker_id: 'worker-1',
        started_at: NOW,
        completed_at: null,
        duration_seconds: 1,
        created_at: NOW,
        updated_at: NOW,
      },
    ],
    progress: {
      total: 2,
      completed: 1,
      failed: 0,
      pending: 0,
      processing: 1,
      percent: 50,
    },
  },
  [MANUAL_OPERATION.id]: {
    operation: {
      ...MANUAL_OPERATION,
      tasks: [
        {
          id: 'task-manual-1',
          database: DATABASE_ID,
          database_name: 'db-services',
          status: 'completed',
          result: {},
          error_message: '',
          error_code: '',
          retry_count: 0,
          max_retries: 3,
          worker_id: 'worker-1',
          started_at: NOW,
          completed_at: NOW,
          duration_seconds: 1,
          created_at: NOW,
          updated_at: NOW,
        },
      ],
    },
    execution_plan: null,
    bindings: [],
    tasks: [
      {
        id: 'task-manual-1',
        database: DATABASE_ID,
        database_name: 'db-services',
        status: 'completed',
        result: {},
        error_message: '',
        error_code: '',
        retry_count: 0,
        max_retries: 3,
        worker_id: 'worker-1',
        started_at: NOW,
        completed_at: NOW,
        duration_seconds: 1,
        created_at: NOW,
        updated_at: NOW,
      },
    ],
    progress: {
      total: 1,
      completed: 1,
      failed: 0,
      pending: 0,
      processing: 0,
      percent: 100,
    },
  },
  [ZERO_TASK_OPERATION.id]: {
    operation: {
      ...ZERO_TASK_OPERATION,
      tasks: [],
    },
    execution_plan: {
      kind: 'workflow',
      workflow_id: WORKFLOW.id,
    },
    bindings: [],
    tasks: [],
    progress: {
      total: 0,
      completed: 0,
      failed: 0,
      pending: 0,
      processing: 0,
      percent: 100,
    },
  },
}

const OPERATION_TIMELINES: Record<string, {
  operation_id: string
  timeline: Array<Record<string, unknown>>
  total_events: number
  duration_ms: number | null
}> = {
  [WORKFLOW_OPERATION.id]: {
    operation_id: WORKFLOW_OPERATION.id,
    timeline: [
      {
        timestamp: 1000,
        event: 'orchestrator.created',
        service: 'orchestrator',
        workflow_execution_id: POOL_RUN.workflow_execution_id,
        node_id: 'services-node-1',
        root_operation_id: WORKFLOW_OPERATION.id,
        execution_consumer: 'workflows',
        lane: 'workflows',
        metadata: {},
      },
      {
        timestamp: 1800,
        event: 'worker.command.completed',
        service: 'worker',
        workflow_execution_id: POOL_RUN.workflow_execution_id,
        node_id: 'services-node-1',
        root_operation_id: WORKFLOW_OPERATION.id,
        execution_consumer: 'workflows',
        lane: 'workflows',
        metadata: {},
      },
    ],
    total_events: 2,
    duration_ms: 800,
  },
  [MANUAL_OPERATION.id]: {
    operation_id: MANUAL_OPERATION.id,
    timeline: [
      {
        timestamp: 1000,
        event: 'orchestrator.created',
        service: 'orchestrator',
        root_operation_id: MANUAL_OPERATION.id,
        execution_consumer: 'operations',
        lane: 'operations',
        metadata: {},
      },
      {
        timestamp: 1300,
        event: 'worker.command.completed',
        service: 'worker',
        root_operation_id: MANUAL_OPERATION.id,
        execution_consumer: 'operations',
        lane: 'operations',
        metadata: {},
      },
    ],
    total_events: 2,
    duration_ms: 300,
  },
}

const ADMIN_USER = {
  id: 101,
  username: 'admin',
  email: 'admin@example.com',
  first_name: 'Admin',
  last_name: 'Operator',
  is_staff: true,
  is_active: true,
  last_login: NOW,
  date_joined: NOW,
}

const USERS_RESPONSE = {
  users: [ADMIN_USER],
  count: 1,
  total: 1,
}

const DLQ_MESSAGE = {
  dlq_message_id: 'dlq-message-1',
  operation_id: WORKFLOW_OPERATION.id,
  original_message_id: 'original-message-1',
  worker_id: 'worker-1',
  failed_at: NOW,
  error_code: 'network_error',
  error_message: 'Temporary failure while executing operation',
}

const DLQ_LIST_RESPONSE = {
  messages: [DLQ_MESSAGE],
  count: 1,
  total: 1,
}

const ACTIVE_ARTIFACT = {
  id: 'artifact-services-config',
  name: 'services-config',
  kind: 'config_xml',
  is_versioned: true,
  tags: ['services'],
  is_deleted: false,
  deleted_at: null,
  purge_state: 'none',
  purge_after: null,
  purge_blocked_until: null,
  purge_blockers: [],
  created_at: NOW,
}

const DELETED_ARTIFACT = {
  ...ACTIVE_ARTIFACT,
  id: 'artifact-services-config-deleted',
  name: 'services-config-deleted',
  is_deleted: true,
  deleted_at: NOW,
}

const ARTIFACT_VERSIONS_RESPONSE = {
  versions: [
    {
      id: 'artifact-version-1',
      version: 'v1',
      filename: 'services-config.xml',
      storage_key: 'artifacts/services-config/v1.xml',
      size: 128,
      checksum: 'a'.repeat(64),
      content_type: 'application/xml',
      metadata: {},
      created_at: NOW,
    },
  ],
  count: 1,
}

const ARTIFACT_ALIASES_RESPONSE = {
  aliases: [
    {
      id: 'artifact-alias-stable',
      alias: 'stable',
      version: 'v1',
      version_id: 'artifact-version-1',
      updated_at: NOW,
    },
  ],
  count: 1,
}

const EXTENSIONS_OVERVIEW_RESPONSE = {
  extensions: [
    {
      name: 'ServicePublisher',
      purpose: 'Publishes service-related extensions across accessible databases.',
      flags: {
        active: {
          policy: true,
          observed: { state: 'on', true_count: 1, false_count: 0, unknown_count: 0 },
          drift_count: 0,
          unknown_drift_count: 0,
        },
        safe_mode: {
          policy: false,
          observed: { state: 'off', true_count: 0, false_count: 1, unknown_count: 0 },
          drift_count: 0,
          unknown_drift_count: 0,
        },
        unsafe_action_protection: {
          policy: true,
          observed: { state: 'on', true_count: 1, false_count: 0, unknown_count: 0 },
          drift_count: 0,
          unknown_drift_count: 0,
        },
      },
      installed_count: 1,
      active_count: 1,
      inactive_count: 0,
      missing_count: 0,
      unknown_count: 0,
      versions: [{ version: '1.0.0', count: 1 }],
      latest_snapshot_at: NOW,
    },
  ],
  count: 1,
  total: 1,
  total_databases: 1,
}

const EXTENSIONS_DATABASES_RESPONSE = {
  databases: [
    {
      database_id: DATABASE_ID,
      database_name: DATABASE_RECORD.name,
      cluster_id: 'cluster-1',
      cluster_name: 'Main Cluster',
      status: 'active',
      version: '1.0.0',
      snapshot_updated_at: NOW,
      flags: {
        active: true,
        safe_mode: false,
        unsafe_action_protection: true,
      },
    },
  ],
  count: 1,
  total: 1,
}

const EXTENSIONS_MANUAL_BINDINGS_RESPONSE = {
  bindings: [
    {
      manual_operation: 'extensions.set_flags',
      template_id: 'tpl-sync-extension',
      updated_at: NOW,
      updated_by: 'analyst',
    },
  ],
}

const RUNTIME_SETTINGS_RESPONSE = {
  settings: [
    {
      key: 'runtime.concurrency.max_workers',
      value: 8,
      source: 'runtime',
      value_type: 'int',
      description: 'Maximum number of concurrent workers.',
      min_value: 1,
      max_value: 32,
      default: 4,
    },
    {
      key: 'runtime.feature_flags.enable_fast_path',
      value: true,
      source: 'runtime',
      value_type: 'bool',
      description: 'Enables the fast-path runtime optimization.',
      min_value: null,
      max_value: null,
      default: false,
    },
    {
      key: 'observability.timeline.polling_interval_seconds',
      value: 15,
      source: 'runtime',
      value_type: 'int',
      description: 'Polling interval for timeline reads.',
      min_value: 5,
      max_value: 60,
      default: 10,
    },
    {
      key: 'observability.timeline.enable_projection_refresh',
      value: true,
      source: 'runtime',
      value_type: 'bool',
      description: 'Enables projection refresh for timeline consumers.',
      min_value: null,
      max_value: null,
      default: true,
    },
  ],
}

const RUNTIME_CONTROL_CATALOG_RESPONSE = {
  runtimes: [
    {
      runtime_id: 'local:localhost:orchestrator',
      runtime_name: 'orchestrator',
      display_name: 'orchestrator',
      provider: { key: 'local_scripts', host: 'localhost' },
      observed_state: {
        status: 'degraded',
        process_status: 'up(pid=4201)',
        http_status: 'up(http=200)',
        raw_probe: 'orchestrator proc=up(pid=4201) http=up(http=200)',
        command_status: 'success',
      },
      type: 'django',
      stack: 'python',
      entrypoint: './debug/restart-runtime.sh orchestrator',
      health: 'http://orchestrator.local/health',
      supported_actions: ['probe', 'restart', 'tail_logs'],
      logs_available: true,
      scheduler_supported: false,
    },
    {
      runtime_id: 'local:localhost:worker-workflows',
      runtime_name: 'worker-workflows',
      display_name: 'worker-workflows',
      provider: { key: 'local_scripts', host: 'localhost' },
      observed_state: {
        status: 'online',
        process_status: 'up(pid=4310)',
        http_status: 'up(http=200)',
        raw_probe: 'worker-workflows proc=up(pid=4310) http=up(http=200)',
        command_status: 'success',
      },
      type: 'go-service',
      stack: 'go',
      entrypoint: './debug/restart-runtime.sh worker-workflows',
      health: 'http://worker-workflows.local/health',
      supported_actions: ['probe', 'restart', 'tail_logs', 'trigger_now'],
      logs_available: true,
      scheduler_supported: true,
      desired_state: {
        scheduler_enabled: true,
        jobs: [
          {
            job_name: 'pool_factual_active_sync',
            runtime_id: 'local:localhost:worker-workflows',
            runtime_name: 'worker-workflows',
            display_name: 'Pool factual active sync',
            description: 'Scans active pools and refreshes factual checkpoint windows for the current quarter.',
            enabled: true,
            schedule: '@every 120s',
            schedule_apply_mode: 'controlled_restart',
            enablement_apply_mode: 'live',
            latest_run_id: 4101,
            latest_run_status: 'success',
            latest_run_started_at: NOW,
          },
          {
            job_name: 'pool_factual_closed_quarter_reconcile',
            runtime_id: 'local:localhost:worker-workflows',
            runtime_name: 'worker-workflows',
            display_name: 'Pool factual closed-quarter reconcile',
            description: 'Creates and advances reconcile checkpoints for closed-quarter factual scopes.',
            enabled: true,
            schedule: '0 2 * * *',
            schedule_apply_mode: 'controlled_restart',
            enablement_apply_mode: 'live',
            latest_run_id: 4102,
            latest_run_status: 'success',
            latest_run_started_at: NOW,
          },
        ],
      },
    },
  ],
}

const RUNTIME_CONTROL_DETAILS = {
  'local:localhost:orchestrator': {
    ...RUNTIME_CONTROL_CATALOG_RESPONSE.runtimes[0],
    logs_excerpt: {
      available: true,
      excerpt: 'orchestrator\nqueue_lag=12\nsecret=[REDACTED]',
      path: '/logs/orchestrator.log',
      updated_at: NOW,
    },
    recent_actions: [
      {
        id: 'runtime-action-orchestrator-1',
        provider: 'local_scripts',
        runtime_id: 'local:localhost:orchestrator',
        runtime_name: 'orchestrator',
        action_type: 'probe',
        target_job_name: '',
        status: 'success',
        reason: '',
        requested_by_username: 'ui-platform',
        requested_at: NOW,
        started_at: NOW,
        finished_at: NOW,
        result_excerpt: 'orchestrator proc=up(pid=4201) http=up(http=200)',
        result_payload: { command_status: 'success' },
        error_message: '',
        scheduler_job_run_id: null,
      },
    ],
  },
  'local:localhost:worker-workflows': {
    ...RUNTIME_CONTROL_CATALOG_RESPONSE.runtimes[1],
    logs_excerpt: {
      available: true,
      excerpt: 'worker-workflows\nlast_tick=2026-03-10T12:00:00Z',
      path: '/logs/worker-workflows.log',
      updated_at: NOW,
    },
    recent_actions: [],
  },
}

const COMMAND_SCHEMAS_EDITOR_VIEW = {
  driver: 'ibcmd',
  etag: 'command-schemas-etag-1',
  base: {
    approved_version: 'approved-v1',
    approved_version_id: 'approved-v1-id',
    latest_version: 'latest-v1',
    latest_version_id: 'latest-v1-id',
  },
  overrides: {
    active_version: 'overrides-v1',
    active_version_id: 'overrides-v1-id',
  },
  catalogs: {
    base: {
      catalog_version: 2,
      driver: 'ibcmd',
      commands_by_id: {
        'ibcmd.publish': {
          label: 'Publish infobase',
          description: 'Publishes the selected infobase.',
          argv: ['ibcmd', 'publish'],
          scope: 'per_database',
          risk_level: 'safe',
          params_by_name: {
            mode: {
              kind: 'flag',
              flag: '--mode',
              required: false,
              expects_value: true,
              label: 'Mode',
              description: 'Publication mode',
              value_type: 'string',
              enum: ['safe', 'force'],
            },
          },
        },
      },
    },
    overrides: {
      catalog_version: 2,
      driver: 'ibcmd',
      overrides: {
        driver_schema: {},
        commands_by_id: {},
      },
    },
    effective: {
      base_version: 'approved-v1',
      base_version_id: 'approved-v1-id',
      base_alias: 'approved',
      overrides_version: 'overrides-v1',
      overrides_version_id: 'overrides-v1-id',
      source: 'merged',
      catalog: {
        catalog_version: 2,
        driver: 'ibcmd',
        commands_by_id: {
          'ibcmd.publish': {
            label: 'Publish infobase',
            description: 'Publishes the selected infobase.',
            argv: ['ibcmd', 'publish'],
            scope: 'per_database',
            risk_level: 'safe',
            params_by_name: {
              mode: {
                kind: 'flag',
                flag: '--mode',
                required: false,
                expects_value: true,
                label: 'Mode',
                description: 'Publication mode',
                value_type: 'string',
                enum: ['safe', 'force'],
              },
            },
          },
        },
      },
    },
  },
}

const RBAC_AUDIT_RESPONSE = {
  items: [
    {
      id: 1,
      created_at: NOW,
      actor_username: 'admin',
      actor_id: 1,
      action: 'role.updated',
      outcome: 'success',
      target_type: 'role',
      target_id: 'services_operator',
      metadata: { reason: 'Initial bootstrap' },
      error_message: '',
    },
  ],
  count: 1,
  total: 1,
}

async function fulfillJson(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
    headers: { 'cache-control': 'no-store' },
  })
}

type RequestCounts = {
  bootstrap: number
  meReads: number
  myTenantsReads: number
  streamTickets: number
  usersList: number
  usersDetail: number
  dlqList: number
  dlqDetail: number
  artifactsList: number
  artifactDetail: number
  extensionsOverview: number
  extensionsOverviewDatabases: number
  extensionsManualBindings: number
  runtimeSettingsReads: number
  streamMuxStatusReads: number
  commandSchemasEditorReads: number
  clusterLists: number
  clusterDetails: number
  databaseLists: number
  systemHealthReads: number
  runtimeControlCatalogReads: number
  runtimeControlRuntimeReads: number
  runtimeControlActionWrites: number
  runtimeControlDesiredStateWrites: number
  serviceHistoryReads: number
  metadataManagementReads: number
  decisionsScoped: number
  decisionsUnscoped: number
  bindingProfilesList: number
  bindingProfileDetails: number
  organizationPools: number
  poolOrganizations: number
  poolOrganizationDetails: number
  poolGraphs: number
  poolTopologySnapshots: number
  poolRuns: number
  poolRunReports: number
  operationsList: number
  operationDetails: number
}

function createRequestCounts(): RequestCounts {
  return {
    bootstrap: 0,
    meReads: 0,
    myTenantsReads: 0,
    streamTickets: 0,
    usersList: 0,
    usersDetail: 0,
    dlqList: 0,
    dlqDetail: 0,
    artifactsList: 0,
    artifactDetail: 0,
    extensionsOverview: 0,
    extensionsOverviewDatabases: 0,
    extensionsManualBindings: 0,
    runtimeSettingsReads: 0,
    streamMuxStatusReads: 0,
    commandSchemasEditorReads: 0,
    clusterLists: 0,
    clusterDetails: 0,
    databaseLists: 0,
    systemHealthReads: 0,
    runtimeControlCatalogReads: 0,
    runtimeControlRuntimeReads: 0,
    runtimeControlActionWrites: 0,
    runtimeControlDesiredStateWrites: 0,
    serviceHistoryReads: 0,
    metadataManagementReads: 0,
    decisionsScoped: 0,
    decisionsUnscoped: 0,
    bindingProfilesList: 0,
    bindingProfileDetails: 0,
    organizationPools: 0,
    poolOrganizations: 0,
    poolOrganizationDetails: 0,
    poolGraphs: 0,
    poolTopologySnapshots: 0,
    poolRuns: 0,
    poolRunReports: 0,
    operationsList: 0,
    operationDetails: 0,
  }
}

async function setupAuth(page: Page, options?: { localeOverride?: 'ru' | 'en' | null }) {
  await page.addInitScript(({ tenantId, serviceMeshMetricsMessage, localeOverride }) => {
    window.__CC1C_ENV__ = {
      VITE_BASE_HOST: '127.0.0.1',
      VITE_API_URL: 'http://127.0.0.1:15173',
      VITE_WS_HOST: '127.0.0.1:15173',
    }

    const NativeWebSocket = window.WebSocket
    class QuietServiceMeshWebSocket implements Partial<WebSocket> {
      static readonly CONNECTING = NativeWebSocket.CONNECTING
      static readonly OPEN = NativeWebSocket.OPEN
      static readonly CLOSING = NativeWebSocket.CLOSING
      static readonly CLOSED = NativeWebSocket.CLOSED

      readonly CONNECTING = NativeWebSocket.CONNECTING
      readonly OPEN = NativeWebSocket.OPEN
      readonly CLOSING = NativeWebSocket.CLOSING
      readonly CLOSED = NativeWebSocket.CLOSED

      readonly url: string
      readonly protocol = ''
      readonly extensions = ''
      binaryType: BinaryType = 'blob'
      bufferedAmount = 0
      readyState = NativeWebSocket.CONNECTING
      onopen: ((this: WebSocket, ev: Event) => unknown) | null = null
      onclose: ((this: WebSocket, ev: CloseEvent) => unknown) | null = null
      onerror: ((this: WebSocket, ev: Event) => unknown) | null = null
      onmessage: ((this: WebSocket, ev: MessageEvent) => unknown) | null = null

      constructor(url: string | URL) {
        this.url = typeof url === 'string' ? url : url.toString()
        queueMicrotask(() => {
          this.readyState = NativeWebSocket.OPEN
          this.onopen?.call(this as WebSocket, new Event('open'))
          queueMicrotask(() => {
            this.onmessage?.call(
              this as WebSocket,
              new MessageEvent('message', {
                data: JSON.stringify(serviceMeshMetricsMessage),
              }),
            )
          })
        })
      }

      addEventListener() {}
      removeEventListener() {}
      dispatchEvent() {
        return true
      }

      close(code?: number, reason?: string) {
        this.readyState = NativeWebSocket.CLOSED
        const event = new CloseEvent('close', {
          code: code ?? 1000,
          reason: reason ?? '',
          wasClean: true,
        })
        this.onclose?.call(this as WebSocket, event)
      }

      send(payload?: string) {
        try {
          const message = typeof payload === 'string' ? JSON.parse(payload) as { action?: string } : null
          if (message?.action === 'get_metrics') {
            queueMicrotask(() => {
              this.onmessage?.call(
                this as WebSocket,
                new MessageEvent('message', {
                  data: JSON.stringify(serviceMeshMetricsMessage),
                }),
              )
            })
          }
        } catch {
          // ignore malformed test payloads
        }
      }
    }

    window.WebSocket = class extends NativeWebSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        const nextUrl = typeof url === 'string' ? url : url.toString()
        if (nextUrl.includes('/ws/service-mesh/')) {
          return new QuietServiceMeshWebSocket(url) as WebSocket
        }
        super(url, protocols)
      }
    } as typeof WebSocket

    localStorage.setItem('auth_token', 'test-token')
    localStorage.setItem('active_tenant_id', tenantId)
    if (localeOverride) {
      if (!localStorage.getItem('cc1c_locale_override')) {
        localStorage.setItem('cc1c_locale_override', localeOverride)
      }
    } else {
      localStorage.removeItem('cc1c_locale_override')
    }
  }, {
    tenantId: TENANT_ID,
    serviceMeshMetricsMessage: SERVICE_MESH_METRICS_MESSAGE,
    localeOverride: options?.localeOverride ?? null,
  })
}

async function setupPersistentDatabaseStream(page: Page) {
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window)
    const encoder = new TextEncoder()

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url

      if (url.includes('/api/v2/databases/stream/')) {
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(encoder.encode(`id: ready-1\ndata: ${JSON.stringify({
              version: '1.0',
              type: 'database_stream_connected',
            })}\n\n`))
          },
        })

        return new Response(stream, {
          status: 200,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-store',
          },
        })
      }

      return originalFetch(input, init)
    }
  })
}

async function setupUiPlatformMocks(
  page: Page,
  options?: {
    isStaff?: boolean
    canManageRuntimeControls?: boolean
    counts?: RequestCounts
    clusterAccessLevel?: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN' | null
    clusterDetailDelayMs?: number
    selectedUserOutsideCatalogSlice?: boolean
    selectedDlqOutsideCatalogSlice?: boolean
    selectedArtifactOutsideCatalogSlice?: boolean
    observedLocaleHeaders?: string[]
  },
) {
  const counts = options?.counts
  const isStaff = options?.isStaff ?? false
  const canManageRuntimeControls = options?.canManageRuntimeControls ?? false
  const clusterAccessLevel = options?.clusterAccessLevel ?? null
  const clusterDetailDelayMs = options?.clusterDetailDelayMs ?? 0
  const selectedUserOutsideCatalogSlice = options?.selectedUserOutsideCatalogSlice ?? false
  const selectedDlqOutsideCatalogSlice = options?.selectedDlqOutsideCatalogSlice ?? false
  const selectedArtifactOutsideCatalogSlice = options?.selectedArtifactOutsideCatalogSlice ?? false
  const observedLocaleHeaders = options?.observedLocaleHeaders
  const currentUser = { id: 1, username: 'ui-platform', is_staff: isStaff }
  const tenantContext = {
    active_tenant_id: TENANT_ID,
    tenants: [{ id: TENANT_ID, slug: 'default', name: 'Default', role: 'owner' }],
  }
  const organization = {
    id: 'organization-main',
    tenant_id: TENANT_ID,
    database_id: DATABASE_ID,
    name: 'Org One',
    full_name: 'Org One LLC',
    inn: '730000000001',
    kpp: '123456789',
    status: 'active',
    external_ref: '',
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  }
  const topologyTemplates = [
    JSON.parse(JSON.stringify(TOPOLOGY_TEMPLATE)) as typeof TOPOLOGY_TEMPLATE,
  ]
  const factualWorkspace = JSON.parse(JSON.stringify(POOL_FACTUAL_WORKSPACE)) as typeof POOL_FACTUAL_WORKSPACE
  const masterDataRegistry = JSON.parse(JSON.stringify(MASTER_DATA_REGISTRY_RESPONSE)) as typeof MASTER_DATA_REGISTRY_RESPONSE
  const masterDataParties = JSON.parse(JSON.stringify(MASTER_DATA_PARTIES)) as typeof MASTER_DATA_PARTIES
  const masterDataItems = JSON.parse(JSON.stringify(MASTER_DATA_ITEMS)) as typeof MASTER_DATA_ITEMS
  const masterDataContracts = JSON.parse(JSON.stringify(MASTER_DATA_CONTRACTS)) as typeof MASTER_DATA_CONTRACTS
  const masterDataTaxProfiles = JSON.parse(JSON.stringify(MASTER_DATA_TAX_PROFILES)) as typeof MASTER_DATA_TAX_PROFILES
  const masterDataGlAccounts = JSON.parse(JSON.stringify(MASTER_DATA_GL_ACCOUNTS)) as typeof MASTER_DATA_GL_ACCOUNTS
  const workflowBindings = JSON.parse(JSON.stringify(POOL_WITH_ATTACHMENT.workflow_bindings))
  const systemHealthResponse = JSON.parse(JSON.stringify(SYSTEM_HEALTH_RESPONSE)) as typeof SYSTEM_HEALTH_RESPONSE
  const runtimeControlCatalog = JSON.parse(JSON.stringify(RUNTIME_CONTROL_CATALOG_RESPONSE)) as typeof RUNTIME_CONTROL_CATALOG_RESPONSE
  const runtimeControlDetails = JSON.parse(JSON.stringify(RUNTIME_CONTROL_DETAILS)) as typeof RUNTIME_CONTROL_DETAILS

  if (canManageRuntimeControls) {
    const orchestratorService = systemHealthResponse.services.find((service) => service.name === 'orchestrator')
    if (orchestratorService) {
      orchestratorService.name = 'Orchestrator'
    }
    systemHealthResponse.services.push({
      name: 'Worker Workflows',
      type: 'go-service',
      url: 'http://worker-workflows.local/health',
      status: 'online',
      response_time_ms: 29,
      last_check: NOW,
      details: {
        scheduler: 'active',
      },
    })
    systemHealthResponse.statistics.total = systemHealthResponse.services.length
    systemHealthResponse.statistics.online = 3
  }

  const buildPagedResponse = <T,>(items: T[], key: string, url: URL) => ({
    [key]: items,
    count: items.length,
    limit: Number(url.searchParams.get('limit') || 50),
    offset: Number(url.searchParams.get('offset') || 0),
  })

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    const requestedLocaleHeader = request.headers()['x-cc1c-locale']
    const requestedLocale = requestedLocaleHeader === 'ru' || requestedLocaleHeader === 'en'
      ? requestedLocaleHeader
      : undefined

    if (method === 'GET' && path === '/api/v2/system/bootstrap/') {
      if (counts) {
        counts.bootstrap += 1
      }
      observedLocaleHeaders?.push(requestedLocale ?? '')
      return fulfillJson(route, {
        me: currentUser,
        tenant_context: tenantContext,
        access: {
          user: { id: currentUser.id, username: currentUser.username },
          clusters: clusterAccessLevel ? [{
            cluster: { id: CLUSTER_RECORD.id, name: CLUSTER_RECORD.name },
            level: clusterAccessLevel,
          }] : [],
          databases: [],
          operation_templates: [],
        },
        capabilities: {
          can_manage_rbac: isStaff,
          can_manage_driver_catalogs: isStaff,
          can_manage_runtime_controls: canManageRuntimeControls,
        },
        i18n: {
          supported_locales: ['ru', 'en'],
          default_locale: 'ru',
          requested_locale: requestedLocale ?? null,
          effective_locale: requestedLocale ?? 'ru',
        },
      })
    }

    if (method === 'GET' && path === '/api/v2/system/me/') {
      if (counts) {
        counts.meReads += 1
      }
      return fulfillJson(route, currentUser)
    }

    if (method === 'GET' && path === '/api/v2/ui/table-metadata/') {
      return fulfillJson(route, { table: String(url.searchParams.get('table') || ''), columns: [] })
    }

    if (method === 'GET' && path === '/api/v2/tenants/list-my-tenants/') {
      if (counts) {
        counts.myTenantsReads += 1
      }
      return fulfillJson(route, tenantContext)
    }

    if (method === 'GET' && path === '/api/v2/system/config/') {
      return fulfillJson(route, {
        ras_default_server: `${CLUSTER_RECORD.ras_host}:${CLUSTER_RECORD.ras_port}`,
      })
    }

    if (method === 'GET' && path === '/api/v2/databases/list-databases/') {
      if (counts) {
        counts.databaseLists += 1
      }
      return fulfillJson(route, {
        databases: [DATABASE_RECORD],
        count: 1,
        total: 1,
      })
    }

    if (method === 'GET' && path === '/api/v2/clusters/list-clusters/') {
      if (counts) {
        counts.clusterLists += 1
      }
      return fulfillJson(route, {
        clusters: [CLUSTER_RECORD],
        count: 1,
        total: 1,
      })
    }

    if (method === 'GET' && path === '/api/v2/clusters/get-cluster/') {
      if (counts) {
        counts.clusterDetails += 1
      }
      if (clusterDetailDelayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, clusterDetailDelayMs))
      }
      return fulfillJson(route, CLUSTER_DETAIL_RESPONSE)
    }

    if (method === 'GET' && path === '/api/v2/databases/get-database/') {
      return fulfillJson(route, {
        database: DATABASE_RECORD,
      })
    }

    if (method === 'GET' && path === '/api/v2/databases/get-metadata-management/') {
      if (counts) {
        counts.metadataManagementReads += 1
      }
      return fulfillJson(route, METADATA_MANAGEMENT)
    }

    if (method === 'POST' && path === '/api/v2/databases/stream-ticket/') {
      if (counts) {
        counts.streamTickets += 1
      }
      return fulfillJson(route, {
        ticket: `ticket-${counts?.streamTickets ?? 1}`,
        expires_in: 30,
        stream_url: `/api/v2/databases/stream/?ticket=ticket-${counts?.streamTickets ?? 1}`,
        session_id: 'browser-session',
        lease_id: `lease-${counts?.streamTickets ?? 1}`,
        client_instance_id: 'browser-instance',
        scope: '__all__',
        message: 'Database stream ticket issued',
      })
    }

    if (method === 'GET' && path === '/api/v2/decisions/') {
      const databaseId = url.searchParams.get('database_id') || ''
      if (databaseId) {
        if (counts) {
          counts.decisionsScoped += 1
        }
      } else if (counts) {
        counts.decisionsUnscoped += 1
      }
      return fulfillJson(route, {
        decisions: DECISIONS,
        count: DECISIONS.length,
        ...(databaseId ? { metadata_context: METADATA_CONTEXT } : {}),
      })
    }

    if (method === 'GET' && path === '/api/v2/workflows/list-workflows/') {
      return fulfillJson(route, {
        workflows: [WORKFLOW],
        count: 1,
        total: 1,
        authoring_phase: null,
      })
    }

    if (method === 'GET' && path === '/api/v2/workflows/list-executions/') {
      return fulfillJson(route, {
        executions: [
          {
            id: WORKFLOW_EXECUTION_DETAIL.id,
            workflow_template: WORKFLOW_EXECUTION_DETAIL.workflow_template,
            template_name: WORKFLOW_EXECUTION_DETAIL.template_name,
            template_version: WORKFLOW_EXECUTION_DETAIL.template_version,
            status: WORKFLOW_EXECUTION_DETAIL.status,
            progress_percent: WORKFLOW_EXECUTION_DETAIL.progress_percent,
            current_node_id: WORKFLOW_EXECUTION_DETAIL.current_node_id,
            error_message: WORKFLOW_EXECUTION_DETAIL.error_message,
            error_node_id: WORKFLOW_EXECUTION_DETAIL.error_node_id,
            trace_id: WORKFLOW_EXECUTION_DETAIL.trace_id,
            started_at: WORKFLOW_EXECUTION_DETAIL.started_at,
            completed_at: WORKFLOW_EXECUTION_DETAIL.completed_at,
            duration: WORKFLOW_EXECUTION_DETAIL.duration,
          },
        ],
        count: 1,
        total: 1,
      })
    }

    if (method === 'GET' && path === '/api/v2/workflows/get-execution/') {
      const executionId = String(url.searchParams.get('execution_id') || '')
      if (executionId !== POOL_RUN.workflow_execution_id) {
        return fulfillJson(route, { detail: 'Workflow execution not found.' }, 404)
      }
      return fulfillJson(route, {
        execution: WORKFLOW_EXECUTION_DETAIL,
        execution_plan: {
          kind: 'workflow',
          workflow_id: WORKFLOW.id,
          input_context_masked: {
            pool_id: POOL_RUN.pool_id,
          },
        },
        bindings: [
          {
            target_ref: 'pool_id',
            source_ref: 'request.pool_id',
            resolve_at: 'api',
            sensitive: false,
            status: 'applied',
          },
        ],
        steps: [],
      })
    }

    if (method === 'GET' && path === '/api/v2/workflows/get-workflow/') {
      const workflowId = String(url.searchParams.get('workflow_id') || '')
      if (workflowId !== WORKFLOW.id) {
        return fulfillJson(route, { detail: 'Workflow not found.' }, 404)
      }
      return fulfillJson(route, {
        workflow: WORKFLOW_TEMPLATE_DETAIL,
        statistics: {
          total_executions: 0,
          successful: 0,
          failed: 0,
          cancelled: 0,
          running: 0,
          average_duration: null,
        },
        executions: [],
      })
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
          },
          {
            id: 'template-exposure-2',
            definition_id: 'definition-2',
            surface: 'template',
            alias: 'tpl-set-flags-extension',
            name: 'Set Extension Flags',
            description: 'Updates extension flags on selected databases',
            is_active: true,
            capability: 'extensions.set_flags',
            status: 'published',
            operation_type: 'designer_cli',
            template_exposure_revision: 3,
          },
        ],
        count: 2,
        total: 2,
      })
    }

    if (method === 'GET' && path === '/api/v2/extensions/overview/') {
      if (counts) {
        counts.extensionsOverview += 1
      }
      return fulfillJson(route, EXTENSIONS_OVERVIEW_RESPONSE)
    }

    if (method === 'GET' && path === '/api/v2/extensions/overview/databases/') {
      if (counts) {
        counts.extensionsOverviewDatabases += 1
      }
      return fulfillJson(route, EXTENSIONS_DATABASES_RESPONSE)
    }

    if (method === 'GET' && path === '/api/v2/extensions/manual-operation-bindings/') {
      if (counts) {
        counts.extensionsManualBindings += 1
      }
      return fulfillJson(route, EXTENSIONS_MANUAL_BINDINGS_RESPONSE)
    }

    const manualBindingMatch = path.match(/^\/api\/v2\/extensions\/manual-operation-bindings\/([^/]+)\/$/)
    if (method === 'PUT' && manualBindingMatch) {
      const manualOperation = manualBindingMatch[1] ?? 'extensions.set_flags'
      const payload = request.postDataJSON() as { template_id?: string } | null
      return fulfillJson(route, {
        binding: {
          manual_operation: manualOperation,
          template_id: payload?.template_id || 'tpl-set-flags-extension',
          updated_at: NOW,
          updated_by: 'ui-platform',
        },
      })
    }

    if (method === 'DELETE' && manualBindingMatch) {
      return fulfillJson(route, { deleted: true }, 204)
    }

    if (method === 'GET' && path === '/api/v2/operations/list-operations/') {
      if (counts) {
        counts.operationsList += 1
      }
      return fulfillJson(route, {
        operations: OPERATIONS,
        count: OPERATIONS.length,
        total: OPERATIONS.length,
      })
    }

    if (method === 'GET' && path === '/api/v2/operations/get-operation/') {
      const operationId = String(url.searchParams.get('operation_id') || '')
      const detail = OPERATION_DETAILS[operationId]
      if (!detail) {
        return fulfillJson(route, { detail: 'Operation not found.' }, 404)
      }
      if (counts) {
        counts.operationDetails += 1
      }
      return fulfillJson(route, detail)
    }

    if (method === 'POST' && path === '/api/v2/operations/get-operation-timeline/') {
      const payload = request.postDataJSON() as { operation_id?: string } | null
      const operationId = typeof payload?.operation_id === 'string' ? payload.operation_id : ''
      const timeline = OPERATION_TIMELINES[operationId]
      if (!timeline) {
        return fulfillJson(route, { detail: 'Operation timeline not found.' }, 404)
      }
      return fulfillJson(route, timeline)
    }

    if (method === 'GET' && path === '/api/v2/operations/stream-mux-status/') {
      if (counts) {
        counts.streamMuxStatusReads += 1
      }
      return fulfillJson(route, {
        active_streams: 2,
        max_streams: 16,
        active_subscriptions: 3,
        max_subscriptions: 64,
      })
    }

    if (method === 'GET' && path === '/api/v2/system/health/') {
      if (counts) {
        counts.systemHealthReads += 1
      }
      return fulfillJson(route, systemHealthResponse)
    }

    if (method === 'GET' && path === '/api/v2/system/runtime-control/catalog/') {
      if (counts) {
        counts.runtimeControlCatalogReads += 1
      }
      if (!canManageRuntimeControls) {
        return fulfillJson(route, { success: false, error: { code: 'PERMISSION_DENIED' } }, 403)
      }
      return fulfillJson(route, runtimeControlCatalog)
    }

    const runtimeControlDesiredStateMatch = path.match(/^\/api\/v2\/system\/runtime-control\/runtimes\/(.+)\/desired-state\/$/)
    if (method === 'PATCH' && runtimeControlDesiredStateMatch) {
      if (counts) {
        counts.runtimeControlDesiredStateWrites += 1
      }
      const runtimeId = decodeURIComponent(runtimeControlDesiredStateMatch[1] ?? '')
      const detail = runtimeControlDetails[runtimeId as keyof typeof runtimeControlDetails]
      if (!detail || !detail.desired_state) {
        return fulfillJson(route, { success: false, error: { code: 'NOT_FOUND' } }, 404)
      }
      const payload = request.postDataJSON() as {
        scheduler_enabled?: boolean
        jobs?: Array<{ job_name: string; enabled?: boolean; schedule?: string }>
      } | null
      if (typeof payload?.scheduler_enabled === 'boolean') {
        detail.desired_state.scheduler_enabled = payload.scheduler_enabled
      }
      for (const jobPatch of payload?.jobs ?? []) {
        const job = detail.desired_state.jobs.find((item) => item.job_name === jobPatch.job_name)
        if (!job) continue
        if (typeof jobPatch.enabled === 'boolean') {
          job.enabled = jobPatch.enabled
        }
        if (typeof jobPatch.schedule === 'string') {
          job.schedule = jobPatch.schedule
        }
      }
      const catalogRuntime = runtimeControlCatalog.runtimes.find((item) => item.runtime_id === runtimeId)
      if (catalogRuntime) {
        catalogRuntime.desired_state = JSON.parse(JSON.stringify(detail.desired_state))
      }
      return fulfillJson(route, { runtime_id: runtimeId, desired_state: detail.desired_state })
    }

    const runtimeControlRuntimeActionsMatch = path.match(/^\/api\/v2\/system\/runtime-control\/runtimes\/(.+)\/actions\/$/)
    if (method === 'GET' && runtimeControlRuntimeActionsMatch) {
      const runtimeId = decodeURIComponent(runtimeControlRuntimeActionsMatch[1] ?? '')
      const detail = runtimeControlDetails[runtimeId as keyof typeof runtimeControlDetails]
      return fulfillJson(route, { actions: detail?.recent_actions ?? [] })
    }

    const runtimeControlRuntimeMatch = path.match(/^\/api\/v2\/system\/runtime-control\/runtimes\/(.+)\/$/)
    if (method === 'GET' && runtimeControlRuntimeMatch) {
      if (counts) {
        counts.runtimeControlRuntimeReads += 1
      }
      if (!canManageRuntimeControls) {
        return fulfillJson(route, { success: false, error: { code: 'PERMISSION_DENIED' } }, 403)
      }
      const runtimeId = decodeURIComponent(runtimeControlRuntimeMatch[1] ?? '')
      const detail = runtimeControlDetails[runtimeId as keyof typeof runtimeControlDetails]
      if (!detail) {
        return fulfillJson(route, { success: false, error: { code: 'NOT_FOUND' } }, 404)
      }
      return fulfillJson(route, { runtime: detail })
    }

    if (method === 'POST' && path === '/api/v2/system/runtime-control/actions/') {
      if (counts) {
        counts.runtimeControlActionWrites += 1
      }
      const payload = request.postDataJSON() as {
        runtime_id?: string
        action_type?: 'probe' | 'restart' | 'tail_logs' | 'trigger_now'
        reason?: string
        target_job_name?: string
      } | null
      const runtimeId = String(payload?.runtime_id || '')
      const detail = runtimeControlDetails[runtimeId as keyof typeof runtimeControlDetails]
      if (!detail) {
        return fulfillJson(route, { success: false, error: { code: 'NOT_FOUND' } }, 404)
      }
      const action = {
        id: `runtime-action-${detail.recent_actions.length + 1}`,
        provider: 'local_scripts',
        runtime_id: runtimeId,
        runtime_name: detail.runtime_name,
        action_type: payload?.action_type ?? 'probe',
        target_job_name: payload?.target_job_name ?? '',
        status: 'accepted',
        reason: payload?.reason ?? '',
        requested_by_username: 'ui-platform',
        requested_at: NOW,
        started_at: null,
        finished_at: null,
        result_excerpt: '',
        result_payload: {},
        error_message: '',
        scheduler_job_run_id: payload?.action_type === 'trigger_now' ? 6001 : null,
      }
      detail.recent_actions = [action, ...detail.recent_actions].slice(0, 10)
      if (payload?.action_type === 'tail_logs' && detail.logs_excerpt) {
        detail.logs_excerpt.updated_at = NOW
      }
      if (payload?.action_type === 'trigger_now' && detail.desired_state) {
        const job = detail.desired_state.jobs.find((item) => item.job_name === payload.target_job_name)
        if (job) {
          job.latest_run_status = 'success'
          job.latest_run_started_at = NOW
          job.latest_run_id = (job.latest_run_id ?? 7000) + 1
        }
      }
      return fulfillJson(route, { action }, 202)
    }

    if (method === 'GET' && path === '/api/v2/service-mesh/get-history/') {
      const serviceName = String(url.searchParams.get('service') || '')
      const history = SERVICE_MESH_HISTORY[serviceName]
      if (!history) {
        return fulfillJson(route, { detail: 'Service history not found.' }, 404)
      }
      if (counts) {
        counts.serviceHistoryReads += 1
      }
      return fulfillJson(route, history)
    }

    if (method === 'GET' && path === '/api/v2/settings/runtime/') {
      if (counts) {
        counts.runtimeSettingsReads += 1
      }
      return fulfillJson(route, RUNTIME_SETTINGS_RESPONSE)
    }

    const runtimeSettingMatch = path.match(/^\/api\/v2\/settings\/runtime\/(.+)\/$/)
    if (method === 'PATCH' && runtimeSettingMatch) {
      const key = decodeURIComponent(runtimeSettingMatch[1] ?? '')
      const payload = request.postDataJSON() as { value?: unknown } | null
      const existing = RUNTIME_SETTINGS_RESPONSE.settings.find((item) => item.key === key)
      if (!existing) {
        return fulfillJson(route, { detail: 'Runtime setting not found.' }, 404)
      }
      existing.value = payload?.value
      return fulfillJson(route, existing)
    }

    if (method === 'GET' && path === '/api/v2/settings/command-schemas/editor/') {
      if (counts) {
        counts.commandSchemasEditorReads += 1
      }
      return fulfillJson(route, COMMAND_SCHEMAS_EDITOR_VIEW)
    }

    if (method === 'GET' && path === '/api/v2/users/list/') {
      if (counts) {
        counts.usersList += 1
      }
      const requestedUserId = Number.parseInt(url.searchParams.get('id') || '', 10)
      if (Number.isFinite(requestedUserId) && requestedUserId === ADMIN_USER.id) {
        if (counts) {
          counts.usersDetail += 1
        }
        return fulfillJson(route, {
          users: [ADMIN_USER],
          count: 1,
          total: 1,
        })
      }
      if (selectedUserOutsideCatalogSlice) {
        return fulfillJson(route, {
          users: [],
          count: 0,
          total: 0,
        })
      }
      return fulfillJson(route, USERS_RESPONSE)
    }

    if (method === 'GET' && path === '/api/v2/dlq/list/') {
      if (counts) {
        counts.dlqList += 1
      }
      if (selectedDlqOutsideCatalogSlice) {
        return fulfillJson(route, {
          messages: [],
          count: 0,
          total: 0,
        })
      }
      return fulfillJson(route, DLQ_LIST_RESPONSE)
    }

    if (method === 'GET' && path === '/api/v2/dlq/get/') {
      if (counts) {
        counts.dlqDetail += 1
      }
      const dlqMessageId = String(url.searchParams.get('dlq_message_id') || '')
      if (dlqMessageId !== DLQ_MESSAGE.dlq_message_id) {
        return fulfillJson(route, { detail: 'DLQ message not found.' }, 404)
      }
      return fulfillJson(route, DLQ_MESSAGE)
    }

    if (method === 'POST' && path === '/api/v2/dlq/retry/') {
      return fulfillJson(route, {
        retried: true,
        operation_id: WORKFLOW_OPERATION.id,
      })
    }

    if (method === 'GET' && path === '/api/v2/artifacts/') {
      if (counts) {
        counts.artifactsList += 1
      }
      const artifactId = String(url.searchParams.get('artifact_id') || '')
      const onlyDeleted = url.searchParams.get('only_deleted') === 'true'
      if (artifactId === DELETED_ARTIFACT.id) {
        if (counts) {
          counts.artifactDetail += 1
        }
        return fulfillJson(route, {
          artifacts: [DELETED_ARTIFACT],
          count: 1,
        })
      }
      if (artifactId === ACTIVE_ARTIFACT.id) {
        if (counts) {
          counts.artifactDetail += 1
        }
        return fulfillJson(route, {
          artifacts: [ACTIVE_ARTIFACT],
          count: 1,
        })
      }
      if (selectedArtifactOutsideCatalogSlice) {
        return fulfillJson(route, {
          artifacts: [],
          count: 0,
        })
      }
      const artifacts = onlyDeleted ? [DELETED_ARTIFACT] : [ACTIVE_ARTIFACT]
      return fulfillJson(route, {
        artifacts,
        count: artifacts.length,
      })
    }

    const artifactVersionsMatch = path.match(/^\/api\/v2\/artifacts\/([^/]+)\/versions\/$/)
    if (method === 'GET' && artifactVersionsMatch) {
      return fulfillJson(route, ARTIFACT_VERSIONS_RESPONSE)
    }

    const artifactAliasesMatch = path.match(/^\/api\/v2\/artifacts\/([^/]+)\/aliases\/$/)
    if (method === 'GET' && artifactAliasesMatch) {
      return fulfillJson(route, ARTIFACT_ALIASES_RESPONSE)
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-roles/') {
      return fulfillJson(route, {
        roles: [
          {
            id: 1,
            name: 'services_operator',
            users_count: 1,
            permissions_count: 2,
            permission_codes: ['databases.view', 'operations.view'],
          },
        ],
        count: 1,
        total: 1,
      })
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-admin-audit/') {
      return fulfillJson(route, RBAC_AUDIT_RESPONSE)
    }

    const decisionDetailMatch = path.match(/^\/api\/v2\/decisions\/([^/]+)\/$/)
    if (method === 'GET' && decisionDetailMatch) {
      const decisionId = decisionDetailMatch[1] ?? DECISION.id
      return fulfillJson(route, {
        decision: DECISIONS.find((candidate) => candidate.id === decisionId) ?? DECISION,
        ...(url.searchParams.get('database_id') ? { metadata_context: METADATA_CONTEXT } : {}),
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/binding-profiles/') {
      if (counts) {
        counts.bindingProfilesList += 1
      }
      return fulfillJson(route, {
        binding_profiles: BINDING_PROFILE_SUMMARIES,
        count: BINDING_PROFILE_SUMMARIES.length,
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/topology-templates/') {
      return fulfillJson(route, {
        topology_templates: topologyTemplates,
        count: topologyTemplates.length,
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/registry/') {
      return fulfillJson(route, masterDataRegistry)
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/parties/') {
      return fulfillJson(route, buildPagedResponse(masterDataParties, 'parties', url))
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/items/') {
      return fulfillJson(route, buildPagedResponse(masterDataItems, 'items', url))
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/contracts/') {
      return fulfillJson(route, buildPagedResponse(masterDataContracts, 'contracts', url))
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/tax-profiles/') {
      return fulfillJson(route, buildPagedResponse(masterDataTaxProfiles, 'tax_profiles', url))
    }

    if (method === 'GET' && path === '/api/v2/pools/master-data/gl-accounts/') {
      return fulfillJson(route, buildPagedResponse(masterDataGlAccounts, 'gl_accounts', url))
    }

    if (method === 'GET' && path === '/api/v2/pools/workflow-bindings/') {
      return fulfillJson(route, {
        pool_id: String(url.searchParams.get('pool_id') || POOL_WITH_ATTACHMENT.id),
        workflow_bindings: workflowBindings,
        collection_etag: 'bindings-etag-v1',
        blocking_remediation: null,
      })
    }

    const bindingProfileMatch = path.match(/^\/api\/v2\/pools\/binding-profiles\/([^/]+)\/$/)
    if (method === 'GET' && bindingProfileMatch) {
      const bindingProfileId = bindingProfileMatch[1] ?? BINDING_PROFILE_DETAIL.binding_profile_id
      if (counts) {
        counts.bindingProfileDetails += 1
      }
      return fulfillJson(route, {
        binding_profile: BINDING_PROFILE_DETAILS[bindingProfileId] ?? BINDING_PROFILE_DETAIL,
      })
    }

    if (method === 'POST' && path === '/api/v2/pools/topology-templates/') {
      const payload = request.postDataJSON() as Record<string, unknown>
      const revision = payload.revision && typeof payload.revision === 'object'
        ? payload.revision as Record<string, unknown>
        : {}
      const topologyTemplateId = `template-${topologyTemplates.length + 1}`
      const topologyTemplateRevisionId = `${topologyTemplateId}-revision-r1`
      const createdTemplate = {
        topology_template_id: topologyTemplateId,
        code: String(payload.code || '').trim() || topologyTemplateId,
        name: String(payload.name || '').trim() || 'New Topology Template',
        description: String(payload.description || ''),
        status: 'active',
        metadata: payload.metadata && typeof payload.metadata === 'object' ? payload.metadata : {},
        latest_revision_number: 1,
        latest_revision: {
          topology_template_revision_id: topologyTemplateRevisionId,
          topology_template_id: topologyTemplateId,
          revision_number: 1,
          nodes: Array.isArray(revision.nodes) ? revision.nodes : [],
          edges: Array.isArray(revision.edges) ? revision.edges : [],
          metadata: revision.metadata && typeof revision.metadata === 'object' ? revision.metadata : {},
          created_at: NOW,
        },
        revisions: [
          {
            topology_template_revision_id: topologyTemplateRevisionId,
            topology_template_id: topologyTemplateId,
            revision_number: 1,
            nodes: Array.isArray(revision.nodes) ? revision.nodes : [],
            edges: Array.isArray(revision.edges) ? revision.edges : [],
            metadata: revision.metadata && typeof revision.metadata === 'object' ? revision.metadata : {},
            created_at: NOW,
          },
        ],
        created_at: NOW,
        updated_at: NOW,
      }
      topologyTemplates.unshift(createdTemplate)
      return fulfillJson(route, { topology_template: createdTemplate }, 201)
    }

    const topologyTemplateRevisionMatch = path.match(/^\/api\/v2\/pools\/topology-templates\/([^/]+)\/revisions\/$/)
    if (method === 'POST' && topologyTemplateRevisionMatch) {
      const topologyTemplateId = topologyTemplateRevisionMatch[1] ?? ''
      const template = topologyTemplates.find((item) => item.topology_template_id === topologyTemplateId)
      if (!template) {
        return fulfillJson(route, { detail: 'Topology template not found.' }, 404)
      }
      const payload = request.postDataJSON() as Record<string, unknown>
      const revision = payload.revision && typeof payload.revision === 'object'
        ? payload.revision as Record<string, unknown>
        : {}
      const revisionNumber = Number(template.latest_revision_number || 0) + 1
      const nextRevision = {
        topology_template_revision_id: `${topologyTemplateId}-revision-r${revisionNumber}`,
        topology_template_id: topologyTemplateId,
        revision_number: revisionNumber,
        nodes: Array.isArray(revision.nodes) ? revision.nodes : [],
        edges: Array.isArray(revision.edges) ? revision.edges : [],
        metadata: revision.metadata && typeof revision.metadata === 'object' ? revision.metadata : {},
        created_at: NOW,
      }
      template.latest_revision_number = revisionNumber
      template.latest_revision = nextRevision
      template.revisions = [nextRevision, ...template.revisions]
      template.updated_at = NOW
      return fulfillJson(route, { topology_template: template })
    }

    if (method === 'GET' && path === '/api/v2/pools/') {
      if (counts) {
        counts.organizationPools += 1
      }
      return fulfillJson(route, {
        pools: [POOL_WITH_ATTACHMENT],
        count: 1,
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/schema-templates/') {
      return fulfillJson(route, { templates: [] })
    }

    if (method === 'GET' && path === '/api/v2/pools/organizations/') {
      if (counts) {
        counts.poolOrganizations += 1
      }
      return fulfillJson(route, {
        organizations: [organization],
        count: 1,
      })
    }

    const organizationMatch = path.match(/^\/api\/v2\/pools\/organizations\/([^/]+)\/$/)
    if (method === 'GET' && organizationMatch) {
      if (counts) {
        counts.poolOrganizationDetails += 1
      }
      return fulfillJson(route, {
        organization,
        pool_bindings: [],
      })
    }

    const graphMatch = path.match(/^\/api\/v2\/pools\/([^/]+)\/graph\/$/)
    if (method === 'GET' && graphMatch) {
      if (counts) {
        counts.poolGraphs += 1
      }
      return fulfillJson(route, {
        pool_id: graphMatch[1],
        date: '2026-01-01',
        version: 'v1:topology-initial',
        nodes: [
          {
            node_version_id: 'node-root',
            organization_id: organization.id,
            inn: organization.inn,
            name: organization.name,
            is_root: true,
            metadata: {},
          },
          {
            node_version_id: 'node-child',
            organization_id: 'organization-child',
            inn: '730000000002',
            name: 'Child Org',
            is_root: false,
            metadata: {},
          },
        ],
        edges: [
          {
            edge_version_id: 'edge-1',
            parent_node_version_id: 'node-root',
            child_node_version_id: 'node-child',
            weight: '1',
            min_amount: null,
            max_amount: null,
            metadata: {
              document_policy_key: 'document_policy',
            },
          },
        ],
      })
    }

    if (method === 'GET' && path === '/api/v2/pools/runs/') {
      if (counts) {
        counts.poolRuns += 1
      }
      return fulfillJson(route, { runs: [POOL_RUN] })
    }

    if (method === 'GET' && path === '/api/v2/pools/batches/') {
      return fulfillJson(route, { batches: [], count: 0 })
    }

    const poolRunReportMatch = path.match(/^\/api\/v2\/pools\/runs\/([^/]+)\/report\/$/)
    if (method === 'GET' && poolRunReportMatch) {
      if (counts) {
        counts.poolRunReports += 1
      }
      return fulfillJson(route, POOL_RUN_REPORT)
    }

    if (method === 'GET' && path === '/api/v2/pools/factual/overview/') {
      return fulfillJson(route, POOL_FACTUAL_OVERVIEW)
    }

    if (method === 'GET' && path === '/api/v2/pools/factual/workspace/') {
      if (url.searchParams.get('pool_id') && url.searchParams.get('pool_id') !== POOL_WITH_ATTACHMENT.id) {
        return fulfillJson(route, { detail: 'Pool factual workspace not found.' }, 404)
      }
      return fulfillJson(route, factualWorkspace)
    }

    if (method === 'POST' && path === '/api/v2/pools/factual/review-actions/') {
      const payload = request.postDataJSON() as {
        review_item_id?: string
        action?: 'attribute' | 'reconcile' | 'resolve_without_change'
      } | null
      const reviewItemId = String(payload?.review_item_id || '')
      const action = payload?.action
      const reviewItem = factualWorkspace.review_queue.items.find((item) => item.id === reviewItemId)
      if (!reviewItem || !action) {
        return fulfillJson(route, { detail: 'Review item not found.' }, 404)
      }
      reviewItem.status = action === 'attribute'
        ? 'attributed'
        : action === 'reconcile'
          ? 'reconciled'
          : 'resolved_without_change'
      reviewItem.allowed_actions = []
      reviewItem.attention_required = false
      reviewItem.resolved_at = NOW
      factualWorkspace.review_queue.summary.pending_total = factualWorkspace.review_queue.items.filter(
        (item) => item.status === 'pending'
      ).length
      factualWorkspace.review_queue.summary.unattributed_total = factualWorkspace.review_queue.items.filter(
        (item) => item.status === 'pending' && item.reason === 'unattributed'
      ).length
      factualWorkspace.review_queue.summary.late_correction_total = factualWorkspace.review_queue.items.filter(
        (item) => item.status === 'pending' && item.reason === 'late_correction'
      ).length
      factualWorkspace.review_queue.summary.attention_required_total = factualWorkspace.review_queue.items.filter(
        (item) => item.attention_required
      ).length
      factualWorkspace.summary.pending_review_total = factualWorkspace.review_queue.summary.pending_total
      factualWorkspace.summary.attention_required_total = factualWorkspace.review_queue.summary.attention_required_total
      return fulfillJson(route, {
        review_item: reviewItem,
        review_queue: factualWorkspace.review_queue,
      })
    }

    const topologySnapshotsMatch = path.match(/^\/api\/v2\/pools\/([^/]+)\/topology-snapshots\/$/)
    if (method === 'GET' && topologySnapshotsMatch) {
      if (counts) {
        counts.poolTopologySnapshots += 1
      }
      return fulfillJson(route, {
        pool_id: topologySnapshotsMatch[1],
        count: 1,
        snapshots: [
          {
            effective_from: '2026-01-01',
            effective_to: null,
            nodes_count: 0,
            edges_count: 0,
          },
        ],
      })
    }

    return fulfillJson(route, { detail: `Unhandled mock for ${method} ${path}` }, 404)
  })
}

async function switchShellLocaleToEnglish(page: Page) {
  const localeSelect = page.getByTestId('shell-locale-select')
  await localeSelect.locator('.ant-select-selector').click()
  await page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) [title="English"]').click()
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflowDetails = await page.evaluate(() => {
    const ignoredTags = new Set(['svg', 'g', 'path', 'ellipse', 'circle'])
    const overflow = document.documentElement.scrollWidth - window.innerWidth
    if (overflow <= 1) {
      return null
    }

    const offenders = Array.from(document.querySelectorAll<HTMLElement>('body *'))
      .map((element) => {
        if (ignoredTags.has(element.tagName.toLowerCase())) {
          return null
        }
        if (element.closest('button[aria-label="Open Tanstack query devtools"]')) {
          return null
        }
        const rect = element.getBoundingClientRect()
        const overflowRight = rect.right - window.innerWidth
        return {
          tag: element.tagName.toLowerCase(),
          testId: element.dataset.testid || '',
          text: (element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120),
          overflowRight,
          width: rect.width,
        }
      })
      .filter(Boolean)
      .filter((item) => item.overflowRight > 1)
      .sort((left, right) => right.overflowRight - left.overflowRight)
      .slice(0, 5)

    if (offenders.length === 0) {
      return null
    }

    return {
      overflow,
      offenders,
    }
  })

  if (overflowDetails) {
    throw new Error(`Page has horizontal overflow: ${JSON.stringify(overflowDetails)}`)
  }
}

async function expectNoScopedHorizontalOverflow(locator: Locator, label: string) {
  const overflowDetails = await locator.evaluate((root) => {
    const ignoredTags = new Set(['svg', 'g', 'path', 'ellipse', 'circle'])
    const isVisible = (element: HTMLElement) => {
      const style = window.getComputedStyle(element)
      if (style.display === 'none' || style.visibility === 'hidden') {
        return false
      }
      const rect = element.getBoundingClientRect()
      return rect.width > 0 && rect.height > 0
    }

    const offenders = [root as HTMLElement, ...Array.from(root.querySelectorAll<HTMLElement>('*'))]
      .filter((element) => !ignoredTags.has(element.tagName.toLowerCase()))
      .filter(isVisible)
      .map((element) => ({
        tag: element.tagName.toLowerCase(),
        testId: element.dataset.testid || '',
        text: (element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120),
        overflow: element.scrollWidth - element.clientWidth,
        clientWidth: element.clientWidth,
      }))
      .filter((item) => item.clientWidth > 120 && item.overflow > 4)
      .filter((item) => item.text.length > 0 || item.testId.length > 0)
      .sort((left, right) => right.overflow - left.overflow)
      .slice(0, 5)

    return offenders.length > 0 ? offenders : null
  })

  if (overflowDetails) {
    throw new Error(`${label} has horizontal overflow: ${JSON.stringify(overflowDetails)}`)
  }
}

async function fillTopologyTemplateCreateForm(page: Page) {
  await page.getByTestId('pool-topology-templates-create-code').fill('new-template')
  await page.getByTestId('pool-topology-templates-create-name').fill('New Template')
  await page.getByTestId('pool-topology-templates-create-description').fill('Reusable topology authoring surface')
  await page.getByTestId('pool-topology-templates-create-node-slot-key-0').fill('root')
  await page.getByTestId('pool-topology-templates-create-node-label-0').fill('Root')
  await page.getByTestId('pool-topology-templates-create-node-root-0').click()
  await page.getByTestId('pool-topology-templates-create-add-node').click()
  await page.getByTestId('pool-topology-templates-create-node-slot-key-1').fill('leaf')
  await page.getByTestId('pool-topology-templates-create-node-label-1').fill('Leaf')
  await page.getByTestId('pool-topology-templates-create-add-edge').click()
  await page.getByTestId('pool-topology-templates-create-edge-parent-slot-key-0').fill('root')
  await page.getByTestId('pool-topology-templates-create-edge-child-slot-key-0').fill('leaf')
  await page.getByTestId('pool-topology-templates-create-edge-weight-0').fill('1')
  await page.getByTestId('pool-topology-templates-create-edge-document-policy-key-0').fill('sale')
}

async function fillTopologyTemplateReviseForm(page: Page) {
  await page.getByTestId('pool-topology-templates-revise-node-label-0').fill('Updated Root')
  await page.getByTestId('pool-topology-templates-revise-edge-document-policy-key-0').fill('receipt')
}

async function selectVisibleAntdOption(page: Page, label: string) {
  await page
    .locator('.ant-select-dropdown:visible .ant-select-item-option-content', { hasText: label })
    .first()
    .click()
}

async function expectVisibleWithinContainer(
  locator: ReturnType<Page['locator']>,
  container: ReturnType<Page['locator']>,
) {
  const [box, containerBox] = await Promise.all([locator.boundingBox(), container.boundingBox()])

  if (!box || !containerBox) {
    throw new Error('Expected visible element and container bounding boxes.')
  }

  expect(box.x).toBeGreaterThanOrEqual(containerBox.x)
  expect(box.y).toBeGreaterThanOrEqual(containerBox.y)
  expect(box.x + box.width).toBeLessThanOrEqual(containerBox.x + containerBox.width)
  expect(box.y + box.height).toBeLessThanOrEqual(containerBox.y + containerBox.height)
}

async function expectContrastAtLeast(locator: ReturnType<Page['locator']>, minimumRatio: number) {
  const contrastRatio = await locator.evaluate((element) => {
    const parseColor = (value: string) => {
      const match = value.match(/rgba?\(([^)]+)\)/)
      if (!match) {
        return [0, 0, 0, 1] as const
      }

      const [r = '0', g = '0', b = '0', a = '1'] = match[1].split(',').map((part) => part.trim())
      return [Number(r), Number(g), Number(b), Number(a)] as const
    }

    const composite = (
      foreground: readonly [number, number, number, number],
      background: readonly [number, number, number, number],
    ) => {
      const alpha = foreground[3]
      const channel = (index: number) => (
        foreground[index] * alpha + background[index] * (1 - alpha)
      )

      return [channel(0), channel(1), channel(2), 1] as const
    }

    const luminance = (rgb: readonly [number, number, number, number]) => {
      const toLinear = (channel: number) => {
        const normalized = channel / 255
        return normalized <= 0.04045
          ? normalized / 12.92
          : ((normalized + 0.055) / 1.055) ** 2.4
      }

      const [r, g, b] = rgb
      return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b)
    }

    const resolveBackground = (node: HTMLElement | null) => {
      let current = node
      while (current) {
        const background = parseColor(window.getComputedStyle(current).backgroundColor)
        if (background[3] > 0) {
          return background
        }
        current = current.parentElement
      }

      return [255, 255, 255, 1] as const
    }

    const styles = window.getComputedStyle(element)
    const foreground = composite(parseColor(styles.color), resolveBackground(element.parentElement))
    const background = resolveBackground(element as HTMLElement)
    const lighter = Math.max(luminance(foreground), luminance(background))
    const darker = Math.min(luminance(foreground), luminance(background))

    return (lighter + 0.05) / (darker + 0.05)
  })

  expect(contrastRatio).toBeGreaterThanOrEqual(minimumRatio)
}

test('UI platform: /decisions keeps mobile list stable and opens detail in a drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/decisions', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Decision Policy Library')).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.getByText('Services publication policy').first().click()

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByText('Compiled document_policy JSON')).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /decisions opens authoring in a mobile-safe drawer with labeled fields', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/decisions', { waitUntil: 'domcontentloaded' })

  await page.getByRole('button', { name: 'New policy' }).click()

  const authoringDrawer = page.getByRole('dialog')
  await expect(authoringDrawer).toBeVisible()
  await expect(authoringDrawer.getByLabel('Decision table ID')).toBeVisible()
  await expect(authoringDrawer.getByLabel('Decision name')).toBeVisible()
  await expect(authoringDrawer.getByRole('button', { name: 'Save decision' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /pools/execution-packs keeps mobile catalog readable and opens detail in a drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/pools/execution-packs', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Execution Packs')).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.getByRole('button', { name: 'Open execution pack services-publication' }).click()

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('pool-binding-profiles-selected-code')).toHaveText('services-publication')
  await expect(detailDrawer.getByRole('heading', { name: 'Where this execution pack is used', level: 3 })).toBeVisible()
  await expect(detailDrawer.getByRole('button', { name: 'Publish new revision' })).toBeVisible()
  await expect(detailDrawer.getByRole('button', { name: 'Deactivate execution pack' })).toBeVisible()
  await expect(detailDrawer.getByRole('columnheader', { name: 'Opaque pin' })).toHaveCount(0)
  await expect(detailDrawer.getByRole('button', { name: /Advanced payload and immutable pins/i })).toBeVisible()
  await expectVisibleWithinContainer(detailDrawer.getByRole('button', { name: 'Publish new revision' }), detailDrawer)
  await expectVisibleWithinContainer(detailDrawer.getByRole('button', { name: 'Deactivate execution pack' }), detailDrawer)
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /pools/execution-packs opens create-execution-pack authoring in a mobile-safe modal shell', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/pools/execution-packs', { waitUntil: 'domcontentloaded' })

  await page.getByRole('button', { name: 'Create execution pack' }).click()

  const authoringModal = page.getByRole('dialog')
  await expect(authoringModal).toBeVisible()
  await expect(authoringModal.getByLabel('Execution Pack code')).toBeVisible()
  await expect(authoringModal.getByLabel('Execution Pack name')).toBeVisible()
  await expect(authoringModal.getByTestId('pool-binding-profiles-create-workflow-revision-select')).toBeVisible()
  await expect(authoringModal.getByRole('button', { name: 'Create execution pack' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /pools/execution-packs keeps publication slots compact in the publish revision modal', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto('/pools/execution-packs?profile=e54257e5-c587-4467-bb7c-4eb53ee05293&detail=1', {
    waitUntil: 'domcontentloaded',
  })

  await page.getByRole('button', { name: 'Publish new revision' }).click()

  const authoringModal = page.getByRole('dialog')
  await expect(authoringModal).toBeVisible()

  await authoringModal.getByTestId('pool-binding-profiles-revise-add-slot').click()
  await authoringModal.getByTestId('pool-binding-profiles-revise-add-slot').click()

  const slotRows = [0, 1, 2].map((slotIndex) => (
    authoringModal.getByTestId(`pool-binding-profiles-revise-slot-row-${slotIndex}`)
  ))

  const boxes = await Promise.all(slotRows.map(async (locator) => locator.boundingBox()))
  const [firstRow, secondRow, thirdRow] = boxes

  if (!firstRow || !secondRow || !thirdRow) {
    throw new Error('Expected publication slot rows to have measurable bounding boxes.')
  }

  const firstGap = secondRow.y - (firstRow.y + firstRow.height)
  const secondGap = thirdRow.y - (secondRow.y + secondRow.height)

  expect(firstGap).toBeLessThanOrEqual(24)
  expect(secondGap).toBeLessThanOrEqual(24)
  await expectVisibleWithinContainer(slotRows[2], authoringModal)
})

test('UI platform: /pools/topology-templates keeps mobile catalog readable and opens detail in a drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/pools/topology-templates', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Topology Templates')).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.getByRole('button', { name: 'Open topology template top-down-template' }).click()

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('pool-topology-templates-selected-code')).toHaveText('top-down-template')
  await expect(detailDrawer.getByRole('button', { name: 'Publish new revision' })).toBeVisible()
  await expect(detailDrawer.getByText('Root · root')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(detailDrawer, 'Topology template detail drawer')
})

test('UI platform: /pools/topology-templates opens create-template authoring in a mobile-safe drawer shell', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/pools/topology-templates', { waitUntil: 'domcontentloaded' })

  await page.getByRole('button', { name: 'Create template' }).click()

  const authoringDrawer = page.getByRole('dialog')
  await expect(authoringDrawer).toBeVisible()
  await expect(authoringDrawer.getByLabel('Template code')).toBeVisible()
  await expect(authoringDrawer.getByLabel('Template name')).toBeVisible()
  await expect(authoringDrawer.getByRole('button', { name: 'Create template' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(authoringDrawer, 'Topology template create drawer')
})

test('UI platform: /pools/topology-templates opens revise-template authoring in a mobile-safe drawer shell', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/pools/topology-templates?template=template-top-down&detail=1', {
    waitUntil: 'domcontentloaded',
  })

  await page.getByRole('button', { name: 'Publish new revision' }).click()

  const reviseDrawer = page.getByTestId('pool-topology-templates-revise-drawer')
  await expect(reviseDrawer).toBeVisible()
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expect(reviseDrawer.getByTestId('pool-topology-templates-revise-node-label-0')).toBeVisible()
  await expect(reviseDrawer.getByRole('button', { name: 'Publish revision' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(reviseDrawer, 'Topology template revise drawer')
})

test('UI platform: /workflows restores selected workflow detail from URL-backed workspace state', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/workflows?workflow=${WORKFLOW.id}&detail=1`, { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Workflow Scheme Library', level: 2 })).toBeVisible()
  await expect(page.getByTestId('workflow-list-selected-id')).toHaveText(WORKFLOW.id)
  await expect(page.getByTestId('workflow-list-selected-dag')).toContainText('"start"')
  await expect(page.getByTestId('workflow-list-detail-open')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expect.poll(() => counts.bootstrap).toBe(1)
})

test('UI platform: /templates restores selected template detail from URL-backed workspace state', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/templates?template=tpl-sync-extension&detail=1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Operation Templates', level: 2 })).toBeVisible()
  await expect(page.getByTestId('templates-selected-id')).toHaveText('tpl-sync-extension')
  await expect(page.getByRole('button', { name: 'Edit', exact: true })).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expect.poll(() => counts.bootstrap).toBe(1)
})

test('UI platform: /templates keeps mobile catalog readable and opens detail in a drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/templates', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Operation Templates', level: 2 })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.getByTestId('templates-catalog-item-tpl-sync-extension').click()

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('templates-selected-id')).toHaveText('tpl-sync-extension')
  await expect(detailDrawer.getByRole('button', { name: 'Edit', exact: true })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /workflows keeps mobile catalog readable and opens detail in a drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/workflows', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Workflow Scheme Library', level: 2 })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.getByTestId(`workflow-list-catalog-item-${WORKFLOW.id}`).click()

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('workflow-list-selected-id')).toHaveText(WORKFLOW.id)
  await expect(detailDrawer.getByTestId('workflow-list-detail-open')).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /workflows returns from designer to the same URL-backed workspace context', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  const workflowParams = new URLSearchParams()
  workflowParams.set('q', 'Services')
  workflowParams.set('filters', JSON.stringify({ workflow_type: 'complex' }))
  workflowParams.set('sort', JSON.stringify({ key: 'updated_at', order: 'desc' }))
  workflowParams.set('workflow', WORKFLOW.id)
  workflowParams.set('detail', '1')

  await page.goto(`/workflows?${workflowParams.toString()}`, { waitUntil: 'domcontentloaded' })

  await page.getByTestId('workflow-list-detail-open').click()
  await expect(page).toHaveURL(new RegExp(`/workflows/${WORKFLOW.id}`))
  await page.getByRole('button', { name: 'Back' }).click()

  await expect.poll(() => {
    const url = new URL(page.url())
    return JSON.stringify({
      pathname: url.pathname,
      q: url.searchParams.get('q'),
      filters: url.searchParams.get('filters'),
      sort: url.searchParams.get('sort'),
      workflow: url.searchParams.get('workflow'),
      detail: url.searchParams.get('detail'),
    })
  }).toBe(JSON.stringify({
    pathname: '/workflows',
    q: 'Services',
    filters: JSON.stringify({ workflow_type: 'complex' }),
    sort: JSON.stringify({ key: 'updated_at', order: 'desc' }),
    workflow: WORKFLOW.id,
    detail: '1',
  }))
  await expect(page.getByTestId('workflow-list-selected-id')).toHaveText(WORKFLOW.id)
})

test('UI platform: /workflows/executions restores selected execution detail from URL-backed workspace state', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/workflows/executions?status=pending&execution=${WORKFLOW_EXECUTION_DETAIL.id}&detail=1`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Workflow Executions', level: 2 })).toBeVisible()
  await expect(page.getByTestId('workflow-executions-selected-id')).toHaveText(WORKFLOW_EXECUTION_DETAIL.id)
  await expect(page.getByTestId('workflow-executions-selected-input-context')).toContainText(`"${POOL_RUN.pool_id}"`)
  await expect(page.getByTestId('workflow-executions-detail-open')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expect.poll(() => counts.bootstrap).toBe(1)
})

test('UI platform: /workflows/executions keeps mobile catalog readable and opens detail in a drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/workflows/executions', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Workflow Executions', level: 2 })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.getByTestId(`workflow-executions-catalog-item-${WORKFLOW_EXECUTION_DETAIL.id}`).click()

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('workflow-executions-selected-id')).toHaveText(WORKFLOW_EXECUTION_DETAIL.id)
  await expect(detailDrawer.getByTestId('workflow-executions-detail-open')).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /workflows/executions returns from monitor to the same URL-backed diagnostics context', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  const executionParams = new URLSearchParams()
  executionParams.set('status', 'pending')
  executionParams.set('workflow_id', WORKFLOW.id)
  executionParams.set('execution', WORKFLOW_EXECUTION_DETAIL.id)
  executionParams.set('detail', '1')

  await page.goto(`/workflows/executions?${executionParams.toString()}`, {
    waitUntil: 'domcontentloaded',
  })

  await page.getByTestId('workflow-executions-detail-open').click()
  await expect(page).toHaveURL(new RegExp(`/workflows/executions/${WORKFLOW_EXECUTION_DETAIL.id}`))
  await page.getByRole('button', { name: 'Back' }).click()

  await expect.poll(() => {
    const url = new URL(page.url())
    return JSON.stringify({
      pathname: url.pathname,
      status: url.searchParams.get('status'),
      workflow_id: url.searchParams.get('workflow_id'),
      execution: url.searchParams.get('execution'),
      detail: url.searchParams.get('detail'),
    })
  }).toBe(JSON.stringify({
    pathname: '/workflows/executions',
    status: 'pending',
    workflow_id: WORKFLOW.id,
    execution: WORKFLOW_EXECUTION_DETAIL.id,
    detail: '1',
  }))
  await expect(page.getByTestId('workflow-executions-selected-id')).toHaveText(WORKFLOW_EXECUTION_DETAIL.id)
})

test('UI platform: /workflows/:id restores selected node context from URL-backed authoring state', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  await page.goto(`/workflows/${WORKFLOW.id}?node=start`, { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: WORKFLOW.name, level: 2 })).toBeVisible()
  await expect(page.getByTestId('workflow-designer-selected-node')).toHaveText('Selected node: Start')
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /workflows/:id keeps mobile authoring readable and opens platform-owned drawers', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto(`/workflows/${WORKFLOW.id}`, { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: WORKFLOW.name, level: 2 })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Node palette' })).toBeVisible()
  await expectNoHorizontalOverflow(page)

  await page.getByRole('button', { name: 'Node palette' }).click()
  await expect(page.getByTestId('workflow-designer-palette-drawer')).toBeVisible()
  await expect(page.getByText('Scheme Building Blocks')).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(page.getByTestId('workflow-designer-palette-drawer')).toBeHidden()

  await page.getByTestId('rf__node-start').evaluate((element: HTMLElement) => element.click())

  const nodeDrawer = page.getByTestId('workflow-designer-node-drawer')
  await expect(nodeDrawer).toBeVisible()
  await expect(page.getByTestId('workflow-designer-selected-node')).toHaveText('Selected node: Start')
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /workflows/executions/:executionId restores selected node diagnostics from URL-backed workspace state', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  await page.goto(`/workflows/executions/${WORKFLOW_EXECUTION_DETAIL.id}?node=start`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Workflow Execution', level: 2 })).toBeVisible()
  await expect(page.getByTestId('workflow-monitor-selected-node')).toHaveText('Selected node: Start')
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('dialog').getByText('start', { exact: true })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /workflows/executions/:executionId keeps diagnostics readable on mobile and opens node details in a drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto(`/workflows/executions/${WORKFLOW_EXECUTION_DETAIL.id}`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Workflow Execution', level: 2 })).toBeVisible()
  await expect(page.getByText('Execution Info')).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.getByTestId('rf__node-start').evaluate((element: HTMLElement) => element.click())

  const nodeDrawer = page.getByRole('dialog')
  await expect(nodeDrawer).toBeVisible()
  await expect(page.getByTestId('workflow-monitor-selected-node')).toHaveText('Selected node: Start')
  await expect(nodeDrawer.getByText('start', { exact: true })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /pools/topology-templates submits create-template authoring and surfaces the created template in the detail drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto('/pools/topology-templates', { waitUntil: 'domcontentloaded' })

  await page.getByRole('button', { name: 'Create template' }).click()
  await fillTopologyTemplateCreateForm(page)

  const createRequestPromise = page.waitForRequest((request) => (
    request.method() === 'POST'
    && request.url().endsWith('/api/v2/pools/topology-templates/')
  ))
  await page.getByTestId('pool-topology-templates-create-submit').click()

  const createRequest = await createRequestPromise
  const createPayload = createRequest.postDataJSON() as Record<string, unknown>

  expect(createPayload.code).toBe('new-template')
  expect(createPayload.name).toBe('New Template')
  expect(createPayload.description).toBe('Reusable topology authoring surface')
  await expect(page.getByTestId('pool-topology-templates-selected-code')).toHaveText('new-template')
  await expect(page).toHaveURL(/\/pools\/topology-templates\?template=template-\d+&detail=1$/)
  await expect(page.getByRole('button', { name: 'Publish new revision' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /pools/topology-templates submits revise-template authoring and refreshes the selected revision evidence', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto('/pools/topology-templates?template=template-top-down&detail=1', {
    waitUntil: 'domcontentloaded',
  })

  await page.getByRole('button', { name: 'Publish new revision' }).click()
  await fillTopologyTemplateReviseForm(page)

  const reviseRequestPromise = page.waitForRequest((request) => (
    request.method() === 'POST'
    && request.url().endsWith('/api/v2/pools/topology-templates/template-top-down/revisions/')
  ))
  await page.getByTestId('pool-topology-templates-revise-submit').click()

  const reviseRequest = await reviseRequestPromise
  const revisePayload = reviseRequest.postDataJSON() as Record<string, unknown>
  const revision = revisePayload.revision as Record<string, unknown>

  expect(Array.isArray(revision.nodes)).toBe(true)
  expect(Array.isArray(revision.edges)).toBe(true)
  await expect(page).toHaveURL(/\/pools\/topology-templates\?template=template-top-down&detail=1$/)
  await expect(page.getByTestId('pool-topology-templates-selected-code')).toHaveText('top-down-template')
  await expect(page.getByText('Updated Root')).toBeVisible()
  await expect(
    page.locator('table:has(th:has-text("Created at")) tbody tr:not(.ant-table-measure-row)').first()
  ).toContainText('r4')
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(page.getByTestId('pool-topology-templates-detail-surface'), 'Topology template detail surface')
})

test('UI platform: /pools/catalog restores attachment workspace in a mobile-safe drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto(`/pools/catalog?pool_id=${POOL_WITH_ATTACHMENT.id}&tab=bindings`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Pool Catalog', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByTestId('pool-catalog-context-pool')).toHaveText('pool-main - Main Pool')
  const detailDrawer = page.getByTestId('pool-catalog-bindings-drawer')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('pool-catalog-save-bindings')).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /databases restores selected database and management context from a deep-link', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  await page.goto(`/databases?cluster=cluster-1&database=${DATABASE_ID}&context=metadata`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Databases', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByRole('combobox', { name: 'Cluster filter' })).toBeVisible()
  await expect(page.getByRole('button', { name: `Open database ${DATABASE_RECORD.name}` })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('database-workspace-selected-id')).toHaveText(DATABASE_ID, {
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByTestId('database-metadata-management-drawer')).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`\\/databases\\?cluster=cluster-1&database=${DATABASE_ID}&context=metadata$`))
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /databases keeps selected management context on browser back and forward', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  await page.goto(`/databases?database=${DATABASE_ID}&context=inspect`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByTestId('database-workspace-selected-id')).toHaveText(DATABASE_ID, {
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })

  await page.getByTestId('database-workspace-open-credentials').click()
  await expect(page).toHaveURL(new RegExp(`\\/databases\\?database=${DATABASE_ID}&context=credentials$`))
  await expect(page.getByText(`Credentials: ${DATABASE_RECORD.name}`)).toBeVisible()

  await page.goBack()
  await expect(page).toHaveURL(new RegExp(`\\/databases\\?database=${DATABASE_ID}&context=inspect$`))
  await expect(page.getByText(`Database Workspace: ${DATABASE_RECORD.name}`)).toBeVisible()

  await page.goForward()
  await expect(page).toHaveURL(new RegExp(`\\/databases\\?database=${DATABASE_ID}&context=credentials$`))
  await expect(page.getByText(`Credentials: ${DATABASE_RECORD.name}`)).toBeVisible()
})

test('UI platform: /databases opens mobile management context without stacked overlays', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto(`/databases?database=${DATABASE_ID}&context=metadata`, {
    waitUntil: 'domcontentloaded',
  })

  const metadataDrawer = page.getByTestId('database-metadata-management-drawer')
  await expect(metadataDrawer).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(metadataDrawer, 'Database metadata management drawer')
})

test('UI platform: /pools/runs restores selected run and stage from a deep-link', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto(`/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Pool Runs', level: 2 })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Inspect' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('pool-runs-lineage-pool')).toHaveText('pool-main - Main Pool')
  await expect(page.getByTestId('pool-runs-lineage-binding-id')).toHaveText('binding-top-down')
  await expect(page.getByTestId('pool-runs-lineage-slot-coverage')).toContainText('resolved: 1')
  await expect(page.getByRole('button', { name: 'Open Workflow Diagnostics' })).toBeVisible()
})

test('UI platform: /pools/runs keeps selected stage on browser back and forward', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto(`/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('tab', { name: 'Inspect' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('pool-runs-lineage-binding-id')).toHaveText('binding-top-down', { timeout: 15000 })

  await page.getByRole('tab', { name: 'Retry Failed' }).click()
  await expect(page).toHaveURL(new RegExp(`\\/pools\\/runs\\?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=retry&detail=1$`))
  await expect(page.getByRole('tab', { name: 'Retry Failed' })).toHaveAttribute('aria-selected', 'true')

  await page.goBack()
  await expect(page).toHaveURL(new RegExp(`\\/pools\\/runs\\?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1$`))
  await expect(page.getByRole('tab', { name: 'Inspect' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('pool-runs-lineage-binding-id')).toHaveText('binding-top-down')

  await page.goForward()
  await expect(page).toHaveURL(new RegExp(`\\/pools\\/runs\\?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=retry&detail=1$`))
  await expect(page.getByRole('tab', { name: 'Retry Failed' })).toHaveAttribute('aria-selected', 'true')
})

test('UI platform: /pools/runs opens inspect detail in a mobile-safe drawer without page-wide overflow', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto(`/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`, {
    waitUntil: 'domcontentloaded',
  })

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('pool-runs-lineage-pool')).toHaveText('pool-main - Main Pool')
  await expect(detailDrawer.getByRole('button', { name: 'Open Workflow Diagnostics' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /pools/factual restores compact selection and detail workspace from a deep-link', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto(`/pools/factual?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&quarter_start=2026-01-01&focus=settlement&detail=1`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Pool Factual Monitoring', level: 2 })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open factual workspace for Main Pool' })).toBeVisible()
  await expect(page.getByText('Factual operator workspace')).toBeVisible()
  const overallState = page.getByText('Overall state')
  const poolMovement = page.getByText('Pool movement')
  const runLinkedHandoff = page.getByText('Run-linked settlement handoff')
  const syncDiagnostics = page.getByText('Sync diagnostics')
  const executionControls = page.getByText('Execution controls stay in Pool Runs')

  await expect(overallState).toBeVisible()
  await expect(poolMovement).toBeVisible()
  await expect(runLinkedHandoff).toBeVisible()
  await expect(page.getByText('Manual review queue', { exact: true }).last()).toBeVisible()
  await expect(page.getByText('Read backlog has 2 overdue checkpoint(s) on the default sync lane.')).toBeVisible()
  await expect(page.getByText('focus=settlement')).toBeVisible()

  const [overallStateBox, poolMovementBox, runLinkedHandoffBox, syncDiagnosticsBox, executionControlsBox] = await Promise.all([
    overallState.boundingBox(),
    poolMovement.boundingBox(),
    runLinkedHandoff.boundingBox(),
    syncDiagnostics.boundingBox(),
    executionControls.boundingBox(),
  ])

  if (!overallStateBox || !poolMovementBox || !runLinkedHandoffBox || !syncDiagnosticsBox || !executionControlsBox) {
    throw new Error('Expected factual workspace sections to have visible bounding boxes.')
  }

  expect(overallStateBox.y).toBeLessThan(syncDiagnosticsBox.y)
  expect(overallStateBox.y).toBeLessThan(poolMovementBox.y)
  expect(poolMovementBox.y).toBeLessThan(syncDiagnosticsBox.y)
  expect(poolMovementBox.y).toBeLessThan(runLinkedHandoffBox.y)
  expect(runLinkedHandoffBox.y).toBeLessThan(syncDiagnosticsBox.y)
  expect(overallStateBox.y).toBeLessThan(executionControlsBox.y)

  await expectNoHorizontalOverflow(page)
})

test('UI platform: /pools/runs handoff to factual workspace preserves quarter_start', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto(`/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByText('Run Lineage / Operator Report')).toBeVisible({ timeout: 15000 })
  await expect(page.getByRole('button', { name: 'Open factual workspace' })).toBeVisible({ timeout: 15000 })
  await page.getByRole('button', { name: 'Open factual workspace' }).click()

  await expect(page).toHaveURL(
    new RegExp(
      `\\/pools\\/factual\\?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&quarter_start=2026-01-01&focus=settlement&detail=1$`
    )
  )
  await expect(page.getByRole('heading', { name: 'Pool Factual Monitoring', level: 2 })).toBeVisible()
  await expect(page.getByText('Run-linked settlement handoff')).toBeVisible()
})

test('UI platform: /pools/factual opens review detail in a mobile-safe drawer without page-wide overflow', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto(`/pools/factual?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&focus=review&detail=1`, {
    waitUntil: 'domcontentloaded',
  })

  const detailDrawer = page.getByRole('dialog').filter({ hasText: 'Factual operator workspace' }).first()
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByText('Factual operator workspace')).toBeVisible()
  await expect(detailDrawer.getByText('Overall state')).toBeVisible()
  await expect(detailDrawer.getByText('Manual review queue', { exact: true }).last()).toBeVisible()
  await expect(detailDrawer.getByText('review focus')).toBeVisible()
  await expect(detailDrawer.getByRole('button', { name: 'Attribute review item unattributed-pool-main' })).toBeVisible()
  await detailDrawer.getByRole('button', { name: 'Attribute review item unattributed-pool-main' }).click()
  await expect(page.getByText('Choose or confirm attribution targets')).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /pools/factual keeps locale switch, reload, and review modal copy aligned with shell i18n', async ({ page }) => {
  const observedLocaleHeaders: string[] = []
  const localeSelect = page.getByTestId('shell-locale-select')

  await setupAuth(page, { localeOverride: 'ru' })
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { observedLocaleHeaders })

  await page.goto(`/pools/factual?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&focus=review&detail=1`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(localeSelect).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
  await expect(localeSelect).toHaveAttribute('aria-label', 'Язык')
  await expect(page.getByRole('menuitem', { name: 'Факты пулов' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Фактический мониторинг пулов', level: 2 })).toBeVisible()
  await expect(page.getByText('Операторский factual workspace')).toBeVisible()
  await expect(page.getByText('Ручной review', { exact: true }).last()).toBeVisible()
  await expect(page.getByText('Фокус review', { exact: true })).toBeVisible()
  await expect.poll(() => observedLocaleHeaders[0]).toBe('ru')

  await page.getByRole('button', { name: 'Атрибутировать review item unattributed-pool-main' }).click()
  const reviewDialogRu = page.getByRole('dialog')
  await expect(reviewDialogRu).toBeVisible()
  await expect(reviewDialogRu.locator('.ant-modal-title')).toContainText('Подтвердить атрибуцию')
  await expect(reviewDialogRu.getByRole('button', { name: 'Подтвердить атрибуцию' })).toBeVisible()
  await reviewDialogRu.locator('.ant-modal-close').click()
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await switchShellLocaleToEnglish(page)

  await expect(localeSelect).toHaveAttribute('aria-label', 'Language')
  await expect(page.getByRole('menuitem', { name: 'Pool Factual' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Pool Factual Monitoring', level: 2 })).toBeVisible()
  await expect(page.getByText('Factual operator workspace')).toBeVisible()
  await expect(page.getByText('Manual review queue', { exact: true }).last()).toBeVisible()
  await expect(page.getByText('Focus review', { exact: true })).toBeVisible()
  await expect.poll(() => observedLocaleHeaders.at(-1)).toBe('en')

  await page.getByRole('button', { name: 'Attribute review item unattributed-pool-main' }).click()
  const reviewDialogEn = page.getByRole('dialog')
  await expect(reviewDialogEn).toBeVisible()
  await expect(reviewDialogEn.locator('.ant-modal-title')).toContainText('Confirm attribution')
  await expect(reviewDialogEn.getByRole('button', { name: 'Confirm attribution' })).toBeVisible()
  await reviewDialogEn.locator('.ant-modal-close').click()
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await page.reload({ waitUntil: 'domcontentloaded' })

  await expect(localeSelect).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
  await expect(localeSelect).toHaveAttribute('aria-label', 'Language')
  await expect(page.getByRole('menuitem', { name: 'Pool Factual' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Pool Factual Monitoring', level: 2 })).toBeVisible()
  await expect(page.getByText('Factual operator workspace')).toBeVisible()
  await expect(page.getByText('Manual review queue', { exact: true }).last()).toBeVisible()
  await expect(page.getByText('Focus review', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Attribute review item unattributed-pool-main' })).toBeVisible()
  await expect(page.getByText('Ручной review', { exact: true })).toHaveCount(0)
  await expect.poll(() => observedLocaleHeaders.at(-1)).toBe('en')
})

test('UI platform: /operations restores selected operation and inspect context from a deep-link', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  await page.goto(`/operations?operation=${WORKFLOW_OPERATION.id}&tab=inspect`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Operations Monitor', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByRole('button', { name: 'Open operation workflow root execute' })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`)).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByRole('button', { name: 'Timeline' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open workflow diagnostics' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(page.getByTestId('operation-inspect-surface'), 'Operation inspect surface')
})

test('UI platform: /operations keeps selected operation view on browser back and forward', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  await page.goto(`/operations?operation=${WORKFLOW_OPERATION.id}&tab=inspect`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`)).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })

  await page.getByRole('button', { name: 'Timeline' }).click()
  await expect(page).toHaveURL(new RegExp(`\\/operations\\?operation=${WORKFLOW_OPERATION.id}&tab=monitor$`))

  await page.goBack()
  await expect(page).toHaveURL(new RegExp(`\\/operations\\?operation=${WORKFLOW_OPERATION.id}&tab=inspect$`))
  await expect(page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`)).toBeVisible()

  await page.goForward()
  await expect(page).toHaveURL(new RegExp(`\\/operations\\?operation=${WORKFLOW_OPERATION.id}&tab=monitor$`))
})

test('UI platform: /operations opens inspect detail in a mobile-safe drawer without page-wide overflow', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto(`/operations?operation=${WORKFLOW_OPERATION.id}&tab=inspect`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`)).toBeVisible({ timeout: 15000 })
  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expect(detailDrawer.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`)).toBeVisible()
  await expect(detailDrawer.getByRole('button', { name: 'Timeline' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(page.getByTestId('operation-inspect-surface'), 'Operation inspect drawer surface')
})

test('UI platform: /operations renders zero-task diagnostics as empty state instead of completed workload', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  await page.goto(`/operations?operation=${ZERO_TASK_OPERATION.id}&tab=inspect`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByText(`Operation Details: ${ZERO_TASK_OPERATION.name}`)).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByTestId('operation-inspect-no-task-telemetry')).toBeVisible()
  await expect(page.getByText('Task list will appear when runtime reports a task workset for this operation.')).toBeVisible()
  await expect(page.locator('.ant-progress')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /clusters restores selected cluster context and opens edit flow in a canonical modal shell', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page, { localeOverride: 'ru' })
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/clusters?cluster=cluster-1&context=edit&q=Main&status=active', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Кластеры', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  const editModal = page.getByRole('dialog')
  await expect(editModal).toBeVisible()
  await expect(editModal.getByLabel('Имя кластера')).toHaveValue(CLUSTER_RECORD.name)
  await expect(editModal.getByLabel('RAS Host')).toHaveValue(CLUSTER_RECORD.ras_host)
  await expect(editModal.getByRole('button', { name: 'Обновить' })).toBeVisible()
  await expect.poll(() => counts.clusterLists).toBe(1)
  await expect.poll(() => counts.clusterDetails).toBe(1)
  await expectNoHorizontalOverflow(page)
})

test('Runtime contract: /clusters hands off to /databases without replaying shell reads', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page, { localeOverride: 'ru' })
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/clusters?cluster=cluster-1&context=inspect', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Кластеры', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByRole('button', { name: 'Открыть базы' })).toBeVisible()
  await expect.poll(() => counts.clusterLists).toBe(1)
  await expect.poll(() => counts.clusterDetails).toBe(1)

  await page.getByRole('button', { name: 'Открыть базы' }).click()

  await expect(page).toHaveURL(/\/databases\?cluster=cluster-1(?:&.*)?$/)
  await expect(page.getByRole('heading', { name: 'Базы', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
})

test('Runtime contract: /clusters ignores same-route menu re-entry and keeps selected cluster context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page, { localeOverride: 'ru' })
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/clusters?cluster=cluster-1&context=inspect', {
    waitUntil: 'domcontentloaded',
  })

  const clustersMenuItem = page.getByRole('menuitem', { name: /Кластеры/i })

  await expect(page.getByRole('button', { name: 'Открыть базы' })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByText('Primary RAS cluster for shared services')).toBeVisible()
  await expect.poll(() => counts.clusterLists).toBe(1)
  await expect.poll(() => counts.clusterDetails).toBe(1)

  const initialUrl = page.url()
  const initialClusterListReads = counts.clusterLists
  const initialClusterDetailReads = counts.clusterDetails

  await clustersMenuItem.click()
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(initialUrl)
  await expect(page.getByRole('button', { name: 'Открыть базы' })).toBeVisible()
  await expect(page.getByText('Primary RAS cluster for shared services')).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.clusterLists).toBe(initialClusterListReads)
  await expect(counts.clusterDetails).toBe(initialClusterDetailReads)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('UI platform: /clusters opens inspect detail in a mobile-safe drawer without page-wide overflow', async ({ page }) => {
  await setupAuth(page, { localeOverride: 'ru' })
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/clusters?cluster=cluster-1&context=inspect', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Кластеры', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expect(detailDrawer.getByRole('button', { name: 'Открыть базы' })).toBeVisible()
  await expect(detailDrawer.getByText('Primary RAS cluster for shared services')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(detailDrawer, 'Clusters detail drawer')
})

test('Runtime contract: /clusters normalizes unauthorized mutating deep-links to inspect state', async ({ page }) => {
  await setupAuth(page, { localeOverride: 'ru' })
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: false, clusterAccessLevel: 'VIEW' })

  await page.goto('/clusters?cluster=cluster-1&context=edit', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Кластеры', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByRole('button', { name: 'Обновить' })).toHaveCount(0)
  await expect(page.getByText('Primary RAS cluster for shared services')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Редактировать' })).toBeDisabled()
  await expect.poll(() => {
    const currentUrl = new URL(page.url())
    return {
      path: currentUrl.pathname,
      cluster: currentUrl.searchParams.get('cluster'),
      context: currentUrl.searchParams.get('context'),
    }
  }).toEqual({
    path: '/clusters',
    cluster: 'cluster-1',
    context: 'inspect',
  })
})

test('UI platform: /clusters keeps detail loading fail-closed until the detail snapshot arrives', async ({ page }) => {
  await setupAuth(page, { localeOverride: 'ru' })
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, clusterDetailDelayMs: 1500 })

  await page.goto('/clusters?cluster=cluster-1&context=inspect', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Кластеры', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await page.waitForTimeout(200)
  await expect(page.getByText('Для этого snapshot кластера базы не вернулись.')).toHaveCount(0)
  await expect(page.getByText('Метаданные кластера')).toHaveCount(0)
  await expect(page.getByText('Превью баз')).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
  await expect(page.getByText('db-services')).toBeVisible()
})

test('UI platform: /system-status keeps locale switch and reload aligned with the shell i18n context', async ({ page }) => {
  const observedLocaleHeaders: string[] = []
  const localeSelect = page.getByTestId('shell-locale-select')
  const localeSelectTrigger = localeSelect.locator('.ant-select-selector')
  const refreshButtonRu = page.locator('button').filter({ hasText: /^Обновить$/ })
  const refreshButtonEn = page.locator('button').filter({ hasText: /^Refresh$/ })
  const systemStatusMenuItemRu = page.getByRole('menuitem', { name: 'Статус системы' })
  const databasesMenuItemRu = page.getByRole('menuitem', { name: 'Базы' })
  const poolCatalogMenuItemRu = page.getByRole('menuitem', { name: 'Каталог пулов' })
  const systemStatusMenuItemEn = page.getByRole('menuitem', { name: 'System Status' })
  const databasesMenuItemEn = page.getByRole('menuitem', { name: 'Databases' })
  const poolCatalogMenuItemEn = page.getByRole('menuitem', { name: 'Pool Catalog' })

  await setupAuth(page, { localeOverride: 'ru' })
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { observedLocaleHeaders })

  await page.goto('/system-status', { waitUntil: 'domcontentloaded' })

  await expect(localeSelect).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
  await expect(localeSelect).toHaveAttribute('aria-label', 'Язык')
  await expect(refreshButtonRu).toBeVisible()
  await expect(systemStatusMenuItemRu).toBeVisible()
  await expect(databasesMenuItemRu).toBeVisible()
  await expect(poolCatalogMenuItemRu).toBeVisible()
  await expect.poll(() => observedLocaleHeaders[0]).toBe('ru')

  await localeSelectTrigger.click()
  await page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) [title="English"]').click()

  await expect(localeSelect).toHaveAttribute('aria-label', 'Language')
  await expect(refreshButtonEn).toBeVisible()
  await expect(systemStatusMenuItemEn).toBeVisible()
  await expect(databasesMenuItemEn).toBeVisible()
  await expect(poolCatalogMenuItemEn).toBeVisible()
  await expect.poll(() => observedLocaleHeaders.at(-1)).toBe('en')

  await page.reload({ waitUntil: 'domcontentloaded' })

  await expect(localeSelect).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
  await expect(localeSelect).toHaveAttribute('aria-label', 'Language')
  await expect(refreshButtonEn).toBeVisible()
  await expect(systemStatusMenuItemEn).toBeVisible()
  await expect(databasesMenuItemEn).toBeVisible()
  await expect(poolCatalogMenuItemEn).toBeVisible()
  await expect.poll(() => observedLocaleHeaders.at(-1)).toBe('en')
})

for (const localeWaveCase of [
  {
    label: '2.1 /extensions',
    path: '/extensions',
    ruVisible: (page: Page) => page.getByPlaceholder('Поиск по имени расширения'),
    enVisible: (page: Page) => page.getByPlaceholder('Search extension name'),
  },
  {
    label: '2.2 /artifacts',
    path: '/artifacts',
    ruVisible: (page: Page) => page.getByRole('heading', { name: 'Артефакты', level: 2 }),
    enVisible: (page: Page) => page.getByRole('heading', { name: 'Artifacts', level: 2 }),
  },
  {
    label: '2.3 /operations',
    path: '/operations',
    ruVisible: (page: Page) => page.getByRole('heading', { name: 'Монитор операций', level: 2 }),
    enVisible: (page: Page) => page.getByRole('heading', { name: 'Operations Monitor', level: 2 }),
  },
  {
    label: '2.4 /workflows',
    path: '/workflows',
    ruVisible: (page: Page) => page.getByRole('heading', { name: 'Библиотека workflow-схем', level: 2 }),
    enVisible: (page: Page) => page.getByRole('heading', { name: 'Workflow Scheme Library', level: 2 }),
  },
  {
    label: '2.5 /pools/templates',
    path: '/pools/templates',
    ruVisible: (page: Page) => page.getByRole('button', { name: 'Создать шаблон' }),
    enVisible: (page: Page) => page.getByRole('button', { name: 'Create Template' }),
  },
  {
    label: '2.6 /pools/runs',
    path: '/pools/runs',
    ruVisible: (page: Page) => page.getByRole('button', { name: 'Обновить данные' }),
    enVisible: (page: Page) => page.getByRole('button', { name: 'Refresh Data' }),
  },
] as const) {
  test(`UI platform: ${localeWaveCase.label} keeps locale switch and reload aligned with shell i18n`, async ({ page }) => {
    const observedLocaleHeaders: string[] = []
    const localeSelect = page.getByTestId('shell-locale-select')

    await setupAuth(page, { localeOverride: 'ru' })
    await setupPersistentDatabaseStream(page)
    await setupUiPlatformMocks(page, { isStaff: true, observedLocaleHeaders })

    await page.goto(localeWaveCase.path, { waitUntil: 'domcontentloaded' })

    await expect(localeSelect).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
    await expect(localeSelect).toHaveAttribute('aria-label', 'Язык')
    await expect(localeWaveCase.ruVisible(page)).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
    await expect.poll(() => observedLocaleHeaders[0]).toBe('ru')

    await switchShellLocaleToEnglish(page)

    await expect(localeSelect).toHaveAttribute('aria-label', 'Language')
    await expect(localeWaveCase.enVisible(page)).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })

    await page.reload({ waitUntil: 'domcontentloaded' })

    await expect(localeSelect).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
    await expect(localeSelect).toHaveAttribute('aria-label', 'Language')
    await expect(localeWaveCase.enVisible(page)).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
    await expect(localeWaveCase.ruVisible(page)).toHaveCount(0)
    await expect.poll(() => observedLocaleHeaders.at(-1)).toBe('en')
  })
}

test('UI platform: /system-status restores diagnostics context in a mobile-safe drawer with paused polling', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/system-status?service=orchestrator&poll=paused', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'System status', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Resume auto-refresh' })).toBeVisible()
  await expect(detailDrawer).toContainText('orchestrator')
  await expect(detailDrawer.getByText('Delayed queue drain')).toBeVisible()
  await expect.poll(() => counts.systemHealthReads).toBeGreaterThan(0)
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(detailDrawer, 'System status detail drawer')
})

test('Runtime contract: /system-status hands off to /service-mesh without replaying shell reads', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/system-status?service=orchestrator&poll=paused', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'System status', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByText('Delayed queue drain')).toBeVisible()
  await expect.poll(() => counts.systemHealthReads).toBeGreaterThan(0)

  await page.getByRole('button', { name: 'Open service mesh' }).click()

  await expect(page).toHaveURL(/\/service-mesh\?service=orchestrator$/)
  await expect(page.getByRole('heading', { name: 'Service mesh', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByTestId('service-mesh-service-drawer')).toBeVisible()
  await expect.poll(() => counts.serviceHistoryReads).toBeGreaterThan(0)
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
})

test('Runtime contract: /system-status ignores same-route menu re-entry and keeps diagnostics context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/system-status?service=orchestrator&poll=paused', {
    waitUntil: 'domcontentloaded',
  })

  const systemStatusMenuItem = page.getByRole('menuitem', { name: /System status/i })

  await expect(page.getByText('Delayed queue drain')).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect.poll(() => counts.systemHealthReads).toBeGreaterThan(0)

  const initialUrl = page.url()
  const initialSystemHealthReads = counts.systemHealthReads

  await systemStatusMenuItem.click()
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(initialUrl)
  await expect(page.getByText('Delayed queue drain')).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.systemHealthReads).toBe(initialSystemHealthReads)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime control: /system-status exposes scheduler controls for worker-workflows and hands off cadence editing to runtime settings', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, canManageRuntimeControls: true, counts })

  await page.goto('/system-status?service=worker-workflows&tab=scheduler&poll=paused', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'System status', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByText('Global scheduler enablement')).toBeVisible()
  await expect(page.getByText('Pool factual active sync')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Trigger now' }).first()).toBeVisible()
  await expect.poll(() => counts.runtimeControlCatalogReads).toBeGreaterThan(0)
  await expect.poll(() => counts.runtimeControlRuntimeReads).toBeGreaterThan(0)

  await page.getByRole('button', { name: 'Open cadence' }).first().click()

  await expect(page).toHaveURL(/\/settings\/runtime\?setting=runtime\.scheduler\.job\.pool_factual_active_sync\.schedule$/)
  await expect(page.getByRole('heading', { name: 'Runtime Settings', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect.poll(() => counts.runtimeSettingsReads).toBeGreaterThan(0)
})

test('Runtime control: /system-status restores selected scheduler job context from a deep-link', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, canManageRuntimeControls: true, counts })

  await page.goto('/system-status?service=worker-workflows&tab=scheduler&job=pool_factual_closed_quarter_reconcile&poll=paused', {
    waitUntil: 'domcontentloaded',
  })

  const selectedJob = page.getByTestId('system-status-selected-scheduler-job')
  await expect(selectedJob).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(selectedJob).toContainText('Pool factual closed-quarter reconcile')
  await expect(selectedJob).toContainText('0 2 * * *')
  await expect.poll(() => counts.runtimeControlCatalogReads).toBeGreaterThan(0)
  await expect.poll(() => counts.runtimeControlRuntimeReads).toBeGreaterThan(0)

  await selectedJob.getByRole('button', { name: 'Open cadence' }).click()

  await expect(page).toHaveURL(/\/settings\/runtime\?setting=runtime\.scheduler\.job\.pool_factual_closed_quarter_reconcile\.schedule$/)
})

test('Runtime control: /system-status restart action uses a reason-gated modal flow inside diagnostics workspace', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, canManageRuntimeControls: true, counts })

  await page.goto('/system-status?service=orchestrator&tab=controls&poll=paused', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'System status', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByRole('button', { name: 'Restart runtime' })).toBeVisible()

  await page.getByRole('button', { name: 'Restart runtime' }).click()

  const restartDialog = page.getByRole('dialog')
  await expect(restartDialog).toContainText('Restart is a dangerous action and requires an explicit operator reason.')
  await expect(restartDialog.getByRole('button', { name: 'Restart' })).toBeDisabled()

  await restartDialog.getByPlaceholder('Explain why this runtime needs a restart').fill('Rotate runtime after factual scheduler drift')
  await expect(restartDialog.getByRole('button', { name: 'Restart' })).toBeEnabled()
  await restartDialog.getByRole('button', { name: 'Restart' }).click()

  await expect(restartDialog).toHaveCount(0)
  await expect.poll(() => counts.runtimeControlActionWrites).toBeGreaterThan(0)
})

test('Runtime control: /system-status hands off to /service-mesh with canonical runtime keys even when diagnostics labels are title-cased', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, canManageRuntimeControls: true, counts })

  await page.goto('/system-status?service=orchestrator&tab=controls&poll=paused', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'System status', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByRole('button', { name: 'Restart runtime' })).toBeVisible()

  await page.getByRole('button', { name: 'Open service mesh' }).click()

  await expect(page).toHaveURL(/\/service-mesh\?service=orchestrator$/)
  await expect(page.getByRole('heading', { name: 'Service mesh', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByTestId('service-mesh-service-drawer')).toBeVisible()
  await expect.poll(() => counts.serviceHistoryReads).toBeGreaterThan(0)
})

test('Runtime control: /system-status surfaces scheduler run correlation in runtime action history', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, canManageRuntimeControls: true, counts })

  await page.goto('/system-status?service=worker-workflows&tab=scheduler&job=pool_factual_active_sync&poll=paused', {
    waitUntil: 'domcontentloaded',
  })

  const selectedJob = page.getByTestId('system-status-selected-scheduler-job')
  await expect(selectedJob).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await selectedJob.getByRole('button', { name: 'Trigger now' }).click()
  await expect.poll(() => counts.runtimeControlActionWrites).toBeGreaterThan(0)

  await page.getByText('Controls', { exact: true }).click()
  await expect(page.getByText('Scheduler run: #6001')).toBeVisible()
  await expect(page.getByText('pool_factual_active_sync')).toBeVisible()
})

test('Runtime control: /system-status keeps diagnostics-only workspace without runtime-control capability', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, canManageRuntimeControls: false, counts })

  await page.goto('/system-status?service=orchestrator&tab=controls&poll=paused', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'System status', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByText('Delayed queue drain')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Controls' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Restart runtime' })).toHaveCount(0)
  await expect(page.getByText('Runtime control summary')).toHaveCount(0)
  await expect.poll(() => counts.systemHealthReads).toBeGreaterThan(0)
})

test('UI platform: /service-mesh restores selected service context in a mobile-safe drawer', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/service-mesh?service=orchestrator', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Service mesh', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  const serviceDrawer = page.getByTestId('service-mesh-service-drawer')
  await expect(serviceDrawer).toBeVisible()
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expect(serviceDrawer.getByText('Historical Metrics')).toBeVisible()
  await expect(serviceDrawer.locator('.ant-statistic-title').filter({ hasText: 'Ops/min' }).first()).toBeVisible()
  await expect.poll(() => counts.serviceHistoryReads).toBeGreaterThan(0)
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(serviceDrawer, 'Service mesh service drawer')
})

test('UI platform: /service-mesh restores realtime context in a mobile-safe timeline drawer', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto(`/service-mesh?service=orchestrator&operation=${WORKFLOW_OPERATION.id}`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Service mesh', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByText('Operation timeline context restored from the route state.')).toBeVisible()
  const timelineDrawer = page.getByTestId('service-mesh-operation-timeline-drawer')
  await expect(timelineDrawer).toBeVisible()
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expect(timelineDrawer.getByText('Operation Timeline')).toBeVisible()
  await expect(timelineDrawer.getByText(WORKFLOW_OPERATION.id)).toBeVisible()
  await expect.poll(() => counts.operationsList).toBeGreaterThan(0)
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(timelineDrawer, 'Service mesh timeline drawer')
})

test('Runtime contract: /service-mesh ignores same-route menu re-entry and keeps selected service context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/service-mesh?service=orchestrator', {
    waitUntil: 'domcontentloaded',
  })

  const serviceMeshMenuItem = page.getByRole('menuitem', { name: /Service mesh/i })
  const serviceDrawer = page.getByTestId('service-mesh-service-drawer')

  await expect(serviceDrawer).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(serviceDrawer.getByText('Historical Metrics')).toBeVisible()
  await expect.poll(() => counts.serviceHistoryReads).toBeGreaterThan(0)

  const initialUrl = page.url()
  const initialServiceHistoryReads = counts.serviceHistoryReads

  await serviceMeshMenuItem.dispatchEvent('click')
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(initialUrl)
  await expect(serviceDrawer).toBeVisible()
  await expect(serviceDrawer.getByText('Historical Metrics')).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.serviceHistoryReads).toBe(initialServiceHistoryReads)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /service-mesh ignores same-route menu re-entry and keeps realtime context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/service-mesh?service=orchestrator&operation=${WORKFLOW_OPERATION.id}`, {
    waitUntil: 'domcontentloaded',
  })

  const serviceMeshMenuItem = page.getByRole('menuitem', { name: /Service mesh/i })
  const timelineDrawer = page.getByTestId('service-mesh-operation-timeline-drawer')

  await expect(timelineDrawer).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByText('Operation timeline context restored from the route state.')).toBeVisible()
  await expect.poll(() => counts.operationsList).toBeGreaterThan(0)

  const initialUrl = page.url()
  const initialOperationsListReads = counts.operationsList

  await serviceMeshMenuItem.dispatchEvent('click')
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(initialUrl)
  await expect(timelineDrawer).toBeVisible()
  await expect(page.getByText('Operation timeline context restored from the route state.')).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.operationsList).toBe(initialOperationsListReads)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /service-mesh exports websocket owner diagnostics through the UI journal bundle', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto('/service-mesh?service=orchestrator', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Service mesh', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })

  await expect.poll(async () => page.evaluate(() => {
    const bundle = (window as Window & {
      __CC1C_UI_JOURNAL__?: {
        exportBundle: () => {
          events: Array<Record<string, unknown>>
          active_websockets_by_owner: Record<string, Record<string, unknown>>
        }
      }
    }).__CC1C_UI_JOURNAL__?.exportBundle()

    if (!bundle) {
      return null
    }

    return {
      lifecycleEvents: bundle.events.filter(
        (event) => event.event_type === 'websocket.lifecycle' && event.owner === 'serviceMeshManager',
      ),
      ownerSummary: bundle.active_websockets_by_owner.serviceMeshManager ?? null,
    }
  }), {
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  }).toEqual(expect.objectContaining({
    lifecycleEvents: expect.arrayContaining([
      expect.objectContaining({
        owner: 'serviceMeshManager',
        reuse_key: 'service-mesh:global',
        channel_kind: 'shared',
        outcome: 'connect',
      }),
    ]),
    ownerSummary: expect.objectContaining({
      active_connection_count: 1,
    }),
  }))
})

test('UI platform: /rbac restores selected mode and tab from URL-backed governance workspace state', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  await page.goto('/rbac?mode=roles&tab=audit', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'RBAC', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByTestId('rbac-tab-roles')).toBeVisible()
  await expect(page.getByTestId('rbac-tab-audit')).toBeVisible()
  await expect(page.getByTestId('rbac-tab-permissions')).toHaveCount(0)
  await expect(page.getByTestId('rbac-audit-panel')).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /users restores selected user context outside the current catalog slice and opens edit flow in a canonical modal shell', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, {
    isStaff: true,
    counts,
    selectedUserOutsideCatalogSlice: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto(`/users?user=${ADMIN_USER.id}&context=edit`, { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Users', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByTestId('users-selected-username')).toContainText(ADMIN_USER.username)
  const editModal = page.getByRole('dialog')
  await expect(editModal).toBeVisible()
  await expect(editModal.getByLabel('Username')).toHaveValue(ADMIN_USER.username)
  await expect(editModal.getByRole('button', { name: 'Save' })).toBeVisible()
  await expect.poll(() => counts.usersDetail).toBe(1)
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /dlq preserves selected message context outside the current catalog slice and hands off to /operations without leaving the SPA shell', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, {
    isStaff: true,
    counts,
    selectedDlqOutsideCatalogSlice: true,
  })

  await page.goto(`/dlq?message=${DLQ_MESSAGE.dlq_message_id}`, { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'DLQ', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  const detailDrawer = page.getByTestId('dlq-message-detail-drawer')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByText(DLQ_MESSAGE.error_message)).toBeVisible()
  await expect.poll(() => counts.dlqDetail).toBe(1)
  await detailDrawer.getByRole('button', { name: 'Open in Operations' }).click()

  await expect(page).toHaveURL(new RegExp(`\\/operations\\?tab=monitor&operation=${WORKFLOW_OPERATION.id}$`))
  await expect(page.getByRole('heading', { name: 'Operations Monitor', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
})

test('UI platform: /artifacts restores deleted catalog tab and selected artifact detail outside the current catalog slice in a mobile-safe drawer', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, {
    isStaff: true,
    counts,
    selectedArtifactOutsideCatalogSlice: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto(`/artifacts?tab=deleted&artifact=${DELETED_ARTIFACT.id}&context=inspect`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Artifacts', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByText('tab=deleted')).toBeVisible()
  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByText(DELETED_ARTIFACT.name)).toBeVisible()
  await expect(detailDrawer.getByRole('button', { name: 'Delete permanently' })).toBeVisible()
  await expect.poll(() => counts.artifactDetail).toBe(1)
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /extensions restores selected extension context in a mobile-safe secondary drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto(`/extensions?extension=ServicePublisher&database=${DATABASE_ID}`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Extensions', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  const detailDrawer = page.getByTestId('extensions-management-drawer')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('extensions-selected-name')).toHaveText('ServicePublisher')
  await expect(detailDrawer.getByTestId('extensions-selected-database')).toHaveText(DATABASE_RECORD.name)
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(detailDrawer, 'Extensions management drawer')
})

test('UI platform: /settings/runtime restores selected setting context in a canonical settings drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/settings/runtime?setting=runtime.concurrency.max_workers&context=setting', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Runtime Settings', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByTestId('runtime-settings-page')).toBeVisible()
  const detailDrawer = page.getByTestId('runtime-settings-detail-drawer')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByText('runtime.concurrency.max_workers')).toBeVisible()
  await expect(detailDrawer.getByRole('button', { name: 'Save' })).toBeVisible()
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expectNoHorizontalOverflow(page)
})

test('UI platform: /settings/timeline keeps diagnostics in a single mobile-safe secondary drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/settings/timeline?context=diagnostics', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Timeline Settings', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByTestId('timeline-settings-page')).toBeVisible()
  const diagnosticsDrawer = page.getByTestId('timeline-settings-diagnostics-drawer')
  await expect(diagnosticsDrawer).toBeVisible()
  await expect(diagnosticsDrawer.getByText('Active mux streams: 2/16')).toBeVisible()
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expectNoHorizontalOverflow(page)
  await expectNoScopedHorizontalOverflow(diagnosticsDrawer, 'Timeline settings diagnostics drawer')
})

test('UI platform: /settings/command-schemas restores driver, mode, and selected command in a mobile-safe detail drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/settings/command-schemas?driver=ibcmd&mode=guided&command=ibcmd.publish', {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Command Schemas', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByTestId('command-schemas-page')).toBeVisible()
  await expect(page.getByTestId('command-schemas-command-ibcmd.publish')).toHaveAttribute('aria-current', 'true')
  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByText('Publish infobase')).toBeVisible()
  await expect(page.locator('.ant-drawer-content-wrapper:visible')).toHaveCount(1)
  await expectNoHorizontalOverflow(page)
})

test('Runtime contract: /extensions ignores same-route menu re-entry and keeps selected extension context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/extensions?extension=ServicePublisher&database=${DATABASE_ID}`, {
    waitUntil: 'domcontentloaded',
  })

  const extensionsMenuItem = page.getByRole('menuitem', { name: /Extensions/i })
  const detailDrawer = page.getByTestId('extensions-management-drawer')

  await expect(detailDrawer).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
  await expect(detailDrawer.getByTestId('extensions-selected-name')).toHaveText('ServicePublisher')
  await expect.poll(() => counts.extensionsOverview).toBeGreaterThan(0)
  await expect.poll(() => counts.extensionsOverviewDatabases).toBeGreaterThan(0)
  await expect.poll(() => counts.extensionsManualBindings).toBeGreaterThan(0)

  const initialUrl = page.url()
  const initialOverviewReads = counts.extensionsOverview
  const initialOverviewDatabasesReads = counts.extensionsOverviewDatabases
  const initialManualBindingsReads = counts.extensionsManualBindings

  await extensionsMenuItem.dispatchEvent('click')
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(initialUrl)
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('extensions-selected-name')).toHaveText('ServicePublisher')
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.extensionsOverview).toBe(initialOverviewReads)
  await expect(counts.extensionsOverviewDatabases).toBe(initialOverviewDatabasesReads)
  await expect(counts.extensionsManualBindings).toBe(initialManualBindingsReads)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /settings/runtime ignores same-route menu re-entry and keeps selected setting context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/settings/runtime?setting=runtime.concurrency.max_workers&context=setting', {
    waitUntil: 'domcontentloaded',
  })

  const runtimeSettingsMenuItem = page.getByRole('menuitem', { name: /Runtime Settings/i })
  const detailDrawer = page.getByTestId('runtime-settings-detail-drawer')

  await expect(detailDrawer).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
  await expect(detailDrawer.getByText('runtime.concurrency.max_workers')).toBeVisible()
  await expect.poll(() => counts.runtimeSettingsReads).toBeGreaterThan(0)

  const initialUrl = page.url()
  const initialRuntimeSettingsReads = counts.runtimeSettingsReads

  await runtimeSettingsMenuItem.dispatchEvent('click')
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(initialUrl)
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByText('runtime.concurrency.max_workers')).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.runtimeSettingsReads).toBe(initialRuntimeSettingsReads)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /settings/timeline ignores same-route menu re-entry and keeps diagnostics context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/settings/timeline?context=diagnostics', {
    waitUntil: 'domcontentloaded',
  })

  const timelineSettingsMenuItem = page.getByRole('menuitem', { name: /Timeline Settings/i })
  const diagnosticsDrawer = page.getByTestId('timeline-settings-diagnostics-drawer')

  await expect(diagnosticsDrawer).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS })
  await expect(diagnosticsDrawer.getByText('Active mux streams: 2/16')).toBeVisible()
  await expect.poll(() => counts.runtimeSettingsReads).toBeGreaterThan(0)
  await expect.poll(() => counts.streamMuxStatusReads).toBeGreaterThan(0)

  const initialUrl = page.url()
  const initialRuntimeSettingsReads = counts.runtimeSettingsReads
  const initialStreamMuxStatusReads = counts.streamMuxStatusReads

  await timelineSettingsMenuItem.dispatchEvent('click')
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(initialUrl)
  await expect(diagnosticsDrawer).toBeVisible()
  await expect(diagnosticsDrawer.getByText('Active mux streams: 2/16')).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.runtimeSettingsReads).toBe(initialRuntimeSettingsReads)
  await expect(counts.streamMuxStatusReads).toBe(initialStreamMuxStatusReads)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /settings/command-schemas ignores same-route menu re-entry and keeps selected command context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/settings/command-schemas?driver=ibcmd&mode=guided&command=ibcmd.publish', {
    waitUntil: 'domcontentloaded',
  })

  const commandSchemasMenuItem = page.getByRole('menuitem', { name: /Command Schemas/i })
  const selectedCommand = page.getByTestId('command-schemas-command-ibcmd.publish')

  await expect(selectedCommand).toHaveAttribute('aria-current', 'true', { timeout: ROUTE_MOUNT_TIMEOUT_MS })
  await expect(page.getByText('Publish infobase')).toBeVisible()
  await expect.poll(() => counts.commandSchemasEditorReads).toBeGreaterThan(0)

  const initialUrl = page.url()
  const initialCommandSchemasReads = counts.commandSchemasEditorReads

  await commandSchemasMenuItem.dispatchEvent('click')
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(initialUrl)
  await expect(selectedCommand).toHaveAttribute('aria-current', 'true')
  await expect(page.getByText('Publish infobase')).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.commandSchemasEditorReads).toBe(initialCommandSchemasReads)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /decisions avoids mount-time waterfall and duplicate notifications on the default path', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/decisions', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Decision Policy Library')).toBeVisible()
  await expect(page.getByText('Services publication policy').first()).toBeVisible()

  await expect.poll(() => counts.bootstrap).toBe(1)
  await expect.poll(() => counts.streamTickets).toBe(1)
  await expect.poll(() => counts.databaseLists).toBe(1)
  await expect.poll(() => counts.metadataManagementReads).toBe(1)
  await expect.poll(() => counts.decisionsScoped).toBe(1)
  await expect.poll(() => counts.decisionsUnscoped).toBe(0)
  await expect.poll(() => counts.organizationPools).toBe(0)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /pools/execution-packs keeps usage scoped without broad pool scans', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/pools/execution-packs', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Execution Packs')).toBeVisible()
  await expect.poll(() => counts.bindingProfileDetails).toBe(1)
  await expect.poll(() => counts.organizationPools).toBe(0)

  await page.getByRole('button', { name: 'Load attachment usage' }).click()

  await expect.poll(() => counts.organizationPools).toBe(0)
  await expect(counts.bindingProfileDetails).toBe(1)
  await expect(page.getByText('Main Pool')).toBeVisible()
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /pools/catalog keeps the default mount within a single initial read budget', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/pools/catalog', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Pool Catalog', level: 2 })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Pools' })).toHaveAttribute('aria-selected', 'true')
  await expect(page).toHaveURL(/\/pools\/catalog\?pool_id=.*&tab=pools&date=2026-01-01$/)

  await expect.poll(() => counts.poolOrganizations).toBe(1)
  await expect.poll(() => counts.poolOrganizationDetails).toBe(1)
  await expect.poll(() => counts.organizationPools).toBe(1)
  await expect.poll(() => counts.poolTopologySnapshots).toBe(1)
  await expect.poll(() => counts.poolGraphs).toBe(1)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /pools/execution-packs hands off to /pools/catalog without replaying shell reads', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/pools/execution-packs', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Execution Packs')).toBeVisible()
  await expect.poll(() => counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)

  await page.getByRole('button', { name: 'Load attachment usage' }).click()
  await page.getByRole('button', { name: 'Open pool attachment' }).click()

  await expect(page).toHaveURL(/\/pools\/catalog\?pool_id=pool-1&tab=bindings(?:&date=2026-01-01)?$/)
  await expect(page.getByRole('heading', { name: 'Pool Catalog', level: 2 })).toBeVisible()
  await expect(page.getByTestId('pool-catalog-context-pool')).toHaveText('pool-main - Main Pool')
  await expect(page.getByTestId('pool-catalog-bindings-drawer')).toBeVisible()

  await expect(counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
  await expect.poll(() => counts.organizationPools).toBe(1)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /pools/catalog creates a reusable topology template through handoff and restores the same topology task without replaying shell reads', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/pools/catalog?pool_id=pool-1&tab=topology&date=2026-01-01', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Pool Catalog', level: 2 })).toBeVisible()
  await expect.poll(() => counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
  await expect(page.getByTestId('pool-catalog-open-topology-template-workspace')).toBeVisible()

  await page.getByTestId('pool-catalog-open-topology-template-workspace').click()

  await expect(page).toHaveURL(/\/pools\/topology-templates\?/)
  await expect.poll(() => {
    const url = new URL(page.url())
    return {
      return_pool_id: url.searchParams.get('return_pool_id'),
      return_tab: url.searchParams.get('return_tab'),
      return_date: url.searchParams.get('return_date'),
      template: url.searchParams.get('template'),
      compose: url.searchParams.get('compose'),
    }
  }).toEqual({
    return_pool_id: 'pool-1',
    return_tab: 'topology',
    return_date: '2026-01-01',
    template: 'template-top-down',
    compose: null,
  })
  await expect(page.getByRole('heading', { name: 'Topology Templates', level: 2 })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: 'Create template' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()

  const createRequestPromise = page.waitForRequest((request) => (
    request.method() === 'POST'
    && request.url().endsWith('/api/v2/pools/topology-templates/')
  ))
  await fillTopologyTemplateCreateForm(page)
  await page.getByTestId('pool-topology-templates-create-submit').click()
  const createRequest = await createRequestPromise
  const createPayload = createRequest.postDataJSON() as Record<string, unknown>

  expect(createPayload.code).toBe('new-template')
  await expect(page.getByTestId('pool-topology-templates-selected-code')).toHaveText('new-template')

  await page.getByRole('button', { name: 'Return to pool topology' }).click()

  await expect(page).toHaveURL(/\/pools\/catalog\?pool_id=pool-1&tab=topology&date=2026-01-01$/)
  await expect(page.getByRole('heading', { name: 'Pool Catalog', level: 2 })).toBeVisible()
  await expect(page.getByTestId('pool-catalog-context-pool')).toHaveText('pool-main - Main Pool')
  await expect(page.getByRole('tab', { name: 'Topology Editor' })).toHaveAttribute('aria-selected', 'true')
  await page.getByTestId('pool-catalog-topology-authoring-mode').click()
  await selectVisibleAntdOption(page, 'Template-based instantiation')
  await expect(page.getByTestId('pool-catalog-topology-authoring-mode')).toContainText('Template-based instantiation')
  await expect(page.getByText('Template-based path is the preferred reuse flow')).toBeVisible()
  await expect(page.getByTestId('pool-catalog-topology-template-revision')).toBeVisible()
  await page.getByTestId('pool-catalog-topology-template-revision').click()
  await expect(
    page.locator('.ant-select-dropdown:visible .ant-select-item-option-content', { hasText: 'New Template · r1' }).first()
  ).toBeVisible()

  await expect(counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /pools/catalog generic Open topology templates CTA preserves topology return context', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/pools/catalog?pool_id=pool-1&tab=topology&date=2026-01-01', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Pool Catalog', level: 2 })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open topology templates' })).toBeVisible()

  await page.getByRole('button', { name: 'Open topology templates' }).click()

  await expect(page).toHaveURL(/\/pools\/topology-templates\?return_pool_id=pool-1&return_tab=topology&return_date=2026-01-01$/)
  await expect(page.getByRole('heading', { name: 'Topology Templates', level: 2 })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Return to pool topology' })).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
})

test('Runtime contract: /pools/catalog publishes a topology template revision through handoff and exposes it in consumer selection', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/pools/catalog?pool_id=pool-1&tab=topology&date=2026-01-01', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Pool Catalog', level: 2 })).toBeVisible()
  await page.getByTestId('pool-catalog-topology-authoring-mode').click()
  await selectVisibleAntdOption(page, 'Template-based instantiation')
  await expect(page.getByTestId('pool-catalog-topology-authoring-mode')).toContainText('Template-based instantiation')
  await page.getByTestId('pool-catalog-topology-template-revision').click()
  await selectVisibleAntdOption(page, 'Top Down Template · r3')
  await page.getByTestId('pool-catalog-revise-topology-template').click()

  await expect(page).toHaveURL(/\/pools\/topology-templates\?template=template-top-down&detail=1&compose=revise&return_pool_id=pool-1&return_tab=topology&return_date=2026-01-01$/)
  await expect(page.getByTestId('pool-topology-templates-revise-drawer')).toBeVisible()

  const reviseRequestPromise = page.waitForRequest((request) => (
    request.method() === 'POST'
    && request.url().endsWith('/api/v2/pools/topology-templates/template-top-down/revisions/')
  ))
  await fillTopologyTemplateReviseForm(page)
  await page.getByTestId('pool-topology-templates-revise-submit').click()
  const reviseRequest = await reviseRequestPromise
  const revisePayload = reviseRequest.postDataJSON() as Record<string, unknown>

  expect(Array.isArray((revisePayload.revision as Record<string, unknown>).nodes)).toBe(true)
  await expect(
    page.locator('table:has(th:has-text("Created at")) tbody tr:not(.ant-table-measure-row)').first()
  ).toContainText('r4')

  await page.getByRole('button', { name: 'Return to pool topology' }).click()

  await expect(page).toHaveURL(/\/pools\/catalog\?pool_id=pool-1&tab=topology&date=2026-01-01$/)
  await expect(page.getByRole('tab', { name: 'Topology Editor' })).toHaveAttribute('aria-selected', 'true')
  await page.getByTestId('pool-catalog-topology-authoring-mode').click()
  await selectVisibleAntdOption(page, 'Template-based instantiation')
  await expect(page.getByTestId('pool-catalog-topology-authoring-mode')).toContainText('Template-based instantiation')
  await expect(page.getByText('Template-based path is the preferred reuse flow')).toBeVisible()
  await expect(page.getByTestId('pool-catalog-topology-template-revision')).toBeVisible()
  await page.getByTestId('pool-catalog-topology-template-revision').click()
  await expect(
    page.locator('.ant-select-dropdown:visible .ant-select-item-option-content', { hasText: 'Top Down Template · r4' }).first()
  ).toBeVisible()

  await expect(counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /pools/runs hands off to workflow diagnostics without replaying shell reads', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Pool Runs', level: 2 })).toBeVisible()
  await expect.poll(() => counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)

  await page.getByRole('button', { name: 'Open Workflow Diagnostics' }).click()

  await expect(page).toHaveURL(`/workflows/executions/${POOL_RUN.workflow_execution_id}`)
  await expect(page.getByText('Workflow Execution')).toBeVisible()
  await expect(page.getByText('Execution Info')).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
})

test('Runtime contract: /databases hands off to /operations without replaying shell reads', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/databases?database=${DATABASE_ID}&context=inspect`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Databases', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect.poll(() => counts.bootstrap).toBe(1)
  await expect.poll(() => counts.databaseLists).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)

  await page.getByTestId('database-workspace-open-operations').click()

  await expect(page).toHaveURL(new RegExp(`\\/operations\\?wizard=true&databases=${DATABASE_ID}$`))
  await expect(page.getByRole('heading', { name: 'Operations Monitor', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
})

test('Runtime contract: /operations hands off to workflow diagnostics without replaying shell reads', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/operations?operation=${WORKFLOW_OPERATION.id}&tab=inspect`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('heading', { name: 'Operations Monitor', level: 2 })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect.poll(() => counts.bootstrap).toBe(1)
  await expect.poll(() => counts.operationsList).toBe(1)
  await expect.poll(() => counts.operationDetails).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)

  await page.getByRole('button', { name: 'Open workflow diagnostics' }).click()

  await expect(page).toHaveURL(`/workflows/executions/${POOL_RUN.workflow_execution_id}`)
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
})

test('Runtime contract: /operations ignores same-route menu re-entry and keeps inspect context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/operations?operation=${WORKFLOW_OPERATION.id}&tab=inspect`, {
    waitUntil: 'domcontentloaded',
  })

  const operationsMenuItem = page.getByRole('menuitem', { name: /Operations/i })

  await expect(page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`)).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect.poll(() => counts.operationsList).toBe(1)
  await expect.poll(() => counts.operationDetails).toBe(1)

  await operationsMenuItem.click()
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(new RegExp(`\\/operations\\?operation=${WORKFLOW_OPERATION.id}&tab=inspect$`))
  await expect(page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`)).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.operationsList).toBe(1)
  await expect(counts.operationDetails).toBe(1)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: / ignores same-route menu re-entry and keeps dashboard shell stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto('/', { waitUntil: 'domcontentloaded' })

  const dashboardMenuItem = page.getByRole('menuitem', { name: /Dashboard/i })

  await expect(page.getByRole('heading', { name: 'Dashboard', level: 2 })).toBeVisible()
  await expect.poll(() => counts.bootstrap).toBe(1)
  await expect.poll(() => counts.operationsList).toBeGreaterThan(0)
  await expect.poll(() => counts.databaseLists).toBeGreaterThan(0)
  await expect.poll(() => counts.clusterLists).toBeGreaterThan(0)

  const initialOperationsList = counts.operationsList
  const initialDatabaseLists = counts.databaseLists
  const initialClusterLists = counts.clusterLists

  await dashboardMenuItem.click()
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('heading', { name: 'Dashboard', level: 2 })).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.operationsList).toBe(initialOperationsList)
  await expect(counts.databaseLists).toBe(initialDatabaseLists)
  await expect(counts.clusterLists).toBe(initialClusterLists)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /databases ignores same-route menu re-entry and keeps management context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/databases?database=${DATABASE_ID}&context=inspect`, {
    waitUntil: 'domcontentloaded',
  })

  const databasesMenuItem = page.getByRole('menuitem', { name: /Databases/i })

  await expect(page.getByText(`Database Workspace: ${DATABASE_RECORD.name}`)).toBeVisible({ timeout: 15000 })
  await expect(page.getByTestId('database-workspace-selected-id')).toHaveText(DATABASE_ID, { timeout: 15000 })
  await expect.poll(() => counts.databaseLists).toBe(1)
  await expect.poll(() => counts.clusterLists).toBe(1)
  await expect(counts.metadataManagementReads).toBe(0)

  await databasesMenuItem.click()
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(new RegExp(`\\/databases\\?database=${DATABASE_ID}&context=inspect$`))
  await expect(page.getByTestId('database-workspace-selected-id')).toHaveText(DATABASE_ID)
  await expect(page.getByText(`Database Workspace: ${DATABASE_RECORD.name}`)).toBeVisible()
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.databaseLists).toBe(1)
  await expect(counts.clusterLists).toBe(1)
  await expect(counts.metadataManagementReads).toBe(0)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /pools/catalog ignores same-route menu re-entry and keeps attachment context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/pools/catalog?pool_id=${POOL_WITH_ATTACHMENT.id}&tab=pools&date=2026-01-01`, {
    waitUntil: 'domcontentloaded',
  })

  const poolCatalogMenuItem = page.getByRole('menuitem', { name: /Pool Catalog/i })

  await expect(page.getByTestId('pool-catalog-context-pool')).toHaveText('pool-main - Main Pool')
  await expect(page.getByRole('tab', { name: 'Pools' })).toHaveAttribute('aria-selected', 'true')
  await expect.poll(() => counts.organizationPools).toBe(1)
  await expect.poll(() => counts.poolOrganizations).toBe(1)
  await expect.poll(() => counts.poolOrganizationDetails).toBe(1)
  await expect.poll(() => counts.poolTopologySnapshots).toBe(1)
  await expect.poll(() => counts.poolGraphs).toBe(1)

  await poolCatalogMenuItem.click()
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(new RegExp(`\\/pools\\/catalog\\?pool_id=${POOL_WITH_ATTACHMENT.id}&tab=pools&date=2026-01-01$`))
  await expect(page.getByTestId('pool-catalog-context-pool')).toHaveText('pool-main - Main Pool')
  await expect(page.getByRole('tab', { name: 'Pools' })).toHaveAttribute('aria-selected', 'true')
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.organizationPools).toBe(1)
  await expect(counts.poolOrganizations).toBe(1)
  await expect(counts.poolOrganizationDetails).toBe(1)
  await expect(counts.poolTopologySnapshots).toBe(1)
  await expect(counts.poolGraphs).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /pools/runs ignores same-route menu re-entry and keeps inspect context stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`, {
    waitUntil: 'domcontentloaded',
  })

  const poolRunsMenuItem = page.getByRole('menuitem', { name: /Pool Runs/i })

  await expect(page.getByRole('tab', { name: 'Inspect' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('pool-runs-lineage-binding-id')).toHaveText('binding-top-down')
  await expect.poll(() => counts.organizationPools).toBe(1)
  await expect.poll(() => counts.poolGraphs).toBeGreaterThan(0)
  await expect.poll(() => counts.poolRuns).toBeGreaterThan(0)
  await expect.poll(() => counts.poolRunReports).toBeGreaterThan(0)

  const initialUrl = page.url()
  const initialPoolGraphs = counts.poolGraphs
  const initialPoolRuns = counts.poolRuns
  const initialPoolRunReports = counts.poolRunReports

  await poolRunsMenuItem.click()
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(initialUrl)
  await expect(page.getByRole('tab', { name: 'Inspect' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('pool-runs-lineage-binding-id')).toHaveText('binding-top-down')
  await expect(counts.bootstrap).toBe(1)
  await expect(counts.organizationPools).toBe(1)
  await expect(counts.poolGraphs).toBe(initialPoolGraphs)
  await expect(counts.poolRuns).toBe(initialPoolRuns)
  await expect(counts.poolRunReports).toBe(initialPoolRunReports)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('Runtime contract: /decisions hands off to /pools/execution-packs without replaying shell reads', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/decisions?database=${DATABASE_ID}&decision=${DECISION.id}`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByText('Decision Policy Library')).toBeVisible()
  await expect.poll(() => counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)

  await page.getByRole('button', { name: 'Open execution packs' }).click()

  await expect(page).toHaveURL(/\/pools\/execution-packs$/)
  await expect(page.getByRole('heading', { name: 'Execution Packs' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create execution pack' })).toBeVisible()

  await expect(counts.bootstrap).toBe(1)
  await expect(counts.meReads).toBe(0)
  await expect(counts.myTenantsReads).toBe(0)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('UI platform: /decisions restores deep-link context and keeps diagnostics behind disclosure', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto(`/decisions?database=${DATABASE_ID}&decision=${FALLBACK_DECISION.id}&snapshot=all`, {
    waitUntil: 'domcontentloaded',
  })

  await expect(page.getByRole('combobox', { name: 'Target database' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open decision Fallback services publication policy' })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('button', { name: 'Show matching configuration only' })).toBeVisible()
  await expect(page.getByText('shared_scope')).toHaveCount(0)

  await page.getByRole('button', { name: /Target metadata context/i }).click()

  await expect(page.getByText('shared_scope')).toBeVisible()
  await expect(page.getByText('snapshot-shared-services')).toBeVisible()
})

test('UI platform: /decisions keeps selected revision on browser back and forward', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto(`/decisions?database=${DATABASE_ID}&decision=${DECISION.id}`, {
    waitUntil: 'domcontentloaded',
  })

  const primaryDecisionButton = page.getByRole('button', { name: `Open decision ${DECISION.name}` })
  const fallbackDecisionButton = page.getByRole('button', { name: `Open decision ${FALLBACK_DECISION.name}` })

  await expect(primaryDecisionButton).toHaveAttribute('aria-pressed', 'true')

  await fallbackDecisionButton.click()

  await expect(page).toHaveURL(new RegExp(`\\?database=${DATABASE_ID}&decision=${FALLBACK_DECISION.id}$`))
  await expect(fallbackDecisionButton).toHaveAttribute('aria-pressed', 'true')

  await page.goBack()

  await expect(page).toHaveURL(new RegExp(`\\?database=${DATABASE_ID}&decision=${DECISION.id}$`))
  await expect(primaryDecisionButton).toHaveAttribute('aria-pressed', 'true')

  await page.goForward()

  await expect(page).toHaveURL(new RegExp(`\\?database=${DATABASE_ID}&decision=${FALLBACK_DECISION.id}$`))
  await expect(fallbackDecisionButton).toHaveAttribute('aria-pressed', 'true')
})

test('Runtime contract: /decisions ignores same-route menu re-entry and keeps catalog state stable', async ({ page }) => {
  const counts = createRequestCounts()

  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true, counts })

  await page.goto(`/decisions?database=${DATABASE_ID}&decision=${DECISION.id}`, {
    waitUntil: 'domcontentloaded',
  })

  const decisionsMenuItem = page.getByRole('menuitem', { name: /Decisions/i })
  const primaryDecisionButton = page.getByRole('button', { name: `Open decision ${DECISION.name}` })

  await expect(primaryDecisionButton).toHaveAttribute('aria-pressed', 'true')
  await expect.poll(() => counts.databaseLists).toBe(1)
  await expect.poll(() => counts.metadataManagementReads).toBe(1)
  await expect.poll(() => counts.decisionsScoped).toBe(1)

  await decisionsMenuItem.click()
  await page.waitForTimeout(750)

  await expect(page).toHaveURL(new RegExp(`\\?database=${DATABASE_ID}&decision=${DECISION.id}$`))
  await expect(primaryDecisionButton).toHaveAttribute('aria-pressed', 'true')
  await expect(counts.databaseLists).toBe(1)
  await expect(counts.metadataManagementReads).toBe(1)
  await expect(counts.decisionsScoped).toBe(1)
  await expect(counts.decisionsUnscoped).toBe(0)
  await expect(page.getByText('Request Error')).toHaveCount(0)
})

test('UI platform: /pools/execution-packs restores catalog context and keeps selection keyboard-first', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto('/pools/execution-packs?q=legacy&profile=bp-legacy&detail=1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Execution Packs', level: 2 })).toBeVisible({ timeout: 15000 })
  await expect(page.getByLabel('Search execution packs')).toHaveValue('legacy', { timeout: 15000 })
  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('legacy-archive', { timeout: 15000 })
  await expect(page.getByText('legacy_archive · r1')).toBeVisible()
  await expect(page.getByText('Workflow definition key')).toHaveCount(0)

  await page.goto('/pools/execution-packs', { waitUntil: 'domcontentloaded' })

  const legacyProfileButton = page.getByRole('button', { name: 'Open execution pack legacy-archive' })
  await legacyProfileButton.focus()
  await page.keyboard.press('Enter')

  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('legacy-archive')
  await expect(legacyProfileButton).toHaveAttribute('aria-pressed', 'true')
})

test('UI platform: /pools/execution-packs keeps selected profile on browser back and forward', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page)

  await page.goto(`/pools/execution-packs?profile=${BINDING_PROFILE_DETAIL.binding_profile_id}`, {
    waitUntil: 'domcontentloaded',
  })

  const servicesProfileButton = page.getByRole('button', { name: 'Open execution pack services-publication' })
  const legacyProfileButton = page.getByRole('button', { name: 'Open execution pack legacy-archive' })

  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('services-publication')
  await expect(servicesProfileButton).toHaveAttribute('aria-pressed', 'true')

  await legacyProfileButton.click()

  await expect(page).toHaveURL(new RegExp(`\\?profile=${LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id}&detail=1$`))
  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('legacy-archive')
  await expect(legacyProfileButton).toHaveAttribute('aria-pressed', 'true')

  await page.goBack()

  await expect(page).toHaveURL(new RegExp(`\\?profile=${BINDING_PROFILE_DETAIL.binding_profile_id}$`))
  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('services-publication')
  await expect(servicesProfileButton).toHaveAttribute('aria-pressed', 'true')

  await page.goForward()

  await expect(page).toHaveURL(new RegExp(`\\?profile=${LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id}&detail=1$`))
  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('legacy-archive')
  await expect(legacyProfileButton).toHaveAttribute('aria-pressed', 'true')
})

test('UI platform: /pools/execution-packs keeps shell labels accessible and primary states above contrast floor', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })

  await page.goto('/pools/execution-packs', { waitUntil: 'domcontentloaded' })

  const streamStatusButton = page.getByRole('button', { name: 'Stream: Connected' })
  const selectedMenuItem = page.getByRole('menuitem', { name: /Pool Execution Packs/i })
  const subtitle = page.getByText(/Reusable execution-pack workspace for selecting an execution pack/i).first()
  const createProfileButton = page.getByRole('button', { name: 'Create execution pack' })
  const deactivateProfileButton = page.getByRole('button', { name: 'Deactivate execution pack' })
  const activeStatusBadge = page.getByTestId('pool-binding-profiles-status').locator('.ant-tag')

  await expect(streamStatusButton).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Where this execution pack is used', level: 3 })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Opaque pin' })).toHaveCount(0)

  await page.getByRole('button', { name: /Advanced payload and immutable pins/i }).click()

  await expect(page.getByRole('columnheader', { name: 'Opaque pin' })).toBeVisible()
  await expect(page.getByText('Latest immutable revision')).toBeVisible()

  await expectContrastAtLeast(selectedMenuItem, 4.5)
  await expectContrastAtLeast(streamStatusButton.locator('.ant-tag'), 4.5)
  await expectContrastAtLeast(subtitle, 4.5)
  await expectContrastAtLeast(createProfileButton, 4.5)
  await expectContrastAtLeast(deactivateProfileButton, 4.5)
  await expectContrastAtLeast(activeStatusBadge, 4.5)
})

test('UI platform: /pools/execution-packs keeps fallback stream labels and deactivated states above contrast floor', async ({ page }) => {
  await setupAuth(page)
  await setupUiPlatformMocks(page, { isStaff: false })

  await page.goto(`/pools/execution-packs?profile=${LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id}&detail=1`, { waitUntil: 'domcontentloaded' })

  const streamStatusButton = page.getByRole('button', { name: 'Stream: Fallback' })
  const deactivatedStatusBadge = page.getByTestId('pool-binding-profiles-status').locator('.ant-tag')

  await expect(streamStatusButton).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Where this execution pack is used', level: 3 })).toBeVisible()
  await expect(page.getByTestId('pool-binding-profiles-selected-code')).toHaveText('legacy-archive')
  await expect(deactivatedStatusBadge).toContainText('Deactivated')

  await expectContrastAtLeast(streamStatusButton.locator('.ant-tag'), 4.5)
  await expectContrastAtLeast(deactivatedStatusBadge, 4.5)
})

test('Runtime contract: one browser instance keeps a single database stream owner across tabs', async ({ context }) => {
  const counts = createRequestCounts()
  const firstPage = await context.newPage()

  await setupAuth(firstPage)
  await setupPersistentDatabaseStream(firstPage)
  await setupUiPlatformMocks(firstPage, { isStaff: true, counts })

  await firstPage.goto('/decisions', { waitUntil: 'domcontentloaded' })
  await expect(firstPage.getByText('Decision Policy Library')).toBeVisible()
  await expect.poll(() => counts.streamTickets).toBe(1)

  const secondPage = await context.newPage()
  await setupAuth(secondPage)
  await setupPersistentDatabaseStream(secondPage)
  await setupUiPlatformMocks(secondPage, { isStaff: true, counts })

  await secondPage.goto('/pools/execution-packs', { waitUntil: 'domcontentloaded' })
  await expect(secondPage.getByText('Execution Packs')).toBeVisible()
  await expect.poll(() => counts.streamTickets).toBe(1)
  await expect(firstPage.getByText('Request Error')).toHaveCount(0)
  await expect(secondPage.getByText('Request Error')).toHaveCount(0)
})
