import { useCallback, useMemo, useState } from 'react'
import { Alert, App, Button, Space, Tabs, Typography } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'

import { useAuthz } from '../../authz/useAuthz'
import { useArtifacts, useDeleteArtifact, useRestoreArtifact } from '../../api/queries'
import type { Artifact } from '../../api/artifacts'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { queryKeys } from '../../api/queries'
import { ArtifactsCreateModal } from './ArtifactsCreateModal'
import { ArtifactDetailsDrawer } from './ArtifactDetailsDrawer'
import { ArtifactsPurgeModal } from './ArtifactsPurgeModal'
import { useArtifactsColumns } from './useArtifactsColumns'

const { Title } = Typography

export const ArtifactsPage = () => {
  const { message, modal } = App.useApp()
  const queryClient = useQueryClient()
  const { isStaff } = useAuthz()

  const [catalogTab, setCatalogTab] = useState<'active' | 'deleted'>('active')
  const [createOpen, setCreateOpen] = useState(false)

  const [detailsOpen, setDetailsOpen] = useState(false)
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null)

  const [purgeOpen, setPurgeOpen] = useState(false)
  const [purgeTarget, setPurgeTarget] = useState<Artifact | null>(null)

  const deleteArtifactMutation = useDeleteArtifact()
  const restoreArtifactMutation = useRestoreArtifact()

  const handleOpenDetails = useCallback((artifact: Artifact) => {
    setSelectedArtifact(artifact)
    setDetailsOpen(true)
  }, [])

  const openPurgeModal = useCallback((artifact: Artifact) => {
    if (!isStaff) {
      message.error('Permanent delete requires staff access')
      return
    }
    setPurgeTarget(artifact)
    setPurgeOpen(true)
  }, [isStaff, message])

  const handleDeleteArtifact = useCallback((artifact: Artifact) => {
    if (!isStaff) {
      message.error('Delete requires staff access')
      return
    }
    modal.confirm({
      title: `Delete artifact "${artifact.name}"?`,
      content: 'Artifact will be hidden from the catalog. Versions and aliases remain stored.',
      okText: 'Delete',
      okButtonProps: { danger: true, loading: deleteArtifactMutation.isPending },
      onOk: async () => {
        try {
          await deleteArtifactMutation.mutateAsync(artifact.id)
          message.success('Artifact deleted')
          if (selectedArtifact?.id === artifact.id) {
            setDetailsOpen(false)
            setSelectedArtifact(null)
          }
          queryClient.invalidateQueries({ queryKey: queryKeys.artifacts.all })
        } catch {
          message.error('Failed to delete artifact')
        }
      },
    })
  }, [deleteArtifactMutation, isStaff, message, modal, queryClient, selectedArtifact?.id])

  const handleRestoreArtifact = useCallback((artifact: Artifact) => {
    if (!isStaff) {
      message.error('Restore requires staff access')
      return
    }
    modal.confirm({
      title: `Restore artifact "${artifact.name}"?`,
      content: 'Artifact will be returned to the active catalog.',
      okText: 'Restore',
      onOk: async () => {
        try {
          await restoreArtifactMutation.mutateAsync(artifact.id)
          message.success('Artifact restored')
          if (selectedArtifact?.id === artifact.id) {
            setDetailsOpen(false)
            setSelectedArtifact(null)
          }
          queryClient.invalidateQueries({ queryKey: queryKeys.artifacts.all })
        } catch {
          message.error('Failed to restore artifact')
        }
      },
    })
  }, [isStaff, message, modal, queryClient, restoreArtifactMutation, selectedArtifact?.id])

  const columns = useArtifactsColumns({
    catalogTab,
    isStaff,
    onOpenDetails: handleOpenDetails,
    onDeleteArtifact: handleDeleteArtifact,
    onRestoreArtifact: handleRestoreArtifact,
    onOpenPurgeModal: openPurgeModal,
  })

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'kind', label: 'Kind', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'tags', label: 'Tags', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'purge_after', label: 'Auto purge', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'created_at', label: 'Created', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'actions', label: 'Actions', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const table = useTableToolkit({
    tableId: 'artifacts',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })

  const tableFilters = table.filters
  const nameFilter = typeof tableFilters.name === 'string' ? tableFilters.name.trim() : ''
  const kindFilter = typeof tableFilters.kind === 'string' ? tableFilters.kind.trim() : ''
  const tagFilter = typeof tableFilters.tags === 'string' ? tableFilters.tags.trim() : ''
  const searchName = table.search.trim()

  const artifactsQuery = useArtifacts(
    {
      name: nameFilter || searchName || undefined,
      kind: kindFilter || undefined,
      tag: tagFilter.split(',')[0]?.trim() || undefined,
      include_deleted: catalogTab === 'deleted',
      only_deleted: catalogTab === 'deleted',
    },
    { enabled: isStaff }
  )

  const artifacts = artifactsQuery.data?.artifacts ?? []
  const totalArtifacts = artifactsQuery.data?.count ?? artifacts.length

  return (
    <div>
      <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
        <Title level={2} style={{ margin: 0 }}>Artifacts</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateOpen(true)}
          disabled={!isStaff}
        >
          Add artifact
        </Button>
      </Space>

      <Tabs
        activeKey={catalogTab}
        onChange={(key) => setCatalogTab(key as 'active' | 'deleted')}
        items={[
          { key: 'active', label: 'Active' },
          { key: 'deleted', label: 'Deleted' },
        ]}
      />

      {!isStaff && (
        <Alert
          type="warning"
          message="Доступ ограничен"
          description="Каталог артефактов доступен только сотрудникам."
          style={{ marginBottom: 16 }}
        />
      )}

      {artifactsQuery.error && (
        <Alert
          type="error"
          message="Не удалось загрузить артефакты"
          style={{ marginBottom: 16 }}
        />
      )}

      <TableToolkit
        table={table}
        data={artifacts}
        total={totalArtifacts}
        loading={artifactsQuery.isLoading}
        rowKey="id"
        columns={columns}
        tableLayout="fixed"
        scroll={{ x: table.totalColumnsWidth }}
        searchPlaceholder="Search artifacts"
      />

      <ArtifactsCreateModal
        open={createOpen}
        isStaff={isStaff}
        onClose={() => setCreateOpen(false)}
        onCreated={handleOpenDetails}
      />

      <ArtifactDetailsDrawer
        open={detailsOpen}
        artifact={selectedArtifact}
        catalogTab={catalogTab}
        isStaff={isStaff}
        onClose={() => setDetailsOpen(false)}
        onDeleteArtifact={handleDeleteArtifact}
        onRestoreArtifact={handleRestoreArtifact}
        onOpenPurgeModal={openPurgeModal}
      />

      <ArtifactsPurgeModal
        open={purgeOpen}
        target={purgeTarget}
        onClose={() => {
          setPurgeOpen(false)
          setPurgeTarget(null)
        }}
        onDeleted={(artifactId) => {
          if (selectedArtifact?.id === artifactId) {
            setDetailsOpen(false)
            setSelectedArtifact(null)
          }
        }}
      />
    </div>
  )
}
