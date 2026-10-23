import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import config from '../test/intakeConfig.json'
import { mockApi } from '../test/utils'
import { getDraft } from './drafts'
import { emptyIntake } from './types'
import { SYNC_INTERVAL_MS, useIntakeSync } from './useIntakeSync'

it('syncs every 15 seconds in production', () => {
  expect(SYNC_INTERVAL_MS).toBe(15_000)
})

const caseDetail = {
  id: 'c1',
  patient: { birth_date: '1960-05-17' },
  procedure_key: 'tka',
  procedure_label: 'ТЭП коленного сустава',
  side: 'left',
}
const intake = (updatedAt: string, pain: number | null = null) => {
  const data = emptyIntake()
  data.complaints.pain_vas = pain
  return {
    data,
    schema_version: 1,
    updated_at: updatedAt,
    completed_at: null,
    is_new: false,
    can_edit: true,
  }
}

type PutBody = {
  request_id: string
  base_updated_at: string | null
  data: ReturnType<typeof emptyIntake>
}

function setup(extra: Record<string, unknown> = {}) {
  const id = `c-${Math.random().toString(36).slice(2)}`
  return { id, handlers: { 'GET /cases/X': caseDetail, 'GET /config/intake': config, ...extra } }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

// The production interval is 15 s (SYNC_INTERVAL_MS); tests use a short one.
const FAST = 250

function install(id: string, handlers: Record<string, unknown>) {
  const mapped: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(handlers))
    mapped[key.replace('/cases/X', `/cases/${id}`)] = value
  return mockApi(mapped)
}

