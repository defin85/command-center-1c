import { useCallback } from 'react'
import { Alert, Space } from 'antd'
import { useSearchParams } from 'react-router-dom'

import ServiceMeshTab from '../../components/service-mesh/ServiceMeshTab'
import { PageHeader, RouteButton, WorkspacePage } from '../../components/platform'

const ServiceMeshPage = () => {
  const [searchParams, setSearchParams] = useSearchParams()
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
          title="Service mesh"
          subtitle="Real-time topology and metrics inside the shared observability workspace."
          actions={(
            <Space wrap>
              <RouteButton
                to={selectedService ? `/system-status?service=${encodeURIComponent(selectedService)}` : '/system-status'}
              >
                Open system status
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
          message="Operation timeline context restored from the route state."
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
