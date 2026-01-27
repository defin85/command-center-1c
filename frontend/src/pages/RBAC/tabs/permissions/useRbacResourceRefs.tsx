import type { UIEvent } from 'react'
import { useMemo, useState } from 'react'

import { useRbacRefArtifacts, useRbacRefClusters, useRbacRefDatabases, useRbacRefOperationTemplates, useRbacRefWorkflowTemplates, type ClusterRef } from '../../../../api/queries/rbac'
import { usePaginatedRefSelectOptions } from '../../hooks/usePaginatedRefSelectOptions'
import { ensureSelectOptionsContain } from '../../utils/selectOptions'
import type { RbacPermissionsResourceKey } from './types'

type ResourceRef = {
  options: Array<{ label: string; value: string }>
  loading: boolean
  showSearch: boolean
  filterOption: boolean
  onSearch?: (value: string) => void
  onPopupScroll?: (event: UIEvent<HTMLDivElement>) => void
}

const EMPTY_CLUSTER_REFS: ClusterRef[] = []

export function useRbacResourceRefs(params: {
  enabled: boolean
  resourceKey: RbacPermissionsResourceKey
  selectedResourceIds: Array<string | undefined>
  selectedResourceId: string | undefined
}) {
  const { enabled, resourceKey, selectedResourceIds, selectedResourceId } = params

  const REF_PAGE_SIZE = 50

  const clusterDatabasePickerI18n = useMemo(() => ({
    clearText: 'Очистить',
    modalTitleClusters: 'Выбор кластера',
    modalTitleDatabases: 'Выбор базы',
    treeTitle: 'Ресурсы',
    searchPlaceholderClusters: 'Поиск кластеров',
    searchPlaceholderDatabases: 'Поиск баз',
    loadingText: 'Загрузка…',
    loadMoreText: 'Загрузить ещё…',
    clearSelectionText: 'Снять выбор',
  }), [])

  const clustersRefQuery = useRbacRefClusters({ limit: 1000, offset: 0 }, { enabled })
  const clusters = clustersRefQuery.data?.clusters ?? EMPTY_CLUSTER_REFS
  const clustersSelectOptions = useMemo(() => (
    clusters.map((c) => ({ label: `${c.name} #${c.id}`, value: c.id }))
  ), [clusters])
  const [clustersRefSearch, setClustersRefSearch] = useState<string>('')

  const {
    search: databasesRefSearch,
    setSearch: setDatabasesRefSearch,
    options: databasesRefOptions,
    labelById: databasesLabelById,
    query: databasesRefQuery,
    handlePopupScroll: handleDatabasesPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefDatabases,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.databases,
    getId: (db) => db.id,
    getLabel: (db) => `${db.name} #${db.id}`,
  })

  const {
    search: operationTemplatesRefSearch,
    setSearch: setOperationTemplatesRefSearch,
    options: operationTemplatesRefOptions,
    labelById: operationTemplatesLabelById,
    query: operationTemplatesRefQuery,
    handlePopupScroll: handleOperationTemplatesPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefOperationTemplates,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.templates,
    getId: (tpl) => tpl.id,
    getLabel: (tpl) => `${tpl.name} #${tpl.id}`,
  })

  const {
    search: workflowTemplatesRefSearch,
    setSearch: setWorkflowTemplatesRefSearch,
    options: workflowTemplatesRefOptions,
    labelById: workflowTemplatesLabelById,
    query: workflowTemplatesRefQuery,
    handlePopupScroll: handleWorkflowTemplatesPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefWorkflowTemplates,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.templates,
    getId: (tpl) => tpl.id,
    getLabel: (tpl) => `${tpl.name} #${tpl.id}`,
  })

  const {
    search: artifactsRefSearch,
    setSearch: setArtifactsRefSearch,
    options: artifactsRefOptions,
    labelById: artifactsLabelById,
    query: artifactsRefQuery,
    handlePopupScroll: handleArtifactsPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefArtifacts,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.artifacts,
    getId: (artifact) => artifact.id,
    getLabel: (artifact) => `${artifact.name} #${artifact.id}`,
  })

  const handleDatabasesLoaded = (items: Array<{ id: string; name: string }>) => {
    items.forEach((db) => {
      databasesLabelById.current.set(db.id, `${db.name} #${db.id}`)
    })
  }

  const databasesSelectOptions = ensureSelectOptionsContain(databasesRefOptions, resourceKey === 'databases' ? selectedResourceIds : [], databasesLabelById.current)
  const operationTemplatesSelectOptions = ensureSelectOptionsContain(operationTemplatesRefOptions, resourceKey === 'operation-templates' ? selectedResourceIds : [], operationTemplatesLabelById.current)
  const workflowTemplatesSelectOptions = ensureSelectOptionsContain(workflowTemplatesRefOptions, resourceKey === 'workflow-templates' ? selectedResourceIds : [], workflowTemplatesLabelById.current)
  const artifactsSelectOptions = ensureSelectOptionsContain(artifactsRefOptions, resourceKey === 'artifacts' ? selectedResourceIds : [], artifactsLabelById.current)

  const resourceRef: ResourceRef = (() => {
    if (resourceKey === 'clusters') {
      return {
        options: clustersSelectOptions,
        loading: clustersRefQuery.isFetching,
        showSearch: true,
        filterOption: true,
      }
    }

    if (resourceKey === 'databases') {
      return {
        options: databasesSelectOptions,
        loading: databasesRefQuery.isFetching,
        showSearch: true,
        filterOption: false,
        onSearch: setDatabasesRefSearch,
        onPopupScroll: handleDatabasesPopupScroll,
      }
    }

    if (resourceKey === 'operation-templates') {
      return {
        options: operationTemplatesSelectOptions,
        loading: operationTemplatesRefQuery.isFetching,
        showSearch: true,
        filterOption: false,
        onSearch: setOperationTemplatesRefSearch,
        onPopupScroll: handleOperationTemplatesPopupScroll,
      }
    }

    if (resourceKey === 'workflow-templates') {
      return {
        options: workflowTemplatesSelectOptions,
        loading: workflowTemplatesRefQuery.isFetching,
        showSearch: true,
        filterOption: false,
        onSearch: setWorkflowTemplatesRefSearch,
        onPopupScroll: handleWorkflowTemplatesPopupScroll,
      }
    }

    return {
      options: artifactsSelectOptions,
      loading: artifactsRefQuery.isFetching,
      showSearch: true,
      filterOption: false,
      onSearch: setArtifactsRefSearch,
      onPopupScroll: handleArtifactsPopupScroll,
    }
  })()

  const resourceSearchValue: string = (() => {
    switch (resourceKey) {
      case 'clusters':
        return clustersRefSearch
      case 'databases':
        return databasesRefSearch
      case 'operation-templates':
        return operationTemplatesRefSearch
      case 'workflow-templates':
        return workflowTemplatesRefSearch
      case 'artifacts':
        return artifactsRefSearch
    }
  })()

  const setResourceSearchValue = (value: string) => {
    switch (resourceKey) {
      case 'clusters':
        setClustersRefSearch(value)
        return
      case 'databases':
        setDatabasesRefSearch(value)
        return
      case 'operation-templates':
        setOperationTemplatesRefSearch(value)
        return
      case 'workflow-templates':
        setWorkflowTemplatesRefSearch(value)
        return
      case 'artifacts':
        setArtifactsRefSearch(value)
        return
    }
  }

  const resourceBrowserOptions = useMemo(() => {
    const options = resourceRef.options
    if (resourceKey !== 'clusters') return options
    const query = clustersRefSearch.trim().toLowerCase()
    if (!query) return options
    return options.filter((opt) => (
      opt.label.toLowerCase().includes(query) || opt.value.toLowerCase().includes(query)
    ))
  }, [clustersRefSearch, resourceKey, resourceRef.options])

  const selectedResourceLabel = useMemo(() => {
    if (!selectedResourceId) return undefined
    const match = resourceRef.options.find((opt) => opt.value === selectedResourceId)
    return match?.label ?? selectedResourceId
  }, [resourceRef.options, selectedResourceId])

  const resetSearchForKey = (key: RbacPermissionsResourceKey) => {
    if (key === 'clusters') setClustersRefSearch('')
    if (key === 'databases') setDatabasesRefSearch('')
    if (key === 'operation-templates') setOperationTemplatesRefSearch('')
    if (key === 'workflow-templates') setWorkflowTemplatesRefSearch('')
    if (key === 'artifacts') setArtifactsRefSearch('')
  }

  return {
    clusterDatabasePickerI18n,
    clusters,
    clustersSelectOptions,
    databasesLabelById,
    handleDatabasesLoaded,
    resourceRef,
    resourceSearchValue,
    setResourceSearchValue,
    resourceBrowserOptions,
    selectedResourceLabel,
    resetSearchForKey,
  }
}
