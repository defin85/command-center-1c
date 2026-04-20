import { describe } from 'vitest'

import {
  registerPoolRunsOperationsTests,
  setupPoolRunsPageTestSuite,
} from './poolRunsPageTestHarness'

describe('PoolRunsPage operations', () => {
  setupPoolRunsPageTestSuite()
  registerPoolRunsOperationsTests()
})
