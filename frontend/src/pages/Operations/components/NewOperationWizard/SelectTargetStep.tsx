/**
 * SelectTargetStep - Step 2 of NewOperationWizard
 * Displays databases table with filters and checkbox selection.
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { Table, Input, Select, Space, Typography, Tag, Checkbox } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { Key } from 'react'
import { getV2 } from '../../../../api/generated'
import type { Database } from '../../../../api/generated/model/database'
import type { Cluster } from '../../../../api/generated/model/cluster'
import type { SelectTargetStepProps, DatabaseWithCluster, DatabaseFilters } from './types'
import { getHealthTag, getStatusTag } from '../../../../utils/databaseStatus'

const { Title, Text } = Typography
const { Option } = Select

// Initialize API
const api = getV2()

/**
 * SelectTargetStep component
 * Renders a filterable table of databases with checkbox selection
 */
export const SelectTargetStep = ({
  selectedDatabases,
  onSelectionChange,
  preselectedDatabases,
}: SelectTargetStepProps) => {
  // Data state
  const [databases, setDatabases] = useState<Database[]>([])
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [loading, setLoading] = useState(false)

  // Track if preselection has been applied
  const hasAppliedPreselection = useRef(false)

  // Filter state
  const [filters, setFilters] = useState<DatabaseFilters>({
    search: '',
    clusterId: null,
    status: null,
  })

  // Load databases and clusters on mount
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [dbResponse, clusterResponse] = await Promise.all([
          api.getDatabasesListDatabases(),
          api.getClustersListClusters(),
        ])
        setDatabases(dbResponse.databases ?? [])
        setClusters(clusterResponse.clusters ?? [])
      } catch (error) {
        console.error('Failed to load data:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  // Apply preselected databases only once on initial load
  useEffect(() => {
    if (!hasAppliedPreselection.current && preselectedDatabases && preselectedDatabases.length > 0) {
      hasAppliedPreselection.current = true
      onSelectionChange(preselectedDatabases)
    }
  }, [preselectedDatabases, onSelectionChange])

  // Enhance databases with cluster info
  const databasesWithCluster: DatabaseWithCluster[] = useMemo(() => {
    return databases.map((db) => {
      // Try to find cluster by matching host/server address
      // This is a heuristic - in production you might have a cluster_id field
      let matchedCluster: Cluster | undefined

      // Check if database has cluster reference in its properties
      // For now, we'll group by similar host patterns
      for (const cluster of clusters) {
        if (cluster.ras_server && db.host && cluster.ras_server.includes(db.host.split(':')[0])) {
          matchedCluster = cluster
          break
        }
      }

      return {
        ...db,
        clusterName: matchedCluster?.name,
        clusterId: matchedCluster?.id,
      }
    })
  }, [databases, clusters])

  // Filter databases
  const filteredDatabases = useMemo(() => {
    return databasesWithCluster.filter((db) => {
      // Search filter
      if (filters.search) {
        const searchLower = filters.search.toLowerCase()
        const matchName = db.name.toLowerCase().includes(searchLower)
        const matchHost = db.host?.toLowerCase().includes(searchLower)
        const matchCluster = db.clusterName?.toLowerCase().includes(searchLower)
        if (!matchName && !matchHost && !matchCluster) {
          return false
        }
      }

      // Cluster filter
      if (filters.clusterId && db.clusterId !== filters.clusterId) {
        return false
      }

      // Status filter
      if (filters.status && db.status !== filters.status) {
        return false
      }

      return true
    })
  }, [databasesWithCluster, filters])

  // Handle filter changes
  const handleSearchChange = useCallback((value: string) => {
    setFilters((prev) => ({ ...prev, search: value }))
  }, [])

  const handleClusterChange = useCallback((value: string | null) => {
    setFilters((prev) => ({ ...prev, clusterId: value }))
  }, [])

  const handleStatusChange = useCallback((value: string | null) => {
    setFilters((prev) => ({ ...prev, status: value }))
  }, [])

  // Handle row selection
  const handleSelectionChange = useCallback(
    (selectedRowKeys: Key[]) => {
      onSelectionChange(selectedRowKeys as string[])
    },
    [onSelectionChange]
  )

  // Handle select all filtered
  const handleSelectAllFiltered = useCallback(
    (checked: boolean) => {
      if (checked) {
        const filteredIds = filteredDatabases.map((db) => db.id)
        // Merge with existing selection (databases not in current filter)
        const existingNotInFilter = selectedDatabases.filter(
          (id) => !filteredDatabases.some((db) => db.id === id)
        )
        onSelectionChange([...existingNotInFilter, ...filteredIds])
      } else {
        // Remove only filtered databases from selection
        const filteredIds = new Set(filteredDatabases.map((db) => db.id))
        onSelectionChange(selectedDatabases.filter((id) => !filteredIds.has(id)))
      }
    },
    [filteredDatabases, selectedDatabases, onSelectionChange]
  )

  // Check if all filtered are selected
  const allFilteredSelected =
    filteredDatabases.length > 0 &&
    filteredDatabases.every((db) => selectedDatabases.includes(db.id))

  const someFilteredSelected =
    filteredDatabases.some((db) => selectedDatabases.includes(db.id)) && !allFilteredSelected

  // Table columns
  const columns: ColumnsType<DatabaseWithCluster> = [
    {
      title: 'Database',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
      render: (name: string, record) => (
        <div>
          <Text strong>{name}</Text>
          {record.host && (
            <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>
              {record.host}:{record.port || 80}
            </Text>
          )}
        </div>
      ),
    },
    {
      title: 'Cluster',
      dataIndex: 'clusterName',
      key: 'cluster',
      render: (clusterName: string | undefined) =>
        clusterName ? <Tag>{clusterName}</Tag> : <Text type="secondary">-</Text>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const tag = getStatusTag(status)
        return <Tag color={tag.color}>{tag.label}</Tag>
      },
    },
    {
      title: 'Health',
      dataIndex: 'last_check_status',
      key: 'health',
      width: 80,
      render: (status: string) => {
        const tag = getHealthTag(status)
        return <Tag color={tag.color}>{tag.label}</Tag>
      },
    },
  ]

  // Row selection config
  const rowSelection = {
    selectedRowKeys: selectedDatabases,
    onChange: handleSelectionChange,
    getCheckboxProps: (record: DatabaseWithCluster) => ({
      // Disable selection for databases in maintenance mode
      disabled: record.status === 'maintenance',
    }),
  }

  // Get unique statuses for filter
  const uniqueStatuses = useMemo(() => {
    const statuses = new Set<string>()
    databases.forEach((db) => {
      if (db.status) statuses.add(db.status)
    })
    return Array.from(statuses)
  }, [databases])

  return (
    <div style={{ padding: '16px 0' }}>
      <Title level={4} style={{ marginBottom: 24 }}>
        Select Target Databases
      </Title>

      {/* Filters */}
      <Space style={{ marginBottom: 16, width: '100%' }} wrap>
        <Input
          placeholder="Search databases..."
          prefix={<SearchOutlined />}
          value={filters.search}
          onChange={(e) => handleSearchChange(e.target.value)}
          style={{ width: 250 }}
          allowClear
        />
        <Select
          placeholder="All Clusters"
          value={filters.clusterId}
          onChange={handleClusterChange}
          style={{ width: 200 }}
          allowClear
        >
          {clusters.map((cluster) => (
            <Option key={cluster.id} value={cluster.id}>
              {cluster.name}
            </Option>
          ))}
        </Select>
        <Select
          placeholder="All Statuses"
          value={filters.status}
          onChange={handleStatusChange}
          style={{ width: 150 }}
          allowClear
        >
          {uniqueStatuses.map((status) => (
            <Option key={status} value={status}>
              {status}
            </Option>
          ))}
        </Select>
      </Space>

      {/* Select all filtered checkbox */}
      <div style={{ marginBottom: 8 }}>
        <Checkbox
          checked={allFilteredSelected}
          indeterminate={someFilteredSelected}
          onChange={(e) => handleSelectAllFiltered(e.target.checked)}
          disabled={filteredDatabases.length === 0}
        >
          Select all filtered ({filteredDatabases.length} databases)
        </Checkbox>
      </div>

      {/* Table */}
      <Table
        rowSelection={rowSelection}
        columns={columns}
        dataSource={filteredDatabases}
        rowKey="id"
        loading={loading}
        pagination={{
          pageSize: 10,
          showSizeChanger: true,
          showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} databases`,
        }}
        size="middle"
      />

      {/* Selection summary */}
      <div style={{ marginTop: 16 }}>
        <Text strong>
          Selected: {selectedDatabases.length} database
          {selectedDatabases.length !== 1 ? 's' : ''}
        </Text>
      </div>
    </div>
  )
}
