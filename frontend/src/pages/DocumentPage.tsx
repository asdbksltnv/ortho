import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { DocumentDetail, DocumentField } from '../api/types'
import { copyPayload, copyText } from '../lib/clipboard'

const COPYABLE = (f: DocumentField) => copyPayload(f) !== null && !f.locked

export function DocumentPage() {
  const { id = '', templateId: routeTemplate, entryId } = useParams()
  const templateId = routeTemplate ?? 't6_progress_note'
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const listRef = useRef<HTMLOListElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const key = ['doc', id, templateId, entryId ?? '']
  const base = entryId
    ? `/cases/${id}/postop/${entryId}/document`
    : `/cases/${id}/documents/${templateId}`
  const fieldPath = (field: string) =>
    entryId ? `${base}/fields/${field}/copied` : `${base}/fields/${field}/copied`

  const query = useQuery({ queryKey: key, queryFn: () => api.get<DocumentDetail>(base) })
  const setDoc = (doc: DocumentDetail) => {
    queryClient.setQueryData(key, doc)
    void queryClient.invalidateQueries({ queryKey: ['documents', id] })
  }

  const generate = useMutation({
    mutationFn: () => api.post<DocumentDetail>(`${base}/generate`),
    onSuccess: (doc) => {
      setError(null)
      setDoc(doc)
    },
    onError: (e) => {
      if (e instanceof ApiError && e.code === 'generation_blocked') {
        void queryClient.invalidateQueries({ queryKey: key })
      }
      setError(e instanceof ApiError ? e.message : t('errors.unknown'))
    },
  })

  // "Copied" ticks are sent one at a time, in order: they rewrite one document on the server, and
  // pressing Enter down the list is much faster than a round trip.
  const queue = useRef<Promise<unknown>>(Promise.resolve())
  const pending = useRef(0)
  const mark = {
    mutate: ({ field, copied }: { field: string; copied: boolean }) => {
      queryClient.setQueryData<DocumentDetail>(key, (previous) =>
        previous
          ? {
              ...previous,
              fields: previous.fields.map((f) => (f.key === field ? { ...f, copied } : f)),
            }
          : previous,
      )
      pending.current += 1
      queue.current = queue.current
        .then(() => api.post<DocumentDetail>(fieldPath(field), { copied }))
        .catch(() => undefined)
        .finally(() => {
          pending.current -= 1
          if (pending.current === 0) void queryClient.invalidateQueries({ queryKey: key })
        })
    },
  }

  const copyAll = useMutation({
    mutationFn: () => api.post<DocumentDetail>(`${base}/copy-all`),
    onSuccess: async (doc) => {
      if (await copyText(doc.all_text)) setNotice(t('docs.copyAllDone'))
    },
  })

  if (query.isLoading) return <p className="p-4">{t('common.loading')}</p>
  if (query.isError || !query.data) return <p className="p-4 text-red-700">{t('common.error')}</p>
  const doc = query.data
  const generated = doc.status === 'generated' || doc.status === 'outdated'

  const focusRow = (index: number) =>
    listRef.current?.querySelector<HTMLElement>(`[data-row="${index}"]`)?.focus()

  const copyField = async (field: DocumentField, index: number) => {
    const payload = copyPayload(field)
    // Start the copy inside the key press (clipboard access needs the user gesture), move on at
    // once so quick presses never hit the same row twice, then record the tick.
    const copying = payload === null ? null : copyText(payload)
    focusRow(index + 1)
    if (copying && (await copying)) mark.mutate({ field: field.key, copied: true })
  }

  const copyable = doc.fields.filter(COPYABLE)
  const copiedCount = copyable.filter((f) => f.copied).length

  return (
    <main className="mx-auto max-w-3xl px-3 pb-24 pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto text-xl font-bold">{doc.title_ru}</h1>
        <Link
          to={`/case/${id}/documents`}
          className="min-h-11 rounded border border-slate-400 px-3 py-2 text-sm"
        >
          {t('docs.title')}
        </Link>
      </div>

      {doc.status === 'awaiting_template' && (
        <p className="mt-4 rounded bg-slate-100 p-3">{t('docs.awaiting')}</p>
      )}

      {(!generated || doc.is_outdated) && doc.status !== 'awaiting_template' && (
        <section className="mt-4 rounded border border-slate-300 bg-white p-3" aria-live="polite">
          {doc.is_outdated && (
            <p role="alert" className="mb-2 rounded bg-amber-50 p-2 text-sm text-amber-900">
              {t('docs.outdated')}
            </p>
          )}
          {doc.problems.length > 0 && (
            <div role="alert" className="mb-2 text-sm text-red-800">
              <p className="font-semibold">{t('docs.blocked')}</p>
              <ul className="mt-1 list-disc pl-5">
                {doc.problems.map((p, i) => (
                  <li key={`${p.code}-${p.key ?? i}`}>{p.message}</li>
                ))}
              </ul>
              <Link to={`/case/${id}/intake`} className="mt-2 inline-block underline">
                {t('docs.intake')}
              </Link>
            </div>
          )}
          {error && <p className="mb-2 text-sm text-red-700">{error}</p>}
          <button
            type="button"
            disabled={generate.isPending || !doc.can_generate}
            onClick={() => generate.mutate()}
            className="min-h-11 rounded bg-teal-700 px-4 font-medium text-white disabled:opacity-50"
          >
            {generated ? t('docs.regenerate') : t('docs.generate')}
          </button>
        </section>
      )}

      {generated && (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
            <span>
              {t('docs.progress')}: <strong>{copiedCount}</strong> / {copyable.length}
            </span>
            <button
              type="button"
              onClick={() => copyAll.mutate()}
              className="ml-auto min-h-11 rounded border border-slate-400 px-3"
            >
              {t('docs.copyAll')}
            </button>
          </div>
          {notice && (
            <p role="status" className="mt-1 text-sm text-green-800">
              {notice}
            </p>
          )}
          <p className="mt-1 text-xs text-slate-600">{t('docs.hintEnter')}</p>

          <ol ref={listRef} className="mt-3 grid gap-2">
            {doc.fields.map((field, index) => (
              <FieldRow
                key={field.key}
                field={field}
                index={index}
                showSection={index === 0 || doc.fields[index - 1].section !== field.section}
                changed={doc.changed_keys.includes(field.key)}
                onCopy={() => void copyField(field, index)}
                onSkip={() => focusRow(index + 1)}
                onToggle={(copied) => mark.mutate({ field: field.key, copied })}
              />
            ))}
          </ol>
        </>
      )}
    </main>
  )
}

