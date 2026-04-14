import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Alert, App as AntApp, Space, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'

import { usePoolsTranslation } from '../../i18n'
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
import { DedupeReviewTab } from './masterData/DedupeReviewTab'
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
  'dedupe-review',
] as const

type MasterDataTabKey = typeof MASTER_DATA_TAB_KEYS[number]

type MasterDataZoneDefinition = {
  key: MasterDataTabKey
  label: string
  description: string
  render: (registryEntries: PoolMasterDataRegistryEntry[]) => ReactNode
}

const buildMasterDataZones = (
  t: (key: string, options?: Record<string, unknown>) => string
): MasterDataZoneDefinition[] => [
  {
    key: 'party',
    label: t('masterData.zones.party.label'),
    description: t('masterData.zones.party.description'),
    render: () => <PartiesTab />,
  },
  {
    key: 'item',
    label: t('masterData.zones.item.label'),
    description: t('masterData.zones.item.description'),
    render: () => <ItemsTab />,
  },
  {
    key: 'contract',
    label: t('masterData.zones.contract.label'),
    description: t('masterData.zones.contract.description'),
    render: () => <ContractsTab />,
  },
  {
    key: 'tax-profile',
    label: t('masterData.zones.taxProfile.label'),
    description: t('masterData.zones.taxProfile.description'),
    render: () => <TaxProfilesTab />,
  },
  {
    key: 'gl-account',
    label: t('masterData.zones.glAccount.label'),
    description: t('masterData.zones.glAccount.description'),
    render: (registryEntries) => <GLAccountsTab registryEntries={registryEntries} />,
  },
  {
    key: 'gl-account-set',
    label: t('masterData.zones.glAccountSet.label'),
    description: t('masterData.zones.glAccountSet.description'),
    render: (registryEntries) => <GLAccountSetsTab registryEntries={registryEntries} />,
  },
  {
    key: 'bindings',
    label: t('masterData.zones.bindings.label'),
    description: t('masterData.zones.bindings.description'),
    render: (registryEntries) => <BindingsTab registryEntries={registryEntries} />,
  },
  {
    key: 'sync',
    label: t('masterData.zones.sync.label'),
    description: t('masterData.zones.sync.description'),
    render: (registryEntries) => <SyncStatusTab registryEntries={registryEntries} />,
  },
  {
    key: 'bootstrap-import',
    label: t('masterData.zones.bootstrapImport.label'),
    description: t('masterData.zones.bootstrapImport.description'),
    render: (registryEntries) => <BootstrapImportTab registryEntries={registryEntries} />,
  },
  {
    key: 'dedupe-review',
    label: t('masterData.zones.dedupeReview.label'),
    description: t('masterData.zones.dedupeReview.description'),
    render: (registryEntries) => <DedupeReviewTab registryEntries={registryEntries} />,
  },
]

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
  const { t, ready } = usePoolsTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const activeTabFromUrl = normalizeMasterDataTab(searchParams.get('tab'))
  const detailOpenFromUrl = searchParams.get('detail') === '1'
  const [activeTab, setActiveTab] = useState<MasterDataTabKey>(activeTabFromUrl)
  const [isDetailOpen, setIsDetailOpen] = useState(detailOpenFromUrl)
  const [registryEntries, setRegistryEntries] = useState<PoolMasterDataRegistryEntry[]>([])
  const masterDataZones = buildMasterDataZones(t)

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
    const clusterId = searchParams.get('clusterId')?.trim() ?? ''
    const reviewItemId = searchParams.get('reviewItemId')?.trim() ?? ''
    const role = searchParams.get('role')?.trim() ?? ''

    if (entityType || canonicalId || databaseId) {
      lines.push(
        `entity_type=${entityType || '-'} canonical_id=${canonicalId || '-'} database_id=${databaseId || '-'}`
      )
    }
    if (clusterId || reviewItemId) {
      lines.push(`cluster_id=${clusterId || '-'} review_item_id=${reviewItemId || '-'}`)
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
          const resolved = resolveApiError(error, t('masterData.messages.failedToLoadRegistry'))
          message.error(resolved.message)
        }
      })

    return () => {
      cancelled = true
    }
  }, [message, t])

  const selectedZone = useMemo(
    () => masterDataZones.find((zone) => zone.key === activeTab) ?? masterDataZones[0],
    [activeTab, masterDataZones]
  )

  if (!ready) {
    return null
  }

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t('masterData.page.title')}
          subtitle={t('masterData.page.subtitle')}
        />
      )}
    >
      <Alert
        type="info"
        showIcon
        message={t('masterData.alerts.routeOwnedShellTitle')}
        description={(
          <Space direction="vertical" size={4}>
            <Text>{t('masterData.alerts.routeOwnedShellDescription')}</Text>
            <Text type="secondary">
              {t('masterData.alerts.currentZone', { zone: selectedZone.label })}
            </Text>
          </Space>
        )}
      />

      {remediationContextLines.length > 0 ? (
        <Alert
          type="info"
          showIcon
          message={t('masterData.alerts.remediationContextTitle')}
          description={(
            <Space direction="vertical" size={0} data-testid="pool-master-data-remediation-context">
              <Text>{t('masterData.alerts.remediationContextOpenedFromRun')}</Text>
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
        detailDrawerTitle={t('masterData.page.detailDrawerTitle', { zone: selectedZone.label })}
        list={(
          <EntityList
            title={t('masterData.list.title')}
            emptyDescription={t('masterData.list.emptyDescription')}
            dataSource={masterDataZones}
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
                  aria-label={t('masterData.list.openZone', { zone: zone.label })}
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
