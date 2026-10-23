import { describe, expect, it } from 'vitest'
import { formatDate, formatDateTime } from './format'
import { canEditItem } from './permissions'

describe('formatDate', () => {
  it('uses ДД.ММ.ГГГГ', () => expect(formatDate('2026-03-09')).toBe('09.03.2026'))
  it('handles empty values', () => expect(formatDate(null)).toBe('—'))
})

describe('formatDateTime', () => {
  it('renders Asia/Tashkent time (UTC+5)', () => {
    expect(formatDateTime('2026-03-09T19:30:00+00:00')).toBe('10.03.2026 00:30')
  })
})

describe('canEditItem (UI mirror of the backend matrix)', () => {
  it('lets only the anaesthesiologist and head edit clearance', () => {
    expect(canEditItem('anaesthesiologist', 'anaesthesia', 'anaesthesiologist', false)).toBe(true)
    expect(canEditItem('head_of_department', 'anaesthesia', 'anaesthesiologist', false)).toBe(true)
    expect(canEditItem('doctor', 'anaesthesia', 'anaesthesiologist', true)).toBe(false)
    expect(canEditItem('nurse', 'anaesthesia', 'anaesthesiologist', false)).toBe(false)
  })
  it('restricts doctors to their own patients', () => {
    expect(canEditItem('doctor', 'docs', 'doctor', true)).toBe(true)
    expect(canEditItem('doctor', 'docs', 'doctor', false)).toBe(false)
  })
  it('lets nurses edit nurse items and the surgical consent', () => {
    expect(canEditItem('nurse', 'labs_core', 'nurse', false)).toBe(true)
    expect(canEditItem('nurse', 'consent_surgical', 'doctor', false)).toBe(true)
    expect(canEditItem('nurse', 'docs', 'doctor', false)).toBe(false)
  })
  it('gives admin no clinical edit rights', () => {
    expect(canEditItem('admin', 'docs', 'doctor', true)).toBe(false)
  })
})
