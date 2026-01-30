import React from 'react';
import { Modal, Typography, List, Alert, Input, Form, DatePicker } from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getOperationConfig } from './constants';

interface DatabaseInfo {
  id: string;
  name: string;
}

export interface OperationConfirmModalProps {
  visible: boolean;
  operation: string;
  databases: DatabaseInfo[];
  onConfirm: (config?: {
    message?: string;
    permission_code?: string;
    denied_from?: string;
    denied_to?: string;
    parameter?: string;
  }) => void;
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
      const payload = { ...values } as Record<string, unknown>;
      const deniedFrom = payload.denied_from;
      const deniedTo = payload.denied_to;
      if (dayjs.isDayjs(deniedFrom)) {
        payload.denied_from = deniedFrom.toISOString();
      }
      if (dayjs.isDayjs(deniedTo)) {
        payload.denied_to = deniedTo.toISOString();
      }
      onConfirm(payload as {
        message?: string;
        permission_code?: string;
        denied_from?: string;
        denied_to?: string;
        parameter?: string;
      });
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
            name="denied_from"
            label="Block start (optional)"
            help="Start time for blocking new sessions"
            htmlFor="operation-confirm-block-start"
          >
            <DatePicker
              id="operation-confirm-block-start"
              showTime={{ format: 'HH:mm' }}
              allowClear
              style={{ width: '100%' }}
              format="DD.MM.YYYY HH:mm"
            />
          </Form.Item>

          <Form.Item
            name="denied_to"
            label="Block end (optional)"
            help="End time for blocking new sessions"
            htmlFor="operation-confirm-block-end"
          >
            <DatePicker
              id="operation-confirm-block-end"
              showTime={{ format: 'HH:mm' }}
              allowClear
              style={{ width: '100%' }}
              format="DD.MM.YYYY HH:mm"
            />
          </Form.Item>

          <Form.Item
            name="message"
            label="Block message (shown to users)"
            rules={[{ required: true, message: 'Please enter a message' }]}
            htmlFor="operation-confirm-message"
          >
            <Input.TextArea id="operation-confirm-message" rows={2} placeholder="Maintenance in progress\u2026" />
          </Form.Item>

          <Form.Item
            name="permission_code"
            label="Permission code (optional)"
            help="Users with this code can still connect"
            htmlFor="operation-confirm-permission-code"
          >
            <Input id="operation-confirm-permission-code" placeholder="Enter permission code" />
          </Form.Item>

          <Form.Item
            name="parameter"
            label="Block parameter (optional)"
            help="Additional block parameter for 1C"
            htmlFor="operation-confirm-block-parameter"
          >
            <Input id="operation-confirm-block-parameter" placeholder="Enter block parameter" />
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
        footer={databases.length > 10 ? `\u2026 and ${databases.length - 10} more` : null}
        style={{ maxHeight: 200, overflow: 'auto' }}
      />
    </Modal>
  );
};

export default OperationConfirmModal;
