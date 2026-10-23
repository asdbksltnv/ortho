import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Order } from '../api/types'
import { OrderRow } from '../components/OrdersPanel'

export function TasksPage() {
  const { t } = useTranslation()
  const tasks = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.get<Order[]>('/tasks'),
    refetchInterval: 15_000,
  })
  return (
    <main className="mx-auto max-w-3xl px-3 py-4">
      <h1 className="text-xl font-bold">{t('tasks.title')}</h1>
      {tasks.isLoading && <p className="mt-3">{t('common.loading')}</p>}
      {tasks.data?.length === 0 && <p className="mt-4 text-slate-700">{t('tasks.empty')}</p>}
      <ul className="mt-3 grid gap-2">
        {tasks.data?.map((o) => (
          <div key={o.id}>
            <OrderRow order={o} showCase />
            <Link to={`/case/${o.case_id}`} className="ml-1 text-xs text-teal-800 underline">
              {t('case.title')}
            </Link>
          </div>
        ))}
      </ul>
    </main>
  )
}
