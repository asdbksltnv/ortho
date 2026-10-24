/** Mirrors app/domain/intake.py. Every field is optional so drafts can be saved at any time. */

export interface Finding {
  normal: boolean | null
  text: string
}
export interface IcdEntry {
  code: string
  text: string
}
export interface Vitals {
  bp: string | null
  pulse: number | null
  hr: number | null
  rr: number | null
  spo2: number | null
  temp: number | null
  weight: number | null
  height: number | null
}
export const SYSTEM_KEYS = ['skin', 'cvs', 'resp', 'msk', 'gu', 'gi', 'neuro'] as const
export const PSYCHO_KEYS = [
  'behavior',
  'appearance',
  'mood',
  'emotions',
  'understanding',
  'criticism',
] as const

export interface IntakeData {
  history: {
    onset_date: string | null
    mechanism: string
    duration: string
    prior_treatment: string
    course: string | null
    hospitalization_count: number | null
  }
  complaints: {
    segment: string | null
    pain_vas: number | null
    limitation: boolean
    deformity: boolean
    swelling: boolean
    weight_bearing: string | null
    other: string
    /** Answers to the location-specific questions, keyed by question key. */
    details: Record<string, string | string[]>
  }
  allergy: { has: boolean | null; description: string }
  past: {
    denies: boolean
    items: { text: string; year: number | null }[]
    epidemiological: string[]
    epidemiological_other: string
  }
  medications: { name: string; dose: string; frequency: string; is_anticoagulant: boolean }[]
  medications_none: boolean
  social: {
    alcohol: string | null
    alcohol_amount: string
    tobacco: string | null
    drugs: string | null
    economic: string | null
    physical_activity: string | null
  }
  psycho: Record<(typeof PSYCHO_KEYS)[number], string | null>
  vitals: Vitals
  general: { severity: string | null; consciousness: string | null; position: string | null }
  systems: Record<(typeof SYSTEM_KEYS)[number], Finding>
  local_status: {
    segment: string | null
    inspection: string[]
    inspection_text: string
    palpation: string
    rom: { movement: string; degrees: number }[]
    stability: { test: string; result: string }[]
    neurovascular: { pulsation: string | null; sensation: string | null; motor: string | null }
    other: string
  }
  columbia: Record<`q${1 | 2 | 3 | 4 | 5 | 6 | 7}`, boolean | null>
  nutrition: {
    weight_loss: boolean | null
    reduced_intake: boolean | null
    stress_factor: boolean | null
  }
  caprini: { factors: string[] }
  diagnosis: {
    main: IcdEntry
    competing: IcdEntry
    complication: IcdEntry
    background: IcdEntry
    comorbid: IcdEntry[]
  }
  plan: {
    checked: string[]
    diet: string
    special_diet: string
    labs: string[]
    instrumental: string[]
    consults: string[]
    medications: { name: string; note: string; kind: string }[]
    recommendations: string
  }
  preop: {
    economic_assessment: string | null
    social_needs: string | null
    psychological_needs: string | null
    discharge_needs: string[]
    vitals: Vitals
    general_condition: string
    local_status: string
    imaging: string
    failed_conservative: string
  }
}

export interface LocationQuestion {
  key: string
  label_ru: string
  multi: boolean
  options: string[]
}
export interface LocationSpec {
  questions: LocationQuestion[]
  movements: { name_ru: string; rom_normal: number | null }[]
  tests: string[]
}
export interface LocationsConfig {
  common: LocationQuestion[]
  locations: Record<string, LocationSpec>
}

export interface IntakeResponse {
  data: IntakeData
  schema_version: number
  updated_at: string | null
  completed_at: string | null
  is_new: boolean
  can_edit: boolean
}

