import { readFile } from 'node:fs/promises'
import { describe, expect, it } from 'vitest'
import {
  FAST_DEFAULT_VITEST_PROJECT,
  HEAVY_ROUTE_PRIMARY_VITEST_PROJECT,
  HEAVY_ROUTE_PROJECT_FILES,
  HEAVY_ROUTE_SECONDARY_VITEST_PROJECT,
  HEAVY_ROUTE_TERTIARY_VITEST_PROJECT,
  HEAVY_ROUTE_TEST_FAMILIES,
  HEAVY_ROUTE_TEST_FILES,
  HEAVY_ROUTE_VITEST_PROJECT_PATTERN,
} from '../test/runtimePerimeters'

type PackageJson = {
  scripts: Record<string, string>
}

const readJson = async <T>(relativePath: string): Promise<T> => {
  const file = await readFile(new URL(relativePath, import.meta.url).pathname, 'utf8')
  return JSON.parse(file) as T
}

const readText = async (relativePath: string): Promise<string> => (
  readFile(new URL(relativePath, import.meta.url).pathname, 'utf8')
)

describe('frontend test runtime governance', () => {
  it('keeps the heavy route inventory explicit and unique', () => {
    const inventory = [...HEAVY_ROUTE_TEST_FILES]
    const families = Object.values(HEAVY_ROUTE_TEST_FAMILIES).flat()

    expect(new Set(inventory).size).toBe(inventory.length)
    expect([...families].sort()).toEqual([...inventory].sort())
  })

  it('partitions fast and heavy Vitest projects without duplicate heavy paths', async () => {
    const vitestConfig = await readText('../../vitest.config.ts')

    expect(vitestConfig).toContain('projects: [')
    expect(vitestConfig).toContain('extends: true')
    expect(vitestConfig).toContain('name: FAST_DEFAULT_VITEST_PROJECT')
    expect(vitestConfig).toContain('exclude: [...defaultExcludes, ...HEAVY_ROUTE_TEST_FILES]')
    expect(vitestConfig).toContain('name: HEAVY_ROUTE_PRIMARY_VITEST_PROJECT')
    expect(vitestConfig).toContain(
      'include: [...HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_PRIMARY_VITEST_PROJECT]]',
    )
    expect(vitestConfig).toContain('name: HEAVY_ROUTE_SECONDARY_VITEST_PROJECT')
    expect(vitestConfig).toContain(
      'include: [...HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_SECONDARY_VITEST_PROJECT]]',
    )
    expect(vitestConfig).toContain('name: HEAVY_ROUTE_TERTIARY_VITEST_PROJECT')
    expect(vitestConfig).toContain(
      'include: [...HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_TERTIARY_VITEST_PROJECT]]',
    )
    expect(vitestConfig).toContain('fileParallelism: false')
    expect(vitestConfig).toContain('maxWorkers: 1')
    expect(vitestConfig).toContain('minWorkers: 1')
    expect(vitestConfig).toContain('groupOrder: 0')
    expect(vitestConfig).toContain('groupOrder: 1')
    expect(vitestConfig).toContain('groupOrder: 2')
    expect(vitestConfig).toContain('groupOrder: 3')
    expect(new Set(HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_PRIMARY_VITEST_PROJECT]).size).toBe(
      HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_PRIMARY_VITEST_PROJECT].length,
    )
    expect(new Set(HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_SECONDARY_VITEST_PROJECT]).size).toBe(
      HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_SECONDARY_VITEST_PROJECT].length,
    )
    expect(new Set(HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_TERTIARY_VITEST_PROJECT]).size).toBe(
      HEAVY_ROUTE_PROJECT_FILES[HEAVY_ROUTE_TERTIARY_VITEST_PROJECT].length,
    )
  })

  it('keeps repo-owned focused commands aligned to canonical projects', async () => {
    const packageJson = await readJson<PackageJson>('../../package.json')

    expect(packageJson.scripts['test:run:changed']).toBe('vitest run --changed')
    expect(packageJson.scripts['test:run:fast']).toBe(
      `vitest run --project ${FAST_DEFAULT_VITEST_PROJECT}`,
    )
    expect(packageJson.scripts['test:run:heavy']).toBe(
      `vitest run --project ${HEAVY_ROUTE_VITEST_PROJECT_PATTERN}`,
    )
    expect(packageJson.scripts['test:run:related']).toBe('vitest related --run')
    expect(packageJson.scripts['test:run:decisions-heavy']).toBe(
      `vitest run --project ${HEAVY_ROUTE_TERTIARY_VITEST_PROJECT} ${HEAVY_ROUTE_TEST_FAMILIES.decisions.join(' ')}`,
    )
    expect(packageJson.scripts['test:run:pools-heavy']).toBe(
      `vitest run --project ${HEAVY_ROUTE_VITEST_PROJECT_PATTERN} ${HEAVY_ROUTE_TEST_FAMILIES.pools.join(' ')}`,
    )
    expect(packageJson.scripts['test:run:pools-catalog']).toBe(
      `vitest run --project ${HEAVY_ROUTE_VITEST_PROJECT_PATTERN} ${HEAVY_ROUTE_TEST_FAMILIES.pools.filter((file) => file.includes('PoolCatalogPage')).join(' ')}`,
    )
    expect(packageJson.scripts['validate:ui-platform:iter']).toBe(
      'npm run generate:api:if-needed && npm run lint && npm run test:run:changed && npm run build:assets',
    )
  })
})
