import {
  AppstoreOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  KeyOutlined,
  LinkOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { Button, Descriptions, Space, Typography } from 'antd'

import type { Database } from '../../../api/generated/model/database'
import { EntityDetails, RouteButton, StatusBadge } from '../../../components/platform'
import { useDatabasesTranslation, useLocaleFormatters } from '../../../i18n'
import { getHealthTag, getStatusTag } from '../../../utils/databaseStatus'

const { Text } = Typography

export type DatabaseManagementContext =
  | 'inspect'
  | 'credentials'
  | 'dbms'
  | 'ibcmd'
  | 'metadata'
  | 'extensions'

type DatabaseWorkspaceDetailPanelProps = {
  database: Database
  activeContext: DatabaseManagementContext
  canView: boolean
  canManage: boolean
  canOperate: boolean
  mutatingDisabled: boolean
  onOpenContext: (context: Exclude<DatabaseManagementContext, 'inspect'>) => void
}

const formatValue = (value: string | number | null | undefined, fallback: string) => {
  if (value === null || value === undefined) return fallback
  if (typeof value === 'string') {
    return value.trim() ? value : fallback
  }
  return String(value)
}

const mapHealthStatus = (status: Database['last_check_status']) => {
  switch (status) {
    case 'ok':
      return 'active'
    case 'degraded':
      return 'warning'
    case 'down':
      return 'error'
    default:
      return 'unknown'
  }
}

export function DatabaseWorkspaceDetailPanel({
  database,
  activeContext,
  canView,
  canManage,
  canOperate,
  mutatingDisabled,
  onOpenContext,
}: DatabaseWorkspaceDetailPanelProps) {
  const { t } = useDatabasesTranslation()
  const formatters = useLocaleFormatters()
  const mutatingContextDisabled = mutatingDisabled || !canManage
  const extensionsDisabled = mutatingDisabled || !canOperate
  const notAvailable = t(($) => $.shared.notAvailable)
  const statusLabels = {
    active: t(($) => $.status.active),
    inactive: t(($) => $.status.inactive),
    maintenance: t(($) => $.status.maintenance),
    error: t(($) => $.status.error),
    unknown: t(($) => $.status.unknown),
  } as const
  const healthLabels = {
    ok: t(($) => $.health.ok),
    degraded: t(($) => $.health.degraded),
    down: t(($) => $.health.down),
    unknown: t(($) => $.health.unknown),
  } as const
  const statusTag = getStatusTag(database.status, statusLabels)
  const healthTag = getHealthTag(database.last_check_status, healthLabels)
  const restrictionsValue = t(($) => $.detail.restrictionsValue, {
    jobs: database.scheduled_jobs_deny == null
      ? t(($) => $.shared.unknown)
      : database.scheduled_jobs_deny
        ? t(($) => $.shared.yes)
        : t(($) => $.shared.no),
    sessions: database.sessions_deny == null
      ? t(($) => $.shared.unknown)
      : database.sessions_deny
        ? t(($) => $.shared.yes)
        : t(($) => $.shared.no),
  })

  return (
    <EntityDetails title={t(($) => $.detail.titleWithName, { name: database.name })}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space size={[8, 8]} wrap>
          <StatusBadge status={database.status ?? 'unknown'} label={statusTag.label} />
          <StatusBadge status={mapHealthStatus(database.last_check_status)} label={t(($) => $.detail.badges.health, { value: healthTag.label })} />
          <StatusBadge
            status={database.password_configured ? 'active' : 'warning'}
            label={database.password_configured
              ? t(($) => $.detail.badges.credentialsConfigured)
              : t(($) => $.detail.badges.credentialsMissing)}
          />
          <StatusBadge
            status={database.ibcmd_connection ? 'active' : 'warning'}
            label={database.ibcmd_connection
              ? t(($) => $.detail.badges.ibcmdConfigured)
              : t(($) => $.detail.badges.ibcmdMissing)}
          />
        </Space>

        <Space size={[8, 8]} wrap>
          <Button
            icon={<DeploymentUnitOutlined />}
            type={activeContext === 'metadata' ? 'primary' : 'default'}
            onClick={() => onOpenContext('metadata')}
            disabled={!canView}
            data-testid="database-workspace-open-metadata"
          >
            {t(($) => $.detail.actions.metadata)}
          </Button>
          <Button
            icon={<DatabaseOutlined />}
            type={activeContext === 'dbms' ? 'primary' : 'default'}
            onClick={() => onOpenContext('dbms')}
            disabled={mutatingContextDisabled}
            data-testid="database-workspace-open-dbms"
          >
            {t(($) => $.detail.actions.dbms)}
          </Button>
          <Button
            icon={<LinkOutlined />}
            type={activeContext === 'ibcmd' ? 'primary' : 'default'}
            onClick={() => onOpenContext('ibcmd')}
            disabled={mutatingContextDisabled}
            data-testid="database-workspace-open-ibcmd"
          >
            {t(($) => $.detail.actions.ibcmd)}
          </Button>
          <Button
            icon={<KeyOutlined />}
            type={activeContext === 'credentials' ? 'primary' : 'default'}
            onClick={() => onOpenContext('credentials')}
            disabled={mutatingContextDisabled}
            data-testid="database-workspace-open-credentials"
          >
            {t(($) => $.detail.actions.credentials)}
          </Button>
          <Button
            icon={<AppstoreOutlined />}
            type={activeContext === 'extensions' ? 'primary' : 'default'}
            onClick={() => onOpenContext('extensions')}
            disabled={extensionsDisabled}
            data-testid="database-workspace-open-extensions"
          >
            {t(($) => $.detail.actions.extensions)}
          </Button>
          <RouteButton
            icon={<ThunderboltOutlined />}
            to={`/operations?wizard=true&databases=${database.id}`}
            data-testid="database-workspace-open-operations"
          >
            {t(($) => $.detail.actions.operations)}
          </RouteButton>
        </Space>

        {mutatingDisabled ? (
          <Text type="warning">
            {t(($) => $.detail.mutatingDisabled)}
          </Text>
        ) : null}

        <Descriptions
          title={t(($) => $.detail.summaryTitle)}
          size="small"
          bordered
          column={1}
          items={[
            {
              key: 'id',
              label: t(($) => $.detail.fields.databaseId),
              children: <Text code data-testid="database-workspace-selected-id">{database.id}</Text>,
            },
            {
              key: 'cluster',
              label: t(($) => $.detail.fields.clusterId),
              children: formatValue(database.cluster_id, notAvailable),
            },
            {
              key: 'host',
              label: t(($) => $.detail.fields.host),
              children: formatValue(database.host, notAvailable),
            },
            {
              key: 'server_address',
              label: t(($) => $.detail.fields.server),
              children: `${formatValue(database.server_address, notAvailable)}:${formatValue(database.server_port, notAvailable)}`,
            },
            {
              key: 'infobase',
              label: t(($) => $.detail.fields.infobase),
              children: formatValue(database.infobase_name || database.base_name, notAvailable),
            },
            {
              key: 'version',
              label: t(($) => $.detail.fields.version),
              children: formatValue(database.version, notAvailable),
            },
            {
              key: 'last_check',
              label: t(($) => $.detail.fields.lastCheck),
              children: formatters.dateTime(database.last_check, { fallback: notAvailable }),
            },
            {
              key: 'dbms',
              label: t(($) => $.detail.fields.dbms),
              children: `${formatValue(database.dbms, notAvailable)} / ${formatValue(database.db_server, notAvailable)} / ${formatValue(database.db_name, notAvailable)}`,
            },
            {
              key: 'odata',
              label: t(($) => $.detail.fields.odata),
              children: formatValue(database.odata_url, notAvailable),
            },
            {
              key: 'restrictions',
              label: t(($) => $.detail.fields.restrictions),
              children: restrictionsValue,
            },
          ]}
        />
      </Space>
    </EntityDetails>
  )
}
