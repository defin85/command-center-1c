import { Alert, App, Button, Grid, Radio, Space, Spin, Typography } from 'antd'
import { LinkOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
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

const formatDateTime = (value?: string | null): string => {
  if (!value) return 'n/a'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('DD.MM.YYYY HH:mm:ss') : value
}

const formatValue = (value?: string | null): string => {
  return typeof value === 'string' && value.trim() ? value : 'n/a'
}

const formatBoolean = (value?: boolean): string => (value ? 'Yes' : 'No')

const buildProfileStatusDescriptor = (
  profile: ConfigurationProfileState
): StatusDescriptor => {
  const reverifyBlocked = profile.reverify_available === false
  const blockerMessage = typeof profile.reverify_blocker_message === 'string'
    ? profile.reverify_blocker_message.trim()
    : ''
  switch (profile.status) {
    case 'verified':
      return {
        tone: 'success',
        label: 'Verified',
        message: 'Configuration identity подтверждён.',
        description: 'Reuse key берётся из проверенного configuration profile.',
      }
    case 'verification_pending':
      return {
        tone: 'info',
        label: 'Pending',
        message: 'Идёт асинхронная перепроверка configuration identity.',
        description: 'Следить за выполнением можно через Operations.',
      }
    case 'migrated_legacy':
      return {
        tone: 'warning',
        label: reverifyBlocked ? 'Blocked' : 'Legacy',
        message: reverifyBlocked
          ? 'Profile собран из legacy snapshot, но перепроверка сейчас недоступна.'
          : 'Profile собран из legacy snapshot и требует перепроверки.',
        description: blockerMessage || 'Запустите Re-verify configuration identity, чтобы закрепить canonical reuse key.',
      }
    case 'reverify_required':
      return {
        tone: 'warning',
        label: reverifyBlocked ? 'Blocked' : 'Reverify required',
        message: reverifyBlocked
          ? 'Configuration identity требует перепроверки, но re-verify сейчас недоступен.'
          : 'Configuration identity помечен как требующий перепроверки.',
        description: blockerMessage || 'Запустите Re-verify configuration identity перед полаганием на reuse key.',
      }
    case 'verification_failed':
      return {
        tone: reverifyBlocked ? 'warning' : 'error',
        label: reverifyBlocked ? 'Blocked' : 'Failed',
        message: reverifyBlocked
          ? 'Последняя перепроверка configuration identity завершилась ошибкой, а повторный запуск сейчас недоступен.'
          : 'Последняя перепроверка configuration identity завершилась ошибкой.',
        description: blockerMessage || 'Повторите re-verify и проверьте operation result.',
      }
    default:
      return {
        tone: 'warning',
        label: reverifyBlocked ? 'Blocked' : 'Missing',
        message: 'Configuration profile отсутствует.',
        description: blockerMessage || 'Сначала запустите Re-verify configuration identity.',
      }
  }
}

const buildSnapshotStatusDescriptor = (
  snapshot: DatabaseMetadataManagementSnapshot,
  profile?: ConfigurationProfileState | null,
): StatusDescriptor => {
  if (snapshot.status !== 'available') {
    if (snapshot.missing_reason === 'configuration_profile_unavailable') {
      const blockerMessage = typeof profile?.reverify_blocker_message === 'string'
        ? profile.reverify_blocker_message.trim()
        : ''
      return {
        tone: 'warning',
        label: 'Blocked',
        message: 'Metadata snapshot недоступен, пока не подтверждён configuration profile.',
        description: blockerMessage || 'Сначала перепроверьте configuration identity.',
      }
    }
    return {
      tone: 'warning',
        label: 'Missing',
      message: 'Current metadata snapshot отсутствует.',
      description: 'Запустите Refresh metadata snapshot для выбранной ИБ.',
    }
  }

  if (snapshot.publication_drift) {
    const lastObservedRefresh = formatDateTime(profile?.observed_metadata_fetched_at)
    const canonicalSnapshotFetchedAt = formatDateTime(snapshot.fetched_at)
    return {
      tone: 'warning',
      label: 'Drift',
      message: 'Live metadata отличается от canonical snapshot.',
      description: (
        <Space direction="vertical" size={4}>
          <span>{`Последний успешный live metadata refresh: ${lastObservedRefresh}.`}</span>
          <span>{`Текущий canonical snapshot fetched at: ${canonicalSnapshotFetchedAt}.`}</span>
          <span>
            {snapshot.is_shared_snapshot
              ? 'Refresh metadata snapshot может завершиться успешно и всё равно оставить drift: для этой business identity reused shared snapshot, поэтому observed hash обновляется, а canonical остаётся прежним.'
              : 'Refresh metadata snapshot может завершиться успешно и всё равно оставить drift, пока live publication metadata не совпадёт с canonical snapshot.'}
          </span>
        </Space>
      ),
    }
  }

  return {
    tone: 'success',
    label: snapshot.is_shared_snapshot ? 'Shared' : 'Database scope',
    message: 'Metadata snapshot доступен.',
    description: snapshot.is_shared_snapshot
      ? 'Для этой ИБ используется shared snapshot по config_name/config_version.'
      : 'Для этой ИБ используется database-scoped snapshot.',
  }
}

const buildEligibilityStatusDescriptor = (
  state: ClusterAllEligibilityState
): StatusDescriptor => {
  switch (state) {
    case 'eligible':
      return {
        tone: 'success',
        label: 'Eligible',
        message: 'Эта база войдёт в pool master-data cluster_all launch.',
        description: 'Use this for databases that intentionally belong to cluster-wide manual sync.',
      }
    case 'excluded':
      return {
        tone: 'info',
        label: 'Excluded',
        message: 'Эта база намеренно исключена из pool master-data cluster_all.',
        description: 'Для разового запуска по этой ИБ используйте target mode Database Set.',
      }
    default:
      return {
        tone: 'warning',
        label: 'Unconfigured',
        message: 'По этой базе ещё не принято явное решение для cluster_all.',
        description: 'Пока состояние не переведено в Eligible или Excluded, cluster-wide launch блокируется fail-closed.',
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
  const profileDescriptor = profile ? buildProfileStatusDescriptor(profile) : null
  const snapshotDescriptor = snapshot ? buildSnapshotStatusDescriptor(snapshot, profile) : null
  const eligibilityDescriptor = buildEligibilityStatusDescriptor(eligibilityState)
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
          message.success(response.message || 'Configuration identity re-verify queued')
        },
        onError: (error: Error) => {
          message.error(`Не удалось запустить re-verify: ${error.message}`)
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
          message.success('Metadata snapshot обновлён')
        },
        onError: (error: Error) => {
          message.error(`Не удалось обновить snapshot: ${error.message}`)
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
          message.success(response.message || 'Pool master-data eligibility updated')
        },
        onError: (error: Error) => {
          message.error(`Не удалось обновить eligibility: ${error.message}`)
        },
      },
    )
  }

  return (
    <DrawerFormShell
      open={open}
      onClose={onClose}
      width={640}
      title={`Metadata management: ${databaseName ?? databaseId ?? 'database'}`}
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
          Открыть Operations
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
          message="Не удалось загрузить metadata management state"
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
                  {isNarrow ? 'Открыть IBCMD' : 'Открыть IBCMD profile'}
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
                  {isNarrow ? 'Перепроверить' : 'Перепроверить configuration identity'}
                </Button>
              )
            }
          />

          {renderMetadataSummarySection('Configuration profile', [
            { key: 'config_name', label: 'Config name', value: formatValue(profile.config_name) },
            { key: 'config_version', label: 'Config version', value: formatValue(profile.config_version) },
            { key: 'config_generation_id', label: 'Generation ID', value: formatValue(profile.config_generation_id) },
            { key: 'config_root_name', label: 'Config root name', value: formatValue(profile.config_root_name) },
            { key: 'config_vendor', label: 'Vendor', value: formatValue(profile.config_vendor) },
            { key: 'verified_at', label: 'Verified at', value: formatDateTime(profile.verified_at) },
            { key: 'probe_requested', label: 'Generation probe requested', value: formatDateTime(profile.generation_probe_requested_at) },
            { key: 'probe_checked', label: 'Generation probe checked', value: formatDateTime(profile.generation_probe_checked_at) },
            { key: 'observed_metadata_hash', label: 'Observed metadata hash', value: formatValue(profile.observed_metadata_hash) },
            { key: 'canonical_metadata_hash', label: 'Canonical metadata hash', value: formatValue(profile.canonical_metadata_hash) },
            { key: 'publication_drift', label: 'Publication drift', value: profile.publication_drift ? 'Да' : 'Нет' },
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
                {isNarrow ? 'Обновить snapshot' : 'Обновить metadata snapshot'}
              </Button>
            }
          />

          {renderMetadataSummarySection('Metadata snapshot', [
            { key: 'snapshot_id', label: 'Snapshot ID', value: formatValue(snapshot.snapshot_id) },
            { key: 'source', label: 'Source', value: formatValue(snapshot.source) },
            { key: 'fetched_at', label: 'Fetched at', value: formatDateTime(snapshot.fetched_at) },
            { key: 'catalog_version', label: 'Catalog version', value: formatValue(snapshot.catalog_version) },
            { key: 'config_name', label: 'Snapshot config name', value: formatValue(snapshot.config_name) },
            { key: 'config_version', label: 'Snapshot config version', value: formatValue(snapshot.config_version) },
            { key: 'metadata_hash', label: 'Metadata hash', value: formatValue(snapshot.metadata_hash) },
            { key: 'observed_metadata_hash', label: 'Observed metadata hash', value: formatValue(snapshot.observed_metadata_hash) },
            { key: 'resolution_mode', label: 'Resolution mode', value: formatValue(snapshot.resolution_mode) },
            { key: 'is_shared_snapshot', label: 'Shared snapshot', value: snapshot.is_shared_snapshot ? 'Да' : 'Нет' },
            { key: 'provenance_database_id', label: 'Provenance database', value: formatValue(snapshot.provenance_database_id) },
            { key: 'provenance_confirmed_at', label: 'Provenance confirmed at', value: formatDateTime(snapshot.provenance_confirmed_at) },
            { key: 'missing_reason', label: 'Missing reason', value: formatValue(snapshot.missing_reason) },
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
                Save eligibility
              </Button>
            )}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Typography.Title level={5} style={{ margin: 0 }}>
              Pool master-data cluster_all eligibility
            </Typography.Title>
            <Radio.Group
              value={eligibilityDraft}
              onChange={(event) => setEligibilityDraft(event.target.value as ClusterAllEligibilityState)}
              disabled={eligibilityMutatingDisabled}
              data-testid="database-metadata-management-eligibility"
            >
              <Space direction="vertical" size={8}>
                <Radio value="eligible">Eligible: include this database in cluster_all.</Radio>
                <Radio value="excluded">Excluded: keep it out of cluster_all intentionally.</Radio>
                <Radio value="unconfigured">Unconfigured: block cluster_all until a decision is made.</Radio>
              </Space>
            </Radio.Group>
            <Typography.Text type="secondary">
              Eligibility is an operator decision about business participation. It does not change automatically
              when readiness or health drifts.
            </Typography.Text>
          </div>

          {renderMetadataSummarySection('Pool master-data readiness', [
            { key: 'cluster_attached', label: 'Cluster attached', value: formatBoolean(readiness?.cluster_attached) },
            { key: 'runtime_enabled', label: 'Runtime enabled', value: formatBoolean(readiness?.runtime_enabled) },
            { key: 'inbound_enabled', label: 'Inbound enabled', value: formatBoolean(readiness?.inbound_enabled) },
            { key: 'outbound_enabled', label: 'Outbound enabled', value: formatBoolean(readiness?.outbound_enabled) },
            { key: 'odata_configured', label: 'OData configured', value: formatBoolean(readiness?.odata_configured) },
            { key: 'credentials_configured', label: 'Credentials configured', value: formatBoolean(readiness?.credentials_configured) },
            { key: 'ibcmd_profile_configured', label: 'IBCMD profile configured', value: formatBoolean(readiness?.ibcmd_profile_configured) },
            { key: 'service_mapping_status', label: 'Service mapping status', value: formatValue(readiness?.service_mapping_status) },
            { key: 'service_mapping_count', label: 'Service mapping count', value: String(readiness?.service_mapping_count ?? 0) },
            { key: 'default_policy', label: 'Default policy', value: formatValue(readiness?.default_policy) },
            { key: 'health_status', label: 'Health status', value: formatValue(readiness?.health_status) },
          ])}

          <Typography.Text type="secondary">
            Identity/reuse key и содержимое metadata snapshot управляются раздельно: re-verify обслуживает
            configuration profile, refresh обновляет нормализованный snapshot и drift diagnostics.
          </Typography.Text>
        </Space>
      ) : null}
    </DrawerFormShell>
  )
}
