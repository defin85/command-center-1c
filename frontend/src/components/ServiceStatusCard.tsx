/**
 * Service status card component
 */

import { Card, Badge, Typography, Space, Tag } from 'antd';
import {
    CheckCircleOutlined,
    CloseCircleOutlined,
    ExclamationCircleOutlined,
} from '@ant-design/icons';
import type { ServiceHealth } from '@/api/generated/model';

const { Text } = Typography;

interface ServiceStatusCardProps {
    service: ServiceHealth;
}

export const ServiceStatusCard: React.FC<ServiceStatusCardProps> = ({ service }) => {
    const getStatusColor = (status: string) => {
        switch (status) {
            case 'online':
                return 'success';
            case 'offline':
                return 'error';
            case 'degraded':
                return 'warning';
            default:
                return 'default';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'online':
                return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
            case 'offline':
                return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
            case 'degraded':
                return <ExclamationCircleOutlined style={{ color: '#faad14' }} />;
            default:
                return null;
        }
    };

    return (
        <Card
            size="small"
            style={{
                borderLeft: `4px solid ${service.status === 'online'
                    ? '#52c41a'
                    : service.status === 'offline'
                        ? '#ff4d4f'
                        : '#faad14'
                    }`
            }}
        >
            <Space direction="vertical" style={{ width: '100%' }} size="small">
                <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Space>
                        {getStatusIcon(service.status)}
                        <Text strong>{service.name}</Text>
                    </Space>
                    <Badge status={getStatusColor(service.status)} text={service.status} />
                </Space>

                <Space size="small">
                    <Tag color="blue">{service.type}</Tag>
                    {service.response_time_ms != null && (
                        <Tag color="green">{service.response_time_ms}ms</Tag>
                    )}
                </Space>

                {'url' in service && service.url && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        <a href={service.url} target="_blank" rel="noreferrer">
                            {service.url}
                        </a>
                    </Text>
                )}

                {service.details && Object.keys(service.details).length > 0 && (
                    <div style={{ marginTop: 8 }}>
                        {'error' in service.details && service.details.error != null && (
                            <Text type="danger" style={{ fontSize: 12 }}>
                                Error: {String(service.details.error)}
                            </Text>
                        )}
                        {'version' in service.details && service.details.version != null && (
                            <Text type="secondary" style={{ fontSize: 12 }}>
                                v{String(service.details.version)}
                            </Text>
                        )}
                    </div>
                )}
            </Space>
        </Card>
    );
};
