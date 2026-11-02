import assert from 'node:assert/strict'
import test from 'node:test'

import {
  MAX_GROUP_SIZE,
  activeWindowId,
  capacityLabel,
  differenceBadge,
  groupOpeningQueryParams,
  groupSizePayload,
  groupSizeProblem,
  shiftLabel,
} from '../src/lib/groupOpeningState.ts'

const row = (patch = {}) => ({
  semester: 3, shift: 'M', requests: 0, retakers: 0, suggested_groups: 0, existing_groups: 0,
  existing_capacity: 0, groups_without_capacity: 0, difference: 0, status: 'correcto', label: 'Correcto', ...patch,
})

test('shifts have a Spanish label and unknown ones are shown as they are', () => {
  assert.equal(shiftLabel('M'), 'M Mañana')
  assert.equal(shiftLabel('T'), 'T Tarde')
  assert.equal(shiftLabel('N'), 'N Noche')
  assert.equal(shiftLabel('X'), 'X')
})

test('group size accepts whole numbers from 1 to 200 only', () => {
  assert.equal(MAX_GROUP_SIZE, 200)
  for (const good of ['1', '40', '200', ' 35 ']) assert.equal(groupSizeProblem(good), null, good)
  for (const bad of ['', '  ', '0', '-3', '201', '40.5', 'abc', '1e2', '4 0']) {
    assert.match(groupSizeProblem(bad) ?? '', /1 y 200/, bad)
  }
})

test('group size payload is a number and refuses invalid text', () => {
  assert.deepEqual(groupSizePayload(' 35 '), { group_size: 35 })
  assert.throws(() => groupSizePayload('0'))
})

test('the difference badge follows the backend status and keeps its label', () => {
  assert.deepEqual(differenceBadge(row({ status: 'faltan', difference: 2, label: 'Faltan 2 grupos' })),
    { label: 'Faltan 2 grupos', variant: 'error' })
  assert.deepEqual(differenceBadge(row({ status: 'sobran', difference: -1, label: 'Sobra 1 grupo' })),
    { label: 'Sobra 1 grupo', variant: 'warning' })
  assert.deepEqual(differenceBadge(row()), { label: 'Correcto', variant: 'success' })
})

test('capacity shows the known total and flags groups without a size', () => {
  assert.equal(capacityLabel(row({ existing_groups: 0 })), '—')
  assert.equal(capacityLabel(row({ existing_groups: 2, existing_capacity: 60 })), '60')
  assert.equal(capacityLabel(row({ existing_groups: 3, existing_capacity: 60, groups_without_capacity: 1 })), '60 + 1 sin capacidad')
  assert.equal(capacityLabel(row({ existing_groups: 2, existing_capacity: 0, groups_without_capacity: 2 })), 'Sin capacidad')
})

test('the active window is the chosen one, else the open one, else the first', () => {
  const windows = [
    { id: 3, term_code: 'II/2027', is_open: false }, { id: 2, term_code: 'I/2027', is_open: true },
    { id: 1, term_code: 'II/2026', is_open: false },
  ]
  assert.equal(activeWindowId(windows, undefined), 2)
  assert.equal(activeWindowId(windows, 1), 1)
  assert.equal(activeWindowId(windows, 99), 2)
  assert.equal(activeWindowId([{ ...windows[0] }], undefined), 3)
  assert.equal(activeWindowId([], undefined), undefined)
})

test('the query asks for the window only when there is one', () => {
  assert.deepEqual(groupOpeningQueryParams(4), { window_id: 4 })
  assert.deepEqual(groupOpeningQueryParams(undefined), {})
})
