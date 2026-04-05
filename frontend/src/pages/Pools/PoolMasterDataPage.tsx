import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Alert, App as AntApp, Space, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'

import { getPoolMasterDataRegistry, type PoolMasterDataRegistryEntry } from '../../api/intercompanyPools'
import {
  EntityDetails,
  EntityList,
  MasterDetailShell,
  PageHeader,
  WorkspacePage,
} from '../../components/platform'
import { BindingsTab } from './masterData/BindingsTab'
import { BootstrapImportTab } from './masterData/BootstrapImportTab'
import { ContractsTab } from './masterData/ContractsTab'
import { GLAccountsTab } from './masterData/GLAccountsTab'
import { GLAccountSetsTab } from './masterData/GLAccountSetsTab'
import { ItemsTab } from './masterData/ItemsTab'
import { PartiesTab } from './masterData/PartiesTab'
import { SyncStatusTab } from './masterData/SyncStatusTab'
import { TaxProfilesTab } from './masterData/TaxProfilesTab'
import { resolveApiError } from './masterData/errorUtils'

const { Text } = Typography

const MASTER_DATA_TAB_KEYS = [
  'party',
  'item',
  'contract',
  'tax-profile',
  'gl-account',
  'gl-account-set',
  'bindings',
  'sync',
  'bootstrap-import',
] as const

type MasterDataTabKey = typeof MASTER_DATA_TAB_KEYS[number]

type MasterDataZoneDefinition = {
  key: MasterDataTabKey
  label: string
  description: string
  render: (registryEntries: PoolMasterDataRegistryEntry[]) => ReactNode
}

const MASTER_DATA_ZONES: MasterDataZoneDefinition[] = [
  {
    key: 'party',
    label: 'Party',
    description: 'Canonical party records and role-aware authoring.',
    render: () => <PartiesTab />,
  },
  {
    key: 'item',
    label: 'Item',
    description: 'Reusable item catalog and mapping coverage.',
    render: () => <ItemsTab />,
  },
  {
    key: 'contract',
    label: 'Contract',
    description: 'Contract records and ownership-aware bindings.',
    render: () => <ContractsTab />,
  },
  {
    key: 'tax-profile',
    label: 'Tax Profile',
    description: 'Tax profile references for reusable pool execution.',
    render: () => <TaxProfilesTab />,
  },
  {
    key: 'gl-account',
    label: 'GL Account',
    description: 'Chart-scoped reusable accounts with explicit compatibility class.',
    render: (registryEntries) => <GLAccountsTab registryEntries={registryEntries} />,
  },
  {
    key: 'gl-account-set',
    label: 'GL Account Set',
    description: 'Draft, publish and immutable revision lifecycle for reusable account profiles.',
    render: (registryEntries) => <GLAccountSetsTab registryEntries={registryEntries} />,
  },
  {
    key: 'bindings',
    label: 'Bindings',
    description: 'Registry-aware canonical bindings across target databases.',
    render: (registryEntries) => <BindingsTab registryEntries={registryEntries} />,
  },
  {
    key: 'sync',
    label: 'Sync',
    description: 'Operator-facing sync diagnostics and conflict actions.',
    render: (registryEntries) => <SyncStatusTab registryEntries={registryEntries} />,
  },
  {
    key: 'bootstrap-import',
    label: 'Bootstrap Import',
    description: 'Bootstrap-capable import flows for supported reusable entities.',
    render: (registryEntries) => <BootstrapImportTab registryEntries={registryEntries} />,
  },
]

const DEFAULT_MASTER_DATA_ZONE = MASTER_DATA_ZONES[0]

const normalizeMasterDataTab = (rawValue: string | null): MasterDataTabKey => {
  const candidate = typeof rawValue === 'string' ? rawValue.trim() : ''
  return MASTER_DATA_TAB_KEYS.includes(candidate as MasterDataTabKey)
    ? candidate as MasterDataTabKey
    : 'party'
}

