import type { CaseSnapshot } from '../drafts'
import type { CapriniResult, NutritionResult } from '../scores'
import type { IntakeConfig, IntakeData } from '../types'

export interface Ctx {
  data: IntakeData
  update: (path: string, value: unknown) => void
  config: IntakeConfig
  snapshot: CaseSnapshot
  age: number | null
  bmiValue: number | null
  caprini: CapriniResult
  nutrition: NutritionResult
  columbiaVisible: number[]
  columbiaAlert: boolean
}
