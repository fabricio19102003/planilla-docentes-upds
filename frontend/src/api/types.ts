export interface ScheduleSlot {
  day?: string
  dia?: string
  start_time?: string
  end_time?: string
  hora_inicio?: string
  hora_fin?: string
  hours_academicas?: number
  horas_academicas?: number
  [key: string]: unknown
}

export interface Designation {
  id: number
  teacher_ci: string
  subject: string
  semester: string
  group_code: string
  schedule_json: ScheduleSlot[]
  semester_hours: number | null
  monthly_hours: number | null
  weekly_hours: number | null
  weekly_hours_calculated: number | null
  schedule_raw: string | null
  created_at: string
}

export interface Teacher {
  ci: string
  full_name: string
  email: string | null
  phone: string | null
  gender: string | null
  external_permanent: string | null
  academic_level: string | null
  profession: string | null
  specialty: string | null
  bank: string | null
  account_number: string | null
  sap_code: string | null
  invoice_retention: string | null
  created_at: string
  updated_at: string | null
}

export interface TeacherAttendanceSummary {
  total_records: number
  attended: number
  late: number
  absent: number
  no_exit: number
  total_academic_hours: number
}

export interface TeacherWithDesignations extends Teacher {
  designations: Designation[]
}

export interface TeacherDetail extends Teacher {
  designations: Designation[]
  attendance_summary: TeacherAttendanceSummary
}

export interface BiometricUpload {
  id: number
  filename: string
  upload_date: string
  month: number
  year: number
  total_records: number
  total_teachers: number
  status: string
}

export interface BiometricRecord {
  id: number
  upload_id: number
  teacher_ci: string
  teacher_name: string | null
  date: string
  entry_time: string | null
  exit_time: string | null
  worked_minutes: number | null
  shift: string | null
  created_at: string
}

export interface BiometricUploadResult {
  upload_id: number
  filename: string
  teachers_found: number
  records_count: number
  warnings: string[]
}

export interface AttendanceRecord {
  id: number
  teacher_ci: string
  designation_id: number
  date: string
  scheduled_start: string
  scheduled_end: string
  actual_entry: string | null
  actual_exit: string | null
  status: string
  academic_hours: number
  late_minutes: number
  observation: string | null
  biometric_record_id: number | null
  month: number
  year: number
  created_at: string
}

export interface AttendanceWithDetails extends AttendanceRecord {
  teacher_name: string | null
  subject: string | null
  group_code: string | null
  semester: string | null
}

export interface AttendanceSummary {
  total_teachers: number
  total_slots: number
  attended: number
  late: number
  absent: number
  no_exit: number
  attendance_rate: number
  total_academic_hours: number
  observations: Observation[]
}

export interface AttendanceProcessResponse {
  total_records: number
  attended: number
  late: number
  absent: number
  no_exit: number
  attendance_rate: number
  observations_count: number
  warnings: string[]
}

export interface Observation {
  id: number
  teacher_ci: string
  teacher_name: string | null
  designation_id: number
  subject: string | null
  group_code: string | null
  date: string
  scheduled_start: string
  scheduled_end: string
  status: string
  late_minutes: number
  observation: string | null
}

export interface PlanillaOutput {
  id: number
  month: number
  year: number
  generated_at: string
  file_path: string | null
  total_teachers: number
  total_hours: number
  total_payment: string
  status: string
}

export interface PlanillaGenerateResponse {
  planilla_id: number
  month: number
  year: number
  file_path: string | null
  total_teachers: number
  total_hours: number
  total_payment: string
  warnings: string[]
}

export interface DashboardSummary {
  recent_uploads: BiometricUpload[]
  latest_attendance_summary: AttendanceSummary | null
  teacher_count: number
  designation_count: number
}

export interface DesignationUploadResponse {
  teachers_created: number
  teachers_reused: number
  designations_loaded: number
  skipped: number
  warnings: string[]
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

export interface AttendanceFilters {
  month: number
  year: number
  page?: number
  perPage?: number
  teacherCi?: string
  status?: string
}

export interface ProcessAttendancePayload {
  upload_id: number
  month: number
  year: number
}

export interface GeneratePlanillaPayload {
  month: number
  year: number
  payment_overrides: Record<string, number>
}

export interface UploadBiometricPayload {
  file: File
  month: number
  year: number
  onProgress?: (progress: number) => void
}

export interface UploadDesignationsPayload {
  file: File
  onProgress?: (progress: number) => void
}
