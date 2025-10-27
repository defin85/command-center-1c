import React, { useState } from 'react'
import { Layout, Typography, Space, Divider } from 'antd'
import { BatchInstallButton } from '../../components/Installation/BatchInstallButton'
import { InstallationProgressBar } from '../../components/Installation/InstallationProgressBar'
import { InstallationStatusTable } from '../../components/Installation/InstallationStatusTable'
import { useInstallationProgress } from '../../hooks/useInstallationProgress'

const { Content } = Layout
const { Title } = Typography

export const InstallationMonitorPage: React.FC = () => {
  const [taskId, setTaskId] = useState<string | null>(null)
  const { progress, loading } = useInstallationProgress({ taskId, enabled: !!taskId })

  return (
    <Layout style={{ padding: '24px' }}>
      <Content>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2}>OData Extension Installation</Title>
            <p>Monitor and manage OData extension installations across all databases</p>
          </div>

          <BatchInstallButton onStarted={setTaskId} />

          {taskId && (
            <>
              <Divider />
              <InstallationProgressBar progress={progress} loading={loading} />
            </>
          )}

          <Divider />

          <div>
            <Title level={3}>Installation History</Title>
            <InstallationStatusTable />
          </div>
        </Space>
      </Content>
    </Layout>
  )
}
