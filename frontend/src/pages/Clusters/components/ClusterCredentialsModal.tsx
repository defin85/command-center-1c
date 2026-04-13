import { Button, Form, Input, Space } from 'antd'
import type { FormInstance } from 'antd/es/form'

import type { Cluster } from '../../../api/generated/model/cluster'
import { ModalFormShell } from '../../../components/platform'
import { useClustersTranslation } from '../../../i18n'

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
  const { t } = useClustersTranslation()

  return (
    <ModalFormShell
      open={open}
      onClose={onCancel}
      onSubmit={onSave}
      title={cluster ? t(($) => $.credentialsModal.title, { name: cluster.name }) : t(($) => $.credentialsModal.titleFallback)}
      subtitle={t(($) => $.credentialsModal.subtitle)}
      submitText={t(($) => $.actions.save)}
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
            {t(($) => $.actions.reset)}
          </Button>
        </Space>
        <Form form={form} layout="vertical">
          <Form.Item label={t(($) => $.credentialsModal.clusterAdminUser)} name="username" htmlFor="cluster-credentials-username">
            <Input id="cluster-credentials-username" placeholder={t(($) => $.credentialsModal.optionalClusterAdminUsername)} />
          </Form.Item>
          <Form.Item label={t(($) => $.credentialsModal.clusterAdminPassword)} name="password" htmlFor="cluster-credentials-password">
            <Input.Password
              id="cluster-credentials-password"
              placeholder={cluster?.cluster_pwd_configured
                ? t(($) => $.credentialsModal.configuredPlaceholder)
                : t(($) => $.credentialsModal.enterPasswordPlaceholder)}
            />
          </Form.Item>
        </Form>
      </Space>
    </ModalFormShell>
  )
}
