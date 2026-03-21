import { Alert, Button, Form, Input, Space } from 'antd'
import type { FormInstance } from 'antd'

import type { Database } from '../../../api/generated/model/database'
import { ModalFormShell } from '../../../components/platform'

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
  const disableReset = !database?.password_configured && !database?.username

  return (
    <ModalFormShell
      open={open}
      onClose={onCancel}
      onSubmit={onSave}
      title={database ? `Credentials: ${database.name}` : 'Credentials'}
      subtitle="Legacy OData credential override"
      submitText="Save"
      confirmLoading={saving}
      forceRender
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button danger onClick={onReset} disabled={disableReset}>
            Reset
          </Button>
        </Space>
        <Form form={form} layout="vertical">
          <Alert
            type="info"
            showIcon
            message="Pool publication credentials now use RBAC mappings"
            description="Для `pool.publication_odata` система использует OData user/password из /rbac → Infobase Users. Поля ниже остаются только для legacy сценариев."
            style={{ marginBottom: 12 }}
          />
          <Form.Item label="OData Username" name="username" htmlFor="database-credentials-username">
            <Input id="database-credentials-username" placeholder="Optional OData username" />
          </Form.Item>
          <Form.Item label="OData Password" name="password" htmlFor="database-credentials-password">
            <Input.Password
              id="database-credentials-password"
              placeholder={database?.password_configured ? 'Configured' : 'Enter password'}
            />
          </Form.Item>
        </Form>
      </Space>
    </ModalFormShell>
  )
}
