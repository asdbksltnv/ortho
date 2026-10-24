import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { z } from 'zod'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { LogoMark } from '../components/Icon'
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

  const input =
    'min-h-12 rounded-xl border border-slate-300 bg-white px-3.5 text-base shadow-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20'

  return (
    <main className="pb-10">
      <div className="bg-gradient-to-br from-teal-950 via-teal-900 to-teal-700 px-4 pb-24 pt-12 [clip-path:ellipse(140%_100%_at_50%_0%)]">
        <div className="animate-fade-up flex flex-col items-center text-center text-white">
          <span className="inline-flex rounded-2xl bg-white/10 p-2 ring-1 ring-white/25">
            <LogoMark size={48} />
          </span>
          <h1 className="mt-3 text-3xl font-bold tracking-tight">{t('app.name')}</h1>
          <p className="mt-1 text-sm text-teal-50">{t('app.tagline')}</p>
        </div>
      </div>
      <div className="animate-fade-up relative mx-auto -mt-16 w-full max-w-sm px-4">
        <div className="rounded-3xl border border-slate-200/70 bg-white p-6 shadow-xl shadow-teal-950/10">
          <h2 className="text-lg font-semibold text-slate-900">{t('login.title')}</h2>
          {params.get('expired') && (
            <p role="status" className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
              {t('login.expired')}
            </p>
          )}
          <form onSubmit={onSubmit} className="mt-4 grid gap-4" noValidate>
            <label className="grid gap-1.5 text-sm font-medium text-slate-800">
              {t('login.login')}
              <input
                {...register('login')}
                autoComplete="username"
                autoCapitalize="none"
                className={input}
              />
            </label>
            <label className="grid gap-1.5 text-sm font-medium text-slate-800">
              {t('login.password')}
              <input
                {...register('password')}
                type="password"
                autoComplete="current-password"
                className={input}
              />
            </label>
            {error && (
              <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={formState.isSubmitting}
              className="mt-1 min-h-12 rounded-xl bg-teal-700 font-semibold text-white shadow-sm transition-colors hover:bg-teal-800 disabled:opacity-60"
            >
              {t('login.submit')}
            </button>
          </form>
        </div>
      </div>
    </main>
  )
}