export interface IntakeConfig {
  picklists: Record<string, string[]>
  segments: { key: string; name_ru: string; gen_ru: string }[]
  /** Optional so a config cached offline by an older build still loads. */
  locations?: LocationsConfig
  systems: Record<string, { label_ru: string; normal_ru: string | null }>
  psycho: Record<string, { label_ru: string; default_ru: string }>
  caprini: {
    factors: {
      key: string
      points: number
      label_ru: string
      auto: { type: string; min: number | null; max: number | null; value: number | null } | null
    }[]
    risk_categories: { key: string; label_ru: string; min: number; max: number | null }[]
  }
  columbia: {
    questions: { n: number; text_ru: string | null }[]
    always_ask: number[]
    follow_up: number[]
    follow_up_trigger: number[]
    urgent_consult_rule: { all_yes: number[]; any_yes: number[]; rule_text_ru: string | null }
  }
  nutrition: {
    bmi_threshold: number
    questions: { key: string; label_ru: string; auto: boolean }[]
  }
  diets: string[]
  default_diet: string | null
  core_labs: string[]
}

const emptyFinding = (): Finding => ({ normal: null, text: '' })
const emptyVitals = (): Vitals => ({
  bp: null,
  pulse: null,
  hr: null,
  rr: null,
  spo2: null,
  temp: null,
  weight: null,
  height: null,
})
const emptyIcd = (): IcdEntry => ({ code: '', text: '' })

export function emptyIntake(): IntakeData {
  return {
    history: {
      onset_date: null,
      mechanism: '',
      duration: '',
      prior_treatment: '',
      course: null,
      hospitalization_count: null,
    },
    complaints: {
      segment: null,
      pain_vas: null,
      limitation: false,
      deformity: false,
      swelling: false,
      weight_bearing: null,
      other: '',
      details: {},
    },
    allergy: { has: null, description: '' },
    past: { denies: false, items: [], epidemiological: [], epidemiological_other: '' },
    medications: [],
    medications_none: false,
    social: {
      alcohol: null,
      alcohol_amount: '',
      tobacco: null,
      drugs: null,
      economic: null,
      physical_activity: null,
    },
    psycho: {
      behavior: null,
      appearance: null,
      mood: null,
      emotions: null,
      understanding: null,
      criticism: null,
    },
    vitals: emptyVitals(),
    general: { severity: null, consciousness: null, position: null },
    systems: {
      skin: emptyFinding(),
      cvs: emptyFinding(),
      resp: emptyFinding(),
      msk: emptyFinding(),
      gu: emptyFinding(),
      gi: emptyFinding(),
      neuro: emptyFinding(),
    },
    local_status: {
      segment: null,
      inspection: [],
      inspection_text: '',
      palpation: '',
      rom: [],
      stability: [],
      neurovascular: { pulsation: null, sensation: null, motor: null },
      other: '',
    },
    columbia: { q1: null, q2: null, q3: null, q4: null, q5: null, q6: null, q7: null },
    nutrition: { weight_loss: null, reduced_intake: null, stress_factor: null },
    caprini: { factors: [] },
    diagnosis: {
      main: emptyIcd(),
      competing: emptyIcd(),
      complication: emptyIcd(),
      background: emptyIcd(),
      comorbid: [],
    },
    plan: {
      checked: [],
      diet: '',
      special_diet: '',
      labs: [],
      instrumental: [],
      consults: [],
      medications: [],
      recommendations: '',
    },
    preop: {
      economic_assessment: null,
      social_needs: null,
      psychological_needs: null,
      discharge_needs: [],
      vitals: emptyVitals(),
      general_condition: '',
      local_status: '',
      imaging: '',
      failed_conservative: '',
    },
  }
}

/** Common questions first, then the ones for the segment; none until a segment is chosen. */
export function questionsFor(config: IntakeConfig, segment: string | null): LocationQuestion[] {
  if (!segment || !config.locations) return []
  return [...config.locations.common, ...(config.locations.locations[segment]?.questions ?? [])]
}

export function locationSpec(config: IntakeConfig, segment: string | null): LocationSpec | null {
  return (segment && config.locations?.locations[segment]) || null
}
