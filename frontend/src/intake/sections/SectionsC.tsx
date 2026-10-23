import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  AddButton,
  Chips,
  Field,
  RemoveButton,
  Section,
  Segmented,
  Text,
  TextArea,
  YesNo,
} from '../widgets'
import type { Ctx } from './ctx'
import { VitalsFields } from './SectionsB'

function ItemList({
  label,
  items,
  suggestions,
  onChange,
}: {
  label: string
  items: string[]
  suggestions: string[]
  onChange: (items: string[]) => void
}) {
  const { t } = useTranslation('intake')
  const [draft, setDraft] = useState('')
  const options = [...new Set([...suggestions, ...items])]
  return (
    <div className="grid gap-2">
      <Chips label={label} options={options} value={items} onChange={onChange} />
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          const v = draft.trim()
          if (v && !items.includes(v)) onChange([...items, v])
          setDraft('')
        }}
      >
        <div className="min-w-0 flex-1">
          <Text
            label={`${label}: ${t('f.addItem')}`}
            placeholder={t('f.addItem')}
            value={draft}
            onChange={setDraft}
          />
        </div>
        <button type="submit" className="min-h-11 rounded border border-slate-400 px-3 text-sm">
          +
        </button>
      </form>
    </div>
  )
}

export function SectionsC({ c }: { c: Ctx }) {
  const { t } = useTranslation('intake')
  const { data, update, config } = c
  const pick = config.picklists
  const f = (k: string) => t(`f.${k}`)
  const sections = (k: string) => t(`sections.${k}`)
  const questionText = (n: number) =>
    config.columbia.questions.find((q) => q.n === n)?.text_ru ?? `${f('question')} ${n}`
  const kinds = t('kinds', { returnObjects: true }) as string[]
  const groups = [1, 2, 3, 5]
  const manual = data.caprini.factors

  return (
    <>
      <Section id="s12" number={12} title={sections('s12')}>
        <h3 className="font-semibold">{f('columbia')}</h3>
        {c.columbiaAlert && (
          <div
            role="alert"
            className="rounded border-2 border-red-700 bg-red-50 p-3 text-base font-semibold text-red-900"
          >
            {config.columbia.urgent_consult_rule.rule_text_ru ?? f('columbiaAlert')}
          </div>
        )}
        {c.columbiaVisible.map((n) => (
          <Field key={n} label={questionText(n)}>
            <YesNo
              label={questionText(n)}
              value={data.columbia[`q${n}` as 'q1']}
              onChange={(v) => update(`columbia.q${n}`, v)}
            />
          </Field>
        ))}
        <h3 className="mt-2 font-semibold">{f('nutrition')}</h3>
        <p className="text-sm text-slate-800">
          {f('bmiLow')}:{' '}
          <strong>{c.nutrition.bmiLow === null ? '—' : c.nutrition.bmiLow ? 'Да' : 'Нет'}</strong>{' '}
          <span className="text-slate-600">
            ({c.nutrition.bmiLow === null ? f('bmiLowUnknown') : f('bmiLowAuto')})
          </span>
        </p>
        {(
          [
            ['weight_loss', 'weightLoss'],
            ['reduced_intake', 'reducedIntake'],
            ['stress_factor', 'stress'],
          ] as const
        ).map(([key, label]) => (
          <Field key={key} label={f(label)}>
            <YesNo
              label={f(label)}
              value={data.nutrition[key]}
              onChange={(v) => update(`nutrition.${key}`, v)}
            />
          </Field>
        ))}
        <p className="text-sm">
          {f('nutritionTotal')}: <strong>{c.nutrition.complete ? c.nutrition.total : '—'}</strong>
        </p>
      </Section>

      <Section id="s13" number={13} title={sections('s13')}>
        {groups.map((points) => (
          <fieldset key={points} className="grid gap-1">
            <legend className="text-sm font-semibold text-slate-800">
              {points} {f('points')}
            </legend>
            {config.caprini.factors
              .filter((factor) => factor.points === points)
              .map((factor) => {
                const checked = c.caprini.counted.includes(factor.key)
                const locked =
                  factor.auto !== null &&
                  (factor.auto.type === 'age' ? c.age !== null : c.bmiValue !== null)
                return (
                  <label
                    key={factor.key}
                    className="flex min-h-11 cursor-pointer items-center gap-3 text-sm"
                  >
                    <input
                      type="checkbox"
                      className="h-5 w-5"
                      checked={checked}
                      disabled={locked}
                      onChange={(e) =>
                        update(
                          'caprini.factors',
                          e.target.checked
                            ? [...manual, factor.key]
                            : manual.filter((k) => k !== factor.key),
                        )
                      }
                    />
                    <span>
                      {factor.label_ru}
                      {factor.auto && locked ? ` (${f('auto')})` : ''}
                    </span>
                  </label>
                )
              })}
          </fieldset>
        ))}
        <p className="rounded bg-slate-100 p-2 text-sm" aria-live="polite">
          {f('capriniTotal')}: <strong>{c.caprini.total}</strong> · {f('capriniCategory')}:{' '}
          <strong>{c.caprini.categoryLabel}</strong>
        </p>
      </Section>

      <Section id="s14" number={14} title={sections('s14')}>
        {(
          [
            ['main', 'dxMain'],
            ['competing', 'dxCompeting'],
            ['complication', 'dxComplication'],
            ['background', 'dxBackground'],
          ] as const
        ).map(([key, label]) => (
          <Field key={key} label={f(label)}>
            <div className="grid gap-2 sm:grid-cols-[10rem_1fr]">
              <Text
                label={`${f(label)}: ${f('code')}`}
                placeholder={f('code')}
                value={data.diagnosis[key].code}
                onChange={(v) => update(`diagnosis.${key}.code`, v)}
              />
              <Text
                label={`${f(label)}: ${f('dxText')}`}
                placeholder={f('dxText')}
                value={data.diagnosis[key].text}
                onChange={(v) => update(`diagnosis.${key}.text`, v)}
                maxLength={2000}
              />
            </div>
          </Field>
        ))}
        <Field label={f('dxComorbid')}>
          {data.diagnosis.comorbid.map((entry, i) => (
            <div key={i} className="flex gap-2">
              <div className="w-32 shrink-0">
                <Text
                  label={f('code')}
                  placeholder={f('code')}
                  value={entry.code}
                  onChange={(v) => update(`diagnosis.comorbid.${i}.code`, v)}
                />
              </div>
              <div className="min-w-0 flex-1">
                <Text
                  label={f('dxText')}
                  placeholder={f('dxText')}
                  value={entry.text}
                  onChange={(v) => update(`diagnosis.comorbid.${i}.text`, v)}
                  maxLength={2000}
                />
              </div>
              <RemoveButton
                label="Удалить"
                onClick={() =>
                  update(
                    'diagnosis.comorbid',
                    data.diagnosis.comorbid.filter((_, j) => j !== i),
                  )
                }
              />
            </div>
          ))}
          <AddButton
            onClick={() =>
              update('diagnosis.comorbid', [...data.diagnosis.comorbid, { code: '', text: '' }])
            }
          >
            {f('addComorbid')}
          </AddButton>
        </Field>
      </Section>

      <Section id="s15" number={15} title={sections('s15')}>
        <Field label={f('diet')}>
          {config.diets.length > 0 ? (
            <Segmented
              label={f('diet')}
              options={config.diets}
              value={data.plan.diet || null}
              onChange={(v) => update('plan.diet', v ?? '')}
            />
          ) : (
            <Text
              label={f('diet')}
              value={data.plan.diet}
              onChange={(v) => update('plan.diet', v)}
            />
          )}
        </Field>
        <Field label={f('specialDiet')}>
          <Text
            label={f('specialDiet')}
            value={data.plan.special_diet}
            onChange={(v) => update('plan.special_diet', v)}
          />
        </Field>
        <Field label={f('labs')}>
          <ItemList
            label={f('labs')}
            items={data.plan.labs}
            suggestions={config.core_labs}
            onChange={(v) => update('plan.labs', v)}
          />
        </Field>
        <Field label={f('instrumental')}>
          <ItemList
            label={f('instrumental')}
            items={data.plan.instrumental}
            suggestions={[]}
            onChange={(v) => update('plan.instrumental', v)}
          />
        </Field>
        <Field label={f('consults')}>
          <ItemList
            label={f('consults')}
            items={data.plan.consults}
            suggestions={pick.consults ?? []}
            onChange={(v) => update('plan.consults', v)}
          />
        </Field>
        <Field label={f('orders')}>
          {data.plan.medications.map((m, i) => (
            <div key={i} className="grid gap-2 rounded border border-slate-200 p-2">
              <div className="flex gap-2">
                <div className="min-w-0 flex-1">
                  <Text
                    label={f('drug')}
                    placeholder={f('drug')}
                    value={m.name}
                    onChange={(v) => update(`plan.medications.${i}.name`, v)}
                  />
                </div>
                <RemoveButton
                  label="Удалить"
                  onClick={() =>
                    update(
                      'plan.medications',
                      data.plan.medications.filter((_, j) => j !== i),
                    )
                  }
                />
              </div>
              <Segmented
                label={f('orderKind')}
                options={kinds}
                value={m.kind || null}
                onChange={(v) => update(`plan.medications.${i}.kind`, v ?? '')}
              />
              <Text
                label={f('orderNote')}
                placeholder={f('orderNote')}
                value={m.note}
                onChange={(v) => update(`plan.medications.${i}.note`, v)}
              />
            </div>
          ))}
          <AddButton
            onClick={() =>
              update('plan.medications', [
                ...data.plan.medications,
                { name: '', note: '', kind: '' },
              ])
            }
          >
            {f('addOrder')}
          </AddButton>
        </Field>
        <Field label={f('recommendations')}>
          <TextArea
            label={f('recommendations')}
            value={data.plan.recommendations}
            onChange={(v) => update('plan.recommendations', v)}
            rows={2}
          />
        </Field>
      </Section>

      <Section id="s16" number={16} title={sections('s16')}>
        <Field label={f('economicAbility')}>
          <Segmented
            label={f('economicAbility')}
            options={pick.economic_ability ?? []}
            value={data.preop.economic_assessment}
            onChange={(v) => update('preop.economic_assessment', v)}
          />
        </Field>
        <Field label={f('socialNeeds')}>
          <Segmented
            label={f('socialNeeds')}
            options={pick.social_needs ?? []}
            value={data.preop.social_needs}
            onChange={(v) => update('preop.social_needs', v)}
          />
        </Field>
        <Field label={f('psychNeeds')}>
          <Segmented
            label={f('psychNeeds')}
            options={pick.psychological_needs ?? []}
            value={data.preop.psychological_needs}
            onChange={(v) => update('preop.psychological_needs', v)}
          />
        </Field>
        <Field label={f('dischargeNeeds')}>
          <Chips
            label={f('dischargeNeeds')}
            options={pick.discharge_needs ?? []}
            value={data.preop.discharge_needs}
            onChange={(v) => update('preop.discharge_needs', v)}
          />
        </Field>
        <Field label={f('freshVitals')}>
          <VitalsFields vitals={data.preop.vitals} base="preop.vitals" update={update} />
        </Field>
        <Field label={f('generalUpdate')}>
          <TextArea
            label={f('generalUpdate')}
            value={data.preop.general_condition}
            onChange={(v) => update('preop.general_condition', v)}
            rows={2}
          />
        </Field>
        <Field label={f('localUpdate')}>
          <TextArea
            label={f('localUpdate')}
            value={data.preop.local_status}
            onChange={(v) => update('preop.local_status', v)}
            rows={2}
          />
        </Field>
        <Field label={f('imaging')}>
          <TextArea
            label={f('imaging')}
            value={data.preop.imaging}
            onChange={(v) => update('preop.imaging', v)}
            rows={2}
          />
        </Field>
        <Field label={f('failedConservative')}>
          <TextArea
            label={f('failedConservative')}
            value={data.preop.failed_conservative}
            onChange={(v) => update('preop.failed_conservative', v)}
            rows={2}
          />
        </Field>
      </Section>
    </>
  )
}
