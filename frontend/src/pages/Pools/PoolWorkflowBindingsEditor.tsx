import { Alert, Button, Card, Col, Form, Input, Row, Select, Space, Tag, Typography } from 'antd'

import type { BindingProfileSummary } from '../../api/poolBindingProfiles'
import type {
  PoolWorkflowBinding,
  PoolWorkflowBindingResolvedProfile,
} from '../../api/intercompanyPools'
import { POOL_BINDING_PROFILES_ROUTE } from './routes'
import {
  createEmptyWorkflowBindingFormValue,
  getWorkflowBindingCardSummary,
  getWorkflowBindingCardTitle,
  type PoolWorkflowBindingFormValue,
} from './poolWorkflowBindingsForm'
import {
  buildTopologyCoverageContext,
  summarizeTopologySlotCoverage,
  type TopologyEdgeSelector,
} from './topologySlotCoverage'
import {
  type PoolWorkflowBindingPresentationValue,
  resolvePoolWorkflowBindingDecisionRefs,
  resolvePoolWorkflowBindingLifecycleWarning,
  resolvePoolWorkflowBindingProfileLabel,
  resolvePoolWorkflowBindingProfileStatus,
  resolvePoolWorkflowBindingWorkflow,
} from './poolWorkflowBindingPresentation'

const { Text } = Typography

type PoolWorkflowBindingsEditorProps = {
  availableBindingProfiles?: BindingProfileSummary[]
  bindingProfilesLoading?: boolean
  bindingProfilesLoadError?: string | null
  topologyEdgeSelectors?: TopologyEdgeSelector[]
  disabled?: boolean
}

const STATUS_OPTIONS = [
  { value: 'draft', label: 'draft' },
  { value: 'active', label: 'active' },
  { value: 'inactive', label: 'inactive' },
]

const toSyntheticBinding = (value: PoolWorkflowBindingFormValue | undefined): PoolWorkflowBindingPresentationValue | null => {
  if (!value) return null
  return {
    binding_id: String(value.binding_id ?? '').trim(),
    pool_id: String(value.pool_id ?? '').trim(),
    revision: Number(value.revision ?? 0),
    status: (value.status ?? 'draft'),
    binding_profile_id: String(value.binding_profile_id ?? '').trim() || undefined,
    binding_profile_revision_id: String(value.binding_profile_revision_id ?? '').trim() || undefined,
    binding_profile_revision_number: typeof value.binding_profile_revision_number === 'number'
      ? value.binding_profile_revision_number
      : Number(value.binding_profile_revision_number ?? 0) || undefined,
    resolved_profile: value.resolved_profile ?? undefined,
    profile_lifecycle_warning: value.profile_lifecycle_warning ?? null,
    selector: {
      direction: String(value.selector?.direction ?? '').trim() || undefined,
      mode: String(value.selector?.mode ?? '').trim() || undefined,
      tags: String(value.selector?.tags_csv ?? '')
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
    },
    effective_from: String(value.effective_from ?? '').trim(),
    effective_to: String(value.effective_to ?? '').trim() || null,
  }
}

type RevisionOption = {
  value: string
  label: string
  bindingProfileId?: string
  bindingProfileRevisionNumber?: number
  resolvedProfile?: PoolWorkflowBindingResolvedProfile | null
  profileLifecycleWarning?: PoolWorkflowBinding['profile_lifecycle_warning']
}

