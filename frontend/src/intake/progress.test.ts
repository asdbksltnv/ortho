import { describe, expect, it } from 'vitest'
import { filledSections } from './progress'
import { emptyIntake } from './types'

describe('filledSections', () => {
  it('is empty for a blank form and grows with answers', () => {
    const d = emptyIntake()
    expect(filledSections(d).size).toBe(0)
    d.allergy.has = false
    d.complaints.segment = 'knee'
    d.vitals.pulse = 70
    d.systems.neuro = { normal: true, text: '' }
    expect([...filledSections(d)].sort((a, b) => a - b)).toEqual([2, 3, 8, 10])
  })

  it('counts a «denies» tick as an answer', () => {
    const d = emptyIntake()
    d.past.denies = true
    d.medications_none = true
    expect(filledSections(d)).toEqual(new Set([4, 5]))
  })
})
