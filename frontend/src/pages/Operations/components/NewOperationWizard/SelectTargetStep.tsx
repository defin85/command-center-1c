/**
 * SelectTargetStep - Step 2 of NewOperationWizard
 * Displays databases table with server-side filters and checkbox selection.
 */

import { useEffect, useMemo, useCallback, useRef } from 'react'
import { Checkbox, Space, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Key } from 'react'
import type { Cluster } from '../../../../api/generated/model/cluster'
import type { Database } from '../../../../api/generated/model/database'
import { useDatabases } from '../../../../api/queries/databases'
import { useClusters } from '../../../../api/queries/clusters'
import type { SelectTargetStepProps } from './types'
import { getHealthTag, getStatusTag } from '../../../../utils/databaseStatus'
import { TableToolkit } from '../../../../components/table/TableToolkit'
import { useTableToolkit } from '../../../../components/table/hooks/useTableToolkit'
import { useAuthz } from '../../../../authz/useAuthz'

const { Title, Text } = Typography

const EMPTY_CLUSTERS: Cluster[] = []
const EMPTY_DATABASES: Database[] = []

export const SelectTargetStep = ({
  selectedDatabases,
  onSelectionChange,
  onSelectionMetadataChange,
  preselectedDatabases,
}: SelectTargetStepProps) => {
  const hasAppliedPreselection = useRef(false)
  const authz = useAuthz()

  const clustersQuery = useClusters()
  const clusters = clustersQuery.data?.clusters ?? EMPTY_CLUSTERS
  const clusterNameById = useMemo(() => {
    const map = new Map<string, string>()
    clusters.forEach((cluster) => {
      map.set(cluster.id, cluster.name)
    })
    return map
  }, [clusters])

  const canOperateDatabase = useCallback(
    (databaseId: string) => authz.canDatabase(databaseId, 'OPERATE'),
    [authz]
  )

  useEffect(() => {
    if (!hasAppliedPreselection.current && preselectedDatabases && preselectedDatabases.length > 0) {
      hasAppliedPreselection.current = true
      onSelectionChange(preselectedDatabases)
    }
  }, [preselectedDatabases, onSelectionChange])

  useEffect(() => {
    if (authz.isLoading) return
    const filtered = selectedDatabases.filter((id) => canOperateDatabase(id))
    if (filtered.length !== selectedDatabases.length) {
      onSelectionChange(filtered)
    }
  }, [authz.isLoading, canOperateDatabase, onSelectionChange, selectedDatabases])

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
  const databases = databasesResponse?.databases ?? EMPTY_DATABASES
  const totalDatabases = typeof databasesResponse?.total === 'number'
    ? databasesResponse.total
    : databases.length

  const selectableIds = useMemo(
    () =>
      databases
        .filter((db) => canOperateDatabase(db.id) && db.status !== 'maintenance')
        .map((db) => db.id),
    [canOperateDatabase, databases]
  )

  useEffect(() => {
    if (!onSelectionMetadataChange) return
    if (selectedDatabases.length === 0 || databases.length === 0) return
    const map: Record<string, string> = {}
    databases.forEach((db) => {
      if (selectedDatabases.includes(db.id)) {
        map[db.id] = db.name
      }
    })
    if (Object.keys(map).length > 0) {
      onSelectionMetadataChange(map)
    }
  }, [databases, onSelectionMetadataChange, selectedDatabases])

  const handleSelectionChange = useCallback(
    (selectedRowKeys: Key[]) => {
      onSelectionChange(selectedRowKeys as string[])
    },
    [onSelectionChange]
  )

  const handleSelectPage = useCallback((checked: boolean) => {
    if (selectableIds.length === 0) return
    if (checked) {
      const combined = new Set([...selectedDatabases, ...selectableIds])
      onSelectionChange(Array.from(combined))
      return
    }
    const pageIdSet = new Set(selectableIds)
    onSelectionChange(selectedDatabases.filter((id) => !pageIdSet.has(id)))
  }, [onSelectionChange, selectableIds, selectedDatabases])

  const allPageSelected =
    selectableIds.length > 0 && selectableIds.every((id) => selectedDatabases.includes(id))
  const somePageSelected =
    selectableIds.some((id) => selectedDatabases.includes(id)) && !allPageSelected

  const rowSelection = {
    selectedRowKeys: selectedDatabases,
    onChange: handleSelectionChange,
    getCheckboxProps: (record: Database) => ({
      disabled: record.status === 'maintenance' || !canOperateDatabase(record.id),
    }),
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }} align="center">
        <Title level={4} style={{ margin: 0 }}>Select Databases</Title>
        <Checkbox
          id="wizard-select-page"
          indeterminate={somePageSelected}
          checked={allPageSelected}
          onChange={(event) => handleSelectPage(event.target.checked)}
          disabled={selectableIds.length === 0}
        >
          Select page ({selectableIds.length})
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
