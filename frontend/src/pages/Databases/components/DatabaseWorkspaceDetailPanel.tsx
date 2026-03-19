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

const formatValue = (value?: string | number | null) => {
  if (value === null || value === undefined) return 'n/a'
  if (typeof value === 'string') {
    return value.trim() ? value : 'n/a'
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
  const mutatingContextDisabled = mutatingDisabled || !canManage
  const extensionsDisabled = mutatingDisabled || !canOperate

  return (
    <EntityDetails title={`Database Workspace: ${database.name}`}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space size={[8, 8]} wrap>
          <StatusBadge status={database.status ?? 'unknown'} label={database.status_display || database.status || 'Unknown'} />
          <StatusBadge status={mapHealthStatus(database.last_check_status)} label={`Health: ${database.last_check_status}`} />
          <StatusBadge status={database.password_configured ? 'active' : 'warning'} label={database.password_configured ? 'Credentials configured' : 'Credentials missing'} />
          <StatusBadge
            status={database.ibcmd_connection ? 'active' : 'warning'}
            label={database.ibcmd_connection ? 'IBCMD profile configured' : 'IBCMD profile missing'}
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
            Metadata management
          </Button>
          <Button
            icon={<DatabaseOutlined />}
            type={activeContext === 'dbms' ? 'primary' : 'default'}
            onClick={() => onOpenContext('dbms')}
            disabled={mutatingContextDisabled}
            data-testid="database-workspace-open-dbms"
          >
            DBMS metadata
          </Button>
          <Button
            icon={<LinkOutlined />}
            type={activeContext === 'ibcmd' ? 'primary' : 'default'}
            onClick={() => onOpenContext('ibcmd')}
            disabled={mutatingContextDisabled}
            data-testid="database-workspace-open-ibcmd"
          >
            IBCMD profile
          </Button>
          <Button
            icon={<KeyOutlined />}
            type={activeContext === 'credentials' ? 'primary' : 'default'}
            onClick={() => onOpenContext('credentials')}
            disabled={mutatingContextDisabled}
            data-testid="database-workspace-open-credentials"
          >
            Credentials
          </Button>
          <Button
            icon={<AppstoreOutlined />}
            type={activeContext === 'extensions' ? 'primary' : 'default'}
            onClick={() => onOpenContext('extensions')}
            disabled={extensionsDisabled}
            data-testid="database-workspace-open-extensions"
          >
            Extensions
          </Button>
          <RouteButton
            icon={<ThunderboltOutlined />}
            to={`/operations?wizard=true&databases=${database.id}`}
            data-testid="database-workspace-open-operations"
          >
            Open operations workspace
          </RouteButton>
        </Space>

        {mutatingDisabled ? (
          <Text type="warning">
            Mutating actions require an active tenant context before credentials, DBMS metadata,
            IBCMD profile, or extensions changes can be launched.
          </Text>
        ) : null}

        <Descriptions
          title="Database Summary"
          size="small"
          bordered
          column={1}
          items={[
            {
              key: 'id',
              label: 'Database ID',
              children: <Text code data-testid="database-workspace-selected-id">{database.id}</Text>,
            },
            {
              key: 'cluster',
              label: 'Cluster ID',
              children: formatValue(database.cluster_id),
            },
            {
              key: 'host',
              label: 'Host',
              children: formatValue(database.host),
            },
            {
              key: 'server_address',
              label: '1C server',
              children: `${formatValue(database.server_address)}:${formatValue(database.server_port)}`,
            },
            {
              key: 'infobase',
              label: 'Infobase',
              children: formatValue(database.infobase_name || database.base_name),
            },
            {
              key: 'version',
              label: 'Version',
              children: formatValue(database.version),
            },
            {
              key: 'last_check',
              label: 'Last check',
              children: formatValue(database.last_check),
            },
            {
              key: 'dbms',
              label: 'DBMS metadata',
              children: `${formatValue(database.dbms)} / ${formatValue(database.db_server)} / ${formatValue(database.db_name)}`,
            },
            {
              key: 'odata',
              label: 'OData URL',
              children: formatValue(database.odata_url),
            },
            {
              key: 'restrictions',
              label: 'Restrictions',
              children: `jobs=${String(database.scheduled_jobs_deny)} sessions=${String(database.sessions_deny)}`,
            },
          ]}
        />
      </Space>
    </EntityDetails>
  )
}
