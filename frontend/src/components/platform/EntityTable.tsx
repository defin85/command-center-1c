import { ProCard } from '@ant-design/pro-components'
import { Spin, Table } from 'antd'
import type { ColumnsType, TableProps } from 'antd/es/table'
import type { ReactNode } from 'react'

import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'

type EntityTableProps<T extends object> = {
  title: ReactNode
  extra?: ReactNode
  toolbar?: ReactNode
  error?: string | null
  loading?: boolean
  emptyDescription?: ReactNode
  dataSource: T[]
  columns: ColumnsType<T>
  rowKey: TableProps<T>['rowKey']
  onRow?: TableProps<T>['onRow']
  rowClassName?: TableProps<T>['rowClassName']
  pagination?: TableProps<T>['pagination']
  size?: TableProps<T>['size']
}

export function EntityTable<T extends object>({
  title,
  extra,
  toolbar,
  error,
  loading = false,
  emptyDescription,
  dataSource,
  columns,
  rowKey,
  onRow,
  rowClassName,
  pagination = false,
  size = 'small',
}: EntityTableProps<T>) {
  return (
    <ProCard title={title} extra={extra}>
      {toolbar}
      {error ? (
        <ErrorState message={error} />
      ) : loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
          <Spin />
        </div>
      ) : dataSource.length === 0 ? (
        <EmptyState description={emptyDescription} />
      ) : (
        <Table
          rowKey={rowKey}
          size={size}
          pagination={pagination}
          columns={columns}
          dataSource={dataSource}
          onRow={onRow}
          rowClassName={rowClassName}
        />
      )}
    </ProCard>
  )
}
