import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { z } from 'zod'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { isClinical } from '../lib/permissions'

const schema = z.object({ login: z.string().min(1), password: z.string().min(1) })
type Form = z.infer<typeof schema>

export function LoginPage() {
  const { t } = useTranslation()
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const rawNext = params.get('next')
  // Only same-site paths: never redirect to another origin after login.
  const next = rawNext && rawNext.startsWith('/') && !rawNext.startsWith('//') ? rawNext : null
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState } = useForm<Form>({ resolver: zodResolver(schema) })

  if (user) return <Navigate to={next ?? (isClinical(user.role) ? '/' : '/admin/users')} replace />

  const onSubmit = handleSubmit(async (values) => {
    setError(null)
    try {
      const u = await login(values.login, values.password)
      navigate(next ?? (isClinical(u.role) ? '/' : '/admin/users'), { replace: true })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t('errors.unknown'))
    }
  })

  return (
    <main className="mx-auto max-w-sm px-4 py-10">
      <h1 className="text-2xl font-bold">{t('app.name')}</h1>
      <p className="mt-1 text-slate-700">{t('app.tagline')}</p>
      {params.get('expired') && (
        <p role="status" className="mt-4 rounded bg-amber-50 p-3 text-sm text-amber-900">
          {t('login.expired')}
        </p>
      )}
      <form onSubmit={onSubmit} className="mt-6 grid gap-4" noValidate>
        <label className="grid gap-1 text-sm font-medium">
          {t('login.login')}
          <input
            {...register('login')}
            autoComplete="username"
            autoCapitalize="none"
            className="min-h-11 rounded border border-slate-400 px-3 text-base"
          />
        </label>
        <label className="grid gap-1 text-sm font-medium">
          {t('login.password')}
          <input
            {...register('password')}
            type="password"
            autoComplete="current-password"
            className="min-h-11 rounded border border-slate-400 px-3 text-base"
          />
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
          {t('login.submit')}
        </button>
      </form>
    </main>
  )
}
