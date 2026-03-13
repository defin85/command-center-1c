import { Alert, App, Button, Descriptions, Divider, Drawer, Space, Spin, Tag, Typography } from 'antd'
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

type AlertTone = 'success' | 'info' | 'warning' | 'error'

export interface DatabaseMetadataManagementDrawerProps {
  open: boolean
  databaseId?: string
  databaseName?: string
  mutatingDisabled?: boolean
  onClose: () => void
  onOperationQueued?: (operationId: string) => void
}

type StatusDescriptor = {
  tone: AlertTone
  label: string
  message: string
  description?: string
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
  profile: DatabaseMetadataManagementConfigurationProfile
): StatusDescriptor => {
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
        label: 'Legacy',
        message: 'Profile собран из legacy snapshot и требует перепроверки.',
        description: 'Запустите Re-verify configuration identity, чтобы закрепить canonical reuse key.',
      }
    case 'reverify_required':
      return {
        tone: 'warning',
        label: 'Reverify required',
        message: 'Configuration identity помечен как требующий перепроверки.',
        description: 'Запустите Re-verify configuration identity перед полаганием на reuse key.',
      }
    case 'verification_failed':
      return {
        tone: 'error',
        label: 'Failed',
        message: 'Последняя перепроверка configuration identity завершилась ошибкой.',
        description: 'Повторите re-verify и проверьте operation result.',
      }
    default:
      return {
        tone: 'warning',
        label: 'Missing',
        message: 'Configuration profile отсутствует.',
        description: 'Сначала запустите Re-verify configuration identity.',
      }
  }
}

const buildSnapshotStatusDescriptor = (
  snapshot: DatabaseMetadataManagementSnapshot
): StatusDescriptor => {
  if (snapshot.status !== 'available') {
    if (snapshot.missing_reason === 'configuration_profile_unavailable') {
      return {
        tone: 'warning',
        label: 'Blocked',
        message: 'Metadata snapshot недоступен, пока не подтверждён configuration profile.',
        description: 'Сначала перепроверьте configuration identity.',
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
  const colorMap: Record<AlertTone, string> = {
    success: 'green',
    info: 'blue',
    warning: 'gold',
    error: 'red',
  }
  return <Tag color={colorMap[descriptor.tone]}>{descriptor.label}</Tag>
}

export const DatabaseMetadataManagementDrawer = ({
  open,
  databaseId,
  databaseName,
  mutatingDisabled = false,
  onClose,
  onOperationQueued,
}: DatabaseMetadataManagementDrawerProps) => {
  const { message } = App.useApp()
  const metadataQuery = useDatabaseMetadataManagement({
    id: databaseId ?? '',
    enabled: open && Boolean(databaseId),
  })
  const reverifyMutation = useReverifyDatabaseConfigurationProfile()
  const refreshMutation = useRefreshDatabaseMetadataSnapshot()

  const payload: DatabaseMetadataManagementResponse | null = metadataQuery.data ?? null
  const profile = payload?.configuration_profile ?? null
  const snapshot = payload?.metadata_snapshot ?? null
  const profileDescriptor = profile ? buildProfileStatusDescriptor(profile) : null
  const snapshotDescriptor = snapshot ? buildSnapshotStatusDescriptor(snapshot) : null
  const queuedOperationId =
    reverifyMutation.data?.operation_id || profile?.verification_operation_id || ''

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
    <Drawer
      open={open}
      onClose={onClose}
      width={640}
      title={`Metadata management: ${databaseName ?? databaseId ?? 'database'}`}
      data-testid="database-metadata-management-drawer"
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
              <Button
                icon={<SyncOutlined />}
                onClick={handleReverify}
                loading={reverifyMutation.isPending}
                disabled={mutatingDisabled}
                data-testid="database-metadata-management-reverify"
              >
                Перепроверить configuration identity
              </Button>
            }
          />

          <Descriptions
            title="Configuration profile"
            size="small"
            bordered
            column={1}
            items={[
              { key: 'config_name', label: 'Config name', children: formatValue(profile.config_name) },
              { key: 'config_version', label: 'Config version', children: formatValue(profile.config_version) },
              { key: 'config_generation_id', label: 'Generation ID', children: formatValue(profile.config_generation_id) },
              { key: 'config_root_name', label: 'Config root name', children: formatValue(profile.config_root_name) },
              { key: 'config_vendor', label: 'Vendor', children: formatValue(profile.config_vendor) },
              { key: 'verified_at', label: 'Verified at', children: formatDateTime(profile.verified_at) },
              { key: 'probe_requested', label: 'Generation probe requested', children: formatDateTime(profile.generation_probe_requested_at) },
              { key: 'probe_checked', label: 'Generation probe checked', children: formatDateTime(profile.generation_probe_checked_at) },
              { key: 'observed_metadata_hash', label: 'Observed metadata hash', children: formatValue(profile.observed_metadata_hash) },
              { key: 'canonical_metadata_hash', label: 'Canonical metadata hash', children: formatValue(profile.canonical_metadata_hash) },
              { key: 'publication_drift', label: 'Publication drift', children: profile.publication_drift ? 'Да' : 'Нет' },
            ]}
          />

          <Divider style={{ margin: 0 }} />

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
                disabled={mutatingDisabled}
                data-testid="database-metadata-management-refresh"
              >
                Обновить metadata snapshot
              </Button>
            }
          />

          <Descriptions
            title="Metadata snapshot"
            size="small"
            bordered
            column={1}
            items={[
              { key: 'snapshot_id', label: 'Snapshot ID', children: formatValue(snapshot.snapshot_id) },
              { key: 'source', label: 'Source', children: formatValue(snapshot.source) },
              { key: 'fetched_at', label: 'Fetched at', children: formatDateTime(snapshot.fetched_at) },
              { key: 'catalog_version', label: 'Catalog version', children: formatValue(snapshot.catalog_version) },
              { key: 'config_name', label: 'Snapshot config name', children: formatValue(snapshot.config_name) },
              { key: 'config_version', label: 'Snapshot config version', children: formatValue(snapshot.config_version) },
              { key: 'metadata_hash', label: 'Metadata hash', children: formatValue(snapshot.metadata_hash) },
              { key: 'observed_metadata_hash', label: 'Observed metadata hash', children: formatValue(snapshot.observed_metadata_hash) },
              { key: 'resolution_mode', label: 'Resolution mode', children: formatValue(snapshot.resolution_mode) },
              { key: 'is_shared_snapshot', label: 'Shared snapshot', children: snapshot.is_shared_snapshot ? 'Да' : 'Нет' },
              { key: 'provenance_database_id', label: 'Provenance database', children: formatValue(snapshot.provenance_database_id) },
              { key: 'provenance_confirmed_at', label: 'Provenance confirmed at', children: formatDateTime(snapshot.provenance_confirmed_at) },
              { key: 'missing_reason', label: 'Missing reason', children: formatValue(snapshot.missing_reason) },
            ]}
          />

          <Typography.Text type="secondary">
            Identity/reuse key и содержимое metadata snapshot управляются раздельно: re-verify обслуживает
            configuration profile, refresh обновляет нормализованный snapshot и drift diagnostics.
          </Typography.Text>
        </Space>
      ) : null}
    </Drawer>
  )
}
