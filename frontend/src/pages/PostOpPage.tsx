import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { PostOpData, PostOpEntry, PostOpList } from '../api/types'
import { TrendChart } from '../components/TrendChart'
import type { IntakeConfig } from '../intake/types'
import { setIn } from '../intake/path'
import { BloodPressure } from '../intake/sections/SectionsB'
import { Check, Field, Num, Section, Segmented, Text, TextArea } from '../intake/widgets'
import { formatDateTime } from '../lib/format'

export function emptyPostOp(): PostOpData {
  return {
    complaints: '',
    pain_vas: null,
    consciousness: null,
    vitals: { bp: null, pulse: null, rr: null, spo2: null, temp: null, cvp: null },
    wound: {
      dressing: null,
      discharge: null,
      redness: false,
      swelling: false,
      sutures: null,
      dressing_changed: false,
    },
    drain: { present: false, output_ml: null, removed: false },
    neurovascular: { pulsation: null, sensation: null, motor: null },
    calf_tenderness: false,
    mobilization: { level: null, weight_bearing: null, physiotherapy: false },
    therapy: { antibiotic_day: null, vte_prophylaxis: false, analgesia: '' },
    recommendations: '',
    photo_key: null,
  }
}

export function PostOpPage() {
  const { id = '' } = useParams()
  const { t } = useTranslation('intake')
  const { t: tc } = useTranslation()
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)
  const [form, setForm] = useState<PostOpData>(emptyPostOp)
  const [loadedFor, setLoadedFor] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const list = useQuery({
    queryKey: ['postop', id],
    queryFn: () => api.get<PostOpList>(`/cases/${id}/postop`),
  })
  const config = useQuery({
    queryKey: ['intake-config'],
    queryFn: () => api.get<IntakeConfig>('/config/intake'),
    staleTime: Infinity,
  })
  const pick = config.data?.picklists ?? {}
  const data = list.data
  const todayEntry = data?.entries.find((e) => e.id === data.today_entry_id) ?? null
  const current: PostOpEntry | null =
    data?.entries.find((e) => e.id === (selected ?? data.today_entry_id)) ?? null

  // Load today's entry into the form once per entry.
  useEffect(() => {
    if (todayEntry && loadedFor !== todayEntry.id) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setForm(todayEntry.data)
      setLoadedFor(todayEntry.id)
    }
  }, [todayEntry, loadedFor])

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['postop', id] })
  const save = useMutation({
    mutationFn: () =>
      todayEntry
        ? api.put<PostOpEntry>(`/cases/${id}/postop/${todayEntry.id}`, { data: form })
        : api.post<PostOpEntry>(`/cases/${id}/postop`, { data: form }),
    onSuccess: (entry) => {
      setMessage(t('postop.saved'))
      setError(null)
      setLoadedFor(entry.id)
      void refresh()
    },
    onError: (e) => {
      setMessage(null)
      setError(e instanceof ApiError ? e.message : tc('errors.unknown'))
    },
  })

  const set = (path: string, value: unknown) => setForm((f) => setIn(f, path, value))
  const f = (k: string) => t(`postop.${k}`)

  if (list.isLoading || !data) return <p className="p-4">{tc('common.loading')}</p>
  const readOnly = !data.can_edit

  return (
    <main className="mx-auto max-w-3xl px-3 pb-24 pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto text-xl font-bold">{f('title')}</h1>
        <Link
          to={`/case/${id}`}
          className="min-h-11 rounded border border-slate-400 px-3 py-2 text-sm"
        >
          {t('actions.toCase')}
        </Link>
      </div>

      {!data.can_record && (
        <p className="mt-3 rounded bg-slate-100 p-2 text-sm">{f('notRecordable')}</p>
      )}
      {readOnly && data.can_record && (
        <p className="mt-3 rounded bg-slate-100 p-2 text-sm">{f('readOnly')}</p>
      )}
      {todayEntry && todayEntry.alerts.length > 0 && (
        <p
          role="alert"
          className="mt-3 rounded border-2 border-red-700 bg-red-50 p-2 text-sm font-semibold text-red-900"
        >
          {f('alerts')}: {todayEntry.alerts.map((a) => t(`postop.alertCodes.${a}`)).join(', ')}
        </p>
      )}

      {data.can_record && !readOnly && (
        <form
          className="mt-3 grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            save.mutate()
          }}
        >
          <Section
            id="p1"
            number={1}
            title={`${f('today')}${todayEntry ? ` · ${todayEntry.post_op_day === 0 ? f('dayZero') : `${todayEntry.post_op_day}-е ${f('day')}`}` : ''}`}
          >
            <Field label={f('complaints')}>
              <TextArea
                label={f('complaints')}
                value={form.complaints}
                onChange={(v) => set('complaints', v)}
                rows={2}
              />
            </Field>
            <Field label={f('pain')}>
              <Segmented
                label={f('pain')}
                options={Array.from({ length: 11 }, (_, i) => String(i))}
                value={form.pain_vas === null ? null : String(form.pain_vas)}
                onChange={(v) => set('pain_vas', v === null ? null : Number(v))}
              />
            </Field>
            <Field label={f('consciousness')}>
              <Segmented
                label={f('consciousness')}
                options={pick.consciousness ?? []}
                value={form.consciousness}
                onChange={(v) => set('consciousness', v)}
              />
            </Field>
          </Section>

          <Section id="p2" number={2} title={f('vitals')}>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={f('bp')}>
                <BloodPressure
                  label={f('bp')}
                  value={form.vitals.bp}
                  onChange={(v) => set('vitals.bp', v)}
                />
              </Field>
              <Field label={f('pulse')}>
                <Num
                  label={f('pulse')}
                  value={form.vitals.pulse}
                  onChange={(v) => set('vitals.pulse', v)}
                  min={20}
                  max={250}
                />
              </Field>
              <Field label={f('rr')}>
                <Num
                  label={f('rr')}
                  value={form.vitals.rr}
                  onChange={(v) => set('vitals.rr', v)}
                  min={4}
                  max={80}
                />
              </Field>
              <Field label={f('spo2')}>
                <Num
                  label={f('spo2')}
                  value={form.vitals.spo2}
                  onChange={(v) => set('vitals.spo2', v)}
                  min={50}
                  max={100}
                />
              </Field>
              <Field label={f('temp')}>
                <Num
                  label={f('temp')}
                  value={form.vitals.temp}
                  onChange={(v) => set('vitals.temp', v)}
                  decimal
                  min={30}
                  max={45}
                />
              </Field>
              <Field label={f('cvp')}>
                <Num
                  label={f('cvp')}
                  value={form.vitals.cvp}
                  onChange={(v) => set('vitals.cvp', v)}
                  decimal
                  negative
                />
              </Field>
            </div>
          </Section>

          <Section id="p3" number={3} title={f('wound')}>
            <Field label={f('dressing')}>
              <Segmented
                label={f('dressing')}
                options={pick.dressing ?? []}
                value={form.wound.dressing}
                onChange={(v) => set('wound.dressing', v)}
              />
            </Field>
            <Field label={f('discharge')}>
              <Segmented
                label={f('discharge')}
                options={pick.wound_discharge ?? []}
                value={form.wound.discharge}
                onChange={(v) => set('wound.discharge', v)}
              />
            </Field>
            <Check
              label={f('redness')}
              checked={form.wound.redness}
              onChange={(v) => set('wound.redness', v)}
            />
            <Check
              label={f('swelling')}
              checked={form.wound.swelling}
              onChange={(v) => set('wound.swelling', v)}
            />
            <Field label={f('sutures')}>
              <Text
                label={f('sutures')}
                value={form.wound.sutures ?? ''}
                onChange={(v) => set('wound.sutures', v || null)}
              />
            </Field>
            <Check
              label={f('dressingChanged')}
              checked={form.wound.dressing_changed}
              onChange={(v) => set('wound.dressing_changed', v)}
            />
          </Section>

          <Section id="p4" number={4} title={f('drain')}>
            <Check
              label={f('drainPresent')}
              checked={form.drain.present}
              onChange={(v) => set('drain.present', v)}
            />
            {form.drain.present && (
              <>
                <Field label={f('drainOutput')}>
                  <Num
                    label={f('drainOutput')}
                    value={form.drain.output_ml}
                    onChange={(v) => set('drain.output_ml', v)}
                    min={0}
                    max={5000}
                  />
                </Field>
                <Check
                  label={f('drainRemoved')}
                  checked={form.drain.removed}
                  onChange={(v) => set('drain.removed', v)}
                />
              </>
            )}
          </Section>

          <Section id="p5" number={5} title={f('neuro')}>
            {(['pulsation', 'sensation', 'motor'] as const).map((k) => (
              <Field key={k} label={f(k)}>
                <Segmented
                  label={f(k)}
                  options={pick[k] ?? []}
                  value={form.neurovascular[k]}
                  onChange={(v) => set(`neurovascular.${k}`, v)}
                />
              </Field>
            ))}
            <Check
              label={f('calf')}
              checked={form.calf_tenderness}
              onChange={(v) => set('calf_tenderness', v)}
            />
          </Section>

          <Section id="p6" number={6} title={f('mobilization')}>
            <Field label={f('level')}>
              <Segmented
                label={f('level')}
                options={pick.mobilization ?? []}
                value={form.mobilization.level}
                onChange={(v) => set('mobilization.level', v)}
              />
            </Field>
            <Field label={f('weightBearing')}>
              <Segmented
                label={f('weightBearing')}
                options={pick.weight_bearing ?? []}
                value={form.mobilization.weight_bearing}
                onChange={(v) => set('mobilization.weight_bearing', v)}
              />
            </Field>
            <Check
              label={f('physio')}
              checked={form.mobilization.physiotherapy}
              onChange={(v) => set('mobilization.physiotherapy', v)}
            />
          </Section>

          <Section id="p7" number={7} title={f('therapy')}>
            <Field label={f('abDay')}>
              <Num
                label={f('abDay')}
                value={form.therapy.antibiotic_day}
                onChange={(v) => set('therapy.antibiotic_day', v)}
                min={1}
                max={60}
              />
            </Field>
            <Check
              label={f('vte')}
              checked={form.therapy.vte_prophylaxis}
              onChange={(v) => set('therapy.vte_prophylaxis', v)}
            />
            <Field label={f('analgesia')}>
              <Text
                label={f('analgesia')}
                value={form.therapy.analgesia}
                onChange={(v) => set('therapy.analgesia', v)}
              />
            </Field>
            <Field label={f('recommendations')}>
              <TextArea
                label={f('recommendations')}
                value={form.recommendations}
                onChange={(v) => set('recommendations', v)}
                rows={2}
              />
            </Field>
          </Section>

          <div className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-300 bg-white p-2">
            <div className="mx-auto flex max-w-3xl items-center gap-3">
              {message && (
                <span role="status" className="text-sm font-semibold text-green-800">
                  {message}
                </span>
              )}
              {error && (
                <span role="alert" className="text-sm text-red-700">
                  {error}
                </span>
              )}
              <button
                type="submit"
                disabled={save.isPending}
                className="ml-auto min-h-11 rounded bg-teal-700 px-6 font-medium text-white disabled:opacity-60"
              >
                {f('save')}
              </button>
            </div>
          </div>
        </form>
      )}

      {current && (
        <NotePanel
          caseId={id}
          entry={current}
          canEdit={data.can_edit}
          photoEnabled={data.photo_enabled}
          onChanged={() => void refresh()}
        />
      )}

      <section className="mt-6" aria-labelledby="trends">
        <h2 id="trends" className="text-lg font-semibold">
          {f('trends')}
        </h2>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <TrendChart
            title={f('trendTemp')}
            unit="°C"
            points={data.trends.map((p) => ({ day: p.day, value: p.temp }))}
          />
          <TrendChart
            title={f('trendDrain')}
            unit="мл"
            integer
            points={data.trends.map((p) => ({ day: p.day, value: p.drain_ml }))}
          />
          <TrendChart
            title={f('trendPain')}
            unit="ВАШ"
            integer
            points={data.trends.map((p) => ({ day: p.day, value: p.pain }))}
          />
          <figure className="rounded border border-slate-300 bg-white p-3">
            <figcaption className="text-sm font-semibold">{f('trendWound')}</figcaption>
            <table className="mt-2 w-full text-sm">
              <thead>
                <tr className="text-left text-slate-600">
                  <th className="py-1 font-medium">{f('day')}</th>
                  <th className="py-1 font-medium">{f('discharge')}</th>
                  <th className="py-1 font-medium">{f('redness')}</th>
                  <th className="py-1 font-medium">{f('swelling')}</th>
                </tr>
              </thead>
              <tbody>
                {data.trends.map((p) => (
                  <tr key={p.day} className="border-t border-slate-100">
                    <td className="py-1">{p.day}</td>
                    <td className="py-1">{p.discharge ?? '—'}</td>
                    <td className="py-1">{p.redness ? 'есть' : 'нет'}</td>
                    <td className="py-1">{p.swelling ? 'есть' : 'нет'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </figure>
        </div>
      </section>

      {data.entries.length > 0 && (
        <section className="mt-6" aria-labelledby="days">
          <h2 id="days" className="text-lg font-semibold">
            {f('entries')}
          </h2>
          <ul className="mt-2 grid gap-2">
            {data.entries.map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  onClick={() => setSelected(e.id)}
                  className={`min-h-11 w-full rounded border px-3 py-2 text-left text-sm ${current?.id === e.id ? 'border-teal-800 bg-teal-50' : 'border-slate-300 bg-white'}`}
                >
                  <strong>
                    {e.post_op_day === 0 ? f('dayZero') : `${e.post_op_day}-е ${f('day')}`}
                  </strong>{' '}
                  · {formatDateTime(e.entered_at)}
                  {e.note?.approved ? ` · ✔ ${f('noteChecked')}` : ''}
                  {e.alerts.length > 0 ? ` · ⚠ ${f('alerts')}` : ''}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  )
}

function NotePanel({
  caseId,
  entry,
  canEdit,
  photoEnabled,
  onChanged,
}: {
  caseId: string
  entry: PostOpEntry
  canEdit: boolean
  photoEnabled: boolean
  onChanged: () => void
}) {
  const { t } = useTranslation('intake')
  const { t: tc } = useTranslation()
  const note = entry.note
  const [general, setGeneral] = useState(note?.general_condition ?? '')
  const [local, setLocal] = useState(note?.local_status ?? '')
  const [syncedKey, setSyncedKey] = useState(
    `${entry.id}|${note?.general_condition}|${note?.local_status}`,
  )
  const key = `${entry.id}|${note?.general_condition}|${note?.local_status}`
  if (key !== syncedKey) {
    // The draft was regenerated (or another entry was opened): show the new text.
    setSyncedKey(key)
    setGeneral(note?.general_condition ?? '')
    setLocal(note?.local_status ?? '')
  }
  const [error, setError] = useState<string | null>(null)
  const base = `/cases/${caseId}/postop/${entry.id}`
  const approve = useMutation({
    mutationFn: () =>
      api.post<PostOpEntry>(`${base}/note/approve`, {
        general_condition: general,
        local_status: local,
      }),
    onSuccess: () => {
      setError(null)
      onChanged()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : tc('errors.unknown')),
  })
  const regenerate = useMutation({
    mutationFn: () => api.post<PostOpEntry>(`${base}/note/regenerate`),
    onSuccess: onChanged,
  })
  const upload = useMutation({
    mutationFn: async (file: File) => {
      const response = await fetch(`/api/v1${base}/photo`, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: {
          'Content-Type': file.type,
          'X-CSRF-Token': document.cookie.match(/csrf_token=([^;]+)/)?.[1] ?? '',
        },
        body: file,
      })
      if (!response.ok)
        throw new ApiError(
          response.status,
          'upload',
          ((await response.json().catch(() => ({}))) as { message?: string }).message ??
            tc('errors.unknown'),
        )
    },
    onSuccess: () => {
      setError(null)
      onChanged()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : tc('errors.unknown')),
  })

  if (!note) return null
  return (
    <section className="mt-6 rounded border border-slate-300 bg-white p-3" aria-labelledby="note-h">
      <h2 id="note-h" className="text-lg font-semibold">
        {t('postop.note')} ·{' '}
        {entry.post_op_day === 0
          ? t('postop.dayZero')
          : `${entry.post_op_day}-е ${t('postop.day')}`}
      </h2>
      <p
        className={`mt-1 text-sm ${note.approved ? 'text-green-800' : 'text-amber-900'}`}
        data-testid="note-state"
      >
        {note.approved
          ? `✔ ${t('postop.noteChecked')}${note.approved_by_name ? ` · ${t('postop.approvedBy')}: ${note.approved_by_name}` : ''}`
          : t('postop.noteDraft')}
        <span className="ml-2 text-xs text-slate-600">
          ({t(`postop.generator.${note.generator}`)})
        </span>
      </p>
      <label className="mt-3 grid gap-1 text-sm font-medium">
        {t('postop.generalCondition')}
        <textarea
          value={general}
          onChange={(e) => setGeneral(e.target.value)}
          rows={4}
          maxLength={1500}
          disabled={!canEdit}
          className="rounded border border-slate-400 p-2 text-base"
        />
      </label>
      <label className="mt-3 grid gap-1 text-sm font-medium">
        {t('postop.localStatus')}
        <textarea
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          rows={4}
          maxLength={1500}
          disabled={!canEdit}
          className="rounded border border-slate-400 p-2 text-base"
        />
      </label>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {canEdit && (
          <>
            <button
              type="button"
              disabled={approve.isPending || !general.trim() || !local.trim()}
              onClick={() => approve.mutate()}
              className="min-h-11 rounded bg-teal-700 px-5 font-medium text-white disabled:opacity-50"
            >
              {t('postop.approve')}
            </button>
            <button
              type="button"
              onClick={() => regenerate.mutate()}
              className="min-h-11 rounded border border-slate-400 px-4 text-sm"
            >
              {t('postop.regenerate')}
            </button>
          </>
        )}
        <Link
          to={`/case/${caseId}/postop/${entry.id}/document`}
          className="inline-flex min-h-11 items-center rounded border border-teal-800 px-4 text-sm font-medium text-teal-900"
        >
          {t('postop.openDocument')}
        </Link>
      </div>
      <div className="mt-4">
        <p className="text-sm font-medium">{t('postop.photo')}</p>
        {entry.has_photo && (
          <img
            src={`/api/v1${base}/photo`}
            alt={t('postop.photo')}
            className="mt-1 max-h-48 rounded border"
          />
        )}
        {photoEnabled && canEdit ? (
          <label className="mt-1 inline-flex min-h-11 cursor-pointer items-center rounded border border-slate-400 px-3 text-sm">
            {t('postop.photoUpload')}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])}
            />
          </label>
        ) : (
          !photoEnabled && <p className="text-xs text-slate-600">{t('postop.photoDisabled')}</p>
        )}
      </div>
    </section>
  )
}
