import { Button, Form, Input, Space } from 'antd'
import type { FormInstance } from 'antd/es/form'

import type { Cluster } from '../../../api/generated/model/cluster'
import { ModalFormShell } from '../../../components/platform'

export function ClusterCredentialsModal({
  open,
  cluster,
  form,
  saving,
  onCancel,
  onSave,
  onReset,
}: {
  open: boolean
  cluster: Cluster | null
  form: FormInstance
  saving: boolean
  onCancel: () => void
  onSave: () => void
  onReset: () => void
}) {
  return (
    <ModalFormShell
      open={open}
      onClose={onCancel}
      onSubmit={onSave}
      title={cluster ? `Credentials: ${cluster.name}` : 'Credentials'}
      subtitle="Cluster admin credential override"
      submitText="Save"
      confirmLoading={saving}
      forceRender
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button
            danger
            onClick={onReset}
            disabled={!cluster?.cluster_pwd_configured}
          >
            Reset
          </Button>
        </Space>
        <Form form={form} layout="vertical">
          <Form.Item label="Cluster Admin User" name="username" htmlFor="cluster-credentials-username">
            <Input id="cluster-credentials-username" placeholder="Optional cluster admin username" />
          </Form.Item>
          <Form.Item label="Cluster Admin Password" name="password" htmlFor="cluster-credentials-password">
            <Input.Password
              id="cluster-credentials-password"
              placeholder={cluster?.cluster_pwd_configured ? 'Configured' : 'Enter password'}
            />
          </Form.Item>
        </Form>
      </Space>
    </ModalFormShell>
  )
}
