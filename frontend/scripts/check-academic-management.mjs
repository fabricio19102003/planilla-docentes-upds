import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  academicCollectionRequest,
  availabilityPayload,
  normalizeClassroomResources,
  optionalPositiveInteger,
  teacherAvailabilityRequest,
  teacherSearchRequest,
} from '../src/lib/academicManagementState.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const app = read('src/App.tsx')
const sidebar = read('src/components/layout/Sidebar.tsx')
const page = read('src/pages/AcademicManagementPage.tsx')
const hooks = read('src/api/hooks/useAcademicManagement.ts')
const types = read('src/api/types.ts')
const state = read('src/lib/academicManagementState.ts')

test('registers the protected route and admin navigation entry', () => {
  assert.match(app, /path="academic-management"/)
  assert.match(app, /<AcademicManagementPage/)
  assert.match(sidebar, /to: '\/academic-management'/)
  assert.match(sidebar, /label: 'Gestión académica'/)
})

test('covers all six academic management sections and API resources', () => {
  for (const [value, resource] of [
    ['programs', 'programs'], ['subjects', 'subjects'], ['offerings', 'offerings'],
    ['groups', 'groups'], ['classrooms', 'classrooms'], ['availability', 'availability'],
  ]) {
    assert.match(page, new RegExp(`value="${value}"`))
    assert.match(hooks, new RegExp(`'${resource}'`))
  }
  assert.match(hooks, /\/admin\/academic-management/)
  assert.match(types, /interface TeacherAvailability/)
})

test('builds bounded collection, availability, and teacher-search query contracts', () => {
  assert.deepEqual(academicCollectionRequest('programs'), {
    queryKey: ['academic-management', 'programs'],
    url: '/admin/academic-management/programs',
  })
  assert.deepEqual(teacherAvailabilityRequest('CI-1', 'II/2026'), {
    queryKey: ['academic-management', 'availability', 'CI-1', 'II/2026'],
    url: '/admin/academic-management/availability',
    params: { teacher_ci: 'CI-1', academic_period: 'II/2026' },
    enabled: true,
  })
  assert.equal(teacherAvailabilityRequest('', 'II/2026').enabled, false)
  assert.deepEqual(teacherSearchRequest('Ana', 3).params, {
    search: 'Ana', page: 3, per_page: 20,
  })
  assert.match(hooks, /useAcademicTeacherSearch/)
  assert.match(hooks, /placeholderData: \(previous\) => previous/)
})

test('normalizes form state and constructs availability payloads', () => {
  assert.deepEqual(normalizeClassroomResources(' Proyector, pizarra, , TV '), ['Proyector', 'pizarra', 'TV'])
  assert.equal(optionalPositiveInteger(''), null)
  assert.equal(optionalPositiveInteger('30'), 30)
  assert.deepEqual(
    availabilityPayload('CI-2', 'I/2027', { weekday: 'friday', start_time: '08:00', end_time: '10:00' }),
    { teacher_ci: 'CI-2', academic_period: 'I/2027', weekday: 'friday', start_time: '08:00', end_time: '10:00' },
  )
})

test('keeps forms labeled and exposes field-linked non-toast errors', () => {
  assert.match(page, /<Label htmlFor=/)
  assert.match(page, /aria-invalid=/)
  assert.match(page, /aria-describedby=/)
  assert.match(page, /role="alert"/)
  assert.match(page, /aria-live="polite"/)
  assert.match(page, /role="status"/)
  assert.match(page, /query\.isError/)
  assert.match(page, /teachers\.isError/)
  assert.match(page, /availability\.isError/)
  assert.match(page, /Reintentar/)
  assert.doesNotMatch(page, /toast\s*\(/)
})

test('surfaces overlap failures and preserves availability contract fields', () => {
  for (const field of ['teacher_ci', 'academic_period', 'weekday', 'start_time', 'end_time']) {
    assert.match(`${page}\n${state}`, new RegExp(field))
  }
  assert.match(page, /setError\(errorMessage\(caught\)\)/)
  assert.match(page, /availability-error/)
  assert.match(page, /Buscar docente/)
  assert.match(page, /teacherPage/)
})
