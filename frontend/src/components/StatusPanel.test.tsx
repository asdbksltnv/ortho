import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CaseDetail, User } from '../api/types'
import { baseMeta, mockApi, renderWithProviders } from '../test/utils'
import { StatusPanel } from './StatusPanel'

afterEach(() => vi.unstubAllGlobals())

const defs = {
  checklist: [
    { key: 'labs_core', label_ru: 'Анализы', short_label_ru: 'Анализы', owner_role: 'nurse' },
    {
      key: 'consent_surgical',
      label_ru: 'Согласие',
      short_label_ru: 'Согласие',
      owner_role: 'doctor',
    },
  ],
  procedures: [],
}

const detail = (over: Partial<CaseDetail> = {}): CaseDetail =>
  ({
    id: 'c1',
    status: 'approved_for_surgery',
    planned_surgery_date: '2026-03-11',
    planned_surgery_time: null,
    override_reason: null,
    is_emergency: false,
    readiness: { ready: false, blocking: ['labs_core', 'consent_surgical'] },
    available_transitions: ['called_to_or'],
    ...over,
  }) as CaseDetail

const user = (role: User['role']): User => ({
  id: 'u',
  login: 'x',
  full_name: 'Тест',
  role,
  is_active: true,
})

function setup(role: User['role'], _d: CaseDetail, extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /meta': baseMeta,
    'GET /auth/me': user(role),
    'GET /config/definitions': defs,
    'GET /cases/c1/events': [],
    ...extra,
  })
}

describe('StatusPanel', () => {
  it('explains what blocks a call to the OR and gives a doctor no way around it', async () => {
    const post = vi.fn()
    setup('doctor', detail(), { 'POST /cases/c1/transition': post })
    renderWithProviders(<StatusPanel detail={detail()} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Вызвать в операционную' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('Пациент не готов к операции. Не хватает:')
    expect(dialog).toHaveTextContent('Анализы')
    expect(dialog).toHaveTextContent('Согласие')
    expect(screen.queryByRole('button', { name: 'Подтвердить' })).not.toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('lets the head override only with a written reason', async () => {
    const post = vi.fn(() => ({ body: detail({ status: 'called_to_or' }) }))
    setup('head_of_department', detail(), { 'POST /cases/c1/transition': post })
    renderWithProviders(<StatusPanel detail={detail()} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Вызвать в операционную' }))
    const confirm = await screen.findByRole('button', { name: 'Подтвердить' })
    expect(confirm).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Причина'), {
      target: { value: 'Освободилась операционная' },
    })
    expect(confirm).toBeEnabled()
    fireEvent.click(confirm)
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith({
        method: 'POST',
        body: { to: 'called_to_or', reason: 'Освободилась операционная' },
      }),
    )
  })

  it('calls a ready case straight away', async () => {
    const ready = detail({ readiness: { ready: true, blocking: [] } })
    const post = vi.fn(() => ({ body: detail({ status: 'called_to_or' }) }))
    setup('doctor', ready, { 'POST /cases/c1/transition': post })
    renderWithProviders(<StatusPanel detail={ready} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Вызвать в операционную' }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith({ method: 'POST', body: { to: 'called_to_or' } }),
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('asks the head for the planned date when approving', async () => {
    const d = detail({
      status: 'in_preparation',
      available_transitions: ['approved_for_surgery'],
      planned_surgery_date: null,
    })
    const post = vi.fn(() => ({ body: detail() }))
    setup('head_of_department', d, { 'POST /cases/c1/transition': post })
    renderWithProviders(<StatusPanel detail={d} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Одобрить к операции' }))
    fireEvent.change(await screen.findByLabelText('Плановая дата операции'), {
      target: { value: '2026-03-12' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить' }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith({
        method: 'POST',
        body: { to: 'approved_for_surgery', planned_surgery_date: '2026-03-12' },
      }),
    )
  })

  it('requires a reason to cancel a call', async () => {
    const d = detail({ status: 'called_to_or', available_transitions: ['approved_for_surgery'] })
    setup('head_of_department', d)
    renderWithProviders(<StatusPanel detail={d} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Отменить вызов' }))
    expect(await screen.findByRole('button', { name: 'Подтвердить' })).toBeDisabled()
  })

  it('shows the override on the case and in the history', async () => {
    const d = detail({
      status: 'called_to_or',
      override_reason: 'Срочно',
      available_transitions: [],
    })
    setup('nurse', d, {
      'GET /cases/c1/events': [
        {
          from_status: 'approved_for_surgery',
          to_status: 'called_to_or',
          user_name: 'Заведующий',
          reason: 'Срочно',
          is_override: true,
          created_at: '2026-03-10T08:00:00+00:00',
        },
      ],
    })
    renderWithProviders(<StatusPanel detail={d} />)
    expect(await screen.findAllByText(/Срочно/)).not.toHaveLength(0)
    expect(screen.getByText('Вызов вне готовности:')).toBeInTheDocument()
  })

  it('offers no actions when nothing is available', async () => {
    setup('nurse', detail({ available_transitions: [] }))
    renderWithProviders(<StatusPanel detail={detail({ available_transitions: [] })} />)
    await screen.findByText('Статус и ход лечения')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
