import { useQuery } from '@tanstack/react-query'
import QRCode from 'qrcode'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { BoardRow } from '../api/types'
import { formatDate } from '../lib/format'

/** Draws the QR modules as an SVG path (no HTML injection, no external image). */
export function QrCode({ value, size = 160 }: { value: string; size?: number }) {
  const { path, count } = useMemo(() => {
    const qr = QRCode.create(value, { errorCorrectionLevel: 'M' })
    const n = qr.modules.size
    let d = ''
    for (let y = 0; y < n; y++)
      for (let x = 0; x < n; x++) if (qr.modules.get(x, y)) d += `M${x + 4},${y + 4}h1v1h-1z`
    return { path: d, count: n + 8 }
  }, [value])
  return (
    <svg
      role="img"
      aria-label="QR"
      width={size}
      height={size}
      viewBox={`0 0 ${count} ${count}`}
      shapeRendering="crispEdges"
    >
      <rect width={count} height={count} fill="#fff" />
      <path d={path} fill="#000" />
    </svg>
  )
}

/** Printable case label: initials, room and bed, procedure; QR to /case/<uuid>. No name, no record number. */
export function LabelPage() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const board = useQuery({
    queryKey: ['board', 'label'],
    queryFn: () => api.get<{ rows: BoardRow[] }>('/board'),
  })
  const row = board.data?.rows.find((r) => r.case_id === id)
  const url = `${window.location.origin}/case/${id}`

  return (
    <main className="mx-auto max-w-md px-3 py-4">
      <div className="print:hidden">
        <h1 className="text-xl font-bold">{t('label.title')}</h1>
        <p className="mt-1 text-sm text-slate-700">{t('label.hint')}</p>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => window.print()}
            className="min-h-11 rounded bg-teal-700 px-5 font-medium text-white"
          >
            {t('label.print')}
          </button>
          <Link
            to={`/case/${id}`}
            className="inline-flex min-h-11 items-center rounded border border-slate-400 px-4 text-sm"
          >
            {t('case.title')}
          </Link>
        </div>
        <p className="mt-2 text-xs text-slate-600">{t('label.noNames')}</p>
      </div>

      <section
        aria-label={t('label.title')}
        data-testid="label"
        className="mt-4 flex items-center gap-4 rounded border-2 border-black bg-white p-4 text-black print:mt-0 print:border"
      >
        <QrCode value={url} />
        <div>
          {row ? (
            <>
              <p className="text-2xl font-bold">{row.initials}</p>
              <p className="text-lg">
                {row.room_name ?? '—'}, {row.bed_label ?? '—'}
              </p>
              <p className="text-sm">{row.procedure_label}</p>
              {row.planned_surgery_date && (
                <p className="text-sm">{formatDate(row.planned_surgery_date)}</p>
              )}
            </>
          ) : (
            <p className="text-sm">{board.isLoading ? t('common.loading') : '—'}</p>
          )}
        </div>
      </section>
    </main>
  )
}