const buildRevisionOptions = (
  availableBindingProfiles: BindingProfileSummary[],
  binding: PoolWorkflowBindingPresentationValue | null,
): RevisionOption[] => {
  const catalogOptions = availableBindingProfiles.map((profile) => ({
    value: profile.latest_revision.binding_profile_revision_id,
    label: `${profile.code} · ${profile.name} · r${profile.latest_revision_number} · ${profile.status}`,
    bindingProfileId: profile.binding_profile_id,
    bindingProfileRevisionNumber: profile.latest_revision_number,
    resolvedProfile: {
      binding_profile_id: profile.binding_profile_id,
      code: profile.code,
      name: profile.name,
      status: profile.status,
      binding_profile_revision_id: profile.latest_revision.binding_profile_revision_id,
      binding_profile_revision_number: profile.latest_revision.revision_number,
      workflow: profile.latest_revision.workflow,
      decisions: profile.latest_revision.decisions,
      parameters: profile.latest_revision.parameters,
      role_mapping: profile.latest_revision.role_mapping as Record<string, string>,
    },
    profileLifecycleWarning: null,
  }))

  const currentRevisionId = String(binding?.binding_profile_revision_id ?? '').trim()
  const hasCurrentOption = currentRevisionId
    ? catalogOptions.some((option) => option.value === currentRevisionId)
    : false

  if (!currentRevisionId || hasCurrentOption) {
    return catalogOptions
  }

  return [
    {
      value: currentRevisionId,
      label: `${resolvePoolWorkflowBindingProfileLabel(binding)} · r${binding?.binding_profile_revision_number ?? '?'} · current`,
      bindingProfileId: binding?.binding_profile_id ?? binding?.resolved_profile?.binding_profile_id,
      bindingProfileRevisionNumber: binding?.binding_profile_revision_number ?? binding?.resolved_profile?.binding_profile_revision_number,
      resolvedProfile: binding?.resolved_profile,
      profileLifecycleWarning: binding?.profile_lifecycle_warning ?? null,
    },
    ...catalogOptions,
  ]
}

