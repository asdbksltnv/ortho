import { useEffect, useMemo, useState } from 'react'
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
import { filledSections } from '../intake/progress'
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

const SECTION_COUNT = 16

/** Id of the section at the top of the screen, for highlighting its chip in the jump bar. */
function useActiveSection(ready: boolean): string | null {
  const [active, setActive] = useState<string | null>(null)
  useEffect(() => {
    if (!ready || typeof IntersectionObserver === 'undefined') return
    const visible = new Map<string, number>()
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) visible.set(e.target.id, e.boundingClientRect.top)
          else visible.delete(e.target.id)
        }
        const top = [...visible.entries()].sort((a, b) => a[1] - b[1])[0]
        if (top) setActive(top[0])
      },
      { rootMargin: '-120px 0px -55% 0px' },
    )
    for (let n = 1; n <= SECTION_COUNT; n++) {
      const el = document.getElementById(`s${n}`)
      if (el) observer.observe(el)
    }
    return () => observer.disconnect()
  }, [ready])
  // Keep the highlighted chip in view inside the horizontally scrolling bar.
  useEffect(() => {
    // Scroll only the bar: scrollIntoView here would interrupt the page's own smooth scroll.
    const chip = document.querySelector<HTMLElement>(`nav a[href="#${active}"]`)
    const bar = chip?.parentElement
    if (!chip || !bar) return
    bar.scrollTo?.({
      left: chip.offsetLeft - bar.clientWidth / 2 + chip.clientWidth / 2,
      behavior: 'smooth',
    })
  }, [active])
  return active
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
      filled: filledSections(data),
    }
  }, [data, config, snapshot, setData])
  const active = useActiveSection(Boolean(ctx))

  if (sync.status === 'loading' && !data) return <p className="p-4">Загрузка…</p>
  if (!ctx) {
    return (
      <p role="alert" className="p-4 text-red-700">
        {sync.message ?? 'Не удалось загрузить форму. Откройте её один раз при наличии связи.'}
      </p>
    )
  }
  const readOnly = !sync.meta.canEdit

  const filledCount = ctx.filled.size
  const pct = Math.round((filledCount / SECTION_COUNT) * 100)

  return (
    <main className="mx-auto max-w-3xl px-3 pb-36 pt-3">
      <header className="rounded-2xl bg-gradient-to-br from-teal-800 to-teal-950 p-4 text-white shadow-md">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="mr-auto w-full text-xl font-bold sm:w-auto">{t('title')}</h1>
          <Link
            to={`/case/${id}`}
            className="inline-flex min-h-10 items-center rounded-lg bg-white/10 px-3 text-sm font-medium ring-1 ring-white/30 hover:bg-white/20"
          >
            {t('actions.toCase')}
          </Link>
          <Link
            to={`/case/${id}/documents`}
            className="inline-flex min-h-10 items-center rounded-lg bg-white px-3 text-sm font-semibold text-teal-900 hover:bg-teal-50"
          >
            {t('actions.documents')}
          </Link>
        </div>
        <p className="mt-2 truncate text-sm text-teal-50">{snapshot?.procedure_label}</p>
        <div className="mt-3 flex items-center gap-3">
          <div
            className="h-2 flex-1 overflow-hidden rounded-full bg-white/20"
            role="progressbar"
            aria-label={t('progress.label')}
            aria-valuemin={0}
            aria-valuemax={SECTION_COUNT}
            aria-valuenow={filledCount}
          >
            <div
              className="h-full rounded-full bg-emerald-300 transition-[width] duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="shrink-0 text-xs font-medium text-teal-50">
            {t('progress.label')}: {filledCount} {t('progress.of')} {SECTION_COUNT}
          </span>
        </div>
      </header>

      <nav
        aria-label={t('actions.jump')}
        className="sticky top-14 z-20 -mx-3 mt-3 flex gap-1.5 overflow-x-auto bg-slate-50/90 px-3 py-2 backdrop-blur [scrollbar-width:none]"
      >
        {Array.from({ length: SECTION_COUNT }, (_, i) => {
          const n = i + 1
          const isActive = active === `s${n}`
          const done = ctx.filled.has(n)
          return (
            <a
              key={n}
              href={`#s${n}`}
              aria-current={isActive ? 'location' : undefined}
              onClick={(e) => {
                e.preventDefault()
                document
                  .getElementById(`s${n}`)
                  ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
              }}
              className={`inline-flex min-h-10 shrink-0 items-center gap-1 whitespace-nowrap rounded-full border px-3 text-xs font-medium transition-colors ${
                isActive
                  ? 'border-teal-800 bg-teal-800 text-white shadow-sm'
                  : done
                    ? 'border-teal-300 bg-teal-50 text-teal-950'
                    : 'border-slate-300 bg-white text-slate-800 hover:border-teal-700'
              }`}
            >
              {done && <span aria-hidden>✓</span>}
              {n}. {t(`sections.s${n}`).split(/[ ,]/)[0]}
              {done && <span className="sr-only">, {t('progress.filled')}</span>}
            </a>
          )
        })}
      </nav>

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

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 p-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-[0_-4px_16px_rgba(15,23,42,0.08)] backdrop-blur">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-2">
          <span
            role="status"
            aria-live="polite"
            data-testid="sync-status"
            data-state={sync.status}
            className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_STYLE[sync.status]}`}
          >
            {t(`sync.${sync.status}`)}
            {sync.status === 'error' && sync.message ? `: ${sync.message}` : ''}
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-800">
            Caprini: <strong>{ctx.caprini.total}</strong> · {ctx.caprini.categoryLabel}
          </span>
          {!readOnly && (
            <>
              <button
                type="button"
                className="ml-auto min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium hover:bg-slate-50"
                onClick={() => void sync.syncNow()}
              >
                {t('actions.saveNow')}
              </button>
              <button
                type="button"
                className="min-h-11 rounded-lg bg-teal-700 px-4 text-sm font-semibold text-white shadow-sm hover:bg-teal-800"
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
