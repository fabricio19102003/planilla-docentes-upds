/** Types and pure helpers for curriculum, students and the legacy academic history import. */

import type { PortalAccount } from '@/lib/reenrollmentState'

export type RecordStatus = 'aprobado' | 'reprobado' | 'retirado' | 'pendiente'
export type BadgeVariant = 'success' | 'error' | 'outline' | 'info'

export interface CurriculumSlot {
  id: number
  subject_id: number | null
  code: string | null
  name: string
  theory_hours: number
  practice_hours: number
  credits: number
  is_elective: boolean
}

export interface CurriculumPlan {
  id: number
  code: string
  name: string
  program_code: string
  total_semesters: number
  semesters: { semester: number; subjects: CurriculumSlot[] }[]
}

export interface CurriculumPlanSummary {
  id: number
  code: string
  name: string
  program_code: string
  total_semesters: number
  subject_count: number
}

export interface AcademicTerm {
  id: number
  code: string
  name: string
  year: number
  kind: 'I' | 'II' | 'INV' | 'VER'
  is_intensive: boolean
  record_count: number
}

export interface StudentListItem {
  id: number
  document_number: string
  full_name: string
  nationality: string | null
  is_foreign: boolean
  legacy_enrollment_status: string | null
  last_term: string | null
  record_count: number
}

export interface StudentList {
  items: StudentListItem[]
  total: number
  page: number
  page_size: number
}

export interface StudentRecord {
  legacy_registration_id: number
  subject_code: string
  subject_name: string
  group_code: string | null
  shift: string | null
  teacher_name: string | null
  status: RecordStatus
  grade: number | null
  in_curriculum: boolean
}

export interface StudentDetail {
  student: {
    id: number
    document_number: string
    document_type: string
    first_names: string
    last_names: string
    full_name: string
    birth_date: string | null
    gender: string | null
    phone: string | null
    personal_email: string | null
    academic_email: string | null
    birth_country: string | null
    nationality: string | null
    is_foreign: boolean
    school: string | null
    address: string | null
    legacy_enrollment_status: string | null
    curriculum_plan: string | null
  }
  history: {
    term: Omit<AcademicTerm, 'id' | 'record_count'>
    records: StudentRecord[]
  }[]
  /** Student portal account; only the admin student detail includes it. */
  account?: PortalAccount | null
}

export interface ImportIssue {
  level: 'error' | 'warning'
  row: number | null
  rows: number
  message: string
}

export interface ImportCounts {
  rows: number
  valid_rows: number
  error_rows: number
  students_new: number
  students_updated: number
  students_unchanged: number
  records_new: number
  records_updated: number
  records_unchanged: number
  terms_new: number
  subjects_new: number
  teachers_linked: number
  warnings: number
}

export interface ImportPreview {
  file_name: string
  file_sha256: string
  counts: ImportCounts
  terms: string[]
  issues: ImportIssue[]
}

export interface ImportResult extends ImportPreview {
  import_id: number
}

export interface ImportReceipt {
  id: number
  file_name: string
  file_sha256: string
  counts: ImportCounts
  terms: string[]
  issue_count: number
  actor_name: string | null
  created_at: string
}

export type NationalityFilter = 'all' | 'national' | 'foreign'

export interface StudentFilters {
  search: string
  status: string
  nationality: NationalityFilter
  page: number
}

export const STUDENT_PAGE_SIZE = 25
export const LEGACY_ENROLLMENT_STATUSES = ['Nuevo', 'Antiguo', 'Reincorporado', 'Abandono', 'Desertor']

const STATUSES: Record<RecordStatus, { label: string; variant: BadgeVariant }> = {
  aprobado: { label: 'Aprobado', variant: 'success' },
  reprobado: { label: 'Reprobado', variant: 'error' },
  retirado: { label: 'Retirado', variant: 'outline' },
  pendiente: { label: 'En curso', variant: 'info' },
}

export function recordStatus(status: RecordStatus) {
  return STATUSES[status]
}

export function formatGrade(grade: number | null): string {
  return grade === null ? '—' : String(grade)
}

/** Average of graded approved/failed subjects; withdrawn and in-progress subjects do not count. */
export function termAverage(records: Pick<StudentRecord, 'status' | 'grade'>[]): number | null {
  const grades = records
    .filter((record) => (record.status === 'aprobado' || record.status === 'reprobado') && record.grade !== null)
    .map((record) => record.grade as number)
  if (!grades.length) return null
  return Math.round((grades.reduce((sum, grade) => sum + grade, 0) / grades.length) * 100) / 100
}

export function studentQueryParams(filters: StudentFilters) {
  const params: Record<string, string | number | boolean> = { page: filters.page, page_size: STUDENT_PAGE_SIZE }
  if (filters.search.trim()) params.search = filters.search.trim()
  if (filters.status) params.status = filters.status
  if (filters.nationality !== 'all') params.foreign = filters.nationality === 'foreign'
  return params
}

export function splitIssues(issues: ImportIssue[]) {
  return {
    errors: issues.filter((issue) => issue.level === 'error'),
    warnings: issues.filter((issue) => issue.level === 'warning'),
  }
}

const COUNT_LABELS: [keyof ImportCounts, string][] = [
  ['rows', 'Filas leídas'],
  ['error_rows', 'Filas con error (se omiten)'],
  ['students_new', 'Estudiantes nuevos'],
  ['students_updated', 'Estudiantes actualizados'],
  ['students_unchanged', 'Estudiantes sin cambios'],
  ['records_new', 'Materias cursadas nuevas'],
  ['records_updated', 'Materias cursadas actualizadas'],
  ['records_unchanged', 'Materias cursadas sin cambios'],
  ['terms_new', 'Períodos nuevos'],
  ['subjects_new', 'Materias nuevas en el catálogo'],
  ['teachers_linked', 'Registros vinculados a un docente de SIPAD'],
]

export function importCountRows(counts: ImportCounts) {
  return COUNT_LABELS.map(([key, label]) => ({ label, value: counts[key] }))
}

/** Gzip the export in the browser: the proxy only accepts uploads up to 25 MB. */
export async function gzipCsv(file: File): Promise<File> {
  const stream = file.stream().pipeThrough(new CompressionStream('gzip'))
  const blob = await new Response(stream).blob()
  return new File([blob], `${file.name}.gz`, { type: 'application/gzip' })
}
