import { Table, Button, Space, Tag } from 'antd'
import { PlusOutlined } from '@ant-design/icons'

export const Databases = () => {
  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Host',
      dataIndex: 'host',
      key: 'host',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>
          {status}
        </Tag>
      ),
    },
    {
      title: 'Last Check',
      dataIndex: 'last_check',
      key: 'last_check',
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <h1>Databases</h1>
        <Button type="primary" icon={<PlusOutlined />}>
          Add Database
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
