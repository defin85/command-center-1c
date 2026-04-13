import React, { useEffect } from 'react'
import { App, Form, Input, InputNumber, Space } from 'antd'
import type { DiscoverClustersRequest } from '../../api/generated/model/discoverClustersRequest'
import { ModalFormShell } from '../platform'
import {
    DEFAULT_CLUSTER_SERVICE_URL,
    DEFAULT_RAS_SERVER,
    DEFAULT_RAS_PORT,
    parseHostPort,
    useDiscoverClusters,
    useSystemConfig,
} from '../../api/queries/clusters'
import { useClustersTranslation } from '../../i18n'

interface DiscoverClustersModalProps {
    open: boolean
    onClose: () => void
}

export const DiscoverClustersModal: React.FC<DiscoverClustersModalProps> = ({
    open,
    onClose,
}) => {
    const { message } = App.useApp()
    const { t } = useClustersTranslation()
    const [form] = Form.useForm<DiscoverClustersRequest>()

    // React Query hooks
    const { data: systemConfig } = useSystemConfig()
    const discoverClusters = useDiscoverClusters()

    // Set default values when modal opens
    useEffect(() => {
        if (!open) return
        const rasDefaults = parseHostPort(systemConfig?.ras_default_server ?? DEFAULT_RAS_SERVER)
        form.setFieldsValue({
            ras_host: rasDefaults.host,
            ras_port: rasDefaults.port || DEFAULT_RAS_PORT,
            cluster_service_url: DEFAULT_CLUSTER_SERVICE_URL,
        })
    }, [open, systemConfig, form])

    const handleDiscover = async () => {
        try {
            const values = await form.validateFields()

            discoverClusters.mutate(values, {
                onSuccess: (response) => {
                    message.success(t(($) => $.messages.discoveryStarted, { id: response.operation_id }))
                    form.resetFields()
                    onClose()
                },
                onError: (error: unknown) => {
                    const errorMessage = (() => {
                        if (typeof error === 'object' && error !== null) {
                            const maybe = error as {
                                response?: { data?: { error?: { message?: string }; message?: string } }
                                message?: string
                            }
                            return (
                                maybe.response?.data?.error?.message ||
                                maybe.response?.data?.message ||
                                maybe.message
                            )
                        }
                        return undefined
                    })()
                    message.error(t(($) => $.messages.discoveryFailed, {
                        message: errorMessage || t(($) => $.discoverModal.unknownError),
                    }))
                },
            })
        } catch {
            // Form validation failed - errors shown automatically
        }
    }

    const handleCancel = () => {
        form.resetFields()
        onClose()
    }

    return (
        <ModalFormShell
            open={open}
            onClose={handleCancel}
            onSubmit={handleDiscover}
            title={t(($) => $.discoverModal.title)}
            subtitle={t(($) => $.discoverModal.subtitle)}
            confirmLoading={discoverClusters.isPending}
            submitText={t(($) => $.actions.discoverSubmit)}
            forceRender
        >
            <Form form={form} layout="vertical">
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'minmax(0, 1fr) 140px' }}>
                        <Form.Item
                            label={t(($) => $.discoverModal.rasHost)}
                            name="ras_host"
                            rules={[{ required: true, message: t(($) => $.discoverModal.rasHostRequired) }]}
                            htmlFor="discover-ras-host"
                        >
                            <Input id="discover-ras-host" placeholder="localhost" />
                        </Form.Item>
                        <Form.Item
                            label={t(($) => $.discoverModal.rasPort)}
                            name="ras_port"
                            rules={[{ required: true, message: t(($) => $.discoverModal.rasPortRequired) }]}
                            htmlFor="discover-ras-port"
                        >
                            <InputNumber
                                id="discover-ras-port"
                                min={1}
                                max={65535}
                                style={{ width: '100%' }}
                                placeholder={String(DEFAULT_RAS_PORT)}
                            />
                        </Form.Item>
                    </div>
                    <Form.Item
                        label={t(($) => $.discoverModal.clusterServiceUrl)}
                        name="cluster_service_url"
                        rules={[{ required: true, message: t(($) => $.discoverModal.clusterServiceUrlRequired) }]}
                        extra={t(($) => $.discoverModal.clusterServiceUrlHelp)}
                        htmlFor="discover-cluster-service-url"
                    >
                        <Input id="discover-cluster-service-url" placeholder="http://localhost:8188" />
                    </Form.Item>
                    <Form.Item label={t(($) => $.discoverModal.clusterAdminUser)} name="cluster_user" htmlFor="discover-cluster-user">
                        <Input id="discover-cluster-user" placeholder="admin" />
                    </Form.Item>
                    <Form.Item label={t(($) => $.discoverModal.clusterAdminPassword)} name="cluster_pwd" htmlFor="discover-cluster-password">
                        <Input.Password id="discover-cluster-password" placeholder="password" />
                    </Form.Item>
                </Space>
            </Form>
        </ModalFormShell>
    )
}

export default DiscoverClustersModal
