import { readFile } from 'node:fs/promises'
import { describe, expect, it } from 'vitest'

type PackageJson = {
  dependencies: Record<string, string>
  scripts: Record<string, string>
}

const readJson = async <T>(relativePath: string): Promise<T> => {
  const file = await readFile(new URL(relativePath, import.meta.url).pathname, 'utf8')
  return JSON.parse(file) as T
}

const readText = async (relativePath: string): Promise<string> => (
  readFile(new URL(relativePath, import.meta.url).pathname, 'utf8')
)

describe('frontend UI-platform delivery path', () => {
  it('routes build through the full validation gate', async () => {
    const packageJson = await readJson<PackageJson>('../../package.json')

    expect(packageJson.scripts.build).toBe('npm run validate:ui-platform')
    expect(packageJson.scripts['validate:ui-platform']).toBe(
      'npm run generate:api && npm run lint && npm run test:run && npm run test:browser:ui-platform && npm run build:assets',
    )
    expect(packageJson.scripts.analyze).toBe('ANALYZE_BUNDLE=1 npm run build:assets')
  })

  it('keeps the Ant baseline aligned across package and docs', async () => {
    const packageJson = await readJson<PackageJson>('../../package.json')
    const readme = await readText('../../../README.md')
    const runbook = await readText('../../../docs/deployment/frontend-ui-platform-validation-runbook.md')
    const design = await readText('../../../openspec/changes/refactor-ui-platform-on-ant/design.md')

    expect(packageJson.dependencies.antd).toBe('^5.29.3')
    expect(packageJson.dependencies['@ant-design/pro-components']).toBe('^2.8.10')

    expect(readme).toContain('`antd`: `5.29.3`')
    expect(readme).toContain('`@ant-design/pro-components`: `2.8.10`')
    expect(readme).toContain('Default delivery path: `cd frontend && npm run build`')

    expect(runbook).toContain('- `antd`: `5.29.3`')
    expect(runbook).toContain('- `@ant-design/pro-components`: `2.8.10`')
    expect(runbook).toContain('cd frontend && npm run build')
    expect(runbook).toContain('`frontend/Dockerfile` must stay on `RUN npm run build`')

    expect(design).toContain('`antd 5.29.3`')
    expect(design).toContain('`@ant-design/pro-components 2.8.10`')
    expect(design).toContain('`cd frontend && npm run build`')
  })

  it('keeps the repository UI-platform contract explicit in AGENTS', async () => {
    const agents = await readText('../../../AGENTS.md')

    expect(agents).toContain('## UI Platform Contract')
    expect(agents).toContain('`antd` + `@ant-design/pro-components` + project-owned thin design layer')
    expect(agents).toContain('`MasterDetail` на узких viewport обязан деградировать в `list + Drawer`')
    expect(agents).toContain('`ModalFormShell` и `DrawerFormShell` являются canonical entry points')
    expect(agents).toContain('Blocking frontend gate для platform migrations: `npm run lint`, `npm run test:run`, `npm run test:browser:ui-platform`, затем production build.')
  })
})
