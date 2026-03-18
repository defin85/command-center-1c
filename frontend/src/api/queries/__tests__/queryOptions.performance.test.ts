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

  it('uses bootstrap workload for shell bootstrap', async () => {
    const { useShellBootstrap } = await import('../shellBootstrap')
    const options = useShellBootstrap() as { refetchOnWindowFocus?: boolean; staleTime?: number; meta?: { queryPolicy?: string } }
    expect(options.refetchOnWindowFocus).toBe(false)
    expect(options.staleTime).toBe(5 * 60_000)
    expect(options.meta?.queryPolicy).toBe('bootstrap')
  })

  it('disables refetchOnWindowFocus for RBAC permission checks', async () => {
    const { useCanManageRbac } = await import('../rbac/roles')
    const options = useCanManageRbac() as { refetchOnWindowFocus?: boolean; staleTime?: number; meta?: { queryPolicy?: string } }
    expect(options.refetchOnWindowFocus).toBe(false)
    expect(options.staleTime).toBe(5 * 60_000)
    expect(options.meta?.queryPolicy).toBe('capability')
  })

  it('marks databases list as realtime-backed workload', async () => {
    const { useDatabases } = await import('../databases')
    const options = useDatabases() as { refetchOnWindowFocus?: boolean; meta?: { queryPolicy?: string } }
    expect(options.refetchOnWindowFocus).toBe(false)
    expect(options.meta?.queryPolicy).toBe('realtime-backed')
  })

  it('marks database metadata management reads as interactive workload', async () => {
    const { useDatabaseMetadataManagement } = await import('../databases')
    const options = useDatabaseMetadataManagement({ id: 'db-1' }) as {
      refetchOnWindowFocus?: boolean
      meta?: { queryPolicy?: string }
    }
    expect(options.refetchOnWindowFocus).toBe(false)
    expect(options.meta?.queryPolicy).toBe('interactive')
  })

  it('marks binding profiles queries as interactive workload', async () => {
    const { useBindingProfiles } = await import('../poolBindingProfiles')
    const options = useBindingProfiles() as { refetchOnWindowFocus?: boolean; meta?: { queryPolicy?: string } }
    expect(options.refetchOnWindowFocus).toBe(false)
    expect(options.meta?.queryPolicy).toBe('interactive')
  })
})
