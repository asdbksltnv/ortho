import { useTranslation } from 'react-i18next'
import { PSYCHO_KEYS, SYSTEM_KEYS, type Vitals } from '../types'
import {
  AddButton,
  Chips,
  Field,
  Num,
  RemoveButton,
  Section,
  Segmented,
  Select,
  Text,
  TextArea,
} from '../widgets'
import type { Ctx } from './ctx'

export function BloodPressure({
  value,
  onChange,
  label,
}: {
  value: string | null
  onChange: (value: string | null) => void
  label: string
}) {
  const [sys, dia] = value ? value.split('/') : ['', '']
  const compose = (s: string, d: string) => onChange(s || d ? `${s}/${d}` : null)
  const part = (v: string | undefined, set: (v: string) => void, aria: string) => (
    <input
      aria-label={aria}
      inputMode="numeric"
      pattern="[0-9]*"
      maxLength={3}
      value={v ?? ''}
      onChange={(e) => set(e.target.value.replace(/\D/g, ''))}
      className="min-h-11 w-20 rounded border border-slate-400 px-3 text-base"
    />
  )
  return (
    <div className="flex items-center gap-2" role="group" aria-label={label}>
      {part(sys, (s) => compose(s, dia ?? ''), 'АД систолическое')}
      <span aria-hidden>/</span>
      {part(dia, (d) => compose(sys ?? '', d), 'АД диастолическое')}
    </div>
  )
}

export function VitalsFields({
  vitals,
  base,
  update,
}: {
  vitals: Vitals
  base: string
  update: (path: string, value: unknown) => void
}) {
  const { t } = useTranslation('intake')
  const f = (k: string) => t(`f.${k}`)
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label={f('bp')}>
        <BloodPressure
          label={f('bp')}
          value={vitals.bp}
          onChange={(v) => update(`${base}.bp`, v)}
        />
      </Field>
      <Field label={f('pulse')}>
        <Num
          label={f('pulse')}
          value={vitals.pulse}
          onChange={(v) => update(`${base}.pulse`, v)}
          min={20}
          max={250}
        />
      </Field>
      <Field
        label={f('hr')}
        hint={
          vitals.hr === null && vitals.pulse !== null
            ? `${f('hrAuto')} (${vitals.pulse})`
            : undefined
        }
      >
        <Num
          label={f('hr')}
          value={vitals.hr}
          onChange={(v) => update(`${base}.hr`, v)}
          min={20}
          max={250}
        />
      </Field>
      <Field label={f('rr')}>
        <Num
          label={f('rr')}
          value={vitals.rr}
          onChange={(v) => update(`${base}.rr`, v)}
          min={4}
          max={80}
        />
      </Field>
      <Field label={f('spo2')}>
        <Num
          label={f('spo2')}
          value={vitals.spo2}
          onChange={(v) => update(`${base}.spo2`, v)}
          min={50}
          max={100}
        />
      </Field>
      <Field label={f('temp')}>
        <Num
          label={f('temp')}
          value={vitals.temp}
          onChange={(v) => update(`${base}.temp`, v)}
          decimal
          min={30}
          max={45}
        />
      </Field>
      <Field label={f('weight')}>
        <Num
          label={f('weight')}
          value={vitals.weight}
          onChange={(v) => update(`${base}.weight`, v)}
          decimal
          min={2}
          max={400}
        />
      </Field>
      <Field label={f('height')}>
        <Num
          label={f('height')}
          value={vitals.height}
          onChange={(v) => update(`${base}.height`, v)}
          min={30}
          max={260}
        />
      </Field>
    </div>
  )
}

