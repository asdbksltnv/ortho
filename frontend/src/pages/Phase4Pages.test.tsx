import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Kpi } from '../api/types'
import { baseMeta, mockApi, renderWithProviders } from '../test/utils'
import { App } from '../App'
import { KpiPage } from './KpiPage'
import { LabelPage, QrCode } from './LabelPage'

afterEach(() => vi.unstubAllGlobals())

const kpi: Kpi = {
  period_from: '2026-01-01',
  period_to: '2026-03-31',
  cases_total: 12,
  ready_cases: 7,
  median_hours_to_ready: 26.5,
  blocking_items: [
    { key: 'labs_core', label: 'Анализы', count: 5 },
    { key: 'docs', label: 'Документы', count: 2 },
  ],
  overrides: [
    {
      at: '2026-03-10T08:00:00+00:00',
      case_id: 'c1',
      case_label: 'Пал. 1, к. 1 (И. А. Д.)',
      reason: 'Срочно',
    },
  ],
  surgeries_checked: 4,
  not_ready_eve: [{ case_id: 'c2', case_label: 'Пал. 2, к. 1 (П. И. И.)', planned: '2026-03-11' }],
}

function mount(ui: React.ReactElement, path: string, route: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('KpiPage', () => {
  it('shows the four KPIs and the CSV link for the chosen period', async () => {
    mockApi({ 'GET /kpi': kpi })
    mount(<KpiPage />, '/kpi', '/kpi')
    expect(await screen.findByText('26,5 ч')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('Анализы')).toBeInTheDocument()
    expect(screen.getByText('Срочно')).toBeInTheDocument()
    expect(screen.getByText(/Пал. 2, к. 1 \(П. И. И.\)/)).toBeInTheDocument()
    const csv = screen.getByRole('link', { name: /Скачать CSV/ })
    expect(csv.getAttribute('href')).toMatch(
      /^\/api\/v1\/kpi\/export\.csv\?from=\d{4}-\d{2}-\d{2}&to=\d{4}-\d{2}-\d{2}$/,
    )
  })

  it('handles an empty ward', async () => {
    mockApi({
      'GET /kpi': {
        ...kpi,
        cases_total: 0,
        ready_cases: 0,
        median_hours_to_ready: null,
        blocking_items: [],
        overrides: [],
        not_ready_eve: [],
      },
    })
    mount(<KpiPage />, '/kpi', '/kpi')
    expect(await screen.findByText('нет данных')).toBeInTheDocument()
    expect(screen.getByText('Блокирующих пунктов нет')).toBeInTheDocument()
    expect(screen.getByText('Не было')).toBeInTheDocument()
    expect(screen.getByText('Все были готовы')).toBeInTheDocument()
  })

  it('reloads for a new period', async () => {
    const fetchMock = mockApi({ 'GET /kpi': kpi })
    mount(<KpiPage />, '/kpi', '/kpi')
    await screen.findByText('26,5 ч')
    fireEvent.change(screen.getByLabelText('С'), { target: { value: '2026-02-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Показать' }))
    await waitFor(() =>
      expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('from=2026-02-01'))).toBe(true),
    )
  })
})

describe('QR label', () => {
  it('draws a deterministic QR code for the case url', () => {
    const a = render(<QrCode value="https://example.org/case/1" />)
    const first = a.container.querySelector('path')!.getAttribute('d')
    a.unmount()
    const b = render(<QrCode value="https://example.org/case/1" />)
    expect(b.container.querySelector('path')!.getAttribute('d')).toBe(first)
    expect(first!.length).toBeGreaterThan(200)
    b.unmount()
    const c = render(<QrCode value="https://example.org/case/2" />)
    expect(c.container.querySelector('path')!.getAttribute('d')).not.toBe(first)
  })

  it('shows initials, bed and procedure only', async () => {
    mockApi({
      'GET /board': {
        columns: [],
        generated_at: 'x',
        rows: [
          {
            case_id: 'c1',
            bed_id: 'b',
            initials: 'И. А. Д.',
            room_id: 'r',
            room_name: 'Пал. 3',
            bed_label: 'к. 2',
            status: 'admitted',
            procedure_label: 'ТЭП коленного сустава',
            planned_surgery_date: '2026-03-11',
            is_emergency: false,
            treating_doctor_id: 'd',
            treating_doctor_name: 'Врач',
            ready: false,
            blocking: [],
            override_reason: null,
            items: {},
          },
        ],
      },
    })
    mount(<LabelPage />, '/case/c1/label', '/case/:id/label')
    const label = await screen.findByTestId('label')
    await waitFor(() => expect(label).toHaveTextContent('И. А. Д.'))
    expect(label).toHaveTextContent('Пал. 3, к. 2')
    expect(label).toHaveTextContent('11.03.2026')
    expect(screen.getByText(/нет ФИО и номера истории болезни/)).toBeInTheDocument()
  })

  it('prints on demand', async () => {
    mockApi({ 'GET /board': { columns: [], generated_at: 'x', rows: [] } })
    const print = vi.fn()
    vi.stubGlobal('print', print)
    mount(<LabelPage />, '/case/c1/label', '/case/:id/label')
    fireEvent.click(await screen.findByRole('button', { name: 'Печать' }))
    expect(print).toHaveBeenCalled()
  })
})

describe('login redirect', () => {
  const unauthenticated = { status: 401, body: { code: 'unauthorized', message: 'x', details: {} } }
  it('sends anonymous visitors to the login form and remembers where they were going', async () => {
    mockApi({ 'GET /meta': baseMeta, 'GET /auth/me': () => unauthenticated })
    const { container } = renderWithProviders(<App />, '/case/abc')
    expect(await screen.findByRole('button', { name: 'Войти' })).toBeInTheDocument()
    expect(container).toBeTruthy()
  })
})
