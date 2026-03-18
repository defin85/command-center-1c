import type { QueryClient } from '@tanstack/react-query'

import { queryKeys } from '../../api/queries/queryKeys'
import type {
  DatabaseEventProjectionTarget,
  DatabaseEventProjector,
  DatabaseRealtimeEvent,
} from './databaseStreamTypes'

const isDatabaseListQuery = (queryKey: readonly unknown[]) => (
  Array.isArray(queryKey)
  && queryKey[0] === queryKeys.databases.all[0]
  && queryKey[1] === 'list'
)

const isAuthoringReferencesListQuery = (queryKey: readonly unknown[]) => (
  Array.isArray(queryKey)
  && queryKey[0] === queryKeys.authoringReferences.all[0]
  && queryKey[1] === 'list'
)

export const getDatabaseEventProjectionTargets = (
  event: DatabaseRealtimeEvent,
): DatabaseEventProjectionTarget[] => {
  const databaseId = typeof event.database_id === 'string' && event.database_id.trim()
    ? event.database_id.trim()
    : ''

  if (event.type !== 'database_update' || !databaseId) {
    return []
  }

  return [
    {
      label: 'databases.list',
      filters: {
        predicate: (query) => isDatabaseListQuery(query.queryKey),
      },
    },
    {
      label: 'databases.detail',
      filters: {
        queryKey: queryKeys.databases.detail(databaseId),
      },
    },
    {
      label: 'databases.extensionsSnapshot',
      filters: {
        queryKey: queryKeys.databases.extensionsSnapshot(databaseId),
      },
    },
    {
      label: 'databases.metadataManagement',
      filters: {
        queryKey: queryKeys.databases.metadataManagement(databaseId),
      },
    },
    {
      label: 'authoringReferences.list',
      filters: {
        predicate: (query) => isAuthoringReferencesListQuery(query.queryKey),
      },
    },
  ]
}

export const projectDatabaseStreamEvent = async (
  queryClient: QueryClient,
  event: DatabaseRealtimeEvent,
) => {
  const targets = getDatabaseEventProjectionTargets(event)
  for (const target of targets) {
    await queryClient.invalidateQueries(target.filters)
  }
}

export const createDatabaseEventProjector = (): DatabaseEventProjector => ({
  project: projectDatabaseStreamEvent,
})
