import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import type { Meta } from '../api/client'
import { AuthProvider } from '../auth/AuthContext'

export const baseMeta: Meta = {
  version: '0.1.0',
  demo_mode: false,
  session_timeout_min: 15,
  decimal_separator: ',',
  tz_display: 'Asia/Tashkent',
}

type Handler = (init: { method: string; body: unknown }) => {
  status?: number
  body?: unknown
  networkError?: boolean
}

/** Routes fetch('/api/v1/<path>') calls to handlers keyed by "METHOD /path". */
export function mockApi(handlers: Record<string, Handler | unknown>) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const path = url.replace('/api/v1', '').split('?')[0]
    const key = `${method} ${path}`
    const entry = handlers[key]
    if (entry === undefined) {
      return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) })
    }
    const result =
      typeof entry === 'function'
        ? (entry as Handler)({
            method,
            body: init?.body ? JSON.parse(String(init.body)) : undefined,
          })
        : { body: entry }
    if (result.networkError) return Promise.reject(new TypeError('Failed to fetch'))
    const status = result.status ?? 200
    return Promise.resolve({
      ok: status < 400,
      status,
      json: () => Promise.resolve(result.body ?? {}),
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function renderWithProviders(ui: ReactElement, route = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}
