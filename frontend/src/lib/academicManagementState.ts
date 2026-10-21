export type AcademicCollectionResource = 'programs' | 'subjects' | 'offerings' | 'groups' | 'classrooms'

export const ACADEMIC_MANAGEMENT_ROOT = '/admin/academic-management'
export const TEACHER_SEARCH_PAGE_SIZE = 20

export function academicCollectionRequest(resource: AcademicCollectionResource) {
  return {
    queryKey: ['academic-management', resource] as const,
    url: `${ACADEMIC_MANAGEMENT_ROOT}/${resource}`,
  }
}

export function teacherAvailabilityRequest(teacherCi: string, academicPeriod: string) {
  return {
    queryKey: ['academic-management', 'availability', teacherCi, academicPeriod] as const,
    url: `${ACADEMIC_MANAGEMENT_ROOT}/availability`,
    params: { teacher_ci: teacherCi, academic_period: academicPeriod },
    enabled: Boolean(teacherCi && academicPeriod),
  }
}

export function teacherSearchRequest(search: string, page: number) {
  return {
    queryKey: ['teachers', { search: search || undefined, page, perPage: TEACHER_SEARCH_PAGE_SIZE }] as const,
    params: {
      search: search || undefined,
      page,
      per_page: TEACHER_SEARCH_PAGE_SIZE,
    },
  }
}

export function normalizeClassroomResources(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

export function optionalPositiveInteger(value: string): number | null {
  return value === '' ? null : Number(value)
}

export function availabilityPayload(
  teacherCi: string,
  academicPeriod: string,
  form: { weekday: string; start_time: string; end_time: string },
) {
  return {
    teacher_ci: teacherCi,
    academic_period: academicPeriod,
    weekday: form.weekday,
    start_time: form.start_time,
    end_time: form.end_time,
  }
}

const foldText = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim()

/** Accent- and case-insensitive match on code or name; a blank query matches everything. */
export function matchesCatalogSearch(item: { code: string; name?: string }, query: string): boolean {
  const needle = foldText(query)
  if (!needle) return true
  return foldText(`${item.code} ${item.name ?? ''}`).includes(needle)
}

interface SubjectLike { id: number; code: string; name: string }
interface OfferingLike { subject_id: number; academic_period: string; semester: number; theory_hours: number; practice_hours: number; active: boolean }

export interface SubjectSemesterSection<S extends SubjectLike, O extends OfferingLike> {
  semester: number | null
  rows: Array<{ subject: S; offering: O | null }>
}

/** Subjects grouped by the semester of their offerings in the period; subjects without one go last. */
export function groupSubjectsBySemester<S extends SubjectLike, O extends OfferingLike>(
  subjects: S[], offerings: O[], period: string,
): SubjectSemesterSection<S, O>[] {
  const sections = new Map<number | null, SubjectSemesterSection<S, O>>()
  const add = (semester: number | null, subject: S, offering: O | null) => {
    const section = sections.get(semester) ?? { semester, rows: [] }
    section.rows.push({ subject, offering })
    sections.set(semester, section)
  }
  for (const subject of subjects) {
    const own = offerings.filter((item) => item.subject_id === subject.id && item.academic_period === period && item.active)
    if (!own.length) add(null, subject, null)
    for (const offering of own) add(offering.semester, subject, offering)
  }
  for (const section of sections.values()) section.rows.sort((a, b) => a.subject.code.localeCompare(b.subject.code))
  return [...sections.values()].sort((a, b) => (a.semester === null ? 1 : 0) - (b.semester === null ? 1 : 0)
    || (a.semester ?? 0) - (b.semester ?? 0))
}

const SHIFT_ORDER: Record<string, number> = { M: 0, T: 1, N: 2 }

/** Shift (M, T, N, then others) and number, accepting catalog codes like M-01. */
const groupKey = (code: string) => {
  const match = /^([A-Za-z]+)-?0*(\d+)$/.exec(code.trim())
  const shift = match ? SHIFT_ORDER[match[1].toUpperCase()] : undefined
  return shift === undefined ? [3, 0, code] as const : [shift, Number(match![2]), code] as const
}

/** Groups of the period by semester, in shift order M, T, N, then others (M-2 before M-10). */
export function groupGroupsBySemester<G extends { academic_period: string; semester: number; code: string }>(
  groups: G[], period: string,
): Array<{ semester: number; rows: G[] }> {
  const sections = new Map<number, G[]>()
  for (const group of groups.filter((item) => item.academic_period === period)) {
    sections.set(group.semester, [...(sections.get(group.semester) ?? []), group])
  }
  return [...sections.entries()].sort(([a], [b]) => a - b).map(([semester, rows]) => ({
    semester,
    rows: rows.sort((a, b) => {
      const [shiftA, numberA, codeA] = groupKey(a.code)
      const [shiftB, numberB, codeB] = groupKey(b.code)
      return shiftA - shiftB || numberA - numberB || codeA.localeCompare(codeB)
    }),
  }))
}
