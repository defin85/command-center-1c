import { Button, Form, Input, Space } from 'antd'
import type { FormInstance } from 'antd'

import type { Database } from '../../../api/generated/model/database'
import { ModalFormShell } from '../../../components/platform'
import { useDatabasesTranslation } from '../../../i18n'

export type DatabaseDbmsMetadataModalProps = {
  open: boolean
  database: Database | null
  form: FormInstance
  saving: boolean
  onCancel: () => void
  onSave: () => void
  onReset: () => void
}

export function DatabaseDbmsMetadataModal({
  open,
  database,
  form,
  saving,
  onCancel,
  onSave,
  onReset,
}: DatabaseDbmsMetadataModalProps) {
  const { t } = useDatabasesTranslation()
  const dbAny = (database ?? null) as (Database & { dbms?: string | null; db_server?: string | null; db_name?: string | null }) | null
  const disableReset = !dbAny?.dbms && !dbAny?.db_server && !dbAny?.db_name

  return (
    <ModalFormShell
      open={open}
      onClose={onCancel}
      onSubmit={onSave}
      title={database
        ? t(($) => $.modals.dbms.titleWithName, { name: database.name })
        : t(($) => $.modals.dbms.title)}
      subtitle={t(($) => $.modals.dbms.subtitle)}
      submitText={t(($) => $.modals.dbms.save)}
      confirmLoading={saving}
      forceRender
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button danger onClick={onReset} disabled={disableReset}>
            {t(($) => $.modals.dbms.reset)}
          </Button>
        </Space>
        <Form form={form} layout="vertical">
          <Form.Item label={t(($) => $.modals.dbms.dbmsLabel)} name="dbms" htmlFor="database-dbms-metadata-dbms">
            <Input id="database-dbms-metadata-dbms" placeholder={t(($) => $.modals.dbms.dbmsPlaceholder)} />
          </Form.Item>
          <Form.Item label={t(($) => $.modals.dbms.serverLabel)} name="db_server" htmlFor="database-dbms-metadata-db-server">
            <Input id="database-dbms-metadata-db-server" placeholder={t(($) => $.modals.dbms.serverPlaceholder)} />
          </Form.Item>
          <Form.Item label={t(($) => $.modals.dbms.nameLabel)} name="db_name" htmlFor="database-dbms-metadata-db-name">
            <Input id="database-dbms-metadata-db-name" placeholder={t(($) => $.modals.dbms.namePlaceholder)} />
          </Form.Item>
        </Form>
      </Space>
    </ModalFormShell>
  )
}
