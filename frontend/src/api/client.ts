export interface Meta {
  version: string
  demo_mode: boolean
  session_timeout_min: number
  decimal_separator: string
  tz_display: string
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message)
  }
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

export const UNAUTHORIZED_EVENT = 'auth:unauthorized'

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET') headers['X-CSRF-Token'] = csrfToken()
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers,
    credentials: 'same-origin',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (response.status === 204) return undefined as T
  const data = (await response.json().catch(() => ({}))) as Record<string, unknown>
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login') {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    }
    throw new ApiError(
      response.status,
      String(data.code ?? 'error'),
      String(data.message ?? 'Ошибка запроса'),
      (data.details as Record<string, unknown>) ?? {},
    )
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}

export const fetchMeta = () => api.get<Meta>('/meta')