export function PoolWorkflowBindingsEditor({
  availableBindingProfiles = [],
  bindingProfilesLoading = false,
  bindingProfilesLoadError = null,
  topologyEdgeSelectors = [],
  disabled = false,
}: PoolWorkflowBindingsEditorProps) {
  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="Workflow bindings are managed as pool-scoped attachments"
        description="Attach an existing reusable binding profile revision, edit only pool-local scope, and use /pools/binding-profiles for workflow, slot, parameter, or role-mapping authoring."
      />
      {bindingProfilesLoadError ? (
        <Alert
          type="warning"
          showIcon
          message={bindingProfilesLoadError}
          description="Existing pinned attachments remain visible, but attaching a new profile revision requires the reusable profile catalog."
        />
      ) : null}
      <Form.List name="workflow_bindings">
        {(fields, { add, remove }) => (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {fields.length === 0 ? (
              <Text type="secondary">No workflow attachments configured for this pool yet.</Text>
            ) : null}
            {fields.map((field) => (
              <Form.Item key={field.key} noStyle shouldUpdate>
                {({ getFieldValue, setFieldValue }) => {
                  const binding = getFieldValue(['workflow_bindings', field.name]) as PoolWorkflowBindingFormValue | undefined
                  const syntheticBinding = toSyntheticBinding(binding)
                  const revisionOptions = buildRevisionOptions(availableBindingProfiles, syntheticBinding)
                  const workflow = resolvePoolWorkflowBindingWorkflow(syntheticBinding)
                  const decisions = resolvePoolWorkflowBindingDecisionRefs(syntheticBinding)
                  const slotRefs = decisions
                    .map((decision) => {
                      const slotKey = String(decision?.slot_key ?? decision?.decision_key ?? '').trim()
                      const decisionTableId = String(decision?.decision_table_id ?? '').trim()
                      const decisionKey = String(decision?.decision_key ?? '').trim()
                      const decisionRevision = String(decision?.decision_revision ?? '').trim()
                      if (!slotKey || !decisionTableId || !decisionRevision) {
                        return null
                      }
                      return {
                        slotKey,
                        refLabel: `${decisionTableId} (${decisionKey || 'decision'}) r${decisionRevision}`,
                      }
                    })
                    .filter((slotRef): slotRef is { slotKey: string; refLabel: string } => Boolean(slotRef))
                  const slotCoverageItems = slotRefs.map((slotRef, slotIndex) => ({
                    slotKey: slotRef.slotKey,
                    refLabel: slotRef.refLabel,
                    slotIndex,
                    matchedEdges: topologyEdgeSelectors.filter((edge) => edge.slotKey === slotRef.slotKey),
                  }))
                  const coverageSummary = summarizeTopologySlotCoverage(
                    topologyEdgeSelectors,
                    buildTopologyCoverageContext({
                      bindingLabel: getWorkflowBindingCardTitle(binding, field.name + 1),
                      detail: 'Coverage is evaluated against the resolved reusable profile revision pinned by this attachment.',
                      slotRefs,
                      source: 'selected',
                    }),
                  )
                  const unresolvedCoverageItems = coverageSummary.items.filter((item) => item.coverage.status !== 'resolved')
                  const lifecycleWarning = resolvePoolWorkflowBindingLifecycleWarning(syntheticBinding)

                  return (
                    <Card
                      size="small"
                      title={getWorkflowBindingCardTitle(binding, field.name + 1)}
                      extra={(
                        <Button
                          danger
                          size="small"
                          onClick={() => remove(field.name)}
                          disabled={disabled}
                          data-testid={`pool-catalog-workflow-binding-remove-${field.name}`}
                        >
                          Remove
                        </Button>
                      )}
                      data-testid={`pool-catalog-workflow-binding-card-${field.name}`}
                    >
                      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                        <Text
                          type="secondary"
                          data-testid={`pool-catalog-workflow-binding-summary-${field.name}`}
                        >
                          {getWorkflowBindingCardSummary(binding)}
                        </Text>

                        {lifecycleWarning ? (
                          <Alert
                            type="warning"
                            showIcon
                            message={lifecycleWarning.title}
                            description={lifecycleWarning.detail}
                          />
                        ) : null}

                        <Card
                          size="small"
                          title="Topology coverage"
                          data-testid={`pool-catalog-workflow-binding-coverage-${field.name}`}
                        >
                          {topologyEdgeSelectors.length === 0 ? (
                            <Text type="secondary">No topology edges in the selected snapshot yet.</Text>
                          ) : (
                            <Space direction="vertical" size="small" style={{ width: '100%' }}>
                              <Space size={[4, 4]} wrap>
                                <Tag>edges: {coverageSummary.totalEdges}</Tag>
                                <Tag color="success">resolved: {coverageSummary.counts.resolved}</Tag>
                                <Tag color="error">missing slot: {coverageSummary.counts.missing_slot}</Tag>
                                <Tag color="default">missing selector: {coverageSummary.counts.missing_selector}</Tag>
                                <Tag color="warning">ambiguous: {coverageSummary.counts.ambiguous_slot}</Tag>
                              </Space>
                              {slotCoverageItems.length > 0 ? (
                                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                  {slotCoverageItems.map((slotCoverage) => (
                                    <Space key={`${slotCoverage.slotKey}:${slotCoverage.slotIndex}`} size={8} wrap>
                                      <Tag
                                        color={slotCoverage.matchedEdges.length > 0 ? 'green' : 'default'}
                                        data-testid={`pool-catalog-workflow-binding-slot-coverage-${field.name}-${slotCoverage.slotIndex}`}
                                      >
                                        {slotCoverage.matchedEdges.length > 0
                                          ? `edges: ${slotCoverage.matchedEdges.length}`
                                          : 'unused by topology'}
                                      </Tag>
                                      <Text type="secondary">
                                        {slotCoverage.slotKey} · {slotCoverage.refLabel}
                                      </Text>
                                    </Space>
                                  ))}
                                </Space>
                              ) : null}
                              {unresolvedCoverageItems.length === 0 ? (
                                <Text type="secondary">All topology edges are covered by the pinned profile revision.</Text>
                              ) : (
                                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                  {unresolvedCoverageItems.map((item, itemIndex) => (
                                    <Text
                                      key={`${item.edgeId}:${item.coverage.status}`}
                                      type="secondary"
                                      data-testid={`pool-catalog-workflow-binding-coverage-item-${field.name}-${itemIndex}`}
                                    >
                                      {`${item.edgeLabel} · ${item.slotKey || 'slot not set'} · ${item.coverage.label}`}
                                    </Text>
                                  ))}
                                </Space>
                              )}
                            </Space>
                          )}
                        </Card>

                        <Row gutter={12}>
                          <Col span={12}>
                            <Form.Item name={[field.name, 'binding_id']} label="pool_workflow_binding_id">
                              <Input
                                allowClear
                                placeholder="optional existing attachment id"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-id-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item name={[field.name, 'status']} label="status">
                              <Select
                                options={STATUS_OPTIONS}
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-status-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Row gutter={12}>
                          <Col span={18}>
                            <Form.Item
                              name={[field.name, 'binding_profile_revision_id']}
                              label="binding_profile_revision_id"
                            >
                              <Select
                                showSearch
                                optionFilterProp="label"
                                loading={bindingProfilesLoading}
                                options={revisionOptions}
                                disabled={disabled}
                                placeholder="Select reusable profile revision"
                                data-testid={`pool-catalog-workflow-binding-profile-revision-${field.name}`}
                                onChange={(value) => {
                                  const option = revisionOptions.find((item) => item.value === value)
                                  setFieldValue(['workflow_bindings', field.name, 'binding_profile_id'], option?.bindingProfileId ?? '')
                                  setFieldValue(
                                    ['workflow_bindings', field.name, 'binding_profile_revision_number'],
                                    option?.bindingProfileRevisionNumber ?? null,
                                  )
                                  setFieldValue(['workflow_bindings', field.name, 'resolved_profile'], option?.resolvedProfile ?? null)
                                  setFieldValue(
                                    ['workflow_bindings', field.name, 'profile_lifecycle_warning'],
                                    option?.profileLifecycleWarning ?? null,
                                  )
                                }}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={6}>
                            <Button
                              block
                              href={POOL_BINDING_PROFILES_ROUTE}
                              style={{ marginTop: 30 }}
                              data-testid={`pool-catalog-workflow-binding-handoff-${field.name}`}
                            >
                              Edit in catalog
                            </Button>
                          </Col>
                        </Row>

                        <Card
                          size="small"
                          title="Resolved profile summary"
                          data-testid={`pool-catalog-workflow-binding-profile-summary-${field.name}`}
                        >
                          <Space direction="vertical" size={4} style={{ width: '100%' }}>
                            <Text data-testid={`pool-catalog-workflow-binding-profile-label-${field.name}`}>
                              {resolvePoolWorkflowBindingProfileLabel(syntheticBinding)}
                            </Text>
                            <Text data-testid={`pool-catalog-workflow-binding-profile-status-${field.name}`}>
                              {resolvePoolWorkflowBindingProfileStatus(syntheticBinding) ?? 'not resolved'}
                            </Text>
                            <Text data-testid={`pool-catalog-workflow-binding-workflow-name-${field.name}`}>
                              {workflow?.workflow_name ?? '-'}
                            </Text>
                            <Text data-testid={`pool-catalog-workflow-binding-workflow-key-${field.name}`}>
                              {workflow?.workflow_definition_key ?? '-'}
                            </Text>
                            <Text data-testid={`pool-catalog-workflow-binding-workflow-revision-id-${field.name}`}>
                              {workflow?.workflow_revision_id ?? '-'}
                            </Text>
                            <Text data-testid={`pool-catalog-workflow-binding-workflow-revision-${field.name}`}>
                              {workflow ? String(workflow.workflow_revision) : '-'}
                            </Text>
                          </Space>
                        </Card>

                        <Row gutter={12}>
                          <Col span={12}>
                            <Form.Item name={[field.name, 'effective_from']} label="effective_from">
                              <Input
                                type="date"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-effective-from-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item name={[field.name, 'effective_to']} label="effective_to">
                              <Input
                                type="date"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-effective-to-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Row gutter={12}>
                          <Col span={8}>
                            <Form.Item name={[field.name, 'selector', 'direction']} label="selector.direction">
                              <Input
                                allowClear
                                placeholder="top_down"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-selector-direction-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item name={[field.name, 'selector', 'mode']} label="selector.mode">
                              <Input
                                allowClear
                                placeholder="safe"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-selector-mode-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item name={[field.name, 'selector', 'tags_csv']} label="selector.tags">
                              <Input
                                allowClear
                                placeholder="baseline, monthly"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-selector-tags-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                        </Row>
                      </Space>
                    </Card>
                  )
                }}
              </Form.Item>
            ))}
            <Button
              type="dashed"
              onClick={() => add(createEmptyWorkflowBindingFormValue())}
              disabled={disabled || bindingProfilesLoading || availableBindingProfiles.length === 0}
              data-testid="pool-catalog-workflow-binding-add"
            >
              Attach profile revision
            </Button>
          </Space>
        )}
      </Form.List>
    </Space>
  )
}
