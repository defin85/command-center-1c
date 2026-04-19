import { access, stat } from 'node:fs/promises'
import { constants } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repoRoot = resolve(frontendRoot, '..')

const inputPaths = [
  resolve(frontendRoot, 'orval.config.ts'),
  resolve(frontendRoot, 'scripts/patch-orval-error-types.mjs'),
  resolve(frontendRoot, '../contracts/orchestrator/openapi.yaml'),
  resolve(frontendRoot, '../contracts/api-gateway/openapi.yaml'),
]

const outputPaths = [
  resolve(frontendRoot, 'src/api/generated/v2/v2.ts'),
  resolve(frontendRoot, 'src/api/generated/model/index.ts'),
  resolve(frontendRoot, 'src/api/generated-gateway/index.ts'),
]

const generatedGitPaths = [
  'frontend/src/api/generated',
  'frontend/src/api/generated-gateway',
]

const fileExists = async (path) => {
  try {
    await access(path, constants.F_OK)
    return true
  } catch {
    return false
  }
}

const getMtimeMs = async (path) => (await stat(path)).mtimeMs

const getDirtyGeneratedPaths = () => {
  const status = spawnSync('git', ['status', '--porcelain', '--', ...generatedGitPaths], {
    cwd: repoRoot,
    encoding: 'utf8',
  })

  if (status.error || status.status !== 0) {
    return null
  }

  return status.stdout
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

const runOrval = (reason) => {
  console.log(`[generate:api:if-needed] ${reason}`)
  const result = spawnSync('npx', ['orval'], {
    cwd: frontendRoot,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  })

  if (result.status !== 0) {
    process.exit(result.status ?? 1)
  }
}

const main = async () => {
  const dirtyGeneratedPaths = getDirtyGeneratedPaths()
  if (dirtyGeneratedPaths?.length) {
    console.error(
      '[generate:api:if-needed] generated API clients have local modifications; run `cd frontend && npm run generate:api` after reviewing them.',
    )
    for (const line of dirtyGeneratedPaths) {
      console.error(`  ${line}`)
    }
    process.exit(1)
  }

  const missingOutput = await Promise.any(
    outputPaths.map(async (path) => (!(await fileExists(path)) ? path : Promise.reject(new Error('exists')))),
  ).catch(() => null)

  if (missingOutput) {
    runOrval(`missing generated output: ${missingOutput.replace(`${frontendRoot}/`, '')}`)
    return
  }

  const newestInputMtime = Math.max(...(await Promise.all(inputPaths.map(getMtimeMs))))
  const oldestOutputMtime = Math.min(...(await Promise.all(outputPaths.map(getMtimeMs))))

  if (newestInputMtime > oldestOutputMtime) {
    runOrval('OpenAPI inputs or generator hooks changed since the last client generation')
    return
  }

  console.log('[generate:api:if-needed] generated API clients are up to date')
}

await main()
