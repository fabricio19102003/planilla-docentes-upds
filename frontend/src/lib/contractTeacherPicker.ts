export interface PickerTeacher {
  ci: string
  full_name: string
}

const fold = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim()

/** Text shown for a teacher in the trigger and used as the option's accessible label. */
export function teacherOptionLabel(teacher: PickerTeacher): string {
  return `${teacher.full_name} — CI ${teacher.ci}`
}

/** Whether every word of the query appears in the teacher's name or CI, ignoring accents and case. */
export function matchesTeacher(teacher: PickerTeacher, query: string): boolean {
  const words = fold(query).split(' ').filter(Boolean)
  if (words.length === 0) return true
  const haystack = fold(`${teacher.full_name} ${teacher.ci}`)
  return words.every((word) => haystack.includes(word))
}

export function filterTeachers<T extends PickerTeacher>(teachers: readonly T[], query: string): T[] {
  return teachers.filter((teacher) => matchesTeacher(teacher, query))
}
