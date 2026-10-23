import { useInfiniteQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api/client'
import type { AuditPage as Page } from '../api/types'
import { formatDateTime } from '../lib/format'

const ENTITIES = [
  'case',
  'checklist_item',
  'order',
  'intake_form',
  'generated_document',
  'postop_entry',
  'ai_note_draft',
  'case_status',
  'user',
  'session',
  'kpi_csv',
]
const ACTIONS = ['view', 'create', 'update', 'delete', 'copy', 'export', 'login']

export function AuditPage() {
  const { t } = useTranslation()
  const [entity, setEntity] = useState('')
  const [action, setAction] = useState('')
  const query = useInfiniteQuery({
    queryKey: ['audit', entity, action],
    queryFn: ({ pageParam }) => {
      const p = new URLSearchParams({ limit: '50' })
      if (pageParam) p.set('cursor', pageParam)
      if (entity) p.set('entity', entity)
      if (action) p.set('action', action)
      return api.get<Page>(`/audit?${p.toString()}`)
    },
    initialPageParam: '',
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
  const rows = query.data?.pages.flatMap((p) => p.items) ?? []
  const select = 'min-h-11 rounded border border-slate-400 bg-white px-2'
  return (
    <main className="mx-auto max-w-5xl px-3 py-4">
      <h1 className="text-xl font-bold">{t('admin.audit')}</h1>
      <div className="mt-3 flex flex-wrap gap-2">
        <select
          aria-label={t('admin.filterEntity')}
          value={entity}
          onChange={(e) => setEntity(e.target.value)}
          className={select}
        >
          <option value="">
            {t('admin.filterEntity')}: {t('admin.all')}
          </option>
          {ENTITIES.map((e) => (
            <option key={e} value={e}>
              {e}
            </option>
          ))}
        </select>
        <select
          aria-label={t('admin.filterAction')}
          value={action}
          onChange={(e) => setAction(e.target.value)}
          className={select}
        >
          <option value="">
            {t('admin.filterAction')}: {t('admin.all')}
          </option>
          {ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>
      <div className="mt-3 overflow-x-auto rounded border border-slate-300 bg-white">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="px-3 py-2">{t('admin.when')}</th>
              <th className="px-3 py-2">{t('admin.user')}</th>
              <th className="px-3 py-2">{t('admin.action')}</th>
              <th className="px-3 py-2">{t('admin.entity')}</th>
              <th className="px-3 py-2">{t('admin.details')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-200">
                <td className="whitespace-nowrap px-3 py-1">{formatDateTime(r.created_at)}</td>
                <td className="px-3 py-1">{r.user_name ?? '—'}</td>
                <td className="px-3 py-1">{r.action}</td>
                <td className="px-3 py-1">{r.entity}</td>
                <td className="break-all px-3 py-1 text-xs">
                  {r.diff ? JSON.stringify(r.diff) : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {query.isLoading && <p className="mt-2">{t('common.loading')}</p>}
      {query.hasNextPage && (
        <button
          type="button"
          onClick={() => void query.fetchNextPage()}
          className="mt-3 min-h-11 rounded border border-slate-400 px-4"
        >
          {t('common.loadMore')}
        </button>
      )}
    </main>
  )
}
