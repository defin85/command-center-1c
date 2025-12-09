import React, { useEffect, useState } from 'react'
import { Modal, Progress, Typography, Alert, Space, Spin, Button } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, ClockCircleOutlined, MonitorOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { ExtensionInstallation } from '../../types/installation'

const { Text, Title, Paragraph } = Typography

interface InstallationProgressModalProps {
    visible: boolean
    databaseId: string
    databaseName: string
    operationId?: string  // Operation ID для мониторинга workflow
    onClose: () => void
    pollInterval?: number // ms, по умолчанию 2000
    fetchStatus: (databaseId: string) => Promise<ExtensionInstallation | null>
}

export const InstallationProgressModal: React.FC<InstallationProgressModalProps> = ({
    visible,
    databaseId,
    databaseName,
    operationId,
    onClose,
    pollInterval = 2000,
    fetchStatus,
}) => {
    const navigate = useNavigate()
    const [installation, setInstallation] = useState<ExtensionInstallation | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!visible || !databaseId) return

        const fetchProgress = async () => {
            try {
                setLoading(true)
                const data = await fetchStatus(databaseId)
                setInstallation(data)
                setError(null)

                // Остановить polling если установка завершена или провалилась
                if (data && (data.status === 'completed' || data.status === 'failed')) {
                    clearInterval(intervalId)
                }
            } catch (err: any) {
                setError(err.message || 'Failed to fetch installation status')
            } finally {
                setLoading(false)
            }
        }

        // Первый запрос сразу
        fetchProgress()

        // Polling каждые N секунд
        const intervalId = setInterval(fetchProgress, pollInterval)

        return () => clearInterval(intervalId)
    }, [visible, databaseId, pollInterval, fetchStatus])

    const getStatusIcon = () => {
        if (!installation) return <LoadingOutlined spin />

        switch (installation.status) {
            case 'completed':
                return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 24 }} />
            case 'failed':
                return <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 24 }} />
            case 'in_progress':
                return <LoadingOutlined spin style={{ fontSize: 24 }} />
            case 'pending':
                return <ClockCircleOutlined style={{ color: '#faad14', fontSize: 24 }} />
            default:
                return <LoadingOutlined spin />
        }
    }

    const getStatusText = () => {
        if (!installation) return 'Загрузка...'

        switch (installation.status) {
            case 'completed':
                return 'Установка завершена успешно'
            case 'failed':
                return 'Ошибка установки'
            case 'in_progress':
                return 'Установка в процессе...'
            case 'pending':
                return 'Ожидание начала установки...'
            default:
                return 'Неизвестный статус'
        }
    }

    const getProgressPercent = () => {
        if (!installation) return 0

        switch (installation.status) {
            case 'completed':
                return 100
            case 'failed':
                return 100
            case 'in_progress':
                return 50 // Можно добавить реальный процент из backend
            case 'pending':
                return 10
            default:
                return 0
        }
    }

    const formatDuration = (seconds: number | null) => {
        if (!seconds) return 'N/A'
        const mins = Math.floor(seconds / 60)
        const secs = seconds % 60
        return `${mins}м ${secs}с`
    }

    return (
        <Modal
            title="Прогресс установки расширения"
            open={visible}
            onCancel={onClose}
            footer={null}
            width={600}
            maskClosable={installation?.status === 'completed' || installation?.status === 'failed'}
        >
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
                {/* Header с иконкой статуса */}
                <div style={{ textAlign: 'center' }}>
                    {getStatusIcon()}
                    <Title level={4} style={{ marginTop: 16 }}>
                        {databaseName}
                    </Title>
                    <Text type="secondary">{installation?.extension_name || 'Extension'}</Text>
                </div>

                {/* Progress Bar */}
                <Progress
                    percent={getProgressPercent()}
                    status={
                        installation?.status === 'failed'
                            ? 'exception'
                            : installation?.status === 'completed'
                                ? 'success'
                                : 'active'
                    }
                    strokeColor={
                        installation?.status === 'in_progress'
                            ? { from: '#108ee9', to: '#87d068' }
                            : undefined
                    }
                />

                {/* Status Text */}
                <Alert
                    message={getStatusText()}
                    type={
                        installation?.status === 'completed'
                            ? 'success'
                            : installation?.status === 'failed'
                                ? 'error'
                                : installation?.status === 'in_progress'
                                    ? 'info'
                                    : 'warning'
                    }
                    showIcon
                />

                {/* Operation ID Block */}
                {operationId && (
                    <div style={{
                        padding: '12px',
                        background: '#f0f2f5',
                        borderRadius: '8px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center'
                    }}>
                        <div>
                            <Text strong>Operation ID: </Text>
                            <Paragraph
                                copyable={{ text: operationId, tooltips: ['Копировать', 'Скопировано!'] }}
                                style={{ marginBottom: 0, display: 'inline', fontSize: '12px' }}
                            >
                                <code>{operationId}</code>
                            </Paragraph>
                        </div>
                        <Button
                            type="primary"
                            icon={<MonitorOutlined />}
                            onClick={() => {
                                navigate(`/operations?tab=monitor&operation=${operationId}`)
                                onClose()
                            }}
                        >
                            Monitor Workflow
                        </Button>
                    </div>
                )}

                {/* Error Message */}
                {installation?.error_message && (
                    <Alert message="Ошибка" description={installation.error_message} type="error" showIcon />
                )}

                {/* Metadata */}
                <div>
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        {installation?.started_at && (
                            <div>
                                <Text strong>Начало: </Text>
                                <Text>{new Date(installation.started_at).toLocaleString('ru-RU')}</Text>
                            </div>
                        )}
                        {installation?.completed_at && (
                            <div>
                                <Text strong>Завершение: </Text>
                                <Text>{new Date(installation.completed_at).toLocaleString('ru-RU')}</Text>
                            </div>
                        )}
                        {installation?.duration_seconds !== null && installation?.duration_seconds !== undefined && (
                            <div>
                                <Text strong>Длительность: </Text>
                                <Text>{formatDuration(installation.duration_seconds)}</Text>
                            </div>
                        )}
                        {installation && installation.retry_count > 0 && (
                            <div>
                                <Text strong>Попытки: </Text>
                                <Text>{installation.retry_count}</Text>
                            </div>
                        )}
                    </Space>
                </div>

                {/* Loading Indicator для polling */}
                {loading && installation?.status === 'in_progress' && (
                    <div style={{ textAlign: 'center' }}>
                        <Spin size="small" />
                        <Text type="secondary" style={{ marginLeft: 8 }}>
                            Обновление статуса...
                        </Text>
                    </div>
                )}

                {/* Error State */}
                {error && <Alert message="Ошибка загрузки" description={error} type="error" showIcon />}
            </Space>
        </Modal>
    )
}
