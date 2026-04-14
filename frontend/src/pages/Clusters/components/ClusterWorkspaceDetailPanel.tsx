import { Alert, Button, Descriptions, List, Popconfirm, Space, Typography } from 'antd'
import {
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  ReloadOutlined,
  SearchOutlined,
  UnlockOutlined,
} from '@ant-design/icons'

import type { Cluster } from '../../../api/generated/model/cluster'
import type { ClusterStatistics } from '../../../api/generated/model/clusterStatistics'
import type { Database } from '../../../api/generated/model/database'
import { JsonBlock, RouteButton, StatusBadge } from '../../../components/platform'
import { formatHostPort } from '../../../api/queries/clusters'
import { useClustersTranslation, useLocaleFormatters } from '../../../i18n'

const { Text, Title } = Typography

type ClusterWorkspaceDetailPanelProps = {
  cluster: Cluster
  statistics?: ClusterStatistics | null
  databases: Database[]
  canManage: boolean
  canOperate: boolean
  canAdmin: boolean
  canDiscover: boolean
  canResetSync: boolean
  syncing: boolean
  resetting: boolean
  deleting: boolean
  onOpenEdit: () => void
  onOpenCredentials: () => void
  onSync: () => void
  onResetSyncStatus: () => void
  onDelete: () => void
  onOpenDiscover: () => void
}