function FieldRow({
  field,
  index,
  showSection,
  changed,
  onCopy,
  onSkip,
  onToggle,
}: {
  field: DocumentField
  index: number
  showSection: boolean
  changed: boolean
  onCopy: () => void
  onSkip: () => void
  onToggle: (copied: boolean) => void
}) {
  const { t } = useTranslation()
  const [ticked, setTicked] = useState<Set<string>>(new Set())
  const canCopy = COPYABLE(field) && !field.locked
  const muted = field.display !== 'value'

  return (
    <>
      {showSection && (
        <li className="mt-3 text-xs font-bold uppercase tracking-wide text-teal-900">
          {field.section}
        </li>
      )}
      <li
        data-row={index}
        data-key={field.key}
        data-changed={changed || undefined}
        tabIndex={0}
        aria-label={field.label}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && e.target === e.currentTarget) {
            e.preventDefault()
            if (canCopy) onCopy()
            else onSkip()
          }
        }}
        className={`rounded border bg-white p-3 outline-none focus:ring-2 focus:ring-teal-700 ${
          changed ? 'border-amber-600 bg-amber-50' : 'border-slate-300'
        } ${field.missing ? 'border-red-600' : ''}`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-auto text-sm font-semibold text-slate-900">
            {field.label}
            {field.critical && (
              <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 text-[11px] font-semibold text-red-900">
                {t('docs.critical')}
              </span>
            )}
          </span>
          <span className="rounded bg-slate-200 px-2 py-0.5 text-[11px] font-medium text-slate-800">
            {t(`docs.types.${field.emr_type}`)}
          </span>
        </div>

        <div className="mt-2 text-sm">
          {field.display === 'keep_emr' && <strong>{t('docs.keepEmr')}</strong>}
          {field.display === 'calculate' && (
            <span className="text-slate-700">{t('docs.calculate')}</span>
          )}
          {field.display === 'skip' && (
            <span className="text-slate-600">{field.hint ?? t('docs.skip')}</span>
          )}
          {field.display === 'manual' && (
            <span className="text-slate-700">{field.hint ?? t('docs.manual')}</span>
          )}
          {field.display === 'value' && field.value && (
            <p className="whitespace-pre-wrap break-words" data-testid={`value-${field.key}`}>
              {field.value}
            </p>
          )}
          {field.display === 'value' && field.items && field.items.length > 0 && (
            <ul className="grid gap-1">
              {field.items.map((item) => (
                <li key={item}>
                  <label className="flex min-h-11 items-center gap-3">
                    <input
                      type="checkbox"
                      className="h-5 w-5"
                      checked={ticked.has(item)}
                      onChange={(e) => {
                        const next = new Set(ticked)
                        if (e.target.checked) next.add(item)
                        else next.delete(item)
                        setTicked(next)
                      }}
                    />
                    {item}
                  </label>
                </li>
              ))}
            </ul>
          )}
          {field.display === 'value' && field.icd && field.icd.length > 0 && (
            <ul className="grid gap-1">
              {field.icd.map((entry) => (
                <li key={`${entry.code}-${entry.text}`}>
                  <strong>{entry.code}</strong> {entry.text}
                </li>
              ))}
            </ul>
          )}
          {field.display === 'value' && !canCopy && (
            <span className="text-slate-500">{t('docs.empty')}</span>
          )}
          {field.display === 'value' && field.hint && (
            <p className="mt-1 text-xs text-amber-900">{field.hint}</p>
          )}
          {field.missing && (
            <p role="alert" className="mt-1 text-xs font-semibold text-red-800">
              {t('docs.problem.missing')}
            </p>
          )}
        </div>

        {canCopy && (
          <div className="mt-2 flex items-center gap-3">
            <button
              type="button"
              onClick={onCopy}
              className="min-h-11 rounded bg-teal-700 px-4 text-sm font-medium text-white"
            >
              {t('docs.copy')}
            </button>
            {field.emr_type === 'icd10' ? (
              <label className="flex min-h-11 items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="h-5 w-5"
                  checked={field.copied}
                  onChange={(e) => onToggle(e.target.checked)}
                />
                {t('docs.selected')}
              </label>
            ) : (
              field.copied && (
                <span
                  className="text-sm font-semibold text-green-800"
                  aria-label={t('docs.copied')}
                >
                  ✔ {t('docs.copied')}
                </span>
              )
            )}
          </div>
        )}
        {field.locked && (
          <p
            role="status"
            className="mt-2 text-sm font-semibold text-amber-900"
            data-testid={`locked-${field.key}`}
          >
            {t('docs.locked')}
          </p>
        )}
        {muted &&
          field.display === 'keep_emr' &&
          field.hint &&
          field.hint !== t('docs.keepEmr') && <p className="mt-1 text-xs">{field.hint}</p>}
      </li>
    </>
  )
}
