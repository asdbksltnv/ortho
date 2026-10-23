export interface Meta {
  version: string
  demo_mode: boolean
  session_timeout_min: number
  decimal_separator: string
  tz_display: string
}

export class ApiError extends Error {
  constructor(public status: number) {
    super(`HTTP ${status}`)
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { credentials: 'same-origin' })
  if (!response.ok) throw new ApiError(response.status)
  return (await response.json()) as T
}

export const fetchMeta = () => apiGet<Meta>('/meta')
