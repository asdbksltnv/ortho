import { describe, expect, it } from 'vitest'
import config from '../test/intakeConfig.json'
import {
  ageOn,
  bmi,
  columbiaAnswers,
  computeCaprini,
  computeNutrition,
  latestVitals,
  tashkentToday,
  urgentConsultAlert,
  visibleQuestions,
} from './scores'
import { emptyIntake, type IntakeConfig } from './types'

// src/test/intakeConfig.json is generated from the real config/*.yaml (see Phase 2 notes), so
// these tests exercise the same factors, points and categories as the backend.
const cfg = config as unknown as IntakeConfig

const caprini = (manual: string[], age: number | null = 30, bmiValue: number | null = 22) =>
  computeCaprini(cfg.caprini, manual, age, bmiValue)

describe('Caprini score', () => {
  it.each([
    [[], 0, 'very_low'],
    [['minor_surgery'], 1, 'low'],
    [['arthroscopic_surgery'], 2, 'low'],
    [['vte_history'], 3, 'moderate'],
    [['arthroscopic_surgery', 'malignancy'], 4, 'moderate'],
    [['hip_pelvis_leg_fracture'], 5, 'high'],
  ])('manual factors %j -> %i (%s)', (manual, total, category) => {
    const r = caprini(manual as string[])
    expect([r.total, r.categoryKey]).toEqual([total, category])
  })

  it.each([
    [40, 0],
    [41, 1],
    [60, 1],
    [61, 2],
    [74, 2],
    [75, 3],
  ])('age %i adds %i point(s) automatically', (age, points) => {
    expect(caprini([], age).total).toBe(points)
  })

  it('BMI factor is strictly above 25 and overrides a manual tick when known', () => {
    expect(caprini([], 30, 25).total).toBe(0)
    expect(caprini([], 30, 25.1).total).toBe(1)
    expect(caprini(['bmi_over_25'], 30, 20).total).toBe(0)
    expect(caprini(['bmi_over_25'], 30, null).total).toBe(1)
  })

  it('reports automatic factors', () => {
    expect(caprini([], 65, 30).automatic.sort()).toEqual(['age_61_74', 'bmi_over_25'])
  })
})

describe('age and BMI helpers', () => {
  it('computes age on the birthday boundary', () => {
    expect(ageOn('1985-03-10', new Date(2026, 2, 9))).toBe(40)
    expect(ageOn('1985-03-10', new Date(2026, 2, 10))).toBe(41)
  })
  it('uses the Tashkent calendar date', () => {
    // 21:00 UTC on 9 March is already 10 March in Tashkent (UTC+5)
    const d = tashkentToday(new Date('2026-03-09T21:00:00Z'))
    expect([d.getFullYear(), d.getMonth() + 1, d.getDate()]).toEqual([2026, 3, 10])
  })
  it('computes BMI', () => {
    expect(bmi(92, 170)).toBeCloseTo(31.83, 1)
    expect(bmi(null, 170)).toBeNull()
  })
  it('prefers the fresh pre-op measurement', () => {
    const d = emptyIntake()
    d.vitals.weight = 90
    d.vitals.height = 170
    d.preop.vitals.weight = 88
    expect(latestVitals(d)).toMatchObject({ weight: 88, height: 170 })
  })
})

describe('Columbia display logic', () => {
  const answers = (a: Record<number, boolean | null>) => ({
    1: null,
    2: null,
    3: null,
    4: null,
    5: null,
    6: null,
    7: null,
    ...a,
  })

  it('asks Q1, Q2 and Q7 always; Q3-6 only after a «да» to Q1 or Q2', () => {
    expect(visibleQuestions(cfg.columbia, answers({}))).toEqual([1, 2, 7])
    expect(visibleQuestions(cfg.columbia, answers({ 1: false, 2: false }))).toEqual([1, 2, 7])
    expect(visibleQuestions(cfg.columbia, answers({ 1: true }))).toEqual([1, 2, 3, 4, 5, 6, 7])
    expect(visibleQuestions(cfg.columbia, answers({ 2: true }))).toEqual([1, 2, 3, 4, 5, 6, 7])
  })

  it('applies the configurable urgent rule (default: Q4 and (Q5 or Q6))', () => {
    expect(urgentConsultAlert(cfg.columbia, answers({ 1: true, 4: true, 5: true }))).toBe(true)
    expect(urgentConsultAlert(cfg.columbia, answers({ 2: true, 4: true, 6: true }))).toBe(true)
    expect(urgentConsultAlert(cfg.columbia, answers({ 1: true, 4: true }))).toBe(false)
    expect(urgentConsultAlert(cfg.columbia, answers({ 4: true, 5: true }))).toBe(false) // hidden
  })

  it('reads answers from the intake data', () => {
    const d = emptyIntake()
    d.columbia.q1 = true
    expect(columbiaAnswers(d)[1]).toBe(true)
  })
})

describe('nutrition screen', () => {
  it('answers the BMI question automatically from weight and height', () => {
    const d = emptyIntake()
    d.nutrition = { weight_loss: false, reduced_intake: false, stress_factor: false }
    expect(computeNutrition(cfg.nutrition, d, 20.4)).toEqual({
      bmiLow: true,
      total: 1,
      complete: true,
    })
    expect(computeNutrition(cfg.nutrition, d, 20.5).bmiLow).toBe(false)
    expect(computeNutrition(cfg.nutrition, d, null)).toMatchObject({
      bmiLow: null,
      complete: false,
    })
  })
})
