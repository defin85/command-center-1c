export type ClusterDatabaseTreeParsedKey = {
  type: 'cluster' | 'database' | 'load-more'
  id: string
}

export function clusterKey(clusterId: string) {
  return `cluster:${clusterId}`
}

export function databaseKey(databaseId: string) {
  return `database:${databaseId}`
}

export function loadMoreKey(clusterId: string) {
  return `load-more:${clusterId}`
}

export function parseKey(raw: string): ClusterDatabaseTreeParsedKey | null {
  if (raw.startsWith('cluster:')) return { type: 'cluster', id: raw.slice('cluster:'.length) }
  if (raw.startsWith('database:')) return { type: 'database', id: raw.slice('database:'.length) }
  if (raw.startsWith('load-more:')) return { type: 'load-more', id: raw.slice('load-more:'.length) }
  return null
}

