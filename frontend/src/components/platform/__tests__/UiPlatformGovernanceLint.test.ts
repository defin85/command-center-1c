import path from 'node:path'

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
})
