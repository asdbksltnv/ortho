/** Live Caprini / Columbia / nutrition logic. Mirrors app/domain/{caprini,columbia,nutrition}.py. */
import type { IntakeConfig, IntakeData, Vitals } from './types'

type Factor = IntakeConfig['caprini']['factors'][number]

export function bmi(weight: number | null, height: number | null): number | null {
  if (!weight || !height || weight <= 0 || height <= 0) return null
  const m = height / 100
  return weight / (m * m)
}

/** Admission vitals overridden by the fresh pre-operative measurement where present. */
export function latestVitals(data: IntakeData): Vitals {
  const merged = { ...data.vitals }
  for (const [key, value] of Object.entries(data.preop.vitals)) {
    if (value !== null && value !== undefined) (merged as Record<string, unknown>)[key] = value
  }
  return merged
}

export function ageOn(birth: string, on: Date): number {
  const [y, m, d] = birth.slice(0, 10).split('-').map(Number)
  let years = on.getFullYear() - y
  if (on.getMonth() + 1 < m || (on.getMonth() + 1 === m && on.getDate() < d)) years -= 1
  return years
}

/** Today's calendar date in Tashkent as a local Date (year, month, day only). */
export function tashkentToday(now: Date = new Date()): Date {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tashkent',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now)
  const [y, m, d] = parts.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function autoApplies(factor: Factor, age: number | null, bmiValue: number | null): boolean | null {
  const rule = factor.auto
  if (!rule) return null
  if (rule.type === 'age') {
    if (age === null) return null
    return (rule.min === null || age >= rule.min) && (rule.max === null || age <= rule.max)
  }
  if (rule.type === 'bmi_over') {
    if (bmiValue === null || rule.value === null) return null
    return bmiValue > rule.value
  }
  return null
}

export interface CapriniResult {
  total: number
  categoryKey: string
  categoryLabel: string
  counted: string[]
  automatic: string[]
}

export function computeCaprini(
  config: IntakeConfig['caprini'],
  manual: string[],
  age: number | null,
  bmiValue: number | null,
): CapriniResult {
  const counted: string[] = []
  const automatic: string[] = []
  let total = 0
  for (const factor of config.factors) {
    let applies: boolean
    if (factor.auto) {
      const auto = autoApplies(factor, age, bmiValue)
      applies = auto === null ? manual.includes(factor.key) : auto
      if (auto === true) automatic.push(factor.key)
    } else {
      applies = manual.includes(factor.key)
    }
    if (applies) {
      counted.push(factor.key)
      total += factor.points
    }
  }
  const category = config.risk_categories.find(
    (c) => total >= c.min && (c.max === null || total <= c.max),
  )
  return {
    total,
    categoryKey: category?.key ?? '',
    categoryLabel: category?.label_ru ?? '',
    counted,
    automatic,
  }
}

type Answers = Record<number, boolean | null>

export function columbiaAnswers(data: IntakeData): Answers {
  const out: Answers = {}
  for (let i = 1; i <= 7; i++) out[i] = data.columbia[`q${i}` as keyof IntakeData['columbia']]
  return out
}

export function visibleQuestions(config: IntakeConfig['columbia'], answers: Answers): number[] {
  const triggered = config.follow_up_trigger.some((n) => answers[n] === true)
  const shown = new Set([...config.always_ask, ...(triggered ? config.follow_up : [])])
  return [...shown].sort((a, b) => a - b)
}

export function urgentConsultAlert(config: IntakeConfig['columbia'], answers: Answers): boolean {
  const shown = new Set(visibleQuestions(config, answers))
  const yes = (n: number) => shown.has(n) && answers[n] === true
  const rule = config.urgent_consult_rule
  if (rule.all_yes.length === 0 && rule.any_yes.length === 0) return false
  return rule.all_yes.every(yes) && (rule.any_yes.length === 0 || rule.any_yes.some(yes))
}

export interface NutritionResult {
  bmiLow: boolean | null
  total: number
  complete: boolean
}

export function computeNutrition(
  config: IntakeConfig['nutrition'],
  data: IntakeData,
  bmiValue: number | null,
): NutritionResult {
  const bmiLow = bmiValue === null ? null : bmiValue < config.bmi_threshold
  const answers = [
    bmiLow,
    data.nutrition.weight_loss,
    data.nutrition.reduced_intake,
    data.nutrition.stress_factor,
  ]
  return {
    bmiLow,
    total: answers.filter((a) => a === true).length,
    complete: answers.every((a) => a !== null),
  }
}
