export const FAST_DEFAULT_VITEST_PROJECT = 'fast-default'
export const HEAVY_ROUTE_PRIMARY_VITEST_PROJECT = 'heavy-routes-primary'
export const HEAVY_ROUTE_SECONDARY_VITEST_PROJECT = 'heavy-routes-secondary'
export const HEAVY_ROUTE_TERTIARY_VITEST_PROJECT = 'heavy-routes-tertiary'
export const HEAVY_ROUTE_VITEST_PROJECT_PATTERN = 'heavy-routes-*'

export const HEAVY_ROUTE_TEST_FAMILIES = {
  decisions: ['src/pages/Decisions/__tests__/DecisionsPage.test.tsx'],
  pools: [
    'src/pages/Pools/__tests__/PoolBindingProfilesPage.test.tsx',
    'src/pages/Pools/__tests__/PoolCatalogPage.bindings.test.tsx',
    'src/pages/Pools/__tests__/PoolCatalogPage.core.test.tsx',
    'src/pages/Pools/__tests__/PoolCatalogPage.errors-sync.test.tsx',
    'src/pages/Pools/__tests__/PoolCatalogPage.topology.test.tsx',
    'src/pages/Pools/__tests__/PoolFactualPage.test.tsx',
    'src/pages/Pools/__tests__/PoolMasterDataPage.test.tsx',
    'src/pages/Pools/__tests__/PoolRunsPage.test.tsx',
    'src/pages/Pools/__tests__/PoolTopologyTemplatesPage.test.tsx',
  ],
} as const

export const HEAVY_ROUTE_PROJECT_FILES = {
  [HEAVY_ROUTE_PRIMARY_VITEST_PROJECT]: [
    'src/pages/Pools/__tests__/PoolFactualPage.test.tsx',
    'src/pages/Pools/__tests__/PoolRunsPage.test.tsx',
  ],
  [HEAVY_ROUTE_SECONDARY_VITEST_PROJECT]: [
    'src/pages/Pools/__tests__/PoolCatalogPage.topology.test.tsx',
    'src/pages/Pools/__tests__/PoolMasterDataPage.test.tsx',
  ],
  [HEAVY_ROUTE_TERTIARY_VITEST_PROJECT]: [
    'src/pages/Decisions/__tests__/DecisionsPage.test.tsx',
    'src/pages/Pools/__tests__/PoolBindingProfilesPage.test.tsx',
    'src/pages/Pools/__tests__/PoolCatalogPage.bindings.test.tsx',
    'src/pages/Pools/__tests__/PoolCatalogPage.core.test.tsx',
    'src/pages/Pools/__tests__/PoolCatalogPage.errors-sync.test.tsx',
    'src/pages/Pools/__tests__/PoolTopologyTemplatesPage.test.tsx',
  ],
} as const

export const HEAVY_ROUTE_VITEST_PROJECTS = [
  HEAVY_ROUTE_PRIMARY_VITEST_PROJECT,
  HEAVY_ROUTE_SECONDARY_VITEST_PROJECT,
  HEAVY_ROUTE_TERTIARY_VITEST_PROJECT,
] as const

export const HEAVY_ROUTE_TEST_FILES = [
  ...HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_PRIMARY_VITEST_PROJECT],
  ...HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_SECONDARY_VITEST_PROJECT],
  ...HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_TERTIARY_VITEST_PROJECT],
] as const
