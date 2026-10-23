import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DocumentDetail, Order, PostOpEntry, PostOpList } from '../api/types'
import { NotificationsBell } from '../components/NotificationsBell'
import config from '../test/intakeConfig.json'
import { baseMeta, mockApi, renderWithProviders } from '../test/utils'
import { DocumentPage } from './DocumentPage'
import { emptyPostOp, PostOpPage } from './PostOpPage'
import { RoundPage } from './RoundPage'
import { TasksPage } from './TasksPage'

afterEach(() => vi.unstubAllGlobals())

const doctor = { id: 'd1', login: 'doc', full_name: 'Тест Врач', role: 'doctor', is_active: true }
const order = (over: Partial<Order> = {}): Order => ({
  id: 'o1',
  case_id: 'c1',
  type: 'lab',
  item: 'ОАК',
  assignee_id: 'n1',
  assignee_name: 'Тест Медсестра',
  status: 'ordered',
  linked_checklist_key: null,
  created_at_round: true,
  created_at: '2026-03-10T08:00:00+00:00',
  case_label: 'Пал. 1, к. 1 (И. А. Д.)',
  next_statuses: ['in_progress'],
  ...over,
})

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

const entry = (over: Partial<PostOpEntry> = {}): PostOpEntry => ({
  id: 'e1',
  case_id: 'c1',
  entered_at: '2026-03-10T08:00:00+00:00',
  entry_date: '2026-03-10',
  post_op_day: 2,
  data: emptyPostOp(),
  alerts: [],
  has_photo: false,
  note: {
    generator: 'template',
    general_condition: '2-е сутки после операции. Боль по ВАШ 3 из 10.',
    local_status: 'Повязка сухая.',
    approved: false,
    approved_at: null,
    approved_by_name: null,
  },
  ...over,
})
const postopList = (over: Partial<PostOpList> = {}): PostOpList => ({
  entries: [entry()],
  trends: [
    {
      day: 2,
      date: '2026-03-10',
      temp: 36.7,
      drain_ml: 120,
      pain: 3,
      discharge: 'нет',
      redness: false,
      swelling: true,
    },
  ],
  can_record: true,
  can_edit: true,
  photo_enabled: false,
  today_entry_id: 'e1',
  ...over,
})

