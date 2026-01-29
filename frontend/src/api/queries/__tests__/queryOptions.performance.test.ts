import { describe, expect, it, vi } from 'vitest'

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: unknown) => options,
  useMutation: (options: unknown) => options,
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}))

describe('query options (performance)', () => {
  it('disables refetchOnWindowFocus for me', async () => {
    const { useMe } = await import('../me')
    const options = useMe() as { refetchOnWindowFocus?: boolean; staleTime?: number }
    expect(options.refetchOnWindowFocus).toBe(false)
    expect(options.staleTime).toBe(5 * 60_000)
  })

  it('disables refetchOnWindowFocus for RBAC permission checks', async () => {
    const { useCanManageRbac } = await import('../rbac/roles')
    const options = useCanManageRbac() as { refetchOnWindowFocus?: boolean; staleTime?: number }
    expect(options.refetchOnWindowFocus).toBe(false)
    expect(options.staleTime).toBe(5 * 60_000)
  })
})

