import { Alert, App, Button, Grid, Radio, Space, Spin, Typography } from 'antd'
import { LinkOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons'
import { useEffect, useState, type ReactNode } from 'react'

import type { DatabaseMetadataManagementConfigurationProfile } from '../../../api/generated/model/databaseMetadataManagementConfigurationProfile'
import type { DatabaseMetadataManagementResponse } from '../../../api/generated/model/databaseMetadataManagementResponse'
import type { DatabaseMetadataManagementSnapshot } from '../../../api/generated/model/databaseMetadataManagementSnapshot'
import {
  useDatabaseMetadataManagement,
  useRefreshDatabaseMetadataSnapshot,
  useReverifyDatabaseConfigurationProfile,
  useUpdateDatabaseMasterDataSyncEligibility,
} from '../../../api/queries/databases'
import { DrawerFormShell } from '../../../components/platform'
import { useDatabasesTranslation, useLocaleFormatters } from '../../../i18n'
import { trackUiAction } from '../../../observability/uiActionJournal'

type AlertTone = 'success' | 'info' | 'warning' | 'error'

export interface DatabaseMetadataManagementDrawerProps {
  open: boolean
  databaseId?: string
  databaseName?: string
  mutatingDisabled?: boolean
  eligibilityMutatingDisabled?: boolean
  onClose: () => void
  onOperationQueued?: (operationId: string) => void
  onOpenIbcmdProfile?: () => void
}

type StatusDescriptor = {
  tone: AlertTone
  label: string
  message: string
  description?: ReactNode
}

type ConfigurationProfileState = DatabaseMetadataManagementConfigurationProfile & {
  reverify_available?: boolean
  reverify_blocker_code?: string
  reverify_blocker_message?: string
  reverify_blocking_action?: string
  observed_metadata_fetched_at?: string | null
}

type MetadataSummaryItem = {
  key: string
  label: string
  value: string
}

type ClusterAllEligibilityState = 'eligible' | 'excluded' | 'unconfigured'

type DatabaseMetadataManagementPoolMasterDataSyncState = {
  cluster_all_eligibility?: {
    state?: ClusterAllEligibilityState | null
  } | null
  readiness?: {
    cluster_attached?: boolean
    odata_configured?: boolean
    credentials_configured?: boolean
    ibcmd_profile_configured?: boolean
    service_mapping_status?: string
    service_mapping_count?: number
    runtime_enabled?: boolean
    inbound_enabled?: boolean
    outbound_enabled?: boolean
    default_policy?: string
    health_status?: string
  } | null
}

type MetadataManagementPayload = DatabaseMetadataManagementResponse & {
  pool_master_data_sync?: DatabaseMetadataManagementPoolMasterDataSyncState | null
}

const { useBreakpoint } = Grid
const DESKTOP_BREAKPOINT_PX = 992

type DatabasesT = ReturnType<typeof useDatabasesTranslation>['t']
type LocaleFormatters = ReturnType<typeof useLocaleFormatters>

const formatDateTime = (formatters: LocaleFormatters, t: DatabasesT, value?: string | null): string => (
  formatters.dateTime(value, { fallback: t(($) => $.shared.notAvailable) })
)

const formatValue = (t: DatabasesT, value?: string | null): string => (
  typeof value === 'string' && value.trim() ? value : t(($) => $.shared.notAvailable)
)

const formatBoolean = (t: DatabasesT, value?: boolean): string => (
  value ? t(($) => $.shared.yes) : t(($) => $.shared.no)
)

const buildProfileStatusDescriptor = (
  profile: ConfigurationProfileState,
  t: DatabasesT,
): StatusDescriptor => {
  const reverifyBlocked = profile.reverify_available === false
  const blockerMessage = typeof profile.reverify_blocker_message === 'string'
    ? profile.reverify_blocker_message.trim()
    : ''
  switch (profile.status) {
    case 'verified':
      return {
        tone: 'success',
        label: t(($) => $.metadata.profile.verifiedLabel),
        message: t(($) => $.metadata.profile.verifiedMessage),
        description: t(($) => $.metadata.profile.verifiedDescription),
      }
    case 'verification_pending':
      return {
        tone: 'info',
        label: t(($) => $.metadata.profile.pendingLabel),
        message: t(($) => $.metadata.profile.pendingMessage),
        description: t(($) => $.metadata.profile.pendingDescription),
      }
    case 'migrated_legacy':
      return {
        tone: 'warning',
        label: reverifyBlocked ? t(($) => $.metadata.profile.blockedLabel) : t(($) => $.metadata.profile.legacyLabel),
        message: reverifyBlocked
          ? t(($) => $.metadata.profile.legacyBlockedMessage)
          : t(($) => $.metadata.profile.legacyMessage),
        description: blockerMessage || t(($) => $.metadata.profile.legacyDescription),
      }
    case 'reverify_required':
      return {
        tone: 'warning',
        label: reverifyBlocked ? t(($) => $.metadata.profile.blockedLabel) : t(($) => $.metadata.profile.reverifyRequiredLabel),
        message: reverifyBlocked
          ? t(($) => $.metadata.profile.reverifyBlockedMessage)
          : t(($) => $.metadata.profile.reverifyMessage),
        description: blockerMessage || t(($) => $.metadata.profile.reverifyDescription),
      }
    case 'verification_failed':
      return {
        tone: reverifyBlocked ? 'warning' : 'error',
        label: reverifyBlocked ? t(($) => $.metadata.profile.blockedLabel) : t(($) => $.metadata.profile.failedLabel),
        message: reverifyBlocked
          ? t(($) => $.metadata.profile.failedBlockedMessage)
          : t(($) => $.metadata.profile.failedMessage),
        description: blockerMessage || t(($) => $.metadata.profile.failedDescription),
      }
    default:
      return {
        tone: 'warning',
        label: reverifyBlocked ? t(($) => $.metadata.profile.blockedLabel) : t(($) => $.metadata.profile.missingLabel),
        message: t(($) => $.metadata.profile.missingMessage),
        description: blockerMessage || t(($) => $.metadata.profile.missingDescription),
      }
  }
}

const buildSnapshotStatusDescriptor = (
  snapshot: DatabaseMetadataManagementSnapshot,
  t: DatabasesT,
  formatters: LocaleFormatters,
  profile?: ConfigurationProfileState | null,
): StatusDescriptor => {
  if (snapshot.status !== 'available') {
    if (snapshot.missing_reason === 'configuration_profile_unavailable') {
      const blockerMessage = typeof profile?.reverify_blocker_message === 'string'
        ? profile.reverify_blocker_message.trim()
        : ''
      return {
        tone: 'warning',
        label: t(($) => $.metadata.snapshot.blockedLabel),
        message: t(($) => $.metadata.snapshot.blockedMessage),
        description: blockerMessage || t(($) => $.metadata.snapshot.blockedDescription),
      }
    }
    return {
      tone: 'warning',
      label: t(($) => $.metadata.snapshot.missingLabel),
      message: t(($) => $.metadata.snapshot.missingMessage),
      description: t(($) => $.metadata.snapshot.missingDescription),
    }
  }

  if (snapshot.publication_drift) {
    const lastObservedRefresh = formatDateTime(formatters, t, profile?.observed_metadata_fetched_at)
    const canonicalSnapshotFetchedAt = formatDateTime(formatters, t, snapshot.fetched_at)
    return {
      tone: 'warning',
      label: t(($) => $.metadata.snapshot.driftLabel),
      message: t(($) => $.metadata.snapshot.driftMessage),
      description: (
        <Space direction="vertical" size={4}>
          <span>{t(($) => $.metadata.snapshot.lastObservedRefresh, { value: lastObservedRefresh })}</span>
          <span>{t(($) => $.metadata.snapshot.canonicalFetchedAt, { value: canonicalSnapshotFetchedAt })}</span>
          <span>
            {snapshot.is_shared_snapshot
              ? t(($) => $.metadata.snapshot.driftSharedExplanation)
              : t(($) => $.metadata.snapshot.driftDatabaseExplanation)}
          </span>
        </Space>
      ),
    }
  }

  return {
    tone: 'success',
    label: snapshot.is_shared_snapshot
      ? t(($) => $.metadata.snapshot.sharedLabel)
      : t(($) => $.metadata.snapshot.databaseScopeLabel),
    message: t(($) => $.metadata.snapshot.availableMessage),
    description: snapshot.is_shared_snapshot
      ? t(($) => $.metadata.snapshot.availableSharedDescription)
      : t(($) => $.metadata.snapshot.availableDatabaseDescription),
  }
}

const buildEligibilityStatusDescriptor = (
  state: ClusterAllEligibilityState,
  t: DatabasesT,
): StatusDescriptor => {
  switch (state) {
    case 'eligible':
      return {
        tone: 'success',
        label: t(($) => $.metadata.eligibility.eligibleLabel),
        message: t(($) => $.metadata.eligibility.eligibleMessage),
        description: t(($) => $.metadata.eligibility.eligibleDescription),
      }
    case 'excluded':
      return {
        tone: 'info',
        label: t(($) => $.metadata.eligibility.excludedLabel),
        message: t(($) => $.metadata.eligibility.excludedMessage),
        description: t(($) => $.metadata.eligibility.excludedDescription),
      }
    default:
      return {
        tone: 'warning',
        label: t(($) => $.metadata.eligibility.unconfiguredLabel),
        message: t(($) => $.metadata.eligibility.unconfiguredMessage),
        description: t(($) => $.metadata.eligibility.unconfiguredDescription),
      }
  }
}

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error && error.message) return error.message
  return 'unknown error'
}

