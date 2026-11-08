import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  activeClassrooms,
  applyRoomsLabel,
  canApplyRooms,
  roomImportError,
  roomLabel,
  roomPreviewSections,
  roomSectionTabs,
} from '../src/lib/designationRoomImport.ts'
import {
  formToPayload,
  hasOnlyClassroomChange,
  itemToForm,
} from '../src/lib/designationAdminState.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const room = (id, code, name) => ({ id, code, name })
const matched = (id, changed, current, next) => ({
  designation_id: id, teacher_ci: `T${id}`, teacher_name: `DOCENTE ${id}`, subject: 'ANATOMIA', semester: 'PRIMERO',
  group_code: 'M-1', current_classroom: current, new_classroom: next, changed,
})

const preview = {
  academic_period: 'II/2026',
  matched: [
    matched(1, true, null, room(5, 'A-20', 'Aula 20')),
    matched(2, true, room(4, 'A-1', 'Aula 1'), room(5, 'A-20', 'Aula 20')),
    matched(3, false, room(5, 'A-20', 'Aula 20'), room(5, 'A-20', 'Aula 20')),
  ],
  unknown_rooms: [{ row: 9, teacher: 'X', subject: 'FISIO', group_code: 'T-1', aula: 'Z9', reason: 'El aula no existe en el catálogo.' }],
  unmatched_rows: [{ row: 11, teacher: 'Y', subject: 'QUIMICA', semester: 'PRIMERO', group_code: 'N-1', aula: '3' }],
  designations_without_row: [
    { designation_id: 8, teacher_name: 'W', subject: 'BIO', group_code: 'M-2' },
    { designation_id: 9, teacher_name: 'V', subject: 'BIO', group_code: 'M-3' },
  ],
  summary: { matched: 3, changed: 2, unknown_rooms: 1, unmatched_rows: 1, designations_without_row: 2 },
  preview_digest: 'abc',
}

test('preview rows are grouped into the sections the admin reviews', () => {
  const sections = roomPreviewSections(preview)
  assert.deepEqual(sections.assign.map((row) => row.designation_id), [1, 2])
  assert.deepEqual(sections.unchanged.map((row) => row.designation_id), [3])
  assert.equal(sections.unknown.length, 1)
  assert.equal(sections.unmatched.length, 1)
  assert.equal(sections.withoutRow.length, 2)
})

test('section tabs are named in plain words and carry their counts', () => {
  assert.deepEqual(roomSectionTabs(preview), [
    { key: 'assign', label: 'Se asignan', count: 2 },
    { key: 'unknown', label: 'Aulas no reconocidas', count: 1 },
    { key: 'unmatched', label: 'Filas sin designación', count: 1 },
    { key: 'withoutRow', label: 'Designaciones sin fila', count: 2 },
  ])
})

test('apply button states the number of changes and is disabled when nothing changes', () => {
  assert.equal(applyRoomsLabel(preview), 'Aplicar 2 cambios')
  assert.equal(canApplyRooms(preview), true)
  const one = { ...preview, matched: [preview.matched[0], preview.matched[2]] }
  assert.equal(applyRoomsLabel(one), 'Aplicar 1 cambio')
  const none = { ...preview, matched: [preview.matched[2]] }
  assert.equal(applyRoomsLabel(none), 'Aplicar 0 cambios')
  assert.equal(canApplyRooms(none), false)
})

test('a missing classroom reads "Sin aula" and only active classrooms can be picked', () => {
  assert.equal(roomLabel(null), 'Sin aula')
  assert.equal(roomLabel(undefined), 'Sin aula')
  assert.equal(roomLabel(room(1, 'A-1', 'Aula 1')), 'Aula 1')
  const catalog = [
    { id: 2, code: 'B', name: 'Aula B', active: true },
    { id: 1, code: 'A-1', name: 'Aula 1', active: true },
    { id: 3, code: 'X', name: 'Cerrada', active: false },
  ]
  assert.deepEqual(activeClassrooms(catalog).map((item) => item.id), [1, 2])
})

test('a 409 means the preview changed; any other answer keeps the server message', () => {
  const failure = (status, detail) => ({ response: { status, data: { detail } } })
  assert.deepEqual(roomImportError(failure(409, 'La vista previa cambió; volvé a generarla.'), 'x'),
    { stale: true, message: 'La vista previa cambió; volvé a generarla.' })
  assert.deepEqual(roomImportError(failure(422, 'El Excel debe tener la hoja DOCENTES TEORICOS.'), 'x'),
    { stale: false, message: 'El Excel debe tener la hoja DOCENTES TEORICOS.' })
  assert.deepEqual(roomImportError(new Error('network'), 'No se pudo leer el archivo.'),
    { stale: false, message: 'No se pudo leer el archivo.' })
})

