import assert from 'node:assert/strict'
import test from 'node:test'

import {
  activeFilterCount,
  blockedReason,
  contractText,
  designationKpis,
  displayName,
  filterByStatus,
  semesterChipLabel,
  statusFilterCounts,
  weeklyHoursOf,
} from '../src/lib/designationListView.ts'

const row = (overrides = {}) => ({
  id: 1, status: 'active', monthly_hours: 8, has_contract: false, ...overrides,
})

const items = [
  row({ id: 1, monthly_hours: 8, has_contract: true }),
  row({ id: 2, monthly_hours: 12.5 }),
  row({ id: 3, status: 'finalized', monthly_hours: 4, has_contract: true }),
  row({ id: 4, status: 'finalized', monthly_hours: null }),
]

test('KPIs count designations by status, contract and add the monthly hours', () => {
  assert.deepEqual(designationKpis(items), { total: 4, active: 2, finalized: 2, monthlyHours: 24.5, withContract: 2 })
})

test('KPIs of an empty list are all zero', () => {
  assert.deepEqual(designationKpis([]), { total: 0, active: 0, finalized: 0, monthlyHours: 0, withContract: 0 })
})

test('status quick filter counts match the KPIs and the "all" bucket', () => {
  assert.deepEqual(statusFilterCounts(items), { all: 4, active: 2, finalized: 2 })
  assert.deepEqual(statusFilterCounts([]), { all: 0, active: 0, finalized: 0 })
})

test('filterByStatus keeps the order and returns everything for "all"', () => {
  assert.deepEqual(filterByStatus(items, 'all').map((i) => i.id), [1, 2, 3, 4])
  assert.deepEqual(filterByStatus(items, 'active').map((i) => i.id), [1, 2])
  assert.deepEqual(filterByStatus(items, 'finalized').map((i) => i.id), [3, 4])
  assert.deepEqual(filterByStatus([], 'active'), [])
})

test('uppercase names are shown in Title Case, mixed case names stay as written', () => {
  assert.equal(displayName('ANA MARÍA PÉREZ'), 'Ana María Pérez')
  assert.equal(displayName('JUAN DE LA CRUZ'), 'Juan de la Cruz')
  assert.equal(displayName("MARÍA O'BRIEN-LÓPEZ"), "María O'Brien-López")
  assert.equal(displayName('Ana Pérez'), 'Ana Pérez')
  assert.equal(displayName('de la Rosa'), 'de la Rosa')
  assert.equal(displayName('  '), '')
})

test('semester chip shows a short label for known semesters and the original text otherwise', () => {
  assert.equal(semesterChipLabel('PRIMERO'), '1.º sem')
  assert.equal(semesterChipLabel('Séptimo'), '7.º sem')
  assert.equal(semesterChipLabel('3'), '3.º sem')
  assert.equal(semesterChipLabel('Electiva'), 'Electiva')
})

test('active filter count ignores empty filters and the default status', () => {
  assert.equal(activeFilterCount({ search: '', period: '', semester: '', type: '', status: 'all' }, ''), 0)
  assert.equal(activeFilterCount({ search: '  ', period: '', semester: '', type: '', status: 'all' }, ''), 0)
  assert.equal(activeFilterCount({ search: 'ana', period: '', semester: 'PRIMERO', type: 'practice', status: 'active' }, ''), 4)
  assert.equal(activeFilterCount({ search: '', period: 'I/2026', semester: '', type: '', status: 'all' }, 'CI-1'), 2)
})

test('contract dates read as a range, with plain words for open ends', () => {
  assert.equal(contractText({ contract_start_date: null, contract_end_date: null }), 'Todo el período')
  assert.equal(contractText({ contract_start_date: '2026-08-10', contract_end_date: '2026-12-18' }), '10/08/2026 – 18/12/2026')
  assert.equal(contractText({ contract_start_date: '2026-08-10', contract_end_date: null }), '10/08/2026 – fin del período')
  assert.equal(contractText({ contract_start_date: null, contract_end_date: '2026-12-18' }), 'Inicio del período – 18/12/2026')
})

test('weekly hours fall back to the calculated value and then to a dash', () => {
  assert.equal(weeklyHoursOf({ weekly_hours: 4, weekly_hours_calculated: 2 }), 4)
  assert.equal(weeklyHoursOf({ weekly_hours: null, weekly_hours_calculated: 2 }), 2)
  assert.equal(weeklyHoursOf({ weekly_hours: null, weekly_hours_calculated: null }), '—')
})

test('the finalize reason is only reported when the action is blocked', () => {
  const actions = (finalize) => ({ actions: { finalize } })
  assert.equal(blockedReason(actions({ allowed: true, reason: null })), null)
  assert.equal(blockedReason(actions({ allowed: false, reason: 'Ya está finalizada.' })), 'Ya está finalizada.')
})
