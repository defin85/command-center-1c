import { describe } from 'vitest'

import {
  registerPoolMasterDataBootstrapTests,
  setupPoolMasterDataPageTestSuite,
} from './poolMasterDataPageTestHarness'

describe('PoolMasterDataPage bootstrap', () => {
  setupPoolMasterDataPageTestSuite()
  registerPoolMasterDataBootstrapTests()
})
