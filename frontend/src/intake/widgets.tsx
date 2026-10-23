import { useState, type ReactNode } from 'react'

const touch = 'min-h-11'

export function Section({
  id,
  number,
  title,
  children,
}: {
  id: string
  number: number
  title: string
  children: ReactNode
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-h`}
      className="scroll-mt-24 rounded border border-slate-300 bg-white p-3"
    >
      <h2 id={`${id}-h`} className="text-base font-bold text-slate-900">
        {number}. {title}
      </h2>
      <div className="mt-3 grid gap-4">{children}</div>
    </section>
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
    <div role="group" aria-label={label} className="grid gap-1">
      <span className="text-sm font-medium text-slate-800">{label}</span>
      {children}
      {hint && <span className="text-xs text-slate-600">{hint}</span>}
    </div>
  )
}

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
            className={`${touch} rounded border px-3 text-sm ${
              selected
                ? 'border-teal-800 bg-teal-700 font-semibold text-white'
                : 'border-slate-400 bg-white text-slate-900'
            }`}
          >
            {option}
          </button>
        )
      })}
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
    <label className={`flex ${touch} cursor-pointer items-center gap-3 text-sm`}>
      <input
        type="checkbox"
        className="h-5 w-5"
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
            className={`${touch} rounded-full border px-3 text-sm ${
              on ? 'border-teal-800 bg-teal-700 text-white' : 'border-slate-400 bg-white'
            }`}
          >
            {on ? '✔ ' : ''}
            {option}
          </button>
        )
      })}
    </div>
  )
}

const inputClass = `${touch} w-full rounded border border-slate-400 bg-white px-3 text-base`

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
      className="w-full rounded border border-slate-400 bg-white p-3 text-base"
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
      className={`${inputClass} max-w-40`}
    />
  )
}

export function Select({
  value,
  onChange,
  label,
  options,
}: {
  value: string | null
  onChange: (value: string | null) => void
  label: string
  options: { value: string; label: string }[]
}) {
  return (
    <select
      aria-label={label}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value || null)}
      className={inputClass}
    >
      <option value="" />
      {options.map((o) => (
        <option key={o.value} value={o.value}>
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
      className={`${touch} w-fit rounded border border-dashed border-teal-800 px-4 text-sm font-medium text-teal-900`}
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
      className={`${touch} min-w-11 rounded border border-slate-400 text-lg leading-none`}
    >
      ×
    </button>
  )
}
