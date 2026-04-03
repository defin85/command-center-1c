import { useEffect, useMemo, useState } from 'react'
import { Alert, App as AntApp, Card, Space, Tabs, Typography } from 'antd'

import { getPoolMasterDataRegistry, type PoolMasterDataRegistryEntry } from '../../api/intercompanyPools'
import { BindingsTab } from './masterData/BindingsTab'
import { BootstrapImportTab } from './masterData/BootstrapImportTab'
import { ContractsTab } from './masterData/ContractsTab'
import { ItemsTab } from './masterData/ItemsTab'
import { PartiesTab } from './masterData/PartiesTab'
import { SyncStatusTab } from './masterData/SyncStatusTab'
import { TaxProfilesTab } from './masterData/TaxProfilesTab'
import { resolveApiError } from './masterData/errorUtils'

const { Title, Text } = Typography

const MASTER_DATA_TAB_KEYS = [
  'party',
  'item',
  'contract',
  'tax-profile',
  'bindings',
  'sync',
  'bootstrap-import',
] as const

type MasterDataTabKey = typeof MASTER_DATA_TAB_KEYS[number]

const normalizeMasterDataTab = (rawValue: string | null): MasterDataTabKey => {
  const candidate = typeof rawValue === 'string' ? rawValue.trim() : ''
  return MASTER_DATA_TAB_KEYS.includes(candidate as MasterDataTabKey)
    ? candidate as MasterDataTabKey
    : 'party'
}

export function PoolMasterDataPage() {
  const { message } = AntApp.useApp()
  const searchParams = useMemo(() => new URLSearchParams(window.location.search), [])
  const [activeTab, setActiveTab] = useState<MasterDataTabKey>(
    normalizeMasterDataTab(searchParams.get('tab'))
  )
  const [registryEntries, setRegistryEntries] = useState<PoolMasterDataRegistryEntry[]>([])
  const remediationContextLines = useMemo(() => {
    const lines: string[] = []
    const entityType = searchParams.get('entityType')?.trim() ?? ''
    const canonicalId = searchParams.get('canonicalId')?.trim() ?? ''
    const databaseId = searchParams.get('databaseId')?.trim() ?? ''
    const role = searchParams.get('role')?.trim() ?? ''

    if (entityType || canonicalId || databaseId) {
      lines.push(
        `entity_type=${entityType || '-'} canonical_id=${canonicalId || '-'} database_id=${databaseId || '-'}`
      )
    }
    if (role) {
      lines.push(`role=${role}`)
    }
    return lines
  }, [searchParams])

  useEffect(() => {
    let cancelled = false
    void getPoolMasterDataRegistry()
      .then((response) => {
        if (!cancelled) {
          setRegistryEntries(response.entries)
        }
      })
      .catch((error) => {
        if (!cancelled) {
          const resolved = resolveApiError(error, 'Не удалось загрузить reusable-data registry.')
          message.error(resolved.message)
        }
      })
    return () => {
      cancelled = true
    }
  }, [message])

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
      {remediationContextLines.length > 0 && (
        <Alert
          type="info"
          showIcon
          message="Remediation Context"
          description={(
            <Space direction="vertical" size={0} data-testid="pool-master-data-remediation-context">
              <Text>Opened from pool run remediation transition.</Text>
              {remediationContextLines.map((line) => (
                <Text key={line} code>{line}</Text>
              ))}
            </Space>
          )}
        />
      )}
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(normalizeMasterDataTab(key))}
        items={[
          { key: 'party', label: 'Party', children: <PartiesTab /> },
          { key: 'item', label: 'Item', children: <ItemsTab /> },
          { key: 'contract', label: 'Contract', children: <ContractsTab /> },
          { key: 'tax-profile', label: 'TaxProfile', children: <TaxProfilesTab /> },
          { key: 'bindings', label: 'Bindings', children: <BindingsTab registryEntries={registryEntries} /> },
          { key: 'sync', label: 'Sync', children: <SyncStatusTab registryEntries={registryEntries} /> },
          {
            key: 'bootstrap-import',
            label: 'Bootstrap Import',
            children: <BootstrapImportTab registryEntries={registryEntries} />,
          },
        ]}
      />
    </Space>
  )
}
