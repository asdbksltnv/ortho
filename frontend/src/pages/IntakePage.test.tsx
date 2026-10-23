import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import config from '../test/intakeConfig.json'
import { mockApi } from '../test/utils'
import { emptyIntake } from '../intake/types'
import { IntakePage } from './IntakePage'

afterEach(() => vi.unstubAllGlobals())

let counter = 0

function renderIntake(options: { canEdit?: boolean; birth?: string } = {}) {
  counter += 1
  const id = `intake-case-${counter}`
  const put = vi.fn(() => ({
    body: {
      data: emptyIntake(),
      schema_version: 1,
      updated_at: 'u2',
      completed_at: null,
      is_new: false,
      can_edit: true,
    },
  }))
  mockApi({
    [`GET /cases/${id}`]: {
      id,
      patient: { birth_date: options.birth ?? '1960-05-17' },
      procedure_key: 'tka',
      procedure_label: 'Тотальное эндопротезирование коленного сустава',
      side: 'left',
    },
    'GET /config/intake': config,
    [`GET /cases/${id}/intake`]: {
      data: emptyIntake(),
      schema_version: 1,
      updated_at: 'u1',
      completed_at: null,
      is_new: true,
      can_edit: options.canEdit ?? true,
    },
    [`PUT /cases/${id}/intake`]: put,
  })
  const client = new QueryClient()
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/case/${id}/intake`]}>
        <Routes>
          <Route path="/case/:id/intake" element={<IntakePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { id, put }
}

const radio = (group: string, name: string) =>
  within(screen.getByRole('radiogroup', { name: group })).getByRole('radio', { name })

describe('IntakePage', () => {
  it('has the 15 EMR sections plus the pre-op extras, with touch-sized controls', async () => {
    renderIntake()
    await screen.findByRole('heading', { name: /1\. Идентификация и план/ })
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(headings).toHaveLength(16)
    expect(headings[9]).toMatch(/Объективный осмотр по системам/)
    const pain = screen.getByRole('radiogroup', { name: 'Боль по ВАШ (0–10)' })
    expect(within(pain).getAllByRole('radio')).toHaveLength(11)
    for (const btn of within(pain).getAllByRole('radio')) expect(btn.className).toMatch(/min-h-11/)
  })

  it('uses a numeric keypad for number fields', async () => {
    renderIntake()
    const pulse = await screen.findAllByRole('textbox', { name: 'Пульс, уд/мин' })
    expect(pulse[0]).toHaveAttribute('inputmode', 'numeric')
    expect(screen.getAllByRole('textbox', { name: 'Температура, °C' })[0]).toHaveAttribute(
      'inputmode',
      'decimal',
    )
  })

  it('sets all six psycho-emotional fields to normal with one tap', async () => {
    renderIntake()
    fireEvent.click(await screen.findByRole('button', { name: 'Всё в норме' }))
    expect(screen.getByRole('textbox', { name: 'Поведение' })).toHaveValue('Адекватное')
    expect(screen.getByRole('textbox', { name: 'Критика к своему заболеванию' })).toHaveValue(
      'Сохранена',
    )
    expect(screen.getByRole('textbox', { name: 'Понимание информации' })).toHaveValue(
      'Понимает в полном объёме',
    )
  })

  it('shows Columbia Q3–6 only after a «да» to Q1 or Q2, and Q7 always', async () => {
    renderIntake()
    await screen.findByRole('heading', { name: /12\./ })
    expect(screen.queryByRole('radiogroup', { name: 'Вопрос 3' })).not.toBeInTheDocument()
    expect(screen.getByRole('radiogroup', { name: 'Вопрос 7' })).toBeInTheDocument()
    fireEvent.click(radio('Вопрос 1', 'Да'))
    for (const n of [3, 4, 5, 6]) {
      expect(screen.getByRole('radiogroup', { name: `Вопрос ${n}` })).toBeInTheDocument()
    }
    fireEvent.click(radio('Вопрос 1', 'Нет'))
    expect(screen.queryByRole('radiogroup', { name: 'Вопрос 3' })).not.toBeInTheDocument()
  })

  it('raises a prominent alert when the urgent-consultation rule is met', async () => {
    renderIntake()
    await screen.findByRole('heading', { name: /12\./ })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    fireEvent.click(radio('Вопрос 2', 'Да'))
    fireEvent.click(radio('Вопрос 4', 'Да'))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    fireEvent.click(radio('Вопрос 6', 'Да'))
    const alerts = await screen.findAllByRole('alert')
    expect(alerts[0]).toHaveTextContent('Выполняется условие срочной консультации')
  })

  it('answers the nutrition BMI question automatically from weight and height', async () => {
    renderIntake()
    await screen.findByRole('heading', { name: /12\./ })
    expect(screen.getByText(/укажите вес и рост/)).toBeInTheDocument()
    fireEvent.change(screen.getAllByRole('textbox', { name: 'Вес, кг' })[0], {
      target: { value: '50' },
    })
    fireEvent.change(screen.getAllByRole('textbox', { name: 'Рост, см' })[0], {
      target: { value: '175' },
    })
    expect(await screen.findByText(/определяется автоматически/)).toBeInTheDocument()
    expect(screen.getByText('ИМТ ниже 20,5 кг/м²:').parentElement).toHaveTextContent('Да')
  })

  it('shows the Caprini total and category live', async () => {
    renderIntake({ birth: '1960-05-17' }) // 65 years old -> 2 points automatically
    const bar = await screen.findByTestId('sync-status')
    const footer = bar.parentElement!
    await waitFor(() => expect(footer).toHaveTextContent(/Caprini:\s*2\s*·\s*Низкий/))
    fireEvent.click(screen.getByRole('checkbox', { name: /Плановое большое эндопротезирование/ }))
    await waitFor(() => expect(footer).toHaveTextContent(/Caprini:\s*7\s*·\s*Высокий/))
    expect(screen.getByRole('checkbox', { name: /Возраст 61–74 года \(авто\)/ })).toBeDisabled()
  })

  it('lets the doctor accept a normal finding or describe a change', async () => {
    renderIntake()
    const group = await screen.findByRole('radiogroup', { name: 'Неврологическая система' })
    fireEvent.click(within(group).getByRole('radio', { name: 'Норма' }))
    expect(screen.getByText('Без очаговой неврологической симптоматики')).toBeInTheDocument()
    const skin = screen.getByRole('radiogroup', { name: 'Кожа' })
    fireEvent.click(within(skin).getByRole('radio', { name: 'Норма' }))
    expect(screen.getByText('Норма (текст не задан отделением)')).toBeInTheDocument()
    fireEvent.click(within(skin).getByRole('radio', { name: 'Изменено' }))
    expect(screen.getByLabelText('Описание изменений')).toBeInTheDocument()
  })

  it('shows the sync state and saves on demand', async () => {
    const { put } = renderIntake()
    const status = await screen.findByTestId('sync-status')
    expect(status).toHaveAttribute('data-state', 'saved')
    fireEvent.click(radio('Есть аллергия?', 'Нет'))
    expect(status).toHaveAttribute('data-state', 'dirty')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(put).toHaveBeenCalled())
    await waitFor(() => expect(status).toHaveAttribute('data-state', 'saved'))
  })

  it('is read-only for users who may not edit the form', async () => {
    renderIntake({ canEdit: false })
    expect(await screen.findByText(/Только просмотр/)).toBeInTheDocument()
    expect(radio('Есть аллергия?', 'Да')).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Завершить приём' })).not.toBeInTheDocument()
  })

  it('notes that the draft holds no identifiers', async () => {
    renderIntake()
    expect(await screen.findByText(/без ФИО и номера истории болезни/)).toBeInTheDocument()
  })
})
