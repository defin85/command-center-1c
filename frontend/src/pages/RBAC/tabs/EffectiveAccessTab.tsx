import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Select, Space, Table, Typography, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { EffectiveAccessArtifactItem } from '../../../api/generated/model/effectiveAccessArtifactItem'
import type { EffectiveAccessArtifactSourceItem } from '../../../api/generated/model/effectiveAccessArtifactSourceItem'
import type { EffectiveAccessClusterItem } from '../../../api/generated/model/effectiveAccessClusterItem'
import type { EffectiveAccessClusterSourceItem } from '../../../api/generated/model/effectiveAccessClusterSourceItem'
import type { EffectiveAccessDatabaseItem } from '../../../api/generated/model/effectiveAccessDatabaseItem'
import type { EffectiveAccessDatabaseSourceItem } from '../../../api/generated/model/effectiveAccessDatabaseSourceItem'
import type { EffectiveAccessOperationTemplateItem } from '../../../api/generated/model/effectiveAccessOperationTemplateItem'
import type { EffectiveAccessOperationTemplateSourceItem } from '../../../api/generated/model/effectiveAccessOperationTemplateSourceItem'
import type { EffectiveAccessWorkflowTemplateItem } from '../../../api/generated/model/effectiveAccessWorkflowTemplateItem'
import type { EffectiveAccessWorkflowTemplateSourceItem } from '../../../api/generated/model/effectiveAccessWorkflowTemplateSourceItem'
import { useEffectiveAccess, useRbacRefArtifacts, useRbacRefClusters, useRbacRefDatabases, useRbacRefOperationTemplates, useRbacRefWorkflowTemplates, useRbacUsers, type ClusterRef } from '../../../api/queries/rbac'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { RbacResourcePicker } from '../components/RbacResourcePicker'
import { usePaginatedRefSelectOptions } from '../hooks/usePaginatedRefSelectOptions'
import { getEffectiveAccessSourceTagColor } from '../utils/effectiveAccessSourceTag'
import { ensureSelectOptionsContain } from '../utils/selectOptions'

const { Text } = Typography

type RbacPermissionsResourceKey = 'clusters' | 'databases' | 'operation-templates' | 'workflow-templates' | 'artifacts'

const EMPTY_CLUSTER_REFS: ClusterRef[] = []

