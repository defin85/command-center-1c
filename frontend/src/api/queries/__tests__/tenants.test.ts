import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockGet = vi.fn()

vi.mock('../../client', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
  },
}))

describe('fetchMyTenants', () => {
  beforeEach(() => {
    localStorage.clear()
    mockGet.mockReset()
  })

  it('persists active tenant from API response before callers use the result', async () => {
    mockGet.mockResolvedValue({
      data: {
        active_tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        tenants: [
          {
            id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            slug: 'default',
            name: 'Default',
            role: 'admin',
          },
        ],
      },
    })

    const { fetchMyTenants } = await import('../tenants')
    const response = await fetchMyTenants()

    expect(mockGet).toHaveBeenCalledWith('/api/v2/tenants/list-my-tenants/')
    expect(response.active_tenant_id).toBe('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    expect(localStorage.getItem('active_tenant_id')).toBe('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
  })

  it('updates stale localStorage tenant to the server-selected tenant', async () => {
    localStorage.setItem('active_tenant_id', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')
    mockGet.mockResolvedValue({
      data: {
        active_tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        tenants: [
          {
            id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            slug: 'default',
            name: 'Default',
            role: 'admin',
          },
        ],
      },
    })

    const { fetchMyTenants } = await import('../tenants')
    await fetchMyTenants()

    expect(localStorage.getItem('active_tenant_id')).toBe('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
  })
})
