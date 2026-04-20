import { describe } from 'vitest'

import {
  registerPoolMasterDataSyncTests,
  setupPoolMasterDataPageTestSuite,
} from './poolMasterDataPageTestHarness'

describe('PoolMasterDataPage sync', () => {
  setupPoolMasterDataPageTestSuite()
  registerPoolMasterDataSyncTests()
})
