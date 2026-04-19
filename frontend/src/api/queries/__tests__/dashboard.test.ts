import { beforeEach, describe, expect, it, vi } from 'vitest'

import { queryKeys } from '../queryKeys'

const useQueryMock = vi.fn()
const getOperationsListOperations = vi.fn()
const getDatabasesListDatabases = vi.fn()
const getClustersListClusters = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (...args: unknown[]) => useQueryMock(...args),
}))

vi.mock('../../generated', () => ({
  getV2: () => ({
    getOperationsListOperations,
    getDatabasesListDatabases,
    getClustersListClusters,
  }),
}))

describe('useDashboardQuery', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    getOperationsListOperations.mockReset()
    getDatabasesListDatabases.mockReset()
    getClustersListClusters.mockReset()
    useQueryMock.mockReturnValue({ data: undefined })
  })

  it('uses interval polling without immediate retries', async () => {
    const { useDashboardQuery } = await import('../dashboard')

    useDashboardQuery({ refetchInterval: 15_000 })

    expect(useQueryMock).toHaveBeenCalledWith(expect.objectContaining({
      queryKey: queryKeys.dashboard.stats,
      refetchInterval: 15_000,
      retry: false,
      refetchOnWindowFocus: false,
    }))
  })
})
