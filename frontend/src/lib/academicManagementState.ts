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