export function ClusterWorkspaceDetailPanel({
  cluster,
  statistics,
  databases,
  canManage,
  canOperate,
  canAdmin,
  canDiscover,
  canResetSync,
  syncing,
  resetting,
  deleting,
  onOpenEdit,
  onOpenCredentials,
  onSync,
  onResetSyncStatus,
  onDelete,
  onOpenDiscover,
}: ClusterWorkspaceDetailPanelProps) {
  const { t } = useClustersTranslation()
  const formatters = useLocaleFormatters()
  const databasesByStatus = statistics?.databases_by_status
  const previewDatabases = databases.slice(0, 6)

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Space wrap size={[8, 8]}>
        <StatusBadge status={cluster.status ?? 'unknown'} label={cluster.status_display} />
        <Text type="secondary">
          {t(($) => $.labels.databasesCount, {
            count: cluster.databases_count,
          })}
        </Text>
        <Text type="secondary">
          {t(($) => $.labels.lastSync, {
            value: formatters.dateTime(cluster.last_sync, {
              fallback: t(($) => $.values.never),
            }),
          })}
        </Text>
      </Space>

      <Space wrap size={[8, 8]}>
        <RouteButton
          type="primary"
          icon={<DatabaseOutlined />}
          to={`/databases?cluster=${cluster.id}`}
        >
          {t(($) => $.actions.openDatabases)}
        </RouteButton>
        <Button
          icon={<EditOutlined />}
          onClick={onOpenEdit}
          disabled={!canManage}
        >
          {t(($) => $.actions.edit)}
        </Button>
        <Button
          icon={<KeyOutlined />}
          onClick={onOpenCredentials}
          disabled={!canManage}
        >
          {t(($) => $.actions.credentials)}
        </Button>
        <Button
          icon={<SearchOutlined />}
          onClick={onOpenDiscover}
          disabled={!canDiscover}
        >
          {t(($) => $.actions.discover)}
        </Button>
        <Button
          icon={<ReloadOutlined />}
          loading={syncing}
          onClick={onSync}
          disabled={!canOperate}
        >
          {t(($) => $.actions.syncWithRas)}
        </Button>
        {canResetSync ? (
          <Popconfirm
            title={t(($) => $.confirmations.resetSyncTitle)}
            description={t(($) => $.confirmations.resetSyncDescription)}
            okText={t(($) => $.actions.reset)}
            cancelText={t(($) => $.actions.cancel)}
            onConfirm={onResetSyncStatus}
          >
            <Button
              icon={<UnlockOutlined />}
              loading={resetting}
            >
              {t(($) => $.actions.resetSync)}
            </Button>
          </Popconfirm>
        ) : null}
        {canAdmin ? (
          <Popconfirm
            title={t(($) => $.confirmations.deleteTitle)}
            description={t(($) => $.confirmations.deleteDescription)}
            okText={t(($) => $.actions.delete)}
            cancelText={t(($) => $.actions.cancel)}
            onConfirm={onDelete}
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              loading={deleting}
            >
              {t(($) => $.actions.delete)}
            </Button>
          </Popconfirm>
        ) : null}
      </Space>

      {cluster.description ? (
        <Alert
          type="info"
          showIcon
          message={t(($) => $.labels.description)}
          description={cluster.description}
        />
      ) : null}

      <Descriptions
        title={t(($) => $.labels.clusterConnection)}
        size="small"
        column={1}
        items={[
          {
            key: 'ras',
            label: t(($) => $.labels.ras),
            children: formatHostPort(cluster.ras_host, cluster.ras_port, cluster.ras_server),
          },
          {
            key: 'rmngr',
            label: t(($) => $.labels.rmngr),
            children: formatHostPort(cluster.rmngr_host, cluster.rmngr_port, t(($) => $.values.notConfigured)),
          },
          {
            key: 'ragent',
            label: t(($) => $.labels.ragent),
            children: formatHostPort(cluster.ragent_host, cluster.ragent_port, t(($) => $.values.notConfigured)),
          },
          {
            key: 'rphost',
            label: t(($) => $.labels.rphostRange),
            children: `${cluster.rphost_port_from ?? '—'}..${cluster.rphost_port_to ?? '—'}`,
          },
          {
            key: 'service-url',
            label: t(($) => $.labels.clusterServiceUrl),
            children: cluster.cluster_service_url || t(($) => $.values.notConfigured),
          },
          {
            key: 'credentials',
            label: t(($) => $.labels.credentials),
            children: cluster.cluster_pwd_configured ? t(($) => $.values.configured) : t(($) => $.values.missing),
          },
        ]}
      />

      {statistics ? (
        <Descriptions
          title={t(($) => $.labels.clusterDatabaseHealth)}
          size="small"
          column={1}
          items={[
            {
              key: 'total',
              label: t(($) => $.labels.totalDatabases),
              children: statistics.total_databases,
            },
            {
              key: 'healthy',
              label: t(($) => $.labels.healthyDatabases),
              children: statistics.healthy_databases,
            },
            {
              key: 'active',
              label: t(($) => $.labels.activeStatus),
              children: databasesByStatus?.active ?? 0,
            },
            {
              key: 'inactive',
              label: t(($) => $.labels.inactiveStatus),
              children: databasesByStatus?.inactive ?? 0,
            },
            {
              key: 'error',
              label: t(($) => $.labels.errorStatus),
              children: databasesByStatus?.error ?? 0,
            },
            {
              key: 'maintenance',
              label: t(($) => $.labels.maintenanceStatus),
              children: databasesByStatus?.maintenance ?? 0,
            },
          ]}
        />
      ) : null}

      <div>
        <Title level={5} style={{ marginTop: 0 }}>
          {t(($) => $.labels.databasePreview)}
        </Title>
        {previewDatabases.length === 0 ? (
          <Alert
            type="warning"
            showIcon
            message={t(($) => $.alerts.noDatabasesPreview)}
          />
        ) : (
          <List
            size="small"
            bordered
            dataSource={previewDatabases}
            renderItem={(database) => (
              <List.Item>
                <Space direction="vertical" size={0} style={{ width: '100%' }}>
                  <Text strong>{database.name || database.id}</Text>
                  <Space wrap size={[8, 8]}>
                    <StatusBadge status={database.status ?? 'unknown'} label={database.status_display} />
                    <Text type="secondary">{database.host}:{database.port}</Text>
                    <Text type="secondary">{database.base_name || t(($) => $.labels.noBaseName)}</Text>
                  </Space>
                </Space>
              </List.Item>
            )}
          />
        )}
      </div>

      <JsonBlock
        title={t(($) => $.labels.clusterMetadata)}
        value={cluster.metadata ?? {}}
        dataTestId="cluster-metadata-json"
      />
    </Space>
  )
}
