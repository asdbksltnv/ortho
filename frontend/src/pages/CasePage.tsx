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
import { formatDate, formatDateTime } from '../lib/format'
import { canEditItem, canWriteRecords } from '../lib/permissions'

export function CasePage() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
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
    },
  })

  const consent = useMutation({
    mutationFn: (type: 'surgical' | 'anaesthesia') =>
      api.post(`/cases/${id}/consents`, { type, signed_at: new Date().toISOString() }),
  })

  const addLab = useMutation({
    mutationFn: (body: { lab_code: string; result_text: string }) =>
      api.post(`/cases/${id}/labs`, { ...body, collected_at: new Date().toISOString() }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['labs', id] }),
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

  return (
    <main className="mx-auto max-w-3xl px-3 py-4">
      <header className="rounded border border-slate-300 bg-white p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-bold">{c.patient.full_name}</h1>
          {c.is_emergency && (
            <span className="rounded bg-red-700 px-2 py-0.5 text-xs font-semibold text-white">
              {t('board.emergency')}
            </span>
          )}
        </div>
        <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          <Field label={t('case.birth')} value={formatDate(c.patient.birth_date)} />
          <Field
            label={t('case.sex')}
            value={c.patient.sex === 'M' ? t('case.male') : t('case.female')}
          />
          <Field label={t('case.mrn')} value={c.patient.medical_record_number} />
          <Field label={t('case.doctor')} value={c.treating_doctor.full_name} />
          <Field
            label={t('case.bed')}
            value={c.bed_label ? `${c.room_name}, ${c.bed_label}` : t('case.noBed')}
          />
          <Field label={t('case.procedure')} value={c.procedure_label} />
          <Field label={t('case.side')} value={c.side ? t(`case.${c.side}`) : '—'} />
          <Field label={t('case.planned')} value={formatDate(c.planned_surgery_date)} />
          <Field label="Статус" value={t(`caseStatus.${c.status}`)} />
        </dl>
        <p
          className={`mt-3 rounded p-2 text-sm font-semibold ${
            c.readiness.ready ? 'bg-green-50 text-green-900' : 'bg-red-50 text-red-900'
          }`}
        >
          {c.readiness.ready ? `✔ ${t('case.readyYes')}` : `✖ ${t('case.readyNo')}`}
          {!c.readiness.ready && (
            <span className="font-normal">
              {' '}
              — {t('board.missing')}:{' '}
              {c.readiness.blocking
                .map((k) => columns.find((col) => col.key === k)?.short_label_ru ?? k)
                .join(', ')}
            </span>
          )}
        </p>
        {c.override_reason && <p className="mt-2 text-sm text-amber-900">{c.override_reason}</p>}
      </header>

      <nav className="mt-4 flex flex-wrap gap-2" aria-label="Разделы карточки">
        <Link
          to={`/case/${c.id}/intake`}
          className="inline-flex min-h-11 items-center rounded bg-teal-700 px-4 text-sm font-medium text-white"
        >
          {t('case.intake')}
        </Link>
        <Link
          to={`/case/${c.id}/documents`}
          className="inline-flex min-h-11 items-center rounded border border-teal-800 px-4 text-sm font-medium text-teal-900"
        >
          {t('case.documents')}
        </Link>
        <Link
          to={`/case/${c.id}/postop`}
          className="inline-flex min-h-11 items-center rounded border border-teal-800 px-4 text-sm font-medium text-teal-900"
        >
          {t('case.postop')}
        </Link>
      </nav>

      <StatusPanel detail={c} />

      <OrdersPanel
        caseId={c.id}
        canCreate={user.role === 'doctor' || user.role === 'head_of_department'}
      />

      <section className="mt-4 rounded border border-slate-300 bg-white p-4" aria-labelledby="chk">
        <h2 id="chk" className="text-lg font-semibold">
          {t('case.checklist')}
        </h2>
        <ul className="mt-2 divide-y divide-slate-200">
          {c.items.map((item) => {
            const col = columns.find((d) => d.key === item.key)
            return (
              <li key={item.key} className="flex items-center gap-3 py-1">
                <button
                  type="button"
                  onClick={() => setEditingKey(item.key)}
                  className="inline-flex min-h-11 flex-1 items-center gap-3 text-left"
                  aria-label={`${col?.label_ru ?? item.key}: ${t(`itemStatus.${item.status}`)}`}
                >
                  <StatusIcon status={item.status} />
                  <span>
                    <span className="block text-sm font-medium">{col?.label_ru ?? item.key}</span>
                    <span className="block text-xs text-slate-600">
                      {t(`itemStatus.${item.status}`)}
                      {item.note ? ` — ${item.note}` : ''}
                      {item.updated_by
                        ? ` · ${item.updated_by}, ${formatDateTime(item.updated_at)}`
                        : ''}
                    </span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </section>

      {c.can_edit && (
        <section className="mt-4 rounded border border-slate-300 bg-white p-4">
          <label className="flex min-h-11 items-center gap-3">
            <input
              type="checkbox"
              className="h-5 w-5"
              checked={c.takes_anticoagulant}
              onChange={(e) => update.mutate({ takes_anticoagulant: e.target.checked })}
            />
            {t('case.anticoag')}
          </label>
          <label className="mt-2 flex min-h-11 items-center gap-3">
            <input
              type="checkbox"
              className="h-5 w-5"
              checked={c.is_emergency}
              onChange={(e) => update.mutate({ is_emergency: e.target.checked })}
            />
            {t('case.emergency')}
          </label>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            <label className="grid gap-1 text-sm font-medium">
              {t('case.planned')}
              <input
                type="date"
                defaultValue={c.planned_surgery_date ?? ''}
                onChange={(e) => update.mutate({ planned_surgery_date: e.target.value || null })}
                className="min-h-11 rounded border border-slate-400 px-2"
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
                className="min-h-11 rounded border border-slate-400 px-2"
              />
            </label>
          </div>
        </section>
      )}

      <section className="mt-4 rounded border border-slate-300 bg-white p-4" aria-labelledby="labs">
        <h2 id="labs" className="text-lg font-semibold">
          {t('case.labs')}
        </h2>
        <ul className="mt-2 text-sm">
          {labs.data?.map((l) => (
            <li key={l.id} className="border-b border-slate-100 py-1">
              <strong>{l.lab_code}</strong>: {l.result_text} · {formatDateTime(l.collected_at)}
              {l.valid_until ? ` · до ${formatDate(l.valid_until)}` : ''}
            </li>
          ))}
          {labs.data?.length === 0 && <li className="text-slate-600">{t('common.none')}</li>}
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
              className="min-h-11 rounded border border-slate-400 bg-white px-2"
            >
              {['hbsag', 'anti_hcv', 'rw', 'hiv', 'cbc', 'blood_group_rh'].map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
            <input
              aria-label={t('case.labResult')}
              value={labText}
              onChange={(e) => setLabText(e.target.value)}
              maxLength={2000}
              className="min-h-11 rounded border border-slate-400 px-2"
              placeholder={t('case.labResult')}
            />
            <button type="submit" className="min-h-11 rounded bg-teal-700 px-4 text-white">
              {t('case.addLab')}
            </button>
          </form>
        )}
      </section>

      {canWriteRecords(user.role) && (
        <section className="mt-4 rounded border border-slate-300 bg-white p-4">
          <h2 className="text-lg font-semibold">{t('case.consents')}</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              className="min-h-11 rounded border border-slate-400 px-3"
              onClick={() => consent.mutate('surgical')}
            >
              {t('case.recordConsent')}: {t('case.surgical')}
            </button>
            <button
              type="button"
              className="min-h-11 rounded border border-slate-400 px-3"
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

      {(user.role === 'anaesthesiologist' || user.role === 'head_of_department') && (
        <AnaesthesiaForm caseId={c.id} type={c.anaesthesia_type} remarks={c.anaesthesia_remarks} />
      )}
      {user.role !== 'anaesthesiologist' &&
        user.role !== 'head_of_department' &&
        c.anaesthesia_type && (
          <p className="mt-4 rounded border border-slate-300 bg-white p-3 text-sm">
            {t('case.anaesthesiaType')}: <strong>{c.anaesthesia_type}</strong>
          </p>
        )}

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
    <section className="mt-4 rounded border border-slate-300 bg-white p-4" aria-labelledby="an">
      <h2 id="an" className="text-lg font-semibold">
        {t('case.anaesthesia')}
      </h2>
      <label className="mt-2 grid gap-1 text-sm font-medium">
        {t('case.anaesthesiaType')}
        <input
          value={typeValue}
          maxLength={200}
          onChange={(e) => setType(e.target.value)}
          className="min-h-11 rounded border border-slate-400 px-3"
        />
      </label>
      <label className="mt-2 grid gap-1 text-sm font-medium">
        {t('case.anaesthesiaRemarks')}
        <textarea
          value={remarksValue}
          maxLength={2000}
          rows={2}
          onChange={(e) => setRemarks(e.target.value)}
          className="rounded border border-slate-400 p-2"
        />
      </label>
      <button
        type="button"
        onClick={() => save.mutate()}
        className="mt-2 min-h-11 rounded bg-teal-700 px-4 text-white"
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
