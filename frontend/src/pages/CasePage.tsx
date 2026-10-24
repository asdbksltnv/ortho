import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { CaseDetail, Definitions, LabResult } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ChecklistEditor } from '../components/ChecklistEditor'
import { OrdersPanel } from '../components/OrdersPanel'
import { StatusPanel } from '../components/StatusPanel'
import { StatusIcon } from '../components/StatusIcon'
import { Icon } from '../components/Icon'
import { useToast } from '../components/Toast'
import { formatDate, formatDateTime } from '../lib/format'
import { canEditItem, canWriteRecords } from '../lib/permissions'

export function CasePage() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [editingKey, setEditingKey] = useState<string | null>(null)

  const caseQuery = useQuery({
    queryKey: ['case', id],
    queryFn: () => api.get<CaseDetail>(`/cases/${id}`),
    refetchInterval: 10_000,
  })
  const defs = useQuery({
    queryKey: ['definitions'],
    queryFn: () => api.get<Definitions>('/config/definitions'),
    staleTime: Infinity,
  })
  const labs = useQuery({
    queryKey: ['labs', id],
    queryFn: () => api.get<LabResult[]>(`/cases/${id}/labs`),
  })

  const update = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patch<CaseDetail>(`/cases/${id}`, body),
    onSuccess: (data) => {
      queryClient.setQueryData(['case', id], data)
      void queryClient.invalidateQueries({ queryKey: ['board'] })
      toast(t('case.toastSaved'))
    },
    onError: () => toast(t('errors.unknown'), 'error'),
  })

  const consent = useMutation({
    mutationFn: (type: 'surgical' | 'anaesthesia') =>
      api.post(`/cases/${id}/consents`, { type, signed_at: new Date().toISOString() }),
    onSuccess: () => toast(t('case.toastConsent')),
  })

  const addLab = useMutation({
    mutationFn: (body: { lab_code: string; result_text: string }) =>
      api.post(`/cases/${id}/labs`, { ...body, collected_at: new Date().toISOString() }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['labs', id] })
      toast(t('case.toastLab'))
    },
  })

  const [labCode, setLabCode] = useState('hbsag')
  const [labText, setLabText] = useState('')

  if (!user) return null
  if (caseQuery.isLoading) return <p className="p-4">{t('common.loading')}</p>
  if (caseQuery.isError || !caseQuery.data)
    return <p className="p-4 text-red-700">{t('common.error')}</p>
  const c = caseQuery.data
  const columns = defs.data?.checklist ?? []
  const isOwn = c.treating_doctor.id === user.id
  const editingItem = c.items.find((i) => i.key === editingKey)
  const editingCol = columns.find((col) => col.key === editingKey)

  const applicable = c.readiness.applicable ?? c.items.map((i) => i.key)
  const done = Math.max(0, applicable.length - c.readiness.blocking.length)
  const pct = applicable.length ? Math.round((done / applicable.length) * 100) : 100
  const labName = (code: string) => defs.data?.labs?.find((l) => l.code === code)?.name_ru ?? code
  // Blocking items first, then the rest in configured order.
  const orderedItems = [...c.items].sort(
    (a, b) =>
      Number(c.readiness.blocking.includes(b.key)) - Number(c.readiness.blocking.includes(a.key)),
  )
  const card = 'rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm sm:p-5'
  const linkBtn =
    'inline-flex min-h-11 shrink-0 items-center gap-2 rounded-xl border px-4 text-sm font-medium shadow-sm transition-colors'

  return (
    <main className="mx-auto max-w-6xl px-3 py-4">
      <header className={card}>
        <div className="flex flex-wrap items-center gap-3">
          <span
            aria-hidden
            className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-600 to-teal-800 text-lg font-bold text-white shadow-sm"
          >
            {c.patient.full_name
              .split(/\s+/)
              .slice(0, 2)
              .map((p) => p[0] ?? '')
              .join('')
              .toUpperCase()}
          </span>
          <h1 className="min-w-0 text-xl font-bold tracking-tight md:text-2xl">
            {c.patient.full_name}
          </h1>
          {c.is_emergency && (
            <span className="rounded bg-red-700 px-2 py-0.5 text-xs font-semibold text-white">
              {t('board.emergency')}
            </span>
          )}
        </div>
        <div className="mt-2 flex flex-wrap gap-2 text-sm">
          <Chip>{c.bed_label ? `${c.room_name}, ${c.bed_label}` : t('case.noBed')}</Chip>
          <Chip>{t(`caseStatus.${c.status}`)}</Chip>
          <Chip>
            {c.procedure_label}
            {c.side ? ` · ${t(`case.${c.side}`)}` : ''}
          </Chip>
          <Chip>
            {formatDate(c.planned_surgery_date)}
            {c.planned_surgery_time ? ` ${c.planned_surgery_time.slice(0, 5)}` : ''}
          </Chip>
        </div>
        <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1 text-sm text-slate-700 sm:grid-cols-2 lg:grid-cols-4">
          <Field label={t('case.birth')} value={formatDate(c.patient.birth_date)} />
          <Field
            label={t('case.sex')}
            value={c.patient.sex === 'M' ? t('case.male') : t('case.female')}
          />
          <Field label={t('case.mrn')} value={c.patient.medical_record_number} />
          <Field label={t('case.doctor')} value={c.treating_doctor.full_name} />
        </dl>
        <div
          className={`mt-3 rounded-lg p-3 ${c.readiness.ready ? 'bg-green-50 text-green-900' : 'bg-red-50 text-red-900'}`}
        >
          <div className="flex items-center justify-between gap-2 text-sm font-semibold">
            <span>{c.readiness.ready ? `✔ ${t('case.readyYes')}` : `✖ ${t('case.readyNo')}`}</span>
            <span className="font-normal">
              {done}/{applicable.length}
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/70" aria-hidden>
            <div
              className={`h-full rounded-full ${c.readiness.ready ? 'bg-green-600' : 'bg-red-600'}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          {!c.readiness.ready && (
            <p className="mt-2 text-sm">
              {t('board.missing')}:{' '}
              {c.readiness.blocking
                .map((k) => columns.find((col) => col.key === k)?.short_label_ru ?? k)
                .join(', ')}
            </p>
          )}
        </div>
        {c.override_reason && <p className="mt-2 text-sm text-amber-900">{c.override_reason}</p>}
      </header>

      <nav
        className="-mx-3 mt-3 flex gap-2 overflow-x-auto px-3 pb-1"
        aria-label="Разделы карточки"
      >
        <Link
          to={`/case/${c.id}/intake`}
          className={`${linkBtn} border-teal-700 bg-teal-700 text-white hover:bg-teal-800`}
        >
          <Icon name="clipboard" size={18} />
          {t('case.intake')}
        </Link>
        <Link
          to={`/case/${c.id}/documents`}
          className={`${linkBtn} border-teal-200 bg-white text-teal-900 hover:border-teal-600 hover:bg-teal-50`}
        >
          <Icon name="docs" size={18} />
          {t('case.documents')}
        </Link>
        <Link
          to={`/case/${c.id}/postop`}
          className={`${linkBtn} border-teal-200 bg-white text-teal-900 hover:border-teal-600 hover:bg-teal-50`}
        >
          <Icon name="pulse" size={18} />
          {t('case.postop')}
        </Link>
        <Link
          to={`/case/${c.id}/label`}
          className={`${linkBtn} border-slate-300 bg-white text-slate-800 hover:bg-slate-50`}
        >
          <Icon name="qr" size={18} />
          {t('label.open')}
        </Link>
      </nav>

      <div className="grid gap-x-4 lg:grid-cols-2">
        <div>
          <section className={`mt-4 ${card}`} aria-labelledby="chk">
            <h2 id="chk" className="text-lg font-semibold">
              {t('case.checklist')}
            </h2>
            <ul className="mt-2 divide-y divide-slate-100">
              {orderedItems.map((item) => {
                const col = columns.find((d) => d.key === item.key)
                const blocking = c.readiness.blocking.includes(item.key)
                const touched = item.status !== 'not_started'
                return (
                  <li key={item.key}>
                    <button
                      type="button"
                      onClick={() => setEditingKey(item.key)}
                      className="flex min-h-12 w-full items-center gap-3 rounded-lg px-1 py-1 text-left hover:bg-slate-50"
                    >
                      <StatusIcon status={item.status} />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium">
                          {col?.label_ru ?? item.key}
                        </span>
                        <span className="block text-xs text-slate-600">
                          {t(`itemStatus.${item.status}`)}
                          {item.note ? ` — ${item.note}` : ''}
                          {touched && item.updated_by
                            ? ` · ${item.updated_by}, ${formatDateTime(item.updated_at)}`
                            : ''}
                        </span>
                      </span>
                      {blocking && (
                        <span className="shrink-0 rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-900">
                          {t('case.blocking')}
                        </span>
                      )}
                      <span aria-hidden className="text-slate-400">
                        ›
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </section>

          {c.can_edit && (
            <section className={`mt-4 ${card}`} aria-labelledby="params">
              <h2 id="params" className="text-lg font-semibold">
                {t('case.params')}
              </h2>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <label className="grid gap-1 text-sm font-medium">
                  {t('case.planned')}
                  <input
                    type="date"
                    defaultValue={c.planned_surgery_date ?? ''}
                    onChange={(e) =>
                      update.mutate({ planned_surgery_date: e.target.value || null })
                    }
                    className="min-h-11 rounded-lg border border-slate-300 px-2"
                  />
                </label>
                <label className="grid gap-1 text-sm font-medium">
                  {t('case.plannedTime')}
                  <input
                    type="time"
                    defaultValue={c.planned_surgery_time?.slice(0, 5) ?? ''}
                    onChange={(e) =>
                      update.mutate({
                        planned_surgery_time: e.target.value ? `${e.target.value}:00` : null,
                      })
                    }
                    className="min-h-11 rounded-lg border border-slate-300 px-2"
                  />
                </label>
              </div>
              <label className="mt-2 flex min-h-11 items-center gap-3">
                <input
                  type="checkbox"
                  className="h-5 w-5"
                  checked={c.takes_anticoagulant}
                  onChange={(e) => update.mutate({ takes_anticoagulant: e.target.checked })}
                />
                {t('case.anticoag')}
              </label>
              <label className="flex min-h-11 items-center gap-3">
                <input
                  type="checkbox"
                  className="h-5 w-5"
                  checked={c.is_emergency}
                  onChange={(e) => update.mutate({ is_emergency: e.target.checked })}
                />
                {t('case.emergency')}
              </label>
            </section>
          )}

          <section className={`mt-4 ${card}`} aria-labelledby="labs">
            <h2 id="labs" className="text-lg font-semibold">
              {t('case.labs')}
            </h2>
            <ul className="mt-2 divide-y divide-slate-100 text-sm">
              {labs.data?.map((l) => (
                <li key={l.id} className="py-1.5">
                  <strong>{labName(l.lab_code)}</strong>: {l.result_text}
                  <span className="block text-xs text-slate-600">
                    {formatDateTime(l.collected_at)}
                    {l.valid_until ? ` · до ${formatDate(l.valid_until)}` : ''}
                  </span>
                </li>
              ))}
              {labs.data?.length === 0 && (
                <li className="py-1 text-slate-600">{t('common.none')}</li>
              )}
            </ul>
            {canWriteRecords(user.role) && (
              <form
                className="mt-3 grid gap-2 sm:grid-cols-[1fr_2fr_auto]"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (labText.trim()) {
                    addLab.mutate({ lab_code: labCode, result_text: labText.trim() })
                    setLabText('')
                  }
                }}
              >
                <select
                  aria-label={t('case.labCode')}
                  value={labCode}
                  onChange={(e) => setLabCode(e.target.value)}
                  className="min-h-11 rounded-lg border border-slate-300 bg-white px-2"
                >
                  {(defs.data?.labs ?? []).map((lab) => (
                    <option key={lab.code} value={lab.code}>
                      {lab.name_ru}
                    </option>
                  ))}
                </select>
                <input
                  aria-label={t('case.labResult')}
                  value={labText}
                  onChange={(e) => setLabText(e.target.value)}
                  maxLength={2000}
                  className="min-h-11 rounded-lg border border-slate-300 px-2"
                  placeholder={t('case.labResult')}
                />
                <button type="submit" className="min-h-11 rounded-lg bg-teal-700 px-4 text-white">
                  {t('case.addLab')}
                </button>
              </form>
            )}
          </section>

          {canWriteRecords(user.role) && (
            <section className={`mt-4 ${card}`}>
              <h2 className="text-lg font-semibold">{t('case.consents')}</h2>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  className="min-h-11 rounded-lg border border-slate-300 px-3"
                  onClick={() => consent.mutate('surgical')}
                >
                  {t('case.recordConsent')}: {t('case.surgical')}
                </button>
                <button
                  type="button"
                  className="min-h-11 rounded-lg border border-slate-300 px-3"
                  onClick={() => consent.mutate('anaesthesia')}
                >
                  {t('case.recordConsent')}: {t('case.anaesthesiaConsent')}
                </button>
              </div>
              {consent.isSuccess && (
                <p role="status" className="mt-2 text-sm text-green-800">
                  {t('case.saved')}
                </p>
              )}
            </section>
          )}
        </div>

        <div>
          <StatusPanel detail={c} />
          <OrdersPanel
            caseId={c.id}
            canCreate={user.role === 'doctor' || user.role === 'head_of_department'}
          />
          {(user.role === 'anaesthesiologist' || user.role === 'head_of_department') && (
            <AnaesthesiaForm
              caseId={c.id}
              type={c.anaesthesia_type}
              remarks={c.anaesthesia_remarks}
            />
          )}
          {user.role !== 'anaesthesiologist' &&
            user.role !== 'head_of_department' &&
            c.anaesthesia_type && (
              <p className={`mt-4 ${card} text-sm`}>
                {t('case.anaesthesiaType')}: <strong>{c.anaesthesia_type}</strong>
              </p>
            )}
        </div>
      </div>

      {editingKey && editingItem && (
        <ChecklistEditor
          key={`${editingKey}-${editingItem.updated_at}`}
          caseId={c.id}
          itemKey={editingKey}
          label={editingCol?.label_ru ?? editingKey}
          status={editingItem.status}
          note={editingItem.note}
          updatedAt={editingItem.updated_at}
          updatedBy={editingItem.updated_by}
          canEdit={canEditItem(user.role, editingKey, editingCol?.owner_role ?? 'doctor', isOwn)}
          onClose={() => setEditingKey(null)}
        />
      )}
    </main>
  )
}

function Chip({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-800">{children}</span>
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-slate-600">{label}:</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  )
}

function AnaesthesiaForm({
  caseId,
  type,
  remarks,
}: {
  caseId: string
  type: string | null
  remarks: string | null
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [typeValue, setType] = useState(type ?? '')
  const [remarksValue, setRemarks] = useState(remarks ?? '')
  const save = useMutation({
    mutationFn: () =>
      api.put<CaseDetail>(`/cases/${caseId}/anaesthesia`, {
        type: typeValue || null,
        remarks: remarksValue || null,
      }),
    onSuccess: (data) => queryClient.setQueryData(['case', caseId], data),
  })
  return (
    <section
      className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
      aria-labelledby="an"
    >
      <h2 id="an" className="text-lg font-semibold">
        {t('case.anaesthesia')}
      </h2>
      <label className="mt-2 grid gap-1 text-sm font-medium">
        {t('case.anaesthesiaType')}
        <input
          value={typeValue}
          maxLength={200}
          onChange={(e) => setType(e.target.value)}
          className="min-h-11 rounded-lg border border-slate-300 px-3"
        />
      </label>
      <label className="mt-2 grid gap-1 text-sm font-medium">
        {t('case.anaesthesiaRemarks')}
        <textarea
          value={remarksValue}
          maxLength={2000}
          rows={2}
          onChange={(e) => setRemarks(e.target.value)}
          className="rounded-lg border border-slate-300 p-2"
        />
      </label>
      <button
        type="button"
        onClick={() => save.mutate()}
        className="mt-2 min-h-11 rounded-lg bg-teal-700 px-4 font-medium text-white hover:bg-teal-800"
      >
        {t('common.save')}
      </button>
      {save.isSuccess && (
        <span role="status" className="ml-3 text-sm text-green-800">
          {t('case.saved')}
        </span>
      )}
    </section>
  )
}
