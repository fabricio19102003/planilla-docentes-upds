import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import { publicationDiffItems } from '../src/lib/schedulePlannerState.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const page = read('src/pages/SchedulePlannerPage.tsx')
const hooks = read('src/api/hooks/useSchedulePlanner.ts')
const types = read('src/api/types.ts')

test('maps publication differences without hiding zero values', () => {
  assert.deepEqual(
    publicationDiffItems({
      added_blocks: 2,
      removed_blocks: 1,
      changed_blocks: 0,
      teacher_replacements: 3,
      workload_changes: [],
    }).map(({ key, label, value }) => ({ key, label, value })),
    [
      { key: 'added', label: 'Añadidos', value: 2 },
      { key: 'removed', label: 'Retirados', value: 1 },
      { key: 'changed', label: 'Cambiados', value: 0 },
      { key: 'teachers', label: 'Reemplazos', value: 3 },
    ],
  )
})

test('defines digest-bound publication and immutable snapshot contracts', () => {
  for (const contract of [
    'SchedulePublicationPreview',
    'SchedulePublicationBlocker',
    'SchedulePublicationDiff',
    'AcademicSchedulePublication',
    'PublishedScheduleBlock',
    'PublishedScheduleAssignment',
  ]) assert.match(types, new RegExp(`interface ${contract}`))
  assert.match(types, /status: 'draft' \| 'archived' \| 'published'/)
})

test('uses preview, digest-bound publish, history, and clone APIs', () => {
  assert.match(hooks, /publication-preview/)
  assert.match(hooks, /preview_digest: digest/)
  assert.match(hooks, /schedule-publications/)
  assert.match(hooks, /\/clone/)
  assert.match(hooks, /invalidateQueries\(\{ queryKey: \['academic-management', 'schedule-publications'\]/)
})

test('renders accessible blocker, error, focus, history, clone, and warning states', () => {
  assert.match(page, /Revisar publicación completa/)
  assert.match(page, /Publicación bloqueada/)
  assert.match(page, /Historial de publicaciones/)
  assert.match(page, /Clonar como borrador editable/)
  assert.match(page, /Publicado e inmutable/)
  assert.match(page, /No despliegue esta publicación sola en producción/)
  assert.match(page, /role="alert"/)
  assert.match(page, /role="status"/)
  assert.match(page, /aria-describedby=/)
  assert.match(page, /publishConfirmRef\.current\?\.focus\(\)/)
  assert.doesNotMatch(page, /toast\s*\(/)
})
