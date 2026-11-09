import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  filterTeachers,
  matchesTeacher,
  teacherOptionLabel,
} from '../src/lib/contractTeacherPicker.ts'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const card = readFileSync(resolve(root, 'src/components/contracts/IndividualContractCard.tsx'), 'utf8')

const jose = { ci: '7654321', full_name: 'José Ángel Pérez Quispe' }
const maria = { ci: '1234567-1A', full_name: 'María Fernández Rojas' }
const teachers = [jose, maria]

test('an empty or blank query matches every teacher', () => {
  assert.equal(matchesTeacher(jose, ''), true)
  assert.equal(matchesTeacher(jose, '   '), true)
  assert.deepEqual(filterTeachers(teachers, ''), teachers)
})

test('matching ignores accents and case in either direction', () => {
  assert.equal(matchesTeacher(jose, 'jose'), true)
  assert.equal(matchesTeacher(jose, 'JOSÉ'), true)
  assert.equal(matchesTeacher(jose, 'angel perez'), true)
  assert.equal(matchesTeacher(maria, 'FERNANDEZ'), true)
  assert.equal(matchesTeacher(maria, 'maria'), true)
})

test('a fragment of the CI matches', () => {
  assert.deepEqual(filterTeachers(teachers, '5432'), [jose])
  assert.deepEqual(filterTeachers(teachers, '1234567-1a'), [maria])
  assert.deepEqual(filterTeachers(teachers, '567'), [maria])
})

test('several words match in any order and across name and CI', () => {
  assert.equal(matchesTeacher(jose, 'quispe jose'), true)
  assert.equal(matchesTeacher(jose, 'perez   angel'), true)
  assert.equal(matchesTeacher(jose, '7654 jose'), true)
  assert.equal(matchesTeacher(jose, 'jose fernandez'), false)
})

test('non-matching queries return nothing', () => {
  assert.equal(matchesTeacher(jose, 'zzz'), false)
  assert.deepEqual(filterTeachers(teachers, 'zzz'), [])
})

test('option label shows the full name and the CI', () => {
  assert.equal(teacherOptionLabel(jose), 'José Ángel Pérez Quispe — CI 7654321')
})

test('the individual card uses the coss combobox instead of the generic select', () => {
  assert.match(card, /from '@\/components\/ui\/combobox'/)
  assert.doesNotMatch(card, /@\/components\/ui\/select/)
  assert.doesNotMatch(card, /<Select\b/)
  assert.match(card, /from '@\/lib\/contractTeacherPicker'/)
  assert.match(card, /Ningún docente coincide con la búsqueda\./)
  assert.match(card, /<FieldLabel id="individual-contract-teacher-label" htmlFor="individual-contract-teacher">Docente<\/FieldLabel>/)
  assert.match(card, /aria-labelledby="individual-contract-teacher-label individual-contract-teacher"/)
})

test('the card shows a polite loading state while the terms load', () => {
  assert.match(card, /from '@\/components\/ui\/skeleton'/)
  assert.match(card, /Calculando la carga del docente…/)
  assert.match(card, /aria-live="polite"/)
  assert.match(card, /terms\.isLoading|terms\.isFetching/)
})
