import { useState, useEffect } from 'react';
import { Card, Row, Col, Spin, message, Space } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { systemApi } from '../../api/endpoints/system';
import type { SystemHealthResponse } from '../../api/endpoints/system';
import { SystemOverview } from '../../components/SystemOverview';
import { ServiceStatusCard } from '../../components/ServiceStatusCard';

export const SystemStatus = () => {
    const [health, setHealth] = useState<SystemHealthResponse | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchHealth = async () => {
        try {
            const data = await systemApi.getHealth();
            setHealth(data);
        } catch (error) {
            console.error('Failed to fetch system health:', error);
            message.error('Не удалось загрузить статус системы');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHealth();

        // Auto-refresh every 15 seconds
        const interval = setInterval(() => {
            fetchHealth();
        }, 15000);

        return () => clearInterval(interval);
    }, []);

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: '50px' }}>
                <Spin size="large" tip="Загрузка статуса системы..." />
            </div>
        );
    }

    return (
        <div>
            <Space direction="vertical" style={{ width: '100%' }} size="large">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h1>Статус системы</h1>
                    <ReloadOutlined
                        spin={loading}
                        onClick={fetchHealth}
                        style={{ fontSize: 20, cursor: 'pointer' }}
                    />
                </div>

                {health && (
                    <>
                        <SystemOverview health={health} />

                        <Card title="Статус сервисов">
                            <Row gutter={[16, 16]}>
                                {health.services.map((service, index) => (
                                    <Col xs={24} sm={12} md={8} lg={6} key={index}>
                                        <ServiceStatusCard service={service} />
                                    </Col>
                                ))}
                            </Row>
                        </Card>
                    </>
                )}
            </Space>
        </div>
    );
};
