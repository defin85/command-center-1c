import { useMemo, useState } from 'react'
import { Alert, Button, Drawer, Input, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import dayjs from 'dayjs'
import { useNavigate } from 'react-router-dom'

import { useClusters } from '../../api/queries/clusters'
import {
  useExtensionsOverview,
  useExtensionsOverviewDatabases,
  type ExtensionsOverviewDatabaseRow,
  type ExtensionsOverviewRow,
} from '../../api/queries/extensions'

const { Title, Text } = Typography

type Status = 'active' | 'inactive' | 'missing' | 'unknown'

const statusTagColor = (status: Status): string => {
  if (status === 'active') return 'green'
  if (status === 'inactive') return 'orange'
  if (status === 'missing') return 'red'
  return 'default'
}

export const Extensions = () => {
  const navigate = useNavigate()

  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<Status | undefined>(undefined)
  const [version, setVersion] = useState('')
  const [clusterId, setClusterId] = useState<string | undefined>(undefined)

  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  const clustersQuery = useClusters({ limit: 500, offset: 0 })
  const clusterOptions = useMemo(() => {
    const clusters = clustersQuery.data?.clusters ?? []
    return clusters
      .map((c) => ({ label: c.name || c.id, value: c.id }))
      .sort((a, b) => a.label.localeCompare(b.label))
  }, [clustersQuery.data?.clusters])

  const overviewQuery = useExtensionsOverview({
    search: search.trim() || undefined,
    status,
    version: version.trim() || undefined,
    cluster_id: clusterId,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  })

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedExtension, setSelectedExtension] = useState<string | null>(null)
  const [drawerStatus, setDrawerStatus] = useState<Status | undefined>(undefined)
  const [drawerVersion, setDrawerVersion] = useState<string>('')
  const [drawerPage, setDrawerPage] = useState(1)
  const [drawerPageSize, setDrawerPageSize] = useState(50)

  const drilldownEnabled = drawerOpen && Boolean(selectedExtension)
  const drilldownQuery = useExtensionsOverviewDatabases({
    name: selectedExtension || '',
    status: drawerStatus,
    version: drawerVersion.trim() || undefined,
    cluster_id: clusterId,
    limit: drawerPageSize,
    offset: (drawerPage - 1) * drawerPageSize,
  }, drilldownEnabled)

  const openDrawer = (name: string) => {
    setSelectedExtension(name)
    setDrawerOpen(true)
    setDrawerStatus(undefined)
    setDrawerVersion('')
    setDrawerPage(1)
    setDrawerPageSize(50)
  }

  const overviewColumns: ColumnsType<ExtensionsOverviewRow> = [
    {
      title: 'Extension',
      dataIndex: 'name',
      key: 'name',
      render: (value: string, row) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => openDrawer(row.name)}>
          {value}
        </Button>
      ),
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: 'Installed',
      key: 'installed',
      align: 'right',
      render: (_: unknown, row) => (
        <Text>
          {row.installed_count}
        </Text>
      ),
    },
    {
      title: 'Active',
      dataIndex: 'active_count',
      key: 'active_count',
      align: 'right',
      render: (v: number) => <Text>{v}</Text>,
    },
    {
      title: 'Inactive',
      dataIndex: 'inactive_count',
      key: 'inactive_count',
      align: 'right',
      render: (v: number) => <Text>{v}</Text>,
    },
    {
      title: 'Missing',
      dataIndex: 'missing_count',
      key: 'missing_count',
      align: 'right',
      render: (v: number) => <Text>{v}</Text>,
    },
    {
      title: 'Unknown',
      dataIndex: 'unknown_count',
      key: 'unknown_count',
      align: 'right',
      render: (v: number) => <Text>{v}</Text>,
    },
    {
      title: 'Versions',
      dataIndex: 'versions',
      key: 'versions',
      render: (versions: { version: string | null; count: number }[]) => {
        const top = [...(versions || [])]
          .filter((v) => v.count > 0)
          .sort((a, b) => b.count - a.count)
          .slice(0, 4)
        if (top.length === 0) {
          return <Text type="secondary">—</Text>
        }
        return (
          <Space size={4} wrap>
            {top.map((v) => (
              <Tag key={`${v.version ?? 'null'}-${v.count}`}>{v.version ?? '—'}: {v.count}</Tag>
            ))}
          </Space>
        )
      },
    },
    {
      title: 'Latest snapshot',
      dataIndex: 'latest_snapshot_at',
      key: 'latest_snapshot_at',
      render: (value?: string | null) => (
        value ? <Text>{dayjs(value).format('DD.MM.YYYY HH:mm')}</Text> : <Text type="secondary">—</Text>
      ),
    },
  ]

  const overviewPagination: TablePaginationConfig = {
    current: page,
    pageSize,
    total: overviewQuery.data?.total ?? 0,
    showSizeChanger: true,
    pageSizeOptions: [20, 50, 100, 200],
    onChange: (nextPage, nextPageSize) => {
      setPage(nextPage)
      if (nextPageSize && nextPageSize !== pageSize) {
        setPageSize(nextPageSize)
        setPage(1)
      }
    },
  }

  const drillColumns: ColumnsType<ExtensionsOverviewDatabaseRow> = [
    {
      title: 'Database',
      dataIndex: 'database_name',
      key: 'database_name',
      render: (value: string) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => navigate('/databases')}>
          {value}
        </Button>
      ),
    },
    {
      title: 'Cluster',
      key: 'cluster',
      render: (_: unknown, row) => (
        <Text type="secondary">{row.cluster_name || row.cluster_id || '—'}</Text>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (value: Status) => (
        <Tag color={statusTagColor(value)}>{value}</Tag>
      ),
    },
    {
      title: 'Version',
      dataIndex: 'version',
      key: 'version',
      render: (value?: string | null) => (
        value ? <Text>{value}</Text> : <Text type="secondary">—</Text>
      ),
    },
    {
      title: 'Snapshot',
      dataIndex: 'snapshot_updated_at',
      key: 'snapshot_updated_at',
      render: (value?: string | null) => (
        value ? <Text>{dayjs(value).format('DD.MM.YYYY HH:mm')}</Text> : <Text type="secondary">—</Text>
      ),
    },
  ]

  const drillPagination: TablePaginationConfig = {
    current: drawerPage,
    pageSize: drawerPageSize,
    total: drilldownQuery.data?.total ?? 0,
    showSizeChanger: true,
    pageSizeOptions: [20, 50, 100, 200],
    onChange: (nextPage, nextPageSize) => {
      setDrawerPage(nextPage)
      if (nextPageSize && nextPageSize !== drawerPageSize) {
        setDrawerPageSize(nextPageSize)
        setDrawerPage(1)
      }
    },
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>Extensions</Title>
          <Text type="secondary">Overview across accessible databases (snapshot-driven).</Text>
        </div>
        <Button onClick={() => overviewQuery.refetch()} loading={overviewQuery.isFetching}>
          Refresh
        </Button>
      </div>

      <Space wrap>
        <Input
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          placeholder="Search extension name"
          style={{ width: 260 }}
          allowClear
        />
        <Select
          value={status}
          onChange={(v) => { setStatus(v); setPage(1) }}
          allowClear
          placeholder="Status"
          style={{ width: 180 }}
          options={[
            { value: 'active', label: 'active' },
            { value: 'inactive', label: 'inactive' },
            { value: 'missing', label: 'missing' },
            { value: 'unknown', label: 'unknown' },
          ]}
        />
        <Input
          data-testid="extensions-overview-version"
          value={version}
          onChange={(e) => { setVersion(e.target.value); setPage(1) }}
          placeholder="Version (exact)"
          style={{ width: 220 }}
          allowClear
        />
        <Select
          value={clusterId}
          onChange={(v) => { setClusterId(v); setPage(1) }}
          allowClear
          placeholder="Cluster"
          style={{ width: 260 }}
          options={clusterOptions}
          loading={clustersQuery.isLoading}
          showSearch
          optionFilterProp="label"
        />
        <Text type="secondary">
          Total DBs: {overviewQuery.data?.total_databases ?? '—'}
        </Text>
      </Space>

      {overviewQuery.isError && (
        <Alert type="error" showIcon message="Failed to load extensions overview" />
      )}

      <Table
        rowKey="name"
        columns={overviewColumns}
        dataSource={overviewQuery.data?.extensions ?? []}
        loading={overviewQuery.isLoading}
        pagination={overviewPagination}
        size="middle"
      />

      <Drawer
        title={selectedExtension ? `Extension: ${selectedExtension}` : 'Extension'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={860}
        destroyOnHidden
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space wrap>
            <Select
              value={drawerStatus}
              onChange={(v) => { setDrawerStatus(v); setDrawerPage(1) }}
              allowClear
              placeholder="Status"
              style={{ width: 180 }}
              options={[
                { value: 'active', label: 'active' },
                { value: 'inactive', label: 'inactive' },
                { value: 'missing', label: 'missing' },
                { value: 'unknown', label: 'unknown' },
              ]}
            />
            <Input
              value={drawerVersion}
              onChange={(e) => { setDrawerVersion(e.target.value); setDrawerPage(1) }}
              placeholder="Version (exact)"
              style={{ width: 220 }}
              allowClear
            />
            <Button onClick={() => drilldownQuery.refetch()} loading={drilldownQuery.isFetching} disabled={!drilldownEnabled}>
              Refresh
            </Button>
          </Space>

          {drilldownQuery.isError && (
            <Alert type="error" showIcon message="Failed to load databases" />
          )}

          <Table
            rowKey="database_id"
            columns={drillColumns}
            dataSource={drilldownQuery.data?.databases ?? []}
            loading={drilldownQuery.isLoading}
            pagination={drillPagination}
            size="small"
          />
        </Space>
      </Drawer>
    </Space>
  )
}
