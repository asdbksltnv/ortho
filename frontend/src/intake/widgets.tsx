import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

const touch = 'min-h-11'

export function Section({
  id,
  number,
  title,
  filled,
  children,
}: {
  id: string
  number: number
  title: string
  filled?: boolean
  children: ReactNode
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-h`}
      className="scroll-mt-32 rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm sm:p-5"
    >
      <h2 id={`${id}-h`} className="flex items-center gap-3 text-base font-bold text-slate-900">
        <span
          aria-hidden
          className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm ${
            filled ? 'bg-teal-700 text-white' : 'bg-teal-50 text-teal-900 ring-1 ring-teal-200'
          }`}
        >
          {number}
        </span>
        <span className="min-w-0">
          <span className="sr-only">{`${number}.`}</span>
          {` ${title}`}
        </span>
      </h2>
      <div className="mt-4 grid gap-5">{children}</div>
    </section>
  )
}

/** A titled group inside a section. */
export function SubSection({
  title,
  aside,
  children,
}: {
  title: string
  aside?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="grid gap-4 rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200/70 sm:p-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="mr-auto text-sm font-bold uppercase tracking-wide text-teal-900">{title}</h3>
        {aside}
      </div>
      {children}
    </div>
  )
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string
  children: ReactNode
  hint?: string
}) {
  return (
    <div role="group" aria-label={label} className="grid gap-1.5">
      <span className="text-sm font-semibold text-slate-800">{label}</span>
      {children}
      {hint && <span className="text-xs text-slate-600">{hint}</span>}
    </div>
  )
}

const optionOn = 'border-teal-700 bg-teal-700 font-semibold text-white shadow-sm'
const optionOff = 'border-slate-300 bg-white text-slate-900 hover:border-teal-600 hover:bg-teal-50'

/** Large touch buttons instead of typing. Tapping the selected option again clears it. */
export function Segmented({
  options,
  value,
  onChange,
  label,
}: {
  options: string[]
  value: string | null
  onChange: (value: string | null) => void
  label: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((option) => {
        const selected = value === option
        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(selected ? null : option)}
            className={`${touch} rounded-lg border px-3.5 text-sm transition-colors ${selected ? optionOn : optionOff}`}
          >
            {option}
          </button>
        )
      })}
    </div>
  )
}

// Green to red; text colour chosen per step so every button keeps AA contrast.
const PAIN_STEPS = [
  'bg-emerald-100 border-emerald-300 text-emerald-950',
  'bg-emerald-100 border-emerald-300 text-emerald-950',
  'bg-lime-100 border-lime-300 text-lime-950',
  'bg-lime-100 border-lime-300 text-lime-950',
  'bg-yellow-100 border-yellow-300 text-yellow-950',
  'bg-amber-100 border-amber-300 text-amber-950',
  'bg-amber-200 border-amber-400 text-amber-950',
  'bg-orange-200 border-orange-400 text-orange-950',
  'bg-orange-300 border-orange-500 text-orange-950',
  'bg-red-200 border-red-400 text-red-950',
  'bg-red-300 border-red-500 text-red-950',
]

/** Visual analogue scale 0–10 as a colour-graded row of touch buttons. */
export function PainScale({
  value,
  onChange,
  label,
}: {
  value: number | null
  onChange: (value: number | null) => void
  label: string
}) {
  return (
    <div className="grid gap-1">
      <div role="radiogroup" aria-label={label} className="grid grid-cols-11 gap-1">
        {PAIN_STEPS.map((tone, n) => {
          const selected = value === n
          return (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(selected ? null : n)}
              className={`${touch} rounded-lg border text-sm font-semibold tabular-nums transition ${tone} ${
                selected
                  ? 'scale-105 ring-2 ring-slate-900 ring-offset-1'
                  : value !== null
                    ? 'opacity-60'
                    : ''
              }`}
            >
              {n}
            </button>
          )
        })}
      </div>
      <div className="flex justify-between text-[11px] text-slate-600" aria-hidden>
        <span>нет боли</span>
        <span>умеренная</span>
        <span>нестерпимая</span>
      </div>
    </div>
  )
}

export function YesNo({
  value,
  onChange,
  label,
}: {
  value: boolean | null
  onChange: (value: boolean | null) => void
  label: string
}) {
  return (
    <Segmented
      label={label}
      options={['Да', 'Нет']}
      value={value === null ? null : value ? 'Да' : 'Нет'}
      onChange={(v) => onChange(v === null ? null : v === 'Да')}
    />
  )
}

