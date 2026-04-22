import { describe } from 'vitest'

import {
  registerPoolMasterDataChartImportTests,
  setupPoolMasterDataPageTestSuite,
} from './poolMasterDataPageTestHarness'

describe('PoolMasterDataPage chart import', () => {
  setupPoolMasterDataPageTestSuite()
  registerPoolMasterDataChartImportTests()
})
