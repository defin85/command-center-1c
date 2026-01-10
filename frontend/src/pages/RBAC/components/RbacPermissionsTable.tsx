import { Alert, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'

export function RbacPermissionsTable(props: {
  columns: ColumnsType<any>
  dataSource: any[]
  rowKey: (row: any) => string
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

      <Table
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

