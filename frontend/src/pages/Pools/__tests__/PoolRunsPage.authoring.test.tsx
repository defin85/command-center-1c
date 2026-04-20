import { describe } from 'vitest'

import {
  registerPoolRunsAuthoringTests,
  setupPoolRunsPageTestSuite,
} from './poolRunsPageTestHarness'

describe('PoolRunsPage authoring', () => {
  setupPoolRunsPageTestSuite()
  registerPoolRunsAuthoringTests()
})
