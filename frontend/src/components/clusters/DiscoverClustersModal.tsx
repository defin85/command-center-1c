import React, { useState } from 'react'
import { Modal, Form, Input, App } from 'antd'
import { apiClient } from '../../api/client'

interface DiscoverClustersModalProps {
    visible: boolean
    onClose: () => void
    onSuccess: () => void
}

interface DiscoverForm {
    ras_server: string
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
