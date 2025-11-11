/**
 * System overview component with health statistics
 */

import { Card, Row, Col, Statistic, Progress, Space, Typography, Alert } from 'antd';
import {
    CheckCircleOutlined,
    CloseCircleOutlined,
    ExclamationCircleOutlined,
    ThunderboltOutlined,
} from '@ant-design/icons';
import type { SystemHealthResponse } from '@/api/endpoints/system';

const { Title, Text } = Typography;

interface SystemOverviewProps {
    health: SystemHealthResponse;
}

export const SystemOverview: React.FC<SystemOverviewProps> = ({ health }) => {
    const { statistics, overall_status } = health;

    const getOverallStatusConfig = () => {
        switch (overall_status) {
            case 'healthy':
                return {
                    color: '#52c41a',
                    icon: <CheckCircleOutlined />,
                    text: 'Система работает нормально',
                    type: 'success' as const,
                };
            case 'degraded':
                return {
                    color: '#faad14',
                    icon: <ExclamationCircleOutlined />,
                    text: 'Обнаружены проблемы с некритичными сервисами',
                    type: 'warning' as const,
                };
            case 'critical':
                return {
                    color: '#ff4d4f',
                    icon: <CloseCircleOutlined />,
                    text: 'Критическая ошибка! Некоторые сервисы недоступны',
                    type: 'error' as const,
                };
            default:
                return {
                    color: '#d9d9d9',
                    icon: <ThunderboltOutlined />,
                    text: 'Статус неизвестен',
                    type: 'info' as const,
                };
        }
    };

    const statusConfig = getOverallStatusConfig();
    const healthPercentage = Math.round((statistics.online / statistics.total) * 100);

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
                            title="Всего сервисов"
                            value={statistics.total}
                            prefix={<ThunderboltOutlined />}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} md={6}>
                    <Card>
                        <Statistic
                            title="Работают"
                            value={statistics.online}
                            valueStyle={{ color: '#52c41a' }}
                            prefix={<CheckCircleOutlined />}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} md={6}>
                    <Card>
                        <Statistic
                            title="Недоступны"
                            value={statistics.offline}
                            valueStyle={{ color: '#ff4d4f' }}
                            prefix={<CloseCircleOutlined />}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} md={6}>
                    <Card>
                        <Statistic
                            title="Проблемы"
                            value={statistics.degraded}
                            valueStyle={{ color: '#faad14' }}
                            prefix={<ExclamationCircleOutlined />}
                        />
                    </Card>
                </Col>
            </Row>

            <Card>
                <Space direction="vertical" style={{ width: '100%' }}>
                    <Title level={5}>Общее состояние системы</Title>
                    <Progress
                        percent={healthPercentage}
                        strokeColor={{
                            '0%': healthPercentage > 80 ? '#52c41a' : '#ff4d4f',
                            '100%': healthPercentage > 80 ? '#52c41a' : '#faad14',
                        }}
                        status={healthPercentage === 100 ? 'success' : 'active'}
                    />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        Последнее обновление: {new Date(health.timestamp).toLocaleString('ru-RU')}
                    </Text>
                </Space>
            </Card>
        </Space>
    );
};
