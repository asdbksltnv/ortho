import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DocumentDetail, DocumentField } from '../api/types'
import { mockApi } from '../test/utils'
import { DocumentPage } from './DocumentPage'

const field = (over: Partial<DocumentField>): DocumentField => ({
  key: 'k',
  section: 'Раздел',
  label: 'Поле',
  emr_type: 'text',
  critical: false,
  display: 'value',
  value: null,
  items: null,
  icd: null,
  hint: null,
  missing: false,
  copied: false,
  ...over,
})

const doc = (over: Partial<DocumentDetail> = {}): DocumentDetail => ({
  template_id: 't1_primary_exam',
  title_ru: 'Первичный врачебный осмотр в отделении',
  status: 'generated',
  can_generate: true,
  problems: [],
  generated_at: '2026-03-10T08:00:00+00:00',
  is_outdated: false,
  changed_keys: [],
  all_text: 'Артериальное давление: 130/80',
  fields: [
    field({ key: 'bp', label: 'Артериальное давление', value: '130/80', critical: true }),
    field({ key: 'temp', label: 'Температура', emr_type: 'number', value: '36,6' }),
    field({
      key: 'bmi',
      label: 'ИМТ',
      emr_type: 'calculate',
      display: 'calculate',
      hint: 'Рассчитывается в EMR',
    }),
    field({ key: 'skin', label: 'Кожа', display: 'keep_emr', hint: 'Оставить текст EMR' }),
    field({
      key: 'labs',
      label: 'Лабораторная диагностика',
      emr_type: 'service',
      items: ['ОАК', 'ВИЧ'],
    }),
    field({
      key: 'dx',
      label: 'Основной',
      emr_type: 'icd10',
      icd: [{ code: 'TEST.1', text: 'Тестовый диагноз' }],
    }),
    field({ key: 'pulse', label: 'Пульс', emr_type: 'number', value: '78' }),
  ],
  ...over,
})

let written: string[]

beforeEach(() => {
  written = []
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn((text: string) => (written.push(text), Promise.resolve())) },
  })
})
afterEach(() => vi.unstubAllGlobals())

