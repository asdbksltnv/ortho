/** Copies text; falls back to a hidden textarea where the async Clipboard API is unavailable. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // fall through to the legacy path
  }
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.appendChild(area)
  area.select()
  try {
    return document.execCommand('copy')
  } finally {
    document.body.removeChild(area)
  }
}

/** What the Copy button puts on the clipboard for one EMR field. */
export function copyPayload(field: {
  display: string
  value: string | null
  items: string[] | null
  icd: { code: string; text: string }[] | null
}): string | null {
  if (field.display !== 'value') return null
  if (field.value) return field.value
  if (field.items && field.items.length > 0) return field.items.join('\n')
  if (field.icd && field.icd.length > 0) return field.icd.map((e) => e.code || e.text).join('\n')
  return null
}
