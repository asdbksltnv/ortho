import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '../api/client'
import type { ConfigFile } from '../api/types'

export function ConfigWarning() {
  const { t } = useTranslation()
  const { data } = useQuery({
    queryKey: ['config-status'],
    queryFn: () => api.get<ConfigFile[]>('/admin/config-status'),
  })
  const pending = data?.filter((f) => f.requires_clinical_validation) ?? []
  if (pending.length === 0) return null
  return (
    <div
      role="status"
      className="rounded border border-amber-600 bg-amber-50 p-3 text-sm text-amber-900"
    >
      <p className="font-semibold">{t('admin.configWarning')}</p>
      <p className="mt-1 break-words">{pending.map((f) => f.name).join(', ')}</p>
    </div>
  )
}
