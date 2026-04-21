import { expect, type Locator, type Page, type Route } from "@playwright/test";

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>;
  }
}

export const TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
export const DATABASE_ID = "10101010-1010-1010-1010-101010101010";
export const NOW = "2026-03-10T12:00:00Z";
export const WORKFLOW_REVISION_ID = "wf-services-r4";
export const ROUTE_MOUNT_TIMEOUT_MS = 15000;
export const DATABASE_RECORD = {
  id: DATABASE_ID,
  name: "db-services",
  host: "srv-1c.local",
  port: 1541,
  base_name: "shared-profile",
  odata_url: "http://srv-1c.local/odata",
  username: "odata_user",
  password: "",
  password_configured: true,
  server_address: "srv-1c.local",
  server_port: 1540,
  infobase_name: "shared-profile",
  status: "active",
  status_display: "Active",
  version: "8.3.24",
  last_check: NOW,
  last_check_status: "ok",
  consecutive_failures: 0,
  avg_response_time: 12,
  cluster_id: "cluster-1",
  is_healthy: true,
  sessions_deny: false,
  scheduled_jobs_deny: false,
  dbms: "PostgreSQL",
  db_server: "pg-db.internal",
  db_name: "shared_profile",
  ibcmd_connection: {
    remote: "ssh://srv-1c.local:22",
    pid: 1200,
    offline: {
      path: "/srv/ibcmd",
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
};

export const CLUSTER_RECORD = {
  id: "cluster-1",
  name: "Main Cluster",
  description: "Primary RAS cluster for shared services",
  ras_host: "srv-ras.local",
  ras_port: 1545,
  ras_server: "srv-ras.local:1545",
  rmngr_host: "srv-rmngr.local",
  rmngr_port: 1541,
  ragent_host: "srv-ragent.local",
  ragent_port: 1540,
  rphost_port_from: 1560,
  rphost_port_to: 1591,
  cluster_service_url: "http://srv-ragent.local:8188",
  cluster_user: "cluster-admin",
  cluster_pwd_configured: true,
  status: "active",
  status_display: "Active",
  last_sync: NOW,
  metadata: {
    deployment: "primary",
    region: "eu-central",
  },
  databases_count: 1,
  created_at: NOW,
  updated_at: NOW,
};

export const CLUSTER_DETAIL_RESPONSE = {
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
};

export const SYSTEM_HEALTH_RESPONSE = {
  timestamp: NOW,
  overall_status: "degraded",
  services: [
    {
      name: "api-gateway",
      type: "go-service",
      url: "http://gateway.local/health",
      status: "online",
      response_time_ms: 24,
      last_check: NOW,
      details: {
        version: "1.0.0",
      },
    },
    {
      name: "orchestrator",
      type: "django",
      url: "http://orchestrator.local/health",
      status: "degraded",
      response_time_ms: 148,
      last_check: NOW,
      details: {
        reason: "Delayed queue drain",
      },
    },
    {
      name: "worker",
      type: "go-service",
      url: "http://worker.local/health",
      status: "online",
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
};

export const SERVICE_MESH_METRICS_MESSAGE = {
  type: "metrics_update",
  timestamp: NOW,
  overallHealth: "degraded",
  services: [
    {
      name: "api-gateway",
      display_name: "API Gateway",
      status: "healthy",
      ops_per_minute: 124,
      active_operations: 2,
      p95_latency_ms: 32,
      error_rate: 0.003,
      last_updated: NOW,
    },
    {
      name: "orchestrator",
      display_name: "Orchestrator",
      status: "degraded",
      ops_per_minute: 76,
      active_operations: 1,
      p95_latency_ms: 190,
      error_rate: 0.018,
      last_updated: NOW,
    },
    {
      name: "worker",
      display_name: "Worker",
      status: "healthy",
      ops_per_minute: 58,
      active_operations: 1,
      p95_latency_ms: 64,
      error_rate: 0.001,
      last_updated: NOW,
    },
  ],
  connections: [
    {
      source: "api-gateway",
      target: "orchestrator",
      requests_per_minute: 124,
      avg_latency_ms: 18,
    },
    {
      source: "orchestrator",
      target: "worker",
      requests_per_minute: 58,
      avg_latency_ms: 42,
    },
  ],
};

export const SERVICE_MESH_HISTORY: Record<
  string,
  {
    service: string;
    display_name: string;
    minutes: number;
    data_points: Array<{
      timestamp: string;
      ops_per_minute: number;
      p95_latency_ms: number;
      error_rate: number;
    }>;
  }
> = {
  orchestrator: {
    service: "orchestrator",
    display_name: "Orchestrator",
    minutes: 30,
    data_points: [
      {
        timestamp: "2026-03-10T11:40:00Z",
        ops_per_minute: 68,
        p95_latency_ms: 160,
        error_rate: 0.01,
      },
      {
        timestamp: "2026-03-10T11:50:00Z",
        ops_per_minute: 74,
        p95_latency_ms: 176,
        error_rate: 0.015,
      },
      {
        timestamp: "2026-03-10T12:00:00Z",
        ops_per_minute: 76,
        p95_latency_ms: 190,
        error_rate: 0.018,
      },
    ],
  },
  "api-gateway": {
    service: "api-gateway",
    display_name: "API Gateway",
    minutes: 30,
    data_points: [
      {
        timestamp: "2026-03-10T11:40:00Z",
        ops_per_minute: 118,
        p95_latency_ms: 28,
        error_rate: 0.002,
      },
      {
        timestamp: "2026-03-10T11:50:00Z",
        ops_per_minute: 122,
        p95_latency_ms: 30,
        error_rate: 0.003,
      },
      {
        timestamp: "2026-03-10T12:00:00Z",
        ops_per_minute: 124,
        p95_latency_ms: 32,
        error_rate: 0.003,
      },
    ],
  },
  worker: {
    service: "worker",
    display_name: "Worker",
    minutes: 30,
    data_points: [
      {
        timestamp: "2026-03-10T11:40:00Z",
        ops_per_minute: 52,
        p95_latency_ms: 58,
        error_rate: 0.001,
      },
      {
        timestamp: "2026-03-10T11:50:00Z",
        ops_per_minute: 55,
        p95_latency_ms: 61,
        error_rate: 0.001,
      },
      {
        timestamp: "2026-03-10T12:00:00Z",
        ops_per_minute: 58,
        p95_latency_ms: 64,
        error_rate: 0.001,
      },
    ],
  },
};

export const METADATA_CONTEXT = {
  database_id: DATABASE_ID,
  snapshot_id: "snapshot-shared-services",
  source: "db",
  fetched_at: NOW,
  catalog_version: "v1:shared-services",
  config_name: "shared-profile",
  config_version: "8.3.24",
  config_generation_id: "generation-shared-services",
  extensions_fingerprint: "",
  metadata_hash: "a".repeat(64),
  observed_metadata_hash: "a".repeat(64),
  publication_drift: false,
  resolution_mode: "shared_scope",
  is_shared_snapshot: true,
  provenance_database_id: "20202020-2020-2020-2020-202020202020",
  provenance_confirmed_at: NOW,
  documents: [],
};

export const METADATA_MANAGEMENT = {
  database_id: DATABASE_ID,
  configuration_profile: {
    status: "verified",
    config_name: "shared-profile",
    config_version: "8.3.24",
    config_generation_id: "generation-shared-services",
    config_root_name: "Accounting",
    config_vendor: "1C",
    config_name_source: "manual",
    verification_operation_id: "",
    verified_at: NOW,
    generation_probe_requested_at: null,
    generation_probe_checked_at: null,
    observed_metadata_hash: "a".repeat(64),
    canonical_metadata_hash: "a".repeat(64),
    publication_drift: false,
    reverify_available: true,
    reverify_blocker_code: "",
    reverify_blocker_message: "",
    reverify_blocking_action: "",
  },
  metadata_snapshot: {
    status: "available",
    missing_reason: "",
    snapshot_id: "snapshot-shared-services",
    source: "db",
    fetched_at: NOW,
    catalog_version: "v1:shared-services",
    config_name: "shared-profile",
    config_version: "8.3.24",
    config_generation_id: "generation-shared-services",
    extensions_fingerprint: "",
    metadata_hash: "a".repeat(64),
    resolution_mode: "shared_scope",
    is_shared_snapshot: true,
    provenance_database_id: "20202020-2020-2020-2020-202020202020",
    provenance_confirmed_at: NOW,
    observed_metadata_hash: "a".repeat(64),
    publication_drift: false,
  },
};

export const DECISION = {
  id: "decision-version-2",
  decision_table_id: "services-publication-policy",
  decision_key: "document_policy",
  decision_revision: 2,
  name: "Services publication policy",
  description: "Publishes service documents",
  inputs: [],
  outputs: [],
  rules: [
    {
      rule_id: "default",
      priority: 0,
      conditions: {},
      outputs: {
        document_policy: {
          version: "document_policy.v1",
          chains: [
            {
              chain_id: "sale_chain",
              documents: [
                {
                  document_id: "sale",
                  entity_name: "Document_Sales",
                  document_role: "sale",
                  field_mapping: {
                    Amount: "allocation.amount",
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
  hit_policy: "first_match",
  validation_mode: "fail_closed",
  is_active: true,
  parent_version: "decision-version-1",
  metadata_context: {
    snapshot_id: METADATA_CONTEXT.snapshot_id,
    config_name: METADATA_CONTEXT.config_name,
    config_version: METADATA_CONTEXT.config_version,
    config_generation_id: METADATA_CONTEXT.config_generation_id,
    extensions_fingerprint: "",
    metadata_hash: "a".repeat(64),
    observed_metadata_hash: "a".repeat(64),
    publication_drift: false,
    resolution_mode: "shared_scope",
    is_shared_snapshot: true,
    provenance_database_id: METADATA_CONTEXT.provenance_database_id,
    provenance_confirmed_at: NOW,
  },
  metadata_compatibility: {
    status: "compatible",
    reason: null,
    is_compatible: true,
  },
  created_at: NOW,
  updated_at: NOW,
};

export const FALLBACK_DECISION = {
  ...DECISION,
  id: "decision-version-3",
  decision_revision: 3,
  name: "Fallback services publication policy",
  description: "Fallback policy for diagnostics",
  parent_version: DECISION.id,
};

export const DECISIONS = [DECISION, FALLBACK_DECISION];

export const WORKFLOW = {
  id: WORKFLOW_REVISION_ID,
  name: "Services Publication",
  description: "Reusable workflow for service publication.",
  workflow_type: "complex",
  category: "custom",
  is_valid: true,
  is_active: true,
  is_system_managed: false,
  management_mode: "user_authored",
  visibility_surface: "workflow_library",
  read_only_reason: null,
  version_number: 4,
  parent_version: null,
  created_by: null,
  created_by_username: "analyst",
  node_count: 2,
  execution_count: 0,
  created_at: NOW,
  updated_at: NOW,
};

export const BINDING_PROFILE_DETAIL = {
  binding_profile_id: "bp-services",
  code: "services-publication",
  name: "Services Publication",
  description: "Reusable scheme for top-down publication.",
  status: "active",
  latest_revision_number: 2,
  latest_revision: {
    binding_profile_revision_id: "bp-rev-services-r2",
    binding_profile_id: "bp-services",
    revision_number: 2,
    workflow: {
      workflow_definition_key: "services-publication",
      workflow_revision_id: "wf-services-r2",
      workflow_revision: 4,
      workflow_name: "services_publication",
    },
    decisions: [
      {
        decision_table_id: "services-publication-policy",
        decision_key: "document_policy",
        slot_key: "document_policy",
        decision_revision: 2,
      },
    ],
    parameters: {
      publication_variant: "full",
    },
    role_mapping: {
      initiator: "finance",
    },
    metadata: {
      source: "manual",
    },
    created_by: "analyst",
    created_at: NOW,
  },
  revisions: [
    {
      binding_profile_revision_id: "bp-rev-services-r2",
      binding_profile_id: "bp-services",
      revision_number: 2,
      workflow: {
        workflow_definition_key: "services-publication",
        workflow_revision_id: "wf-services-r2",
        workflow_revision: 4,
        workflow_name: "services_publication",
      },
      decisions: [],
      parameters: {},
      role_mapping: {},
      metadata: {},
      created_by: "analyst",
      created_at: NOW,
    },
  ],
  usage_summary: {
    attachment_count: 1,
    revision_summary: [
      {
        binding_profile_revision_id: "bp-rev-services-r2",
        binding_profile_revision_number: 2,
        attachment_count: 1,
      },
    ],
    attachments: [
      {
        pool_id: "pool-1",
        pool_code: "pool-main",
        pool_name: "Main Pool",
        binding_id: "binding-top-down",
        attachment_revision: 3,
        binding_profile_revision_id: "bp-rev-services-r2",
        binding_profile_revision_number: 2,
        status: "active",
        selector: {
          direction: "top_down",
          mode: "safe",
          tags: [],
        },
        effective_from: NOW,
        effective_to: null,
      },
    ],
  },
  created_by: "analyst",
  updated_by: "analyst",
  deactivated_by: null,
  deactivated_at: null,
  created_at: NOW,
  updated_at: NOW,
};

export const BINDING_PROFILE_SUMMARY = {
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
};

export const LEGACY_BINDING_PROFILE_DETAIL = {
  ...BINDING_PROFILE_DETAIL,
  binding_profile_id: "bp-legacy",
  code: "legacy-archive",
  name: "Legacy Archive",
  description: "Legacy reusable profile kept for pinned attachments.",
  status: "deactivated",
  latest_revision_number: 1,
  latest_revision: {
    binding_profile_revision_id: "bp-rev-legacy-r1",
    binding_profile_id: "bp-legacy",
    revision_number: 1,
    workflow: {
      workflow_definition_key: "legacy-archive",
      workflow_revision_id: "wf-legacy-r1",
      workflow_revision: 1,
      workflow_name: "legacy_archive",
    },
    decisions: [
      {
        decision_table_id: "services-publication-policy",
        decision_key: "document_policy",
        slot_key: "document_policy",
        decision_revision: 2,
      },
    ],
    parameters: {
      publication_variant: "archive",
    },
    role_mapping: {
      initiator: "finance",
    },
    metadata: {
      source: "legacy",
    },
    created_by: "analyst",
    created_at: NOW,
  },
  revisions: [
    {
      binding_profile_revision_id: "bp-rev-legacy-r1",
      binding_profile_id: "bp-legacy",
      revision_number: 1,
      workflow: {
        workflow_definition_key: "legacy-archive",
        workflow_revision_id: "wf-legacy-r1",
        workflow_revision: 1,
        workflow_name: "legacy_archive",
      },
      decisions: [],
      parameters: {},
      role_mapping: {},
      metadata: {},
      created_by: "analyst",
      created_at: NOW,
    },
  ],
  usage_summary: {
    attachment_count: 0,
    revision_summary: [],
    attachments: [],
  },
  deactivated_by: "analyst",
  deactivated_at: NOW,
};

export const LEGACY_BINDING_PROFILE_SUMMARY = {
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
};

export const BINDING_PROFILE_SUMMARIES = [
  BINDING_PROFILE_SUMMARY,
  LEGACY_BINDING_PROFILE_SUMMARY,
];
export const BINDING_PROFILE_DETAILS: Record<
  string,
  typeof BINDING_PROFILE_DETAIL
> = {
  [BINDING_PROFILE_DETAIL.binding_profile_id]: BINDING_PROFILE_DETAIL,
  [LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id]:
    LEGACY_BINDING_PROFILE_DETAIL,
};

export const TOPOLOGY_TEMPLATE = {
  topology_template_id: "template-top-down",
  code: "top-down-template",
  name: "Top Down Template",
  description: "Reusable topology for top-down publication.",
  status: "active",
  metadata: {},
  latest_revision_number: 3,
  latest_revision: {
    topology_template_revision_id: "template-revision-r3",
    topology_template_id: "template-top-down",
    revision_number: 3,
    nodes: [
      {
        slot_key: "root",
        label: "Root",
        is_root: true,
        metadata: {},
      },
      {
        slot_key: "organization_1",
        label: "Organization 1",
        is_root: false,
        metadata: {},
      },
      {
        slot_key: "organization_2",
        label: "Organization 2",
        is_root: false,
        metadata: {},
      },
      {
        slot_key: "organization_3",
        label: "Organization 3",
        is_root: false,
        metadata: {},
      },
      {
        slot_key: "organization_4",
        label: "Organization 4",
        is_root: false,
        metadata: {},
      },
    ],
    edges: [
      {
        parent_slot_key: "root",
        child_slot_key: "organization_1",
        weight: "1",
        min_amount: null,
        max_amount: null,
        document_policy_key: "sale",
        metadata: {},
      },
      {
        parent_slot_key: "organization_1",
        child_slot_key: "organization_2",
        weight: "1",
        min_amount: null,
        max_amount: null,
        document_policy_key: "receipt_internal",
        metadata: {},
      },
      {
        parent_slot_key: "organization_2",
        child_slot_key: "organization_3",
        weight: "1",
        min_amount: null,
        max_amount: null,
        document_policy_key: "receipt_leaf",
        metadata: {},
      },
      {
        parent_slot_key: "organization_2",
        child_slot_key: "organization_4",
        weight: "1",
        min_amount: null,
        max_amount: null,
        document_policy_key: "receipt_leaf",
        metadata: {},
      },
    ],
    metadata: {},
    created_at: NOW,
  },
  revisions: [
    {
      topology_template_revision_id: "template-revision-r3",
      topology_template_id: "template-top-down",
      revision_number: 3,
      nodes: [
        {
          slot_key: "root",
          label: "Root",
          is_root: true,
          metadata: {},
        },
        {
          slot_key: "organization_1",
          label: "Organization 1",
          is_root: false,
          metadata: {},
        },
        {
          slot_key: "organization_2",
          label: "Organization 2",
          is_root: false,
          metadata: {},
        },
        {
          slot_key: "organization_3",
          label: "Organization 3",
          is_root: false,
          metadata: {},
        },
        {
          slot_key: "organization_4",
          label: "Organization 4",
          is_root: false,
          metadata: {},
        },
      ],
      edges: [
        {
          parent_slot_key: "root",
          child_slot_key: "organization_1",
          weight: "1",
          min_amount: null,
          max_amount: null,
          document_policy_key: "sale",
          metadata: {},
        },
        {
          parent_slot_key: "organization_1",
          child_slot_key: "organization_2",
          weight: "1",
          min_amount: null,
          max_amount: null,
          document_policy_key: "receipt_internal",
          metadata: {},
        },
        {
          parent_slot_key: "organization_2",
          child_slot_key: "organization_3",
          weight: "1",
          min_amount: null,
          max_amount: null,
          document_policy_key: "receipt_leaf",
          metadata: {},
        },
        {
          parent_slot_key: "organization_2",
          child_slot_key: "organization_4",
          weight: "1",
          min_amount: null,
          max_amount: null,
          document_policy_key: "receipt_leaf",
          metadata: {},
        },
      ],
      metadata: {},
      created_at: NOW,
    },
    {
      topology_template_revision_id: "template-revision-r2",
      topology_template_id: "template-top-down",
      revision_number: 2,
      nodes: [
        {
          slot_key: "root",
          label: "Root",
          is_root: true,
          metadata: {},
        },
        {
          slot_key: "organization_1",
          label: "Organization 1",
          is_root: false,
          metadata: {},
        },
        {
          slot_key: "organization_2",
          label: "Organization 2",
          is_root: false,
          metadata: {},
        },
        {
          slot_key: "organization_3",
          label: "Organization 3",
          is_root: false,
          metadata: {},
        },
        {
          slot_key: "organization_4",
          label: "Organization 4",
          is_root: false,
          metadata: {},
        },
      ],
      edges: [
        {
          parent_slot_key: "root",
          child_slot_key: "organization_1",
          weight: "1",
          min_amount: null,
          max_amount: null,
          document_policy_key: "receipt",
          metadata: {},
        },
        {
          parent_slot_key: "organization_1",
          child_slot_key: "organization_2",
          weight: "1",
          min_amount: null,
          max_amount: null,
          document_policy_key: "receipt",
          metadata: {},
        },
        {
          parent_slot_key: "organization_2",
          child_slot_key: "organization_3",
          weight: "1",
          min_amount: null,
          max_amount: null,
          document_policy_key: "receipt",
          metadata: {},
        },
        {
          parent_slot_key: "organization_2",
          child_slot_key: "organization_4",
          weight: "1",
          min_amount: null,
          max_amount: null,
          document_policy_key: "receipt",
          metadata: {},
        },
      ],
      metadata: {},
      created_at: NOW,
    },
  ],
  created_at: NOW,
  updated_at: NOW,
};

export const MASTER_DATA_REGISTRY_RESPONSE = {
  contract_version: "pool_master_data_registry.v1",
  count: 5,
  entries: [
    {
      entity_type: "party",
      label: "Party",
      kind: "canonical",
      display_order: 10,
      binding_scope_fields: ["canonical_id", "database_id", "ib_catalog_kind"],
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
        qualifier_kind: "ib_catalog_kind",
        qualifier_required: true,
        qualifier_options: ["organization", "counterparty"],
      },
      bootstrap_contract: { enabled: true, dependency_order: 10 },
      runtime_consumers: [
        "bindings",
        "bootstrap_import",
        "sync",
        "token_catalog",
        "token_parser",
      ],
    },
    {
      entity_type: "item",
      label: "Item",
      kind: "canonical",
      display_order: 20,
      binding_scope_fields: ["canonical_id", "database_id"],
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
        qualifier_kind: "none",
        qualifier_required: false,
        qualifier_options: [],
      },
      bootstrap_contract: { enabled: true, dependency_order: 20 },
      runtime_consumers: [
        "bindings",
        "bootstrap_import",
        "sync",
        "token_catalog",
        "token_parser",
      ],
    },
    {
      entity_type: "contract",
      label: "Contract",
      kind: "canonical",
      display_order: 30,
      binding_scope_fields: [
        "canonical_id",
        "database_id",
        "owner_counterparty_canonical_id",
      ],
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
        qualifier_kind: "owner_counterparty_canonical_id",
        qualifier_required: true,
        qualifier_options: [],
      },
      bootstrap_contract: { enabled: true, dependency_order: 30 },
      runtime_consumers: [
        "bindings",
        "bootstrap_import",
        "sync",
        "token_catalog",
        "token_parser",
      ],
    },
    {
      entity_type: "gl_account",
      label: "GL Account",
      kind: "canonical",
      display_order: 35,
      binding_scope_fields: ["canonical_id", "database_id", "chart_identity"],
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
        qualifier_kind: "none",
        qualifier_required: false,
        qualifier_options: [],
      },
      bootstrap_contract: { enabled: true, dependency_order: 35 },
      runtime_consumers: [
        "bindings",
        "bootstrap_import",
        "token_catalog",
        "token_parser",
      ],
    },
    {
      entity_type: "tax_profile",
      label: "Tax Profile",
      kind: "canonical",
      display_order: 40,
      binding_scope_fields: ["canonical_id", "database_id"],
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
        qualifier_kind: "none",
        qualifier_required: false,
        qualifier_options: [],
      },
      bootstrap_contract: { enabled: true, dependency_order: 40 },
      runtime_consumers: [
        "bindings",
        "bootstrap_import",
        "sync",
        "token_catalog",
        "token_parser",
      ],
    },
  ],
};

export const MASTER_DATA_PARTIES = [
  {
    id: "party-1",
    tenant_id: TENANT_ID,
    canonical_id: "party-org",
    name: "Org One",
    full_name: "Org One LLC",
    inn: "730000000001",
    kpp: "123456789",
    is_our_organization: true,
    is_counterparty: true,
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
];

export const MASTER_DATA_ITEMS = [
  {
    id: "item-1",
    tenant_id: TENANT_ID,
    canonical_id: "item-1",
    name: "Service package",
    sku: "svc-1",
    unit: "pcs",
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
];

export const MASTER_DATA_CONTRACTS = [
  {
    id: "contract-1",
    tenant_id: TENANT_ID,
    canonical_id: "contract-1",
    name: "Main service contract",
    owner_counterparty_id: "party-1",
    owner_counterparty_canonical_id: "party-org",
    number: "C-001",
    date: "2026-01-01",
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
];

export const MASTER_DATA_TAX_PROFILES = [
  {
    id: "tax-profile-1",
    tenant_id: TENANT_ID,
    canonical_id: "tax-profile-1",
    vat_rate: 20,
    vat_included: true,
    vat_code: "VAT20",
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
];

export const MASTER_DATA_GL_ACCOUNTS = [
  {
    id: "gl-account-1",
    tenant_id: TENANT_ID,
    canonical_id: "gl-account-001",
    code: "10.01",
    name: "Main Account",
    chart_identity: "ChartOfAccounts_Main",
    config_name: "Accounting Enterprise",
    config_version: "3.0.1",
    compatibility_class: "current",
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  },
];

export const POOL_WITH_ATTACHMENT = {
  id: "pool-1",
  code: "pool-main",
  name: "Main Pool",
  description: "Workflow-centric pool",
  is_active: true,
  metadata: {},
  updated_at: NOW,
  workflow_bindings: [
    {
      binding_id: "binding-top-down",
      pool_id: "pool-1",
      revision: 3,
      status: "active",
      contract_version: "binding_profile.v1",
      binding_profile_id: "bp-services",
      binding_profile_revision_id: "bp-rev-services-r2",
      binding_profile_revision_number: 2,
      effective_from: NOW,
      effective_to: null,
      selector: {
        direction: "top_down",
        mode: "safe",
        tags: [],
      },
      workflow: {
        workflow_definition_key: "services-publication",
        workflow_revision_id: "wf-services-r2",
        workflow_revision: 4,
        workflow_name: "services_publication",
      },
      decisions: [],
      parameters: {},
      role_mapping: {},
      resolved_profile: {
        binding_profile_id: "bp-services",
        code: "services-publication",
        name: "Services Publication",
        status: "active",
        binding_profile_revision_id: "bp-rev-services-r2",
        binding_profile_revision_number: 2,
        workflow: {
          workflow_definition_key: "services-publication",
          workflow_revision_id: "wf-services-r2",
          workflow_revision: 4,
          workflow_name: "services_publication",
        },
        decisions: [],
        parameters: {},
        role_mapping: {},
      },
      profile_lifecycle_warning: null,
    },
  ],
};

export const POOL_RUN = {
  id: "run-1",
  tenant_id: TENANT_ID,
  pool_id: POOL_WITH_ATTACHMENT.id,
  schema_template_id: null,
  mode: "safe",
  direction: "top_down",
  status: "validated",
  status_reason: "awaiting_approval",
  period_start: "2026-01-01",
  period_end: null,
  run_input: {
    starting_amount: "100.00",
  },
  input_contract_version: "run_input_v1",
  idempotency_key: "idem-run-1",
  workflow_execution_id: "workflow-run-1",
  workflow_status: "pending",
  root_operation_id: "operation-root-1",
  execution_consumer: "pools",
  lane: "workflows",
  approval_state: "awaiting_approval",
  publication_step_state: "not_enqueued",
  readiness_blockers: [],
  readiness_checklist: {
    status: "ready",
    checks: [
      {
        code: "master_data_coverage",
        status: "ready",
        blocker_codes: [],
        blockers: [],
      },
      {
        code: "organization_party_bindings",
        status: "ready",
        blocker_codes: [],
        blockers: [],
      },
      {
        code: "policy_completeness",
        status: "ready",
        blocker_codes: [],
        blockers: [],
      },
      {
        code: "odata_verify_readiness",
        status: "ready",
        blocker_codes: [],
        blockers: [],
      },
    ],
  },
  verification_status: "not_verified",
  verification_summary: null,
  terminal_reason: null,
  execution_backend: "workflow_core",
  workflow_template_name: "pool-template-v1",
  seed: null,
  validation_summary: { rows: 3 },
  publication_summary: { total_targets: 1 },
  diagnostics: [{ step: "prepare_input", status: "ok" }],
  last_error: "",
  created_at: NOW,
  updated_at: NOW,
  validated_at: NOW,
  publication_confirmed_at: null,
  publishing_started_at: null,
  completed_at: null,
  provenance: {
    workflow_run_id: "workflow-run-1",
    workflow_status: "pending",
    execution_backend: "workflow_core",
    root_operation_id: "operation-root-1",
    execution_consumer: "pools",
    lane: "workflows",
    retry_chain: [
      {
        workflow_run_id: "workflow-run-1",
        parent_workflow_run_id: null,
        attempt_number: 1,
        attempt_kind: "initial",
        status: "pending",
      },
    ],
  },
  workflow_binding: POOL_WITH_ATTACHMENT.workflow_bindings[0],
  runtime_projection: {
    version: "pool_runtime_projection.v1",
    run_id: "run-1",
    pool_id: POOL_WITH_ATTACHMENT.id,
    direction: "top_down",
    mode: "safe",
    workflow_definition: {
      plan_key: "plan-services-v4",
      template_version: "workflow-template:4",
      workflow_template_name: "compiled-services-publication",
      workflow_type: "sequential",
    },
    workflow_binding: {
      binding_mode: "pool_workflow_binding",
      binding_id: "binding-top-down",
      binding_profile_id: "bp-services",
      pool_id: POOL_WITH_ATTACHMENT.id,
      binding_profile_revision_id: "bp-rev-services-r2",
      binding_profile_revision_number: 2,
      attachment_revision: 3,
      workflow_definition_key: "services-publication",
      workflow_revision_id: "wf-services-r2",
      workflow_revision: 4,
      workflow_name: "services_publication",
      decision_refs: [
        {
          decision_table_id: "services-publication-policy",
          decision_key: "document_policy",
          slot_key: "document_policy",
          decision_revision: 2,
        },
      ],
      selector: {
        direction: "top_down",
        mode: "safe",
        tags: [],
      },
      status: "active",
    },
    document_policy_projection: {
      source_mode: "decision_tables",
      policy_refs: [
        {
          slot_key: "document_policy",
          edge_ref: {
            parent_node_id: "node-root",
            child_node_id: "node-child",
          },
          policy_version: "document_policy.v1",
          source: "decision_tables",
        },
      ],
      compiled_document_policy_slots: {
        document_policy: {
          decision_table_id: "services-publication-policy",
          decision_revision: 2,
          document_policy_source: "decision_tables",
          document_policy: {
            version: "document_policy.v1",
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
            edge_id: "edge-1",
            edge_label: "Root Org -> Child Org",
            slot_key: "document_policy",
            coverage: {
              code: null,
              status: "resolved",
              label: "Resolved",
              detail: "document_policy -> services-publication-policy r2",
            },
          },
        ],
      },
      policy_refs_count: 1,
      targets_count: 1,
    },
    artifacts: {
      document_plan_artifact_version: "document_plan_artifact.v1",
      topology_version_ref: "topology:v1",
      distribution_artifact_ref: { id: "distribution-artifact:v1" },
    },
    compile_summary: {
      steps_count: 4,
      atomic_publication_steps_count: 1,
      compiled_targets_count: 1,
    },
  },
};

export const POOL_RUN_REPORT = {
  run: POOL_RUN,
  publication_attempts: [
    {
      id: "publication-attempt-1",
      run_id: POOL_RUN.id,
      target_database_id: DATABASE_ID,
      attempt_number: 1,
      attempt_timestamp: NOW,
      status: "failed",
      entity_name: "Document_Sales",
      documents_count: 1,
      publication_identity_strategy: "guid",
      external_document_identity: "sale-1",
      posted: false,
      domain_error_code: "network",
      domain_error_message: "temporary error",
      http_error: null,
      transport_error: null,
    },
  ],
  validation_summary: { rows: 3 },
  publication_summary: { total_targets: 1, failed_targets: 1 },
  diagnostics: [{ step: "distribution_calculation", status: "ok" }],
  attempts_by_status: { failed: 1 },
};

export const POOL_FACTUAL_WORKSPACE = {
  pool_id: POOL_WITH_ATTACHMENT.id,
  summary: {
    quarter: "2026Q1",
    quarter_start: "2026-01-01",
    quarter_end: "2026-03-31",
    amount_with_vat: "120.00",
    amount_without_vat: "100.00",
    vat_amount: "20.00",
    incoming_amount: "170.00",
    outgoing_amount: "115.00",
    open_balance: "55.00",
    pending_review_total: 1,
    attention_required_total: 1,
    backlog_total: 2,
    freshness_state: "stale",
    source_availability: "available",
    source_availability_detail: "",
    last_synced_at: NOW,
    sync_status: "success",
    checkpoints_pending: 0,
    checkpoints_running: 0,
    checkpoints_failed: 0,
    checkpoints_ready: 1,
    activity: "active",
    polling_tier: "active",
    poll_interval_seconds: 120,
    freshness_target_seconds: 120,
    scope_fingerprint: "",
    scope_contract_version: "",
    gl_account_set_revision_id: "",
    scope_contract: null,
    settlement_total: 2,
    checkpoint_total: 1,
  },
  checkpoints: [
    {
      checkpoint_id: "checkpoint-ready-1",
      database_id: DATABASE_ID,
      database_name: DATABASE_RECORD.name,
      workflow_status: "",
      freshness_state: "stale",
      last_synced_at: NOW,
      last_error_code: "",
      last_error: "",
      execution_id: null,
      operation_id: null,
      activity: "active",
      polling_tier: "active",
      poll_interval_seconds: 120,
      freshness_target_seconds: 120,
    },
  ],
  settlements: [
    {
      id: "batch-receipt-1",
      tenant_id: TENANT_ID,
      pool_id: POOL_WITH_ATTACHMENT.id,
      batch_kind: "receipt",
      source_type: "manual",
      schema_template_id: null,
      start_organization_id: "organization-main",
      run_id: POOL_RUN.id,
      workflow_execution_id: null,
      operation_id: null,
      workflow_status: "",
      period_start: "2026-01-01",
      period_end: "2026-03-31",
      source_reference: "receipt-q1",
      raw_payload_ref: "",
      content_hash: "receipt-hash-1",
      source_metadata: {},
      normalization_summary: {},
      publication_summary: {},
      last_error_code: "",
      last_error: "",
      created_by_id: null,
      created_at: NOW,
      updated_at: NOW,
      settlement: {
        id: "settlement-receipt-1",
        tenant_id: TENANT_ID,
        batch_id: "batch-receipt-1",
        status: "partially_closed",
        incoming_amount: "120.00",
        outgoing_amount: "80.00",
        open_balance: "40.00",
        summary: {},
        freshness_at: NOW,
        created_at: NOW,
        updated_at: NOW,
      },
    },
    {
      id: "batch-sale-1",
      tenant_id: TENANT_ID,
      pool_id: POOL_WITH_ATTACHMENT.id,
      batch_kind: "sale",
      source_type: "manual",
      schema_template_id: null,
      start_organization_id: null,
      run_id: null,
      workflow_execution_id: "workflow-sale-1",
      operation_id: "operation-sale-1",
      workflow_status: "completed",
      period_start: "2026-01-01",
      period_end: "2026-03-31",
      source_reference: "sale-q1",
      raw_payload_ref: "",
      content_hash: "sale-hash-1",
      source_metadata: {},
      normalization_summary: {},
      publication_summary: {},
      last_error_code: "",
      last_error: "",
      created_by_id: null,
      created_at: NOW,
      updated_at: NOW,
      settlement: {
        id: "settlement-sale-1",
        tenant_id: TENANT_ID,
        batch_id: "batch-sale-1",
        status: "attention_required",
        incoming_amount: "50.00",
        outgoing_amount: "35.00",
        open_balance: "15.00",
        summary: {},
        freshness_at: NOW,
        created_at: NOW,
        updated_at: NOW,
      },
    },
  ],
  edge_balances: [
    {
      id: "edge-balance-1",
      pool_id: POOL_WITH_ATTACHMENT.id,
      batch_id: "batch-receipt-1",
      organization_id: "organization-leaf-1",
      organization_name: "Leaf Alpha",
      edge_id: "edge-alpha-1",
      parent_node_id: "node-root",
      child_node_id: "node-child",
      quarter: "2026Q1",
      quarter_start: "2026-01-01",
      quarter_end: "2026-03-31",
      amount_with_vat: "120.00",
      amount_without_vat: "100.00",
      vat_amount: "20.00",
      incoming_amount: "120.00",
      outgoing_amount: "80.00",
      open_balance: "40.00",
      freshness_at: NOW,
      metadata: {},
    },
  ],
  review_queue: {
    contract_version: "pool_factual_review_queue.v1",
    subsystem: "reconcile_review",
    summary: {
      pending_total: 1,
      unattributed_total: 1,
      late_correction_total: 0,
      attention_required_total: 1,
    },
    items: [
      {
        id: "unattributed-pool-main",
        pool_id: POOL_WITH_ATTACHMENT.id,
        batch_id: "batch-receipt-1",
        organization_id: "organization-leaf-1",
        edge_id: "edge-alpha-1",
        reason: "unattributed",
        status: "pending",
        quarter: "2026Q1",
        source_document_ref:
          "Document_РеализацияТоваровУслуг(guid'pool-main-sale')",
        allowed_actions: ["attribute", "resolve_without_change"],
        attention_required: true,
        resolved_at: null,
      },
    ],
  },
};

export const POOL_FACTUAL_OVERVIEW = {
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
};

export const WORKFLOW_EXECUTION_DETAIL = {
  id: POOL_RUN.workflow_execution_id,
  workflow_template: WORKFLOW.id,
  template_name: WORKFLOW.name,
  template_version: WORKFLOW.version_number,
  status: "pending",
  input_context: {
    pool_id: POOL_RUN.pool_id,
  },
  final_result: null,
  current_node_id: "",
  completed_nodes: {},
  failed_nodes: {},
  node_statuses: {},
  progress_percent: "0.00",
  error_message: "",
  error_node_id: "",
  trace_id: "",
  started_at: NOW,
  completed_at: null,
  duration: 0,
  step_results: [],
};

export const WORKFLOW_TEMPLATE_DETAIL = {
  id: WORKFLOW.id,
  name: WORKFLOW.name,
  description: WORKFLOW.description,
  workflow_type: "sequential",
  category: WORKFLOW.category,
  dag_structure: {
    nodes: [
      {
        id: "start",
        name: "Start",
        type: "operation",
        template_id: "noop",
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
  management_mode: "user_authored",
  visibility_surface: "workflow_library",
  read_only_reason: null,
  version_number: WORKFLOW.version_number,
  parent_version: null,
  parent_version_name: null,
  created_by: null,
  created_by_username: "analyst",
  execution_count: 0,
  created_at: NOW,
  updated_at: NOW,
};

export const WORKFLOW_OPERATION = {
  id: "workflow-operation-1",
  name: "workflow root execute",
  description: "",
  operation_type: "query",
  target_entity: "Workflow",
  status: "processing",
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
  created_by: "admin",
  metadata: {
    workflow_execution_id: POOL_RUN.workflow_execution_id,
    node_id: "services-node-1",
    root_operation_id: "workflow-operation-1",
    execution_consumer: "workflows",
    lane: "workflows",
    trace_id: "trace-services-1",
  },
  created_at: NOW,
  updated_at: NOW,
  database_names: ["db-services"],
  tasks: [],
};

export const MANUAL_OPERATION = {
  id: "manual-operation-1",
  name: "manual lock scheduled jobs",
  description: "",
  operation_type: "lock_scheduled_jobs",
  target_entity: "Infobase",
  status: "completed",
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
  created_by: "admin",
  metadata: {},
  created_at: NOW,
  updated_at: NOW,
  database_names: ["db-services"],
  tasks: [],
};

export const ZERO_TASK_OPERATION = {
  id: "zero-task-operation-1",
  name: "workflow telemetry pending",
  description: "",
  operation_type: "query",
  target_entity: "Workflow",
  status: "completed",
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
  created_by: "admin",
  metadata: {
    workflow_execution_id: POOL_RUN.workflow_execution_id,
  },
  created_at: NOW,
  updated_at: NOW,
  database_names: ["db-services"],
  tasks: [],
};

export const OPERATIONS = [
  WORKFLOW_OPERATION,
  MANUAL_OPERATION,
  ZERO_TASK_OPERATION,
];

export const OPERATION_DETAILS: Record<
  string,
  {
    operation: typeof WORKFLOW_OPERATION;
    execution_plan: Record<string, unknown> | null;
    bindings: Array<Record<string, unknown>>;
    tasks: Array<Record<string, unknown>>;
    progress: Record<string, number>;
  }
> = {
  [WORKFLOW_OPERATION.id]: {
    operation: {
      ...WORKFLOW_OPERATION,
      tasks: [
        {
          id: "task-workflow-1",
          database: DATABASE_ID,
          database_name: "db-services",
          status: "processing",
          result: {},
          error_message: "",
          error_code: "",
          retry_count: 0,
          max_retries: 3,
          worker_id: "worker-1",
          started_at: NOW,
          completed_at: null,
          duration_seconds: 1,
          created_at: NOW,
          updated_at: NOW,
        },
      ],
    },
    execution_plan: {
      kind: "workflow",
      workflow_id: WORKFLOW.id,
      input_context_masked: {
        workflow_execution_id: POOL_RUN.workflow_execution_id,
      },
    },
    bindings: [
      {
        target_ref: "workflow_execution_id",
        source_ref: "request.workflow_execution_id",
        resolve_at: "api",
        sensitive: false,
        status: "applied",
      },
    ],
    tasks: [
      {
        id: "task-workflow-1",
        database: DATABASE_ID,
        database_name: "db-services",
        status: "processing",
        result: {},
        error_message: "",
        error_code: "",
        retry_count: 0,
        max_retries: 3,
        worker_id: "worker-1",
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
          id: "task-manual-1",
          database: DATABASE_ID,
          database_name: "db-services",
          status: "completed",
          result: {},
          error_message: "",
          error_code: "",
          retry_count: 0,
          max_retries: 3,
          worker_id: "worker-1",
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
        id: "task-manual-1",
        database: DATABASE_ID,
        database_name: "db-services",
        status: "completed",
        result: {},
        error_message: "",
        error_code: "",
        retry_count: 0,
        max_retries: 3,
        worker_id: "worker-1",
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
      kind: "workflow",
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
};

export const OPERATION_TIMELINES: Record<
  string,
  {
    operation_id: string;
    timeline: Array<Record<string, unknown>>;
    total_events: number;
    duration_ms: number | null;
  }
> = {
  [WORKFLOW_OPERATION.id]: {
    operation_id: WORKFLOW_OPERATION.id,
    timeline: [
      {
        timestamp: 1000,
        event: "orchestrator.created",
        service: "orchestrator",
        workflow_execution_id: POOL_RUN.workflow_execution_id,
        node_id: "services-node-1",
        root_operation_id: WORKFLOW_OPERATION.id,
        execution_consumer: "workflows",
        lane: "workflows",
        metadata: {},
      },
      {
        timestamp: 1800,
        event: "worker.command.completed",
        service: "worker",
        workflow_execution_id: POOL_RUN.workflow_execution_id,
        node_id: "services-node-1",
        root_operation_id: WORKFLOW_OPERATION.id,
        execution_consumer: "workflows",
        lane: "workflows",
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
        event: "orchestrator.created",
        service: "orchestrator",
        root_operation_id: MANUAL_OPERATION.id,
        execution_consumer: "operations",
        lane: "operations",
        metadata: {},
      },
      {
        timestamp: 1300,
        event: "worker.command.completed",
        service: "worker",
        root_operation_id: MANUAL_OPERATION.id,
        execution_consumer: "operations",
        lane: "operations",
        metadata: {},
      },
    ],
    total_events: 2,
    duration_ms: 300,
  },
};

export const ADMIN_USER = {
  id: 101,
  username: "admin",
  email: "admin@example.com",
  first_name: "Admin",
  last_name: "Operator",
  is_staff: true,
  is_active: true,
  last_login: NOW,
  date_joined: NOW,
};

export const USERS_RESPONSE = {
  users: [ADMIN_USER],
  count: 1,
  total: 1,
};

export const DLQ_MESSAGE = {
  dlq_message_id: "dlq-message-1",
  operation_id: WORKFLOW_OPERATION.id,
  original_message_id: "original-message-1",
  worker_id: "worker-1",
  failed_at: NOW,
  error_code: "network_error",
  error_message: "Temporary failure while executing operation",
};

export const DLQ_LIST_RESPONSE = {
  messages: [DLQ_MESSAGE],
  count: 1,
  total: 1,
};

export const ACTIVE_ARTIFACT = {
  id: "artifact-services-config",
  name: "services-config",
  kind: "config_xml",
  is_versioned: true,
  tags: ["services"],
  is_deleted: false,
  deleted_at: null,
  purge_state: "none",
  purge_after: null,
  purge_blocked_until: null,
  purge_blockers: [],
  created_at: NOW,
};

export const DELETED_ARTIFACT = {
  ...ACTIVE_ARTIFACT,
  id: "artifact-services-config-deleted",
  name: "services-config-deleted",
  is_deleted: true,
  deleted_at: NOW,
};

export const ARTIFACT_VERSIONS_RESPONSE = {
  versions: [
    {
      id: "artifact-version-1",
      version: "v1",
      filename: "services-config.xml",
      storage_key: "artifacts/services-config/v1.xml",
      size: 128,
      checksum: "a".repeat(64),
      content_type: "application/xml",
      metadata: {},
      created_at: NOW,
    },
  ],
  count: 1,
};

export const ARTIFACT_ALIASES_RESPONSE = {
  aliases: [
    {
      id: "artifact-alias-stable",
      alias: "stable",
      version: "v1",
      version_id: "artifact-version-1",
      updated_at: NOW,
    },
  ],
  count: 1,
};

export const EXTENSIONS_OVERVIEW_RESPONSE = {
  extensions: [
    {
      name: "ServicePublisher",
      purpose:
        "Publishes service-related extensions across accessible databases.",
      flags: {
        active: {
          policy: true,
          observed: {
            state: "on",
            true_count: 1,
            false_count: 0,
            unknown_count: 0,
          },
          drift_count: 0,
          unknown_drift_count: 0,
        },
        safe_mode: {
          policy: false,
          observed: {
            state: "off",
            true_count: 0,
            false_count: 1,
            unknown_count: 0,
          },
          drift_count: 0,
          unknown_drift_count: 0,
        },
        unsafe_action_protection: {
          policy: true,
          observed: {
            state: "on",
            true_count: 1,
            false_count: 0,
            unknown_count: 0,
          },
          drift_count: 0,
          unknown_drift_count: 0,
        },
      },
      installed_count: 1,
      active_count: 1,
      inactive_count: 0,
      missing_count: 0,
      unknown_count: 0,
      versions: [{ version: "1.0.0", count: 1 }],
      latest_snapshot_at: NOW,
    },
  ],
  count: 1,
  total: 1,
  total_databases: 1,
};

export const EXTENSIONS_DATABASES_RESPONSE = {
  databases: [
    {
      database_id: DATABASE_ID,
      database_name: DATABASE_RECORD.name,
      cluster_id: "cluster-1",
      cluster_name: "Main Cluster",
      status: "active",
      version: "1.0.0",
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
};

export const EXTENSIONS_MANUAL_BINDINGS_RESPONSE = {
  bindings: [
    {
      manual_operation: "extensions.set_flags",
      template_id: "tpl-sync-extension",
      updated_at: NOW,
      updated_by: "analyst",
    },
  ],
};

export const RUNTIME_SETTINGS_RESPONSE = {
  settings: [
    {
      key: "runtime.concurrency.max_workers",
      value: 8,
      source: "runtime",
      value_type: "int",
      description: "Maximum number of concurrent workers.",
      min_value: 1,
      max_value: 32,
      default: 4,
    },
    {
      key: "runtime.feature_flags.enable_fast_path",
      value: true,
      source: "runtime",
      value_type: "bool",
      description: "Enables the fast-path runtime optimization.",
      min_value: null,
      max_value: null,
      default: false,
    },
    {
      key: "observability.timeline.polling_interval_seconds",
      value: 15,
      source: "runtime",
      value_type: "int",
      description: "Polling interval for timeline reads.",
      min_value: 5,
      max_value: 60,
      default: 10,
    },
    {
      key: "observability.timeline.enable_projection_refresh",
      value: true,
      source: "runtime",
      value_type: "bool",
      description: "Enables projection refresh for timeline consumers.",
      min_value: null,
      max_value: null,
      default: true,
    },
  ],
};

export const RUNTIME_CONTROL_CATALOG_RESPONSE = {
  runtimes: [
    {
      runtime_id: "local:localhost:orchestrator",
      runtime_name: "orchestrator",
      display_name: "orchestrator",
      provider: { key: "local_scripts", host: "localhost" },
      observed_state: {
        status: "degraded",
        process_status: "up(pid=4201)",
        http_status: "up(http=200)",
        raw_probe: "orchestrator proc=up(pid=4201) http=up(http=200)",
        command_status: "success",
      },
      type: "django",
      stack: "python",
      entrypoint: "./debug/restart-runtime.sh orchestrator",
      health: "http://orchestrator.local/health",
      supported_actions: ["probe", "restart", "tail_logs"],
      logs_available: true,
      scheduler_supported: false,
    },
    {
      runtime_id: "local:localhost:worker-workflows",
      runtime_name: "worker-workflows",
      display_name: "worker-workflows",
      provider: { key: "local_scripts", host: "localhost" },
      observed_state: {
        status: "online",
        process_status: "up(pid=4310)",
        http_status: "up(http=200)",
        raw_probe: "worker-workflows proc=up(pid=4310) http=up(http=200)",
        command_status: "success",
      },
      type: "go-service",
      stack: "go",
      entrypoint: "./debug/restart-runtime.sh worker-workflows",
      health: "http://worker-workflows.local/health",
      supported_actions: ["probe", "restart", "tail_logs", "trigger_now"],
      logs_available: true,
      scheduler_supported: true,
      desired_state: {
        scheduler_enabled: true,
        jobs: [
          {
            job_name: "pool_factual_active_sync",
            runtime_id: "local:localhost:worker-workflows",
            runtime_name: "worker-workflows",
            display_name: "Pool factual active sync",
            description:
              "Scans active pools and refreshes factual checkpoint windows for the current quarter.",
            enabled: true,
            schedule: "@every 120s",
            schedule_apply_mode: "controlled_restart",
            enablement_apply_mode: "live",
            latest_run_id: 4101,
            latest_run_status: "success",
            latest_run_started_at: NOW,
          },
          {
            job_name: "pool_factual_closed_quarter_reconcile",
            runtime_id: "local:localhost:worker-workflows",
            runtime_name: "worker-workflows",
            display_name: "Pool factual closed-quarter reconcile",
            description:
              "Creates and advances reconcile checkpoints for closed-quarter factual scopes.",
            enabled: true,
            schedule: "0 2 * * *",
            schedule_apply_mode: "controlled_restart",
            enablement_apply_mode: "live",
            latest_run_id: 4102,
            latest_run_status: "success",
            latest_run_started_at: NOW,
          },
        ],
      },
    },
  ],
};

export const RUNTIME_CONTROL_DETAILS = {
  "local:localhost:orchestrator": {
    ...RUNTIME_CONTROL_CATALOG_RESPONSE.runtimes[0],
    logs_excerpt: {
      available: true,
      excerpt: "orchestrator\nqueue_lag=12\nsecret=[REDACTED]",
      path: "/logs/orchestrator.log",
      updated_at: NOW,
    },
    recent_actions: [
      {
        id: "runtime-action-orchestrator-1",
        provider: "local_scripts",
        runtime_id: "local:localhost:orchestrator",
        runtime_name: "orchestrator",
        action_type: "probe",
        target_job_name: "",
        status: "success",
        reason: "",
        requested_by_username: "ui-platform",
        requested_at: NOW,
        started_at: NOW,
        finished_at: NOW,
        result_excerpt: "orchestrator proc=up(pid=4201) http=up(http=200)",
        result_payload: { command_status: "success" },
        error_message: "",
        scheduler_job_run_id: null,
      },
    ],
  },
  "local:localhost:worker-workflows": {
    ...RUNTIME_CONTROL_CATALOG_RESPONSE.runtimes[1],
    logs_excerpt: {
      available: true,
      excerpt: "worker-workflows\nlast_tick=2026-03-10T12:00:00Z",
      path: "/logs/worker-workflows.log",
      updated_at: NOW,
    },
    recent_actions: [],
  },
};

export const COMMAND_SCHEMAS_EDITOR_VIEW = {
  driver: "ibcmd",
  etag: "command-schemas-etag-1",
  base: {
    approved_version: "approved-v1",
    approved_version_id: "approved-v1-id",
    latest_version: "latest-v1",
    latest_version_id: "latest-v1-id",
  },
  overrides: {
    active_version: "overrides-v1",
    active_version_id: "overrides-v1-id",
  },
  catalogs: {
    base: {
      catalog_version: 2,
      driver: "ibcmd",
      commands_by_id: {
        "ibcmd.publish": {
          label: "Publish infobase",
          description: "Publishes the selected infobase.",
          argv: ["ibcmd", "publish"],
          scope: "per_database",
          risk_level: "safe",
          params_by_name: {
            mode: {
              kind: "flag",
              flag: "--mode",
              required: false,
              expects_value: true,
              label: "Mode",
              description: "Publication mode",
              value_type: "string",
              enum: ["safe", "force"],
            },
          },
        },
      },
    },
    overrides: {
      catalog_version: 2,
      driver: "ibcmd",
      overrides: {
        driver_schema: {},
        commands_by_id: {},
      },
    },
    effective: {
      base_version: "approved-v1",
      base_version_id: "approved-v1-id",
      base_alias: "approved",
      overrides_version: "overrides-v1",
      overrides_version_id: "overrides-v1-id",
      source: "merged",
      catalog: {
        catalog_version: 2,
        driver: "ibcmd",
        commands_by_id: {
          "ibcmd.publish": {
            label: "Publish infobase",
            description: "Publishes the selected infobase.",
            argv: ["ibcmd", "publish"],
            scope: "per_database",
            risk_level: "safe",
            params_by_name: {
              mode: {
                kind: "flag",
                flag: "--mode",
                required: false,
                expects_value: true,
                label: "Mode",
                description: "Publication mode",
                value_type: "string",
                enum: ["safe", "force"],
              },
            },
          },
        },
      },
    },
  },
};

export const RBAC_AUDIT_RESPONSE = {
  items: [
    {
      id: 1,
      created_at: NOW,
      actor_username: "admin",
      actor_id: 1,
      action: "role.updated",
      outcome: "success",
      target_type: "role",
      target_id: "services_operator",
      metadata: { reason: "Initial bootstrap" },
      error_message: "",
    },
  ],
  count: 1,
  total: 1,
};

export async function fulfillJson(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(data),
    headers: { "cache-control": "no-store" },
  });
}

export type RequestCounts = {
  bootstrap: number;
  meReads: number;
  myTenantsReads: number;
  streamTickets: number;
  usersList: number;
  usersDetail: number;
  dlqList: number;
  dlqDetail: number;
  artifactsList: number;
  artifactDetail: number;
  extensionsOverview: number;
  extensionsOverviewDatabases: number;
  extensionsManualBindings: number;
  runtimeSettingsReads: number;
  streamMuxStatusReads: number;
  commandSchemasEditorReads: number;
  clusterLists: number;
  clusterDetails: number;
  databaseLists: number;
  systemHealthReads: number;
  runtimeControlCatalogReads: number;
  runtimeControlRuntimeReads: number;
  runtimeControlActionWrites: number;
  runtimeControlDesiredStateWrites: number;
  serviceHistoryReads: number;
  metadataManagementReads: number;
  decisionsScoped: number;
  decisionsUnscoped: number;
  bindingProfilesList: number;
  bindingProfileDetails: number;
  organizationPools: number;
  poolOrganizations: number;
  poolOrganizationDetails: number;
  poolGraphs: number;
  poolTopologySnapshots: number;
  poolRuns: number;
  poolRunReports: number;
  operationsList: number;
  operationDetails: number;
};

export function createRequestCounts(): RequestCounts {
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
  };
}

export async function setupAuth(
  page: Page,
  options?: { localeOverride?: "ru" | "en" | null },
) {
  await page.addInitScript(
    ({ tenantId, serviceMeshMetricsMessage, localeOverride }) => {
      window.__CC1C_ENV__ = {
        VITE_BASE_HOST: "127.0.0.1",
        VITE_API_URL: "http://127.0.0.1:15173",
        VITE_WS_HOST: "127.0.0.1:15173",
      };

      const NativeWebSocket = window.WebSocket;
      class QuietServiceMeshWebSocket implements Partial<WebSocket> {
        static readonly CONNECTING = NativeWebSocket.CONNECTING;
        static readonly OPEN = NativeWebSocket.OPEN;
        static readonly CLOSING = NativeWebSocket.CLOSING;
        static readonly CLOSED = NativeWebSocket.CLOSED;

        readonly CONNECTING = NativeWebSocket.CONNECTING;
        readonly OPEN = NativeWebSocket.OPEN;
        readonly CLOSING = NativeWebSocket.CLOSING;
        readonly CLOSED = NativeWebSocket.CLOSED;

        readonly url: string;
        readonly protocol = "";
        readonly extensions = "";
        binaryType: BinaryType = "blob";
        bufferedAmount = 0;
        readyState = NativeWebSocket.CONNECTING;
        onopen: ((this: WebSocket, ev: Event) => unknown) | null = null;
        onclose: ((this: WebSocket, ev: CloseEvent) => unknown) | null = null;
        onerror: ((this: WebSocket, ev: Event) => unknown) | null = null;
        onmessage: ((this: WebSocket, ev: MessageEvent) => unknown) | null =
          null;

        constructor(url: string | URL) {
          this.url = typeof url === "string" ? url : url.toString();
          queueMicrotask(() => {
            this.readyState = NativeWebSocket.OPEN;
            this.onopen?.call(this as WebSocket, new Event("open"));
            queueMicrotask(() => {
              this.onmessage?.call(
                this as WebSocket,
                new MessageEvent("message", {
                  data: JSON.stringify(serviceMeshMetricsMessage),
                }),
              );
            });
          });
        }

        addEventListener() {}
        removeEventListener() {}
        dispatchEvent() {
          return true;
        }

        close(code?: number, reason?: string) {
          this.readyState = NativeWebSocket.CLOSED;
          const event = new CloseEvent("close", {
            code: code ?? 1000,
            reason: reason ?? "",
            wasClean: true,
          });
          this.onclose?.call(this as WebSocket, event);
        }

        send(payload?: string) {
          try {
            const message =
              typeof payload === "string"
                ? (JSON.parse(payload) as { action?: string })
                : null;
            if (message?.action === "get_metrics") {
              queueMicrotask(() => {
                this.onmessage?.call(
                  this as WebSocket,
                  new MessageEvent("message", {
                    data: JSON.stringify(serviceMeshMetricsMessage),
                  }),
                );
              });
            }
          } catch {
            // ignore malformed test payloads
          }
        }
      }

      window.WebSocket = class extends NativeWebSocket {
        constructor(url: string | URL, protocols?: string | string[]) {
          const nextUrl = typeof url === "string" ? url : url.toString();
          if (nextUrl.includes("/ws/service-mesh/")) {
            return new QuietServiceMeshWebSocket(url) as WebSocket;
          }
          super(url, protocols);
        }
      } as typeof WebSocket;

      localStorage.setItem("auth_token", "test-token");
      localStorage.setItem("active_tenant_id", tenantId);
      if (localeOverride) {
        if (!localStorage.getItem("cc1c_locale_override")) {
          localStorage.setItem("cc1c_locale_override", localeOverride);
        }
      } else {
        localStorage.removeItem("cc1c_locale_override");
      }
    },
    {
      tenantId: TENANT_ID,
      serviceMeshMetricsMessage: SERVICE_MESH_METRICS_MESSAGE,
      localeOverride: options?.localeOverride ?? null,
    },
  );
}

export async function setupPersistentDatabaseStream(page: Page) {
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window);
    const encoder = new TextEncoder();

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;

      if (url.includes("/api/v2/databases/stream/")) {
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(
              encoder.encode(
                `id: ready-1\ndata: ${JSON.stringify({
                  version: "1.0",
                  type: "database_stream_connected",
                })}\n\n`,
              ),
            );
          },
        });

        return new Response(stream, {
          status: 200,
          headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-store",
          },
        });
      }

      return originalFetch(input, init);
    };
  });
}

export async function setupUiPlatformMocks(
  page: Page,
  options?: {
    isStaff?: boolean;
    canManageRuntimeControls?: boolean;
    counts?: RequestCounts;
    clusterAccessLevel?: "VIEW" | "OPERATE" | "MANAGE" | "ADMIN" | null;
    clusterDetailDelayMs?: number;
    selectedUserOutsideCatalogSlice?: boolean;
    selectedDlqOutsideCatalogSlice?: boolean;
    selectedArtifactOutsideCatalogSlice?: boolean;
    observedLocaleHeaders?: string[];
  },
) {
  const counts = options?.counts;
  const isStaff = options?.isStaff ?? false;
  const canManageRuntimeControls = options?.canManageRuntimeControls ?? false;
  const clusterAccessLevel = options?.clusterAccessLevel ?? null;
  const clusterDetailDelayMs = options?.clusterDetailDelayMs ?? 0;
  const selectedUserOutsideCatalogSlice =
    options?.selectedUserOutsideCatalogSlice ?? false;
  const selectedDlqOutsideCatalogSlice =
    options?.selectedDlqOutsideCatalogSlice ?? false;
  const selectedArtifactOutsideCatalogSlice =
    options?.selectedArtifactOutsideCatalogSlice ?? false;
  const observedLocaleHeaders = options?.observedLocaleHeaders;
  const currentUser = { id: 1, username: "ui-platform", is_staff: isStaff };
  const tenantContext = {
    active_tenant_id: TENANT_ID,
    tenants: [
      { id: TENANT_ID, slug: "default", name: "Default", role: "owner" },
    ],
  };
  const organization = {
    id: "organization-main",
    tenant_id: TENANT_ID,
    database_id: DATABASE_ID,
    name: "Org One",
    full_name: "Org One LLC",
    inn: "730000000001",
    kpp: "123456789",
    status: "active",
    external_ref: "",
    metadata: {},
    created_at: NOW,
    updated_at: NOW,
  };
  const topologyTemplates = [
    JSON.parse(JSON.stringify(TOPOLOGY_TEMPLATE)) as typeof TOPOLOGY_TEMPLATE,
  ];
  const factualWorkspace = JSON.parse(
    JSON.stringify(POOL_FACTUAL_WORKSPACE),
  ) as typeof POOL_FACTUAL_WORKSPACE;
  const masterDataRegistry = JSON.parse(
    JSON.stringify(MASTER_DATA_REGISTRY_RESPONSE),
  ) as typeof MASTER_DATA_REGISTRY_RESPONSE;
  const masterDataParties = JSON.parse(
    JSON.stringify(MASTER_DATA_PARTIES),
  ) as typeof MASTER_DATA_PARTIES;
  const masterDataItems = JSON.parse(
    JSON.stringify(MASTER_DATA_ITEMS),
  ) as typeof MASTER_DATA_ITEMS;
  const masterDataContracts = JSON.parse(
    JSON.stringify(MASTER_DATA_CONTRACTS),
  ) as typeof MASTER_DATA_CONTRACTS;
  const masterDataTaxProfiles = JSON.parse(
    JSON.stringify(MASTER_DATA_TAX_PROFILES),
  ) as typeof MASTER_DATA_TAX_PROFILES;
  const masterDataGlAccounts = JSON.parse(
    JSON.stringify(MASTER_DATA_GL_ACCOUNTS),
  ) as typeof MASTER_DATA_GL_ACCOUNTS;
  const workflowBindings = JSON.parse(
    JSON.stringify(POOL_WITH_ATTACHMENT.workflow_bindings),
  );
  const systemHealthResponse = JSON.parse(
    JSON.stringify(SYSTEM_HEALTH_RESPONSE),
  ) as typeof SYSTEM_HEALTH_RESPONSE;
  const runtimeControlCatalog = JSON.parse(
    JSON.stringify(RUNTIME_CONTROL_CATALOG_RESPONSE),
  ) as typeof RUNTIME_CONTROL_CATALOG_RESPONSE;
  const runtimeControlDetails = JSON.parse(
    JSON.stringify(RUNTIME_CONTROL_DETAILS),
  ) as typeof RUNTIME_CONTROL_DETAILS;

  if (canManageRuntimeControls) {
    const orchestratorService = systemHealthResponse.services.find(
      (service) => service.name === "orchestrator",
    );
    if (orchestratorService) {
      orchestratorService.name = "Orchestrator";
    }
    systemHealthResponse.services.push({
      name: "Worker Workflows",
      type: "go-service",
      url: "http://worker-workflows.local/health",
      status: "online",
      response_time_ms: 29,
      last_check: NOW,
      details: {
        scheduler: "active",
      },
    });
    systemHealthResponse.statistics.total =
      systemHealthResponse.services.length;
    systemHealthResponse.statistics.online = 3;
  }

  const buildPagedResponse = <T>(items: T[], key: string, url: URL) => ({
    [key]: items,
    count: items.length,
    limit: Number(url.searchParams.get("limit") || 50),
    offset: Number(url.searchParams.get("offset") || 0),
  });

  await page.route("**/api/v2/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const requestedLocaleHeader = request.headers()["x-cc1c-locale"];
    const requestedLocale =
      requestedLocaleHeader === "ru" || requestedLocaleHeader === "en"
        ? requestedLocaleHeader
        : undefined;

    if (method === "GET" && path === "/api/v2/system/bootstrap/") {
      if (counts) {
        counts.bootstrap += 1;
      }
      observedLocaleHeaders?.push(requestedLocale ?? "");
      return fulfillJson(route, {
        me: currentUser,
        tenant_context: tenantContext,
        access: {
          user: { id: currentUser.id, username: currentUser.username },
          clusters: clusterAccessLevel
            ? [
                {
                  cluster: { id: CLUSTER_RECORD.id, name: CLUSTER_RECORD.name },
                  level: clusterAccessLevel,
                },
              ]
            : [],
          databases: [],
          operation_templates: [],
        },
        capabilities: {
          can_manage_rbac: isStaff,
          can_manage_driver_catalogs: isStaff,
          can_manage_runtime_controls: canManageRuntimeControls,
        },
        i18n: {
          supported_locales: ["ru", "en"],
          default_locale: "ru",
          requested_locale: requestedLocale ?? null,
          effective_locale: requestedLocale ?? "ru",
        },
      });
    }

    if (method === "GET" && path === "/api/v2/system/me/") {
      if (counts) {
        counts.meReads += 1;
      }
      return fulfillJson(route, currentUser);
    }

    if (method === "GET" && path === "/api/v2/ui/table-metadata/") {
      return fulfillJson(route, {
        table: String(url.searchParams.get("table") || ""),
        columns: [],
      });
    }

    if (method === "GET" && path === "/api/v2/tenants/list-my-tenants/") {
      if (counts) {
        counts.myTenantsReads += 1;
      }
      return fulfillJson(route, tenantContext);
    }

    if (method === "GET" && path === "/api/v2/system/config/") {
      return fulfillJson(route, {
        ras_default_server: `${CLUSTER_RECORD.ras_host}:${CLUSTER_RECORD.ras_port}`,
      });
    }

    if (method === "GET" && path === "/api/v2/databases/list-databases/") {
      if (counts) {
        counts.databaseLists += 1;
      }
      return fulfillJson(route, {
        databases: [DATABASE_RECORD],
        count: 1,
        total: 1,
      });
    }

    if (method === "GET" && path === "/api/v2/clusters/list-clusters/") {
      if (counts) {
        counts.clusterLists += 1;
      }
      return fulfillJson(route, {
        clusters: [CLUSTER_RECORD],
        count: 1,
        total: 1,
      });
    }

    if (method === "GET" && path === "/api/v2/clusters/get-cluster/") {
      if (counts) {
        counts.clusterDetails += 1;
      }
      if (clusterDetailDelayMs > 0) {
        await new Promise((resolve) =>
          setTimeout(resolve, clusterDetailDelayMs),
        );
      }
      return fulfillJson(route, CLUSTER_DETAIL_RESPONSE);
    }

    if (method === "GET" && path === "/api/v2/databases/get-database/") {
      return fulfillJson(route, {
        database: DATABASE_RECORD,
      });
    }

    if (
      method === "GET" &&
      path === "/api/v2/databases/get-metadata-management/"
    ) {
      if (counts) {
        counts.metadataManagementReads += 1;
      }
      return fulfillJson(route, METADATA_MANAGEMENT);
    }

    if (method === "POST" && path === "/api/v2/databases/stream-ticket/") {
      if (counts) {
        counts.streamTickets += 1;
      }
      return fulfillJson(route, {
        ticket: `ticket-${counts?.streamTickets ?? 1}`,
        expires_in: 30,
        stream_url: `/api/v2/databases/stream/?ticket=ticket-${counts?.streamTickets ?? 1}`,
        session_id: "browser-session",
        lease_id: `lease-${counts?.streamTickets ?? 1}`,
        client_instance_id: "browser-instance",
        scope: "__all__",
        message: "Database stream ticket issued",
      });
    }

    if (method === "GET" && path === "/api/v2/decisions/") {
      const databaseId = url.searchParams.get("database_id") || "";
      if (databaseId) {
        if (counts) {
          counts.decisionsScoped += 1;
        }
      } else if (counts) {
        counts.decisionsUnscoped += 1;
      }
      return fulfillJson(route, {
        decisions: DECISIONS,
        count: DECISIONS.length,
        ...(databaseId ? { metadata_context: METADATA_CONTEXT } : {}),
      });
    }

    if (method === "GET" && path === "/api/v2/workflows/list-workflows/") {
      return fulfillJson(route, {
        workflows: [WORKFLOW],
        count: 1,
        total: 1,
        authoring_phase: null,
      });
    }

    if (method === "GET" && path === "/api/v2/workflows/list-executions/") {
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
      });
    }

    if (method === "GET" && path === "/api/v2/workflows/get-execution/") {
      const executionId = String(url.searchParams.get("execution_id") || "");
      if (executionId !== POOL_RUN.workflow_execution_id) {
        return fulfillJson(
          route,
          { detail: "Workflow execution not found." },
          404,
        );
      }
      return fulfillJson(route, {
        execution: WORKFLOW_EXECUTION_DETAIL,
        execution_plan: {
          kind: "workflow",
          workflow_id: WORKFLOW.id,
          input_context_masked: {
            pool_id: POOL_RUN.pool_id,
          },
        },
        bindings: [
          {
            target_ref: "pool_id",
            source_ref: "request.pool_id",
            resolve_at: "api",
            sensitive: false,
            status: "applied",
          },
        ],
        steps: [],
      });
    }

    if (method === "GET" && path === "/api/v2/workflows/get-workflow/") {
      const workflowId = String(url.searchParams.get("workflow_id") || "");
      if (workflowId !== WORKFLOW.id) {
        return fulfillJson(route, { detail: "Workflow not found." }, 404);
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
      });
    }

    if (method === "GET" && path === "/api/v2/operation-catalog/exposures/") {
      return fulfillJson(route, {
        exposures: [
          {
            id: "template-exposure-1",
            definition_id: "definition-1",
            surface: "template",
            alias: "tpl-sync-extension",
            name: "Sync Extension",
            description: "Syncs extension state",
            is_active: true,
            capability: "extensions.sync",
            status: "published",
            operation_type: "designer_cli",
            template_exposure_revision: 4,
          },
          {
            id: "template-exposure-2",
            definition_id: "definition-2",
            surface: "template",
            alias: "tpl-set-flags-extension",
            name: "Set Extension Flags",
            description: "Updates extension flags on selected databases",
            is_active: true,
            capability: "extensions.set_flags",
            status: "published",
            operation_type: "designer_cli",
            template_exposure_revision: 3,
          },
        ],
        count: 2,
        total: 2,
      });
    }

    if (method === "GET" && path === "/api/v2/extensions/overview/") {
      if (counts) {
        counts.extensionsOverview += 1;
      }
      return fulfillJson(route, EXTENSIONS_OVERVIEW_RESPONSE);
    }

    if (method === "GET" && path === "/api/v2/extensions/overview/databases/") {
      if (counts) {
        counts.extensionsOverviewDatabases += 1;
      }
      return fulfillJson(route, EXTENSIONS_DATABASES_RESPONSE);
    }

    if (
      method === "GET" &&
      path === "/api/v2/extensions/manual-operation-bindings/"
    ) {
      if (counts) {
        counts.extensionsManualBindings += 1;
      }
      return fulfillJson(route, EXTENSIONS_MANUAL_BINDINGS_RESPONSE);
    }

    const manualBindingMatch = path.match(
      /^\/api\/v2\/extensions\/manual-operation-bindings\/([^/]+)\/$/,
    );
    if (method === "PUT" && manualBindingMatch) {
      const manualOperation = manualBindingMatch[1] ?? "extensions.set_flags";
      const payload = request.postDataJSON() as { template_id?: string } | null;
      return fulfillJson(route, {
        binding: {
          manual_operation: manualOperation,
          template_id: payload?.template_id || "tpl-set-flags-extension",
          updated_at: NOW,
          updated_by: "ui-platform",
        },
      });
    }

    if (method === "DELETE" && manualBindingMatch) {
      return fulfillJson(route, { deleted: true }, 204);
    }

    if (method === "GET" && path === "/api/v2/operations/list-operations/") {
      if (counts) {
        counts.operationsList += 1;
      }
      return fulfillJson(route, {
        operations: OPERATIONS,
        count: OPERATIONS.length,
        total: OPERATIONS.length,
      });
    }

    if (method === "GET" && path === "/api/v2/operations/get-operation/") {
      const operationId = String(url.searchParams.get("operation_id") || "");
      const detail = OPERATION_DETAILS[operationId];
      if (!detail) {
        return fulfillJson(route, { detail: "Operation not found." }, 404);
      }
      if (counts) {
        counts.operationDetails += 1;
      }
      return fulfillJson(route, detail);
    }

    if (
      method === "POST" &&
      path === "/api/v2/operations/get-operation-timeline/"
    ) {
      const payload = request.postDataJSON() as {
        operation_id?: string;
      } | null;
      const operationId =
        typeof payload?.operation_id === "string" ? payload.operation_id : "";
      const timeline = OPERATION_TIMELINES[operationId];
      if (!timeline) {
        return fulfillJson(
          route,
          { detail: "Operation timeline not found." },
          404,
        );
      }
      return fulfillJson(route, timeline);
    }

    if (method === "GET" && path === "/api/v2/operations/stream-mux-status/") {
      if (counts) {
        counts.streamMuxStatusReads += 1;
      }
      return fulfillJson(route, {
        active_streams: 2,
        max_streams: 16,
        active_subscriptions: 3,
        max_subscriptions: 64,
      });
    }

    if (method === "GET" && path === "/api/v2/system/health/") {
      if (counts) {
        counts.systemHealthReads += 1;
      }
      return fulfillJson(route, systemHealthResponse);
    }

    if (
      method === "GET" &&
      path === "/api/v2/system/runtime-control/catalog/"
    ) {
      if (counts) {
        counts.runtimeControlCatalogReads += 1;
      }
      if (!canManageRuntimeControls) {
        return fulfillJson(
          route,
          { success: false, error: { code: "PERMISSION_DENIED" } },
          403,
        );
      }
      return fulfillJson(route, runtimeControlCatalog);
    }

    const runtimeControlDesiredStateMatch = path.match(
      /^\/api\/v2\/system\/runtime-control\/runtimes\/(.+)\/desired-state\/$/,
    );
    if (method === "PATCH" && runtimeControlDesiredStateMatch) {
      if (counts) {
        counts.runtimeControlDesiredStateWrites += 1;
      }
      const runtimeId = decodeURIComponent(
        runtimeControlDesiredStateMatch[1] ?? "",
      );
      const detail =
        runtimeControlDetails[runtimeId as keyof typeof runtimeControlDetails];
      if (!detail || !detail.desired_state) {
        return fulfillJson(
          route,
          { success: false, error: { code: "NOT_FOUND" } },
          404,
        );
      }
      const payload = request.postDataJSON() as {
        scheduler_enabled?: boolean;
        jobs?: Array<{
          job_name: string;
          enabled?: boolean;
          schedule?: string;
        }>;
      } | null;
      if (typeof payload?.scheduler_enabled === "boolean") {
        detail.desired_state.scheduler_enabled = payload.scheduler_enabled;
      }
      for (const jobPatch of payload?.jobs ?? []) {
        const job = detail.desired_state.jobs.find(
          (item) => item.job_name === jobPatch.job_name,
        );
        if (!job) continue;
        if (typeof jobPatch.enabled === "boolean") {
          job.enabled = jobPatch.enabled;
        }
        if (typeof jobPatch.schedule === "string") {
          job.schedule = jobPatch.schedule;
        }
      }
      const catalogRuntime = runtimeControlCatalog.runtimes.find(
        (item) => item.runtime_id === runtimeId,
      );
      if (catalogRuntime) {
        catalogRuntime.desired_state = JSON.parse(
          JSON.stringify(detail.desired_state),
        );
      }
      return fulfillJson(route, {
        runtime_id: runtimeId,
        desired_state: detail.desired_state,
      });
    }

    const runtimeControlRuntimeActionsMatch = path.match(
      /^\/api\/v2\/system\/runtime-control\/runtimes\/(.+)\/actions\/$/,
    );
    if (method === "GET" && runtimeControlRuntimeActionsMatch) {
      const runtimeId = decodeURIComponent(
        runtimeControlRuntimeActionsMatch[1] ?? "",
      );
      const detail =
        runtimeControlDetails[runtimeId as keyof typeof runtimeControlDetails];
      return fulfillJson(route, { actions: detail?.recent_actions ?? [] });
    }

    const runtimeControlRuntimeMatch = path.match(
      /^\/api\/v2\/system\/runtime-control\/runtimes\/(.+)\/$/,
    );
    if (method === "GET" && runtimeControlRuntimeMatch) {
      if (counts) {
        counts.runtimeControlRuntimeReads += 1;
      }
      if (!canManageRuntimeControls) {
        return fulfillJson(
          route,
          { success: false, error: { code: "PERMISSION_DENIED" } },
          403,
        );
      }
      const runtimeId = decodeURIComponent(runtimeControlRuntimeMatch[1] ?? "");
      const detail =
        runtimeControlDetails[runtimeId as keyof typeof runtimeControlDetails];
      if (!detail) {
        return fulfillJson(
          route,
          { success: false, error: { code: "NOT_FOUND" } },
          404,
        );
      }
      return fulfillJson(route, { runtime: detail });
    }

    if (
      method === "POST" &&
      path === "/api/v2/system/runtime-control/actions/"
    ) {
      if (counts) {
        counts.runtimeControlActionWrites += 1;
      }
      const payload = request.postDataJSON() as {
        runtime_id?: string;
        action_type?: "probe" | "restart" | "tail_logs" | "trigger_now";
        reason?: string;
        target_job_name?: string;
      } | null;
      const runtimeId = String(payload?.runtime_id || "");
      const detail =
        runtimeControlDetails[runtimeId as keyof typeof runtimeControlDetails];
      if (!detail) {
        return fulfillJson(
          route,
          { success: false, error: { code: "NOT_FOUND" } },
          404,
        );
      }
      const action = {
        id: `runtime-action-${detail.recent_actions.length + 1}`,
        provider: "local_scripts",
        runtime_id: runtimeId,
        runtime_name: detail.runtime_name,
        action_type: payload?.action_type ?? "probe",
        target_job_name: payload?.target_job_name ?? "",
        status: "accepted",
        reason: payload?.reason ?? "",
        requested_by_username: "ui-platform",
        requested_at: NOW,
        started_at: null,
        finished_at: null,
        result_excerpt: "",
        result_payload: {},
        error_message: "",
        scheduler_job_run_id:
          payload?.action_type === "trigger_now" ? 6001 : null,
      };
      detail.recent_actions = [action, ...detail.recent_actions].slice(0, 10);
      if (payload?.action_type === "tail_logs" && detail.logs_excerpt) {
        detail.logs_excerpt.updated_at = NOW;
      }
      if (payload?.action_type === "trigger_now" && detail.desired_state) {
        const job = detail.desired_state.jobs.find(
          (item) => item.job_name === payload.target_job_name,
        );
        if (job) {
          job.latest_run_status = "success";
          job.latest_run_started_at = NOW;
          job.latest_run_id = (job.latest_run_id ?? 7000) + 1;
        }
      }
      return fulfillJson(route, { action }, 202);
    }

    if (method === "GET" && path === "/api/v2/service-mesh/get-history/") {
      const serviceName = String(url.searchParams.get("service") || "");
      const history = SERVICE_MESH_HISTORY[serviceName];
      if (!history) {
        return fulfillJson(
          route,
          { detail: "Service history not found." },
          404,
        );
      }
      if (counts) {
        counts.serviceHistoryReads += 1;
      }
      return fulfillJson(route, history);
    }

    if (method === "GET" && path === "/api/v2/settings/runtime/") {
      if (counts) {
        counts.runtimeSettingsReads += 1;
      }
      return fulfillJson(route, RUNTIME_SETTINGS_RESPONSE);
    }

    const runtimeSettingMatch = path.match(
      /^\/api\/v2\/settings\/runtime\/(.+)\/$/,
    );
    if (method === "PATCH" && runtimeSettingMatch) {
      const key = decodeURIComponent(runtimeSettingMatch[1] ?? "");
      const payload = request.postDataJSON() as { value?: unknown } | null;
      const existing = RUNTIME_SETTINGS_RESPONSE.settings.find(
        (item) => item.key === key,
      );
      if (!existing) {
        return fulfillJson(
          route,
          { detail: "Runtime setting not found." },
          404,
        );
      }
      existing.value = payload?.value;
      return fulfillJson(route, existing);
    }

    if (
      method === "GET" &&
      path === "/api/v2/settings/command-schemas/editor/"
    ) {
      if (counts) {
        counts.commandSchemasEditorReads += 1;
      }
      return fulfillJson(route, COMMAND_SCHEMAS_EDITOR_VIEW);
    }

    if (method === "GET" && path === "/api/v2/users/list/") {
      if (counts) {
        counts.usersList += 1;
      }
      const requestedUserId = Number.parseInt(
        url.searchParams.get("id") || "",
        10,
      );
      if (
        Number.isFinite(requestedUserId) &&
        requestedUserId === ADMIN_USER.id
      ) {
        if (counts) {
          counts.usersDetail += 1;
        }
        return fulfillJson(route, {
          users: [ADMIN_USER],
          count: 1,
          total: 1,
        });
      }
      if (selectedUserOutsideCatalogSlice) {
        return fulfillJson(route, {
          users: [],
          count: 0,
          total: 0,
        });
      }
      return fulfillJson(route, USERS_RESPONSE);
    }

    if (method === "GET" && path === "/api/v2/dlq/list/") {
      if (counts) {
        counts.dlqList += 1;
      }
      if (selectedDlqOutsideCatalogSlice) {
        return fulfillJson(route, {
          messages: [],
          count: 0,
          total: 0,
        });
      }
      return fulfillJson(route, DLQ_LIST_RESPONSE);
    }

    if (method === "GET" && path === "/api/v2/dlq/get/") {
      if (counts) {
        counts.dlqDetail += 1;
      }
      const dlqMessageId = String(url.searchParams.get("dlq_message_id") || "");
      if (dlqMessageId !== DLQ_MESSAGE.dlq_message_id) {
        return fulfillJson(route, { detail: "DLQ message not found." }, 404);
      }
      return fulfillJson(route, DLQ_MESSAGE);
    }

    if (method === "POST" && path === "/api/v2/dlq/retry/") {
      return fulfillJson(route, {
        retried: true,
        operation_id: WORKFLOW_OPERATION.id,
      });
    }

    if (method === "GET" && path === "/api/v2/artifacts/") {
      if (counts) {
        counts.artifactsList += 1;
      }
      const artifactId = String(url.searchParams.get("artifact_id") || "");
      const onlyDeleted = url.searchParams.get("only_deleted") === "true";
      if (artifactId === DELETED_ARTIFACT.id) {
        if (counts) {
          counts.artifactDetail += 1;
        }
        return fulfillJson(route, {
          artifacts: [DELETED_ARTIFACT],
          count: 1,
        });
      }
      if (artifactId === ACTIVE_ARTIFACT.id) {
        if (counts) {
          counts.artifactDetail += 1;
        }
        return fulfillJson(route, {
          artifacts: [ACTIVE_ARTIFACT],
          count: 1,
        });
      }
      if (selectedArtifactOutsideCatalogSlice) {
        return fulfillJson(route, {
          artifacts: [],
          count: 0,
        });
      }
      const artifacts = onlyDeleted ? [DELETED_ARTIFACT] : [ACTIVE_ARTIFACT];
      return fulfillJson(route, {
        artifacts,
        count: artifacts.length,
      });
    }

    const artifactVersionsMatch = path.match(
      /^\/api\/v2\/artifacts\/([^/]+)\/versions\/$/,
    );
    if (method === "GET" && artifactVersionsMatch) {
      return fulfillJson(route, ARTIFACT_VERSIONS_RESPONSE);
    }

    const artifactAliasesMatch = path.match(
      /^\/api\/v2\/artifacts\/([^/]+)\/aliases\/$/,
    );
    if (method === "GET" && artifactAliasesMatch) {
      return fulfillJson(route, ARTIFACT_ALIASES_RESPONSE);
    }

    if (method === "GET" && path === "/api/v2/rbac/list-roles/") {
      return fulfillJson(route, {
        roles: [
          {
            id: 1,
            name: "services_operator",
            users_count: 1,
            permissions_count: 2,
            permission_codes: ["databases.view", "operations.view"],
          },
        ],
        count: 1,
        total: 1,
      });
    }

    if (method === "GET" && path === "/api/v2/rbac/list-admin-audit/") {
      return fulfillJson(route, RBAC_AUDIT_RESPONSE);
    }

    const decisionDetailMatch = path.match(/^\/api\/v2\/decisions\/([^/]+)\/$/);
    if (method === "GET" && decisionDetailMatch) {
      const decisionId = decisionDetailMatch[1] ?? DECISION.id;
      return fulfillJson(route, {
        decision:
          DECISIONS.find((candidate) => candidate.id === decisionId) ??
          DECISION,
        ...(url.searchParams.get("database_id")
          ? { metadata_context: METADATA_CONTEXT }
          : {}),
      });
    }

    if (method === "GET" && path === "/api/v2/pools/binding-profiles/") {
      if (counts) {
        counts.bindingProfilesList += 1;
      }
      return fulfillJson(route, {
        binding_profiles: BINDING_PROFILE_SUMMARIES,
        count: BINDING_PROFILE_SUMMARIES.length,
      });
    }

    if (method === "GET" && path === "/api/v2/pools/topology-templates/") {
      return fulfillJson(route, {
        topology_templates: topologyTemplates,
        count: topologyTemplates.length,
      });
    }

    if (method === "GET" && path === "/api/v2/pools/master-data/registry/") {
      return fulfillJson(route, masterDataRegistry);
    }

    if (method === "GET" && path === "/api/v2/pools/master-data/parties/") {
      return fulfillJson(
        route,
        buildPagedResponse(masterDataParties, "parties", url),
      );
    }

    if (method === "GET" && path === "/api/v2/pools/master-data/items/") {
      return fulfillJson(
        route,
        buildPagedResponse(masterDataItems, "items", url),
      );
    }

    if (method === "GET" && path === "/api/v2/pools/master-data/contracts/") {
      return fulfillJson(
        route,
        buildPagedResponse(masterDataContracts, "contracts", url),
      );
    }

    if (
      method === "GET" &&
      path === "/api/v2/pools/master-data/tax-profiles/"
    ) {
      return fulfillJson(
        route,
        buildPagedResponse(masterDataTaxProfiles, "tax_profiles", url),
      );
    }

    if (method === "GET" && path === "/api/v2/pools/master-data/gl-accounts/") {
      return fulfillJson(
        route,
        buildPagedResponse(masterDataGlAccounts, "gl_accounts", url),
      );
    }

    if (method === "GET" && path === "/api/v2/pools/workflow-bindings/") {
      return fulfillJson(route, {
        pool_id: String(
          url.searchParams.get("pool_id") || POOL_WITH_ATTACHMENT.id,
        ),
        workflow_bindings: workflowBindings,
        collection_etag: "bindings-etag-v1",
        blocking_remediation: null,
      });
    }

    const bindingProfileMatch = path.match(
      /^\/api\/v2\/pools\/binding-profiles\/([^/]+)\/$/,
    );
    if (method === "GET" && bindingProfileMatch) {
      const bindingProfileId =
        bindingProfileMatch[1] ?? BINDING_PROFILE_DETAIL.binding_profile_id;
      if (counts) {
        counts.bindingProfileDetails += 1;
      }
      return fulfillJson(route, {
        binding_profile:
          BINDING_PROFILE_DETAILS[bindingProfileId] ?? BINDING_PROFILE_DETAIL,
      });
    }

    if (method === "POST" && path === "/api/v2/pools/topology-templates/") {
      const payload = request.postDataJSON() as Record<string, unknown>;
      const revision =
        payload.revision && typeof payload.revision === "object"
          ? (payload.revision as Record<string, unknown>)
          : {};
      const topologyTemplateId = `template-${topologyTemplates.length + 1}`;
      const topologyTemplateRevisionId = `${topologyTemplateId}-revision-r1`;
      const createdTemplate = {
        topology_template_id: topologyTemplateId,
        code: String(payload.code || "").trim() || topologyTemplateId,
        name: String(payload.name || "").trim() || "New Topology Template",
        description: String(payload.description || ""),
        status: "active",
        metadata:
          payload.metadata && typeof payload.metadata === "object"
            ? payload.metadata
            : {},
        latest_revision_number: 1,
        latest_revision: {
          topology_template_revision_id: topologyTemplateRevisionId,
          topology_template_id: topologyTemplateId,
          revision_number: 1,
          nodes: Array.isArray(revision.nodes) ? revision.nodes : [],
          edges: Array.isArray(revision.edges) ? revision.edges : [],
          metadata:
            revision.metadata && typeof revision.metadata === "object"
              ? revision.metadata
              : {},
          created_at: NOW,
        },
        revisions: [
          {
            topology_template_revision_id: topologyTemplateRevisionId,
            topology_template_id: topologyTemplateId,
            revision_number: 1,
            nodes: Array.isArray(revision.nodes) ? revision.nodes : [],
            edges: Array.isArray(revision.edges) ? revision.edges : [],
            metadata:
              revision.metadata && typeof revision.metadata === "object"
                ? revision.metadata
                : {},
            created_at: NOW,
          },
        ],
        created_at: NOW,
        updated_at: NOW,
      };
      topologyTemplates.unshift(createdTemplate);
      return fulfillJson(route, { topology_template: createdTemplate }, 201);
    }

    const topologyTemplateRevisionMatch = path.match(
      /^\/api\/v2\/pools\/topology-templates\/([^/]+)\/revisions\/$/,
    );
    if (method === "POST" && topologyTemplateRevisionMatch) {
      const topologyTemplateId = topologyTemplateRevisionMatch[1] ?? "";
      const template = topologyTemplates.find(
        (item) => item.topology_template_id === topologyTemplateId,
      );
      if (!template) {
        return fulfillJson(
          route,
          { detail: "Topology template not found." },
          404,
        );
      }
      const payload = request.postDataJSON() as Record<string, unknown>;
      const revision =
        payload.revision && typeof payload.revision === "object"
          ? (payload.revision as Record<string, unknown>)
          : {};
      const revisionNumber = Number(template.latest_revision_number || 0) + 1;
      const nextRevision = {
        topology_template_revision_id: `${topologyTemplateId}-revision-r${revisionNumber}`,
        topology_template_id: topologyTemplateId,
        revision_number: revisionNumber,
        nodes: Array.isArray(revision.nodes) ? revision.nodes : [],
        edges: Array.isArray(revision.edges) ? revision.edges : [],
        metadata:
          revision.metadata && typeof revision.metadata === "object"
            ? revision.metadata
            : {},
        created_at: NOW,
      };
      template.latest_revision_number = revisionNumber;
      template.latest_revision = nextRevision;
      template.revisions = [nextRevision, ...template.revisions];
      template.updated_at = NOW;
      return fulfillJson(route, { topology_template: template });
    }

    if (method === "GET" && path === "/api/v2/pools/") {
      if (counts) {
        counts.organizationPools += 1;
      }
      return fulfillJson(route, {
        pools: [POOL_WITH_ATTACHMENT],
        count: 1,
      });
    }

    if (method === "GET" && path === "/api/v2/pools/schema-templates/") {
      return fulfillJson(route, { templates: [] });
    }

    if (method === "GET" && path === "/api/v2/pools/organizations/") {
      if (counts) {
        counts.poolOrganizations += 1;
      }
      return fulfillJson(route, {
        organizations: [organization],
        count: 1,
      });
    }

    const organizationMatch = path.match(
      /^\/api\/v2\/pools\/organizations\/([^/]+)\/$/,
    );
    if (method === "GET" && organizationMatch) {
      if (counts) {
        counts.poolOrganizationDetails += 1;
      }
      return fulfillJson(route, {
        organization,
        pool_bindings: [],
      });
    }

    const graphMatch = path.match(/^\/api\/v2\/pools\/([^/]+)\/graph\/$/);
    if (method === "GET" && graphMatch) {
      if (counts) {
        counts.poolGraphs += 1;
      }
      return fulfillJson(route, {
        pool_id: graphMatch[1],
        date: "2026-01-01",
        version: "v1:topology-initial",
        nodes: [
          {
            node_version_id: "node-root",
            organization_id: organization.id,
            inn: organization.inn,
            name: organization.name,
            is_root: true,
            metadata: {},
          },
          {
            node_version_id: "node-child",
            organization_id: "organization-child",
            inn: "730000000002",
            name: "Child Org",
            is_root: false,
            metadata: {},
          },
        ],
        edges: [
          {
            edge_version_id: "edge-1",
            parent_node_version_id: "node-root",
            child_node_version_id: "node-child",
            weight: "1",
            min_amount: null,
            max_amount: null,
            metadata: {
              document_policy_key: "document_policy",
            },
          },
        ],
      });
    }

    if (method === "GET" && path === "/api/v2/pools/runs/") {
      if (counts) {
        counts.poolRuns += 1;
      }
      return fulfillJson(route, { runs: [POOL_RUN] });
    }

    if (method === "GET" && path === "/api/v2/pools/batches/") {
      return fulfillJson(route, { batches: [], count: 0 });
    }

    const poolRunReportMatch = path.match(
      /^\/api\/v2\/pools\/runs\/([^/]+)\/report\/$/,
    );
    if (method === "GET" && poolRunReportMatch) {
      if (counts) {
        counts.poolRunReports += 1;
      }
      return fulfillJson(route, POOL_RUN_REPORT);
    }

    if (method === "GET" && path === "/api/v2/pools/factual/overview/") {
      return fulfillJson(route, POOL_FACTUAL_OVERVIEW);
    }

    if (method === "GET" && path === "/api/v2/pools/factual/workspace/") {
      if (
        url.searchParams.get("pool_id") &&
        url.searchParams.get("pool_id") !== POOL_WITH_ATTACHMENT.id
      ) {
        return fulfillJson(
          route,
          { detail: "Pool factual workspace not found." },
          404,
        );
      }
      return fulfillJson(route, factualWorkspace);
    }

    if (method === "POST" && path === "/api/v2/pools/factual/review-actions/") {
      const payload = request.postDataJSON() as {
        review_item_id?: string;
        action?: "attribute" | "reconcile" | "resolve_without_change";
      } | null;
      const reviewItemId = String(payload?.review_item_id || "");
      const action = payload?.action;
      const reviewItem = factualWorkspace.review_queue.items.find(
        (item) => item.id === reviewItemId,
      );
      if (!reviewItem || !action) {
        return fulfillJson(route, { detail: "Review item not found." }, 404);
      }
      reviewItem.status =
        action === "attribute"
          ? "attributed"
          : action === "reconcile"
            ? "reconciled"
            : "resolved_without_change";
      reviewItem.allowed_actions = [];
      reviewItem.attention_required = false;
      reviewItem.resolved_at = NOW;
      factualWorkspace.review_queue.summary.pending_total =
        factualWorkspace.review_queue.items.filter(
          (item) => item.status === "pending",
        ).length;
      factualWorkspace.review_queue.summary.unattributed_total =
        factualWorkspace.review_queue.items.filter(
          (item) => item.status === "pending" && item.reason === "unattributed",
        ).length;
      factualWorkspace.review_queue.summary.late_correction_total =
        factualWorkspace.review_queue.items.filter(
          (item) =>
            item.status === "pending" && item.reason === "late_correction",
        ).length;
      factualWorkspace.review_queue.summary.attention_required_total =
        factualWorkspace.review_queue.items.filter(
          (item) => item.attention_required,
        ).length;
      factualWorkspace.summary.pending_review_total =
        factualWorkspace.review_queue.summary.pending_total;
      factualWorkspace.summary.attention_required_total =
        factualWorkspace.review_queue.summary.attention_required_total;
      return fulfillJson(route, {
        review_item: reviewItem,
        review_queue: factualWorkspace.review_queue,
      });
    }

    const topologySnapshotsMatch = path.match(
      /^\/api\/v2\/pools\/([^/]+)\/topology-snapshots\/$/,
    );
    if (method === "GET" && topologySnapshotsMatch) {
      if (counts) {
        counts.poolTopologySnapshots += 1;
      }
      return fulfillJson(route, {
        pool_id: topologySnapshotsMatch[1],
        count: 1,
        snapshots: [
          {
            effective_from: "2026-01-01",
            effective_to: null,
            nodes_count: 0,
            edges_count: 0,
          },
        ],
      });
    }

    return fulfillJson(
      route,
      { detail: `Unhandled mock for ${method} ${path}` },
      404,
    );
  });
}

export async function switchShellLocaleToEnglish(page: Page) {
  const localeSelect = page.getByTestId("shell-locale-select");
  await localeSelect.locator(".ant-select-selector").click();
  await page
    .locator(
      '.ant-select-dropdown:not(.ant-select-dropdown-hidden) [title="English"]',
    )
    .click();
}

export async function expectNoHorizontalOverflow(page: Page) {
  const overflowDetails = await page.evaluate(() => {
    const ignoredTags = new Set(["svg", "g", "path", "ellipse", "circle"]);
    const overflow = document.documentElement.scrollWidth - window.innerWidth;
    if (overflow <= 1) {
      return null;
    }

    const offenders = Array.from(
      document.querySelectorAll<HTMLElement>("body *"),
    )
      .map((element) => {
        if (ignoredTags.has(element.tagName.toLowerCase())) {
          return null;
        }
        if (
          element.closest('button[aria-label="Open Tanstack query devtools"]')
        ) {
          return null;
        }
        const rect = element.getBoundingClientRect();
        const overflowRight = rect.right - window.innerWidth;
        return {
          tag: element.tagName.toLowerCase(),
          testId: element.dataset.testid || "",
          text: (element.textContent || "")
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, 120),
          overflowRight,
          width: rect.width,
        };
      })
      .filter(Boolean)
      .filter((item) => item.overflowRight > 1)
      .sort((left, right) => right.overflowRight - left.overflowRight)
      .slice(0, 5);

    if (offenders.length === 0) {
      return null;
    }

    return {
      overflow,
      offenders,
    };
  });

  if (overflowDetails) {
    throw new Error(
      `Page has horizontal overflow: ${JSON.stringify(overflowDetails)}`,
    );
  }
}

export async function expectNoScopedHorizontalOverflow(
  locator: Locator,
  label: string,
) {
  const overflowDetails = await locator.evaluate((root) => {
    const ignoredTags = new Set(["svg", "g", "path", "ellipse", "circle"]);
    const isVisible = (element: HTMLElement) => {
      const style = window.getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden") {
        return false;
      }
      const rect = element.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    };

    const offenders = [
      root as HTMLElement,
      ...Array.from(root.querySelectorAll<HTMLElement>("*")),
    ]
      .filter((element) => !ignoredTags.has(element.tagName.toLowerCase()))
      .filter(isVisible)
      .map((element) => ({
        tag: element.tagName.toLowerCase(),
        testId: element.dataset.testid || "",
        text: (element.textContent || "")
          .replace(/\s+/g, " ")
          .trim()
          .slice(0, 120),
        overflow: element.scrollWidth - element.clientWidth,
        clientWidth: element.clientWidth,
      }))
      .filter((item) => item.clientWidth > 120 && item.overflow > 4)
      .filter((item) => item.text.length > 0 || item.testId.length > 0)
      .sort((left, right) => right.overflow - left.overflow)
      .slice(0, 5);

    return offenders.length > 0 ? offenders : null;
  });

  if (overflowDetails) {
    throw new Error(
      `${label} has horizontal overflow: ${JSON.stringify(overflowDetails)}`,
    );
  }
}

export async function fillTopologyTemplateCreateForm(page: Page) {
  await page
    .getByTestId("pool-topology-templates-create-code")
    .fill("new-template");
  await page
    .getByTestId("pool-topology-templates-create-name")
    .fill("New Template");
  await page
    .getByTestId("pool-topology-templates-create-description")
    .fill("Reusable topology authoring surface");
  await page
    .getByTestId("pool-topology-templates-create-node-slot-key-0")
    .fill("root");
  await page
    .getByTestId("pool-topology-templates-create-node-label-0")
    .fill("Root");
  await page.getByTestId("pool-topology-templates-create-node-root-0").click();
  await page.getByTestId("pool-topology-templates-create-add-node").click();
  await page
    .getByTestId("pool-topology-templates-create-node-slot-key-1")
    .fill("leaf");
  await page
    .getByTestId("pool-topology-templates-create-node-label-1")
    .fill("Leaf");
  await page.getByTestId("pool-topology-templates-create-add-edge").click();
  await page
    .getByTestId("pool-topology-templates-create-edge-parent-slot-key-0")
    .fill("root");
  await page
    .getByTestId("pool-topology-templates-create-edge-child-slot-key-0")
    .fill("leaf");
  await page
    .getByTestId("pool-topology-templates-create-edge-weight-0")
    .fill("1");
  await page
    .getByTestId("pool-topology-templates-create-edge-document-policy-key-0")
    .fill("sale");
}

export async function fillTopologyTemplateReviseForm(page: Page) {
  await page
    .getByTestId("pool-topology-templates-revise-node-label-0")
    .fill("Updated Root");
  await page
    .getByTestId("pool-topology-templates-revise-edge-document-policy-key-0")
    .fill("receipt");
}

export async function selectVisibleAntdOption(page: Page, label: string) {
  await page
    .locator(".ant-select-dropdown:visible .ant-select-item-option-content", {
      hasText: label,
    })
    .first()
    .click();
}

export async function expectVisibleWithinContainer(
  locator: ReturnType<Page["locator"]>,
  container: ReturnType<Page["locator"]>,
) {
  const [box, containerBox] = await Promise.all([
    locator.boundingBox(),
    container.boundingBox(),
  ]);

  if (!box || !containerBox) {
    throw new Error("Expected visible element and container bounding boxes.");
  }

  expect(box.x).toBeGreaterThanOrEqual(containerBox.x);
  expect(box.y).toBeGreaterThanOrEqual(containerBox.y);
  expect(box.x + box.width).toBeLessThanOrEqual(
    containerBox.x + containerBox.width,
  );
  expect(box.y + box.height).toBeLessThanOrEqual(
    containerBox.y + containerBox.height,
  );
}

export async function expectContrastAtLeast(
  locator: ReturnType<Page["locator"]>,
  minimumRatio: number,
) {
  const contrastRatio = await locator.evaluate((element) => {
    const parseColor = (value: string) => {
      const match = value.match(/rgba?\(([^)]+)\)/);
      if (!match) {
        return [0, 0, 0, 1] as const;
      }

      const [r = "0", g = "0", b = "0", a = "1"] = match[1]
        .split(",")
        .map((part) => part.trim());
      return [Number(r), Number(g), Number(b), Number(a)] as const;
    };

    const composite = (
      foreground: readonly [number, number, number, number],
      background: readonly [number, number, number, number],
    ) => {
      const alpha = foreground[3];
      const channel = (index: number) =>
        foreground[index] * alpha + background[index] * (1 - alpha);

      return [channel(0), channel(1), channel(2), 1] as const;
    };

    const luminance = (rgb: readonly [number, number, number, number]) => {
      const toLinear = (channel: number) => {
        const normalized = channel / 255;
        return normalized <= 0.04045
          ? normalized / 12.92
          : ((normalized + 0.055) / 1.055) ** 2.4;
      };

      const [r, g, b] = rgb;
      return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
    };

    const resolveBackground = (node: HTMLElement | null) => {
      let current = node;
      while (current) {
        const background = parseColor(
          window.getComputedStyle(current).backgroundColor,
        );
        if (background[3] > 0) {
          return background;
        }
        current = current.parentElement;
      }

      return [255, 255, 255, 1] as const;
    };

    const styles = window.getComputedStyle(element);
    const foreground = composite(
      parseColor(styles.color),
      resolveBackground(element.parentElement),
    );
    const background = resolveBackground(element as HTMLElement);
    const lighter = Math.max(luminance(foreground), luminance(background));
    const darker = Math.min(luminance(foreground), luminance(background));

    return (lighter + 0.05) / (darker + 0.05);
  });

  expect(contrastRatio).toBeGreaterThanOrEqual(minimumRatio);
}
