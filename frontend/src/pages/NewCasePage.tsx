import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { api, ApiError } from '../api/client'
import type { Board, CaseDetail, Definitions, Staff, Ward } from '../api/types'
import { useAuth } from '../auth/AuthContext'

const schema = z.object({
  full_name: z.string().min(2),
  birth_date: z.string().min(1),
  sex: z.enum(['M', 'F']),
  medical_record_number: z.string().min(1),
  procedure_key: z.string().min(1),
  side: z.string(),
  bed_id: z.string(),
  planned_surgery_date: z.string(),
  treating_doctor_id: z.string(),
  is_emergency: z.boolean(),
})
type Form = z.infer<typeof schema>

export function NewCasePage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const defs = useQuery({
    queryKey: ['definitions'],
    queryFn: () => api.get<Definitions>('/config/definitions'),
    staleTime: Infinity,
  })
  const wards = useQuery({ queryKey: ['wards'], queryFn: () => api.get<Ward[]>('/wards') })
  const board = useQuery({ queryKey: ['board', 'all'], queryFn: () => api.get<Board>('/board') })
  const staff = useQuery({ queryKey: ['staff'], queryFn: () => api.get<Staff[]>('/staff') })

  const { register, handleSubmit, formState } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: {
      sex: 'M',
      side: '',
      bed_id: '',
      planned_surgery_date: '',
      treating_doctor_id: '',
      is_emergency: false,
    },
  })

  if (!user) return null
  const occupied = new Set(board.data?.rows.map((r) => r.bed_id).filter(Boolean))
  const isHead = user.role === 'head_of_department'
  const doctors =
    staff.data?.filter((s) => s.role === 'doctor' || s.role === 'head_of_department') ?? []

  const onSubmit = handleSubmit(async (v) => {
    setError(null)
    try {
      const created = await api.post<CaseDetail>('/cases', {
        patient: {
          full_name: v.full_name.trim(),
          birth_date: v.birth_date,
          sex: v.sex,
          medical_record_number: v.medical_record_number.trim(),
        },
        procedure_key: v.procedure_key,
        side: v.side || null,
        bed_id: v.bed_id || null,
        planned_surgery_date: v.planned_surgery_date || null,
        treating_doctor_id: isHead ? v.treating_doctor_id || null : null,
        is_emergency: v.is_emergency,
      })
      navigate(`/case/${created.id}`)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t('errors.unknown'))
    }
  })

  const input = 'min-h-11 rounded border border-slate-400 bg-white px-3 text-base'
  return (
    <main className="mx-auto max-w-xl px-3 py-4">
      <h1 className="text-xl font-bold">{t('newCase.title')}</h1>
      <form onSubmit={onSubmit} className="mt-4 grid gap-3" noValidate>
        <label className="grid gap-1 text-sm font-medium">
          {t('newCase.fullName')}
          <input {...register('full_name')} className={input} autoComplete="off" />
          {formState.errors.full_name && (
            <span className="text-red-700">{t('newCase.required')}</span>
          )}
        </label>
        <label className="grid gap-1 text-sm font-medium">
          {t('newCase.birthDate')}
          <input type="date" {...register('birth_date')} className={input} />
          {formState.errors.birth_date && (
            <span className="text-red-700">{t('newCase.required')}</span>
          )}
        </label>
        <label className="grid gap-1 text-sm font-medium">
          {t('newCase.sex')}
          <select {...register('sex')} className={input}>
            <option value="M">{t('case.male')}</option>
            <option value="F">{t('case.female')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium">
          {t('newCase.mrn')}
          <input {...register('medical_record_number')} className={input} autoComplete="off" />
          {formState.errors.medical_record_number && (
            <span className="text-red-700">{t('newCase.required')}</span>
          )}
        </label>
        <label className="grid gap-1 text-sm font-medium">
          {t('newCase.procedure')}
          <select {...register('procedure_key')} className={input}>
            <option value="" />
            {defs.data?.procedures.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label_ru}
              </option>
            ))}
          </select>
          {formState.errors.procedure_key && (
            <span className="text-red-700">{t('newCase.required')}</span>
          )}
        </label>
        <label className="grid gap-1 text-sm font-medium">
          {t('newCase.side')}
          <select {...register('side')} className={input}>
            <option value="">{t('newCase.noSide')}</option>
            <option value="left">{t('case.left')}</option>
            <option value="right">{t('case.right')}</option>
            <option value="both">{t('case.both')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium">
          {t('newCase.bed')}
          <select {...register('bed_id')} className={input}>
            <option value="" />
            {wards.data?.flatMap((w) =>
              w.rooms.flatMap((r) =>
                r.beds
                  .filter((b) => b.is_active && !occupied.has(b.id))
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      {r.name}, {b.label}
                    </option>
                  )),
              ),
            )}
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium">
          {t('newCase.planned')}
          <input type="date" {...register('planned_surgery_date')} className={input} />
        </label>
        {isHead && (
          <label className="grid gap-1 text-sm font-medium">
            {t('newCase.doctor')}
            <select {...register('treating_doctor_id')} className={input}>
              <option value="" />
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.full_name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="flex min-h-11 items-center gap-3 text-sm font-medium">
          <input type="checkbox" {...register('is_emergency')} className="h-5 w-5" />
          {t('newCase.emergency')}
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={formState.isSubmitting}
          className="min-h-11 rounded bg-teal-700 font-medium text-white disabled:opacity-60"
        >
          {t('newCase.create')}
        </button>
      </form>
    </main>
  )
}
