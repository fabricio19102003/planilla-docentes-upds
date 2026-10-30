import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildIssuePayload,
  formatSpanishDate,
  toTermsForm,
  validateTermsForm,
} from '../src/lib/contractTermsForm.ts'
import {
  buildComitentePayload,
  COMITENTE_FIELDS,
  toComitenteForm,
  validateComitenteForm,
} from '../src/lib/contractComitenteForm.ts'

const terms = {
  academic_period: 'II/2026',
  period_start: '2026-07-01',
  period_end: '2026-12-31',
  default_start: '2026-08-10',
  default_end: '2026-12-18',
  contract_start_date: null,
  contract_end_date: null,
  signature_date: null,
}

test('form starts empty when no custom dates exist and prefilled when they do', () => {
  assert.deepEqual(toTermsForm(terms), { start: '', end: '', signature: '' })
  assert.deepEqual(
    toTermsForm({ ...terms, contract_start_date: '2026-08-21', signature_date: '2026-08-20' }),
    { start: '2026-08-21', end: '', signature: '2026-08-20' },
  )
})

test('empty form clears custom dates; filled fields are sent as dates', () => {
  assert.deepEqual(buildIssuePayload({ start: '', end: '', signature: '' }, 'Pando', 'II/2026'), {
    department: 'Pando',
    academic_period: 'II/2026',
    clear_custom_terms: true,
  })
  assert.deepEqual(
    buildIssuePayload({ start: '2026-08-21', end: '', signature: '2026-08-20' }, 'Beni', 'II/2026'),
    {
      department: 'Beni',
      academic_period: 'II/2026',
      contract_start_date: '2026-08-21',
      signature_date: '2026-08-20',
    },
  )
})

test('validation mirrors the server messages', () => {
  assert.equal(validateTermsForm({ start: '', end: '', signature: '' }, terms), null)
  assert.equal(validateTermsForm({ start: '2026-08-21', end: '2026-12-01', signature: '' }, terms), null)
  assert.equal(
    validateTermsForm({ start: '2026-12-01', end: '2026-11-30', signature: '' }, terms),
    'La fecha de inicio del contrato no puede ser posterior a la fecha de fin.',
  )
  assert.equal(
    validateTermsForm({ start: '2026-12-19', end: '', signature: '' }, terms),
    'La fecha de inicio del contrato no puede ser posterior a la fecha de fin.',
  )
  assert.equal(
    validateTermsForm({ start: '2026-06-30', end: '', signature: '' }, terms),
    'Las fechas del contrato deben estar dentro del período II/2026 (01 de julio de 2026 al 31 de diciembre de 2026).',
  )
  assert.equal(formatSpanishDate('2026-02-05'), '05 de febrero de 2026')
})

const settings = {
  contract_representative_name: 'Luis Michel Bravo Alencar',
  contract_representative_ci: '1750986 Pando',
  contract_power_number: '1818/2024',
  contract_power_date: '2024-09-04',
  contract_notary_office: '10',
  contract_notary_name: 'Jaime David Canedo Encinas',
  contract_city: 'Cobija',
}

test('comitente form sends only trimmed changed fields', () => {
  assert.equal(COMITENTE_FIELDS.length, 7)
  const form = toComitenteForm(settings)
  assert.deepEqual(buildComitentePayload(form, settings), {})
  assert.deepEqual(
    buildComitentePayload(
      { ...form, contract_representative_name: '  Ana Suárez ', contract_city: 'Riberalta' },
      settings,
    ),
    { contract_representative_name: 'Ana Suárez', contract_city: 'Riberalta' },
  )
})

test('comitente form rejects blank fields with the field label', () => {
  const form = toComitenteForm(settings)
  assert.equal(validateComitenteForm(form), null)
  assert.equal(
    validateComitenteForm({ ...form, contract_notary_name: '   ' }),
    'El campo "Notario" no puede estar vacío.',
  )
})
