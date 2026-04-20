import { describe } from 'vitest'

import {
  registerPoolMasterDataWorkspaceTests,
  setupPoolMasterDataPageTestSuite,
} from './poolMasterDataPageTestHarness'

describe('PoolMasterDataPage workspace', () => {
  setupPoolMasterDataPageTestSuite()
  registerPoolMasterDataWorkspaceTests()
})
