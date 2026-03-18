import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockGetPoolsBindingProfiles = vi.fn()
const mockGetPoolsBindingProfilesDetail = vi.fn()

vi.mock('../generated/v2/v2', () => ({
  getV2: () => ({
    getPoolsBindingProfiles: mockGetPoolsBindingProfiles,
    getPoolsBindingProfilesDetail: mockGetPoolsBindingProfilesDetail,
  }),
}))

import { getBindingProfileDetail, listBindingProfiles } from '../poolBindingProfiles'

describe('poolBindingProfiles api wrappers', () => {
  beforeEach(() => {
    mockGetPoolsBindingProfiles.mockReset()
    mockGetPoolsBindingProfilesDetail.mockReset()
  })

  it('marks binding profile list reads as page-scoped failures', async () => {
    mockGetPoolsBindingProfiles.mockResolvedValue({
      binding_profiles: [],
      count: 0,
    })

    await listBindingProfiles()

    expect(mockGetPoolsBindingProfiles).toHaveBeenCalledWith({ errorPolicy: 'page' })
  })

  it('marks binding profile detail reads as page-scoped failures', async () => {
    mockGetPoolsBindingProfilesDetail.mockResolvedValue({
      binding_profile: {
        binding_profile_id: 'bp-1',
      },
    })

    await getBindingProfileDetail('bp-1')

    expect(mockGetPoolsBindingProfilesDetail).toHaveBeenCalledWith('bp-1', { errorPolicy: 'page' })
  })
})
