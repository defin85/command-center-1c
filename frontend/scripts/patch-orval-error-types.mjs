import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const targetPath = resolve(process.cwd(), 'src/api/generated/v2/v2.ts')
const retryRequestPath = resolve(process.cwd(), 'src/api/generated/model/poolRunRetryRequest.ts')
const poolRunPath = resolve(process.cwd(), 'src/api/generated/model/poolRun.ts')
const metadataManagementProfilePath = resolve(
  process.cwd(),
  'src/api/generated/model/databaseMetadataManagementConfigurationProfile.ts'
)

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

let retryRequestContent = readFileSync(retryRequestPath, 'utf8')
// orval currently marks optional retry subset fields as required for this schema.
retryRequestContent = retryRequestContent.replace(
  '  entity_name: string;\n',
  '  entity_name?: string;\n'
)
retryRequestContent = retryRequestContent.replace(
  '  documents_by_database: PoolRunRetryRequestDocumentsByDatabase;\n',
  '  documents_by_database?: PoolRunRetryRequestDocumentsByDatabase;\n'
)
writeFileSync(retryRequestPath, retryRequestContent, 'utf8')

let poolRunContent = readFileSync(poolRunPath, 'utf8')
// orval currently drops `null` from nullable $ref fields on PoolRun.
poolRunContent = poolRunContent.replace(
  '  master_data_gate?: PoolRunMasterDataGate;\n',
  '  master_data_gate?: PoolRunMasterDataGate | null;\n'
)
poolRunContent = poolRunContent.replace(
  '  verification_summary?: PoolRunVerificationSummary;\n',
  '  verification_summary?: PoolRunVerificationSummary | null;\n'
)
poolRunContent = poolRunContent.replace(
  '  workflow_binding?: PoolWorkflowBinding;\n',
  '  workflow_binding?: PoolWorkflowBinding | null;\n'
)
poolRunContent = poolRunContent.replace(
  '  runtime_projection?: PoolRuntimeProjection;\n',
  '  runtime_projection?: PoolRuntimeProjection | null;\n'
)
writeFileSync(poolRunPath, poolRunContent, 'utf8')

let metadataManagementProfileContent = readFileSync(metadataManagementProfilePath, 'utf8')
// orval currently skips blocker fields for database metadata management profile.
if (!metadataManagementProfileContent.includes('  reverify_available: boolean;\n')) {
  metadataManagementProfileContent = metadataManagementProfileContent.replace(
    '  publication_drift: boolean;\n',
    '  publication_drift: boolean;\n' +
      '  reverify_available: boolean;\n' +
      '  reverify_blocker_code: string;\n' +
      '  reverify_blocker_message: string;\n' +
      '  reverify_blocking_action: string;\n'
  )
}
writeFileSync(metadataManagementProfilePath, metadataManagementProfileContent, 'utf8')
