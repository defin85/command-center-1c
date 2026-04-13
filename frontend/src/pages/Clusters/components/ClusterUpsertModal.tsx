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
import { useClustersTranslation } from '../../../i18n'

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
  const { t } = useClustersTranslation()

  return (
    <ModalFormShell
      open={open}
      onClose={onCancel}
      onSubmit={onSubmit}
      title={editingCluster ? t(($) => $.upsertModal.editTitle) : t(($) => $.upsertModal.createTitle)}
      subtitle={t(($) => $.upsertModal.subtitle)}
      width={600}
      confirmLoading={confirmLoading}
      submitText={editingCluster ? t(($) => $.actions.update) : t(($) => $.actions.createSubmit)}
      forceRender
    >
      <Form form={form} layout="vertical">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Form.Item
            label={t(($) => $.upsertModal.clusterName)}
            name="name"
            rules={[{ required: true, message: t(($) => $.upsertModal.clusterNameRequired) }]}
            htmlFor="cluster-name"
          >
            <Input id="cluster-name" placeholder={t(($) => $.upsertModal.productionClusterPlaceholder)} />
          </Form.Item>

          <Form.Item label={t(($) => $.upsertModal.description)} name="description" htmlFor="cluster-description">
            <TextArea id="cluster-description" rows={3} placeholder={t(($) => $.upsertModal.descriptionPlaceholder)} />
          </Form.Item>

          <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'minmax(0, 1fr) 140px' }}>
            <Form.Item
              label={t(($) => $.upsertModal.rasHost)}
              name="ras_host"
              rules={[{ required: true, message: t(($) => $.upsertModal.rasHostRequired) }]}
              htmlFor="cluster-ras-host"
            >
              <Input id="cluster-ras-host" placeholder={defaultRasHostPlaceholder} />
            </Form.Item>
            <Form.Item
              label={t(($) => $.upsertModal.rasPort)}
              name="ras_port"
              rules={[{ required: true, message: t(($) => $.upsertModal.rasPortRequired) }]}
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
              label={t(($) => $.upsertModal.rmngrHost)}
              name="rmngr_host"
              rules={[{ required: true, message: t(($) => $.upsertModal.rmngrHostRequired) }]}
              htmlFor="cluster-rmngr-host"
            >
              <Input id="cluster-rmngr-host" placeholder="localhost" />
            </Form.Item>
            <Form.Item
              label={t(($) => $.upsertModal.rmngrPort)}
              name="rmngr_port"
              rules={[{ required: true, message: t(($) => $.upsertModal.rmngrPortRequired) }]}
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
            <Form.Item label={t(($) => $.upsertModal.ragentHost)} name="ragent_host" htmlFor="cluster-ragent-host">
              <Input id="cluster-ragent-host" placeholder="localhost" />
            </Form.Item>
            <Form.Item label={t(($) => $.upsertModal.ragentPort)} name="ragent_port" htmlFor="cluster-ragent-port">
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
            <Form.Item label={t(($) => $.upsertModal.rphostPortFrom)} name="rphost_port_from" htmlFor="cluster-rphost-port-from">
              <InputNumber
                id="cluster-rphost-port-from"
                min={1}
                max={65535}
                style={{ width: '100%' }}
                placeholder={String(DEFAULT_RPHOST_PORT_FROM)}
              />
            </Form.Item>
            <Form.Item label={t(($) => $.upsertModal.rphostPortTo)} name="rphost_port_to" htmlFor="cluster-rphost-port-to">
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
            label={t(($) => $.upsertModal.clusterServiceUrl)}
            name="cluster_service_url"
            rules={[{ required: true, message: t(($) => $.upsertModal.clusterServiceUrlRequired) }]}
            htmlFor="cluster-service-url"
          >
            <Input id="cluster-service-url" placeholder={DEFAULT_CLUSTER_SERVICE_URL} />
          </Form.Item>

          {editingCluster ? (
            <Form.Item
              label={t(($) => $.upsertModal.clusterCredentials)}
              htmlFor="cluster-credentials-button"
              extra={t(($) => $.upsertModal.clusterCredentialsHelp)}
            >
              <Button
                id="cluster-credentials-button"
                icon={<KeyOutlined />}
                onClick={() => editingCluster && onOpenCredentials(editingCluster)}
              >
                {t(($) => $.upsertModal.openCredentials)}
              </Button>
            </Form.Item>
          ) : (
            <>
              <Form.Item label={t(($) => $.upsertModal.clusterAdminUser)} name="cluster_user" htmlFor="cluster-admin-user">
                <Input id="cluster-admin-user" placeholder={t(($) => $.upsertModal.optionalClusterAdminUsername)} />
              </Form.Item>
              <Form.Item label={t(($) => $.upsertModal.clusterAdminPassword)} name="cluster_pwd" htmlFor="cluster-admin-password">
                <Input.Password
                  id="cluster-admin-password"
                  placeholder={t(($) => $.upsertModal.optionalClusterAdminPassword)}
                  autoComplete="new-password"
                />
              </Form.Item>
            </>
          )}

          <Form.Item label={t(($) => $.upsertModal.status)} name="status" htmlFor="cluster-status">
            <Select id="cluster-status">
              <Select.Option value="active">{t(($) => $.statusOptions.active)}</Select.Option>
              <Select.Option value="inactive">{t(($) => $.statusOptions.inactive)}</Select.Option>
              <Select.Option value="maintenance">{t(($) => $.statusOptions.maintenance)}</Select.Option>
              <Select.Option value="error">{t(($) => $.statusOptions.error)}</Select.Option>
            </Select>
          </Form.Item>
        </Space>
      </Form>
    </ModalFormShell>
  )
}
