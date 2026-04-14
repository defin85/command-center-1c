import { Alert, Button, Form, Input, Space } from 'antd'
import type { FormInstance } from 'antd'

import type { Database } from '../../../api/generated/model/database'
import { ModalFormShell } from '../../../components/platform'
import { useDatabasesTranslation } from '../../../i18n'

export type DatabaseCredentialsModalProps = {
  open: boolean
  database: Database | null
  form: FormInstance
  saving: boolean
  onCancel: () => void
  onSave: () => void
  onReset: () => void
}

export function DatabaseCredentialsModal({
  open,
  database,
  form,
  saving,
  onCancel,
  onSave,
  onReset,
}: DatabaseCredentialsModalProps) {
  const { t } = useDatabasesTranslation()
  const disableReset = !database?.password_configured && !database?.username

  return (
    <ModalFormShell
      open={open}
      onClose={onCancel}
      onSubmit={onSave}
      title={database
        ? t(($) => $.modals.credentials.titleWithName, { name: database.name })
        : t(($) => $.modals.credentials.title)}
      subtitle={t(($) => $.modals.credentials.subtitle)}
      submitText={t(($) => $.modals.credentials.save)}
      confirmLoading={saving}
      forceRender
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button danger onClick={onReset} disabled={disableReset}>
            {t(($) => $.modals.credentials.reset)}
          </Button>
        </Space>
        <Form form={form} layout="vertical">
          <Alert
            type="info"
            showIcon
            message={t(($) => $.modals.credentials.alertTitle)}
            description={t(($) => $.modals.credentials.alertDescription)}
            style={{ marginBottom: 12 }}
          />
          <Form.Item label={t(($) => $.modals.credentials.usernameLabel)} name="username" htmlFor="database-credentials-username">
            <Input id="database-credentials-username" placeholder={t(($) => $.modals.credentials.usernamePlaceholder)} />
          </Form.Item>
          <Form.Item label={t(($) => $.modals.credentials.passwordLabel)} name="password" htmlFor="database-credentials-password">
            <Input.Password
              id="database-credentials-password"
              placeholder={database?.password_configured
                ? t(($) => $.modals.credentials.passwordConfiguredPlaceholder)
                : t(($) => $.modals.credentials.passwordPlaceholder)}
            />
          </Form.Item>
        </Form>
      </Space>
    </ModalFormShell>
  )
}
