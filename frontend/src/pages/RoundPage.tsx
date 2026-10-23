import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Board, Order, OrderSet, Staff } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ORDER_TYPES } from '../components/OrdersPanel'

const ASSIGNEE_KEY = 'orthoready:round-assignee'

function savedAssignee(): string {
  try {
    return window.localStorage.getItem(ASSIGNEE_KEY) ?? ''
  } catch {
    return ''
  }
}

/** Bed-by-bed round mode: orders in two or three taps, then a summary of everything ordered. */
export function RoundPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [started, setStarted] = useState<string | null>(null)
  const [finished, setFinished] = useState(false)
  const [index, setIndex] = useState(0)
  const [mine, setMine] = useState(user?.role === 'doctor')
  const [assignee, setAssignee] = useState(savedAssignee)
  const [type, setType] = useState<(typeof ORDER_TYPES)[number]>('lab')
  const [item, setItem] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const board = useQuery({
    queryKey: ['board', 'round', mine],
    queryFn: () => api.get<Board>(`/board${mine ? '?mine=true' : ''}`),
  })
  const staff = useQuery({ queryKey: ['staff'], queryFn: () => api.get<Staff[]>('/staff') })
  const sets = useQuery({
    queryKey: ['order-sets'],
    queryFn: () => api.get<OrderSet[]>('/order-sets'),
  })
  const summary = useQuery({
    queryKey: ['round-summary', started],
    queryFn: () =>
      api.get<Order[]>(`/orders/round-summary?since=${encodeURIComponent(started ?? '')}`),
    enabled: finished && started !== null,
  })

  const rows = useMemo(() => board.data?.rows ?? [], [board.data])
  const row = rows[index]

  const pickAssignee = (id: string) => {
    setAssignee(id)
    try {
      window.localStorage.setItem(ASSIGNEE_KEY, id)
    } catch {
      // remembering the last assignee is a convenience only
    }
  }

  const done = (message: string) => {
    setError(null)
    setNotice(message)
    setItem('')
    void queryClient.invalidateQueries({ queryKey: ['board'] })
  }
  const fail = (e: unknown) => {
    setNotice(null)
    setError(e instanceof ApiError ? e.message : t('errors.unknown'))
  }
  const fromSet = useMutation({
    mutationFn: (key: string) =>
      api.post(`/cases/${row.case_id}/orders/from-set`, {
        set_key: key,
        assignee_id: assignee,
        created_at_round: true,
      }),
    onSuccess: () => done(t('round.added')),
    onError: fail,
  })
  const custom = useMutation({
    mutationFn: (text: string) =>
      api.post(`/cases/${row.case_id}/orders`, {
        type,
        item: text,
        assignee_id: assignee,
        created_at_round: true,
      }),
    onSuccess: () => done(t('round.added')),
    onError: fail,
  })

  if (!user) return null

  if (finished) {
    const orders = summary.data ?? []
    const group = (key: (o: Order) => string) =>
      Object.entries(
        orders.reduce<Record<string, Order[]>>((acc, o) => {
          ;(acc[key(o)] ??= []).push(o)
          return acc
        }, {}),
      )
    return (
      <main className="mx-auto max-w-3xl px-3 py-4">
        <h1 className="text-xl font-bold">{t('round.summary')}</h1>
        <p className="mt-1 text-sm">
          {t('round.orderCount')}: <strong>{orders.length}</strong>
        </p>
        {summary.isSuccess && orders.length === 0 && <p className="mt-3">{t('round.noOrders')}</p>}
        <section className="mt-4" aria-labelledby="by-patient">
          <h2 id="by-patient" className="font-semibold">
            {t('round.byPatient')}
          </h2>
          {group((o) => o.case_label).map(([label, list]) => (
            <div key={label} className="mt-2 rounded border border-slate-300 bg-white p-2">
              <Link
                to={`/case/${list[0].case_id}`}
                className="font-semibold text-teal-800 underline"
              >
                {label}
              </Link>
              <ul className="mt-1 text-sm">
                {list.map((o) => (
                  <li key={o.id}>
                    {t(`orders.types.${o.type}`)}: {o.item} → {o.assignee_name}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
        <section className="mt-4" aria-labelledby="by-assignee">
          <h2 id="by-assignee" className="font-semibold">
            {t('round.byAssignee')}
          </h2>
          {group((o) => o.assignee_name).map(([name, list]) => (
            <div key={name} className="mt-2 rounded border border-slate-300 bg-white p-2">
              <strong>{name}</strong>
              <ul className="mt-1 text-sm">
                {list.map((o) => (
                  <li key={o.id}>
                    {o.case_label}: {t(`orders.types.${o.type}`)} — {o.item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
        <button
          type="button"
          className="mt-4 min-h-11 rounded bg-teal-700 px-4 text-white"
          onClick={() => {
            setFinished(false)
            setStarted(null)
            setIndex(0)
          }}
        >
          {t('round.newRound')}
        </button>
      </main>
    )
  }

  if (!started) {
    return (
      <main className="mx-auto max-w-xl px-3 py-4">
        <h1 className="text-xl font-bold">{t('round.title')}</h1>
        {user.role === 'doctor' && (
          <label className="mt-3 flex min-h-11 items-center gap-3">
            <input
              type="checkbox"
              className="h-5 w-5"
              checked={mine}
              onChange={(e) => setMine(e.target.checked)}
            />
            {t('round.mine')}
          </label>
        )}
        {rows.length === 0 && board.isSuccess && <p className="mt-3">{t('round.noPatients')}</p>}
        <button
          type="button"
          disabled={rows.length === 0}
          onClick={() => setStarted(new Date().toISOString())}
          className="mt-4 min-h-11 rounded bg-teal-700 px-6 font-medium text-white disabled:opacity-50"
        >
          {t('round.start')}
        </button>
      </main>
    )
  }

  if (!row) return null
  const typeSets = (sets.data ?? []).filter((s) => s.orders.every((o) => o.type === type))
  const suggestions = [
    ...new Set(
      (sets.data ?? [])
        .flatMap((s) => s.orders)
        .filter((o) => o.type === type)
        .map((o) => o.item),
    ),
  ]
  const last = index === rows.length - 1

  return (
    <main className="mx-auto max-w-xl px-3 py-4">
      <p className="text-sm text-slate-600" aria-live="polite">
        {t('round.progress')} {index + 1} {t('round.of')} {rows.length}
      </p>
      <section className="mt-2 rounded border border-slate-300 bg-white p-3">
        <h1 className="text-xl font-bold">
          {row.room_name ?? '—'}, {row.bed_label ?? '—'} · {row.initials}
        </h1>
        <p className="text-sm text-slate-700">
          {row.procedure_label} · {t(`caseStatus.${row.status}`)}
        </p>
        <p
          className={`mt-1 text-sm font-semibold ${row.ready ? 'text-green-800' : 'text-red-800'}`}
        >
          {row.ready
            ? `✔ ${t('board.ready')}`
            : `✖ ${t('board.notReadyBadge')} (${row.blocking.length})`}
        </p>
        <Link to={`/case/${row.case_id}`} className="text-xs text-teal-800 underline">
          {t('case.title')}
        </Link>
      </section>

      <label className="mt-3 grid gap-1 text-sm font-medium">
        {t('round.pickAssignee')}
        <select
          value={assignee}
          onChange={(e) => pickAssignee(e.target.value)}
          className="min-h-11 rounded border border-slate-400 bg-white px-2"
        >
          <option value="" />
          {staff.data?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.full_name} · {t(`roles.${s.role}`)}
            </option>
          ))}
        </select>
      </label>

      <div className="mt-3 grid gap-2">
        <div role="radiogroup" aria-label={t('orders.type')} className="flex flex-wrap gap-2">
          {ORDER_TYPES.map((o) => (
            <button
              key={o}
              type="button"
              role="radio"
              aria-checked={type === o}
              onClick={() => setType(o)}
              className={`min-h-11 rounded border px-3 text-sm ${type === o ? 'border-teal-800 bg-teal-700 text-white' : 'border-slate-400'}`}
            >
              {t(`orders.types.${o}`)}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {typeSets.map((s) => (
            <button
              key={s.key}
              type="button"
              disabled={!assignee || fromSet.isPending}
              onClick={() => fromSet.mutate(s.key)}
              className="min-h-11 rounded border border-teal-800 bg-teal-50 px-3 text-sm font-medium disabled:opacity-50"
            >
              {s.name_ru}
            </button>
          ))}
          {suggestions
            .filter((s) => !typeSets.some((set) => set.name_ru === s))
            .map((s) => (
              <button
                key={s}
                type="button"
                disabled={!assignee || custom.isPending}
                onClick={() => custom.mutate(s)}
                className="min-h-11 rounded border border-slate-400 px-3 text-sm disabled:opacity-50"
              >
                {s}
              </button>
            ))}
        </div>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (assignee && item.trim()) custom.mutate(item.trim())
          }}
        >
          <input
            aria-label={t('round.custom')}
            placeholder={t('round.custom')}
            value={item}
            maxLength={300}
            onChange={(e) => setItem(e.target.value)}
            className="min-h-11 min-w-0 flex-1 rounded border border-slate-400 px-3"
          />
          <button
            type="submit"
            disabled={!assignee || !item.trim()}
            className="min-h-11 rounded bg-teal-700 px-4 text-white disabled:opacity-50"
          >
            +
          </button>
        </form>
      </div>
      {notice && (
        <p role="status" className="mt-2 text-sm font-semibold text-green-800">
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="mt-4 flex gap-2">
        <button
          type="button"
          disabled={index === 0}
          onClick={() => {
            setIndex(index - 1)
            setNotice(null)
          }}
          className="min-h-11 flex-1 rounded border border-slate-400 px-4 disabled:opacity-40"
        >
          {t('round.prev')}
        </button>
        {last ? (
          <button
            type="button"
            onClick={() => setFinished(true)}
            className="min-h-11 flex-1 rounded bg-teal-700 px-4 font-medium text-white"
          >
            {t('round.finish')}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => {
              setIndex(index + 1)
              setNotice(null)
            }}
            className="min-h-11 flex-1 rounded bg-teal-700 px-4 font-medium text-white"
          >
            {t('round.next')}
          </button>
        )}
      </div>
    </main>
  )
}
