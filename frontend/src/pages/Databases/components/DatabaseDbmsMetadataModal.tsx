import { Button, Form, Input, Space } from 'antd'
import type { FormInstance } from 'antd'

import type { Database } from '../../../api/generated/model/database'
import { ModalFormShell } from '../../../components/platform'

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
  const dbAny = (database ?? null) as (Database & { dbms?: string | null; db_server?: string | null; db_name?: string | null }) | null
  const disableReset = !dbAny?.dbms && !dbAny?.db_server && !dbAny?.db_name

  return (
    <ModalFormShell
      open={open}
      onClose={onCancel}
      onSubmit={onSave}
      title={database ? `DBMS metadata: ${database.name}` : 'DBMS metadata'}
      subtitle="Database-scoped DBMS identity override"
      submitText="Save"
      confirmLoading={saving}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button danger onClick={onReset} disabled={disableReset}>
            Reset
          </Button>
        </Space>
        <Form form={form} layout="vertical">
          <Form.Item label="DBMS" name="dbms" htmlFor="database-dbms-metadata-dbms">
            <Input id="database-dbms-metadata-dbms" placeholder="e.g. PostgreSQL" />
          </Form.Item>
          <Form.Item label="DB server" name="db_server" htmlFor="database-dbms-metadata-db-server">
            <Input id="database-dbms-metadata-db-server" placeholder="e.g. db.example.local" />
          </Form.Item>
          <Form.Item label="DB name" name="db_name" htmlFor="database-dbms-metadata-db-name">
            <Input id="database-dbms-metadata-db-name" placeholder="e.g. my_infobase" />
          </Form.Item>
        </Form>
      </Space>
    </ModalFormShell>
  )
}
