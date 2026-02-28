import { Card, Space, Tabs, Typography } from 'antd'

import { BindingsTab } from './masterData/BindingsTab'
import { ContractsTab } from './masterData/ContractsTab'
import { ItemsTab } from './masterData/ItemsTab'
import { PartiesTab } from './masterData/PartiesTab'
import { TaxProfilesTab } from './masterData/TaxProfilesTab'

const { Title, Text } = Typography

export function PoolMasterDataPage() {
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Title level={2} style={{ marginTop: 0, marginBottom: 0 }}>
          Pool Master Data
        </Title>
        <Text type="secondary">
          Canonical workspace for Party, Item, Contract, Tax Profile and Bindings in current tenant scope.
        </Text>
      </Card>
      <Tabs
        defaultActiveKey="party"
        items={[
          { key: 'party', label: 'Party', children: <PartiesTab /> },
          { key: 'item', label: 'Item', children: <ItemsTab /> },
          { key: 'contract', label: 'Contract', children: <ContractsTab /> },
          { key: 'tax-profile', label: 'TaxProfile', children: <TaxProfilesTab /> },
          { key: 'bindings', label: 'Bindings', children: <BindingsTab /> },
        ]}
      />
    </Space>
  )
}
