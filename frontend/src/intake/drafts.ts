import { openDB, type DBSchema, type IDBPDatabase } from 'idb'
import type { IntakeConfig, IntakeData } from './types'

/** Offline store. Drafts hold clinical answers only: no name, record number or contact data. */
export interface Draft {
  caseId: string
  data: IntakeData
  baseUpdatedAt: string | null // server version this draft was based on
  dirty: boolean
  version: number // bumped on every local change
  request: { version: number; id: string } | null // id of the in-flight / retryable save
  completed: boolean
  savedAt: number
}

export interface CaseSnapshot {
  caseId: string
  birth_date: string
  procedure_key: string
  procedure_label: string
  side: string | null
  can_edit: boolean
}

interface Schema extends DBSchema {
  drafts: { key: string; value: Draft }
  cases: { key: string; value: CaseSnapshot }
  config: { key: string; value: { key: string; value: unknown } }
}

let dbPromise: Promise<IDBPDatabase<Schema>> | null = null

function db(): Promise<IDBPDatabase<Schema>> {
  dbPromise ??= openDB<Schema>('orthoready', 1, {
    upgrade(database) {
      database.createObjectStore('drafts', { keyPath: 'caseId' })
      database.createObjectStore('cases', { keyPath: 'caseId' })
      database.createObjectStore('config', { keyPath: 'key' })
    },
  })
  return dbPromise
}

async function safe<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await fn()
  } catch {
    return fallback // IndexedDB can be unavailable (private mode); the app still works online
  }
}

export const getDraft = (caseId: string) =>
  safe(async () => (await db()).get('drafts', caseId), undefined)
export const putDraft = (draft: Draft) =>
  safe(async () => void (await (await db()).put('drafts', draft)), undefined)
export const deleteDraft = (caseId: string) =>
  safe(async () => (await db()).delete('drafts', caseId), undefined)
export const dirtyDrafts = () =>
  safe(async () => (await (await db()).getAll('drafts')).filter((d) => d.dirty), [] as Draft[])

export const getCaseSnapshot = (caseId: string) =>
  safe(async () => (await db()).get('cases', caseId), undefined)
export const putCaseSnapshot = (snapshot: CaseSnapshot) =>
  safe(async () => void (await (await db()).put('cases', snapshot)), undefined)

export const getCachedConfig = () =>
  safe(
    async () => (await (await db()).get('config', 'intake'))?.value as IntakeConfig | undefined,
    undefined,
  )
export const putCachedConfig = (config: IntakeConfig) =>
  safe(
    async () => void (await (await db()).put('config', { key: 'intake', value: config })),
    undefined,
  )

/** Called on logout: drops identifying snapshots. Unsynced drafts are kept so no work is lost. */
export const clearSnapshots = () =>
  safe(async () => {
    const database = await db()
    await database.clear('cases')
    await database.clear('config')
  }, undefined)
