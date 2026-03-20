import path from 'node:path'
import { readdirSync, readFileSync, statSync } from 'node:fs'

import { ESLint } from 'eslint'
import { describe, expect, it } from 'vitest'

const frontendRoot = path.resolve(__dirname, '../../../..')
const eslint = new ESLint({
  cwd: frontendRoot,
  overrideConfigFile: path.join(frontendRoot, 'eslint.config.js'),
})

async function lintSnippet(filePath: string, code: string) {
  const [result] = await eslint.lintText(code, {
    filePath: path.join(frontendRoot, filePath),
  })
  return result.messages
}

function collectSourceFiles(rootPath: string): string[] {
  const entries = readdirSync(rootPath)
  return entries.flatMap((entry) => {
    const absoluteEntry = path.join(rootPath, entry)
    const relativeEntry = path.relative(frontendRoot, absoluteEntry)
    const stat = statSync(absoluteEntry)

    if (stat.isDirectory()) {
      if (entry === 'api' && absoluteEntry.endsWith(path.join('src', 'api'))) {
        return collectSourceFiles(absoluteEntry)
      }
      if (entry === '__tests__' || entry === 'dist') {
        return []
      }
      return collectSourceFiles(absoluteEntry)
    }

    if (!/\.(ts|tsx)$/.test(entry) || /\.test\.(ts|tsx)$/.test(entry)) {
      return []
    }

    return [relativeEntry]
  })
}

