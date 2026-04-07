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

const formatLastSync = (value: string | null) => (
  value ? new Date(value).toLocaleString() : 'Never'
)

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
  const databasesByStatus = statistics?.databases_by_status
  const previewDatabases = databases.slice(0, 6)

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Space wrap size={[8, 8]}>
        <StatusBadge status={cluster.status ?? 'unknown'} label={cluster.status_display} />
        <Text type="secondary">
          {cluster.databases_count} databases
        </Text>
        <Text type="secondary">
          Last sync: {formatLastSync(cluster.last_sync)}
        </Text>
      </Space>

      <Space wrap size={[8, 8]}>
        <RouteButton
          type="primary"
          icon={<DatabaseOutlined />}
          to={`/databases?cluster=${cluster.id}`}
        >
          Open Databases
        </RouteButton>
        <Button
          icon={<EditOutlined />}
          onClick={onOpenEdit}
          disabled={!canManage}
        >
          Edit
        </Button>
        <Button
          icon={<KeyOutlined />}
          onClick={onOpenCredentials}
          disabled={!canManage}
        >
          Credentials
        </Button>
        <Button
          icon={<SearchOutlined />}
          onClick={onOpenDiscover}
          disabled={!canDiscover}
        >
          Discover
        </Button>
        <Button
          icon={<ReloadOutlined />}
          loading={syncing}
          onClick={onSync}
          disabled={!canOperate}
        >
          Sync with RAS
        </Button>
        {canResetSync ? (
          <Popconfirm
            title="Reset sync status?"
            description="Use this if cluster sync is stuck."
            okText="Reset"
            cancelText="Cancel"
            onConfirm={onResetSyncStatus}
          >
            <Button
              icon={<UnlockOutlined />}
              loading={resetting}
            >
              Reset Sync
            </Button>
          </Popconfirm>
        ) : null}
        {canAdmin ? (
          <Popconfirm
            title="Delete cluster?"
            description="This will also delete all databases in this cluster."
            okText="Delete"
            cancelText="Cancel"
            onConfirm={onDelete}
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              loading={deleting}
            >
              Delete
            </Button>
          </Popconfirm>
        ) : null}
      </Space>

      {cluster.description ? (
        <Alert
          type="info"
          showIcon
          message="Description"
          description={cluster.description}
        />
      ) : null}

      <Descriptions
        title="Cluster connection"
        size="small"
        column={1}
        items={[
          {
            key: 'ras',
            label: 'RAS',
            children: formatHostPort(cluster.ras_host, cluster.ras_port, cluster.ras_server),
          },
          {
            key: 'rmngr',
            label: 'RMNGR',
            children: formatHostPort(cluster.rmngr_host, cluster.rmngr_port, 'Not configured'),
          },
          {
            key: 'ragent',
            label: 'RAGENT',
            children: formatHostPort(cluster.ragent_host, cluster.ragent_port, 'Not configured'),
          },
          {
            key: 'rphost',
            label: 'RPHOST range',
            children: `${cluster.rphost_port_from ?? '—'}..${cluster.rphost_port_to ?? '—'}`,
          },
          {
            key: 'service-url',
            label: 'Cluster service URL',
            children: cluster.cluster_service_url || 'Not configured',
          },
          {
            key: 'credentials',
            label: 'Credentials',
            children: cluster.cluster_pwd_configured ? 'Configured' : 'Missing',
          },
        ]}
      />

      {statistics ? (
        <Descriptions
          title="Cluster database health"
          size="small"
          column={1}
          items={[
            {
              key: 'total',
              label: 'Total databases',
              children: statistics.total_databases,
            },
            {
              key: 'healthy',
              label: 'Healthy databases',
              children: statistics.healthy_databases,
            },
            {
              key: 'active',
              label: 'Active status',
              children: databasesByStatus?.active ?? 0,
            },
            {
              key: 'inactive',
              label: 'Inactive status',
              children: databasesByStatus?.inactive ?? 0,
            },
            {
              key: 'error',
              label: 'Error status',
              children: databasesByStatus?.error ?? 0,
            },
            {
              key: 'maintenance',
              label: 'Maintenance status',
              children: databasesByStatus?.maintenance ?? 0,
            },
          ]}
        />
      ) : null}

      <div>
        <Title level={5} style={{ marginTop: 0 }}>
          Database preview
        </Title>
        {previewDatabases.length === 0 ? (
          <Alert
            type="warning"
            showIcon
            message="No databases returned for this cluster detail snapshot."
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
                    <Text type="secondary">{database.base_name || 'No base name'}</Text>
                  </Space>
                </Space>
              </List.Item>
            )}
          />
        )}
      </div>

      <JsonBlock
        title="Cluster metadata"
        value={cluster.metadata ?? {}}
        dataTestId="cluster-metadata-json"
      />
    </Space>
  )
}
