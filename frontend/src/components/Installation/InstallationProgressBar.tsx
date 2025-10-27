import React from 'react'
import { Progress, Card, Statistic, Row, Col } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons'
import { InstallationProgress } from '../../types/installation'

interface InstallationProgressBarProps {
  progress: InstallationProgress | null
  loading: boolean
}

export const InstallationProgressBar: React.FC<InstallationProgressBarProps> = ({
  progress,
  loading,
}) => {
  if (!progress) {
    return <Card>No installation in progress</Card>
  }

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}m ${remainingSeconds}s`
  }

  return (
    <Card title="Installation Progress" loading={loading}>
      <Progress
        percent={Math.round(progress.progress_percent)}
        status={progress.failed > 0 ? 'exception' : 'active'}
        format={(percent) =>
          `${percent}% (${progress.completed + progress.failed}/${progress.total})`
        }
      />

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={6}>
          <Statistic
            title="Completed"
            value={progress.completed}
            prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="Failed"
            value={progress.failed}
            prefix={<CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="In Progress"
            value={progress.in_progress}
            prefix={<SyncOutlined spin style={{ color: '#1890ff' }} />}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="ETA"
            value={formatTime(progress.estimated_time_remaining)}
            prefix={<ClockCircleOutlined />}
          />
        </Col>
      </Row>
    </Card>
  )
}
