import React, { useState } from 'react'
import { Button, Modal, Form, Input, message } from 'antd'
import { RocketOutlined } from '@ant-design/icons'
import { installationApi } from '../../api/endpoints/installation'

interface BatchInstallButtonProps {
  onStarted?: (taskId: string) => void
}

export const BatchInstallButton: React.FC<BatchInstallButtonProps> = ({ onStarted }) => {
  const [modalVisible, setModalVisible] = useState(false)
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()

  const handleStart = async () => {
    try {
      const values = await form.validateFields()
      setLoading(true)

      const response = await installationApi.batchInstall({
        database_ids: 'all',
        extension_config: {
          name: values.extension_name,
          path: values.extension_path,
        },
      })

      message.success(`Installation started! Task ID: ${response.task_id}`)
      setModalVisible(false)
      form.resetFields()

      if (onStarted) {
        onStarted(response.task_id)
      }
    } catch (error: any) {
      message.error(error.message || 'Failed to start installation')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Button
        type="primary"
        size="large"
        icon={<RocketOutlined />}
        onClick={() => setModalVisible(true)}
      >
        Install OData Extension on All Databases
      </Button>

      <Modal
        title="Batch Install OData Extension"
        open={modalVisible}
        onOk={handleStart}
        onCancel={() => setModalVisible(false)}
        confirmLoading={loading}
        okText="Start Installation"
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            extension_name: 'ODataAutoConfig',
            extension_path: 'C:\\Extensions\\ODataAutoConfig.cfe',
          }}
        >
          <Form.Item
            label="Extension Name"
            name="extension_name"
            rules={[{ required: true, message: 'Please enter extension name' }]}
          >
            <Input placeholder="ODataAutoConfig" />
          </Form.Item>

          <Form.Item
            label="Extension Path (on Windows Server)"
            name="extension_path"
            rules={[{ required: true, message: 'Please enter extension path' }]}
          >
            <Input placeholder="C:\Extensions\ODataAutoConfig.cfe" />
          </Form.Item>

          <p style={{ color: '#ff4d4f', marginBottom: 0 }}>
            Warning: This will install the extension on ALL active databases (700+).
            This operation may take 1-2 hours to complete.
          </p>
        </Form>
      </Modal>
    </>
  )
}
