import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const targetPath = resolve(process.cwd(), 'src/api/generated/v2/v2.ts')

const bodyImportRegex = /import type { BodyType } from ['"]\.\.\/\.\.\/mutator['"];?/
const mutatorTypeImport = "import type { ErrorType } from '../../mutator';"
const readinessProblemImport =
  "import type { PoolRunConfirmPublicationReadinessProblemDetails } from '../model/poolRunConfirmPublicationReadinessProblemDetails';"

const aliasNeedle = 'export type PostPoolsRunsConfirmPublicationResult = NonNullable<'
const aliasBlock =
  'export type PostPoolsRunsConfirmPublicationError = ErrorType<\n' +
  '  PoolRunConfirmPublicationReadinessProblemDetails\n' +
  '>;\n'

let content = readFileSync(targetPath, 'utf8')

if (!content.includes(mutatorTypeImport)) {
  content = content.replace(bodyImportRegex, (match) => `${match}\n${mutatorTypeImport}`)
}

if (!content.includes(readinessProblemImport)) {
  content = content.replace(mutatorTypeImport, `${mutatorTypeImport}\n${readinessProblemImport}`)
}

if (!content.includes('export type PostPoolsRunsConfirmPublicationError = ErrorType<')) {
  const aliasRegex = /(export type PostPoolsRunsConfirmPublicationResult = [^\n]+\n)/
  const match = content.match(aliasRegex)
  if (!match) {
    throw new Error(`Could not find ${aliasNeedle} block in ${targetPath}`)
  }
  content = content.replace(aliasRegex, `$1${aliasBlock}`)
}

writeFileSync(targetPath, content, 'utf8')