const item = {
  id: 7, teacher_ci: 'T1', teacher_name: 'ANA', subject: 'ANATOMIA', semester: 'PRIMERO', group_code: 'M-1',
  academic_period: 'II/2026', designation_type: 'regular',
  schedule_json: [{ dia: 'lunes', hora_inicio: '08:00', hora_fin: '09:30' }],
  semester_hours: 100, monthly_hours: 20, contract_start_date: '2026-08-10', contract_end_date: null,
  classroom_id: 4, classroom: room(4, 'A-1', 'Aula 1'),
}

test('the form carries the classroom and the payload sends it, null when cleared', () => {
  const form = itemToForm(item)
  assert.equal(form.classroomId, 4)
  assert.equal(formToPayload(form).classroom_id, 4)
  assert.equal(formToPayload({ ...form, classroomId: null }).classroom_id, null)
  assert.equal(itemToForm({ ...item, classroom_id: null, classroom: null }).classroomId, null)
  assert.equal(itemToForm({ ...item, classroom_id: undefined }).classroomId, null)
})

test('a payroll-locked edit only changes the classroom, keeping every other value', () => {
  const form = itemToForm(item)
  assert.equal(hasOnlyClassroomChange(form, item), false)
  assert.equal(hasOnlyClassroomChange({ ...form, classroomId: null }, item), true)
  assert.equal(hasOnlyClassroomChange({ ...form, classroomId: 9 }, item), true)
  assert.equal(hasOnlyClassroomChange({ ...form, classroomId: 9, subject: 'OTRA' }, item), false)
})

test('Designaciones wires the room importer next to the existing import', () => {
  const page = read('src/pages/DesignationsPage.tsx')
  assert.ok(page.includes('Importar aulas'))
  assert.ok(page.includes('DesignationRoomImportWizard'))
  const wizard = read('src/components/designations/DesignationRoomImportWizard.tsx')
  for (const text of ['Se asignan', 'Sin cambios', 'Aulas no reconocidas', 'applyRoomsLabel', 'preview_digest', 'previewDigest', 'Volver a generar la vista previa']) {
    assert.ok(wizard.includes(text) || read('src/lib/designationRoomImport.ts').includes(text), text)
  }
  const hooks = read('src/api/hooks/useDesignationAdmin.ts')
  for (const fragment of ['useDesignationRoomPreview', 'useApplyDesignationRooms', '/rooms/preview', '/rooms/apply', 'preview_digest']) {
    assert.ok(hooks.includes(fragment), fragment)
  }
})

test('the list and its mobile card show the classroom or "Sin aula"', () => {
  const list = read('src/components/designations/DesignationListView.tsx')
  assert.ok(list.includes('<TableHead className="px-4">Aula</TableHead>'))
  assert.ok(list.includes('ClassroomCell'))
  assert.ok(list.includes('roomLabel'))
  assert.ok(read('src/components/designations/DesignationMobileCards.tsx').includes('ClassroomCell'))
})

test('the form has the Aula field outside the payroll lock and clears with null', () => {
  const form = read('src/components/designations/DesignationFormDialog.tsx')
  assert.ok(form.includes('Aula'))
  assert.ok(form.includes('ClassroomCombobox'))
  assert.ok(form.includes('hasOnlyClassroomChange'))
  assert.ok(!form.includes('classroomOnlyPayload'))
  const picker = read('src/components/designations/ClassroomCombobox.tsx')
  assert.ok(picker.includes('Combobox'))
  assert.ok(picker.includes('Sin aula'))
})

test('a classroom-only change goes through the dedicated endpoint, every other edit through the generic PUT', () => {
  const hooks = read('src/api/hooks/useDesignationAdmin.ts')
  assert.ok(hooks.includes('export function useSetDesignationClassroom'))
  assert.ok(hooks.includes('`${root}/${id}/classroom`'))
  assert.ok(hooks.includes('{ classroom_id: classroomId }'))
  const form = read('src/components/designations/DesignationFormDialog.tsx')
  assert.ok(form.includes('useSetDesignationClassroom'))
  const save = form.slice(form.indexOf('const save = () => {'), form.indexOf('return (\n    <Dialog'))
  const dedicated = save.indexOf('setClassroom.mutate({ id: item.id, classroomId: form.classroomId }')
  const guard = save.indexOf('if (editing && hasOnlyClassroomChange(form, item))')
  const validation = save.indexOf('formErrors(form)')
  const generic = save.indexOf('update.mutate({ id: item.id, body }')
  assert.ok(guard >= 0 && dedicated > guard, 'classroom-only change must call the dedicated hook')
  assert.ok(validation > dedicated, 'the dedicated save happens before the full-form validation')
  assert.ok(generic > validation, 'other edits keep using the generic PUT')
  assert.ok(save.includes('if (editBlocked) return'), 'a locked form with other changes sends nothing')
})
