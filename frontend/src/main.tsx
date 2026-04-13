import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './lib/queryClient'
import App from './App.tsx'
import { I18nProvider } from './i18n'
import './index.css'

const ReactQueryDevtools = import.meta.env.DEV
  ? lazy(async () => {
    const mod = await import('@tanstack/react-query-devtools')
    return { default: mod.ReactQueryDevtools }
  })
  : null

const rootElement = document.getElementById('root')

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <I18nProvider>
          <App />
          {ReactQueryDevtools ? (
            <Suspense fallback={null}>
              <ReactQueryDevtools initialIsOpen={false} />
            </Suspense>
          ) : null}
        </I18nProvider>
      </QueryClientProvider>
    </React.StrictMode>,
  )
} else {
  console.error('Root element not found')
}
