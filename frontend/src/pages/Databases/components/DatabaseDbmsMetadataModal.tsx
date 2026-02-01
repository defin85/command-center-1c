import { Button, Form, Input, Modal } from 'antd'
import type { FormInstance } from 'antd'

import type { Database } from '../../../api/generated/model/database'

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
    <Modal
      title={database ? `DBMS metadata: ${database.name}` : 'DBMS metadata'}
      open={open}
      onCancel={onCancel}
      footer={[
        <Button key="reset" danger onClick={onReset} disabled={disableReset}>
          Reset
        </Button>,
        <Button key="cancel" onClick={onCancel}>
          Cancel
        </Button>,
        <Button key="save" type="primary" onClick={onSave} loading={saving}>
          Save
        </Button>,
      ]}
    >
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
    </Modal>
  )
}