function renderDoc() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/case/c1/documents/t1_primary_exam']}>
        <Routes>
          <Route path="/case/:id/documents/:templateId" element={<DocumentPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const base = '/cases/c1/documents/t1_primary_exam'

describe('DocumentPage (copy cells)', () => {
  it('shows each field with its label, EMR type badge and value, in order', async () => {
    mockApi({ [`GET ${base}`]: doc() })
    renderDoc()
    const rows = await screen.findAllByRole('listitem', { name: /./ })
    expect(rows.map((r) => r.getAttribute('data-key'))).toEqual([
      'bp',
      'temp',
      'bmi',
      'skin',
      'labs',
      'dx',
      'pulse',
    ])
    expect(screen.getByTestId('value-bp')).toHaveTextContent('130/80')
    expect(screen.getAllByText('Число')).toHaveLength(2)
    expect(screen.getByText('CALCULATE')).toBeInTheDocument()
    expect(screen.getByText('МКБ10')).toBeInTheDocument()
    expect(screen.getByText('Рассчитывается в EMR')).toBeInTheDocument()
    expect(screen.getByText('Оставить текст EMR', { selector: 'strong' })).toBeInTheDocument()
    expect(screen.getByText('TEST.1')).toBeInTheDocument()
  })

  it('copies a value, ticks it and tells the server', async () => {
    let copied = false
    const current = () =>
      doc({ fields: doc().fields.map((f) => (f.key === 'bp' ? { ...f, copied } : f)) })
    const mark = vi.fn(() => {
      copied = true
      return { body: current() }
    })
    mockApi({
      [`GET ${base}`]: () => ({ body: current() }),
      [`POST ${base}/fields/bp/copied`]: mark,
    })
    renderDoc()
    const row = (await screen.findByTestId('value-bp')).closest('li')!
    fireEvent.click(row.querySelector('button')!)
    await waitFor(() => expect(written).toEqual(['130/80']))
    await waitFor(() =>
      expect(mark).toHaveBeenCalledWith({ method: 'POST', body: { copied: true } }),
    )
    expect(await screen.findByLabelText('скопировано')).toBeInTheDocument()
  })

  it('Enter copies the focused field and moves to the next row', async () => {
    mockApi({
      [`GET ${base}`]: doc(),
      [`POST ${base}/fields/bp/copied`]: doc(),
      [`POST ${base}/fields/temp/copied`]: doc(),
    })
    renderDoc()
    const rows = await screen.findAllByRole('listitem', { name: /./ })
    rows[0].focus()
    fireEvent.keyDown(rows[0], { key: 'Enter' })
    await waitFor(() => expect(written).toEqual(['130/80']))
    await waitFor(() => expect(document.activeElement).toBe(rows[1]))
    fireEvent.keyDown(rows[1], { key: 'Enter' })
    await waitFor(() => expect(written).toEqual(['130/80', '36,6']))
    expect(document.activeElement).toBe(rows[2])
  })

  it('Enter on a field with nothing to paste just moves on', async () => {
    mockApi({ [`GET ${base}`]: doc() })
    renderDoc()
    const rows = await screen.findAllByRole('listitem', { name: /./ })
    rows[2].focus() // calculate
    fireEvent.keyDown(rows[2], { key: 'Enter' })
    await waitFor(() => expect(document.activeElement).toBe(rows[3]))
    expect(written).toEqual([])
  })

  it('copies service items as lines and ICD as the code to search for', async () => {
    mockApi({
      [`GET ${base}`]: doc(),
      [`POST ${base}/fields/labs/copied`]: doc(),
      [`POST ${base}/fields/dx/copied`]: doc(),
    })
    renderDoc()
    const labs = (await screen.findAllByRole('listitem', { name: /./ })).find(
      (r) => r.dataset.key === 'labs',
    )!
    fireEvent.click(labs.querySelector('button')!)
    await waitFor(() => expect(written).toContain('ОАК\nВИЧ'))
    const dx = (await screen.findAllByRole('listitem', { name: /./ })).find(
      (r) => r.dataset.key === 'dx',
    )!
    fireEvent.click(dx.querySelector('button')!)
    await waitFor(() => expect(written).toContain('TEST.1'))
  })

  it('offers a «выбрано» checkbox for ICD fields', async () => {
    const mark = vi.fn(() => doc())
    mockApi({ [`GET ${base}`]: doc(), [`POST ${base}/fields/dx/copied`]: mark })
    renderDoc()
    fireEvent.click(await screen.findByRole('checkbox', { name: 'выбрано' }))
    await waitFor(() =>
      expect(mark).toHaveBeenCalledWith({ method: 'POST', body: { copied: true } }),
    )
  })

  it('copies everything as one labelled text', async () => {
    mockApi({ [`GET ${base}`]: doc(), [`POST ${base}/copy-all`]: doc() })
    renderDoc()
    fireEvent.click(await screen.findByRole('button', { name: 'Скопировать всё одним текстом' }))
    await waitFor(() => expect(written).toEqual(['Артериальное давление: 130/80']))
    expect(await screen.findByText('Текст скопирован')).toBeInTheDocument()
  })

  it('highlights changed fields and offers to regenerate when outdated', async () => {
    const regenerate = vi.fn(() => doc())
    mockApi({
      [`GET ${base}`]: doc({ status: 'outdated', is_outdated: true, changed_keys: ['pulse'] }),
      [`POST ${base}/generate`]: regenerate,
    })
    renderDoc()
    expect(await screen.findByText(/Данные пациента изменились/)).toBeInTheDocument()
    const rows = await screen.findAllByRole('listitem', { name: /./ })
    expect(rows.find((r) => r.dataset.key === 'pulse')).toHaveAttribute('data-changed', 'true')
    expect(rows.find((r) => r.dataset.key === 'bp')).not.toHaveAttribute('data-changed')
    fireEvent.click(screen.getByRole('button', { name: 'Создать заново' }))
    await waitFor(() => expect(regenerate).toHaveBeenCalled())
  })

  it('lists what blocks generation and disables the button', async () => {
    mockApi({
      [`GET ${base}`]: doc({
        status: 'not_generated',
        can_generate: false,
        fields: [],
        problems: [
          { code: 'missing', key: 'bp', message: 'Заполните поле: Артериальное давление' },
          { code: 'gating', key: 'labs_core', message: 'Сначала выполните пункт подготовки' },
        ],
      }),
    })
    renderDoc()
    expect(await screen.findByText('Документ нельзя создать')).toBeInTheDocument()
    expect(screen.getByText('Заполните поле: Артериальное давление')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Создать документ' })).toBeDisabled()
  })

  it('shows «Шаблон ожидается» for templates that have not arrived yet', async () => {
    mockApi({
      [`GET ${base}`]: doc({ status: 'awaiting_template', fields: [], can_generate: false }),
    })
    renderDoc()
    expect(await screen.findByText('Шаблон ожидается')).toBeInTheDocument()
  })
})
