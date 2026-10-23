import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { fetchMeta } from '../api/client'

export function DemoBanner() {
  const { t } = useTranslation()
  const { data } = useQuery({ queryKey: ['meta'], queryFn: fetchMeta, staleTime: Infinity })

  if (!data?.demo_mode) return null
  return (
    <div
      role="alert"
      className="bg-amber-300 px-4 py-2 text-center text-sm font-semibold text-black"
    >
      {t('demo.banner')}
    </div>
  )
}
