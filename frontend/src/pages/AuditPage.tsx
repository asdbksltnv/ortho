import { useInfiniteQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '../api/client'
import type { AuditPage as Page } from '../api/types'
import { formatDateTime } from '../lib/format'

export function AuditPage() {
  const { t } = useTranslation()
  const query = useInfiniteQuery({
    queryKey: ['audit'],
    queryFn: ({ pageParam }) =>
      api.get<Page>(
        `/audit?limit=50${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ''}`,
      ),
    initialPageParam: '',
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
  const rows = query.data?.pages.flatMap((p) => p.items) ?? []
  return (
    <main className="mx-auto max-w-5xl px-3 py-4">
      <h1 className="text-xl font-bold">{t('admin.audit')}</h1>
      <div className="mt-3 overflow-x-auto rounded border border-slate-300 bg-white">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="px-3 py-2">{t('admin.when')}</th>
              <th className="px-3 py-2">{t('admin.action')}</th>
              <th className="px-3 py-2">{t('admin.entity')}</th>
              <th className="px-3 py-2">{t('admin.details')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-200">
                <td className="whitespace-nowrap px-3 py-1">{formatDateTime(r.created_at)}</td>
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
