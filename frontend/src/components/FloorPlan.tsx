import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import type { BoardRow, Room, Ward } from '../api/types'

const placed = (r: Room) =>
  r.position_x !== null && r.position_y !== null && !!r.width && !!r.height

/** The ward drawn as on the floor's evacuation plan; patient rooms show who is in each bed. */
export function FloorPlan({ wards, rows }: { wards: Ward[]; rows: BoardRow[] }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const ward = [...wards].sort(
    (a, b) => b.rooms.filter(placed).length - a.rooms.filter(placed).length,
  )[0]
  const rooms = ward?.rooms.filter(placed) ?? []
  if (rooms.length === 0) return <p className="mt-4 text-slate-700">{t('board.noPlan')}</p>

  const byBed = new Map(rows.filter((r) => r.bed_id).map((r) => [r.bed_id as string, r]))
  const width = Math.max(...rooms.map((r) => (r.position_x ?? 0) + (r.width ?? 0))) + 10
  const height = Math.max(...rooms.map((r) => (r.position_y ?? 0) + (r.height ?? 0))) + 10

  return (
    <figure className="mt-3">
      <figcaption className="text-sm text-slate-700">
        {ward.name} · {t('board.planHint')}
      </figcaption>
      <div className="mt-2 overflow-x-auto rounded border border-slate-300 bg-white">
        <svg
          viewBox={`-5 -5 ${width} ${height}`}
          className="h-auto w-full min-w-[760px]"
          role="group"
          aria-label={ward.name}
        >
          {rooms.map((room) => {
            const x = room.position_x ?? 0
            const y = room.position_y ?? 0
            const w = room.width ?? 0
            const h = room.height ?? 0
            const label = room.name.replace(/^Пал\.\s*/, '')
            if (room.kind === 'service' || room.kind === 'exit') {
              const exit = room.kind === 'exit'
              return (
                <g key={room.id} aria-label={room.name} role="img">
                  <rect
                    x={x}
                    y={y}
                    width={w}
                    height={h}
                    rx="3"
                    fill={exit ? '#ecfdf5' : '#f1f5f9'}
                    stroke={exit ? '#15803d' : '#94a3b8'}
                    strokeWidth="1.5"
                    strokeDasharray={exit ? '0' : '4 3'}
                  />
                  <text
                    x={x + w / 2}
                    y={y + h / 2}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize="9"
                    fill={exit ? '#14532d' : '#334155'}
                  >
                    {exit
                      ? `▲ ${t('board.exit')}`
                      : room.name.length > 14
                        ? `${room.name.slice(0, 13)}…`
                        : room.name}
                  </text>
                </g>
              )
            }
            const occupants = room.beds.map((b) => ({ bed: b, row: byBed.get(b.id) }))
            const cases = occupants.filter((o) => o.row)
            const anyNotReady = cases.some((o) => !o.row!.ready)
            const fill = cases.length === 0 ? '#ffffff' : anyNotReady ? '#fef2f2' : '#f0fdf4'
            const stroke = cases.length === 0 ? '#64748b' : anyNotReady ? '#b91c1c' : '#15803d'
            const status = cases
              .map(
                (o) =>
                  `${o.row!.initials}: ${o.row!.ready ? t('board.ready') : `${t('board.notReadyBadge')} (${o.row!.blocking.length})`}`,
              )
              .join('; ')
            const name = `${room.name}: ${status || t('board.free')}`
            const open = () => {
              if (cases.length > 0) navigate(`/case/${cases[0].row!.case_id}`)
            }
            return (
              <g
                key={room.id}
                role={cases.length > 0 ? 'link' : 'img'}
                aria-label={name}
                tabIndex={cases.length > 0 ? 0 : undefined}
                onClick={open}
                onKeyDown={(e) =>
                  (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open())
                }
                className={
                  cases.length > 0
                    ? 'cursor-pointer focus:outline-none [&:focus>rect]:stroke-[3]'
                    : ''
                }
                data-room={room.name}
              >
                <title>{name}</title>
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  rx="4"
                  fill={fill}
                  stroke={stroke}
                  strokeWidth="2"
                />
                <text x={x + 5} y={y + 13} fontSize="11" fontWeight="700" fill="#0f172a">
                  {label}
                </text>
                {occupants.slice(0, 3).map(({ bed, row }, i) => (
                  <text
                    key={bed.id}
                    x={x + 5}
                    y={y + 30 + i * 15}
                    fontSize="10"
                    fill={row ? (row.ready ? '#14532d' : '#7f1d1d') : '#64748b'}
                  >
                    {row
                      ? `${row.ready ? '✔' : '✖'} ${row.initials}${row.is_emergency ? ' !' : ''}`
                      : `○ ${t('board.free')}`}
                  </text>
                ))}
              </g>
            )
          })}
        </svg>
      </div>
      <p className="mt-2 flex flex-wrap gap-4 text-xs text-slate-700">
        <span>✔ {t('board.ready')}</span>
        <span>✖ {t('board.notReadyBadge')}</span>
        <span>○ {t('board.free')}</span>
        <span>! {t('board.emergency')}</span>
      </p>
    </figure>
  )
}
