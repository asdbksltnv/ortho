import type { Role } from '../api/types'

/** UI hints only. The backend enforces every permission. Mirrors app/domain/permissions.py. */
export function canEditItem(
  role: Role,
  key: string,
  ownerRole: Role,
  isTreatingDoctor: boolean,
): boolean {
  if (role === 'head_of_department') return true
  if (role === 'anaesthesiologist') return key === 'anaesthesia'
  if (role === 'nurse' || role === 'head_nurse') {
    return ownerRole === 'nurse' || key === 'consent_surgical'
  }
  if (role === 'doctor') return isTreatingDoctor && key !== 'anaesthesia'
  return false
}

export const isClinical = (role: Role) => role !== 'admin'
export const canCreateCase = (role: Role) => role === 'doctor' || role === 'head_of_department'
export const canWriteRecords = (role: Role) =>
  role === 'doctor' || role === 'head_of_department' || role === 'nurse' || role === 'head_nurse'
export const canReadAudit = (role: Role) => role === 'admin' || role === 'head_of_department'
