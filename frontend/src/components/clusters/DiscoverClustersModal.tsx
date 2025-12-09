import React, { useState, useEffect } from 'react'
import { Modal, Form, Input, App } from 'antd'
import { apiClient } from '../../api/client'

interface DiscoverClustersModalProps {
    visible: boolean
    onClose: () => void
    onSuccess: () => void
}

interface SystemConfig {
    ras_default_server: string
    ras_adapter_url: string
}

interface DiscoverForm {
    ras_server: string
    cluster_service_url: string
    cluster_user?: string
    cluster_pwd?: string
}

interface DiscoverResponse {
    operation_id: string
    message?: string
}

export const DiscoverClustersModal: React.FC<DiscoverClustersModalProps> = ({
    visible,
    onClose,
    onSuccess,
}) => {
    const { message } = App.useApp()
    const [form] = Form.useForm<DiscoverForm>()
    const [loading, setLoading] = useState(false)
    const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null)

    useEffect(() => {
        const fetchSystemConfig = async () => {
            try {
                const response = await apiClient.get<SystemConfig>('/api/v2/system/config/')
                setSystemConfig(response.data)
            } catch (_error) {
                // Use fallback defaults if config endpoint fails
                setSystemConfig({
                    ras_default_server: 'localhost:1545',
                    ras_adapter_url: 'http://localhost:8188',
                })
            }
        }
        fetchSystemConfig()
    }, [])

    useEffect(() => {
        if (visible && systemConfig) {
            form.setFieldsValue({
                ras_server: systemConfig.ras_default_server,
                cluster_service_url: systemConfig.ras_adapter_url,
            })
        }
    }, [visible, systemConfig, form])

    const handleDiscover = async () => {
        try {
            const values = await form.validateFields()
            setLoading(true)

            const response = await apiClient.post<DiscoverResponse>(
                '/api/v2/clusters/discover-clusters/',
                values
            )
            message.success(`Discovery started. Operation ID: ${response.data.operation_id}`)
            form.resetFields()
            onSuccess()
            onClose()
        } catch (error: any) {
            const errorMessage =
                error.response?.data?.error?.message ||
                error.response?.data?.message ||
                error.message
            message.error('Discovery failed: ' + errorMessage)
        } finally {
            setLoading(false)
        }
    }

    const handleCancel = () => {
        form.resetFields()
        onClose()
    }

    return (
        <Modal
            title="Discover Clusters from RAS Server"
            open={visible}
            onOk={handleDiscover}
            onCancel={handleCancel}
            confirmLoading={loading}
            okText="Discover"
            cancelText="Cancel"
        >
            <Form form={form} layout="vertical">
                <Form.Item
                    label="RAS Server Address"
                    name="ras_server"
                    rules={[{ required: true, message: 'RAS server address is required' }]}
                    extra="Format: host:port (e.g., localhost:1545)"
                >
                    <Input placeholder="localhost:1545" />
                </Form.Item>
                <Form.Item
                    label="Cluster Service URL"
                    name="cluster_service_url"
                    rules={[{ required: true, message: 'Cluster service URL is required' }]}
                    extra="RAS Adapter service URL (e.g., http://localhost:8188)"
                >
                    <Input placeholder="http://localhost:8188" />
                </Form.Item>
                <Form.Item label="Cluster Admin User (optional)" name="cluster_user">
                    <Input placeholder="admin" />
                </Form.Item>
                <Form.Item label="Cluster Admin Password (optional)" name="cluster_pwd">
                    <Input.Password placeholder="password" />
                </Form.Item>
            </Form>
        </Modal>
    )
}

export default DiscoverClustersModal
