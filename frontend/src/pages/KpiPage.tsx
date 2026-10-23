import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Kpi } from '../api/types'
import { formatDate, formatDateTime } from '../lib/format'

function isoDaysAgo(days: number): string {
  const d = new Date(Date.now() - days * 86_400_000)
  return d.toISOString().slice(0, 10)
}

export function KpiPage() {
  const { t } = useTranslation()
  const [from, setFrom] = useState(isoDaysAgo(89))
  const [to, setTo] = useState(isoDaysAgo(0))
  const [applied, setApplied] = useState({ from, to })
  const query = useQuery({
    queryKey: ['kpi', applied],
    queryFn: () => api.get<Kpi>(`/kpi?from=${applied.from}&to=${applied.to}`),
  })
  const kpi = query.data
  const max = Math.max(1, ...(kpi?.blocking_items.map((i) => i.count) ?? [1]))

  return (
    <main className="mx-auto max-w-4xl px-3 py-4">
      <h1 className="text-xl font-bold">{t('kpi.title')}</h1>

      <form
        className="mt-3 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          setApplied({ from, to })
        }}
      >
        <label className="grid gap-1 text-sm font-medium">
          {t('kpi.from')}
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            className="min-h-11 rounded border border-slate-400 px-2"
          />
        </label>
        <label className="grid gap-1 text-sm font-medium">
          {t('kpi.to')}
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="min-h-11 rounded border border-slate-400 px-2"
          />
        </label>
        <button type="submit" className="min-h-11 rounded bg-teal-700 px-4 text-white">
          {t('kpi.apply')}
        </button>
        <a
          href={`/api/v1/kpi/export.csv?from=${applied.from}&to=${applied.to}`}
          className="inline-flex min-h-11 items-center rounded border border-teal-800 px-4 text-sm font-medium text-teal-900"
          download
        >
          {t('kpi.csv')}
        </a>
      </form>

      {query.isError && (
        <p role="alert" className="mt-3 text-red-700">
          {t('kpi.error')}
        </p>
      )}
      {query.isLoading && <p className="mt-3">{t('common.loading')}</p>}

      {kpi && (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tile label={t('kpi.cases')} value={String(kpi.cases_total)} />
            <Tile label={t('kpi.readyCases')} value={String(kpi.ready_cases)} />
            <Tile
              label={t('kpi.median')}
              value={
                kpi.median_hours_to_ready === null
                  ? t('kpi.none')
                  : `${String(kpi.median_hours_to_ready).replace('.', ',')} ${t('kpi.hours')}`
              }
            />
            <Tile label={t('kpi.overrides')} value={String(kpi.overrides.length)} />
          </dl>

          <section className="mt-6" aria-labelledby="blocking">
            <h2 id="blocking" className="font-semibold">
              {t('kpi.blocking')}
            </h2>
            {kpi.blocking_items.length === 0 ? (
              <p className="mt-2 text-sm text-slate-700">{t('kpi.noBlocking')}</p>
            ) : (
              <ul className="mt-2 grid gap-2">
                {kpi.blocking_items.map((item) => (
                  <li
                    key={item.key}
                    className="grid grid-cols-[8rem_1fr_2rem] items-center gap-2 text-sm"
                  >
                    <span>{item.label}</span>
                    <span className="h-4 rounded-r bg-slate-100" aria-hidden>
                      <span
                        className="block h-4 rounded-r-[4px]"
                        style={{ width: `${(item.count / max) * 100}%`, background: '#2a78d6' }}
                      />
                    </span>
                    <strong className="text-right">{item.count}</strong>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="mt-6" aria-labelledby="ovr">
            <h2 id="ovr" className="font-semibold">
              {t('kpi.overrides')}
            </h2>
            {kpi.overrides.length === 0 ? (
              <p className="mt-2 text-sm text-slate-700">{t('kpi.noOverrides')}</p>
            ) : (
              <div className="mt-2 overflow-x-auto rounded border border-slate-300 bg-white">
                <table className="w-full min-w-[480px] text-left text-sm">
                  <thead className="bg-slate-100">
                    <tr>
                      <th className="px-3 py-2">{t('kpi.when')}</th>
                      <th className="px-3 py-2">{t('kpi.patient')}</th>
                      <th className="px-3 py-2">{t('kpi.reason')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {kpi.overrides.map((o, i) => (
                      <tr key={i} className="border-t border-slate-200">
                        <td className="whitespace-nowrap px-3 py-1">{formatDateTime(o.at)}</td>
                        <td className="px-3 py-1">
                          <Link to={`/case/${o.case_id}`} className="underline">
                            {o.case_label}
                          </Link>
                        </td>
                        <td className="px-3 py-1">{o.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="mt-6" aria-labelledby="eve">
            <h2 id="eve" className="font-semibold">
              {t('kpi.notReadyEve')}
            </h2>
            <p className="text-xs text-slate-600">
              {t('kpi.notReadyEveHint')} · {t('kpi.checked')}: {kpi.surgeries_checked}
            </p>
            {kpi.not_ready_eve.length === 0 ? (
              <p className="mt-2 text-sm text-slate-700">{t('kpi.noEve')}</p>
            ) : (
              <ul className="mt-2 grid gap-1 text-sm">
                {kpi.not_ready_eve.map((c) => (
                  <li key={c.case_id}>
                    <Link to={`/case/${c.case_id}`} className="underline">
                      {c.case_label}
                    </Link>{' '}
                    · {t('kpi.planned')}: {formatDate(c.planned)}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </main>
  )
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-slate-300 bg-white p-3">
      <dt className="text-xs text-slate-700">{label}</dt>
      <dd className="mt-1 text-2xl font-bold text-slate-900">{value}</dd>
    </div>
  )
}
