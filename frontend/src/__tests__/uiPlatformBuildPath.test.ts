import { readFile } from 'node:fs/promises'
import { describe, expect, it } from 'vitest'

type PackageJson = {
  scripts: Record<string, string>
}

const readJson = async <T>(relativePath: string): Promise<T> => {
  const file = await readFile(new URL(relativePath, import.meta.url).pathname, 'utf8')
  return JSON.parse(file) as T
}

describe('frontend UI-platform delivery path', () => {
  it('routes build through the full validation gate', async () => {
    const packageJson = await readJson<PackageJson>('../../package.json')

    expect(packageJson.scripts.build).toBe('npm run validate:ui-platform')
    expect(packageJson.scripts['validate:ui-platform']).toBe(
      'npm run generate:api && npm run lint && npm run test:run && npm run test:browser:ui-platform && npm run build:assets',
    )
    expect(packageJson.scripts.analyze).toBe('ANALYZE_BUNDLE=1 npm run build:assets')
  })
})
