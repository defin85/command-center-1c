import { useCallback } from 'react'
import { Alert, Space } from 'antd'
import { useSearchParams } from 'react-router-dom'

import ServiceMeshTab from '../../components/service-mesh/ServiceMeshTab'
import { PageHeader, RouteButton, WorkspacePage } from '../../components/platform'
import { useServiceMeshTranslation } from '../../i18n'

const ServiceMeshPage = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const { t } = useServiceMeshTranslation()
  const selectedService = (searchParams.get('service') || '').trim() || null
  const selectedOperationId = (searchParams.get('operation') || '').trim() || null

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(updates).forEach(([key, value]) => {
        if (!value) {
          next.delete(key)
        } else {
          next.set(key, value)
        }
      })
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t(($) => $.page.title)}
          subtitle={t(($) => $.page.subtitle)}
          actions={(
            <Space wrap>
              <RouteButton
                to={selectedService ? `/system-status?service=${encodeURIComponent(selectedService)}` : '/system-status'}
              >
                {t(($) => $.page.openSystemStatus)}
              </RouteButton>
            </Space>
          )}
        />
      )}
    >
      {selectedOperationId ? (
        <Alert
          type="info"
          showIcon
          message={t(($) => $.page.restoredOperationContext)}
        />
      ) : null}
      <ServiceMeshTab
        selectedService={selectedService}
        onSelectedServiceChange={(service) => updateSearchParams({ service })}
        selectedOperationId={selectedOperationId}
        onSelectedOperationIdChange={(operationId) => updateSearchParams({ operation: operationId })}
      />
    </WorkspacePage>
  )
}

export default ServiceMeshPage
