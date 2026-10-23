import { useTranslation } from 'react-i18next'
import { formatDate } from '../../lib/format'
import {
  AddButton,
  Check,
  Chips,
  Field,
  Num,
  RemoveButton,
  Section,
  Segmented,
  Select,
  Text,
  TextArea,
  YesNo,
} from '../widgets'
import type { Ctx } from './ctx'

export function SectionsA({ c }: { c: Ctx }) {
  const { t } = useTranslation('intake')
  const { data, update, config } = c
  const pick = config.picklists
  const sections = (k: string) => t(`sections.${k}`)
  const f = (k: string) => t(`f.${k}`)
  const segmentOptions = config.segments.map((s) => ({ value: s.key, label: s.name_ru }))

  return (
    <>
      <Section id="s1" number={1} title={sections('s1')}>
        <p className="text-sm text-slate-700">
          {f('procedure')}: <strong>{c.snapshot.procedure_label}</strong>
          {c.snapshot.side
            ? ` · ${f('side')}: ${{ left: 'левая', right: 'правая', both: 'обе' }[c.snapshot.side as 'left']}`
            : ''}
        </p>
        <Field label={f('hospCount')}>
          <Num
            label={f('hospCount')}
            value={data.history.hospitalization_count}
            onChange={(v) => update('history.hospitalization_count', v)}
            min={1}
            max={99}
          />
        </Field>
      </Section>

      <Section id="s2" number={2} title={sections('s2')}>
        <Field label={f('segment')}>
          <Select
            label={f('segment')}
            value={data.complaints.segment}
            onChange={(v) => update('complaints.segment', v)}
            options={segmentOptions}
          />
        </Field>
        <Field label={f('pain')}>
          <Segmented
            label={f('pain')}
            options={Array.from({ length: 11 }, (_, i) => String(i))}
            value={data.complaints.pain_vas === null ? null : String(data.complaints.pain_vas)}
            onChange={(v) => update('complaints.pain_vas', v === null ? null : Number(v))}
          />
        </Field>
        <Check
          label={f('limitation')}
          checked={data.complaints.limitation}
          onChange={(v) => update('complaints.limitation', v)}
        />
        <Check
          label={f('deformity')}
          checked={data.complaints.deformity}
          onChange={(v) => update('complaints.deformity', v)}
        />
        <Check
          label={f('swelling')}
          checked={data.complaints.swelling}
          onChange={(v) => update('complaints.swelling', v)}
        />
        <Field label={f('weightBearing')}>
          <Segmented
            label={f('weightBearing')}
            options={pick.weight_bearing ?? []}
            value={data.complaints.weight_bearing}
            onChange={(v) => update('complaints.weight_bearing', v)}
          />
        </Field>
        <Field label={f('otherComplaints')}>
          <TextArea
            label={f('otherComplaints')}
            value={data.complaints.other}
            onChange={(v) => update('complaints.other', v)}
            rows={2}
          />
        </Field>
        <Field
          label={f('onset')}
          hint={data.history.onset_date ? formatDate(data.history.onset_date) : undefined}
        >
          <input
            type="date"
            aria-label={f('onset')}
            value={data.history.onset_date ?? ''}
            onChange={(e) => update('history.onset_date', e.target.value || null)}
            className="min-h-11 w-full max-w-48 rounded border border-slate-400 px-3"
          />
        </Field>
        <Field label={f('mechanism')}>
          <Text
            label={f('mechanism')}
            value={data.history.mechanism}
            onChange={(v) => update('history.mechanism', v)}
          />
        </Field>
        <Field label={f('duration')}>
          <Text
            label={f('duration')}
            value={data.history.duration}
            onChange={(v) => update('history.duration', v)}
          />
        </Field>
        <Field label={f('priorTreatment')}>
          <TextArea
            label={f('priorTreatment')}
            value={data.history.prior_treatment}
            onChange={(v) => update('history.prior_treatment', v)}
            rows={2}
          />
        </Field>
        <Field label={f('course')}>
          <Segmented
            label={f('course')}
            options={pick.course ?? []}
            value={data.history.course}
            onChange={(v) => update('history.course', v)}
          />
        </Field>
      </Section>

      <Section id="s3" number={3} title={sections('s3')}>
        <Field label={f('hasAllergy')}>
          <YesNo
            label={f('hasAllergy')}
            value={data.allergy.has}
            onChange={(v) => update('allergy.has', v)}
          />
        </Field>
        {data.allergy.has === true && (
          <Field label={f('allergyDesc')}>
            <TextArea
              label={f('allergyDesc')}
              value={data.allergy.description}
              onChange={(v) => update('allergy.description', v)}
              rows={2}
            />
          </Field>
        )}
      </Section>

      <Section id="s4" number={4} title={sections('s4')}>
        <Check
          label={f('denies')}
          checked={data.past.denies}
          onChange={(v) => update('past.denies', v)}
        />
        {!data.past.denies && (
          <>
            {data.past.items.map((item, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="min-w-0 flex-1">
                  <Text
                    label={f('pastItem')}
                    placeholder={f('pastItem')}
                    value={item.text}
                    onChange={(v) => update(`past.items.${i}.text`, v)}
                  />
                </div>
                <Num
                  label={f('year')}
                  value={item.year}
                  onChange={(v) => update(`past.items.${i}.year`, v)}
                  min={1900}
                  max={2100}
                />
                <RemoveButton
                  label="Удалить"
                  onClick={() =>
                    update(
                      'past.items',
                      data.past.items.filter((_, j) => j !== i),
                    )
                  }
                />
              </div>
            ))}
            <AddButton
              onClick={() => update('past.items', [...data.past.items, { text: '', year: null }])}
            >
              {f('addPast')}
            </AddButton>
          </>
        )}
        <Field label={f('epi')}>
          <Chips
            label={f('epi')}
            options={pick.epidemiological ?? []}
            value={data.past.epidemiological}
            onChange={(v) => update('past.epidemiological', v)}
          />
          <Text
            label={f('epiOther')}
            placeholder={f('epiOther')}
            value={data.past.epidemiological_other}
            onChange={(v) => update('past.epidemiological_other', v)}
          />
        </Field>
      </Section>

      <Section id="s5" number={5} title={sections('s5')}>
        <Check
          label={f('noMeds')}
          checked={data.medications_none}
          onChange={(v) => update('medications_none', v)}
        />
        {!data.medications_none && (
          <>
            {data.medications.map((m, i) => (
              <div key={i} className="grid gap-2 rounded border border-slate-200 p-2">
                <Text
                  label={f('drug')}
                  placeholder={f('drug')}
                  value={m.name}
                  onChange={(v) => update(`medications.${i}.name`, v)}
                />
                <div className="grid grid-cols-2 gap-2">
                  <Text
                    label={f('dose')}
                    placeholder={f('dose')}
                    value={m.dose}
                    onChange={(v) => update(`medications.${i}.dose`, v)}
                  />
                  <Text
                    label={f('frequency')}
                    placeholder={f('frequency')}
                    value={m.frequency}
                    onChange={(v) => update(`medications.${i}.frequency`, v)}
                  />
                </div>
                <div className="flex items-center justify-between gap-2">
                  <Check
                    label={f('anticoag')}
                    checked={m.is_anticoagulant}
                    onChange={(v) => update(`medications.${i}.is_anticoagulant`, v)}
                  />
                  <RemoveButton
                    label="Удалить"
                    onClick={() =>
                      update(
                        'medications',
                        data.medications.filter((_, j) => j !== i),
                      )
                    }
                  />
                </div>
              </div>
            ))}
            <AddButton
              onClick={() =>
                update('medications', [
                  ...data.medications,
                  { name: '', dose: '', frequency: '', is_anticoagulant: false },
                ])
              }
            >
              {f('addDrug')}
            </AddButton>
          </>
        )}
        {data.medications.some((m) => m.is_anticoagulant) && (
          <p role="status" className="rounded bg-amber-50 p-2 text-sm text-amber-900">
            {f('anticoagNote')}
          </p>
        )}
      </Section>

      <Section id="s6" number={6} title={sections('s6')}>
        <Field label={f('alcohol')}>
          <Segmented
            label={f('alcohol')}
            options={pick.alcohol ?? []}
            value={data.social.alcohol}
            onChange={(v) => update('social.alcohol', v)}
          />
          <Text
            label={f('alcoholAmount')}
            placeholder={f('alcoholAmount')}
            value={data.social.alcohol_amount}
            onChange={(v) => update('social.alcohol_amount', v)}
          />
        </Field>
        <Field label={f('tobacco')}>
          <Segmented
            label={f('tobacco')}
            options={pick.tobacco ?? []}
            value={data.social.tobacco}
            onChange={(v) => update('social.tobacco', v)}
          />
        </Field>
        <Field label={f('drugs')}>
          <Segmented
            label={f('drugs')}
            options={pick.drugs ?? []}
            value={data.social.drugs}
            onChange={(v) => update('social.drugs', v)}
          />
        </Field>
        <Field label={f('economic')}>
          <Segmented
            label={f('economic')}
            options={pick.economic ?? []}
            value={data.social.economic}
            onChange={(v) => update('social.economic', v)}
          />
        </Field>
        <Field label={f('activity')}>
          <Segmented
            label={f('activity')}
            options={pick.physical_activity ?? []}
            value={data.social.physical_activity}
            onChange={(v) => update('social.physical_activity', v)}
          />
        </Field>
      </Section>
    </>
  )
}