const renderStatusTag = (descriptor: StatusDescriptor) => {
  const colorMap: Record<AlertTone, { background: string; border: string; text: string }> = {
    success: { background: '#ecfdf3', border: '#a6f4c5', text: '#166534' },
    info: { background: '#eff6ff', border: '#bfdbfe', text: '#1d4ed8' },
    warning: { background: '#fff7ed', border: '#fed7aa', text: '#c2410c' },
    error: { background: '#fef2f2', border: '#fecaca', text: '#b91c1c' },
  }
  const palette = colorMap[descriptor.tone]
  return (
    <span
      style={{
        background: palette.background,
        border: `1px solid ${palette.border}`,
        borderRadius: 999,
        color: palette.text,
        display: 'inline-flex',
        fontSize: 12,
        fontWeight: 600,
        lineHeight: 1.4,
        padding: '2px 10px',
      }}
    >
      {descriptor.label}
    </span>
  )
}

const renderMetadataSummarySection = (
  title: string,
  items: MetadataSummaryItem[],
) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
    <Typography.Title level={5} style={{ margin: 0 }}>
      {title}
    </Typography.Title>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {items.map((item) => (
        <div
          key={item.key}
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 8,
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            padding: '12px 14px',
          }}
          >
            <Typography.Text type="secondary">{item.label}</Typography.Text>
            <Typography.Text style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}>{item.value}</Typography.Text>
          </div>
        ))}
      </div>
  </div>
)

