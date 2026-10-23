import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '../api/client'
import type { Definitions, Order, OrderSet, Staff } from '../api/types'
import { formatDateTime } from '../lib/format'

export const ORDER_TYPES = ['lab', 'imaging', 'consult', 'other'] as const

export function OrderRow({
  order,
  caseId,
  showCase = false,
}: {
  order: Order
  caseId?: string
  showCase?: boolean
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const move = useMutation({
    mutationFn: (status: string) => api.patch<Order>(`/orders/${order.id}/status`, { status }),
    onSuccess: () => {
      setError(null)
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
      if (caseId) void queryClient.invalidateQueries({ queryKey: ['case', caseId] })
      void queryClient.invalidateQueries({ queryKey: ['board'] })
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : t('errors.unknown')),
  })
  return (
    <li className="rounded border border-slate-200 p-2">
      <div className="flex flex-wrap items-center gap-2">
        {showCase && <span className="text-sm font-semibold">{order.case_label}</span>}
        <span className="rounded bg-slate-200 px-2 py-0.5 text-xs">
          {t(`orders.types.${order.type}`)}
        </span>
        <span className="mr-auto text-sm font-medium">{order.item}</span>
        <span
          className={`rounded px-2 py-0.5 text-xs font-semibold ${
            order.status === 'result_available'
              ? 'bg-amber-100 text-amber-900'
              : 'bg-slate-100 text-slate-900'
          }`}
        >
          {t(`orders.status.${order.status}`)}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-600">
        {order.assignee_name} · {formatDateTime(order.created_at)}
        {order.created_at_round ? ` · ${t('orders.viaRound')}` : ''}
        {order.linked_checklist_key ? ` · ↔ ${order.linked_checklist_key}` : ''}
      </p>
      {order.next_statuses.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {order.next_statuses.map((s) => (
            <button
              key={s}
              type="button"
              disabled={move.isPending}
              onClick={() => move.mutate(s)}
              className={`min-h-11 rounded border px-3 text-sm ${
                s === 'cancelled' ? 'border-slate-400' : 'border-teal-800 bg-teal-50 font-medium'
              }`}
            >
              {t(`orders.move.${s}`)}
            </button>
          ))}
        </div>
      )}
      {error && (
        <p role="alert" className="mt-1 text-xs text-red-700">
          {error}
        </p>
      )}
    </li>
  )
}

export function OrdersPanel({ caseId, canCreate }: { caseId: string; canCreate: boolean }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const orders = useQuery({
    queryKey: ['orders', caseId],
    queryFn: () => api.get<Order[]>(`/cases/${caseId}/orders`),
    refetchInterval: 15_000,
  })
  const staff = useQuery({
    queryKey: ['staff'],
    queryFn: () => api.get<Staff[]>('/staff'),
    enabled: canCreate,
  })
  const sets = useQuery({
    queryKey: ['order-sets'],
    queryFn: () => api.get<OrderSet[]>('/order-sets'),
    enabled: canCreate,
  })
  const defs = useQuery({
    queryKey: ['definitions'],
    queryFn: () => api.get<Definitions>('/config/definitions'),
    staleTime: Infinity,
    enabled: canCreate,
  })

  const [type, setType] = useState<(typeof ORDER_TYPES)[number]>('lab')
  const [item, setItem] = useState('')
  const [assignee, setAssignee] = useState('')
  const [linked, setLinked] = useState('')
  const [error, setError] = useState<string | null>(null)

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['orders', caseId] })
    void queryClient.invalidateQueries({ queryKey: ['case', caseId] })
    void queryClient.invalidateQueries({ queryKey: ['board'] })
  }
  const create = useMutation({
    mutationFn: () =>
      api.post(`/cases/${caseId}/orders`, {
        type,
        item: item.trim(),
        assignee_id: assignee,
        linked_checklist_key: linked || null,
      }),
    onSuccess: () => {
      setItem('')
      setLinked('')
      setError(null)
      refresh()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : t('errors.unknown')),
  })
  const fromSet = useMutation({
    mutationFn: (key: string) =>
      api.post(`/cases/${caseId}/orders/from-set`, { set_key: key, assignee_id: assignee }),
    onSuccess: () => {
      setError(null)
      refresh()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : t('errors.unknown')),
  })

  return (
    <section
      className="mt-4 rounded border border-slate-300 bg-white p-4"
      aria-labelledby="orders-h"
    >
      <h2 id="orders-h" className="text-lg font-semibold">
        {t('orders.title')}
      </h2>
      <ul className="mt-2 grid gap-2">
        {orders.data?.map((o) => (
          <OrderRow key={o.id} order={o} caseId={caseId} />
        ))}
        {orders.data?.length === 0 && (
          <li className="text-sm text-slate-600">{t('orders.none')}</li>
        )}
      </ul>

      {canCreate && (
        <div className="mt-4 grid gap-3 border-t border-slate-200 pt-3">
          <label className="grid gap-1 text-sm font-medium">
            {t('orders.assignee')}
            <select
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
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
          <div>
            <p className="text-sm font-medium">{t('orders.sets')}</p>
            <div className="mt-1 flex flex-wrap gap-2">
              {sets.data?.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  disabled={!assignee || fromSet.isPending}
                  onClick={() => fromSet.mutate(s.key)}
                  className="min-h-11 rounded border border-teal-800 px-3 text-sm disabled:opacity-50"
                >
                  {s.name_ru}
                </button>
              ))}
            </div>
          </div>
          <form
            className="grid gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              if (assignee && item.trim()) create.mutate()
            }}
          >
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
            <input
              aria-label={t('orders.item')}
              placeholder={t('orders.item')}
              value={item}
              maxLength={300}
              onChange={(e) => setItem(e.target.value)}
              className="min-h-11 rounded border border-slate-400 px-3"
            />
            <select
              aria-label={t('orders.linked')}
              value={linked}
              onChange={(e) => setLinked(e.target.value)}
              className="min-h-11 rounded border border-slate-400 bg-white px-2"
            >
              <option value="">{t('orders.linked')}: —</option>
              {defs.data?.checklist.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.short_label_ru}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={!assignee || !item.trim() || create.isPending}
              className="min-h-11 rounded bg-teal-700 px-4 font-medium text-white disabled:opacity-50"
            >
              {t('orders.add')}
            </button>
          </form>
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
