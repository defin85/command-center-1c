/**
 * Statistics cards component for Dashboard.
 *
 * Displays 3 KPI cards: Total Operations, Active Databases, Success Rate.
 */

import { Row, Col, Card, Statistic, Skeleton } from 'antd'
import {
  BarChartOutlined,
  DatabaseOutlined,
  CheckCircleOutlined,
  ArrowUpOutlined,
} from '@ant-design/icons'
import type { OperationsStats, DatabasesStats } from '../types'
import { useDashboardTranslation, useLocaleFormatters } from '../../../i18n'

export interface StatisticsCardsProps {
  operations: OperationsStats
  databases: DatabasesStats
  loading?: boolean
}

/**
 * Get color for success rate based on threshold.
 * Green (>90%), Yellow (70-90%), Red (<70%)
 */
const getSuccessRateColor = (rate: number): string => {
  if (rate >= 90) return '#52c41a' // green
  if (rate >= 70) return '#faad14' // yellow
  return '#f5222d' // red
}

/**
 * StatisticsCards - KPI cards row for dashboard
 */
export const StatisticsCards = ({
  operations,
  databases,
  loading = false,
}: StatisticsCardsProps) => {
  const { t } = useDashboardTranslation()
  const formatters = useLocaleFormatters()

  if (loading) {
    return (
      <Row gutter={16}>
        {[1, 2, 3].map((key) => (
          <Col span={8} key={key}>
            <Card>
              <Skeleton active paragraph={{ rows: 1 }} />
            </Card>
          </Col>
        ))}
      </Row>
    )
  }

  return (
    <Row gutter={[16, 16]}>
      {/* Total Operations */}
      <Col xs={24} sm={12} md={8}>
        <Card>
          <Statistic
            title={t(($) => $.statistics.totalOperations)}
            value={formatters.number(operations.total)}
            prefix={<BarChartOutlined />}
            suffix={
              operations.todayCount > 0 ? (
                <span style={{ fontSize: 14, color: '#52c41a' }}>
                  <ArrowUpOutlined /> +{formatters.number(operations.todayCount)} {t(($) => $.statistics.today)}
                </span>
              ) : undefined
            }
          />
        </Card>
      </Col>

      {/* Active Databases */}
      <Col xs={24} sm={12} md={8}>
        <Card>
          <Statistic
            title={t(($) => $.statistics.activeDatabases)}
            value={formatters.number(databases.active)}
            prefix={<DatabaseOutlined />}
            suffix={
              <span style={{ fontSize: 14, color: '#8c8c8c' }}>
                / {formatters.number(databases.total)}
                {databases.locked > 0 && (
                  <span style={{ marginLeft: 8, color: '#faad14' }}>
                    {formatters.number(databases.locked)} {t(($) => $.statistics.locked)}
                  </span>
                )}
              </span>
            }
          />
        </Card>
      </Col>

      {/* Success Rate */}
      <Col xs={24} sm={24} md={8}>
        <Card>
          <Statistic
            title={t(($) => $.statistics.successRate)}
            value={formatters.number(operations.successRate, {
              minimumFractionDigits: 1,
              maximumFractionDigits: 1,
            })}
            prefix={<CheckCircleOutlined />}
            suffix="%"
            valueStyle={{ color: getSuccessRateColor(operations.successRate) }}
          />
        </Card>
      </Col>
    </Row>
  )
}
