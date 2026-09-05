export const TEACHER_TYPES = ['EXTERNO', 'PERMANENTE', 'TITULAR'] as const

export type TeacherType = (typeof TEACHER_TYPES)[number]

export const TEACHER_TYPE_OPTIONS: ReadonlyArray<{ value: TeacherType; label: string }> = [
  { value: 'EXTERNO', label: 'Externo' },
  { value: 'PERMANENTE', label: 'Permanente' },
  { value: 'TITULAR', label: 'Titular' },
]

export function teacherTypeLabel(value: string | null | undefined): string {
  if (!value) return '—'
  const option = TEACHER_TYPE_OPTIONS.find((item) => item.value === value.toUpperCase())
  return option?.label ?? `Tipo desconocido (${value})`
}