export const DatabaseMetadataManagementDrawer = ({
  open,
  databaseId,
  databaseName,
  mutatingDisabled = false,
  eligibilityMutatingDisabled = mutatingDisabled,
  onClose,
  onOperationQueued,
  onOpenIbcmdProfile,
}: DatabaseMetadataManagementDrawerProps) => {
  const screens = useBreakpoint()
  const { t } = useDatabasesTranslation()
  const formatters = useLocaleFormatters()
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.lg
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < DESKTOP_BREAKPOINT_PX
        : false
    )
  const { message } = App.useApp()
  const metadataQuery = useDatabaseMetadataManagement({
    id: databaseId ?? '',
    enabled: open && Boolean(databaseId),
  })
  const reverifyMutation = useReverifyDatabaseConfigurationProfile()
  const refreshMutation = useRefreshDatabaseMetadataSnapshot()
  const updateEligibilityMutation = useUpdateDatabaseMasterDataSyncEligibility()

  const payload = (metadataQuery.data ?? null) as MetadataManagementPayload | null
  const profile = (payload?.configuration_profile ?? null) as ConfigurationProfileState | null
  const snapshot = payload?.metadata_snapshot ?? null
  const poolMasterDataSync = payload?.pool_master_data_sync ?? null
  const eligibilityState = (
    poolMasterDataSync?.cluster_all_eligibility?.state ?? 'unconfigured'
  ) as ClusterAllEligibilityState
  const readiness = poolMasterDataSync?.readiness ?? null
  const profileDescriptor = profile ? buildProfileStatusDescriptor(profile, t) : null
  const snapshotDescriptor = snapshot ? buildSnapshotStatusDescriptor(snapshot, t, formatters, profile) : null
  const eligibilityDescriptor = buildEligibilityStatusDescriptor(eligibilityState, t)
  const queuedOperationId =
    reverifyMutation.data?.operation_id || profile?.verification_operation_id || ''
  const reverifyBlockedByIbcmdProfile = (
    profile?.reverify_available === false
    && profile?.reverify_blocking_action === 'configure_ibcmd_connection_profile'
  )
  const refreshBlockedByMissingProfile = snapshot?.missing_reason === 'configuration_profile_unavailable'
  const [eligibilityDraft, setEligibilityDraft] = useState<ClusterAllEligibilityState>('unconfigured')
  const trackMetadataAction = <T,>(actionName: string, handler: () => T) => (
    trackUiAction({
      actionKind: 'operator.action',
      actionName,
      context: {
        database_id: databaseId,
        operation_id: queuedOperationId || undefined,
      },
    }, handler)
  )

  useEffect(() => {
    if (!open) {
      return
    }
    setEligibilityDraft(eligibilityState)
  }, [eligibilityState, open])

  const eligibilityDirty = eligibilityDraft !== eligibilityState

  const handleReverify = () => {
    if (!databaseId || mutatingDisabled) return
    reverifyMutation.mutate(
      { database_id: databaseId },
      {
        onSuccess: (response) => {
          message.success(response.message || t(($) => $.metadata.messages.reverifyQueued))
        },
        onError: (error: Error) => {
          message.error(t(($) => $.metadata.messages.reverifyFailed, { error: error.message }))
        },
      }
    )
  }

  const handleRefresh = () => {
    if (!databaseId || mutatingDisabled) return
    refreshMutation.mutate(
      { database_id: databaseId },
      {
        onSuccess: () => {
          message.success(t(($) => $.metadata.messages.snapshotUpdated))
        },
        onError: (error: Error) => {
          message.error(t(($) => $.metadata.messages.snapshotUpdateFailed, { error: error.message }))
        },
      }
    )
  }

  const handleSaveEligibility = () => {
    if (!databaseId || eligibilityMutatingDisabled || !eligibilityDirty) return
    updateEligibilityMutation.mutate(
      {
        database_id: databaseId,
        cluster_all_eligibility_state: eligibilityDraft,
      },
      {
        onSuccess: (response) => {
          message.success(response.message || t(($) => $.metadata.messages.eligibilityUpdated))
        },
        onError: (error: Error) => {
          message.error(t(($) => $.metadata.messages.eligibilityUpdateFailed, { error: error.message }))
        },
      },
    )
  }

  return (
    <DrawerFormShell
      open={open}
      onClose={onClose}
      width={640}
      title={t(($) => $.metadata.title, {
        name: databaseName ?? databaseId ?? t(($) => $.shared.databaseFallback),
      })}
      drawerTestId="database-metadata-management-drawer"
      extra={queuedOperationId ? (
        <Button
          size="small"
          icon={<LinkOutlined />}
          onClick={() => {
            void trackMetadataAction('Open metadata management operations', () => {
              onOperationQueued?.(queuedOperationId)
            })
          }}
          data-testid="database-metadata-management-open-operations"
        >
          {t(($) => $.metadata.openOperations)}
        </Button>
      ) : null}
    >
      {metadataQuery.isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0' }}>
          <Spin />
        </div>
      ) : null}

      {!metadataQuery.isLoading && metadataQuery.error ? (
        <Alert
          type="error"
          showIcon
          message={t(($) => $.metadata.loadingFailedTitle)}
          description={getErrorMessage(metadataQuery.error)}
        />
      ) : null}

      {!metadataQuery.isLoading && payload && profile && snapshot ? (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Alert
            type={profileDescriptor?.tone}
            showIcon
            message={
              <Space size="small" wrap>
                <span>{profileDescriptor?.message}</span>
                {profileDescriptor ? renderStatusTag(profileDescriptor) : null}
              </Space>
            }
            description={profileDescriptor?.description}
            action={
              reverifyBlockedByIbcmdProfile && onOpenIbcmdProfile ? (
                <Button
                  icon={<LinkOutlined />}
                  onClick={() => {
                    void trackMetadataAction('Open IBCMD profile', onOpenIbcmdProfile)
                  }}
                  disabled={mutatingDisabled}
                  data-testid="database-metadata-management-open-ibcmd-profile"
                >
                  {isNarrow ? t(($) => $.metadata.actions.openIbcmdShort) : t(($) => $.metadata.actions.openIbcmd)}
                </Button>
              ) : (
                <Button
                  icon={<SyncOutlined />}
                  onClick={() => {
                    void trackMetadataAction('Re-verify configuration identity', handleReverify)
                  }}
                  loading={reverifyMutation.isPending}
                  disabled={mutatingDisabled || profile?.reverify_available === false}
                  data-testid="database-metadata-management-reverify"
                >
                  {isNarrow ? t(($) => $.metadata.actions.reverifyShort) : t(($) => $.metadata.actions.reverify)}
                </Button>
              )
            }
          />

          {renderMetadataSummarySection(t(($) => $.metadata.sections.configurationProfile), [
            { key: 'config_name', label: t(($) => $.metadata.fields.configName), value: formatValue(t, profile.config_name) },
            { key: 'config_version', label: t(($) => $.metadata.fields.configVersion), value: formatValue(t, profile.config_version) },
            { key: 'config_generation_id', label: t(($) => $.metadata.fields.generationId), value: formatValue(t, profile.config_generation_id) },
            { key: 'config_root_name', label: t(($) => $.metadata.fields.configRootName), value: formatValue(t, profile.config_root_name) },
            { key: 'config_vendor', label: t(($) => $.metadata.fields.vendor), value: formatValue(t, profile.config_vendor) },
            { key: 'verified_at', label: t(($) => $.metadata.fields.verifiedAt), value: formatDateTime(formatters, t, profile.verified_at) },
            { key: 'probe_requested', label: t(($) => $.metadata.fields.generationProbeRequested), value: formatDateTime(formatters, t, profile.generation_probe_requested_at) },
            { key: 'probe_checked', label: t(($) => $.metadata.fields.generationProbeChecked), value: formatDateTime(formatters, t, profile.generation_probe_checked_at) },
            { key: 'observed_metadata_hash', label: t(($) => $.metadata.fields.observedMetadataHash), value: formatValue(t, profile.observed_metadata_hash) },
            { key: 'canonical_metadata_hash', label: t(($) => $.metadata.fields.canonicalMetadataHash), value: formatValue(t, profile.canonical_metadata_hash) },
            { key: 'publication_drift', label: t(($) => $.metadata.fields.publicationDrift), value: profile.publication_drift ? t(($) => $.shared.yes) : t(($) => $.shared.no) },
          ])}

          <div
            aria-hidden
            style={{
              borderTop: '1px solid #e5e7eb',
              margin: 0,
              width: '100%',
            }}
          />

          <Alert
            type={snapshotDescriptor?.tone}
            showIcon
            message={
              <Space size="small" wrap>
                <span>{snapshotDescriptor?.message}</span>
                {snapshotDescriptor ? renderStatusTag(snapshotDescriptor) : null}
              </Space>
            }
            description={snapshotDescriptor?.description}
            action={
              <Button
                icon={<ReloadOutlined />}
                onClick={() => {
                  void trackMetadataAction('Refresh metadata snapshot', handleRefresh)
                }}
                loading={refreshMutation.isPending}
                disabled={mutatingDisabled || refreshBlockedByMissingProfile}
                data-testid="database-metadata-management-refresh"
              >
                {isNarrow ? t(($) => $.metadata.actions.refreshShort) : t(($) => $.metadata.actions.refresh)}
              </Button>
            }
          />

          {renderMetadataSummarySection(t(($) => $.metadata.sections.metadataSnapshot), [
            { key: 'snapshot_id', label: t(($) => $.metadata.fields.snapshotId), value: formatValue(t, snapshot.snapshot_id) },
            { key: 'source', label: t(($) => $.metadata.fields.source), value: formatValue(t, snapshot.source) },
            { key: 'fetched_at', label: t(($) => $.metadata.fields.fetchedAt), value: formatDateTime(formatters, t, snapshot.fetched_at) },
            { key: 'catalog_version', label: t(($) => $.metadata.fields.catalogVersion), value: formatValue(t, snapshot.catalog_version) },
            { key: 'config_name', label: t(($) => $.metadata.fields.snapshotConfigName), value: formatValue(t, snapshot.config_name) },
            { key: 'config_version', label: t(($) => $.metadata.fields.snapshotConfigVersion), value: formatValue(t, snapshot.config_version) },
            { key: 'metadata_hash', label: t(($) => $.metadata.fields.metadataHash), value: formatValue(t, snapshot.metadata_hash) },
            { key: 'observed_metadata_hash', label: t(($) => $.metadata.fields.observedMetadataHash), value: formatValue(t, snapshot.observed_metadata_hash) },
            { key: 'resolution_mode', label: t(($) => $.metadata.fields.resolutionMode), value: formatValue(t, snapshot.resolution_mode) },
            { key: 'is_shared_snapshot', label: t(($) => $.metadata.fields.sharedSnapshot), value: snapshot.is_shared_snapshot ? t(($) => $.shared.yes) : t(($) => $.shared.no) },
            { key: 'provenance_database_id', label: t(($) => $.metadata.fields.provenanceDatabase), value: formatValue(t, snapshot.provenance_database_id) },
            { key: 'provenance_confirmed_at', label: t(($) => $.metadata.fields.provenanceConfirmedAt), value: formatDateTime(formatters, t, snapshot.provenance_confirmed_at) },
            { key: 'missing_reason', label: t(($) => $.metadata.fields.missingReason), value: formatValue(t, snapshot.missing_reason) },
          ])}

          <div
            aria-hidden
            style={{
              borderTop: '1px solid #e5e7eb',
              margin: 0,
              width: '100%',
            }}
          />

          <Alert
            type={eligibilityDescriptor.tone}
            showIcon
            message={
              <Space size="small" wrap>
                <span>{eligibilityDescriptor.message}</span>
                {renderStatusTag(eligibilityDescriptor)}
              </Space>
            }
            description={eligibilityDescriptor.description}
            action={(
              <Button
                type="primary"
                onClick={() => {
                  void trackMetadataAction('Update cluster_all eligibility', handleSaveEligibility)
                }}
                disabled={eligibilityMutatingDisabled || !eligibilityDirty}
                loading={updateEligibilityMutation.isPending}
                data-testid="database-metadata-management-save-eligibility"
              >
                {t(($) => $.metadata.actions.saveEligibility)}
              </Button>
            )}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Typography.Title level={5} style={{ margin: 0 }}>
              {t(($) => $.metadata.sections.clusterAllEligibility)}
            </Typography.Title>
            <Radio.Group
              value={eligibilityDraft}
              onChange={(event) => setEligibilityDraft(event.target.value as ClusterAllEligibilityState)}
              disabled={eligibilityMutatingDisabled}
              data-testid="database-metadata-management-eligibility"
            >
              <Space direction="vertical" size={8}>
                <Radio value="eligible">{t(($) => $.metadata.radio.eligible)}</Radio>
                <Radio value="excluded">{t(($) => $.metadata.radio.excluded)}</Radio>
                <Radio value="unconfigured">{t(($) => $.metadata.radio.unconfigured)}</Radio>
              </Space>
            </Radio.Group>
            <Typography.Text type="secondary">
              {t(($) => $.metadata.decisionNote)}
            </Typography.Text>
          </div>

          {renderMetadataSummarySection(t(($) => $.metadata.sections.readiness), [
            { key: 'cluster_attached', label: t(($) => $.metadata.fields.clusterAttached), value: formatBoolean(t, readiness?.cluster_attached) },
            { key: 'runtime_enabled', label: t(($) => $.metadata.fields.runtimeEnabled), value: formatBoolean(t, readiness?.runtime_enabled) },
            { key: 'inbound_enabled', label: t(($) => $.metadata.fields.inboundEnabled), value: formatBoolean(t, readiness?.inbound_enabled) },
            { key: 'outbound_enabled', label: t(($) => $.metadata.fields.outboundEnabled), value: formatBoolean(t, readiness?.outbound_enabled) },
            { key: 'odata_configured', label: t(($) => $.metadata.fields.odataConfigured), value: formatBoolean(t, readiness?.odata_configured) },
            { key: 'credentials_configured', label: t(($) => $.metadata.fields.credentialsConfigured), value: formatBoolean(t, readiness?.credentials_configured) },
            { key: 'ibcmd_profile_configured', label: t(($) => $.metadata.fields.ibcmdConfigured), value: formatBoolean(t, readiness?.ibcmd_profile_configured) },
            { key: 'service_mapping_status', label: t(($) => $.metadata.fields.serviceMappingStatus), value: formatValue(t, readiness?.service_mapping_status) },
            { key: 'service_mapping_count', label: t(($) => $.metadata.fields.serviceMappingCount), value: String(readiness?.service_mapping_count ?? 0) },
            { key: 'default_policy', label: t(($) => $.metadata.fields.defaultPolicy), value: formatValue(t, readiness?.default_policy) },
            { key: 'health_status', label: t(($) => $.metadata.fields.healthStatus), value: formatValue(t, readiness?.health_status) },
          ])}

          <Typography.Text type="secondary">
            {t(($) => $.metadata.separationNote)}
          </Typography.Text>
        </Space>
      ) : null}
    </DrawerFormShell>
  )
}