export function EffectiveAccessTab(props: { canManageRbac: boolean }) {
  const { canManageRbac } = props

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

  const clustersRefQuery = useRbacRefClusters({ limit: 1000, offset: 0 }, { enabled: canManageRbac })
  const clusters = clustersRefQuery.data?.clusters ?? EMPTY_CLUSTER_REFS
  const clusterNameById = useMemo(() => new Map(clusters.map((c) => [c.id, c.name])), [clusters])

  const {
    setSearch: setDatabasesRefSearch,
    options: databasesRefOptions,
    labelById: databasesLabelById,
    query: databasesRefQuery,
    handlePopupScroll: handleDatabasesPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled: canManageRbac,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefDatabases,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.databases,
    getId: (db) => db.id,
    getLabel: (db) => `${db.name} #${db.id}`,
  })

  const {
    setSearch: setOperationTemplatesRefSearch,
    options: operationTemplatesRefOptions,
    labelById: operationTemplatesLabelById,
    query: operationTemplatesRefQuery,
    handlePopupScroll: handleOperationTemplatesPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled: canManageRbac,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefOperationTemplates,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.templates,
    getId: (tpl) => tpl.id,
    getLabel: (tpl) => `${tpl.name} #${tpl.id}`,
  })

  const {
    setSearch: setWorkflowTemplatesRefSearch,
    options: workflowTemplatesRefOptions,
    labelById: workflowTemplatesLabelById,
    query: workflowTemplatesRefQuery,
    handlePopupScroll: handleWorkflowTemplatesPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled: canManageRbac,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefWorkflowTemplates,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.templates,
    getId: (tpl) => tpl.id,
    getLabel: (tpl) => `${tpl.name} #${tpl.id}`,
  })

  const {
    setSearch: setArtifactsRefSearch,
    options: artifactsRefOptions,
    labelById: artifactsLabelById,
    query: artifactsRefQuery,
    handlePopupScroll: handleArtifactsPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled: canManageRbac,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefArtifacts,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.artifacts,
    getId: (artifact) => artifact.id,
    getLabel: (artifact) => `${artifact.name} #${artifact.id}`,
  })

  const [userSearch, setUserSearch] = useState<string>('')
  const debouncedUserSearch = useDebouncedValue(userSearch, 300)
  const usersQuery = useRbacUsers({ search: debouncedUserSearch || undefined, limit: 20, offset: 0 }, { enabled: canManageRbac })
  const userOptions = useMemo(() => {
    const base = usersQuery.data?.users ?? []
    const map = new Map<number, { label: string; value: number }>()
    base.forEach((user) => {
      if (!map.has(user.id)) {
        map.set(user.id, { label: `${user.username} #${user.id}`, value: user.id })
      }
    })
    return Array.from(map.values())
  }, [usersQuery.data?.users])

  const [selectedEffectiveUserId, setSelectedEffectiveUserId] = useState<number | undefined>()
  const [effectiveResourceKey, setEffectiveResourceKey] = useState<RbacPermissionsResourceKey>('databases')
  const [effectiveResourceId, setEffectiveResourceId] = useState<string | undefined>()
  const [effectiveDbPage, setEffectiveDbPage] = useState<number>(1)
  const [effectiveDbPageSize, setEffectiveDbPageSize] = useState<number>(50)

  useEffect(() => {
    setEffectiveResourceId(undefined)
    setEffectiveDbPage(1)
  }, [effectiveResourceKey])

  useEffect(() => {
    setEffectiveDbPage(1)
  }, [effectiveResourceId])

  const handleDatabasesLoaded = (items: Array<{ id: string; name: string }>) => {
    items.forEach((db) => {
      databasesLabelById.current.set(db.id, `${db.name} #${db.id}`)
    })
  }

  const effectiveResourceRef = (() => {
    if (effectiveResourceKey === 'operation-templates') {
      return {
        options: ensureSelectOptionsContain(operationTemplatesRefOptions, [effectiveResourceId], operationTemplatesLabelById.current),
        loading: operationTemplatesRefQuery.isFetching,
        showSearch: true,
        filterOption: false as const,
        onSearch: setOperationTemplatesRefSearch,
        onPopupScroll: handleOperationTemplatesPopupScroll,
      }
    }

    if (effectiveResourceKey === 'workflow-templates') {
      return {
        options: ensureSelectOptionsContain(workflowTemplatesRefOptions, [effectiveResourceId], workflowTemplatesLabelById.current),
        loading: workflowTemplatesRefQuery.isFetching,
        showSearch: true,
        filterOption: false as const,
        onSearch: setWorkflowTemplatesRefSearch,
        onPopupScroll: handleWorkflowTemplatesPopupScroll,
      }
    }

    if (effectiveResourceKey === 'artifacts') {
      return {
        options: ensureSelectOptionsContain(artifactsRefOptions, [effectiveResourceId], artifactsLabelById.current),
        loading: artifactsRefQuery.isFetching,
        showSearch: true,
        filterOption: false as const,
        onSearch: setArtifactsRefSearch,
        onPopupScroll: handleArtifactsPopupScroll,
      }
    }

    return {
      options: ensureSelectOptionsContain(databasesRefOptions, [effectiveResourceId], databasesLabelById.current),
      loading: databasesRefQuery.isFetching,
      showSearch: true,
      filterOption: false as const,
      onSearch: setDatabasesRefSearch,
      onPopupScroll: handleDatabasesPopupScroll,
    }
  })()

  const effectiveResourcePlaceholder = (() => {
    switch (effectiveResourceKey) {
      case 'clusters':
        return 'Кластер (опционально)'
      case 'databases':
        return 'База (опционально)'
      case 'operation-templates':
        return 'Шаблон операции (опционально)'
      case 'workflow-templates':
        return 'Шаблон рабочего процесса (опционально)'
      case 'artifacts':
        return 'Артефакт (опционально)'
    }
  })()

  const effectiveIncludeClusters = effectiveResourceKey === 'clusters'
  const effectiveIncludeDatabases = effectiveResourceKey === 'databases'
  const effectiveIncludeOperationTemplates = effectiveResourceKey === 'operation-templates'
  const effectiveIncludeWorkflowTemplates = effectiveResourceKey === 'workflow-templates'
  const effectiveIncludeArtifacts = effectiveResourceKey === 'artifacts'
  const effectiveDbPaginationEnabled = effectiveIncludeDatabases && !effectiveResourceId

  const effectiveAccessQuery = useEffectiveAccess(selectedEffectiveUserId, {
    includeDatabases: effectiveIncludeDatabases,
    includeClusters: effectiveIncludeClusters,
    includeTemplates: effectiveIncludeOperationTemplates,
    includeWorkflows: effectiveIncludeWorkflowTemplates,
    includeArtifacts: effectiveIncludeArtifacts,
    limit: effectiveDbPaginationEnabled ? effectiveDbPageSize : undefined,
    offset: effectiveDbPaginationEnabled ? (effectiveDbPage - 1) * effectiveDbPageSize : undefined,
    enabled: canManageRbac && Boolean(selectedEffectiveUserId),
  })

  const effectiveSourceLabel = (source: string) => {
    if (source === 'direct') return 'прямое'
    if (source === 'group') return 'группа'
    if (source === 'cluster') return 'кластер'
    return source
  }

  const effectiveClustersColumns: ColumnsType<EffectiveAccessClusterItem> = useMemo(() => [
    {
      title: 'Кластер',
      key: 'cluster',
      render: (_: unknown, row) => (
        <span>
          {row.cluster.name} <Text type="secondary">#{row.cluster.id}</Text>
        </span>
      ),
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
  ], [])

  const effectiveDatabasesColumns: ColumnsType<EffectiveAccessDatabaseItem> = useMemo(() => [
    {
      title: 'База',
      key: 'database',
      render: (_: unknown, row) => (
        <span>
          {row.database.name} <Text type="secondary">#{row.database.id}</Text>
        </span>
      ),
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => {
        const source = row.source
        const color = source === 'direct' ? 'blue' : source === 'group' ? 'purple' : 'gold'
        return <Tag color={color}>{source === 'cluster' ? 'через кластер' : effectiveSourceLabel(source)}</Tag>
      },
    },
    {
      title: 'Через кластер',
      key: 'via_cluster_id',
      render: (_: unknown, row) => {
        if (row.source !== 'cluster') return '-'
        const viaId = row.via_cluster_id
        if (!viaId) return '-'
        const name = clusterNameById.get(viaId)
        return (
          <span>
            {name ?? '-'} <Text type="secondary">#{viaId}</Text>
          </span>
        )
      },
    },
  ], [clusterNameById])

  const effectiveOperationTemplatesColumns: ColumnsType<EffectiveAccessOperationTemplateItem> = useMemo(() => [
    {
      title: 'Шаблон операции',
      key: 'template',
      render: (_: unknown, row) => (
        <span>
          {row.template.name} <Text type="secondary">#{row.template.id}</Text>
        </span>
      ),
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
  ], [])

  const effectiveWorkflowTemplatesColumns: ColumnsType<EffectiveAccessWorkflowTemplateItem> = useMemo(() => [
    {
      title: 'Шаблон рабочего процесса',
      key: 'template',
      render: (_: unknown, row) => (
        <span>
          {row.template.name} <Text type="secondary">#{row.template.id}</Text>
        </span>
      ),
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
  ], [])

  const effectiveArtifactsColumns: ColumnsType<EffectiveAccessArtifactItem> = useMemo(() => [
    {
      title: 'Артефакт',
      key: 'artifact',
      render: (_: unknown, row) => (
        <span>
          {row.artifact.name} <Text type="secondary">#{row.artifact.id}</Text>
        </span>
      ),
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
  ], [])

  const effectiveClusterSourcesColumns: ColumnsType<EffectiveAccessClusterSourceItem> = useMemo(() => [
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
  ], [])

  const effectiveDatabaseSourcesColumns: ColumnsType<EffectiveAccessDatabaseSourceItem> = useMemo(() => [
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
    {
      title: 'Через кластер',
      key: 'via_cluster_id',
      render: (_: unknown, row) => {
        if (row.source !== 'cluster') return '-'
        const viaId = row.via_cluster_id
        if (!viaId) return '-'
        const name = clusterNameById.get(viaId)
        return (
          <span>
            {name ?? '-'} <Text type="secondary">#{viaId}</Text>
          </span>
        )
      },
    },
  ], [clusterNameById])

  const effectiveOperationTemplateSourcesColumns: ColumnsType<EffectiveAccessOperationTemplateSourceItem> = useMemo(() => [
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
  ], [])

  const effectiveWorkflowTemplateSourcesColumns: ColumnsType<EffectiveAccessWorkflowTemplateSourceItem> = useMemo(() => [
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
  ], [])

  const effectiveArtifactSourcesColumns: ColumnsType<EffectiveAccessArtifactSourceItem> = useMemo(() => [
    {
      title: 'Источник',
      key: 'source',
      render: (_: unknown, row) => <Tag color={getEffectiveAccessSourceTagColor(row.source)}>{effectiveSourceLabel(row.source)}</Tag>,
    },
    { title: 'Уровень', dataIndex: 'level', key: 'level' },
  ], [])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="Эффективный доступ" size="small">
        <Space wrap align="start">
          <Select
            style={{ width: 260 }}
            placeholder="Пользователь"
            allowClear
            showSearch
            filterOption={false}
            onSearch={setUserSearch}
            value={selectedEffectiveUserId}
            onChange={(value) => {
              setSelectedEffectiveUserId(value)
              setEffectiveDbPage(1)
            }}
            options={userOptions}
            loading={usersQuery.isFetching}
          />

          <Select
            style={{ width: 260 }}
            value={effectiveResourceKey}
            options={[
              { label: 'Кластеры', value: 'clusters' },
              { label: 'Базы', value: 'databases' },
              { label: 'Шаблоны операций', value: 'operation-templates' },
              { label: 'Шаблоны рабочих процессов', value: 'workflow-templates' },
              { label: 'Артефакты', value: 'artifacts' },
            ]}
            onChange={(value) => setEffectiveResourceKey(value as RbacPermissionsResourceKey)}
          />

          <RbacResourcePicker
            resourceKey={effectiveResourceKey}
            clusters={clusters}
            allowClear
            value={effectiveResourceId}
            onChange={setEffectiveResourceId}
            placeholder={effectiveResourcePlaceholder}
            width={360}
            databaseLabelById={databasesLabelById.current}
            onDatabasesLoaded={handleDatabasesLoaded}
            select={effectiveResourceRef}
            clusterDatabasePickerI18n={clusterDatabasePickerI18n}
          />

          <Button
            data-testid="rbac-effective-access-refresh"
            onClick={() => effectiveAccessQuery.refetch()}
            loading={effectiveAccessQuery.isFetching}
            disabled={!selectedEffectiveUserId}
          >
            Обновить
          </Button>
        </Space>

        {!selectedEffectiveUserId && (
          <Alert
            style={{ marginTop: 12 }}
            type="info"
            message="Выберите пользователя для просмотра"
            description={(
              <Space direction="vertical" size={4}>
                <Text>Выберите пользователя и тип ресурса. Опционально укажите конкретный ресурс для фильтра.</Text>
                <Text type="secondary">Раскрытие строки показывает источники (прямое/группа/через кластер/{'\u2026'})</Text>
              </Space>
            )}
          />
        )}

        {Boolean(effectiveAccessQuery.error) && Boolean(selectedEffectiveUserId) && (
          <Alert
            style={{ marginTop: 12 }}
            type="warning"
            message="Не удалось загрузить эффективный доступ"
          />
        )}
      </Card>

      {selectedEffectiveUserId && (
        <>
          {effectiveResourceKey === 'clusters' && (
            <Card title="Кластеры" size="small">
              <Table
                size="small"
                rowKey={(row) => row.cluster.id}
                columns={effectiveClustersColumns}
                dataSource={(effectiveAccessQuery.data?.clusters ?? []).filter((row) => (
                  !effectiveResourceId || row.cluster.id === effectiveResourceId
                ))}
                loading={effectiveAccessQuery.isFetching}
                expandable={{
                  rowExpandable: (row) => (row.sources ?? []).length > 0,
                  expandedRowRender: (row) => (
                    <Table
                      size="small"
                      columns={effectiveClusterSourcesColumns}
                      dataSource={row.sources ?? []}
                      rowKey={(_, index) => String(index)}
                      pagination={false}
                    />
                  ),
                }}
                pagination={{ pageSize: 50 }}
              />
            </Card>
          )}

          {effectiveResourceKey === 'databases' && (
            <Card title="Базы" size="small">
              <Table
                size="small"
                rowKey={(row) => row.database.id}
                columns={effectiveDatabasesColumns}
                dataSource={(effectiveAccessQuery.data?.databases ?? []).filter((row) => (
                  !effectiveResourceId || row.database.id === effectiveResourceId
                ))}
                loading={effectiveAccessQuery.isFetching}
                expandable={{
                  rowExpandable: (row) => (row.sources ?? []).length > 0,
                  expandedRowRender: (row) => (
                    <Table
                      size="small"
                      columns={effectiveDatabaseSourcesColumns}
                      dataSource={row.sources ?? []}
                      rowKey={(_, index) => String(index)}
                      pagination={false}
                    />
                  ),
                }}
                pagination={effectiveDbPaginationEnabled ? {
                  current: effectiveDbPage,
                  pageSize: effectiveDbPageSize,
                  total: typeof effectiveAccessQuery.data?.databases_total === 'number'
                    ? effectiveAccessQuery.data.databases_total
                    : (effectiveAccessQuery.data?.databases ?? []).length,
                  showSizeChanger: true,
                  onChange: (page, pageSize) => {
                    setEffectiveDbPage(page)
                    setEffectiveDbPageSize(pageSize)
                  },
                } : false}
              />
            </Card>
          )}

          {effectiveResourceKey === 'operation-templates' && (
            <Card title="Шаблоны операций" size="small">
              <Table
                size="small"
                rowKey={(row) => row.template.id}
                columns={effectiveOperationTemplatesColumns}
                dataSource={(effectiveAccessQuery.data?.operation_templates ?? []).filter((row) => (
                  !effectiveResourceId || row.template.id === effectiveResourceId
                ))}
                loading={effectiveAccessQuery.isFetching}
                expandable={{
                  rowExpandable: (row) => (row.sources ?? []).length > 0,
                  expandedRowRender: (row) => (
                    <Table
                      size="small"
                      columns={effectiveOperationTemplateSourcesColumns}
                      dataSource={row.sources ?? []}
                      rowKey={(_, index) => String(index)}
                      pagination={false}
                    />
                  ),
                }}
                pagination={{ pageSize: 50 }}
              />
            </Card>
          )}

          {effectiveResourceKey === 'workflow-templates' && (
            <Card title="Шаблоны рабочих процессов" size="small">
              <Table
                size="small"
                rowKey={(row) => row.template.id}
                columns={effectiveWorkflowTemplatesColumns}
                dataSource={(effectiveAccessQuery.data?.workflow_templates ?? []).filter((row) => (
                  !effectiveResourceId || row.template.id === effectiveResourceId
                ))}
                loading={effectiveAccessQuery.isFetching}
                expandable={{
                  rowExpandable: (row) => (row.sources ?? []).length > 0,
                  expandedRowRender: (row) => (
                    <Table
                      size="small"
                      columns={effectiveWorkflowTemplateSourcesColumns}
                      dataSource={row.sources ?? []}
                      rowKey={(_, index) => String(index)}
                      pagination={false}
                    />
                  ),
                }}
                pagination={{ pageSize: 50 }}
              />
            </Card>
          )}

          {effectiveResourceKey === 'artifacts' && (
            <Card title="Артефакты" size="small">
              <Table
                size="small"
                rowKey={(row) => row.artifact.id}
                columns={effectiveArtifactsColumns}
                dataSource={(effectiveAccessQuery.data?.artifacts ?? []).filter((row) => (
                  !effectiveResourceId || row.artifact.id === effectiveResourceId
                ))}
                loading={effectiveAccessQuery.isFetching}
                expandable={{
                  rowExpandable: (row) => (row.sources ?? []).length > 0,
                  expandedRowRender: (row) => (
                    <Table
                      size="small"
                      columns={effectiveArtifactSourcesColumns}
                      dataSource={row.sources ?? []}
                      rowKey={(_, index) => String(index)}
                      pagination={false}
                    />
                  ),
                }}
                pagination={{ pageSize: 50 }}
              />
            </Card>
          )}
        </>
      )}
    </Space>
  )
}
