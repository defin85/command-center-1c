import React, { useEffect } from 'react'
import { Modal, Form, Input, App } from 'antd'
import type { DiscoverClustersRequest } from '../../api/generated/model/discoverClustersRequest'
import {
    DEFAULT_CLUSTER_SERVICE_URL,
    DEFAULT_RAS_SERVER,
    useDiscoverClusters,
    useSystemConfig,
} from '../../api/queries/clusters'

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
        if (!visible) return
        form.setFieldsValue({
            ras_server: systemConfig?.ras_default_server ?? DEFAULT_RAS_SERVER,
            cluster_service_url: DEFAULT_CLUSTER_SERVICE_URL,
        })
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
                    message.error('Discovery failed: ' + (errorMessage || 'unknown error'))
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
                    htmlFor="discover-ras-server"
                >
                    <Input id="discover-ras-server" placeholder="localhost:1545" />
                </Form.Item>
                <Form.Item
                    label="Cluster Service URL"
                    name="cluster_service_url"
                    rules={[{ required: true, message: 'Cluster service URL is required' }]}
                    extra="RAS Adapter service URL (e.g., http://localhost:8188)"
                    htmlFor="discover-cluster-service-url"
                >
                    <Input id="discover-cluster-service-url" placeholder="http://localhost:8188" />
                </Form.Item>
                <Form.Item label="Cluster Admin User (optional)" name="cluster_user" htmlFor="discover-cluster-user">
                    <Input id="discover-cluster-user" placeholder="admin" />
                </Form.Item>
                <Form.Item label="Cluster Admin Password (optional)" name="cluster_pwd" htmlFor="discover-cluster-password">
                    <Input.Password id="discover-cluster-password" placeholder="password" />
                </Form.Item>
            </Form>
        </Modal>
    )
}

export default DiscoverClustersModal
