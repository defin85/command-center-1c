import { useCallback, useMemo } from 'react'
import { Alert, App, Button, Space, Typography } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { useAuthz } from '../../authz/useAuthz'
import { useArtifact, useArtifacts, useDeleteArtifact, useRestoreArtifact } from '../../api/queries'
import type { Artifact } from '../../api/artifacts'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { PageHeader, WorkspacePage } from '../../components/platform'
import { queryKeys } from '../../api/queries'
import { ArtifactsCreateModal } from './ArtifactsCreateModal'
import { ArtifactDetailsDrawer } from './ArtifactDetailsDrawer'
import { ArtifactsPurgeModal } from './ArtifactsPurgeModal'
import { useArtifactsColumns } from './useArtifactsColumns'

type ArtifactCatalogTab = 'active' | 'deleted'
type ArtifactContext = 'inspect' | 'create' | 'purge'

const parseCatalogTab = (value: string | null): ArtifactCatalogTab => (
  value === 'deleted' ? 'deleted' : 'active'
)

const parseArtifactContext = (value: string | null): ArtifactContext => {
  if (value === 'create' || value === 'purge') {
    return value
  }
  return 'inspect'
}

export const ArtifactsPage = () => {
  const { message, modal } = App.useApp()
  const queryClient = useQueryClient()
  const { isStaff } = useAuthz()
  const [searchParams, setSearchParams] = useSearchParams()

  const catalogTab = parseCatalogTab(searchParams.get('tab'))
  const activeContext = parseArtifactContext(searchParams.get('context'))
  const selectedArtifactId = (searchParams.get('artifact') || '').trim() || null

  const deleteArtifactMutation = useDeleteArtifact()
  const restoreArtifactMutation = useRestoreArtifact()

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(updates).forEach(([key, value]) => {
        if (!value) {
          next.delete(key)
        } else {
          next.set(key, value)
        }
      })
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )

  const handleOpenDetails = useCallback((artifact: Artifact) => {
    updateSearchParams({
      artifact: artifact.id,
      context: 'inspect',
    })
  }, [updateSearchParams])

  const openPurgeModal = useCallback((artifact: Artifact) => {
    if (!isStaff) {
      message.error('Permanent delete requires staff access')
      return
    }
    updateSearchParams({
      artifact: artifact.id,
      context: 'purge',
    })
  }, [isStaff, message, updateSearchParams])

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
          updateSearchParams({ artifact: null, context: null, tab: 'deleted' })
          queryClient.invalidateQueries({ queryKey: queryKeys.artifacts.all })
        } catch {
          message.error('Failed to delete artifact')
        }
      },
    })
  }, [deleteArtifactMutation, isStaff, message, modal, queryClient, updateSearchParams])

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
          updateSearchParams({ artifact: artifact.id, context: 'inspect', tab: 'active' })
          queryClient.invalidateQueries({ queryKey: queryKeys.artifacts.all })
        } catch {
          message.error('Failed to restore artifact')
        }
      },
    })
  }, [isStaff, message, modal, queryClient, restoreArtifactMutation, updateSearchParams])

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
  const selectedArtifactFromCatalog = selectedArtifactId
    ? artifacts.find((artifact) => artifact.id === selectedArtifactId) ?? null
    : null
  const selectedArtifactQuery = useArtifact(selectedArtifactId, {
    enabled: isStaff && Boolean(selectedArtifactId) && selectedArtifactFromCatalog === null,
    include_deleted: catalogTab === 'deleted',
    only_deleted: catalogTab === 'deleted',
  })
  const selectedArtifact = selectedArtifactFromCatalog ?? selectedArtifactQuery.data ?? null
  const selectedArtifactLoading = Boolean(selectedArtifactId)
    && selectedArtifact === null
    && selectedArtifactQuery.isLoading
  const selectedArtifactError = Boolean(selectedArtifactId)
    && selectedArtifact === null
    && !selectedArtifactLoading
    ? 'Selected artifact could not be restored. Reload the workspace or choose another artifact from the catalog.'
    : null

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="Artifacts"
          subtitle="Catalog workspace с URL-backed tab/artifact context и canonical secondary surfaces."
          actions={(
            <Space wrap>
              <Button onClick={() => artifactsQuery.refetch()} loading={artifactsQuery.isFetching}>
                Refresh
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => updateSearchParams({ artifact: null, context: 'create' })}
                disabled={!isStaff}
              >
                Add artifact
              </Button>
            </Space>
          )}
        />
      )}
    >
      <Space wrap>
        <Button
          type={catalogTab === 'active' ? 'primary' : 'default'}
          onClick={() => updateSearchParams({ tab: 'active', artifact: null, context: null })}
        >
          Active
        </Button>
        <Button
          type={catalogTab === 'deleted' ? 'primary' : 'default'}
          onClick={() => updateSearchParams({ tab: 'deleted', artifact: null, context: null })}
        >
          Deleted
        </Button>
        <Typography.Text type="secondary">tab={catalogTab}</Typography.Text>
      </Space>

      {!isStaff && (
        <Alert
          type="warning"
          message="Доступ ограничен"
          description="Каталог артефактов доступен только сотрудникам."
        />
      )}

      {artifactsQuery.error && (
        <Alert
          type="error"
          message="Не удалось загрузить артефакты"
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
        onRow={(record) => ({
          onClick: () => handleOpenDetails(record),
          style: { cursor: 'pointer' },
        })}
      />

      <ArtifactsCreateModal
        open={activeContext === 'create'}
        isStaff={isStaff}
        onClose={() => updateSearchParams({ context: null, artifact: selectedArtifactId })}
        onCreated={handleOpenDetails}
      />

      <ArtifactDetailsDrawer
        open={activeContext === 'inspect' && Boolean(selectedArtifactId)}
        artifact={selectedArtifact}
        loading={selectedArtifactLoading}
        error={selectedArtifactError}
        catalogTab={catalogTab}
        isStaff={isStaff}
        onClose={() => updateSearchParams({ artifact: null, context: null })}
        onDeleteArtifact={handleDeleteArtifact}
        onRestoreArtifact={handleRestoreArtifact}
        onOpenPurgeModal={openPurgeModal}
      />

      <ArtifactsPurgeModal
        open={activeContext === 'purge' && Boolean(selectedArtifactId)}
        target={selectedArtifact}
        onClose={() => updateSearchParams({ context: 'inspect', artifact: selectedArtifactId })}
        onDeleted={(artifactId) => {
          if (selectedArtifactId === artifactId) {
            updateSearchParams({ artifact: null, context: null })
          }
        }}
      />
    </WorkspacePage>
  )
}
