import { describe, expect, it, vi } from 'vitest'
import type { QueryClient } from '@tanstack/react-query'

import { queryKeys } from '../../../api/queries/queryKeys'
import { getDatabaseEventProjectionTargets, projectDatabaseStreamEvent } from '../databaseEventProjector'

describe('databaseEventProjector', () => {
  it('projects database update events into scoped query invalidations', async () => {
    const event = {
      type: 'database_update',
      action: 'metadata_updated',
      database_id: 'db-42',
      cluster_id: 'cluster-7',
    }

    const targets = getDatabaseEventProjectionTargets(event)
    expect(targets.map((target) => target.label)).toEqual([
      'databases.list',
      'databases.detail',
      'databases.extensionsSnapshot',
      'databases.metadataManagement',
      'authoringReferences.list',
    ])

    const invalidateQueries = vi.fn().mockResolvedValue(undefined)
    await projectDatabaseStreamEvent(
      { invalidateQueries } as unknown as QueryClient,
      event,
    )

    expect(invalidateQueries).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: queryKeys.databases.detail('db-42') }),
    )
    expect(invalidateQueries).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: queryKeys.databases.extensionsSnapshot('db-42') }),
    )
    expect(invalidateQueries).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: queryKeys.databases.metadataManagement('db-42') }),
    )
    expect(invalidateQueries).toHaveBeenCalledTimes(5)
  })

  it('ignores non-domain events without blanket invalidation', async () => {
    const invalidateQueries = vi.fn().mockResolvedValue(undefined)

    await projectDatabaseStreamEvent(
      { invalidateQueries } as unknown as QueryClient,
      { type: 'database_stream_connected' },
    )

    expect(invalidateQueries).not.toHaveBeenCalled()
  })
})
