import assert from 'node:assert/strict'
import test from 'node:test'

import {
  MAX_NAME_LENGTH,
  MAX_NOTES_LENGTH,
  completeBlockReason,
  documentBadge,
  documentFormProblem,
  documentPayload,
  formatExpiry,
  inboxRegularizadoBadge,
  movePosition,
  pendingLabels,
  regularizadoBadge,
  typeNameProblem,
} from '../src/lib/migrationDocumentsState.ts'

const status = (patch = {}) => ({ applies: true, regularizado: false, missing: [], expired: [], documents: [], ...patch })

test('document states have a Spanish badge', () => {
  assert.deepEqual(documentBadge('present'), { label: 'Presentado', variant: 'success' })
  assert.deepEqual(documentBadge('missing'), { label: 'Falta', variant: 'error' })
  assert.deepEqual(documentBadge('expired'), { label: 'Vencido', variant: 'warning' })
})

test('the regularizado badge only exists for foreign students', () => {
  assert.deepEqual(regularizadoBadge(status({ regularizado: true })), { label: 'Regularizado', variant: 'success' })
  assert.deepEqual(regularizadoBadge(status()), { label: 'No regularizado', variant: 'error' })
  assert.equal(regularizadoBadge(status({ applies: false, regularizado: true })), null)
  assert.deepEqual(inboxRegularizadoBadge(true), { label: 'Regularizado', variant: 'success' })
  assert.deepEqual(inboxRegularizadoBadge(false), { label: 'No regularizado', variant: 'error' })
  assert.equal(inboxRegularizadoBadge(null), null)
})

test('expiry dates are shown as dd/mm/yyyy without time zone shifts', () => {
  assert.equal(formatExpiry('2026-12-09'), '09/12/2026')
  assert.equal(formatExpiry('2027-01-01'), '01/01/2027')
  assert.equal(formatExpiry(null), '—')
})

test('pending documents list the missing ones and the expired ones with their date', () => {
  assert.deepEqual(pendingLabels(status({
    missing: ['Pasaporte'], expired: [{ name: 'Visa', expires_on: '2026-12-09' }],
  })), ['Pasaporte', 'Visa (vencido el 09/12/2026)'])
  assert.deepEqual(pendingLabels(status({ regularizado: true })), [])
})

test('completing is blocked with the reason only when a foreign student is not regularizado', () => {
  const blocked = status({ missing: ['Pasaporte'], expired: [{ name: 'Visa', expires_on: '2026-12-09' }] })
  assert.equal(
    completeBlockReason(blocked),
    'Documentos migratorios pendientes: Pasaporte, Visa (vencido el 09/12/2026)',
  )
  assert.equal(completeBlockReason(status({ regularizado: true })), null)
  assert.equal(completeBlockReason(status({ applies: false, regularizado: true })), null)
  assert.equal(completeBlockReason(undefined), null)
})

test('document names are required, trimmed and at most 120 characters', () => {
  assert.equal(MAX_NAME_LENGTH, 120)
  assert.equal(typeNameProblem(''), 'El nombre del documento es obligatorio')
  assert.equal(typeNameProblem('   '), 'El nombre del documento es obligatorio')
  assert.equal(typeNameProblem('x'.repeat(121)), 'El nombre del documento no puede superar los 120 caracteres')
  assert.equal(typeNameProblem('x'.repeat(120)), null)
  assert.equal(typeNameProblem(' Visa '), null)
})

test('the document form needs an expiry date only when the type requires it', () => {
  assert.equal(documentFormProblem(true, '', ''), 'La fecha de vencimiento es obligatoria para este documento')
  assert.equal(documentFormProblem(true, '2027-13-40', ''), 'La fecha de vencimiento no es válida')
  assert.equal(documentFormProblem(true, '2027-02-30', ''), 'La fecha de vencimiento no es válida')
  assert.equal(documentFormProblem(true, '2028-02-29', ''), null)
  assert.equal(documentFormProblem(false, '', ''), null)
  assert.equal(documentFormProblem(false, 'basura', ''), null)
  assert.equal(MAX_NOTES_LENGTH, 1000)
  assert.equal(documentFormProblem(false, '', 'n'.repeat(1001)), 'Las notas no pueden superar los 1000 caracteres')
  assert.equal(documentFormProblem(false, '', 'n'.repeat(1000)), null)
})

test('the document payload drops the expiry that does not apply and blank notes', () => {
  assert.deepEqual(documentPayload(true, '2027-03-01', ' Trámite '), { expires_on: '2027-03-01', notes: 'Trámite' })
  assert.deepEqual(documentPayload(false, '2027-03-01', '  '), { expires_on: null, notes: null })
})

test('moving a type up or down gives its new position or nothing at the ends', () => {
  const types = [{ id: 7, position: 0 }, { id: 8, position: 1 }, { id: 9, position: 2 }]
  assert.equal(movePosition(types, 8, 'up'), 0)
  assert.equal(movePosition(types, 8, 'down'), 2)
  assert.equal(movePosition(types, 7, 'up'), null)
  assert.equal(movePosition(types, 9, 'down'), null)
  assert.equal(movePosition(types, 99, 'up'), null)
})
