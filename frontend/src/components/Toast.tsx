import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'

type Kind = 'success' | 'error' | 'info'
interface Toast {
  id: number
  text: string
  kind: Kind
}

const ToastContext = createContext<(text: string, kind?: Kind) => void>(() => undefined)

/** Short confirmations ("Сохранено") that do not move the layout; announced to screen readers. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const next = useRef(1)
  const show = useCallback((text: string, kind: Kind = 'success') => {
    const id = next.current++
    setToasts((all) => [...all.slice(-2), { id, text, kind }])
    window.setTimeout(
      () => setToasts((all) => all.filter((t) => t.id !== id)),
      kind === 'error' ? 6000 : 3000,
    )
  }, [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex flex-col items-center gap-2 px-4 md:bottom-6"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.kind === 'error' ? 'alert' : 'status'}
            className={`pointer-events-auto max-w-sm rounded-lg px-4 py-2 text-sm font-medium text-white shadow-lg ${
              t.kind === 'error'
                ? 'bg-red-700'
                : t.kind === 'info'
                  ? 'bg-slate-800'
                  : 'bg-green-800'
            }`}
          >
            {t.kind === 'success' ? '✔ ' : t.kind === 'error' ? '✖ ' : ''}
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
