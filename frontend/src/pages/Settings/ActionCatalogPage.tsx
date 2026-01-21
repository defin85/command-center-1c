import { Alert, Space, Typography } from 'antd'

const { Title, Text } = Typography

export function ActionCatalogPage() {
  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <div>
        <Title level={2} style={{ marginBottom: 0 }}>Action Catalog</Title>
        <Text type="secondary">Staff-only editor for RuntimeSetting <Text code>ui.action_catalog</Text>.</Text>
      </div>
      <Alert
        type="info"
        showIcon
        message="Coming soon"
        description="Guided editor + Raw JSON mode будет добавлен следующим шагом."
      />
    </Space>
  )
}

