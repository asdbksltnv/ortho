/** Immutable set by dotted path: setIn(data, 'vitals.bp', '120/80'). */
export function setIn<T>(obj: T, path: string, value: unknown): T {
  const [head, ...rest] = path.split('.')
  const source = obj as Record<string, unknown>
  const next = Array.isArray(obj) ? ([...obj] as unknown as Record<string, unknown>) : { ...source }
  next[head] = rest.length === 0 ? value : setIn(source[head], rest.join('.'), value)
  return next as T
}

export function getIn(obj: unknown, path: string): unknown {
  return path
    .split('.')
    .reduce<unknown>((node, key) => (node as Record<string, unknown> | undefined)?.[key], obj)
}
