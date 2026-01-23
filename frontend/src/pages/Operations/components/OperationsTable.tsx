import type { OperationsTableProps } from '../types'
import { TableToolkit } from '../../../components/table/TableToolkit'

export const OperationsTable = ({
  table,
  operations,
  total,
  loading,
  toolbarActions,
  columns,
}: OperationsTableProps) => {
  return (
    <TableToolkit
      table={table}
      data={operations}
      total={total}
      loading={loading}
      rowKey="id"
      columns={columns}
      tableLayout="fixed"
      scroll={{ x: table.totalColumnsWidth }}
      toolbarActions={toolbarActions}
      searchPlaceholder="Search operations"
    />
  )
}
