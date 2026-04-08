/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_BASE_HOST?: string
  readonly VITE_CC1C_APP_VERSION?: string
  readonly VITE_CC1C_BUILD_ID?: string
  readonly VITE_WS_HOST?: string
  readonly VITE_DEV_SERVER_URL?: string
  readonly VITE_DEV_SERVER_HOST?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
