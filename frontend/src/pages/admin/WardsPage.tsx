import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api/client'
import type { Ward } from '../../api/types'

export function WardsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const wards = useQuery({ queryKey: ['wards'], queryFn: () => api.get<Ward[]>('/wards') })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['wards'] })
  const [roomName, setRoomName] = useState('')
  const [floor, setFloor] = useState('1')
  const [bedLabels, setBedLabels] = useState<Record<string, string>>({})

  const addRoom = useMutation({
    mutationFn: (v: { ward_id: string; name: string; floor: number }) =>
      api.post('/wards/rooms', v),
    onSuccess: () => {
      setRoomName('')
      void refresh()
    },
  })
  const addBed = useMutation({
    mutationFn: (v: { room_id: string; label: string }) => api.post('/wards/beds', v),
    onSuccess: () => void refresh(),
  })
  const toggleBed = useMutation({
    mutationFn: (v: { id: string; is_active: boolean }) =>
      api.patch(`/wards/beds/${v.id}`, { is_active: v.is_active }),
    onSuccess: () => void refresh(),
  })

  const input = 'min-h-11 rounded border border-slate-400 bg-white px-3'
  return (
    <main className="mx-auto max-w-4xl px-3 py-4">
      <h1 className="text-xl font-bold">{t('admin.wards')}</h1>
      {wards.data?.map((ward) => (
        <section key={ward.id} className="mt-4 rounded border border-slate-300 bg-white p-3">
          <h2 className="font-semibold">{ward.name}</h2>
          <form
            className="mt-2 flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              if (roomName.trim())
                addRoom.mutate({
                  ward_id: ward.id,
                  name: roomName.trim(),
                  floor: Number(floor) || 1,
                })
            }}
          >
            <input
              value={roomName}
              onChange={(e) => setRoomName(e.target.value)}
              placeholder={t('admin.roomName')}
              className={input}
            />
            <input
              value={floor}
              onChange={(e) => setFloor(e.target.value)}
              inputMode="numeric"
              aria-label={t('admin.floor')}
              className={`${input} w-20`}
            />
            <button type="submit" className="min-h-11 rounded bg-teal-700 px-3 text-white">
              {t('admin.addRoom')}
            </button>
          </form>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {ward.rooms.map((room) => (
              <li key={room.id} className="rounded border border-slate-200 p-2">
                <div className="font-medium">
                  {room.name}{' '}
                  <span className="text-xs text-slate-600">
                    ({t('admin.floor')} {room.floor})
                  </span>
                </div>
                <ul className="mt-1 flex flex-wrap gap-1">
                  {room.beds.map((bed) => (
                    <li key={bed.id}>
                      <button
                        type="button"
                        onClick={() => toggleBed.mutate({ id: bed.id, is_active: !bed.is_active })}
                        className={`min-h-11 rounded border px-3 text-sm ${
                          bed.is_active
                            ? 'border-teal-700'
                            : 'border-slate-300 text-slate-500 line-through'
                        }`}
                      >
                        {bed.label}
                      </button>
                    </li>
                  ))}
                </ul>
                <form
                  className="mt-2 flex gap-2"
                  onSubmit={(e) => {
                    e.preventDefault()
                    const label = (bedLabels[room.id] ?? '').trim()
                    if (label) {
                      addBed.mutate({ room_id: room.id, label })
                      setBedLabels({ ...bedLabels, [room.id]: '' })
                    }
                  }}
                >
                  <input
                    value={bedLabels[room.id] ?? ''}
                    onChange={(e) => setBedLabels({ ...bedLabels, [room.id]: e.target.value })}
                    placeholder={t('admin.bedLabel')}
                    className={`${input} min-w-0 flex-1`}
                  />
                  <button
                    type="submit"
                    className="min-h-11 rounded border border-slate-400 px-3 text-sm"
                  >
                    {t('admin.addBed')}
                  </button>
                </form>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </main>
  )
}
