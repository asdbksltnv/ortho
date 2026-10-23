export type Role =
  'doctor' | 'nurse' | 'anaesthesiologist' | 'head_of_department' | 'head_nurse' | 'admin'

export type ItemStatus = 'not_started' | 'pending' | 'done' | 'problem' | 'not_applicable'

export type CaseStatus =
  | 'admitted'
  | 'in_preparation'
  | 'approved_for_surgery'
  | 'called_to_or'
  | 'left_ward'
  | 'in_or'
  | 'returned_to_ward'
  | 'transferred_icu'
  | 'post_op'
  | 'discharged'

export interface User {
  id: string
  login: string
  full_name: string
  role: Role
  is_active: boolean
  telegram_linked?: boolean
}

export interface Staff {
  id: string
  full_name: string
  role: Role
}

export interface ColumnDef {
  key: string
  label_ru: string
  short_label_ru: string
  owner_role: Role
}

export interface BoardItem {
  status: ItemStatus
  note: string | null
  updated_at: string
  updated_by: string | null
}

export interface BoardRow {
  case_id: string
  bed_id: string | null
  initials: string
  room_id: string | null
  room_name: string | null
  bed_label: string | null
  status: CaseStatus
  procedure_label: string
  planned_surgery_date: string | null
  is_emergency: boolean
  treating_doctor_id: string
  treating_doctor_name: string
  ready: boolean
  blocking: string[]
  override_reason: string | null
  items: Record<string, BoardItem>
}

export interface Board {
  columns: ColumnDef[]
  rows: BoardRow[]
  generated_at: string
}

export interface CaseItem extends BoardItem {
  key: string
}

export interface CaseDetail {
  id: string
  status: CaseStatus
  patient: {
    full_name: string
    birth_date: string
    sex: string
    medical_record_number: string
  }
  bed_id: string | null
  room_name: string | null
  bed_label: string | null
  treating_doctor: Staff
  procedure_key: string
  procedure_label: string
  side: string | null
  planned_surgery_date: string | null
  planned_surgery_time: string | null
  anaesthesia_type: string | null
  anaesthesia_remarks: string | null
  is_emergency: boolean
  takes_anticoagulant: boolean
  admitted_at: string
  override_reason: string | null
  items: CaseItem[]
  readiness: { ready: boolean; blocking: string[] }
  can_edit: boolean
  available_transitions: CaseStatus[]
}

export interface Bed {
  id: string
  label: string
  is_active: boolean
}
export interface Room {
  id: string
  name: string
  floor: number
  position_x: number | null
  position_y: number | null
  beds: Bed[]
}
export interface Ward {
  id: string
  name: string
  rooms: Room[]
}

export interface Definitions {
  checklist: ColumnDef[]
  procedures: { id: string; label_ru: string }[]
}

export interface ConfigFile {
  name: string
  version: number
  requires_clinical_validation: boolean
}

export interface AuditRow {
  id: string
  created_at: string
  user_id: string | null
  action: string
  entity: string
  entity_id: string | null
  diff: Record<string, unknown> | null
  ip: string | null
}
export interface AuditPage {
  items: AuditRow[]
  next_cursor: string | null
}

export interface LabResult {
  id: string
  lab_code: string
  result_text: string
  collected_at: string
  valid_until: string | null
}

export interface DocumentProblem {
  code: string
  message: string
  key: string | null
}

export interface DocumentSummary {
  template_id: string
  title_ru: string
  status: 'awaiting_template' | 'not_generated' | 'generated' | 'outdated'
  can_generate: boolean
  problems: DocumentProblem[]
  generated_at: string | null
  is_outdated: boolean
}

export interface DocumentField {
  key: string
  section: string
  label: string
  emr_type: string
  critical: boolean
  display: 'value' | 'keep_emr' | 'calculate' | 'manual' | 'skip'
  value: string | null
  items: string[] | null
  icd: { code: string; text: string }[] | null
  hint: string | null
  missing: boolean
  copied: boolean
  locked?: boolean
}

export interface DocumentDetail extends DocumentSummary {
  changed_keys: string[]
  fields: DocumentField[]
  all_text: string
}

export interface StatusEvent {
  from_status: CaseStatus | null
  to_status: CaseStatus
  user_name: string | null
  reason: string | null
  is_override: boolean
  created_at: string
}

export interface Order {
  id: string
  case_id: string
  type: 'lab' | 'imaging' | 'consult' | 'other'
  item: string
  assignee_id: string
  assignee_name: string
  status: 'ordered' | 'in_progress' | 'result_available' | 'reviewed' | 'cancelled'
  linked_checklist_key: string | null
  created_at_round: boolean
  created_at: string
  case_label: string
  next_statuses: string[]
}

export interface OrderSet {
  key: string
  name_ru: string
  orders: { type: string; item: string }[]
}

export interface AppNotification {
  id: string
  event: string
  text: string
  case_id: string | null
  created_at: string
  read: boolean
}

export interface PostOpData {
  complaints: string
  pain_vas: number | null
  consciousness: string | null
  vitals: {
    bp: string | null
    pulse: number | null
    rr: number | null
    spo2: number | null
    temp: number | null
    cvp: number | null
  }
  wound: {
    dressing: string | null
    discharge: string | null
    redness: boolean
    swelling: boolean
    sutures: string | null
    dressing_changed: boolean
  }
  drain: { present: boolean; output_ml: number | null; removed: boolean }
  neurovascular: { pulsation: string | null; sensation: string | null; motor: string | null }
  calf_tenderness: boolean
  mobilization: { level: string | null; weight_bearing: string | null; physiotherapy: boolean }
  therapy: { antibiotic_day: number | null; vte_prophylaxis: boolean; analgesia: string }
  recommendations: string
  photo_key: string | null
}

export interface PostOpNote {
  generator: string
  general_condition: string
  local_status: string
  approved: boolean
  approved_at: string | null
  approved_by_name: string | null
}

export interface PostOpEntry {
  id: string
  case_id: string
  entered_at: string
  entry_date: string
  post_op_day: number
  data: PostOpData
  alerts: string[]
  note: PostOpNote | null
  has_photo: boolean
}

export interface TrendPoint {
  day: number
  date: string
  temp: number | null
  drain_ml: number | null
  pain: number | null
  discharge: string | null
  redness: boolean
  swelling: boolean
}

export interface PostOpList {
  entries: PostOpEntry[]
  trends: TrendPoint[]
  can_record: boolean
  can_edit: boolean
  photo_enabled: boolean
  today_entry_id: string | null
}

export interface TelegramLink {
  code: string
  expires_at: string
  command: string
}
