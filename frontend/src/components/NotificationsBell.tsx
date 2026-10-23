import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { AppNotification } from '../api/types'
import { formatDateTime } from '../lib/format'

export function NotificationsBell() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const query = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.get<AppNotification[]>('/notifications'),
    refetchInterval: 15_000,
  })
  const readAll = useMutation({
    mutationFn: () => api.post<void>('/notifications/read-all'),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
  const unread = query.data?.filter((n) => !n.read).length ?? 0

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={`${t('bell.title')}${unread ? `: ${unread}` : ''}`}
        className="min-h-11 min-w-11 rounded border border-teal-200 px-3 text-white hover:bg-teal-800"
      >
        <span aria-hidden>🔔</span>
        {unread > 0 && (
          <span
            className="ml-1 rounded-full bg-red-600 px-1.5 text-xs font-bold"
            data-testid="unread-count"
          >
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div
          role="dialog"
          aria-label={t('bell.title')}
          className="absolute right-0 z-30 mt-1 w-80 max-w-[90vw] rounded border border-slate-300 bg-white p-2 text-slate-900 shadow-lg"
        >
          <div className="flex items-center justify-between">
            <strong className="text-sm">{t('bell.title')}</strong>
            <button
              type="button"
              onClick={() => readAll.mutate()}
              className="min-h-11 text-xs underline"
            >
              {t('bell.markRead')}
            </button>
          </div>
          <ul className="max-h-80 overflow-y-auto">
            {query.data?.length === 0 && (
              <li className="p-2 text-sm text-slate-600">{t('bell.empty')}</li>
            )}
            {query.data?.map((n) => (
              <li
                key={n.id}
                className={`border-t border-slate-100 p-2 text-sm ${n.read ? '' : 'font-semibold'}`}
              >
                {n.case_id ? (
                  <Link
                    to={`/case/${n.case_id}`}
                    onClick={() => setOpen(false)}
                    className="underline"
                  >
                    {n.text}
                  </Link>
                ) : (
                  n.text
                )}
                <span className="block text-xs font-normal text-slate-600">
                  {formatDateTime(n.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