export function SectionsB({ c }: { c: Ctx }) {
  const { t } = useTranslation('intake')
  const { data, update, config } = c
  const pick = config.picklists
  const f = (k: string) => t(`f.${k}`)
  const sections = (k: string) => t(`sections.${k}`)
  const segmentOptions = config.segments.map((s) => ({ value: s.key, label: s.name_ru }))

  return (
    <>
      <Section id="s7" number={7} title={sections('s7')}>
        <button
          type="button"
          className="min-h-11 w-fit rounded bg-teal-700 px-4 font-medium text-white"
          onClick={() => {
            PSYCHO_KEYS.forEach((k) => update(`psycho.${k}`, config.psycho[k]?.default_ru ?? null))
          }}
        >
          {f('allNormal')}
        </button>
        {PSYCHO_KEYS.map((k) => (
          <Field key={k} label={f(`psycho_${k}`)}>
            <Text
              label={f(`psycho_${k}`)}
              value={data.psycho[k] ?? ''}
              onChange={(v) => update(`psycho.${k}`, v || null)}
            />
          </Field>
        ))}
      </Section>

      <Section id="s8" number={8} title={sections('s8')}>
        <VitalsFields vitals={data.vitals} base="vitals" update={update} />
        <p className="text-sm text-slate-800">
          {f('bmi')}:{' '}
          <strong>{c.bmiValue === null ? '—' : c.bmiValue.toFixed(1).replace('.', ',')}</strong>
        </p>
      </Section>

      <Section id="s9" number={9} title={sections('s9')}>
        <Field label={f('severity')}>
          <Segmented
            label={f('severity')}
            options={pick.severity ?? []}
            value={data.general.severity}
            onChange={(v) => update('general.severity', v)}
          />
        </Field>
        <Field label={f('consciousness')}>
          <Segmented
            label={f('consciousness')}
            options={pick.consciousness ?? []}
            value={data.general.consciousness}
            onChange={(v) => update('general.consciousness', v)}
          />
        </Field>
        <Field label={f('position')}>
          <Segmented
            label={f('position')}
            options={pick.position ?? []}
            value={data.general.position}
            onChange={(v) => update('general.position', v)}
          />
        </Field>
      </Section>

      <Section id="s10" number={10} title={sections('s10')}>
        {SYSTEM_KEYS.map((key) => {
          const finding = data.systems[key]
          const normalText = config.systems[key]?.normal_ru ?? null
          return (
            <Field key={key} label={config.systems[key]?.label_ru ?? key}>
              <Segmented
                label={config.systems[key]?.label_ru ?? key}
                options={[f('normal'), f('changed')]}
                value={finding.normal === null ? null : finding.normal ? f('normal') : f('changed')}
                onChange={(v) => {
                  if (v === null) update(`systems.${key}`, { normal: null, text: '' })
                  else if (v === f('normal')) update(`systems.${key}`, { normal: true, text: '' })
                  else
                    update(`systems.${key}`, {
                      normal: false,
                      text: finding.text || normalText || '',
                    })
                }}
              />
              {finding.normal === true && (
                <p className="text-sm text-slate-700">{normalText ?? f('normalMissing')}</p>
              )}
              {finding.normal === false && (
                <TextArea
                  label={f('finding')}
                  value={finding.text}
                  onChange={(v) => update(`systems.${key}.text`, v)}
                  rows={2}
                />
              )}
            </Field>
          )
        })}
      </Section>

      <Section id="s11" number={11} title={sections('s11')}>
        <Field label={f('segment')}>
          <Select
            label={f('segment')}
            value={data.local_status.segment}
            onChange={(v) => update('local_status.segment', v)}
            options={segmentOptions}
          />
        </Field>
        <Field label={f('inspection')}>
          <Chips
            label={f('inspection')}
            options={pick.inspection ?? []}
            value={data.local_status.inspection}
            onChange={(v) => update('local_status.inspection', v)}
          />
          <Text
            label={f('inspectionText')}
            placeholder={f('inspectionText')}
            value={data.local_status.inspection_text}
            onChange={(v) => update('local_status.inspection_text', v)}
          />
        </Field>
        <Field label={f('palpation')}>
          <TextArea
            label={f('palpation')}
            value={data.local_status.palpation}
            onChange={(v) => update('local_status.palpation', v)}
            rows={2}
          />
        </Field>
        <Field label={f('rom')}>
          {data.local_status.rom.map((r, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className="min-w-0 flex-1">
                <Select
                  label={f('movement')}
                  value={r.movement || null}
                  onChange={(v) => update(`local_status.rom.${i}.movement`, v ?? '')}
                  options={(pick.movements ?? []).map((m) => ({ value: m, label: m }))}
                />
              </div>
              <Num
                label={f('degrees')}
                value={r.degrees}
                onChange={(v) => update(`local_status.rom.${i}.degrees`, v ?? 0)}
                negative
                min={-90}
                max={360}
              />
              <RemoveButton
                label="Удалить"
                onClick={() =>
                  update(
                    'local_status.rom',
                    data.local_status.rom.filter((_, j) => j !== i),
                  )
                }
              />
            </div>
          ))}
          <AddButton
            onClick={() =>
              update('local_status.rom', [...data.local_status.rom, { movement: '', degrees: 0 }])
            }
          >
            {f('addRom')}
          </AddButton>
        </Field>
        <Field label={f('stability')}>
          {data.local_status.stability.map((s, i) => (
            <div key={i} className="grid gap-2 rounded border border-slate-200 p-2">
              <div className="flex gap-2">
                <div className="min-w-0 flex-1">
                  <Text
                    label={f('testName')}
                    placeholder={f('testName')}
                    value={s.test}
                    onChange={(v) => update(`local_status.stability.${i}.test`, v)}
                  />
                </div>
                <RemoveButton
                  label="Удалить"
                  onClick={() =>
                    update(
                      'local_status.stability',
                      data.local_status.stability.filter((_, j) => j !== i),
                    )
                  }
                />
              </div>
              <Segmented
                label={f('testResult')}
                options={pick.stability_result ?? []}
                value={s.result || null}
                onChange={(v) => update(`local_status.stability.${i}.result`, v ?? '')}
              />
            </div>
          ))}
          <AddButton
            onClick={() =>
              update('local_status.stability', [
                ...data.local_status.stability,
                { test: '', result: '' },
              ])
            }
          >
            {f('addTest')}
          </AddButton>
        </Field>
        <Field label={f('neurovascular')}>
          {(['pulsation', 'sensation', 'motor'] as const).map((k) => (
            <div key={k} className="grid gap-1">
              <span className="text-sm text-slate-700">{f(k)}</span>
              <Segmented
                label={f(k)}
                options={pick[k] ?? []}
                value={data.local_status.neurovascular[k]}
                onChange={(v) => update(`local_status.neurovascular.${k}`, v)}
              />
            </div>
          ))}
        </Field>
        <Field label={f('otherLocal')}>
          <TextArea
            label={f('otherLocal')}
            value={data.local_status.other}
            onChange={(v) => update('local_status.other', v)}
            rows={2}
          />
        </Field>
      </Section>
    </>
  )
}
