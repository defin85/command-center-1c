/**
 * System overview component with health statistics
 */

import { Card, Row, Col, Statistic, Progress, Space, Typography, Alert } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import type { SystemHealthResponse } from '@/api/generated/model'
import { useLocaleFormatters, useSystemStatusTranslation } from '@/i18n'

const { Title, Text } = Typography

interface SystemOverviewProps {
  health: SystemHealthResponse
}

export const SystemOverview: React.FC<SystemOverviewProps> = ({ health }) => {
  const { t } = useSystemStatusTranslation()
  const formatters = useLocaleFormatters()
  const { overall_status } = health

  const statistics = health.statistics ?? {
    total: health.services?.length ?? 0,
    online: health.services?.filter((service) => service.status === 'online').length ?? 0,
    offline: health.services?.filter((service) => service.status === 'offline').length ?? 0,
    degraded: health.services?.filter((service) => service.status === 'degraded').length ?? 0,
  }

  const getOverallStatusConfig = () => {
    switch (overall_status) {
      case 'healthy':
        return {
          color: '#52c41a',
          icon: <CheckCircleOutlined />,
          text: t(($) => $.overview.healthy),
          type: 'success' as const,
        }
      case 'degraded':
        return {
          color: '#faad14',
          icon: <ExclamationCircleOutlined />,
          text: t(($) => $.overview.degraded),
          type: 'warning' as const,
        }
      case 'critical':
        return {
          color: '#ff4d4f',
          icon: <CloseCircleOutlined />,
          text: t(($) => $.overview.critical),
          type: 'error' as const,
        }
      default:
        return {
          color: '#d9d9d9',
          icon: <ThunderboltOutlined />,
          text: t(($) => $.overview.unknown),
          type: 'info' as const,
        }
    }
  }

  const statusConfig = getOverallStatusConfig()
  const healthPercentage = statistics.total > 0
    ? Math.round((statistics.online / statistics.total) * 100)
    : 0

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      {overall_status !== 'healthy' && (
        <Alert
          message={statusConfig.text}
          type={statusConfig.type}
          icon={statusConfig.icon}
          showIcon
          banner
        />
      )}

      <Row gutter={16}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t(($) => $.overview.totalServices)}
              value={statistics.total}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t(($) => $.overview.onlineServices)}
              value={statistics.online}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t(($) => $.overview.offlineServices)}
              value={statistics.offline}
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t(($) => $.overview.degradedServices)}
              value={statistics.degraded}
              valueStyle={{ color: '#faad14' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Title level={5}>{t(($) => $.overview.overall)}</Title>
          <Progress
            percent={healthPercentage}
            strokeColor={{
              '0%': healthPercentage > 80 ? '#52c41a' : '#ff4d4f',
              '100%': healthPercentage > 80 ? '#52c41a' : '#faad14',
            }}
            status={healthPercentage === 100 ? 'success' : 'active'}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t(($) => $.overview.lastUpdated, {
              value: formatters.dateTime(health.timestamp, { fallback: '—' }),
            })}
          </Text>
        </Space>
      </Card>
    </Space>
  )
}
