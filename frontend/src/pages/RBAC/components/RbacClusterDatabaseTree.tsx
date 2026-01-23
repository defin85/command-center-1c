import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Input, Space, Tree, Typography } from 'antd'
import type { DataNode, TreeProps } from 'antd/es/tree'

import { apiClient } from '../../../api/client'
import type { ClusterRef, DatabaseRef } from '../../../api/queries/rbac'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { clusterKey, databaseKey, loadMoreKey, parseKey } from '../utils/clusterDatabaseTreeKeys'

const { Text } = Typography

const DB_PAGE_SIZE = 50

type ClusterDatabasesState = {
  items: DatabaseRef[]
  total: number
  offset: number
  loading: boolean
}

export function RbacClusterDatabaseTree(props: {
  mode: 'clusters' | 'databases'
  clusters: ClusterRef[]
  value?: string
  onChange: (value: string | undefined) => void
  title?: string
  width?: number
  height?: number
  onDatabasesLoaded?: (items: DatabaseRef[]) => void
  searchPlaceholder?: string
  loadingText?: string
  loadMoreText?: string
  clearLabel?: string
}) {
  const [search, setSearch] = useState<string>('')
  const debouncedSearch = useDebouncedValue(search, 300)
  const [expandedKeys, setExpandedKeys] = useState<string[]>([])
  const [clusterDatabases, setClusterDatabases] = useState<Record<string, ClusterDatabasesState>>({})

  const clusterSearch = props.mode === 'clusters' ? debouncedSearch.trim().toLowerCase() : ''
  const databaseSearch = props.mode === 'databases' ? debouncedSearch.trim() : ''

  useEffect(() => {
    setClusterDatabases({})
    setExpandedKeys([])
  }, [clusterSearch, databaseSearch])

  const filteredClusters = useMemo(() => {
    if (!clusterSearch) return props.clusters
    return props.clusters.filter((c) => (
      c.name.toLowerCase().includes(clusterSearch) || c.id.toLowerCase().includes(clusterSearch)
    ))
  }, [props.clusters, clusterSearch])

  const selectedKeys = useMemo(() => {
    if (!props.value) return []
    return [props.mode === 'clusters' ? clusterKey(props.value) : databaseKey(props.value)]
  }, [props.mode, props.value])

  const loadingText = props.loadingText ?? 'Loading\u2026'
  const loadMoreText = props.loadMoreText ?? 'Load more\u2026'

  const treeData: DataNode[] = useMemo(() => {
    return filteredClusters.map((cluster) => {
      const st = clusterDatabases[cluster.id]

      const children: DataNode[] | undefined = st
        ? [
            ...st.items.map((db) => ({
              key: databaseKey(db.id),
              title: (
                <span>
                  {db.name} <Text type="secondary">#{db.id}</Text>
                </span>
              ),
              isLeaf: true,
              selectable: props.mode === 'databases',
            })),
	            ...(st.loading
	              ? [
	                  {
	                    key: `loading:${cluster.id}`,
	                    title: <Text type="secondary">{loadingText}</Text>,
	                    isLeaf: true,
	                    selectable: false,
	                  },
	                ]
	              : st.items.length < st.total
	                ? [
	                    {
	                      key: loadMoreKey(cluster.id),
	                      title: <Text type="secondary">{loadMoreText}</Text>,
	                      isLeaf: true,
	                    },
	                  ]
	                : []),
	          ]
	        : undefined

      return {
        key: clusterKey(cluster.id),
        title: (
          <span>
            {cluster.name} <Text type="secondary">#{cluster.id}</Text>
          </span>
        ),
	        selectable: props.mode === 'clusters',
	        children,
	      }
	    })
	  }, [filteredClusters, clusterDatabases, loadMoreText, loadingText, props.mode])

  const fetchDatabasesPage = async (clusterId: string, offset: number) => {
    const params: Record<string, unknown> = { cluster_id: clusterId, limit: DB_PAGE_SIZE, offset }
    if (databaseSearch) params.search = databaseSearch
    const response = await apiClient.get('/api/v2/rbac/ref-databases/', { params })
    return response.data as { databases: DatabaseRef[]; count: number; total: number }
  }

  const loadClusterDatabases = async (clusterId: string, mode: 'replace' | 'append') => {
    const existing = clusterDatabases[clusterId]
    const offset = mode === 'append' && existing ? existing.items.length : 0
    if (existing?.loading) return

    setClusterDatabases((prev) => ({
      ...prev,
      [clusterId]: {
        items: mode === 'append' && existing ? existing.items : [],
        total: existing?.total ?? 0,
        offset,
        loading: true,
      },
    }))

    try {
      const page = await fetchDatabasesPage(clusterId, offset)
      props.onDatabasesLoaded?.(page.databases)
      setClusterDatabases((prev) => {
        const current = prev[clusterId]
        const base = mode === 'append' && current ? current.items : []
        const merged = [...base, ...page.databases]
        return {
          ...prev,
          [clusterId]: {
            items: merged,
            total: typeof page.total === 'number' ? page.total : merged.length,
            offset,
            loading: false,
          },
        }
      })
    } catch (_error) {
      setClusterDatabases((prev) => {
        const current = prev[clusterId]
        return {
          ...prev,
          [clusterId]: {
            items: current?.items ?? [],
            total: current?.total ?? 0,
            offset: current?.offset ?? 0,
            loading: false,
          },
        }
      })
    }
  }

  const handleLoadData: TreeProps['loadData'] = async (node) => {
    const key = String(node.key)
    const parsed = parseKey(key)
    if (!parsed) return
    if (parsed.type !== 'cluster') return
    if (clusterDatabases[parsed.id]) return
    await loadClusterDatabases(parsed.id, 'replace')
  }

  const handleSelect: TreeProps['onSelect'] = (keys) => {
    const raw = keys.length > 0 ? String(keys[0]) : ''
    const parsed = parseKey(raw)
    if (!parsed) return

    if (parsed.type === 'load-more') {
      void loadClusterDatabases(parsed.id, 'append')
      return
    }

    if (parsed.type === 'cluster' && props.mode === 'clusters') {
      props.onChange(parsed.id)
      return
    }

    if (parsed.type === 'database' && props.mode === 'databases') {
      props.onChange(parsed.id)
      return
    }
  }

  return (
    <Card title={props.title ?? 'Clusters -> Databases'} size="small" style={{ width: props.width ?? 420 }}>
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        <Input
          placeholder={props.searchPlaceholder ?? (props.mode === 'clusters' ? 'Search clusters' : 'Search databases')}
          allowClear
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div
          style={{
            maxHeight: props.height ?? 520,
            overflow: 'auto',
            border: '1px solid #f0f0f0',
            borderRadius: 6,
            padding: 8,
          }}
        >
          <Tree
            blockNode
            showLine
            treeData={treeData}
            loadData={handleLoadData}
            expandedKeys={expandedKeys}
            selectedKeys={selectedKeys}
            onExpand={(keys) => setExpandedKeys(keys as string[])}
            onSelect={handleSelect}
          />
        </div>
        <Button size="small" disabled={!props.value} onClick={() => props.onChange(undefined)}>
          {props.clearLabel ?? 'Clear selection'}
        </Button>
      </Space>
    </Card>
  )
}
