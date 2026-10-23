import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { CaseDetail } from '../api/types'
import {
  getCachedConfig,
  getCaseSnapshot,
  getDraft,
  putCachedConfig,
  putCaseSnapshot,
  putDraft,
  type CaseSnapshot,
  type Draft,
} from './drafts'
import { emptyIntake, type IntakeConfig, type IntakeData, type IntakeResponse } from './types'

export type SyncState = 'loading' | 'saved' | 'dirty' | 'saving' | 'offline' | 'conflict' | 'error'

export const SYNC_INTERVAL_MS = 15_000

export interface IntakeMeta {
  updatedAt: string | null
  completedAt: string | null
  canEdit: boolean
}

function newId(): string {
  return crypto.randomUUID()
}

const isNetworkError = (e: unknown) => e instanceof TypeError

/**
 * Local-first intake state: every change is written to IndexedDB at once and pushed to the server
 * every 15 s while online (and immediately on reconnect). Each save carries a client-generated
 * request id, so a retry after a dropped response is applied at most once.
 */
export function useIntakeSync(caseId: string, intervalMs: number = SYNC_INTERVAL_MS) {
  const [data, setDataState] = useState<IntakeData | null>(null)
  const [meta, setMeta] = useState<IntakeMeta>({
    updatedAt: null,
    completedAt: null,
    canEdit: true,
  })
  const [status, setStatus] = useState<SyncState>('loading')
  const [config, setConfig] = useState<IntakeConfig | null>(null)
  const [snapshot, setSnapshot] = useState<CaseSnapshot | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [conflictAt, setConflictAt] = useState<string | null>(null)
  const draft = useRef<Draft | null>(null)
  const inFlight = useRef(false)

  const persist = useCallback((next: Draft) => {
    draft.current = next
    void putDraft(next)
  }, [])

  const load = useCallback(async () => {
    const [localDraft, localCase, localConfig] = await Promise.all([
      getDraft(caseId),
      getCaseSnapshot(caseId),
      getCachedConfig(),
    ])
    let server: IntakeResponse | null = null
    let online = true
    try {
      const [caseDetail, cfg, intake] = await Promise.all([
        api.get<CaseDetail>(`/cases/${caseId}`),
        api.get<IntakeConfig>('/config/intake'),
        api.get<IntakeResponse>(`/cases/${caseId}/intake`),
      ])
      const snap: CaseSnapshot = {
        caseId,
        birth_date: caseDetail.patient.birth_date,
        procedure_key: caseDetail.procedure_key,
        procedure_label: caseDetail.procedure_label,
        side: caseDetail.side,
        can_edit: intake.can_edit,
      }
      void putCaseSnapshot(snap)
      void putCachedConfig(cfg)
      setSnapshot(snap)
      setConfig(cfg)
      server = intake
    } catch (e) {
      if (!isNetworkError(e)) {
        setMessage(e instanceof ApiError ? e.message : null)
        setStatus('error')
        return
      }
      online = false
      setSnapshot(localCase ?? null)
      setConfig(localConfig ?? null)
    }

    if (localDraft?.dirty) {
      draft.current = localDraft
      setDataState(localDraft.data)
      setMeta({
        updatedAt: server?.updated_at ?? localDraft.baseUpdatedAt,
        completedAt: server?.completed_at ?? null,
        canEdit: server?.can_edit ?? localCase?.can_edit ?? true,
      })
      setStatus(online ? 'dirty' : 'offline')
      return
    }
    if (server) {
      const fresh: Draft = {
        caseId,
        data: server.data,
        baseUpdatedAt: server.updated_at,
        dirty: false,
        version: 0,
        request: null,
        completed: false,
        savedAt: Date.now(),
      }
      persist(fresh)
      setDataState(server.data)
      setMeta({
        updatedAt: server.updated_at,
        completedAt: server.completed_at,
        canEdit: server.can_edit,
      })
      setStatus('saved')
      return
    }
    // Offline with nothing saved for this case.
    if (localDraft) {
      draft.current = localDraft
      setDataState(localDraft.data)
      setStatus('offline')
    } else {
      setDataState(emptyIntake())
      setStatus('offline')
    }
  }, [caseId, persist])

  useEffect(() => {
    // Initial load from IndexedDB and the server: state is set after the awaited fetches.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load()
  }, [load])

  const setData = useCallback(
    (update: (current: IntakeData) => IntakeData) => {
      setDataState((current) => {
        if (!current) return current
        const next = update(current)
        const base = draft.current
        persist({
          caseId,
          data: next,
          baseUpdatedAt: base?.baseUpdatedAt ?? null,
          dirty: true,
          version: (base?.version ?? 0) + 1,
          request: base?.request ?? null,
          completed: base?.completed ?? false,
          savedAt: Date.now(),
        })
        setStatus((s) =>
          s === 'saving' || s === 'conflict' ? s : navigator.onLine ? 'dirty' : 'offline',
        )
        return next
      })
    },
    [caseId, persist],
  )

  const syncNow = useCallback(
    async (completed = false) => {
      const current = draft.current
      if (!current || inFlight.current || (!current.dirty && !completed)) return
      inFlight.current = true
      const sentVersion = current.version
      const requestId = current.request?.version === sentVersion ? current.request.id : newId()
      persist({ ...current, request: { version: sentVersion, id: requestId } })
      setStatus('saving')
      try {
        const response = await api.put<IntakeResponse>(`/cases/${caseId}/intake`, {
          data: current.data,
          request_id: requestId,
          base_updated_at: current.baseUpdatedAt,
          completed,
        })
        const latest = draft.current ?? current
        const stillDirty = latest.version !== sentVersion
        persist({
          ...latest,
          baseUpdatedAt: response.updated_at,
          dirty: stillDirty,
          request: stillDirty ? null : latest.request,
          completed: false,
        })
        setMeta({
          updatedAt: response.updated_at,
          completedAt: response.completed_at,
          canEdit: response.can_edit,
        })
        setMessage(null)
        setStatus(stillDirty ? 'dirty' : 'saved')
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) {
          setConflictAt(String(e.details.current_updated_at ?? ''))
          setStatus('conflict')
        } else if (isNetworkError(e)) {
          setStatus('offline')
        } else {
          setMessage(e instanceof ApiError ? e.message : null)
          setStatus('error')
        }
      } finally {
        inFlight.current = false
      }
    },
    [caseId, persist],
  )

  // Push every 15 s while online, on reconnect, and when the tab is hidden.
  useEffect(() => {
    const tick = () => {
      if (navigator.onLine && draft.current?.dirty) void syncNow()
    }
    const timer = window.setInterval(tick, intervalMs)
    const onVisibility = () => document.visibilityState === 'hidden' && tick()
    window.addEventListener('online', tick)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('online', tick)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [syncNow, intervalMs])

  const takeTheirs = useCallback(async () => {
    const server = await api.get<IntakeResponse>(`/cases/${caseId}/intake`)
    persist({
      caseId,
      data: server.data,
      baseUpdatedAt: server.updated_at,
      dirty: false,
      version: (draft.current?.version ?? 0) + 1,
      request: null,
      completed: false,
      savedAt: Date.now(),
    })
    setDataState(server.data)
    setMeta({
      updatedAt: server.updated_at,
      completedAt: server.completed_at,
      canEdit: server.can_edit,
    })
    setConflictAt(null)
    setStatus('saved')
  }, [caseId, persist])

  const keepMine = useCallback(async () => {
    const current = draft.current
    if (!current) return
    persist({ ...current, baseUpdatedAt: conflictAt || null })
    setConflictAt(null)
    await syncNow()
  }, [conflictAt, persist, syncNow])

  return {
    data,
    setData,
    meta,
    status,
    config,
    snapshot,
    message,
    syncNow,
    takeTheirs,
    keepMine,
  }
}
