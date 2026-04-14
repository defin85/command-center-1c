import { Alert, Button, Card, Col, Form, Grid, Input, Row, Select, Space, Tag, Typography } from 'antd'

import type { BindingProfileDetail, BindingProfileSummary } from '../../api/poolBindingProfiles'
import type {
  PoolWorkflowBinding,
  PoolWorkflowBindingResolvedProfile,
} from '../../api/intercompanyPools'
import { RouteButton } from '../../components/platform'
import { usePoolsTranslation } from '../../i18n'
import { POOL_EXECUTION_PACKS_ROUTE } from './routes'
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
import { describeExecutionPackTopologyCompatibility } from './executionPackTopologyCompatibility'

const { Text } = Typography
const { useBreakpoint } = Grid

type PoolWorkflowBindingsEditorProps = {
  availableBindingProfiles?: BindingProfileSummary[]
  availableBindingProfileDetails?: Record<string, BindingProfileDetail>
  bindingProfilesLoading?: boolean
  bindingProfileDetailsLoading?: boolean
  bindingProfilesLoadError?: string | null
  onBindingProfileRevisionSelectOpen?: () => void
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
  availableBindingProfileDetails: Record<string, BindingProfileDetail>,
  binding: PoolWorkflowBindingPresentationValue | null,
): RevisionOption[] => {
  const revisionIds = new Set<string>()
  const catalogOptions = availableBindingProfiles.flatMap((profile) => {
    const detail = availableBindingProfileDetails[profile.binding_profile_id]
    const detailRevisions = detail?.revisions?.length
      ? detail.revisions.filter(
        (revision) => revision.binding_profile_revision_id !== profile.latest_revision.binding_profile_revision_id,
      )
      : []
    const revisions = [profile.latest_revision, ...detailRevisions]
      .sort((left, right) => right.revision_number - left.revision_number)
    const profileCode = profile.code
    const profileName = profile.name
    const profileStatus = profile.status

    return revisions
      .filter((revision) => {
        const revisionId = String(revision.binding_profile_revision_id)
        if (!revisionId || revisionIds.has(revisionId)) {
          return false
        }
        revisionIds.add(revisionId)
        return true
      })
      .map((revision) => ({
        value: revision.binding_profile_revision_id,
        label: `${profileCode} · ${profileName} · r${revision.revision_number} · ${profileStatus}`,
        bindingProfileId: profile.binding_profile_id,
        bindingProfileRevisionNumber: revision.revision_number,
        resolvedProfile: {
          binding_profile_id: profile.binding_profile_id,
          code: profileCode,
          name: profileName,
          status: profileStatus,
          binding_profile_revision_id: revision.binding_profile_revision_id,
          binding_profile_revision_number: revision.revision_number,
          workflow: revision.workflow,
          decisions: revision.decisions,
          parameters: revision.parameters,
          role_mapping: revision.role_mapping as Record<string, string>,
          topology_template_compatibility: revision.topology_template_compatibility,
        },
        profileLifecycleWarning: null,
      }))
  })

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
  availableBindingProfileDetails = {},
  bindingProfilesLoading = false,
  bindingProfileDetailsLoading = false,
  bindingProfilesLoadError = null,
  onBindingProfileRevisionSelectOpen,
  topologyEdgeSelectors = [],
  disabled = false,
}: PoolWorkflowBindingsEditorProps) {
  const { t } = usePoolsTranslation()
  const screens = useBreakpoint()
  const isNarrow = !screens.md
  const wrappingTextStyle = {
    display: 'block',
    overflowWrap: 'anywhere',
    whiteSpace: 'normal',
  } as const

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%', minWidth: 0, overflowX: 'hidden' }}>
      <Alert
        type="info"
        showIcon
        message="Workflow bindings are managed as pool-scoped attachments"
        description="Attach an existing reusable execution-pack revision, edit only pool-local scope, and use /pools/execution-packs for workflow, slot, parameter, or role-mapping authoring."
      />
      {bindingProfilesLoadError ? (
        <Alert
          type="warning"
          showIcon
          message={bindingProfilesLoadError}
          description="Existing pinned attachments remain visible, but attaching a new execution-pack revision requires the reusable execution-pack catalog."
        />
      ) : null}
      <Form.List name="workflow_bindings">
        {(fields, { add, remove }) => (
          <Space direction="vertical" size="middle" style={{ width: '100%', minWidth: 0 }}>
            {fields.length === 0 ? (
              <Text type="secondary">No workflow attachments configured for this pool yet.</Text>
            ) : null}
            {fields.map((field) => (
              <Form.Item key={field.key} noStyle shouldUpdate>
                {({ getFieldValue, setFieldValue }) => {
                  const binding = getFieldValue(['workflow_bindings', field.name]) as PoolWorkflowBindingFormValue | undefined
                  const syntheticBinding = toSyntheticBinding(binding)
                  const revisionOptions = buildRevisionOptions(
                    availableBindingProfiles,
                    availableBindingProfileDetails,
                    syntheticBinding,
                  )
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
                      detail: 'Coverage is evaluated against the resolved reusable execution-pack revision pinned by this attachment.',
                      slotRefs,
                      source: 'selected',
                    }),
                  )
                  const unresolvedCoverageItems = coverageSummary.items.filter((item) => item.coverage.status !== 'resolved')
                  const lifecycleWarning = resolvePoolWorkflowBindingLifecycleWarning(syntheticBinding)
                  const topologyCompatibility = describeExecutionPackTopologyCompatibility(
                    syntheticBinding?.resolved_profile?.topology_template_compatibility,
                    {
                      notAvailableStatus: t('executionPacks.compatibility.notAvailableStatus'),
                      notAvailableMessage: t('executionPacks.compatibility.notAvailableMessage'),
                      compatibleStatus: t('executionPacks.compatibility.compatibleStatus'),
                      compatibleMessage: t('executionPacks.compatibility.compatibleMessage'),
                      incompatibleStatus: t('executionPacks.compatibility.incompatibleStatus'),
                      incompatibleMessage: t('executionPacks.compatibility.incompatibleMessage'),
                    },
                  )
                  const showTopologyCompatibility = Boolean(
                    syntheticBinding?.binding_profile_revision_id || syntheticBinding?.resolved_profile,
                  )

                  return (
                    <Card
                      size="small"
                      title={(
                        <Space direction="vertical" size={4} style={{ width: '100%', minWidth: 0 }}>
                          <Text strong style={wrappingTextStyle}>
                            {getWorkflowBindingCardTitle(binding, field.name + 1)}
                          </Text>
                          <Text
                            type="secondary"
                            data-testid={`pool-catalog-workflow-binding-summary-${field.name}`}
                            style={wrappingTextStyle}
                          >
                            {getWorkflowBindingCardSummary(binding)}
                          </Text>
                          {isNarrow ? (
                            <Button
                              danger
                              size="small"
                              onClick={() => remove(field.name)}
                              disabled={disabled}
                              data-testid={`pool-catalog-workflow-binding-remove-${field.name}`}
                            >
                              Remove
                            </Button>
                          ) : null}
                        </Space>
                      )}
                      extra={isNarrow ? null : (
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
                      <Space direction="vertical" size="middle" style={{ width: '100%', minWidth: 0 }}>
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
                                <Text type="secondary">All topology edges are covered by the pinned execution-pack revision.</Text>
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

                        <Row gutter={[12, 12]}>
                          <Col xs={24} md={12}>
                            <Form.Item name={[field.name, 'binding_id']} label="pool_workflow_binding_id">
                              <Input
                                allowClear
                                placeholder="optional existing attachment id"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-id-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col xs={24} md={12}>
                            <Form.Item name={[field.name, 'status']} label="status">
                              <Select
                                options={STATUS_OPTIONS}
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-status-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Row gutter={[12, 12]}>
                          <Col xs={24} md={18}>
                            <Form.Item
                              name={[field.name, 'binding_profile_revision_id']}
                              label="binding_profile_revision_id"
                            >
                              <Select
                                showSearch
                                optionFilterProp="label"
                                loading={bindingProfilesLoading || bindingProfileDetailsLoading}
                                options={revisionOptions}
                                disabled={disabled}
                                placeholder="Select reusable execution-pack revision"
                                data-testid={`pool-catalog-workflow-binding-profile-revision-${field.name}`}
                                onOpenChange={(open) => {
                                  if (open) {
                                    onBindingProfileRevisionSelectOpen?.()
                                  }
                                }}
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
                          <Col xs={24} md={6}>
                            <RouteButton
                              block
                              to={POOL_EXECUTION_PACKS_ROUTE}
                              style={{ marginTop: isNarrow ? 0 : 30, whiteSpace: 'normal', height: 'auto' }}
                              data-testid={`pool-catalog-workflow-binding-handoff-${field.name}`}
                            >
                              Edit in execution-pack catalog
                            </RouteButton>
                          </Col>
                        </Row>

                        <Card
                          size="small"
                          title="Resolved profile summary"
                          data-testid={`pool-catalog-workflow-binding-profile-summary-${field.name}`}
                        >
                          <Space direction="vertical" size={4} style={{ width: '100%' }}>
                            <Text
                              data-testid={`pool-catalog-workflow-binding-profile-label-${field.name}`}
                              style={wrappingTextStyle}
                            >
                              {resolvePoolWorkflowBindingProfileLabel(syntheticBinding)}
                            </Text>
                            <Text
                              data-testid={`pool-catalog-workflow-binding-profile-status-${field.name}`}
                              style={wrappingTextStyle}
                            >
                              {resolvePoolWorkflowBindingProfileStatus(syntheticBinding) ?? 'not resolved'}
                            </Text>
                            <Text
                              data-testid={`pool-catalog-workflow-binding-workflow-name-${field.name}`}
                              style={wrappingTextStyle}
                            >
                              {workflow?.workflow_name ?? '-'}
                            </Text>
                            <Text
                              data-testid={`pool-catalog-workflow-binding-workflow-key-${field.name}`}
                              style={wrappingTextStyle}
                            >
                              {workflow?.workflow_definition_key ?? '-'}
                            </Text>
                            <Text
                              data-testid={`pool-catalog-workflow-binding-workflow-revision-id-${field.name}`}
                              style={wrappingTextStyle}
                            >
                              {workflow?.workflow_revision_id ?? '-'}
                            </Text>
                            <Text
                              data-testid={`pool-catalog-workflow-binding-workflow-revision-${field.name}`}
                              style={wrappingTextStyle}
                            >
                              {workflow ? String(workflow.workflow_revision) : '-'}
                            </Text>
                          </Space>
                        </Card>

                        {showTopologyCompatibility ? (
                          <Alert
                            type={topologyCompatibility.alertType}
                            showIcon
                            message={topologyCompatibility.message}
                            description={(
                              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                <Text data-testid={`pool-catalog-workflow-binding-topology-status-${field.name}`}>
                                  Status: {topologyCompatibility.statusText}
                                </Text>
                                <Text
                                  type="secondary"
                                  data-testid={`pool-catalog-workflow-binding-topology-covered-slots-${field.name}`}
                                >
                                  Covered slots: {topologyCompatibility.coveredSlotsText}
                                </Text>
                                {topologyCompatibility.diagnostics.map((diagnostic, diagnosticIndex) => (
                                  <Text
                                    key={`${field.key}:topology:${diagnosticIndex}`}
                                    type="secondary"
                                    data-testid={`pool-catalog-workflow-binding-topology-diagnostic-${field.name}-${diagnosticIndex}`}
                                  >
                                    {diagnostic}
                                  </Text>
                                ))}
                              </Space>
                            )}
                          />
                        ) : null}

                        <Row gutter={[12, 12]}>
                          <Col xs={24} md={12}>
                            <Form.Item name={[field.name, 'effective_from']} label="effective_from">
                              <Input
                                type="date"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-effective-from-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col xs={24} md={12}>
                            <Form.Item name={[field.name, 'effective_to']} label="effective_to">
                              <Input
                                type="date"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-effective-to-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Row gutter={[12, 12]}>
                          <Col xs={24} md={8}>
                            <Form.Item name={[field.name, 'selector', 'direction']} label="selector.direction">
                              <Input
                                allowClear
                                placeholder="top_down"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-selector-direction-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col xs={24} md={8}>
                            <Form.Item name={[field.name, 'selector', 'mode']} label="selector.mode">
                              <Input
                                allowClear
                                placeholder="safe"
                                disabled={disabled}
                                data-testid={`pool-catalog-workflow-binding-selector-mode-${field.name}`}
                              />
                            </Form.Item>
                          </Col>
                          <Col xs={24} md={8}>
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
              disabled={
                disabled
                || bindingProfilesLoading
                || bindingProfileDetailsLoading
                || availableBindingProfiles.length === 0
              }
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
