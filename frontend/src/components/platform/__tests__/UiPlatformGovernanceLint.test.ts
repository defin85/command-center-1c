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
})