describe('ui platform governance lint', () => {
  it('rejects raw Ant container composition in Decisions panel modules', async () => {
    const messages = await lintSnippet(
      'src/pages/Decisions/FutureDecisionPanel.tsx',
      `
        import { Card, Empty } from 'antd'

        export function FutureDecisionPanel() {
          return (
            <Card title="Legacy panel">
              <Empty />
            </Card>
          )
        }
      `,
    )

    expect(messages.some((message) => (
      message.ruleId === 'no-restricted-imports'
        && message.message.includes('platform')
    ))).toBe(true)
  })

  it('rejects raw Ant cards in binding profile authoring modules', async () => {
    const messages = await lintSnippet(
      'src/pages/Pools/BindingProfileFutureEditor.tsx',
      `
        import { Card } from 'antd'

        export function BindingProfileFutureEditor() {
          return <Card title="Binding profile" />
        }
      `,
    )

    expect(messages.some((message) => (
      message.ruleId === 'no-restricted-imports'
        && message.message.includes('platform')
    ))).toBe(true)
  })

  it('rejects raw Ant containers in future operational workspace modules', async () => {
    const messages = await lintSnippet(
      'src/pages/Operations/OperationsWorkspace.tsx',
      `
        import { Card, Row } from 'antd'

        export function OperationsWorkspace() {
          return (
            <Card>
              <Row />
            </Card>
          )
        }
      `,
    )

    expect(messages.some((message) => (
      message.ruleId === 'no-restricted-imports'
        && message.message.includes('Operational workspace modules')
    ))).toBe(true)
  })

  it('rejects raw Ant layout containers in dashboard route modules', async () => {
    const messages = await lintSnippet(
      'src/pages/Dashboard/Dashboard.tsx',
      `
        import { Row, Col, Divider } from 'antd'
        import { DashboardPage, PageHeader } from '../../components/platform'

        export function Dashboard() {
          return (
            <DashboardPage header={<PageHeader title="Dashboard" />}>
              <Divider />
              <Row>
                <Col span={24}>legacy</Col>
              </Row>
            </DashboardPage>
          )
        }
      `,
    )

    expect(messages.some((message) => (
      message.ruleId === 'no-restricted-imports'
        && message.message.includes('Dashboard route')
    ))).toBe(true)
  })

  it('rejects raw Ant layout containers in operations route modules', async () => {
    const messages = await lintSnippet(
      'src/pages/Operations/OperationsPage.tsx',
      `
        import { Card, Drawer, Table } from 'antd'
        import { WorkspacePage, PageHeader } from '../../components/platform'

        export function OperationsPage() {
          return (
            <WorkspacePage header={<PageHeader title="Operations" />}>
              <Card>
                <Table />
                <Drawer open />
              </Card>
            </WorkspacePage>
          )
        }
      `,
    )

    expect(messages.some((message) => (
      message.ruleId === 'no-restricted-imports'
        && message.message.includes('Operations route')
    ))).toBe(true)
  })

  it('rejects raw Ant layout containers in databases route modules', async () => {
    const messages = await lintSnippet(
      'src/pages/Databases/Databases.tsx',
      `
        import { Breadcrumb, Card, Drawer, Table } from 'antd'
        import { WorkspacePage, PageHeader } from '../../components/platform'

        export function Databases() {
          return (
            <WorkspacePage header={<PageHeader title="Databases" />}>
              <Breadcrumb />
              <Card>
                <Table />
                <Drawer open />
              </Card>
            </WorkspacePage>
          )
        }
      `,
    )

    expect(messages.some((message) => (
      message.ruleId === 'no-restricted-imports'
        && message.message.includes('Databases route')
    ))).toBe(true)
  })

  it('rejects raw Ant layout containers in pool catalog route modules', async () => {
    const messages = await lintSnippet(
      'src/pages/Pools/PoolCatalogPage.tsx',
      `
        import { Card, Drawer, Table, Tabs } from 'antd'
        import { WorkspacePage, PageHeader } from '../../components/platform'

        export function PoolCatalogPage() {
          return (
            <WorkspacePage header={<PageHeader title="Pool Catalog" />}>
              <Tabs
                items={[
                  {
                    key: 'pools',
                    label: 'Pools',
                    children: (
                      <Card>
                        <Table />
                        <Drawer open />
                      </Card>
                    ),
                  },
                ]}
              />
            </WorkspacePage>
          )
        }
      `,
    )

    expect(messages.some((message) => (
      message.ruleId === 'no-restricted-imports'
        && message.message.includes('Pool catalog route')
    ))).toBe(true)
  })

  it('rejects raw Ant layout containers in pool runs route modules', async () => {
    const messages = await lintSnippet(
      'src/pages/Pools/PoolRunsPage.tsx',
      `
        import { Card, Table, Tabs } from 'antd'
        import { WorkspacePage, PageHeader } from '../../components/platform'

        export function PoolRunsPage() {
          return (
            <WorkspacePage header={<PageHeader title="Pool Runs" />}>
              <Card title="Run Context" />
              <Tabs
                items={[
                  {
                    key: 'inspect',
                    label: 'Inspect',
                    children: <Table />,
                  },
                ]}
              />
            </WorkspacePage>
          )
        }
      `,
    )

    expect(messages.some((message) => (
      message.ruleId === 'no-restricted-imports'
        && message.message.includes('Pool runs route')
    ))).toBe(true)
  })

  it('rejects raw Ant Modal and Drawer usage in databases management surfaces', async () => {
    const modalMessages = await lintSnippet(
      'src/pages/Databases/components/DatabaseCredentialsModal.tsx',
      `
        import { Modal } from 'antd'

        export function DatabaseCredentialsModal() {
          return <Modal open />
        }
      `,
    )
    const drawerMessages = await lintSnippet(
      'src/pages/Databases/components/ExtensionsDrawer.tsx',
      `
        import { Drawer } from 'antd'

        export function ExtensionsDrawer() {
          return <Drawer open />
        }
      `,
    )

    expect(modalMessages.some((message) => (
      message.ruleId === 'no-restricted-imports'
        && message.message.includes('ModalFormShell')
    ))).toBe(true)
    expect(drawerMessages.some((message) => (
      message.ruleId === 'no-restricted-imports'
        && message.message.includes('DrawerFormShell')
    ))).toBe(true)
  })

  it('rejects raw Ant Descriptions inside future platform modal shells', async () => {
    const messages = await lintSnippet(
      'src/pages/Future/FuturePlatformModal.tsx',
      `
        import { Descriptions } from 'antd'
        import { ModalFormShell } from '../../components/platform'

        export function FuturePlatformModal() {
          return (
            <ModalFormShell open title="Publish immutable revision" onClose={() => {}} onSubmit={() => {}}>
              <Descriptions
                items={[
                  { key: 'workflow', label: 'Workflow', children: 'wf-services-r5' },
                ]}
              />
            </ModalFormShell>
          )
        }
      `,
    )

    expect(messages.some((message) => (
      message.ruleId === 'ui-platform-local/no-legacy-containers-in-platform-shell-modules'
        && message.message.includes('platform-safe summary rows')
    ))).toBe(true)
  })

  it('rejects raw Ant Descriptions inside future platform drawer shells', async () => {
    const messages = await lintSnippet(
      'src/pages/Future/FuturePlatformDrawer.tsx',
      `
        import { Descriptions } from 'antd'
        import { DrawerFormShell } from '../../components/platform'

        export function FuturePlatformDrawer() {
          return (
            <DrawerFormShell open title="Metadata management" onClose={() => {}} onSubmit={() => {}}>
              <Descriptions
                items={[
                  { key: 'snapshot', label: 'Snapshot', children: 'snapshot-1' },
                ]}
              />
            </DrawerFormShell>
          )
        }
      `,
    )

    expect(messages.some((message) => (
      message.ruleId === 'ui-platform-local/no-legacy-containers-in-platform-shell-modules'
        && message.message.includes('platform-safe summary rows')
    ))).toBe(true)
  })

  it('rejects raw Ant Table inside future platform drawer shells', async () => {
    const messages = await lintSnippet(
      'src/pages/Future/FuturePlatformDrawer.tsx',
      `
        import { Table } from 'antd'
        import { DrawerFormShell } from '../../components/platform'

        export function FuturePlatformDrawer() {
          return (
            <DrawerFormShell open title="Metadata management" onClose={() => {}} onSubmit={() => {}}>
              <Table dataSource={[]} columns={[]} />
            </DrawerFormShell>
          )
        }
      `,
    )

    expect(messages.some((message) => (
      message.ruleId === 'ui-platform-local/no-legacy-containers-in-platform-shell-modules'
        && message.message.includes('platform-safe list/summary surfaces')
    ))).toBe(true)
  })

  it('rejects full-document handoff props in audited authenticated modules', async () => {
    const buttonMessages = await lintSnippet(
      'src/pages/Pools/PoolRunsPage.tsx',
      `
        import { Button } from 'antd'

        export function PoolRunsPage() {
          return <Button href="/workflows/executions/run-1">Open Workflow Diagnostics</Button>
        }
      `,
    )
    const breadcrumbMessages = await lintSnippet(
      'src/pages/Databases/Databases.tsx',
      `
        import { Breadcrumb } from 'antd'

        export function Databases() {
          return <Breadcrumb.Item href="/clusters">Clusters</Breadcrumb.Item>
        }
      `,
    )

    expect(buttonMessages.some((message) => (
      message.ruleId === 'no-restricted-syntax'
        && message.message.includes('RouteButton')
    ))).toBe(true)
    expect(breadcrumbMessages.some((message) => (
      message.ruleId === 'no-restricted-syntax'
        && message.message.includes('react-router-dom')
    ))).toBe(true)
  })

  it('keeps shell-owned user context out of authenticated source modules', () => {
    const sourceFiles = collectSourceFiles(path.join(frontendRoot, 'src'))
    const offenders = sourceFiles.filter((relativePath) => {
      if (relativePath === path.join('src', 'api', 'queries', 'me.ts')) {
        return false
      }
      return readFileSync(path.join(frontendRoot, relativePath), 'utf8').includes('useMe(')
    })

    expect(offenders).toEqual([])
  })

  it('keeps shell-owned tenant catalog reads out of authenticated source modules', () => {
    const sourceFiles = collectSourceFiles(path.join(frontendRoot, 'src'))
    const offenders = sourceFiles.filter((relativePath) => {
      if (relativePath === path.join('src', 'api', 'queries', 'tenants.ts')) {
        return false
      }
      return readFileSync(path.join(frontendRoot, relativePath), 'utf8').includes('useMyTenants(')
    })

    expect(offenders).toEqual([])
  })

  it('keeps raw Ant Descriptions and Table out of platform shell modal and drawer modules', () => {
    const sourceFiles = collectSourceFiles(path.join(frontendRoot, 'src'))
    const offenders = sourceFiles.filter((relativePath) => {
      if (!/(Modal|Drawer)\.tsx$/.test(relativePath)) {
        return false
      }

      const source = readFileSync(path.join(frontendRoot, relativePath), 'utf8')
      const usesPlatformShell = source.includes('ModalFormShell') || source.includes('DrawerFormShell')
      const importsLegacyDetailSurface = /import\s*\{[^}]*\b(Descriptions|Table)\b[^}]*\}\s*from ['"]antd['"]/.test(source)

      return usesPlatformShell && importsLegacyDetailSurface
    })

    expect(offenders).toEqual([])
  })
})
