import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'
import { api, ApiError } from '../../api/client'
import type { Role, User } from '../../api/types'
import { ConfigWarning } from '../../components/ConfigWarning'

const ROLES: Role[] = [
  'doctor',
  'nurse',
  'anaesthesiologist',
  'head_of_department',
  'head_nurse',
  'admin',
]

const schema = z.object({
  login: z
    .string()
    .min(3)
    .regex(/^[a-zA-Z0-9._-]+$/),
  full_name: z.string().min(2),
  role: z.enum([
    'doctor',
    'nurse',
    'anaesthesiologist',
    'head_of_department',
    'head_nurse',
    'admin',
  ]),
  password: z.string().min(10),
})
type Form = z.infer<typeof schema>

export function UsersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const users = useQuery({ queryKey: ['users'], queryFn: () => api.get<User[]>('/users') })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['users'] })

  const { register, handleSubmit, reset, formState } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { role: 'doctor' },
  })
  const create = useMutation({
    mutationFn: (v: Form) => api.post<User>('/users', v),
    onSuccess: () => {
      reset({ role: 'doctor', login: '', full_name: '', password: '' })
      void refresh()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : t('errors.unknown')),
  })
  const patch = useMutation({
    mutationFn: ({ id, ...body }: { id: string; role?: Role; is_active?: boolean }) =>
      api.patch<User>(`/users/${id}`, body),
    onSuccess: () => void refresh(),
    onError: (e) => setError(e instanceof ApiError ? e.message : t('errors.unknown')),
  })
  const reset_ = useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) =>
      api.post(`/users/${id}/reset-password`, { password }),
    onError: (e) => setError(e instanceof ApiError ? e.message : t('errors.unknown')),
  })

  const input = 'min-h-11 rounded border border-slate-400 bg-white px-3'
  return (
    <main className="mx-auto max-w-4xl px-3 py-4">
      <h1 className="text-xl font-bold">{t('admin.users')}</h1>
      <div className="mt-3">
        <ConfigWarning />
      </div>
      {error && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <form
        onSubmit={handleSubmit((v) => {
          setError(null)
          create.mutate(v)
        })}
        className="mt-4 grid gap-2 rounded border border-slate-300 bg-white p-3 sm:grid-cols-2"
        noValidate
      >
        <h2 className="font-semibold sm:col-span-2">{t('admin.newUser')}</h2>
        <input
          {...register('login')}
          placeholder={t('admin.loginField')}
          className={input}
          autoCapitalize="none"
        />
        <input {...register('full_name')} placeholder={t('admin.fullName')} className={input} />
        <select {...register('role')} className={input} aria-label={t('admin.role')}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {t(`roles.${r}`)}
            </option>
          ))}
        </select>
        <input
          {...register('password')}
          type="password"
          autoComplete="new-password"
          placeholder={t('admin.password')}
          className={input}
        />
        {Object.keys(formState.errors).length > 0 && (
          <p className="text-sm text-red-700 sm:col-span-2">{t('newCase.required')}</p>
        )}
        <button type="submit" className="min-h-11 rounded bg-teal-700 text-white sm:col-span-2">
          {t('common.create')}
        </button>
      </form>

      <ul className="mt-4 divide-y divide-slate-200 rounded border border-slate-300 bg-white">
        {users.data?.map((u) => (
          <li key={u.id} className="flex flex-wrap items-center gap-2 p-3">
            <div className="mr-auto">
              <div className="font-medium">{u.full_name}</div>
              <div className="text-xs text-slate-600">
                {u.login} · {u.is_active ? t('admin.active') : t('admin.inactive')}
              </div>
            </div>
            <select
              aria-label={t('admin.role')}
              value={u.role}
              onChange={(e) => patch.mutate({ id: u.id, role: e.target.value as Role })}
              className={input}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`roles.${r}`)}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="min-h-11 rounded border border-slate-400 px-3 text-sm"
              onClick={() => patch.mutate({ id: u.id, is_active: !u.is_active })}
            >
              {u.is_active ? t('admin.block') : t('admin.unblock')}
            </button>
            <button
              type="button"
              className="min-h-11 rounded border border-slate-400 px-3 text-sm"
              onClick={() => {
                const password = window.prompt(t('admin.newPassword'))
                if (password) reset_.mutate({ id: u.id, password })
              }}
            >
              {t('admin.resetPassword')}
            </button>
          </li>
        ))}
      </ul>
    </main>
  )
}
