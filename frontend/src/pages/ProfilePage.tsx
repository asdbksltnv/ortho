import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api/client'
import type { TelegramLink } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { formatDateTime } from '../lib/format'

export function ProfilePage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [link, setLink] = useState<TelegramLink | null>(null)
  const refreshMe = () => queryClient.invalidateQueries({ queryKey: ['me'] })

  const getCode = useMutation({
    mutationFn: () => api.post<TelegramLink>('/telegram/link-code'),
    onSuccess: setLink,
  })
  const unlink = useMutation({
    mutationFn: () => api.delete<void>('/telegram/link'),
    onSuccess: () => {
      setLink(null)
      void refreshMe()
    },
  })

  if (!user) return null
  return (
    <main className="mx-auto max-w-xl px-3 py-4">
      <h1 className="text-xl font-bold">{t('profile.title')}</h1>
      <p className="mt-1 text-sm text-slate-700">
        {user.full_name} · {t(`roles.${user.role}`)}
      </p>
      <section className="mt-4 rounded border border-slate-300 bg-white p-4" aria-labelledby="tg">
        <h2 id="tg" className="text-lg font-semibold">
          {t('profile.telegram')}
        </h2>
        <p className="mt-1 text-sm">
          {user.telegram_linked ? t('profile.linked') : t('profile.notLinked')}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => getCode.mutate()}
            className="min-h-11 rounded bg-teal-700 px-4 text-white"
          >
            {t('profile.getCode')}
          </button>
          {user.telegram_linked && (
            <button
              type="button"
              onClick={() => unlink.mutate()}
              className="min-h-11 rounded border border-slate-400 px-4"
            >
              {t('profile.unlink')}
            </button>
          )}
        </div>
        {link && (
          <div className="mt-3 rounded bg-slate-100 p-3" role="status">
            <p className="text-sm">{t('profile.instruction')}</p>
            <p className="mt-1 select-all font-mono text-lg font-bold" data-testid="link-command">
              {link.command}
            </p>
            <p className="mt-1 text-xs text-slate-600">
              {t('profile.expires')} ({formatDateTime(link.expires_at)})
            </p>
          </div>
        )}
        <p className="mt-3 text-xs text-slate-600">{t('profile.noNames')}</p>
      </section>
    </main>
  )
}
