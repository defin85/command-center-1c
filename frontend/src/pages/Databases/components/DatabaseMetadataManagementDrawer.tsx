import { Alert, App, Button, Space, Spin, Typography } from 'antd'
import { LinkOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'

import type { DatabaseMetadataManagementConfigurationProfile } from '../../../api/generated/model/databaseMetadataManagementConfigurationProfile'
import type { DatabaseMetadataManagementResponse } from '../../../api/generated/model/databaseMetadataManagementResponse'
import type { DatabaseMetadataManagementSnapshot } from '../../../api/generated/model/databaseMetadataManagementSnapshot'
import {
  useDatabaseMetadataManagement,
  useRefreshDatabaseMetadataSnapshot,
  useReverifyDatabaseConfigurationProfile,
} from '../../../api/queries/databases'
import { DrawerFormShell } from '../../../components/platform'

type AlertTone = 'success' | 'info' | 'warning' | 'error'

export interface DatabaseMetadataManagementDrawerProps {
  open: boolean
  databaseId?: string
  databaseName?: string
  mutatingDisabled?: boolean
  onClose: () => void
  onOperationQueued?: (operationId: string) => void
  onOpenIbcmdProfile?: () => void
}

type StatusDescriptor = {
  tone: AlertTone
  label: string
  message: string
  description?: string
}

type ConfigurationProfileState = DatabaseMetadataManagementConfigurationProfile & {
  reverify_available?: boolean
  reverify_blocker_code?: string
  reverify_blocker_message?: string
  reverify_blocking_action?: string
}

type MetadataSummaryItem = {
  key: string
  label: string
  value: string
}

const formatDateTime = (value?: string | null): string => {
  if (!value) return 'n/a'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('DD.MM.YYYY HH:mm:ss') : value
}

const formatValue = (value?: string | null): string => {
  return typeof value === 'string' && value.trim() ? value : 'n/a'
}

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
    return {
      tone: 'warning',
      label: 'Drift',
      message: 'Обнаружен publication drift между observed и canonical metadata.',
      description: 'Snapshot доступен, но observed hash отличается от canonical.',
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
          <Typography.Text>{item.value}</Typography.Text>
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
  onClose,
  onOperationQueued,
  onOpenIbcmdProfile,
}: DatabaseMetadataManagementDrawerProps) => {
  const { message } = App.useApp()
  const metadataQuery = useDatabaseMetadataManagement({
    id: databaseId ?? '',
    enabled: open && Boolean(databaseId),
  })
  const reverifyMutation = useReverifyDatabaseConfigurationProfile()
  const refreshMutation = useRefreshDatabaseMetadataSnapshot()

  const payload: DatabaseMetadataManagementResponse | null = metadataQuery.data ?? null
  const profile = (payload?.configuration_profile ?? null) as ConfigurationProfileState | null
  const snapshot = payload?.metadata_snapshot ?? null
  const profileDescriptor = profile ? buildProfileStatusDescriptor(profile) : null
  const snapshotDescriptor = snapshot ? buildSnapshotStatusDescriptor(snapshot, profile) : null
  const queuedOperationId =
    reverifyMutation.data?.operation_id || profile?.verification_operation_id || ''
  const reverifyBlockedByIbcmdProfile = (
    profile?.reverify_available === false
    && profile?.reverify_blocking_action === 'configure_ibcmd_connection_profile'
  )
  const refreshBlockedByMissingProfile = snapshot?.missing_reason === 'configuration_profile_unavailable'

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
          onClick={() => onOperationQueued?.(queuedOperationId)}
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
              <Space size="small">
                <span>{profileDescriptor?.message}</span>
                {profileDescriptor ? renderStatusTag(profileDescriptor) : null}
              </Space>
            }
            description={profileDescriptor?.description}
            action={
              reverifyBlockedByIbcmdProfile && onOpenIbcmdProfile ? (
                <Button
                  icon={<LinkOutlined />}
                  onClick={onOpenIbcmdProfile}
                  disabled={mutatingDisabled}
                  data-testid="database-metadata-management-open-ibcmd-profile"
                >
                  Открыть IBCMD profile
                </Button>
              ) : (
                <Button
                  icon={<SyncOutlined />}
                  onClick={handleReverify}
                  loading={reverifyMutation.isPending}
                  disabled={mutatingDisabled || profile?.reverify_available === false}
                  data-testid="database-metadata-management-reverify"
                >
                  Перепроверить configuration identity
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
              <Space size="small">
                <span>{snapshotDescriptor?.message}</span>
                {snapshotDescriptor ? renderStatusTag(snapshotDescriptor) : null}
              </Space>
            }
            description={snapshotDescriptor?.description}
            action={
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRefresh}
                loading={refreshMutation.isPending}
                disabled={mutatingDisabled || refreshBlockedByMissingProfile}
                data-testid="database-metadata-management-refresh"
              >
                Обновить metadata snapshot
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

          <Typography.Text type="secondary">
            Identity/reuse key и содержимое metadata snapshot управляются раздельно: re-verify обслуживает
            configuration profile, refresh обновляет нормализованный snapshot и drift diagnostics.
          </Typography.Text>
        </Space>
      ) : null}
    </DrawerFormShell>
  )
}
