import { useTranslation } from 'react-i18next'
import type { ItemStatus } from '../api/types'

const COLORS: Record<ItemStatus, string> = {
  not_started: '#64748b',
  pending: '#b45309',
  done: '#15803d',
  problem: '#b91c1c',
  not_applicable: '#64748b',
}

/** Shape + colour + text label: status is never conveyed by colour alone. */
export function StatusIcon({ status, size = 28 }: { status: ItemStatus; size?: number }) {
  const { t } = useTranslation()
  const label = t(`itemStatus.${status}`)
  const c = COLORS[status]
  return (
    <svg
      role="img"
      aria-label={label}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={c}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      data-status={status}
    >
      <title>{label}</title>
      {status === 'not_started' && <circle cx="12" cy="12" r="8" />}
      {status === 'pending' && (
        <>
          <circle cx="12" cy="12" r="8" fill="#fef3c7" />
          <path d="M12 7v5l3 2" />
        </>
      )}
      {status === 'done' && (
        <>
          <circle cx="12" cy="12" r="9" fill={c} />
          <path d="M8 12.5l3 3 5-6" stroke="#fff" />
        </>
      )}
      {status === 'problem' && (
        <>
          <path d="M12 3l10 18H2z" fill="#fee2e2" />
          <path d="M12 10v5M12 18v.5" />
        </>
      )}
      {status === 'not_applicable' && <path d="M6 12h12" />}
    </svg>
  )
}
