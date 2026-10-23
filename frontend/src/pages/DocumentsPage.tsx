import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { DocumentSummary } from '../api/types'
import { formatDateTime } from '../lib/format'

const BADGE: Record<DocumentSummary['status'], string> = {
  awaiting_template: 'bg-slate-200 text-slate-900',
  not_generated: 'bg-slate-200 text-slate-900',
  generated: 'bg-green-100 text-green-900',
  outdated: 'bg-amber-100 text-amber-900',
}

export function DocumentsPage() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const query = useQuery({
    queryKey: ['documents', id],
    queryFn: () => api.get<DocumentSummary[]>(`/cases/${id}/documents`),
  })
  return (
    <main className="mx-auto max-w-3xl px-3 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto text-xl font-bold">{t('docs.title')}</h1>
        <Link
          to={`/case/${id}/intake`}
          className="min-h-11 rounded border border-slate-400 px-3 py-2 text-sm"
        >
          {t('docs.intake')}
        </Link>
        <Link
          to={`/case/${id}`}
          className="min-h-11 rounded border border-slate-400 px-3 py-2 text-sm"
        >
          {t('docs.back')}
        </Link>
      </div>
      {query.isLoading && <p className="mt-3">{t('common.loading')}</p>}
      <ul className="mt-3 grid gap-2">
        {query.data?.map((d) => (
          <li key={d.template_id} className="rounded border border-slate-300 bg-white p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-auto font-medium">{d.title_ru}</span>
              <span className={`rounded px-2 py-0.5 text-xs font-semibold ${BADGE[d.status]}`}>
                {t(`docs.status.${d.status}`)}
              </span>
            </div>
            {d.generated_at && (
              <p className="mt-1 text-xs text-slate-600">
                {t('docs.generatedAt')}: {formatDateTime(d.generated_at)}
              </p>
            )}
            {d.status !== 'awaiting_template' ? (
              <Link
                to={`/case/${id}/documents/${d.template_id}`}
                className="mt-2 inline-flex min-h-11 items-center rounded bg-teal-700 px-4 text-sm font-medium text-white"
              >
                {d.status === 'not_generated' ? t('docs.generate') : t('docs.title')}
              </Link>
            ) : (
              <p className="mt-2 text-sm text-slate-700">{t('docs.awaiting')}</p>
            )}
          </li>
        ))}
      </ul>
    </main>
  )
}
