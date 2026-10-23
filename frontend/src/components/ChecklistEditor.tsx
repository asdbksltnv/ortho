import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '../api/client'
import type { CaseDetail, ItemStatus } from '../api/types'
import { formatDateTime } from '../lib/format'
import { StatusIcon } from './StatusIcon'
import { useToast } from './Toast'

const STATUSES: ItemStatus[] = ['not_started', 'pending', 'done', 'problem', 'not_applicable']

interface Props {
  caseId: string
  itemKey: string
  label: string
  status: ItemStatus
  note: string | null
  updatedAt: string
  updatedBy: string | null
  canEdit: boolean
  onClose: () => void
}

interface Conflict {
  status: ItemStatus
  note: string | null
  updated_at: string
  updated_by: string | null
}

export function ChecklistEditor(props: Props) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [status, setStatus] = useState<ItemStatus>(props.status)
  const [note, setNote] = useState(props.note ?? '')
  const [conflict, setConflict] = useState<Conflict | null>(null)

  const mutation = useMutation({
    mutationFn: (expected: string) =>
      api.patch<CaseDetail>(`/cases/${props.caseId}/checklist/${props.itemKey}`, {
        status,
        note: note.trim() || null,
        expected_updated_at: expected,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['case', props.caseId], updated)
      void queryClient.invalidateQueries({ queryKey: ['board'] })
      toast(t('case.toastSaved'))
      props.onClose()
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setConflict(error.details.current as Conflict)
      }
    },
  })

  const error = mutation.error
  const otherError = error instanceof ApiError && error.status !== 409 ? error.message : null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={props.label}
      className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center"
      onClick={(e) => e.target === e.currentTarget && props.onClose()}
    >
      <div className="max-h-[90vh] w-full overflow-y-auto rounded-t-xl bg-white p-4 shadow-xl sm:max-w-md sm:rounded-xl">
        <h2 className="text-lg font-semibold text-slate-900">{props.label}</h2>
        <p className="mt-1 text-xs text-slate-600">
          {props.updatedBy
            ? `${t('item.changedBy')}: ${props.updatedBy}, ${formatDateTime(props.updatedAt)}`
            : formatDateTime(props.updatedAt)}
        </p>

        <fieldset className="mt-3 grid gap-2" disabled={!props.canEdit}>
          <legend className="sr-only">{props.label}</legend>
          {STATUSES.map((s) => (
            <label
              key={s}
              className={`flex min-h-11 cursor-pointer items-center gap-3 rounded border px-3 ${
                status === s ? 'border-teal-700 bg-teal-50' : 'border-slate-300'
              }`}
            >
              <input
                type="radio"
                name="status"
                value={s}
                checked={status === s}
                onChange={() => setStatus(s)}
                className="h-5 w-5"
              />
              <StatusIcon status={s} size={24} />
              <span>{t(`itemStatus.${s}`)}</span>
            </label>
          ))}
        </fieldset>

        <label className="mt-3 block text-sm font-medium text-slate-800">
          {t('item.note')}
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={1000}
            rows={3}
            disabled={!props.canEdit}
            className="mt-1 w-full rounded border border-slate-300 p-2"
          />
        </label>

        {!props.canEdit && <p className="mt-2 text-sm text-slate-600">{t('item.readOnly')}</p>}
        {otherError && (
          <p role="alert" className="mt-2 text-sm text-red-700">
            {otherError}
          </p>
        )}

        {conflict && (
          <div
            role="alert"
            className="mt-3 rounded border border-amber-600 bg-amber-50 p-3 text-sm"
          >
            <p className="font-semibold">{t('item.conflictTitle')}</p>
            <p className="mt-1 flex items-center gap-2">
              <StatusIcon status={conflict.status} size={20} />
              {t(`itemStatus.${conflict.status}`)}
              {conflict.updated_by ? ` — ${conflict.updated_by}` : ''}
            </p>
            {conflict.note && <p className="mt-1 text-slate-700">{conflict.note}</p>}
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                className="min-h-11 flex-1 rounded bg-teal-700 px-3 text-white"
                onClick={() => {
                  const fresh = conflict.updated_at
                  setConflict(null)
                  mutation.mutate(fresh)
                }}
              >
                {t('item.conflictApply')}
              </button>
              <button
                type="button"
                className="min-h-11 flex-1 rounded border border-slate-400 px-3"
                onClick={() => {
                  void queryClient.invalidateQueries({ queryKey: ['board'] })
                  void queryClient.invalidateQueries({ queryKey: ['case', props.caseId] })
                  props.onClose()
                }}
              >
                {t('item.conflictKeep')}
              </button>
            </div>
          </div>
        )}

        <div className="mt-4 flex gap-2">
          {props.canEdit && !conflict && (
            <button
              type="button"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate(props.updatedAt)}
              className="min-h-11 flex-1 rounded bg-teal-700 px-4 font-medium text-white disabled:opacity-60"
            >
              {mutation.isPending ? t('item.saving') : t('common.save')}
            </button>
          )}
          <button
            type="button"
            onClick={props.onClose}
            className="min-h-11 flex-1 rounded border border-slate-400 px-4"
          >
            {t('common.close')}
          </button>
        </div>
      </div>
    </div>
  )
}