export function Check({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}) {
  return (
    <label
      className={`flex ${touch} w-fit cursor-pointer items-center gap-3 rounded-lg border px-3 text-sm transition-colors ${
        checked
          ? 'border-teal-600 bg-teal-50 font-medium text-teal-950'
          : 'border-slate-300 bg-white hover:border-teal-600'
      }`}
    >
      <input
        type="checkbox"
        className="h-5 w-5 accent-teal-700"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  )
}

export function Chips({
  options,
  value,
  onChange,
  label,
}: {
  options: string[]
  value: string[]
  onChange: (value: string[]) => void
  label: string
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((option) => {
        const on = value.includes(option)
        return (
          <button
            key={option}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(on ? value.filter((v) => v !== option) : [...value, option])}
            className={`${touch} rounded-full border px-3.5 text-sm transition-colors ${on ? optionOn : optionOff}`}
          >
            {on ? '✔ ' : ''}
            {option}
          </button>
        )
      })}
    </div>
  )
}

/** Answers such as «нет» exclude every other answer of a multi-choice question. */
const EXCLUSIVE = new Set(['нет', 'не использует'])

/**
 * Dropdown with checkboxes for questions that allow several answers. It opens in place (not as
 * an overlay) so it is never hidden under the fixed bottom bar on a phone.
 */