describe('PostOpPage', () => {
  const api = (list: PostOpList, extra: Record<string, unknown> = {}) =>
    mockApi({
      'GET /meta': baseMeta,
      'GET /auth/me': doctor,
      'GET /cases/c1/postop': list,
      'GET /config/intake': config,
      ...extra,
    })

  it('shows the AI/template draft as unchecked until the doctor presses «Проверено»', async () => {
    const approve = vi.fn(() => ({
      body: entry({ note: { ...entry().note!, approved: true, approved_by_name: 'Тест Врач' } }),
    }))
    api(postopList(), { 'POST /cases/c1/postop/e1/note/approve': approve })
    mount(<PostOpPage />, '/case/c1/postop', '/case/:id/postop')
    expect(await screen.findByTestId('note-state')).toHaveTextContent('Черновик')
    const general = screen.getByLabelText('Общее состояние')
    fireEvent.change(general, { target: { value: '2-е сутки после операции. Правка врача.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Проверено' }))
    await waitFor(() =>
      expect(approve).toHaveBeenCalledWith({
        method: 'POST',
        body: {
          general_condition: '2-е сутки после операции. Правка врача.',
          local_status: 'Повязка сухая.',
        },
      }),
    )
  })

  it('renders the day, the trend charts with a table alternative, and wound days', async () => {
    api(postopList())
    mount(<PostOpPage />, '/case/c1/postop', '/case/:id/postop')
    expect((await screen.findAllByText('Температура, °C')).length).toBeGreaterThanOrEqual(2)
    expect(
      screen.getAllByRole('img', { name: /Температура|Дренаж|Боль/ }).length,
    ).toBeGreaterThanOrEqual(3)
    expect(screen.getAllByRole('button', { name: 'Таблица' })).toHaveLength(3)
    expect(screen.getByText('Рана по дням')).toBeInTheDocument()
  })

  it('warns about alerts and hides the form when recording is not possible', async () => {
    api(postopList({ entries: [entry({ alerts: ['temperature'] })] }))
    mount(<PostOpPage />, '/case/c1/postop', '/case/:id/postop')
    expect(await screen.findByRole('alert')).toHaveTextContent('температура выше порога')
  })

  it('is read-only for staff who may not record', async () => {
    api(postopList({ can_edit: false }))
    mount(<PostOpPage />, '/case/c1/postop', '/case/:id/postop')
    expect(await screen.findByText(/Только просмотр/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Проверено' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Сохранить запись' })).not.toBeInTheDocument()
  })

  it('explains when entries cannot be recorded yet', async () => {
    api(postopList({ can_record: false, entries: [], trends: [], today_entry_id: null }))
    mount(<PostOpPage />, '/case/c1/postop', '/case/:id/postop')
    expect(
      await screen.findByText(/после возвращения пациента из операционной/),
    ).toBeInTheDocument()
  })

  it("creates today's entry with the entered vitals", async () => {
    const create = vi.fn(() => ({ body: entry() }))
    api(postopList({ entries: [], trends: [], today_entry_id: null }), {
      'POST /cases/c1/postop': create,
    })
    mount(<PostOpPage />, '/case/c1/postop', '/case/:id/postop')
    fireEvent.change(await screen.findByRole('textbox', { name: 'Температура, °C' }), {
      target: { value: '36,9' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить запись' }))
    await waitFor(() => expect(create).toHaveBeenCalled())
    const sent = (create.mock.calls[0] as unknown[])[0] as {
      body: { data: { vitals: { temp: number } } }
    }
    expect(sent.body.data.vitals.temp).toBe(36.9)
  })

  it('offers photo upload only when storage is enabled', async () => {
    api(postopList({ photo_enabled: false }))
    const first = mount(<PostOpPage />, '/case/c1/postop', '/case/:id/postop')
    expect(await screen.findByText('Загрузка фото отключена')).toBeInTheDocument()
    first.unmount()
    api(postopList({ photo_enabled: true }))
    mount(<PostOpPage />, '/case/c1/postop', '/case/:id/postop')
    expect(await screen.findByText('Прикрепить фото')).toBeInTheDocument()
  })
})

describe('T6 document with a locked draft', () => {
  const field = (key: string, over: Record<string, unknown>) => ({
    key,
    section: 'S',
    label: key,
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
  const doc = (approved: boolean): DocumentDetail =>
    ({
      template_id: 't6_progress_note',
      title_ru: 'Дневниковая запись',
      status: 'generated',
      can_generate: true,
      problems: [],
      generated_at: '2026-03-10T08:00:00+00:00',
      is_outdated: false,
      changed_keys: [],
      all_text: '',
      fields: [
        field('bp', { label: 'АД', value: '120/80' }),
        field('general_condition', { label: 'Описание', value: 'Текст', locked: !approved }),
      ],
    }) as DocumentDetail

  it('disables copying of the draft fields and says why', async () => {
    mockApi({ 'GET /cases/c1/postop/e1/document': doc(false) })
    mount(<DocumentPage />, '/case/c1/postop/e1/document', '/case/:id/postop/:entryId/document')
    const locked = await screen.findByTestId('locked-general_condition')
    expect(locked).toHaveTextContent('Сначала проверьте текст')
    const lockedRow = locked.closest('li')!
    expect(within(lockedRow).queryByRole('button', { name: 'Копировать' })).not.toBeInTheDocument()
    const bpRow = (await screen.findByTestId('value-bp')).closest('li')!
    expect(within(bpRow).getByRole('button', { name: 'Копировать' })).toBeInTheDocument()
  })

  it('enables copying after approval', async () => {
    mockApi({ 'GET /cases/c1/postop/e1/document': doc(true) })
    mount(<DocumentPage />, '/case/c1/postop/e1/document', '/case/:id/postop/:entryId/document')
    const row = (await screen.findByTestId('value-general_condition')).closest('li')!
    expect(within(row).getByRole('button', { name: 'Копировать' })).toBeInTheDocument()
    expect(screen.queryByTestId('locked-general_condition')).not.toBeInTheDocument()
  })
})

describe('Tasks, round mode and notifications', () => {
  it('lists my tasks and moves an order forward', async () => {
    const patch = vi.fn(() => ({ body: order({ status: 'in_progress' }) }))
    mockApi({
      'GET /meta': baseMeta,
      'GET /auth/me': doctor,
      'GET /tasks': [order()],
      'PATCH /orders/o1/status': patch,
    })
    renderWithProviders(<TasksPage />)
    expect(await screen.findByText('Пал. 1, к. 1 (И. А. Д.)')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Взять в работу' }))
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith({ method: 'PATCH', body: { status: 'in_progress' } }),
    )
  })

  it('runs a round: quick order in two taps, then a summary by patient and assignee', async () => {
    const board = {
      columns: [],
      generated_at: 'x',
      rows: [
        {
          case_id: 'c1',
          bed_id: 'b1',
          initials: 'И. А. Д.',
          room_id: 'r',
          room_name: 'Пал. 1',
          bed_label: 'к. 1',
          status: 'in_preparation',
          procedure_label: 'ТЭП',
          planned_surgery_date: null,
          is_emergency: false,
          treating_doctor_id: 'd1',
          treating_doctor_name: 'Врач',
          ready: false,
          blocking: ['docs'],
          override_reason: null,
          items: {},
        },
        {
          case_id: 'c2',
          bed_id: 'b2',
          initials: 'П. И. И.',
          room_id: 'r',
          room_name: 'Пал. 1',
          bed_label: 'к. 2',
          status: 'in_preparation',
          procedure_label: 'ТЭП',
          planned_surgery_date: null,
          is_emergency: false,
          treating_doctor_id: 'd1',
          treating_doctor_name: 'Врач',
          ready: true,
          blocking: [],
          override_reason: null,
          items: {},
        },
      ],
    }
    const fromSet = vi.fn(() => ({ body: [order()] }))
    mockApi({
      'GET /meta': baseMeta,
      'GET /auth/me': doctor,
      'GET /board': board,
      'GET /staff': [{ id: 'n1', full_name: 'Тест Медсестра', role: 'nurse' }],
      'GET /order-sets': [
        { key: 'repeat_cbc', name_ru: 'Повторный ОАК', orders: [{ type: 'lab', item: 'ОАК' }] },
      ],
      'POST /cases/c1/orders/from-set': fromSet,
      'GET /orders/round-summary': [order()],
    })
    renderWithProviders(<RoundPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Начать обход' }))
    expect(await screen.findByText(/Пал. 1, к. 1 · И. А. Д./)).toBeInTheDocument()
    expect(screen.getByText('Пациент 1 из 2')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Исполнитель'), { target: { value: 'n1' } }) // tap 1
    fireEvent.click(screen.getByRole('button', { name: 'Повторный ОАК' })) // tap 2
    await waitFor(() =>
      expect(fromSet).toHaveBeenCalledWith({
        method: 'POST',
        body: { set_key: 'repeat_cbc', assignee_id: 'n1', created_at_round: true },
      }),
    )
    expect(await screen.findByText('Добавлено')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Следующий' }))
    expect(await screen.findByText(/к. 2 · П. И. И./)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Завершить обход' }))
    expect(await screen.findByText('Итоги обхода')).toBeInTheDocument()
    expect(await screen.findByText('По пациентам')).toBeInTheDocument()
    expect(screen.getByText('По исполнителям')).toBeInTheDocument()
    expect(screen.getAllByText(/Тест Медсестра/).length).toBeGreaterThan(0)
  })

  it('shows unread notifications in the bell and marks them read', async () => {
    const readAll = vi.fn(() => ({ body: {} }))
    mockApi({
      'GET /notifications': [
        {
          id: 'n1',
          event: 'call_to_or',
          text: 'Пал. 3, к. 2 (А. Д.): вызов в операционную',
          case_id: 'c1',
          created_at: '2026-03-10T08:00:00+00:00',
          read: false,
        },
      ],
      'POST /notifications/read-all': readAll,
    })
    mount(<NotificationsBell />, '/', '/')
    expect(await screen.findByTestId('unread-count')).toHaveTextContent('1')
    fireEvent.click(screen.getByRole('button', { name: /Уведомления/ }))
    expect(
      await screen.findByText('Пал. 3, к. 2 (А. Д.): вызов в операционную'),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Отметить прочитанными' }))
    await waitFor(() => expect(readAll).toHaveBeenCalled())
  })
})
