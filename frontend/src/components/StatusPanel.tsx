import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '../api/client'
import type { CaseDetail, CaseStatus, Definitions, StatusEvent } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { useToast } from './Toast'
import { formatDate, formatDateTime } from '../lib/format'

const REVERSAL_LABEL: Partial<Record<CaseStatus, Partial<Record<CaseStatus, string>>>> = {
  called_to_or: { approved_for_surgery: 'Отменить вызов' },
  approved_for_surgery: { in_preparation: 'Отозвать одобрение' },
}

type Pending = { target: CaseStatus; reversal: boolean } | null

export function StatusPanel({ detail }: { detail: CaseDetail }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [pending, setPending] = useState<Pending>(null)
  const [reason, setReason] = useState('')
  const [date, setDate] = useState(detail.planned_surgery_date ?? '')
  const [time, setTime] = useState(detail.planned_surgery_time?.slice(0, 5) ?? '')
  const [error, setError] = useState<string | null>(null)

  const defs = useQuery({
    queryKey: ['definitions'],
    queryFn: () => api.get<Definitions>('/config/definitions'),
    staleTime: Infinity,
  })
  const events = useQuery({
    queryKey: ['events', detail.id],
    queryFn: () => api.get<StatusEvent[]>(`/cases/${detail.id}/events`),
  })

  const move = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<CaseDetail>(`/cases/${detail.id}/transition`, body),
    onSuccess: (updated) => {
      queryClient.setQueryData(['case', detail.id], updated)
      void queryClient.invalidateQueries({ queryKey: ['board'] })
      void queryClient.invalidateQueries({ queryKey: ['events', detail.id] })
      setPending(null)
      setReason('')
      setError(null)
      toast(t('flow.toastDone'))
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : t('errors.unknown')),
  })

  if (!user) return null
  const targets = detail.available_transitions
  const labels = (key: string) =>
    defs.data?.checklist.find((c) => c.key === key)?.short_label_ru ?? key
  const isHead = user.role === 'head_of_department'
  const notReady = !detail.readiness.ready && !detail.is_emergency

  const start = (target: CaseStatus) => {
    setError(null)
    const reversal = REVERSAL_LABEL[detail.status]?.[target] !== undefined
    if (reversal || target === 'approved_for_surgery' || (target === 'called_to_or' && notReady)) {
      setPending({ target, reversal })
    } else {
      move.mutate({ to: target })
    }
  }

  const confirm = () => {
    if (!pending) return
    const body: Record<string, unknown> = { to: pending.target }
    if (reason.trim()) body.reason = reason.trim()
    if (pending.target === 'approved_for_surgery') {
      if (date) body.planned_surgery_date = date
      if (time) body.planned_surgery_time = `${time}:00`
    }
    move.mutate(body)
  }

  const callBlocked = pending?.target === 'called_to_or' && !isHead

  return (
    <section
      className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
      aria-labelledby="flow"
    >
      <h2 id="flow" className="text-lg font-semibold">
        {t('flow.title')}
      </h2>
      <p className="mt-1 text-sm">
        {t('flow.current')}: <strong>{t(`caseStatus.${detail.status}`)}</strong>
        {detail.is_emergency && (
          <span className="ml-2 text-xs text-red-800">{t('flow.emergencyNote')}</span>
        )}
      </p>
      {detail.override_reason && (
        <p className="mt-2 rounded bg-amber-50 p-2 text-sm text-amber-900">
          <strong>{t('flow.override')}:</strong> {detail.override_reason}
        </p>
      )}

      {targets.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {targets.map((target) => (
            <button
              key={target}
              type="button"
              disabled={move.isPending}
              onClick={() => start(target)}
              className="min-h-11 rounded bg-teal-700 px-4 text-sm font-medium text-white disabled:opacity-60"
            >
              {REVERSAL_LABEL[detail.status]?.[target] ?? t(`flow.to.${target}`)}
            </button>
          ))}
        </div>
      )}
      {error && !pending && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {pending && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={t(`flow.to.${pending.target}`)}
          className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center"
        >
          <div className="max-h-[90vh] w-full overflow-y-auto rounded-t-xl bg-white p-4 shadow-xl sm:max-w-md sm:rounded-xl">
            <h3 className="text-lg font-semibold">
              {REVERSAL_LABEL[detail.status]?.[pending.target] ?? t(`flow.to.${pending.target}`)}
            </h3>

            {pending.target === 'approved_for_surgery' && (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <label className="grid gap-1 text-sm font-medium">
                  {t('flow.planned')}
                  <input
                    type="date"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    className="min-h-11 rounded border border-slate-400 px-2"
                  />
                </label>
                <label className="grid gap-1 text-sm font-medium">
                  {t('flow.plannedTime')}
                  <input
                    type="time"
                    value={time}
                    onChange={(e) => setTime(e.target.value)}
                    className="min-h-11 rounded border border-slate-400 px-2"
                  />
                </label>
              </div>
            )}

            {pending.target === 'called_to_or' && (
              <div className="mt-3 text-sm">
                <p className="font-semibold text-red-800">{t('flow.notReady')}</p>
                <ul className="mt-1 list-disc pl-5">
                  {detail.readiness.blocking.map((k) => (
                    <li key={k}>{labels(k)}</li>
                  ))}
                </ul>
                {isHead && <p className="mt-2 text-slate-700">{t('flow.overrideHint')}</p>}
              </div>
            )}

            {pending.reversal && (
              <p className="mt-3 text-sm text-slate-700">{t('flow.reversalHint')}</p>
            )}

            {!callBlocked && (pending.reversal || pending.target === 'called_to_or') && (
              <label className="mt-3 grid gap-1 text-sm font-medium">
                {t('flow.reasonLabel')}
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  maxLength={1000}
                  className="rounded border border-slate-400 p-2"
                />
              </label>
            )}
            {error && (
              <p role="alert" className="mt-2 text-sm text-red-700">
                {error}
              </p>
            )}
            <div className="mt-4 flex gap-2">
              {!callBlocked && (
                <button
                  type="button"
                  disabled={
                    move.isPending ||
                    ((pending.reversal || pending.target === 'called_to_or') && !reason.trim())
                  }
                  onClick={confirm}
                  className="min-h-11 flex-1 rounded bg-teal-700 px-4 font-medium text-white disabled:opacity-50"
                >
                  {t('flow.confirm')}
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  setPending(null)
                  setError(null)
                }}
                className="min-h-11 flex-1 rounded border border-slate-400 px-4"
              >
                {callBlocked ? t('common.close') : t('flow.cancel')}
              </button>
            </div>
          </div>
        </div>
      )}

      {events.data && events.data.length > 0 && (
        <details className="mt-3">
          <summary className="min-h-11 cursor-pointer py-2 text-sm font-medium">
            {t('flow.events')}
          </summary>
          <ol className="grid gap-1 text-sm">
            {events.data.map((e, i) => (
              <li key={i} className="border-t border-slate-100 py-1">
                <span className="text-slate-600">{formatDateTime(e.created_at)}</span> —{' '}
                {t(`caseStatus.${e.to_status}`)}
                {e.user_name ? ` · ${e.user_name}` : ''}
                {e.is_override && (
                  <strong className="ml-1 text-amber-800">({t('flow.override')})</strong>
                )}
                {e.reason && <span className="block text-slate-700">{e.reason}</span>}
              </li>
            ))}
          </ol>
        </details>
      )}
      {detail.planned_surgery_date && (
        <p className="mt-2 text-xs text-slate-600">
          {t('flow.planned')}: {formatDate(detail.planned_surgery_date)}
          {detail.planned_surgery_time ? ` ${detail.planned_surgery_time.slice(0, 5)}` : ''}
        </p>
      )}
    </section>
  )
}
