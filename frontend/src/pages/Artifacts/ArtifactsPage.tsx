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
import { useArtifactsTranslation } from '../../i18n'
import { ArtifactsCreateModal } from './ArtifactsCreateModal'
import { ArtifactDetailsDrawer } from './ArtifactDetailsDrawer'
import { ArtifactsPurgeModal } from './ArtifactsPurgeModal'
import { useArtifactsColumns } from './useArtifactsColumns'
import { confirmWithTracking } from '../../observability/confirmWithTracking'

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
  const { t } = useArtifactsTranslation()
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
      message.error(t(($) => $.page.staffPurgeRequired))
      return
    }
    updateSearchParams({
      artifact: artifact.id,
      context: 'purge',
    })
  }, [isStaff, message, t, updateSearchParams])

  const handleDeleteArtifact = useCallback((artifact: Artifact) => {
    if (!isStaff) {
      message.error(t(($) => $.page.staffDeleteRequired))
      return
    }
    confirmWithTracking(modal, {
      title: t(($) => $.confirm.deleteTitle, { name: artifact.name }),
      content: t(($) => $.confirm.deleteDescription),
      okText: t(($) => $.confirm.deleteOk),
      okButtonProps: { danger: true, loading: deleteArtifactMutation.isPending },
      onOk: async () => {
        try {
          await deleteArtifactMutation.mutateAsync(artifact.id)
          message.success(t(($) => $.confirm.deleteSuccess))
          updateSearchParams({ artifact: null, context: null, tab: 'deleted' })
          queryClient.invalidateQueries({ queryKey: queryKeys.artifacts.all })
        } catch {
          message.error(t(($) => $.confirm.deleteFailed))
        }
      },
    }, {
      actionKind: 'operator.action',
      actionName: 'Delete artifact',
      context: {
        artifact_id: artifact.id,
        artifact_name: artifact.name,
      },
    })
  }, [deleteArtifactMutation, isStaff, message, modal, queryClient, t, updateSearchParams])

  const handleRestoreArtifact = useCallback((artifact: Artifact) => {
    if (!isStaff) {
      message.error(t(($) => $.page.staffRestoreRequired))
      return
    }
    confirmWithTracking(modal, {
      title: t(($) => $.confirm.restoreTitle, { name: artifact.name }),
      content: t(($) => $.confirm.restoreDescription),
      okText: t(($) => $.confirm.restoreOk),
      onOk: async () => {
        try {
          await restoreArtifactMutation.mutateAsync(artifact.id)
          message.success(t(($) => $.confirm.restoreSuccess))
          updateSearchParams({ artifact: artifact.id, context: 'inspect', tab: 'active' })
          queryClient.invalidateQueries({ queryKey: queryKeys.artifacts.all })
        } catch {
          message.error(t(($) => $.confirm.restoreFailed))
        }
      },
    }, {
      actionKind: 'operator.action',
      actionName: 'Restore artifact',
      context: {
        artifact_id: artifact.id,
        artifact_name: artifact.name,
      },
    })
  }, [isStaff, message, modal, queryClient, restoreArtifactMutation, t, updateSearchParams])

  const columns = useArtifactsColumns({
    catalogTab,
    isStaff,
    onOpenDetails: handleOpenDetails,
    onDeleteArtifact: handleDeleteArtifact,
    onRestoreArtifact: handleRestoreArtifact,
    onOpenPurgeModal: openPurgeModal,
  })

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: t(($) => $.table.name), sortable: true, groupKey: 'core', groupLabel: t(($) => $.groups.core) },
    { key: 'kind', label: t(($) => $.table.kind), sortable: true, groupKey: 'core', groupLabel: t(($) => $.groups.core) },
    { key: 'tags', label: t(($) => $.table.tags), groupKey: 'meta', groupLabel: t(($) => $.groups.meta) },
    { key: 'purge_after', label: t(($) => $.table.autoPurge), sortable: true, groupKey: 'time', groupLabel: t(($) => $.groups.time) },
    { key: 'created_at', label: t(($) => $.table.created), sortable: true, groupKey: 'time', groupLabel: t(($) => $.groups.time) },
    { key: 'actions', label: t(($) => $.table.actions), groupKey: 'actions', groupLabel: t(($) => $.groups.actions) },
  ], [t])

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
    ? t(($) => $.page.selectedArtifactMissing)
    : null
  const currentTabLabel = catalogTab === 'active'
    ? t(($) => $.page.active)
    : t(($) => $.page.deleted)

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t(($) => $.page.title)}
          subtitle={t(($) => $.page.subtitle)}
          actions={(
            <Space wrap>
              <Button onClick={() => artifactsQuery.refetch()} loading={artifactsQuery.isFetching}>
                {t(($) => $.page.refresh)}
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => updateSearchParams({ artifact: null, context: 'create' })}
                disabled={!isStaff}
              >
                {t(($) => $.page.addArtifact)}
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
          {t(($) => $.page.active)}
        </Button>
        <Button
          type={catalogTab === 'deleted' ? 'primary' : 'default'}
          onClick={() => updateSearchParams({ tab: 'deleted', artifact: null, context: null })}
        >
          {t(($) => $.page.deleted)}
        </Button>
        <Typography.Text type="secondary">
          {t(($) => $.page.currentTab, { value: currentTabLabel })}
        </Typography.Text>
      </Space>

      {!isStaff && (
        <Alert
          type="warning"
          message={t(($) => $.page.accessDeniedTitle)}
          description={t(($) => $.page.accessDeniedDescription)}
        />
      )}

      {artifactsQuery.error && (
        <Alert
          type="error"
          message={t(($) => $.page.loadFailed)}
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
        searchPlaceholder={t(($) => $.page.searchPlaceholder)}
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
