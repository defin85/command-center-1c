import { Table, Button, Space } from 'antd'
import { PlusOutlined } from '@ant-design/icons'

export const Operations = () => {
  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
    },
    {
      title: 'Database',
      dataIndex: 'database',
      key: 'database',
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <h1>Operations</h1>
        <Button type="primary" icon={<PlusOutlined />}>
          Create Operation
        </Button>
      </Space>
      <Table
        columns={columns}
        dataSource={[]}
        loading={false}
        pagination={{ pageSize: 50 }}
      />
    </div>
  )
}
