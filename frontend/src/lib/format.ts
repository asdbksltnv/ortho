const TZ = 'Asia/Tashkent'

/** '2026-03-10' -> '10.03.2026' */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const [y, m, d] = value.slice(0, 10).split('-')
  return `${d}.${m}.${y}`
}

/** ISO instant -> 'ДД.ММ.ГГГГ ЧЧ:ММ' in Asia/Tashkent */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const parts = new Intl.DateTimeFormat('ru-RU', {
    timeZone: TZ,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(value))
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? ''
  return `${get('day')}.${get('month')}.${get('year')} ${get('hour')}:${get('minute')}`
}
