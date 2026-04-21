export type UiPlatformBrowserContractShard = Readonly<{
  family: string
  label: string
  path: string
}>

export const UI_PLATFORM_BROWSER_CONTRACT_SHARDS: readonly UiPlatformBrowserContractShard[]
export const UI_PLATFORM_BROWSER_CONTRACT_FAMILIES: readonly string[]
export const UI_PLATFORM_BROWSER_CONTRACT_FILES: readonly string[]
export const UI_PLATFORM_BROWSER_CONTRACT_FAMILY_FILES: Readonly<Record<string, string>>
export const UI_PLATFORM_BROWSER_CONTRACT_RUNNER: string
export const UI_VALIDATION_MEASUREMENT_DEFAULT_SAMPLES: number
export const UI_VALIDATION_ARTIFACT_DIR: string
export const UI_VALIDATION_VITEST_COMMAND: string
export const UI_VALIDATION_BROWSER_COMMAND: string