describe('useIntakeSync', () => {
  it('loads the server copy and reports it as saved', async () => {
    const { id, handlers } = setup({
      'GET /cases/X/intake': intake('2026-03-10T08:00:00+00:00', 3),
    })
    install(id, handlers)
    const { result } = renderHook(() => useIntakeSync(id, FAST))
    await waitFor(() => expect(result.current.status).toBe('saved'))
    expect(result.current.data?.complaints.pain_vas).toBe(3)
    expect(result.current.snapshot?.procedure_label).toBe('ТЭП коленного сустава')
  })

  it('writes every change to IndexedDB at once and pushes to the server every 15 s', async () => {
    const puts: PutBody[] = []
    const { id, handlers } = setup({
      'GET /cases/X/intake': intake('2026-03-10T08:00:00+00:00'),
      'PUT /cases/X/intake': ({ body }: { body: PutBody }) => {
        puts.push(body)
        return { body: intake('2026-03-10T08:01:00+00:00', 5) }
      },
    })
    install(id, handlers)
    const { result } = renderHook(() => useIntakeSync(id, FAST))
    await waitFor(() => expect(result.current.status).toBe('saved'))

    act(() =>
      result.current.setData((d) => ({ ...d, complaints: { ...d.complaints, pain_vas: 5 } })),
    )
    expect(result.current.status).toBe('dirty')
    await waitFor(async () => expect((await getDraft(id))?.dirty).toBe(true))
    expect((await getDraft(id))?.data.complaints.pain_vas).toBe(5)
    expect(puts).toHaveLength(0) // nothing sent before the interval fires

    await waitFor(() => expect(result.current.status).toBe('saved'))
    expect(puts).toHaveLength(1)
    expect(puts[0].base_updated_at).toBe('2026-03-10T08:00:00+00:00')
    expect(puts[0].request_id).toMatch(/^[0-9a-f-]{36}$/)
    expect((await getDraft(id))?.dirty).toBe(false)
  })

  it('queues changes while offline and syncs them when the connection returns', async () => {
    const puts: PutBody[] = []
    let online = false
    const { id, handlers } = setup({
      'GET /cases/X/intake': intake('2026-03-10T08:00:00+00:00'),
      'PUT /cases/X/intake': ({ body }: { body: PutBody }) => {
        if (!online) return { networkError: true }
        puts.push(body)
        return { body: intake('2026-03-10T08:05:00+00:00', 7) }
      },
    })
    install(id, handlers)
    const { result } = renderHook(() => useIntakeSync(id, FAST))
    await waitFor(() => expect(result.current.status).toBe('saved'))

    act(() =>
      result.current.setData((d) => ({ ...d, complaints: { ...d.complaints, pain_vas: 7 } })),
    )
    await waitFor(() => expect(result.current.status).toBe('offline'))
    expect((await getDraft(id))?.dirty).toBe(true) // still queued on the device

    online = true
    await act(async () => {
      window.dispatchEvent(new Event('online'))
    })
    await waitFor(() => expect(result.current.status).toBe('saved'))
    expect(puts).toHaveLength(1)
    expect(puts[0].data.complaints.pain_vas).toBe(7)
  })

  it('retries a lost response with the same request id, and a new id after a further edit', async () => {
    const ids: string[] = []
    let calls = 0
    const { id, handlers } = setup({
      'GET /cases/X/intake': intake('2026-03-10T08:00:00+00:00'),
      'PUT /cases/X/intake': ({ body }: { body: PutBody }) => {
        ids.push(body.request_id)
        calls += 1
        return calls <= 2 ? { networkError: true } : { body: intake('2026-03-10T08:05:00+00:00') }
      },
    })
    install(id, handlers)
    const { result } = renderHook(() => useIntakeSync(id, FAST))
    await waitFor(() => expect(result.current.status).toBe('saved'))

    act(() =>
      result.current.setData((d) => ({ ...d, complaints: { ...d.complaints, pain_vas: 2 } })),
    )
    await act(async () => void (await result.current.syncNow()))
    await act(async () => void (await result.current.syncNow()))
    expect(ids[0]).toBe(ids[1]) // same payload -> same id, so the server applies it once

    act(() =>
      result.current.setData((d) => ({ ...d, complaints: { ...d.complaints, pain_vas: 3 } })),
    )
    await act(async () => void (await result.current.syncNow()))
    expect(ids[2]).not.toBe(ids[1]) // new payload -> new id
    await waitFor(() => expect(result.current.status).toBe('saved'))
  })

  it('detects a version conflict and lets the user keep theirs', async () => {
    const puts: PutBody[] = []
    const { id, handlers } = setup({
      'GET /cases/X/intake': intake('2026-03-10T08:00:00+00:00'),
      'PUT /cases/X/intake': ({ body }: { body: PutBody }) => {
        puts.push(body)
        return puts.length === 1
          ? {
              status: 409,
              body: {
                code: 'conflict',
                message: 'x',
                details: { current_updated_at: '2026-03-10T09:00:00+00:00' },
              },
            }
          : { body: intake('2026-03-10T09:05:00+00:00', 9) }
      },
    })
    install(id, handlers)
    const { result } = renderHook(() => useIntakeSync(id, FAST))
    await waitFor(() => expect(result.current.status).toBe('saved'))
    act(() =>
      result.current.setData((d) => ({ ...d, complaints: { ...d.complaints, pain_vas: 9 } })),
    )
    await act(async () => void (await result.current.syncNow()))
    expect(result.current.status).toBe('conflict')
    await act(async () => void (await result.current.keepMine()))
    await waitFor(() => expect(result.current.status).toBe('saved'))
    expect(puts[1].base_updated_at).toBe('2026-03-10T09:00:00+00:00')
  })

  it('lets the user take the other version on conflict', async () => {
    let gets = 0
    const { id, handlers } = setup({
      'GET /cases/X/intake': () => ({
        body:
          gets++ === 0
            ? intake('2026-03-10T08:00:00+00:00')
            : intake('2026-03-10T09:00:00+00:00', 1),
      }),
      'PUT /cases/X/intake': () => ({
        status: 409,
        body: {
          code: 'conflict',
          message: 'x',
          details: { current_updated_at: '2026-03-10T09:00:00+00:00' },
        },
      }),
    })
    install(id, handlers)
    const { result } = renderHook(() => useIntakeSync(id, FAST))
    await waitFor(() => expect(result.current.status).toBe('saved'))
    act(() =>
      result.current.setData((d) => ({ ...d, complaints: { ...d.complaints, pain_vas: 9 } })),
    )
    await act(async () => void (await result.current.syncNow()))
    await act(async () => void (await result.current.takeTheirs()))
    expect(result.current.status).toBe('saved')
    expect(result.current.data?.complaints.pain_vas).toBe(1)
  })

  it('opens from the device when offline and keeps unsynced work', async () => {
    const { id, handlers } = setup({ 'GET /cases/X/intake': intake('2026-03-10T08:00:00+00:00') })
    install(id, handlers)
    const first = renderHook(() => useIntakeSync(id, FAST))
    await waitFor(() => expect(first.result.current.status).toBe('saved'))
    act(() =>
      first.result.current.setData((d) => ({ ...d, complaints: { ...d.complaints, pain_vas: 4 } })),
    )
    await waitFor(async () => expect((await getDraft(id))?.dirty).toBe(true))
    first.unmount()

    mockApi({}) // every request now fails: the device is offline
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const second = renderHook(() => useIntakeSync(id, FAST))
    await waitFor(() => expect(second.result.current.status).toBe('offline'))
    expect(second.result.current.data?.complaints.pain_vas).toBe(4)
    expect(second.result.current.snapshot?.procedure_key).toBe('tka') // cached for offline use
    expect(second.result.current.config?.caprini.factors.length).toBe(37)
  })

  it('stores no name, record number or contact data in the draft', async () => {
    const { id, handlers } = setup({ 'GET /cases/X/intake': intake('2026-03-10T08:00:00+00:00') })
    install(id, handlers)
    const { result } = renderHook(() => useIntakeSync(id, FAST))
    await waitFor(() => expect(result.current.status).toBe('saved'))
    act(() =>
      result.current.setData((d) => ({ ...d, complaints: { ...d.complaints, pain_vas: 1 } })),
    )
    await waitFor(async () => expect((await getDraft(id))?.dirty).toBe(true))
    const stored = JSON.stringify(await getDraft(id))
    expect(stored).not.toMatch(/full_name|medical_record|1960-05-17/)
  })
})
