import { Button, Form, Input, Modal } from 'antd'
import type { FormInstance } from 'antd/es/form'

import type { Cluster } from '../../../api/generated/model/cluster'

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
    <Modal
      title={cluster ? `Credentials: ${cluster.name}` : 'Credentials'}
      open={open}
      onCancel={onCancel}
      footer={[
        <Button
          key="reset"
          danger
          onClick={onReset}
          disabled={!cluster?.cluster_pwd_configured}
        >
          Reset
        </Button>,
        <Button
          key="cancel"
          onClick={onCancel}
        >
          Cancel
        </Button>,
        <Button
          key="save"
          type="primary"
          onClick={onSave}
          loading={saving}
        >
          Save
        </Button>,
      ]}
    >
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
    </Modal>
  )
}

