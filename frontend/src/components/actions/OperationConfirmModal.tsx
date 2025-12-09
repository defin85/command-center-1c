import React from 'react';
import { Modal, Typography, List, Alert, Input, Form } from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import { getOperationConfig } from './constants';

interface DatabaseInfo {
  id: string;
  name: string;
}

export interface OperationConfirmModalProps {
  visible: boolean;
  operation: string;
  databases: DatabaseInfo[];
  onConfirm: (config?: { message?: string }) => void;
  onCancel: () => void;
  loading?: boolean;
}

export const OperationConfirmModal: React.FC<OperationConfirmModalProps> = ({
  visible,
  operation,
  databases,
  onConfirm,
  onCancel,
  loading = false,
}) => {
  const [form] = Form.useForm();
  const config = getOperationConfig(operation) ?? {
    key: operation,
    label: operation,
    description: '',
    icon: '',
    requiresConfig: false,
  };

  const handleOk = async () => {
    if (config.requiresConfig) {
      const values = await form.validateFields();
      onConfirm(values);
    } else {
      onConfirm();
    }
  };

  const handleCancel = () => {
    form.resetFields();
    onCancel();
  };

  return (
    <Modal
      title={
        <>
          {config.danger && <WarningOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />}
          Confirm: {config.label}
        </>
      }
      open={visible}
      onOk={handleOk}
      onCancel={handleCancel}
      afterClose={() => form.resetFields()}
      okText={config.danger ? 'Yes, proceed' : 'Confirm'}
      okButtonProps={{ danger: config.danger, loading }}
      cancelButtonProps={{ disabled: loading }}
    >
      <Typography.Paragraph>{config.description}</Typography.Paragraph>

      {config.danger && (
        <Alert
          type="warning"
          message="This action cannot be undone"
          style={{ marginBottom: 16 }}
        />
      )}

      {config.requiresConfig && (
        <Form form={form} layout="vertical" style={{ marginBottom: 16 }}>
          <Form.Item
            name="message"
            label="Block message (shown to users)"
            rules={[{ required: true, message: 'Please enter a message' }]}
          >
            <Input.TextArea rows={2} placeholder="Maintenance in progress..." />
          </Form.Item>
        </Form>
      )}

      <Typography.Text strong>
        Target databases ({databases.length}):
      </Typography.Text>
      <List
        size="small"
        dataSource={databases.slice(0, 10)}
        renderItem={(db) => <List.Item>{db.name}</List.Item>}
        footer={databases.length > 10 ? `...and ${databases.length - 10} more` : null}
        style={{ maxHeight: 200, overflow: 'auto' }}
      />
    </Modal>
  );
};

export default OperationConfirmModal;
