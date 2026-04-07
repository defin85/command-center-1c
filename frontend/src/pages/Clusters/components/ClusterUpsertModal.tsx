import { Button, Form, Input, InputNumber, Select, Space } from 'antd'
import { KeyOutlined } from '@ant-design/icons'
import type { FormInstance } from 'antd/es/form'

import type { Cluster } from '../../../api/generated/model/cluster'
import { ModalFormShell } from '../../../components/platform'
import {
  DEFAULT_CLUSTER_SERVICE_URL,
  DEFAULT_RAGENT_PORT,
  DEFAULT_RAS_PORT,
  DEFAULT_RMNGR_PORT,
  DEFAULT_RPHOST_PORT_FROM,
  DEFAULT_RPHOST_PORT_TO,
} from '../../../api/queries/clusters'

const { TextArea } = Input

export function ClusterUpsertModal({
  open,
  editingCluster,
  form,
  confirmLoading,
  defaultRasHostPlaceholder,
  onCancel,
  onSubmit,
  onOpenCredentials,
}: {
  open: boolean
  editingCluster: Cluster | null
  form: FormInstance
  confirmLoading: boolean
  defaultRasHostPlaceholder: string
  onCancel: () => void
  onSubmit: () => void
  onOpenCredentials: (cluster: Cluster) => void
}) {
  return (
    <ModalFormShell
      open={open}
      onClose={onCancel}
      onSubmit={onSubmit}
      title={editingCluster ? 'Edit Cluster' : 'Add New Cluster'}
      subtitle="1C cluster connection and management settings"
      width={600}
      confirmLoading={confirmLoading}
      submitText={editingCluster ? 'Update' : 'Create'}
      forceRender
    >
      <Form form={form} layout="vertical">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Form.Item
            label="Cluster Name"
            name="name"
            rules={[{ required: true, message: 'Please enter cluster name' }]}
            htmlFor="cluster-name"
          >
            <Input id="cluster-name" placeholder="Production Cluster" />
          </Form.Item>

          <Form.Item label="Description" name="description" htmlFor="cluster-description">
            <TextArea id="cluster-description" rows={3} placeholder="Optional description" />
          </Form.Item>

          <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'minmax(0, 1fr) 140px' }}>
            <Form.Item
              label="RAS Host"
              name="ras_host"
              rules={[{ required: true, message: 'Please enter RAS host' }]}
              htmlFor="cluster-ras-host"
            >
              <Input id="cluster-ras-host" placeholder={defaultRasHostPlaceholder} />
            </Form.Item>
            <Form.Item
              label="RAS Port"
              name="ras_port"
              rules={[{ required: true, message: 'Please enter RAS port' }]}
              htmlFor="cluster-ras-port"
            >
              <InputNumber
                id="cluster-ras-port"
                min={1}
                max={65535}
                style={{ width: '100%' }}
                placeholder={String(DEFAULT_RAS_PORT)}
              />
            </Form.Item>
          </div>

          <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'minmax(0, 1fr) 140px' }}>
            <Form.Item
              label="RMNGR Host"
              name="rmngr_host"
              rules={[{ required: true, message: 'Please enter RMNGR host' }]}
              htmlFor="cluster-rmngr-host"
            >
              <Input id="cluster-rmngr-host" placeholder="localhost" />
            </Form.Item>
            <Form.Item
              label="RMNGR Port"
              name="rmngr_port"
              rules={[{ required: true, message: 'Please enter RMNGR port' }]}
              htmlFor="cluster-rmngr-port"
            >
              <InputNumber
                id="cluster-rmngr-port"
                min={1}
                max={65535}
                style={{ width: '100%' }}
                placeholder={String(DEFAULT_RMNGR_PORT)}
              />
            </Form.Item>
          </div>

          <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'minmax(0, 1fr) 140px' }}>
            <Form.Item label="RAGENT Host" name="ragent_host" htmlFor="cluster-ragent-host">
              <Input id="cluster-ragent-host" placeholder="localhost" />
            </Form.Item>
            <Form.Item label="RAGENT Port" name="ragent_port" htmlFor="cluster-ragent-port">
              <InputNumber
                id="cluster-ragent-port"
                min={1}
                max={65535}
                style={{ width: '100%' }}
                placeholder={String(DEFAULT_RAGENT_PORT)}
              />
            </Form.Item>
          </div>

          <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
            <Form.Item label="RPHOST Port From" name="rphost_port_from" htmlFor="cluster-rphost-port-from">
              <InputNumber
                id="cluster-rphost-port-from"
                min={1}
                max={65535}
                style={{ width: '100%' }}
                placeholder={String(DEFAULT_RPHOST_PORT_FROM)}
              />
            </Form.Item>
            <Form.Item label="RPHOST Port To" name="rphost_port_to" htmlFor="cluster-rphost-port-to">
              <InputNumber
                id="cluster-rphost-port-to"
                min={1}
                max={65535}
                style={{ width: '100%' }}
                placeholder={String(DEFAULT_RPHOST_PORT_TO)}
              />
            </Form.Item>
          </div>

          <Form.Item
            label="Cluster Service URL"
            name="cluster_service_url"
            rules={[{ required: true, message: 'Please enter cluster service URL' }]}
            htmlFor="cluster-service-url"
          >
            <Input id="cluster-service-url" placeholder={DEFAULT_CLUSTER_SERVICE_URL} />
          </Form.Item>

          {editingCluster ? (
            <Form.Item
              label="Cluster Credentials"
              htmlFor="cluster-credentials-button"
              extra="Use Credentials to update or reset username/password."
            >
              <Button
                id="cluster-credentials-button"
                icon={<KeyOutlined />}
                onClick={() => editingCluster && onOpenCredentials(editingCluster)}
              >
                Open Credentials
              </Button>
            </Form.Item>
          ) : (
            <>
              <Form.Item label="Cluster Admin User" name="cluster_user" htmlFor="cluster-admin-user">
                <Input id="cluster-admin-user" placeholder="Optional cluster admin username" />
              </Form.Item>
              <Form.Item label="Cluster Admin Password" name="cluster_pwd" htmlFor="cluster-admin-password">
                <Input.Password
                  id="cluster-admin-password"
                  placeholder="Optional cluster admin password"
                  autoComplete="new-password"
                />
              </Form.Item>
            </>
          )}

          <Form.Item label="Status" name="status" htmlFor="cluster-status">
            <Select id="cluster-status">
              <Select.Option value="active">Active</Select.Option>
              <Select.Option value="inactive">Inactive</Select.Option>
              <Select.Option value="maintenance">Maintenance</Select.Option>
              <Select.Option value="error">Error</Select.Option>
            </Select>
          </Form.Item>
        </Space>
      </Form>
    </ModalFormShell>
  )
}
