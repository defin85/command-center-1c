/**
 * Service Mesh Page.
 *
 * Full-page layout for service mesh monitoring with
 * real-time visualization and metrics.
 */
import React from 'react'
import { Typography } from 'antd'
import ServiceMeshTab from '../../components/service-mesh/ServiceMeshTab'
import './ServiceMeshPage.css'

const { Title } = Typography

const ServiceMeshPage: React.FC = () => {
  return (
    <div className="service-mesh-page">
      <div className="service-mesh-page__header">
        <Title level={3} className="service-mesh-page__title">
          Service Mesh Monitor
        </Title>
        <span className="service-mesh-page__subtitle">
          Real-time visualization of microservice topology and metrics
        </span>
      </div>

      <ServiceMeshTab />
    </div>
  )
}

export default ServiceMeshPage
