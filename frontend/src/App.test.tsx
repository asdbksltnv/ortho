import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { Meta } from './api/client'

const baseMeta: Meta = {
  version: '0.1.0',
  demo_mode: false,
  session_timeout_min: 15,
  decimal_separator: ',',
  tz_display: 'Asia/Tashkent',
}

function mockMeta(meta: Meta) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(meta) }))
}

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('App shell', () => {
  it('renders the Russian home page', async () => {
    mockMeta(baseMeta)
    renderApp()
    expect(await screen.findByText(/Каркас приложения запущен/)).toBeInTheDocument()
  })

  it('shows the demo banner in demo mode', async () => {
    mockMeta({ ...baseMeta, demo_mode: true })
    renderApp()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Демо-режим: не вводите реальные данные пациентов',
    )
  })

  it('hides the banner outside demo mode', async () => {
    mockMeta(baseMeta)
    renderApp()
    await screen.findByText(/Каркас приложения запущен/)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
