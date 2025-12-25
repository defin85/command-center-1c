/**
 * SelectTargetStep - Step 2 of NewOperationWizard
 * Displays databases table with server-side filters and checkbox selection.
 */

import { useEffect, useMemo, useCallback, useRef } from 'react'
import { Checkbox, Space, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Key } from 'react'
import type { Database } from '../../../../api/generated/model/database'
import { useDatabases } from '../../../../api/queries/databases'
import { useClusters } from '../../../../api/queries/clusters'
import type { SelectTargetStepProps } from './types'
import { getHealthTag, getStatusTag } from '../../../../utils/databaseStatus'
import { TableToolkit } from '../../../../components/table/TableToolkit'
import { useTableToolkit } from '../../../../components/table/hooks/useTableToolkit'

const { Title, Text } = Typography

export const SelectTargetStep = ({
  selectedDatabases,
  onSelectionChange,
  preselectedDatabases,
}: SelectTargetStepProps) => {
  const hasAppliedPreselection = useRef(false)

  const clustersQuery = useClusters()
  const clusters = clustersQuery.data?.clusters ?? []
  const clusterNameById = useMemo(() => {
    const map = new Map<string, string>()
    clusters.forEach((cluster) => {
      map.set(cluster.id, cluster.name)
    })
    return map
  }, [clusters])

  useEffect(() => {
    if (!hasAppliedPreselection.current && preselectedDatabases && preselectedDatabases.length > 0) {
      hasAppliedPreselection.current = true
      onSelectionChange(preselectedDatabases)
    }
  }, [preselectedDatabases, onSelectionChange])

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Database', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'cluster', label: 'Cluster', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'status', label: 'Status', sortable: true, groupKey: 'status', groupLabel: 'Status' },
    { key: 'last_check_status', label: 'Health', sortable: true, groupKey: 'status', groupLabel: 'Status' },
  ], [])

  const columns: ColumnsType<Database> = useMemo(() => ([
    {
      title: 'Database',
      dataIndex: 'name',
      key: 'name',
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
      dataIndex: 'cluster_id',
      key: 'cluster',
      render: (clusterId: string | null) => {
        const name = clusterId ? clusterNameById.get(clusterId) : undefined
        return name ? <Tag>{name}</Tag> : <Text type="secondary">-</Text>
      },
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
      key: 'last_check_status',
      width: 80,
      render: (status: string) => {
        const tag = getHealthTag(status)
        return <Tag color={tag.color}>{tag.label}</Tag>
      },
    },
  ]), [clusterNameById])

  const table = useTableToolkit({
    tableId: 'operation_targets',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const { data: databasesResponse, isLoading } = useDatabases({
    filters: {
      search: table.search,
      filters: table.filtersPayload,
      sort: table.sortPayload,
      limit: table.pagination.pageSize,
      offset: pageStart,
    },
  })
  const databases = databasesResponse?.databases ?? []
  const totalDatabases = typeof databasesResponse?.total === 'number'
    ? databasesResponse.total
    : databases.length

  const handleSelectionChange = useCallback(
    (selectedRowKeys: Key[]) => {
      onSelectionChange(selectedRowKeys as string[])
    },
    [onSelectionChange]
  )

  const handleSelectPage = useCallback((checked: boolean) => {
    const pageIds = databases.map((db) => db.id)
    if (checked) {
      const combined = new Set([...selectedDatabases, ...pageIds])
      onSelectionChange(Array.from(combined))
      return
    }
    const pageIdSet = new Set(pageIds)
    onSelectionChange(selectedDatabases.filter((id) => !pageIdSet.has(id)))
  }, [databases, onSelectionChange, selectedDatabases])

  const allPageSelected =
    databases.length > 0 && databases.every((db) => selectedDatabases.includes(db.id))
  const somePageSelected =
    databases.some((db) => selectedDatabases.includes(db.id)) && !allPageSelected

  const rowSelection = {
    selectedRowKeys: selectedDatabases,
    onChange: handleSelectionChange,
    getCheckboxProps: (record: Database) => ({
      disabled: record.status === 'maintenance',
    }),
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }} align="center">
        <Title level={4} style={{ margin: 0 }}>Select Databases</Title>
        <Checkbox
          indeterminate={somePageSelected}
          checked={allPageSelected}
          onChange={(event) => handleSelectPage(event.target.checked)}
        >
          Select page ({databases.length})
        </Checkbox>
        <Text type="secondary">
          {selectedDatabases.length} selected
        </Text>
      </Space>

      <TableToolkit
        table={table}
        data={databases}
        total={totalDatabases}
        loading={isLoading}
        rowKey="id"
        columns={columns}
        rowSelection={rowSelection}
        size="small"
        tableLayout="fixed"
        scroll={{ x: table.totalColumnsWidth }}
        searchPlaceholder="Search databases"
      />
    </div>
  )
}