export function MultiSelect({
  options,
  value,
  onChange,
  label,
}: {
  options: string[]
  value: string[]
  onChange: (value: string[]) => void
  label: string
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const panelId = useId()
  useEffect(() => {
    if (!open) return
    const onPointer = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const summary = value.length ? value.join(', ') : 'Выберите…'
  const toggle = (option: string, on: boolean) => {
    if (!on) return onChange(value.filter((v) => v !== option))
    if (EXCLUSIVE.has(option)) return onChange([option])
    onChange([...value.filter((v) => !EXCLUSIVE.has(v)), option])
  }

  return (
    <div ref={root} className="grid gap-1">
      <button
        type="button"
        aria-label={`${label}: ${summary}`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className={`${inputClass} flex items-center gap-2 text-left ${open ? 'border-teal-600 ring-2 ring-teal-600/20' : ''}`}
      >
        <span className={`min-w-0 flex-1 truncate ${value.length ? '' : 'text-slate-500'}`}>
          {summary}
        </span>
        {value.length > 1 && (
          <span
            aria-hidden
            className="rounded-full bg-teal-700 px-2 text-xs font-semibold text-white"
          >
            {value.length}
          </span>
        )}
        <Chevron open={open} />
      </button>
      {open && (
        <div
          id={panelId}
          role="group"
          aria-label={`${label}: варианты`}
          className="grid gap-0.5 rounded-xl border border-slate-200 bg-white p-1 shadow-lg"
        >
          {options.map((option) => {
            const on = value.includes(option)
            return (
              <label
                key={option}
                className={`flex ${touch} cursor-pointer items-center gap-3 rounded-lg px-3 text-sm ${
                  on ? 'bg-teal-50 font-medium text-teal-950' : 'hover:bg-slate-50'
                }`}
              >
                <input
                  type="checkbox"
                  className="h-5 w-5 accent-teal-700"
                  checked={on}
                  onChange={(e) => toggle(option, e.target.checked)}
                />
                {option}
              </label>
            )
          })}
          <div className="flex justify-end gap-2 border-t border-slate-100 p-1 pt-2">
            {value.length > 0 && (
              <button
                type="button"
                onClick={() => onChange([])}
                className={`${touch} rounded-lg px-3 text-sm text-slate-700 hover:bg-slate-100`}
              >
                Очистить
              </button>
            )}
            <button
              type="button"
              onClick={() => setOpen(false)}
              className={`${touch} rounded-lg bg-teal-700 px-4 text-sm font-medium text-white`}
            >
              Готово
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 20 20"
      className={`h-5 w-5 shrink-0 text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`}
      fill="currentColor"
    >
      <path d="M5.3 7.3a1 1 0 0 1 1.4 0L10 10.6l3.3-3.3a1 1 0 1 1 1.4 1.4l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 0 1 0-1.4z" />
    </svg>
  )
}

/**
 * One-tap suggestions under a free-text field. Single mode replaces the text (tap again to
 * clear); append mode adds or removes the phrase in a comma-separated list.
 */
export function QuickPicks({
  options,
  value,
  onChange,
  label,
  append = false,
}: {
  options: string[]
  value: string
  onChange: (value: string) => void
  label: string
  append?: boolean
}) {
  if (options.length === 0) return null
  const parts = value
    .split(',')
    .map((p) => p.trim())
    .filter(Boolean)
  return (
    <div role="group" aria-label={`${label}: быстрый выбор`} className="flex flex-wrap gap-1.5">
      {options.map((option) => {
        const on = append ? parts.includes(option) : value.trim() === option
        return (
          <button
            key={option}
            type="button"
            aria-pressed={on}
            onClick={() => {
              if (!append) return onChange(on ? '' : option)
              onChange((on ? parts.filter((p) => p !== option) : [...parts, option]).join(', '))
            }}
            className={`min-h-9 rounded-full border px-3 text-xs transition-colors ${
              on
                ? 'border-teal-700 bg-teal-700 font-semibold text-white'
                : 'border-dashed border-slate-400 bg-white text-slate-800 hover:border-teal-600 hover:bg-teal-50'
            }`}
          >
            {on ? '✔ ' : '+ '}
            {option}
          </button>
        )
      })}
    </div>
  )
}

const inputClass = `${touch} w-full rounded-lg border border-slate-300 bg-white px-3 text-base shadow-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20`

export function Text({
  value,
  onChange,
  label,
  placeholder,
  maxLength = 200,
}: {
  value: string
  onChange: (value: string) => void
  label: string
  placeholder?: string
  maxLength?: number
}) {
  return (
    <input
      aria-label={label}
      value={value}
      maxLength={maxLength}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className={inputClass}
    />
  )
}

export function TextArea({
  value,
  onChange,
  label,
  rows = 3,
}: {
  value: string
  onChange: (value: string) => void
  label: string
  rows?: number
}) {
  return (
    <textarea
      aria-label={label}
      value={value}
      rows={rows}
      maxLength={2000}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-lg border border-slate-300 bg-white p-3 text-base shadow-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
    />
  )
}

/** Numeric keypad on phones; empty string clears the value. */
export function Num({
  value,
  onChange,
  label,
  decimal = false,
  negative = false,
  min,
  max,
}: {
  value: number | null
  onChange: (value: number | null) => void
  label: string
  decimal?: boolean
  negative?: boolean
  min?: number
  max?: number
}) {
  // While typing, show the raw text; otherwise mirror the value (so outside changes show up).
  const [draft, setDraft] = useState<string | null>(null)
  const text = draft ?? (value === null ? '' : String(value))
  return (
    <input
      aria-label={label}
      type="text"
      inputMode={decimal ? 'decimal' : negative ? 'text' : 'numeric'}
      pattern={decimal ? '[0-9]*[.,]?[0-9]*' : negative ? '-?[0-9]*' : '[0-9]*'}
      value={text}
      onBlur={() => setDraft(null)}
      onChange={(e) => {
        const raw = e.target.value.replace(',', '.').trim()
        if (raw === '') {
          setDraft('')
          return onChange(null)
        }
        const n = Number(raw)
        if (Number.isNaN(n) || (!decimal && raw.includes('.'))) return
        if (
          (min !== undefined && n < min && raw.length >= String(min).length) ||
          (max !== undefined && n > max)
        ) {
          return
        }
        setDraft(e.target.value)
        onChange(n)
      }}
      className={`${inputClass} max-w-40 tabular-nums`}
    />
  )
}

export function Select({
  value,
  onChange,
  label,
  options,
  placeholder = 'Выберите…',
}: {
  value: string | null
  onChange: (value: string | null) => void
  label: string
  options: { value: string; label: string }[]
  placeholder?: string
}) {
  return (
    <select
      aria-label={label}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value || null)}
      className={`${inputClass} select-chevron ${value ? '' : 'text-slate-500'}`}
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value} className="text-slate-900">
          {o.label}
        </option>
      ))}
    </select>
  )
}

export function AddButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${touch} w-fit rounded-lg border border-dashed border-teal-700 px-4 text-sm font-medium text-teal-900 transition-colors hover:bg-teal-50`}
    >
      + {children}
    </button>
  )
}

export function RemoveButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`${touch} min-w-11 rounded-lg border border-slate-300 bg-white text-lg leading-none text-slate-700 transition-colors hover:border-red-400 hover:bg-red-50 hover:text-red-800`}
    >
      ×
    </button>
  )
}
