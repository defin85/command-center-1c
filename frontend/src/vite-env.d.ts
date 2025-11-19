/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  // Добавь другие переменные окружения по мере необходимости
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
