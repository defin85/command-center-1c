import { expect, test, type Page, type Route } from '@playwright/test'

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
    settlement_total: 2,
    checkpoint_total: 1,
  },
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

const OPERATIONS = [WORKFLOW_OPERATION, MANUAL_OPERATION]

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
  clusterLists: number
  databaseLists: number
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
    clusterLists: 0,
    databaseLists: 0,
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
    counts?: RequestCounts
  },
) {
  const counts = options?.counts
  const isStaff = options?.isStaff ?? false
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

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/bootstrap/') {
      if (counts) {
        counts.bootstrap += 1
      }
      return fulfillJson(route, {
        me: currentUser,
        tenant_context: tenantContext,
        access: {
          user: { id: currentUser.id, username: currentUser.username },
          clusters: [],
          databases: [],
          operation_templates: [],
        },
        capabilities: {
          can_manage_rbac: isStaff,
          can_manage_driver_catalogs: false,
        },
      })
    }

    if (method === 'GET' && path === '/api/v2/system/me/') {
      if (counts) {
        counts.meReads += 1
      }
      return fulfillJson(route, currentUser)
    }

    if (method === 'GET' && path === '/api/v2/tenants/list-my-tenants/') {
      if (counts) {
        counts.myTenantsReads += 1
      }
      return fulfillJson(route, tenantContext)
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
        clusters: [
          {
            id: 'cluster-1',
            name: 'Main Cluster',
            status: 'connected',
          },
        ],
        count: 1,
        total: 1,
      })
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
        ],
        count: 1,
        total: 1,
      })
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

async function expectNoHorizontalOverflow(page: Page) {
  const hasOverflow = await page.evaluate(() => (
    document.documentElement.scrollWidth - window.innerWidth > 1
  ))
  expect(hasOverflow).toBe(false)
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
  await expect(reviseDrawer.getByTestId('pool-topology-templates-revise-node-label-0')).toBeVisible()
  await expect(reviseDrawer.getByRole('button', { name: 'Publish revision' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
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

test('UI platform: /workflows keeps mobile catalog readable and opens detail in a drawer', async ({ page }) => {
  await setupAuth(page)
  await setupPersistentDatabaseStream(page)
  await setupUiPlatformMocks(page, { isStaff: true })
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/workflows', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Workflow Scheme Library', level: 2 })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.locator('tbody tr').filter({ hasText: WORKFLOW.name }).first().click()

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('workflow-list-selected-id')).toHaveText(WORKFLOW.id)
  await expect(detailDrawer.getByTestId('workflow-list-detail-open')).toBeVisible()
  await expectNoHorizontalOverflow(page)
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

  await page.locator('tbody tr').filter({ hasText: WORKFLOW.name }).first().click()

  const detailDrawer = page.getByRole('dialog')
  await expect(detailDrawer).toBeVisible()
  await expect(detailDrawer.getByTestId('workflow-executions-selected-id')).toHaveText(WORKFLOW_EXECUTION_DETAIL.id)
  await expect(detailDrawer.getByTestId('workflow-executions-detail-open')).toBeVisible()
  await expectNoHorizontalOverflow(page)
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
  await expect(page.getByTestId('database-workspace-selected-id')).toHaveText(DATABASE_ID, {
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByTestId('database-metadata-management-drawer')).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`\\/databases\\?cluster=cluster-1&database=${DATABASE_ID}&context=metadata$`))
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
  await expect(page.getByText('Quarter summary')).toBeVisible()
  await expect(page.getByText('Manual review queue')).toBeVisible()
  await expect(page.getByText('Read backlog has 2 overdue checkpoint(s) on the default sync lane.')).toBeVisible()
  await expect(page.getByText('focus=settlement')).toBeVisible()
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
  await expect(detailDrawer.getByText('Manual review queue')).toBeVisible()
  await expect(detailDrawer.getByText('review focus')).toBeVisible()
  await expect(detailDrawer.getByRole('button', { name: 'Attribute review item unattributed-pool-main' })).toBeVisible()
  await detailDrawer.getByRole('button', { name: 'Attribute review item unattributed-pool-main' }).click()
  await expect(page.getByText('Choose or confirm attribution targets')).toBeVisible()
  await expectNoHorizontalOverflow(page)
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
  await expect(page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`)).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  })
  await expect(page.getByRole('button', { name: 'Timeline' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open workflow diagnostics' })).toBeVisible()
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
  await expect(detailDrawer.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`)).toBeVisible()
  await expect(detailDrawer.getByRole('button', { name: 'Timeline' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
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

  await expect(page).toHaveURL(/\/pools\/topology-templates\?compose=create&return_pool_id=pool-1&return_tab=topology&return_date=2026-01-01$/)
  await expect(page.getByRole('heading', { name: 'Topology Templates', level: 2 })).toBeVisible()
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
  await expect(deactivatedStatusBadge).toContainText('deactivated')

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
