import type { IntakeData, Vitals } from './types'

const anyVital = (v: Vitals) => Object.values(v).some((x) => x !== null)
const anyOf = (values: unknown[]) =>
  values.some((v) => (Array.isArray(v) ? v.length > 0 : v !== null && v !== '' && v !== false))

/** Numbers of the form sections (1–16) that already hold any answer. */
export function filledSections(d: IntakeData): Set<number> {
  const checks: Record<number, boolean> = {
    1: d.history.hospitalization_count !== null,
    2: anyOf([
      d.complaints.segment,
      d.complaints.pain_vas,
      d.complaints.other,
      d.history.onset_date,
      d.history.mechanism,
    ]),
    3: d.allergy.has !== null,
    4: d.past.denies || d.past.items.length > 0,
    5: d.medications_none || d.medications.length > 0,
    6: anyOf(Object.values(d.social)),
    7: anyOf(Object.values(d.psycho)),
    8: anyVital(d.vitals),
    9: anyOf(Object.values(d.general)),
    10: Object.values(d.systems).some((s) => s.normal !== null),
    11: anyOf([
      d.local_status.inspection,
      d.local_status.palpation,
      d.local_status.rom,
      d.local_status.stability,
      ...Object.values(d.local_status.neurovascular),
    ]),
    12: anyOf([...Object.values(d.columbia), ...Object.values(d.nutrition)]),
    13: d.caprini.factors.length > 0,
    14: anyOf([d.diagnosis.main.code, d.diagnosis.main.text]),
    15: anyOf([d.plan.diet, d.plan.labs, d.plan.instrumental, d.plan.consults, d.plan.medications]),
    16: anyVital(d.preop.vitals) || anyOf([d.preop.imaging, d.preop.economic_assessment]),
  }
  return new Set(
    Object.entries(checks)
      .filter(([, on]) => on)
      .map(([n]) => Number(n)),
  )
}
