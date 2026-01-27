import type { CSSProperties, ReactNode } from 'react'
import { Card, Empty, Space } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { RbacPermissionsTable } from './RbacPermissionsTable'

type AnyRow = object

export function PermissionsTable<T extends AnyRow = AnyRow>(props: {
  title: string
  style?: CSSProperties
  preamble?: ReactNode
  toolbar?: ReactNode
  empty?: {
    show: boolean
    description: ReactNode
  }
  columns: ColumnsType<T>
  rows: T[]
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
    <Card title={props.title} size="small" style={props.style}>
      {props.preamble && (
        <div style={{ marginBottom: 12 }}>
          {props.preamble}
        </div>
      )}
      {props.empty?.show ? (
        <Empty description={props.empty.description} />
      ) : (
        <>
          {props.toolbar && (
            <Space wrap style={{ marginBottom: 12 }}>
              {props.toolbar}
            </Space>
          )}
          <RbacPermissionsTable
            columns={props.columns}
            dataSource={props.rows}
            loading={props.loading}
            rowKey={props.rowKey}
            total={props.total}
            page={props.page}
            pageSize={props.pageSize}
            onPaginationChange={props.onPaginationChange}
            error={props.error}
            errorMessage={props.errorMessage}
          />
        </>
      )}
    </Card>
  )
}
