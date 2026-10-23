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
      className="bg-amber-300 px-3 py-1 text-center text-xs font-semibold text-black md:py-2 md:text-sm"
    >
      {t('demo.banner')}
    </div>
  )
}
