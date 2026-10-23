import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Board, User } from '../api/types'
import { baseMeta, mockApi, renderWithProviders } from '../test/utils'
import { BoardPage } from './BoardPage'

afterEach(() => vi.unstubAllGlobals())

const nurse: User = {
  id: 'u1',
  login: 'nurse',
  full_name: 'Тест Медсестра',
  role: 'nurse',
  is_active: true,
}
const item = (status: string) => ({
  status,
  note: null,
  updated_at: '2026-03-10T08:00:00+00:00',
  updated_by: null,
})
const board: Board = {
  generated_at: '2026-03-10T08:00:00+00:00',
  columns: [
    {
      key: 'docs',
      label_ru: 'Осмотр и документы (5)',
      short_label_ru: 'Документы',
      owner_role: 'doctor',
    },
    { key: 'labs_core', label_ru: 'Анализы', short_label_ru: 'Анализы', owner_role: 'nurse' },
  ],
  rows: [
    {
      case_id: 'c1',
      bed_id: 'b1',
      initials: 'И. А. Д.',
      room_id: 'r1',
      room_name: 'Пал. 1',
      bed_label: 'к. 2',
      status: 'in_preparation',
      procedure_label: 'Тотальное эндопротезирование коленного сустава',
      planned_surgery_date: '2026-03-11',
      is_emergency: false,
      treating_doctor_id: 'd1',
      treating_doctor_name: 'Тест Врач',
      ready: false,
      blocking: ['labs_core'],
      override_reason: null,
      items: { docs: item('done'), labs_core: item('pending') } as Board['rows'][0]['items'],
    },
  ],
}

describe('BoardPage', () => {
  it('shows initials, bed and status icons — and no full names', async () => {
    mockApi({ 'GET /meta': baseMeta, 'GET /auth/me': nurse, 'GET /board': board })
    const { container } = renderWithProviders(<BoardPage />)
    expect(await screen.findByText('И. А. Д.')).toBeInTheDocument()
    expect(screen.getByText('к. 2')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Выполнено' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'В процессе' })).toBeInTheDocument()
    expect(screen.getByText(/✖ Не готов \(1\)/)).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/Иванов/)
  })

  it('lets a nurse change her own item and posts the expected version', async () => {
    const patch = vi.fn(() => ({ body: { id: 'c1' } }))
    mockApi({
      'GET /meta': baseMeta,
      'GET /auth/me': nurse,
      'GET /board': board,
      'PATCH /cases/c1/checklist/labs_core': patch,
    })
    renderWithProviders(<BoardPage />)
    fireEvent.click(await screen.findByRole('button', { name: /Анализы: В процессе/ }))
    fireEvent.click(await screen.findByRole('radio', { name: /Выполнено/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(patch).toHaveBeenCalled())
    expect(patch).toHaveBeenCalledWith({
      method: 'PATCH',
      body: { status: 'done', note: null, expected_updated_at: '2026-03-10T08:00:00+00:00' },
    })
  })

  it('makes items the nurse does not own read-only', async () => {
    mockApi({ 'GET /meta': baseMeta, 'GET /auth/me': nurse, 'GET /board': board })
    renderWithProviders(<BoardPage />)
    fireEvent.click(
      await screen.findByRole('button', { name: /Осмотр и документы \(5\): Выполнено/ }),
    )
    expect(await screen.findByText('Нет прав на изменение')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Сохранить' })).not.toBeInTheDocument()
  })

  it('shows the other user’s value on a conflict and offers to apply mine', async () => {
    let calls = 0
    mockApi({
      'GET /meta': baseMeta,
      'GET /auth/me': nurse,
      'GET /board': board,
      'PATCH /cases/c1/checklist/labs_core': () => {
        calls += 1
        return calls === 1
          ? {
              status: 409,
              body: {
                code: 'conflict',
                message: 'x',
                details: {
                  current: {
                    status: 'problem',
                    note: 'повторить',
                    updated_at: '2026-03-10T09:00:00+00:00',
                    updated_by: 'Старшая',
                  },
                },
              },
            }
          : { body: { id: 'c1' } }
      },
    })
    renderWithProviders(<BoardPage />)
    fireEvent.click(await screen.findByRole('button', { name: /Анализы: В процессе/ }))
    fireEvent.click(await screen.findByRole('radio', { name: /Выполнено/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByText('Пункт уже изменён другим пользователем')).toBeInTheDocument()
    expect(screen.getByText(/Старшая/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Применить моё значение' }))
    await waitFor(() => expect(calls).toBe(2))
  })
})

describe('BoardPage live updates', () => {
  it("shows another user's change within the 10 s target by polling", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let current = board
    mockApi({
      'GET /meta': baseMeta,
      'GET /auth/me': nurse,
      'GET /board': () => ({ body: current }),
    })
    renderWithProviders(<BoardPage />)
    expect(await screen.findAllByRole('img', { name: 'В процессе' })).toHaveLength(1)

    // A second user marks the lab item done on the server.
    current = {
      ...board,
      rows: [
        {
          ...board.rows[0],
          ready: true,
          blocking: [],
          items: { docs: item('done'), labs_core: item('done') } as Board['rows'][0]['items'],
        },
      ],
    }
    await vi.advanceTimersByTimeAsync(10_000)
    await waitFor(() => expect(screen.queryByRole('img', { name: 'В процессе' })).toBeNull())
    expect(screen.getAllByRole('img', { name: 'Выполнено' })).toHaveLength(2)
    vi.useRealTimers()
  })
})
