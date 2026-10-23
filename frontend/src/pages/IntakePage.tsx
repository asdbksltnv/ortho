import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import type { Ctx } from '../intake/sections/ctx'
import { SectionsA } from '../intake/sections/SectionsA'
import { SectionsB } from '../intake/sections/SectionsB'
import { SectionsC } from '../intake/sections/SectionsC'
import {
  ageOn,
  bmi,
  columbiaAnswers,
  computeCaprini,
  computeNutrition,
  latestVitals,
  tashkentToday,
  urgentConsultAlert,
  visibleQuestions,
} from '../intake/scores'
import { setIn } from '../intake/path'
import { useIntakeSync, type SyncState } from '../intake/useIntakeSync'

const STATUS_STYLE: Record<SyncState, string> = {
  loading: 'bg-slate-200 text-slate-900',
  saved: 'bg-green-100 text-green-900',
  dirty: 'bg-amber-100 text-amber-900',
  saving: 'bg-slate-200 text-slate-900',
  offline: 'bg-amber-100 text-amber-900',
  conflict: 'bg-red-100 text-red-900',
  error: 'bg-red-100 text-red-900',
}

export function IntakePage() {
  const { id = '' } = useParams()
  const { t } = useTranslation('intake')
  const sync = useIntakeSync(id)
  const { data, config, snapshot, setData } = sync

  const ctx = useMemo<Ctx | null>(() => {
    if (!data || !config || !snapshot) return null
    const vitals = latestVitals(data)
    const bmiValue = bmi(vitals.weight, vitals.height)
    const age = ageOn(snapshot.birth_date, tashkentToday())
    const answers = columbiaAnswers(data)
    return {
      data,
      config,
      snapshot,
      update: (path, value) => setData((d) => setIn(d, path, value)),
      age,
      bmiValue,
      caprini: computeCaprini(config.caprini, data.caprini.factors, age, bmiValue),
      nutrition: computeNutrition(config.nutrition, data, bmiValue),
      columbiaVisible: visibleQuestions(config.columbia, answers),
      columbiaAlert: urgentConsultAlert(config.columbia, answers),
    }
  }, [data, config, snapshot, setData])

  if (sync.status === 'loading' && !data) return <p className="p-4">Загрузка…</p>
  if (!ctx) {
    return (
      <p role="alert" className="p-4 text-red-700">
        {sync.message ?? 'Не удалось загрузить форму. Откройте её один раз при наличии связи.'}
      </p>
    )
  }
  const readOnly = !sync.meta.canEdit

  return (
    <main className="mx-auto max-w-3xl px-3 pb-28 pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto text-xl font-bold">{t('title')}</h1>
        <Link
          to={`/case/${id}`}
          className="min-h-11 rounded border border-slate-400 px-3 py-2 text-sm"
        >
          {t('actions.toCase')}
        </Link>
        <Link
          to={`/case/${id}/documents`}
          className="min-h-11 rounded border border-slate-400 px-3 py-2 text-sm"
        >
          {t('actions.documents')}
        </Link>
      </div>

      <label className="mt-3 flex min-w-0 items-center gap-2 text-sm">
        <span className="text-slate-700">{t('actions.jump')}</span>
        <select
          className="min-h-11 w-0 min-w-0 flex-1 rounded border border-slate-400 bg-white px-2"
          defaultValue=""
          onChange={(e) => {
            document.getElementById(e.target.value)?.scrollIntoView({ behavior: 'smooth' })
            e.target.value = ''
          }}
        >
          <option value="" />
          {Array.from({ length: 16 }, (_, i) => (
            <option key={i} value={`s${i + 1}`}>
              {i + 1}. {t(`sections.s${i + 1}`)}
            </option>
          ))}
        </select>
      </label>

      {readOnly && (
        <p className="mt-3 rounded bg-slate-100 p-2 text-sm text-slate-800">
          {t('actions.readOnly')}
        </p>
      )}
      {ctx.columbiaAlert && (
        <p
          role="alert"
          className="mt-3 rounded border-2 border-red-700 bg-red-50 p-3 font-semibold text-red-900"
        >
          {ctx.config.columbia.urgent_consult_rule.rule_text_ru ?? t('f.columbiaAlert')}
        </p>
      )}

      <fieldset disabled={readOnly} className="mt-3 grid gap-4 border-0 p-0">
        <SectionsA c={ctx} />
        <SectionsB c={ctx} />
        <SectionsC c={ctx} />
      </fieldset>

      {sync.status === 'conflict' && (
        <div
          role="alertdialog"
          aria-label={t('conflict.title')}
          className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center"
        >
          <div className="w-full rounded-t-xl bg-white p-4 shadow-xl sm:max-w-md sm:rounded-xl">
            <h2 className="text-lg font-semibold">{t('conflict.title')}</h2>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                className="min-h-11 flex-1 rounded border border-slate-400 px-3"
                onClick={() => void sync.takeTheirs()}
              >
                {t('conflict.theirs')}
              </button>
              <button
                type="button"
                className="min-h-11 flex-1 rounded bg-teal-700 px-3 text-white"
                onClick={() => void sync.keepMine()}
              >
                {t('conflict.mine')}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-300 bg-white p-2 shadow-lg">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-2">
          <span
            role="status"
            aria-live="polite"
            data-testid="sync-status"
            data-state={sync.status}
            className={`rounded px-2 py-1 text-xs font-semibold ${STATUS_STYLE[sync.status]}`}
          >
            {t(`sync.${sync.status}`)}
            {sync.status === 'error' && sync.message ? `: ${sync.message}` : ''}
          </span>
          <span className="text-xs text-slate-800">
            Caprini: <strong>{ctx.caprini.total}</strong> · {ctx.caprini.categoryLabel}
          </span>
          {!readOnly && (
            <>
              <button
                type="button"
                className="ml-auto min-h-11 rounded border border-slate-400 px-4 text-sm"
                onClick={() => void sync.syncNow()}
              >
                {t('actions.saveNow')}
              </button>
              <button
                type="button"
                className="min-h-11 rounded bg-teal-700 px-4 text-sm font-medium text-white"
                onClick={() => void sync.syncNow(true)}
              >
                {t('actions.complete')}
              </button>
            </>
          )}
        </div>
        <p className="mx-auto mt-1 max-w-3xl text-[11px] text-slate-600">
          {t('actions.draftNote')}
        </p>
      </div>
    </main>
  )
}
