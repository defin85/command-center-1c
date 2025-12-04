import { useState, useEffect, useCallback } from 'react';
import { Card, Row, Col, Spin, Space, App } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { systemApi } from '../../api/adapters/system';
import type { SystemHealthResponse } from '../../api/adapters/system';
import { SystemOverview } from '../../components/SystemOverview';
import { ServiceStatusCard } from '../../components/ServiceStatusCard';

export const SystemStatus = () => {
    const { message } = App.useApp();
    const [health, setHealth] = useState<SystemHealthResponse | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchHealth = useCallback(async () => {
        try {
            const data = await systemApi.getHealth();
            setHealth(data);
        } catch (error) {
            console.error('Failed to fetch system health:', error);
            message.error('Не удалось загрузить статус системы');
        } finally {
            setLoading(false);
        }
    }, [message]);

    useEffect(() => {
        fetchHealth();

        // Auto-refresh every 15 seconds
        const interval = setInterval(() => {
            fetchHealth();
        }, 15000);

        return () => clearInterval(interval);
    }, [fetchHealth]);

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: '50px' }}>
                <Spin size="large">
                    <div style={{ padding: '20px' }}>Загрузка статуса системы...</div>
                </Spin>
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
