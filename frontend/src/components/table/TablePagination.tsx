import { Pagination, Space, Typography } from 'antd'

const { Text } = Typography

interface TablePaginationProps {
  total: number
  page: number
  pageSize: number
  onChange: (page: number, pageSize: number) => void
  pageSizeOptions?: number[]
}

export const TablePagination = ({
  total,
  page,
  pageSize,
  onChange,
  pageSizeOptions = [25, 50, 100, 200],
}: TablePaginationProps) => {
  if (total <= 0) return null

  return (
    <Space style={{ marginTop: 16, justifyContent: 'space-between', width: '100%' }}>
      <Text type="secondary">
        Total: {total}
      </Text>
      <Pagination
        current={page}
        pageSize={pageSize}
        total={total}
        showSizeChanger
        pageSizeOptions={pageSizeOptions}
        onChange={onChange}
      />
    </Space>
  )
}
