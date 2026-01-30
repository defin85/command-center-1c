import { useMemo, useRef, useState, useEffect, useCallback } from 'react';
import { Alert, Button, Card, Row, Col, Spin, Space, App } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import axios from 'axios';
import { getV2 } from '@/api/generated/v2/v2';
import type { SystemHealthResponse } from '@/api/generated/model';
import { SystemOverview } from '../../components/SystemOverview';
import { ServiceStatusCard } from '../../components/ServiceStatusCard';
import { KNOWN_SERVICES } from '../../constants/services';

const api = getV2();

export const SystemStatus = () => {
    const { message } = App.useApp();
    const [health, setHealth] = useState<SystemHealthResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const hasLoadedOnceRef = useRef(false);
    const pollCooldownUntilMsRef = useRef<number>(0);
    const lastRateLimitNoticeAtMsRef = useRef<number>(0);

    const fetchHealth = useCallback(async (opts?: { silent?: boolean; reason?: 'initial' | 'manual' | 'auto' }) => {
        try {
            if (!opts?.silent) {
                if (hasLoadedOnceRef.current) setRefreshing(true);
                else setLoading(true);
            }
            setError(null);
            const data = await api.getSystemHealth();
            setHealth(data);
        } catch (error) {
            console.error('Failed to fetch system health:', error);
            if (axios.isAxiosError(error) && error.response?.status === 429) {
                const retryAfterHeader = error.response.headers?.['retry-after'];
                const retryAfterSeconds = typeof retryAfterHeader === 'string' ? Number(retryAfterHeader) : NaN;
                const cooldownMs = Number.isFinite(retryAfterSeconds) ? retryAfterSeconds * 1000 : 30_000;
                pollCooldownUntilMsRef.current = Date.now() + cooldownMs;

                setError(`Слишком много запросов (429). Повтор через ~${Math.ceil(cooldownMs / 1000)}с`);

                const now = Date.now();
                if (!opts?.silent && now - lastRateLimitNoticeAtMsRef.current > 10_000) {
                    lastRateLimitNoticeAtMsRef.current = now;
                    message.warning('Сработал rate limit API Gateway (429), замедляю авто-обновление');
                }
                return;
            }

            setError('Не удалось загрузить статус системы');
            if (!opts?.silent) {
                message.error('Не удалось загрузить статус системы');
            }
        } finally {
            setLoading(false);
            setRefreshing(false);
            hasLoadedOnceRef.current = true;
        }
    }, [message]);

    const servicesSorted = useMemo(() => {
        const services = health?.services ?? [];
        const rank = (status: string) => (status === 'offline' ? 0 : status === 'degraded' ? 1 : 2);
        return [...services].sort((a, b) => {
            const d = rank(a.status) - rank(b.status);
            if (d !== 0) return d;
            return String(a.name).localeCompare(String(b.name));
        });
    }, [health]);

    const missing = useMemo(() => {
        const knownTitles = new Set((health?.services ?? []).map((s) => s.name));
        return KNOWN_SERVICES.filter((s) => !knownTitles.has(s.title));
    }, [health]);

    useEffect(() => {
        fetchHealth({ reason: 'initial' });

        // Auto-refresh every 15 seconds (with cooldown on rate limit)
        const interval = setInterval(() => {
            if (Date.now() < pollCooldownUntilMsRef.current) return;
            fetchHealth({ silent: true, reason: 'auto' });
        }, 15000);

        return () => clearInterval(interval);
    }, [fetchHealth]);

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: '50px' }}>
                <Spin size="large">
                    <div style={{ padding: '20px' }}>Загрузка статуса системы{'\u2026'}</div>
                </Spin>
            </div>
        );
    }

    return (
        <div>
            <Space direction="vertical" style={{ width: '100%' }} size="large">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h1>Статус системы</h1>
                    <Button
                        icon={<ReloadOutlined />}
                        onClick={() => fetchHealth({ reason: 'manual' })}
                        loading={refreshing}
                    >
                        Обновить
                    </Button>
                </div>

                {error && !health && (
                    <Alert
                        type="error"
                        message={error}
                        action={
                            <Button size="small" onClick={() => fetchHealth({ reason: 'manual' })}>
                                Повторить
                            </Button>
                        }
                    />
                )}

                {health && (
                    <>
                        <SystemOverview health={health} />

                        {missing.length > 0 && (
                            <Alert
                                type="warning"
                                message="Часть сервисов отсутствует в /api/v2/system/health/"
                                description={missing.map((s) => s.title).join(', ')}
                                showIcon
                            />
                        )}

                        <Card title="Статус сервисов">
                            <Row gutter={[16, 16]}>
                                {servicesSorted.map((service) => (
                                    <Col xs={24} sm={12} md={8} lg={6} key={service.name}>
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
