import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, App, Button, Card, Input, Space, Tabs, Typography, Upload } from 'antd'
import { ReloadOutlined, SaveOutlined, UploadOutlined } from '@ant-design/icons'

import {
  getDriverCatalog,
  importItsCatalog,
  listDriverCatalogs,
  updateDriverCatalog,
  type DriverCatalogListItem,
} from '../../api/driverCatalogs'

const { Title, Text } = Typography
const { TextArea } = Input

interface CatalogState {
  raw: string
  loading: boolean
  error: string | null
}

const DEFAULT_CATALOG = JSON.stringify({
  version: 'unknown',
  source: '',
  commands: [],
}, null, 2)

export function DriverCatalogsPage() {
  const { message } = App.useApp()
  const [drivers, setDrivers] = useState<DriverCatalogListItem[]>([])
  const [activeDriver, setActiveDriver] = useState<string>('cli')
  const [catalogs, setCatalogs] = useState<Record<string, CatalogState>>({})
  const [listError, setListError] = useState<string | null>(null)
  const [listLoading, setListLoading] = useState(false)

  const fetchDrivers = useCallback(async () => {
    setListLoading(true)
    setListError(null)
    try {
      const response = await listDriverCatalogs()
      setDrivers(response.items ?? [])
      if (response.items?.length && !response.items.some((item) => item.driver === activeDriver)) {
        setActiveDriver(response.items[0].driver)
      }
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to load driver catalogs'
      setListError(text)
    } finally {
      setListLoading(false)
    }
  }, [activeDriver])

  const fetchCatalog = useCallback(async (driver: string) => {
    setCatalogs((prev) => ({
      ...prev,
      [driver]: {
        raw: prev[driver]?.raw ?? DEFAULT_CATALOG,
        loading: true,
        error: null,
      },
    }))
    try {
      const response = await getDriverCatalog(driver)
      const raw = JSON.stringify(response.catalog ?? {}, null, 2)
      setCatalogs((prev) => ({
        ...prev,
        [driver]: { raw, loading: false, error: null },
      }))
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to load catalog'
      setCatalogs((prev) => ({
        ...prev,
        [driver]: { raw: prev[driver]?.raw ?? DEFAULT_CATALOG, loading: false, error: text },
      }))
    }
  }, [])

  useEffect(() => {
    void fetchDrivers()
  }, [fetchDrivers])

  useEffect(() => {
    if (!activeDriver) {
      return
    }
    void fetchCatalog(activeDriver)
  }, [activeDriver, fetchCatalog])

  const activeMeta = useMemo(
    () => drivers.find((item) => item.driver === activeDriver),
    [drivers, activeDriver]
  )

  const activeCatalog = catalogs[activeDriver]

  const handleSave = async () => {
    if (!activeDriver) {
      return
    }
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(activeCatalog?.raw ?? '')
    } catch (_err) {
      message.error('Invalid JSON: cannot parse catalog')
      return
    }
    try {
      await updateDriverCatalog({ driver: activeDriver, catalog: parsed })
      message.success('Catalog updated')
      void fetchDrivers()
      void fetchCatalog(activeDriver)
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to update catalog'
      message.error(text)
    }
  }

  const handleReload = async () => {
    if (!activeDriver) {
      return
    }
    await fetchCatalog(activeDriver)
  }

  const handleItsUpload = async (file: File) => {
    let payload: Record<string, unknown>
    try {
      const text = await file.text()
      payload = JSON.parse(text)
    } catch (_err) {
      message.error('Invalid ITS JSON file')
      return false
    }
    try {
      const response = await importItsCatalog({ driver: activeDriver, its_payload: payload })
      const raw = JSON.stringify(response.catalog ?? {}, null, 2)
      setCatalogs((prev) => ({
        ...prev,
        [activeDriver]: { raw, loading: false, error: null },
      }))
      message.success('ITS catalog imported')
      void fetchDrivers()
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to import ITS catalog'
      message.error(text)
    }
    return false
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>Driver Catalogs</Title>
          <Text type="secondary">Upload, inspect, and edit driver catalogs (staff-only).</Text>
        </div>
        <Button onClick={fetchDrivers} loading={listLoading} icon={<ReloadOutlined />}>
          Refresh
        </Button>
      </div>

      {listError && (
        <Alert type="warning" message="Failed to load driver catalogs" description={listError} showIcon />
      )}

      <Alert
        type="info"
        showIcon
        message="ITS import"
        description="Use scripts/dev/its-scrape.py to export ITS JSON, then upload it here for CLI catalogs."
      />

      <Tabs
        activeKey={activeDriver}
        onChange={setActiveDriver}
        items={drivers.map((driver) => ({
          key: driver.driver,
          label: `${driver.driver.toUpperCase()} (${driver.command_count})`,
        }))}
      />

      {activeDriver && (
        <Card
          size="small"
          title={`${activeDriver.toUpperCase()} Catalog`}
          extra={(
            <Space>
              {activeDriver === 'cli' && (
                <Upload
                  accept=".json"
                  showUploadList={false}
                  beforeUpload={handleItsUpload}
                >
                  <Button icon={<UploadOutlined />}>Import ITS JSON</Button>
                </Upload>
              )}
              <Button icon={<ReloadOutlined />} onClick={handleReload} disabled={activeCatalog?.loading}>
                Reload
              </Button>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={handleSave}
                disabled={activeCatalog?.loading}
              >
                Save
              </Button>
            </Space>
          )}
        >
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Text type="secondary">Version: {activeMeta?.version ?? 'unknown'}</Text>
            <Text type="secondary">Source: {activeMeta?.source ?? '-'}</Text>
            {activeCatalog?.error && (
              <Alert type="warning" showIcon message="Catalog error" description={activeCatalog.error} />
            )}
            <TextArea
              rows={18}
              value={activeCatalog?.raw ?? DEFAULT_CATALOG}
              onChange={(event) => {
                const raw = event.target.value
                setCatalogs((prev) => ({
                  ...prev,
                  [activeDriver]: {
                    raw,
                    loading: false,
                    error: prev[activeDriver]?.error ?? null,
                  },
                }))
              }}
            />
          </Space>
        </Card>
      )}
    </Space>
  )
}

export default DriverCatalogsPage
