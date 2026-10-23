import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useRef, type ReactNode } from 'react'
import { api, ApiError, fetchMeta, UNAUTHORIZED_EVENT } from '../api/client'
import type { User } from '../api/types'
import { clearSnapshots } from '../intake/drafts'

const USER_KEY = 'orthoready:user'

/** Last known user, so the app keeps opening on a ward tablet that has lost its connection. */
function cachedUser(): User | null {
  try {
    const raw = window.localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

function rememberUser(user: User | null) {
  try {
    if (user) window.localStorage.setItem(USER_KEY, JSON.stringify(user))
    else window.localStorage.removeItem(USER_KEY)
  } catch {
    // storage unavailable: the app simply requires a connection at start-up
  }
}

interface AuthValue {
  user: User | null
  loading: boolean
  login: (login: string, password: string) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

const ACTIVITY_EVENTS = ['click', 'keydown', 'touchstart', 'pointerdown'] as const

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()

  const me = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        const user = await api.get<User>('/auth/me')
        rememberUser(user)
        return user
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          rememberUser(null)
          return null
        }
        if (error instanceof TypeError) return cachedUser() // offline
        throw error
      }
    },
    retry: false,
    staleTime: Infinity,
  })
  const meta = useQuery({ queryKey: ['meta'], queryFn: fetchMeta, staleTime: Infinity })

  const clearSession = useCallback(() => {
    rememberUser(null)
    void clearSnapshots() // identifying case snapshots must not outlive the session
    queryClient.setQueryData(['me'], null)
    queryClient.removeQueries({
      predicate: (q) => q.queryKey[0] !== 'me' && q.queryKey[0] !== 'meta',
    })
  }, [queryClient])

  useEffect(() => {
    window.addEventListener(UNAUTHORIZED_EVENT, clearSession)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, clearSession)
  }, [clearSession])

  const loginMutation = useMutation({
    mutationFn: (v: { login: string; password: string }) => api.post<User>('/auth/login', v),
    onSuccess: (user) => {
      rememberUser(user)
      queryClient.setQueryData(['me'], user)
    },
  })

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      clearSession()
    }
  }, [clearSession])

  // Client-side idle logout, in addition to the server's sliding token expiry.
  const timeoutMin = meta.data?.session_timeout_min
  const user = me.data ?? null
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => {
    if (!user || !timeoutMin) return
    const arm = () => {
      window.clearTimeout(timer.current)
      timer.current = window.setTimeout(() => {
        void logout().then(() => {
          window.location.assign('/login?expired=1')
        })
      }, timeoutMin * 60_000)
    }
    arm()
    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, arm, { passive: true }))
    return () => {
      window.clearTimeout(timer.current)
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, arm))
    }
  }, [user, timeoutMin, logout])

  const value: AuthValue = {
    user,
    loading: me.isLoading,
    login: (login, password) => loginMutation.mutateAsync({ login, password }),
    logout,
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}
