import { useTranslation } from 'react-i18next'
import { questionsFor } from '../types'
import { Field, MultiSelect, Select, SubSection } from '../widgets'
import type { Ctx } from './ctx'

/** Questions that depend on the painful area: shown once «Область» is chosen. */
export function LocationQuestions({ c }: { c: Ctx }) {
  const { t } = useTranslation('intake')
  const { data, update, config } = c
  const segment = data.complaints.segment
  const details = data.complaints.details ?? {}
  const questions = questionsFor(config, segment)
  const segmentName = config.segments.find((s) => s.key === segment)?.name_ru

  if (!segment) {
    return (
      <p className="rounded-xl border border-dashed border-teal-300 bg-teal-50/60 p-3 text-sm text-teal-950">
        {t('f.locationPick')}
      </p>
    )
  }
  if (questions.length === 0) return null

  const answered = questions.filter((q) => {
    const a = details[q.key]
    return Array.isArray(a) ? a.length > 0 : Boolean(a)
  }).length

  return (
    <SubSection
      title={`${t('f.locationQuestions')}: ${segmentName ?? segment}`}
      aside={
        <span className="text-xs font-medium text-slate-700" data-testid="location-progress">
          {t('f.answered')} {answered} / {questions.length}
        </span>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {questions.map((q) => {
          const answer = details[q.key]
          const path = `complaints.details.${q.key}`
          return (
            <Field key={q.key} label={q.label_ru}>
              {q.multi ? (
                <MultiSelect
                  label={q.label_ru}
                  options={q.options}
                  value={Array.isArray(answer) ? answer : answer ? [answer] : []}
                  onChange={(v) => update(path, v)}
                />
              ) : (
                <Select
                  label={q.label_ru}
                  value={typeof answer === 'string' ? answer : null}
                  onChange={(v) => update(path, v ?? '')}
                  options={q.options.map((o) => ({ value: o, label: o }))}
                />
              )}
            </Field>
          )
        })}
      </div>
    </SubSection>
  )
}
