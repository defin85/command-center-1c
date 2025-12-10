import React, { useEffect } from 'react'
import { Modal, Form, Input, App } from 'antd'
import { useSystemConfig, useDiscoverClusters, type DiscoverClustersRequest } from '../../api/queries/clusters'

interface DiscoverClustersModalProps {
    visible: boolean
    onClose: () => void
}

export const DiscoverClustersModal: React.FC<DiscoverClustersModalProps> = ({
    visible,
    onClose,
}) => {
    const { message } = App.useApp()
    const [form] = Form.useForm<DiscoverClustersRequest>()

    // React Query hooks
    const { data: systemConfig } = useSystemConfig()
    const discoverClusters = useDiscoverClusters()

    // Set default values when modal opens
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

            discoverClusters.mutate(values, {
                onSuccess: (response) => {
                    message.success(`Discovery started. Operation ID: ${response.operation_id}`)
                    form.resetFields()
                    onClose()
                },
                onError: (error: any) => {
                    const errorMessage =
                        error.response?.data?.error?.message ||
                        error.response?.data?.message ||
                        error.message
                    message.error('Discovery failed: ' + errorMessage)
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
        <Modal
            title="Discover Clusters from RAS Server"
            open={visible}
            onOk={handleDiscover}
            onCancel={handleCancel}
            confirmLoading={discoverClusters.isPending}
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
