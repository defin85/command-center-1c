import { Alert, Button, Modal, Select, Space, Spin, Typography } from 'antd'
import { useMemo, useState } from 'react'

import type { ActionCatalogPreviewState } from './useActionCatalogPreview'
import { useDatabases } from '../../../api/queries/databases'

export type ActionCatalogPreviewModalProps = {
  previewModal: ActionCatalogPreviewState
  onClose: () => void
  onRun: () => void
  onDatabaseIdsChange: (ids: string[]) => void
}

const { Text } = Typography

export function ActionCatalogPreviewModal({
  previewModal,
  onClose,
  onRun,
  onDatabaseIdsChange,
}: ActionCatalogPreviewModalProps) {
  const [search, setSearch] = useState('')
  const needsDatabases = previewModal.executorKind === 'ibcmd_cli'

  const databasesQuery = useDatabases({
    filters: { search: search.trim() || undefined, limit: 50, offset: 0 },
    enabled: previewModal.open && needsDatabases,
  })

  const databaseOptions = useMemo(() => {
    const items = databasesQuery.data?.databases ?? []
    return items.map((db) => ({
      value: db.id,
      label: `${db.name} (${db.id})`,
    }))
  }, [databasesQuery.data])

  const canRun = !previewModal.loading && (!needsDatabases || previewModal.databaseIds.length > 0)

  return (
    <Modal
      title={previewModal.title}
      open={previewModal.open}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>Close</Button>,
        <Button key="run" type="primary" onClick={onRun} disabled={!canRun} loading={previewModal.loading}>
          Preview
        </Button>,
      ]}
      width={900}
    >
      {needsDatabases && (
        <Space direction="vertical" size={6} style={{ width: '100%', marginBottom: 12 }}>
          <Text type="secondary">
            Для <Text code>ibcmd_cli</Text> preview требуется выбрать базу (или набор баз), так как connection резолвится per database.
          </Text>
          <Select
            mode="tags"
            showSearch
            value={previewModal.databaseIds}
            onChange={(value) => onDatabaseIdsChange(value)}
            onSearch={(value) => setSearch(value)}
            options={databaseOptions}
            placeholder={databasesQuery.isLoading ? 'Loading databases…' : 'Select databases (or paste IDs)'}
            notFoundContent={databasesQuery.isError ? 'Failed to load databases' : 'No databases'}
            tokenSeparators={['\n', ' ', ',', ';']}
            style={{ width: '100%' }}
            data-testid="action-catalog-preview-database-ids"
          />
        </Space>
      )}

      {previewModal.loading ? (
        <Spin />
      ) : previewModal.error ? (
        <Alert type="error" showIcon message="Preview failed" description={previewModal.error} />
      ) : previewModal.payload === null ? (
        <Alert type="info" showIcon message="Нажмите Preview, чтобы сформировать execution plan." />
      ) : (
        <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
          {JSON.stringify(previewModal.payload, null, 2)}
        </pre>
      )}
    </Modal>
  )
}
