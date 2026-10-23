import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

export interface Point {
  day: number
  value: number | null
}

const W = 320
const H = 150
const PAD = { top: 12, right: 12, bottom: 26, left: 36 }

/**
 * One measure over post-op days. Single series: no legend box (the title names it), a 2 px line,
 * 8 px markers with a surface ring, recessive grid, hover/focus tooltip, and a table view so the
 * values never depend on reading the plot.
 */
export function TrendChart({
  title,
  unit,
  points,
  integer = false,
}: {
  title: string
  unit: string
  points: Point[]
  integer?: boolean
}) {
  const { t } = useTranslation('intake')
  const id = useId()
  const [active, setActive] = useState<number | null>(null)
  const [table, setTable] = useState(false)
  const data = points.filter((p): p is { day: number; value: number } => p.value !== null)

  if (data.length === 0) {
    return (
      <figure
        className="viz-root rounded border border-slate-300 p-3"
        style={{ background: 'var(--surface-1)' }}
      >
        <figcaption className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          {title}
        </figcaption>
        <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
          {t('postop.noTrend')}
        </p>
      </figure>
    )
  }

  const days = data.map((p) => p.day)
  const values = data.map((p) => p.value)
  const minDay = Math.min(...days)
  const maxDay = Math.max(...days)
  let lo = Math.min(...values)
  let hi = Math.max(...values)
  if (lo === hi) {
    lo -= 1
    hi += 1
  }
  const pad = (hi - lo) * 0.15
  lo -= pad
  hi += pad
  const x = (day: number) =>
    maxDay === minDay
      ? (PAD.left + W - PAD.right) / 2
      : PAD.left + ((day - minDay) / (maxDay - minDay)) * (W - PAD.left - PAD.right)
  const y = (v: number) => PAD.top + (1 - (v - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom)
  const fmt = (v: number) => (integer ? String(Math.round(v)) : v.toFixed(1).replace('.', ','))
  const ticks = [lo + pad, (lo + hi) / 2, hi - pad]
  const path = data.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.day)},${y(p.value)}`).join(' ')
  const current = active === null ? null : data[active]

  return (
    <figure
      className="viz-root rounded border border-slate-300 p-3"
      style={{ background: 'var(--surface-1)' }}
      aria-labelledby={`${id}-t`}
    >
      <div className="flex items-center gap-2">
        <figcaption
          id={`${id}-t`}
          className="mr-auto text-sm font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          {title}
        </figcaption>
        <button
          type="button"
          onClick={() => setTable((v) => !v)}
          className="min-h-11 rounded border border-slate-400 px-3 text-xs"
          style={{ color: 'var(--text-secondary)' }}
        >
          {table ? t('postop.chart') : t('postop.table')}
        </button>
      </div>

      {table ? (
        <table className="mt-2 w-full text-sm" style={{ color: 'var(--text-primary)' }}>
          <thead>
            <tr className="text-left" style={{ color: 'var(--text-secondary)' }}>
              <th className="py-1 pr-2 font-medium">{t('postop.day')}</th>
              <th className="py-1 font-medium">{unit}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={p.day} className="border-t" style={{ borderColor: 'var(--grid)' }}>
                <td className="py-1 pr-2">{p.day}</td>
                <td className="py-1">{fmt(p.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="relative">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={`${title}: ${data.map((p) => `${p.day} — ${fmt(p.value)}`).join('; ')}`}
            className="mt-1 h-auto w-full"
            onPointerLeave={() => setActive(null)}
          >
            {ticks.map((tick) => (
              <g key={tick}>
                <line
                  x1={PAD.left}
                  x2={W - PAD.right}
                  y1={y(tick)}
                  y2={y(tick)}
                  stroke="var(--grid)"
                  strokeWidth="1"
                />
                <text
                  x={PAD.left - 6}
                  y={y(tick) + 4}
                  textAnchor="end"
                  fontSize="10"
                  fill="var(--text-muted)"
                >
                  {fmt(tick)}
                </text>
              </g>
            ))}
            {data.map((p) => (
              <text
                key={p.day}
                x={x(p.day)}
                y={H - 8}
                textAnchor="middle"
                fontSize="10"
                fill="var(--text-muted)"
              >
                {p.day}
              </text>
            ))}
            {current && (
              <line
                x1={x(current.day)}
                x2={x(current.day)}
                y1={PAD.top}
                y2={H - PAD.bottom}
                stroke="var(--text-muted)"
                strokeWidth="1"
                strokeDasharray="3 3"
              />
            )}
            {data.length > 1 && (
              <path
                d={path}
                fill="none"
                stroke="var(--series-1)"
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            )}
            {data.map((p, i) => (
              <g key={p.day}>
                {/* generous invisible hit target, larger than the 8 px marker */}
                <circle
                  cx={x(p.day)}
                  cy={y(p.value)}
                  r="14"
                  fill="transparent"
                  tabIndex={0}
                  aria-label={`${t('postop.day')} ${p.day}: ${fmt(p.value)} ${unit}`}
                  onPointerEnter={() => setActive(i)}
                  onFocus={() => setActive(i)}
                  onBlur={() => setActive(null)}
                />
                <circle
                  cx={x(p.day)}
                  cy={y(p.value)}
                  r="4"
                  fill="var(--series-1)"
                  stroke="var(--surface-1)"
                  strokeWidth="2"
                  pointerEvents="none"
                />
              </g>
            ))}
          </svg>
          {current && (
            <div
              role="status"
              className="pointer-events-none absolute right-2 top-1 rounded border px-2 py-1 text-xs shadow"
              style={{
                background: 'var(--surface-1)',
                color: 'var(--text-primary)',
                borderColor: 'var(--grid)',
              }}
            >
              {t('postop.day')} {current.day}: <strong>{fmt(current.value)}</strong> {unit}
            </div>
          )}
        </div>
      )}
    </figure>
  )
}
