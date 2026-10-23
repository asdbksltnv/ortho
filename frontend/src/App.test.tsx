import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { baseMeta, mockApi, renderWithProviders } from './test/utils'

afterEach(() => vi.unstubAllGlobals())

const unauthenticated = { status: 401, body: { code: 'unauthorized', message: 'x', details: {} } }

describe('App shell', () => {
  it('redirects anonymous users to the Russian login form', async () => {
    mockApi({ 'GET /meta': baseMeta, 'GET /auth/me': () => unauthenticated })
    renderWithProviders(<App />)
    expect(await screen.findByRole('button', { name: 'Войти' })).toBeInTheDocument()
    expect(screen.getByLabelText('Логин')).toBeInTheDocument()
  })

  it('shows the demo banner on every page in demo mode', async () => {
    mockApi({
      'GET /meta': { ...baseMeta, demo_mode: true },
      'GET /auth/me': () => unauthenticated,
    })
    renderWithProviders(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Демо-режим: не вводите реальные данные пациентов',
    )
  })

  it('hides the banner outside demo mode', async () => {
    mockApi({ 'GET /meta': baseMeta, 'GET /auth/me': () => unauthenticated })
    renderWithProviders(<App />)
    await screen.findByRole('button', { name: 'Войти' })
    expect(screen.queryByText(/Демо-режим/)).not.toBeInTheDocument()
  })
})
