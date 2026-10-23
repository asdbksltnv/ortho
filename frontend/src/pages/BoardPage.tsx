import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Board, BoardRow, Ward } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ChecklistEditor } from '../components/ChecklistEditor'
import { FloorPlan } from '../components/FloorPlan'
import { StatusIcon } from '../components/StatusIcon'
import { formatDate, formatDateTime } from '../lib/format'
import { canEditItem } from '../lib/permissions'

const POLL_MS = 5000 // other users' changes appear within the 10 s target
const VIEW_KEY = 'orthoready:board-view'

function savedView(): 'table' | 'plan' {
  try {
    return window.localStorage.getItem(VIEW_KEY) === 'plan' ? 'plan' : 'table'
  } catch {
    return 'table'
  }
}

export function BoardPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [mine, setMine] = useState(false)
  const [tomorrow, setTomorrow] = useState(false)
  const [notReady, setNotReady] = useState(false)
  const [doctorId, setDoctorId] = useState('')
  const [editing, setEditing] = useState<{ row: BoardRow; key: string } | null>(null)
  const [view, setViewState] = useState<'table' | 'plan'>(savedView)
  const setView = (v: 'table' | 'plan') => {
    setViewState(v)
    try {
      window.localStorage.setItem(VIEW_KEY, v)
    } catch {
      // remembering the view is a convenience only
    }
  }
  const wards = useQuery({
    queryKey: ['wards'],
    queryFn: () => api.get<Ward[]>('/wards'),
    enabled: view === 'plan',
    staleTime: 60_000,
  })

  const query = useQuery({
    queryKey: ['board', { mine, tomorrow, notReady, doctorId }],
    queryFn: () => {
      const p = new URLSearchParams()
      if (mine) p.set('mine', 'true')
      if (tomorrow) p.set('surgery_tomorrow', 'true')
      if (notReady) p.set('not_ready', 'true')
      if (doctorId) p.set('doctor_id', doctorId)
      return api.get<Board>(`/board?${p.toString()}`)
    },
    refetchInterval: POLL_MS,
    placeholderData: (prev) => prev,
  })

  const doctors = useMemo(() => {
    const seen = new Map<string, string>()
    query.data?.rows.forEach((r) => seen.set(r.treating_doctor_id, r.treating_doctor_name))
    return [...seen.entries()]
  }, [query.data])

  if (!user) return null
  const board = query.data
  const columns = board?.columns ?? []

  return (
    <main className="mx-auto max-w-[1600px] px-3 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto text-xl font-bold">{t('board.title')}</h1>
        <Toggle label={t('board.mine')} checked={mine} onChange={setMine} />
        <Toggle label={t('board.tomorrow')} checked={tomorrow} onChange={setTomorrow} />
        <Toggle label={t('board.notReady')} checked={notReady} onChange={setNotReady} />
        <select
          aria-label={t('board.doctor')}
          value={doctorId}
          onChange={(e) => setDoctorId(e.target.value)}
          className="min-h-11 rounded border border-slate-400 bg-white px-2"
        >
          <option value="">{t('board.allDoctors')}</option>
          {doctors.map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
      </div>

      {query.isError && !board && <p className="mt-4 text-red-700">{t('common.error')}</p>}
      {query.isLoading && <p className="mt-4">{t('common.loading')}</p>}
      {board && board.rows.length === 0 && (
        <p className="mt-6 text-slate-700">{t('board.empty')}</p>
      )}

      <div role="radiogroup" aria-label={t('board.viewTable')} className="mt-3 flex gap-2">
        {(['table', 'plan'] as const).map((v) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={view === v}
            onClick={() => setView(v)}
            className={`min-h-11 rounded border px-4 text-sm ${
              view === v
                ? 'border-teal-800 bg-teal-700 font-semibold text-white'
                : 'border-slate-400 bg-white'
            }`}
          >
            {v === 'table' ? t('board.viewTable') : t('board.viewPlan')}
          </button>
        ))}
      </div>

      {view === 'plan' && board && wards.data && <FloorPlan wards={wards.data} rows={board.rows} />}

      {view === 'table' && board && board.rows.length > 0 && (
        <div className="mt-3 overflow-x-auto rounded border border-slate-300 bg-white">
          <table className="w-full min-w-[900px] border-collapse text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th scope="col" className="sticky left-0 z-10 bg-slate-100 px-3 py-2">
                  {t('board.patient')}
                </th>
                <th scope="col" className="px-2 py-2">
                  {t('board.surgery')}
                </th>
                {columns.map((c) => (
                  <th
                    key={c.key}
                    scope="col"
                    title={c.label_ru}
                    className="px-1 py-2 text-center text-xs font-semibold"
                  >
                    {c.short_label_ru}
                  </th>
                ))}
                <th scope="col" className="px-2 py-2 text-center">
                  {t('board.ready')}
                </th>
              </tr>
            </thead>
            <tbody>
              {board.rows.map((row, i) => {
                const newRoom = i === 0 || board.rows[i - 1].room_name !== row.room_name
                return (
                  <RowGroup
                    key={row.case_id}
                    showRoom={newRoom}
                    row={row}
                    colSpan={columns.length + 3}
                  >
                    <tr className="border-t border-slate-200 odd:bg-white even:bg-slate-50/60">
                      <th
                        scope="row"
                        className="sticky left-0 z-10 bg-inherit px-3 py-2 text-left font-normal"
                      >
                        <Link
                          to={`/case/${row.case_id}`}
                          className="font-semibold text-teal-800 underline"
                        >
                          {row.initials}
                        </Link>
                        <span className="ml-2 text-slate-700">
                          {row.bed_label ?? t('board.noRoom')}
                        </span>
                        {row.is_emergency && (
                          <span className="ml-2 rounded bg-red-700 px-1.5 py-0.5 text-xs font-semibold text-white">
                            {t('board.emergency')}
                          </span>
                        )}
                        <div className="text-xs text-slate-600">
                          {t(`caseStatus.${row.status}`)} · {row.treating_doctor_name}
                        </div>
                      </th>
                      <td className="px-2 py-2 align-top text-xs">
                        <div>{row.procedure_label}</div>
                        <div className="text-slate-600">{formatDate(row.planned_surgery_date)}</div>
                      </td>
                      {columns.map((c) => {
                        const item = row.items[c.key]
                        return (
                          <td key={c.key} className="px-1 py-1 text-center">
                            <button
                              type="button"
                              onClick={() => setEditing({ row, key: c.key })}
                              aria-label={`${c.label_ru}: ${t(`itemStatus.${item.status}`)}`}
                              title={`${c.label_ru}: ${t(`itemStatus.${item.status}`)}${
                                item.note ? ` — ${item.note}` : ''
                              }${
                                item.updated_by
                                  ? ` (${item.updated_by}, ${formatDateTime(item.updated_at)})`
                                  : ''
                              }`}
                              className="inline-flex h-11 w-11 items-center justify-center rounded hover:bg-slate-100"
                            >
                              <StatusIcon status={item.status} />
                            </button>
                          </td>
                        )
                      })}
                      <td className="px-2 py-2 text-center">
                        {row.ready ? (
                          <span className="font-semibold text-green-800">✔ {t('board.ready')}</span>
                        ) : (
                          <span
                            className="text-xs text-red-800"
                            title={`${t('board.missing')}: ${row.blocking
                              .map((k) => columns.find((c) => c.key === k)?.short_label_ru ?? k)
                              .join(', ')}`}
                          >
                            ✖ {t('board.notReadyBadge')} ({row.blocking.length})
                          </span>
                        )}
                        {row.override_reason && (
                          <div className="text-xs text-amber-800">{row.override_reason}</div>
                        )}
                      </td>
                    </tr>
                  </RowGroup>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {board && (
        <p className="mt-2 text-xs text-slate-600">
          {t('board.updated')}: {formatDateTime(board.generated_at)}
        </p>
      )}

      {editing && (
        <ChecklistEditor
          key={`${editing.row.case_id}-${editing.key}-${editing.row.items[editing.key].updated_at}`}
          caseId={editing.row.case_id}
          itemKey={editing.key}
          label={columns.find((c) => c.key === editing.key)?.label_ru ?? editing.key}
          status={editing.row.items[editing.key].status}
          note={editing.row.items[editing.key].note}
          updatedAt={editing.row.items[editing.key].updated_at}
          updatedBy={editing.row.items[editing.key].updated_by}
          canEdit={canEditItem(
            user.role,
            editing.key,
            columns.find((c) => c.key === editing.key)?.owner_role ?? 'doctor',
            editing.row.treating_doctor_id === user.id,
          )}
          onClose={() => setEditing(null)}
        />
      )}
    </main>
  )
}

function RowGroup({
  showRoom,
  row,
  colSpan,
  children,
}: {
  showRoom: boolean
  row: BoardRow
  colSpan: number
  children: React.ReactNode
}) {
  const { t } = useTranslation()
  return (
    <>
      {showRoom && (
        <tr className="bg-teal-50">
          <th
            colSpan={colSpan}
            scope="colgroup"
            className="px-3 py-1 text-left text-xs font-bold text-teal-900"
          >
            {row.room_name ?? t('board.noRoom')}
          </th>
        </tr>
      )}
      {children}
    </>
  )
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <label
      className={`flex min-h-11 cursor-pointer items-center gap-2 rounded border px-3 text-sm ${
        checked ? 'border-teal-700 bg-teal-50 font-semibold' : 'border-slate-400 bg-white'
      }`}
    >
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  )
}
