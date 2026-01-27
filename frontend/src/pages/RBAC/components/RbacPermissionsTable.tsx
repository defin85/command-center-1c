import { Alert, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'

type AnyRow = object

export function RbacPermissionsTable<T extends AnyRow = AnyRow>(props: {
  columns: ColumnsType<T>
  dataSource: T[]
  rowKey: (row: T) => string
  loading: boolean
  total: number
  page: number
  pageSize: number
  onPaginationChange: (page: number, pageSize: number) => void
  error?: unknown
  errorMessage?: string
}) {
  return (
    <>
      {Boolean(props.error) && (
        <Alert
          type="warning"
          message={props.errorMessage ?? 'Failed to load permissions'}
          style={{ marginBottom: 12 }}
        />
      )}

      <Table<T>
        size="small"
        columns={props.columns}
        dataSource={props.dataSource}
        loading={props.loading}
        rowKey={props.rowKey}
        pagination={{
          current: props.page,
          pageSize: props.pageSize,
          total: props.total,
          showSizeChanger: true,
          onChange: props.onPaginationChange,
        }}
      />
    </>
  )
}