const buildZoneButtonStyle = (selected: boolean) => ({
  width: '100%',
  border: selected ? '1px solid #91caff' : '1px solid #f0f0f0',
  borderInlineStart: selected ? '4px solid #1677ff' : '4px solid transparent',
  borderRadius: 8,
  padding: '12px',
  background: selected ? '#e6f4ff' : '#fff',
  boxShadow: selected ? '0 1px 2px rgba(22, 119, 255, 0.12)' : 'none',
  textAlign: 'left' as const,
  cursor: 'pointer',
})

export function PoolMasterDataPage() {
  const { message } = AntApp.useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const activeTabFromUrl = normalizeMasterDataTab(searchParams.get('tab'))
  const detailOpenFromUrl = searchParams.get('detail') === '1'
  const [activeTab, setActiveTab] = useState<MasterDataTabKey>(activeTabFromUrl)
  const [isDetailOpen, setIsDetailOpen] = useState(detailOpenFromUrl)
  const [registryEntries, setRegistryEntries] = useState<PoolMasterDataRegistryEntry[]>([])

  useEffect(() => {
    setActiveTab((current) => (current === activeTabFromUrl ? current : activeTabFromUrl))
  }, [activeTabFromUrl])

  useEffect(() => {
    setIsDetailOpen((current) => (current === detailOpenFromUrl ? current : detailOpenFromUrl))
  }, [detailOpenFromUrl])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)

    next.set('tab', activeTab)

    if (isDetailOpen) {
      next.set('detail', '1')
    } else {
      next.delete('detail')
    }

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(
        next,
        routeUpdateModeRef.current === 'replace'
          ? { replace: true }
          : undefined
      )
    }
    routeUpdateModeRef.current = 'replace'
  }, [activeTab, isDetailOpen, searchParams, setSearchParams])

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

  const selectedZone = useMemo(
    () => MASTER_DATA_ZONES.find((zone) => zone.key === activeTab) ?? DEFAULT_MASTER_DATA_ZONE,
    [activeTab]
  )

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="Pool Master Data"
          subtitle="Canonical multi-zone workspace for reusable master-data authoring, bindings, diagnostics, and bootstrap flows."
        />
      )}
    >
      <Alert
        type="info"
        showIcon
        message="Route-owned workspace shell"
        description={(
          <Space direction="vertical" size={4}>
            <Text>
              Select a workspace zone from the catalog and keep the active zone addressable through the route.
              Reusable account zones now live inside the same canonical platform shell.
            </Text>
            <Text type="secondary">
              Current zone: {selectedZone.label}
            </Text>
          </Space>
        )}
      />

      {remediationContextLines.length > 0 ? (
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
      ) : null}

      <MasterDetailShell
        detailOpen={isDetailOpen}
        onCloseDetail={() => {
          routeUpdateModeRef.current = 'push'
          setIsDetailOpen(false)
        }}
        detailDrawerTitle={`${selectedZone.label} · pool master data`}
        list={(
          <EntityList
            title="Workspace Zones"
            emptyDescription="Master-data zones are not available."
            dataSource={MASTER_DATA_ZONES}
            renderItem={(zone) => {
              const selected = zone.key === activeTab
              return (
                <button
                  key={zone.key}
                  type="button"
                  onClick={() => {
                    routeUpdateModeRef.current = 'push'
                    setActiveTab(zone.key)
                    setIsDetailOpen(true)
                  }}
                  aria-label={`Open ${zone.label} zone`}
                  aria-pressed={selected}
                  style={buildZoneButtonStyle(selected)}
                >
                  <Space direction="vertical" size={2} style={{ width: '100%' }}>
                    <Text strong>{zone.label}</Text>
                    <Text type="secondary">{zone.description}</Text>
                  </Space>
                </button>
              )
            }}
          />
        )}
        detail={(
          <EntityDetails
            title={selectedZone.label}
            empty={false}
            extra={<Text type="secondary">{selectedZone.description}</Text>}
          >
            {selectedZone.render(registryEntries)}
          </EntityDetails>
        )}
      />
    </WorkspacePage>
  )
}
