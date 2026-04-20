import { describe } from 'vitest'

import {
  registerPoolRunsContextTests,
  setupPoolRunsPageTestSuite,
} from './poolRunsPageTestHarness'

describe('PoolRunsPage context', () => {
  setupPoolRunsPageTestSuite()
  registerPoolRunsContextTests()
})
